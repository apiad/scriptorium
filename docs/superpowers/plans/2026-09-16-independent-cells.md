# Independent cells, `continue` chains, and readable errors: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Executed blocks run independently by default, `continue` chains them, a
failing block never poisons later blocks, and errors render as readable red
tracebacks.

**Architecture:** `Fence` gains a `cont` flag. `ExecEnv.run` returns a `RunResult`
and keeps a per-language chain of successful sources instead of an accumulated
session. Python blocks run through a driver script that replays the chain silently
and compiles the block as `<cell>`. `parse._code_units` renders failures as
`<pre class="output error">`, styled in the `base` theme.

**Tech Stack:** Python 3.12+, pytest via `uv run pytest`, WeasyPrint themes (CSS).

**Spec:** `docs/superpowers/specs/2026-09-16-independent-cells-design.md`

## Global Constraints

- English throughout the engine: code, comments, tests, commit messages.
- `uv run pytest` must pass before any commit lands.
- The error colour is `--error: #b42318`, defined in `themes/base/styles.css`.
- The traceback filename for a block is `<cell>`.
- Next release is v0.10.0 (current v0.9.0); this plan only writes the CHANGELOG
  entry under Unreleased, it does not cut the release.
- `uv.lock` in this repo carries another session's change: never stage it.
- Migration baseline: `/home/apiad/Workspace/.playground/scriptorium-cells/baseline.json`,
  159 cells, 0 tracebacks, dumped with the pre-change engine by `dump.py` in the
  same folder.

---

### Task 1: The `continue` flag

**Files:**
- Modify: `scriptorium/fence.py` (`Fence`, `parse_fence`)
- Test: `tests/test_exec.py`

**Interfaces:**
- Produces: `Fence.cont: bool`, default `False`.

- [x] **Step 1: Write the failing test** (append to `tests/test_exec.py`)

```python
def test_parse_fence_continue_flag():
    assert parse_fence("{python continue}").cont is True
    assert parse_fence("python {run continue}").cont is True
    assert parse_fence("{python}").cont is False
```

- [x] **Step 2: Run it and see it fail**

Run: `uv run pytest tests/test_exec.py::test_parse_fence_continue_flag -q`
Expected: FAIL, `AttributeError: 'Fence' object has no attribute 'cont'`.

- [x] **Step 3: Implement**

In `Fence`, after `output_mode`:

```python
    cont: bool = False  # `continue`: run on top of the previous block's chain
```

In `parse_fence`, after the `run` flag check:

```python
    if "continue" in flags:
        f.cont = True
```

- [x] **Step 4: Run it and see it pass**

Run: `uv run pytest tests/test_exec.py::test_parse_fence_continue_flag -q`
Expected: PASS.

- [x] **Step 5: Commit** — `feat(fence): parse the continue flag`, staging
  `scriptorium/fence.py tests/test_exec.py`.

---

### Task 2: `RunResult`, chains, driver, freeze format

**Files:**
- Modify: `scriptorium/execute.py` (whole module)
- Modify: `scriptorium/parse.py` (`_code_units`)
- Modify: `scriptorium/galley.py` (`render_pdf`, after `units = parse(...)`)
- Modify: `scriptorium/freeze.py` (docstring only)
- Test: `tests/test_exec.py`

**Interfaces:**
- Consumes: `Fence.cont`.
- Produces: `RunResult(stdout: str, stderr: str = "", failed: bool = False)`;
  `ExecEnv.run(source: str, lang: str, cont: bool = False) -> RunResult`;
  `ExecEnv.warnings: list[str]`; `ExecEnv.chain: dict[str, list[str]]`;
  `ExecEnv.ran: set[str]`; `ExecEnv.reset_session()` clears `chain` and `ran`.

- [x] **Step 1: Write the failing tests**

Replace `test_session_state_shared_across_blocks` and
`test_session_resets_on_newpage` with the following, and add the rest:

```python
from scriptorium.execute import RunResult
from scriptorium.freeze import Freeze


def _outputs(units):
    return [u.html for u in units if u.name == "output"]


def test_blocks_are_independent_by_default(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```{python}\nx = 1\n```\n\n```{python}\nprint(x)\n```', env=env)
    assert "NameError" in "".join(_outputs(units))


def test_continue_chains_blocks(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```{python}\na = 1\nprint("first")\n```\n\n'
                  '```{python continue}\nb = a + 1\n```\n\n'
                  '```{python continue}\nprint(a + b)\n```', env=env)
    outs = _outputs(units)
    assert len(outs) == 2
    assert "3" in outs[1] and "first" not in outs[1]


def test_continue_after_failure_resumes_prior_state(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```{python}\nx = 1\nprint("one")\n```\n\n'
                  '```{python continue}\nx = 99\nint("3.5")\n```\n\n'
                  '```{python continue}\nprint(x + 1)\n```', env=env)
    outs = _outputs(units)
    assert len(outs) == 3
    assert "ValueError" in outs[1]
    assert "2" in outs[2] and "Traceback" not in outs[2] and "one" not in outs[2]


def test_continue_without_predecessor_warns(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```{python continue}\nprint(41 + 1)\n```', env=env)
    assert "42" in "".join(_outputs(units))
    assert len(env.warnings) == 1 and "print(41 + 1)" in env.warnings[0]


def test_continue_does_not_cross_newpage(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```{python}\nx = 1\n```\n\n\\newpage\n\n'
                  '```{python continue}\nprint(x)\n```', env=env)
    assert "NameError" in "".join(_outputs(units))
    assert len(env.warnings) == 1


def test_python_traceback_is_cell_relative(tmp_path):
    r = ExecEnv(cwd=str(tmp_path)).run('x = 1\nint("3.5")', "python")
    assert r.failed
    assert 'File "<cell>", line 2' in r.stderr
    assert 'int("3.5")' in r.stderr and "^" in r.stderr
    assert "<stdin>" not in r.stderr and "_scriptorium_driver" not in r.stderr


def test_syntax_error_reports_cell_line(tmp_path):
    r = ExecEnv(cwd=str(tmp_path)).run("x = 1\ny = (2,\n", "python")
    assert r.failed and "SyntaxError" in r.stderr
    assert 'File "<cell>", line 2' in r.stderr


def test_sys_exit_zero_is_success(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    ok = env.run('import sys\nprint("a")\nsys.exit(0)', "python")
    assert ok == RunResult("a\n", "", False)
    assert env.run("import sys\nsys.exit(3)", "python").failed


def test_freeze_roundtrips_failure(tmp_path):
    src = 'raise ValueError("boom")'
    r1 = ExecEnv(cwd=str(tmp_path), freeze=Freeze(tmp_path / "f.json")).run(src, "python")
    r2 = ExecEnv(cwd=str(tmp_path), freeze=Freeze(tmp_path / "f.json")).run(src, "python")
    assert r1.failed and "boom" in r1.stderr
    assert r2 == r1


def test_freeze_legacy_string_entry_reads_as_success(tmp_path):
    fz = Freeze(tmp_path / "f.json")
    fz.get = lambda key: "legacy\n"
    r = ExecEnv(cwd=str(tmp_path), freeze=fz).run("print(1)", "python")
    assert r == RunResult("legacy\n", "", False)
```

Update `test_freeze_cache_avoids_rerun` only if it breaks: it compares two
`run` results with `==`, which a dataclass supports.

- [x] **Step 2: Run them and see them fail**

Run: `uv run pytest tests/test_exec.py -q`
Expected: the new tests fail (`ImportError: cannot import name 'RunResult'` stops
collection first).

- [x] **Step 3: Rewrite `scriptorium/execute.py`**

```python
"""Run a code block in a subshell and capture its output.

Every block runs in a fresh process. A block marked `continue` runs on top of a
chain: the sources of the successful blocks since the last unmarked one, replayed
silently before it. A failing block never joins a chain. Chains reset at each
file or chapter boundary (`reset_session`).

Python blocks run through a driver that compiles the block as `<cell>`, so a
traceback numbers lines from the block's first line and shows the source line.
Other languages get the chain replayed as a plain program with a sentinel.
"""

import os
import subprocess
from dataclasses import asdict, dataclass, field

DEFAULT_INTERPRETERS = {
    "python": ["python3", "-"],
    "py": ["python3", "-"],
    "bash": ["bash", "-s"],
    "sh": ["sh", "-s"],
    "node": ["node", "-"],
    "js": ["node", "-"],
}


class ExecError(RuntimeError):
    pass


@dataclass
class RunResult:
    stdout: str
    stderr: str = ""  # empty on success
    failed: bool = False


_MARK = "\x00SCRIPTORIUM_CELL\x00"

_DRIVER = '''\
def _scriptorium_driver(chain, cell):
    import contextlib, io, linecache, sys, traceback
    ns = sys.modules["__main__"].__dict__
    del ns["_scriptorium_driver"]
    with contextlib.redirect_stdout(io.StringIO()):
        for i, src in enumerate(chain):
            exec(compile(src, f"<chain-{i}>", "exec"), ns)
    linecache.cache["<cell>"] = (len(cell), None, cell.splitlines(True), "<cell>")
    try:
        exec(compile(cell, "<cell>", "exec"), ns)
    except SystemExit as e:
        if e.code not in (None, 0):
            raise
    except BaseException as e:
        tb = e.__traceback__
        while tb is not None and tb.tb_frame.f_code.co_filename != "<cell>":
            tb = tb.tb_next
        sys.stdout.flush()
        traceback.print_exception(type(e), e, tb)
        sys.exit(1)

_scriptorium_driver(%r, %r)
'''


@dataclass
class ExecEnv:
    cwd: str | None = None
    timeout: float = 30.0
    interpreters: dict = field(default_factory=lambda: dict(DEFAULT_INTERPRETERS))
    freeze: object | None = None
    allow_error: bool = True  # capture a failing block's traceback vs crashing the build
    pythonpath: list = field(default_factory=list)  # dirs prepended for imports
    chain: dict = field(default_factory=dict)  # lang -> sources of the current chain
    ran: set = field(default_factory=set)  # langs that ran a block in this file
    warnings: list = field(default_factory=list)

    def reset_session(self) -> None:
        """New document/chapter: chains never cross a file boundary."""
        self.chain.clear()
        self.ran.clear()

    def _env(self) -> dict:
        if not self.pythonpath:
            return None
        env = dict(os.environ)
        existing = env.get("PYTHONPATH", "")
        parts = list(self.pythonpath) + ([existing] if existing else [])
        env["PYTHONPATH"] = os.pathsep.join(parts)
        return env

    def run(self, source: str, lang: str, cont: bool = False) -> RunResult:
        cmd = self.interpreters.get(lang)
        if cmd is None:
            raise ExecError(f"no interpreter configured for language '{lang}'")
        if cont and lang not in self.ran:
            first = next((ln.strip() for ln in source.splitlines() if ln.strip()), "")
            self.warnings.append(
                f"`continue` block has no earlier {lang} block in this file to continue: {first}")
        chain = list(self.chain.get(lang, [])) if cont else []

        driven = cmd == DEFAULT_INTERPRETERS["python"]
        if driven:
            program = _DRIVER % (chain, source)
        elif chain:
            program = "\n".join(chain) + f"\nprint({_MARK!r}, end='')\n" + source
        else:
            program = source

        cache_key = None
        hit = None
        if self.freeze is not None:
            cache_key = self.freeze.key(" ".join(cmd) + "|".join(self.pythonpath), program)
            hit = self.freeze.get(cache_key)

        if hit is not None:
            result = RunResult(hit) if isinstance(hit, str) else RunResult(**hit)
        else:
            try:
                proc = subprocess.run(
                    cmd, input=program, capture_output=True, text=True,
                    cwd=self.cwd, timeout=self.timeout, env=self._env(),
                )
            except subprocess.TimeoutExpired as e:
                raise ExecError(f"{lang} block timed out after {self.timeout}s") from e
            out = proc.stdout
            if not driven and _MARK in out:
                out = out.split(_MARK, 1)[1]
            failed = proc.returncode != 0
            if failed and not self.allow_error:
                raise ExecError(
                    f"{lang} block failed (exit {proc.returncode}):\n{proc.stderr.strip()}")
            result = RunResult(out, proc.stderr if failed else "", failed)
            if cache_key is not None:
                self.freeze.set(cache_key, asdict(result))

        # a failing block leaves the chain it ran on; a success extends it
        self.chain[lang] = chain if result.failed else chain + [source]
        self.ran.add(lang)
        return result
```

Note on the chain after a failure: the spec says "`chain[L]` is left as it was
before the block". For a `continue` block that is the same list. For an unmarked
failing block, this plan sets the chain to the empty chain it ran on, so a later
`continue` never resumes a chain the failed block had already broken. Update the
spec's step 5 wording in the docs task.

- [x] **Step 4: Adapt `_code_units` in `scriptorium/parse.py`**

Replace the `if f.run and env is not None:` block with:

```python
    if f.run and env is not None:
        res = env.run(body, f.lang, cont=f.cont)
        if res.failed:
            stdout = res.stdout if not res.stdout or res.stdout.endswith("\n") else res.stdout + "\n"
            units.append(Unit(
                html=(f'<pre class="output error">{escape(stdout)}'
                      f'<span class="stderr">{escape(res.stderr)}</span></pre>'),
                name="output"))
        elif res.stdout.strip():
            if f.output_mode == "code":
                units.append(Unit(html=f'<pre class="output">{escape(res.stdout)}</pre>', name="output"))
            else:  # asis: stdout is raw markdown, re-parsed
                units.extend(parse(res.stdout, theme, env))
```

- [x] **Step 5: Surface the warnings in `render_pdf`** (`scriptorium/galley.py`),
  right after `units = parse(src, theme, env, meta=meta)`:

```python
    if env is not None:
        warnings = warnings + env.warnings
```

- [x] **Step 6: Update the `freeze.py` docstring** first line to
  `"""Freeze cache: content-hash of (interpreter + program) -> captured run result.`

- [x] **Step 7: Run the exec tests, then the whole suite**

Run: `uv run pytest tests/test_exec.py -q`, then `uv run pytest -q`.
Expected: all pass.

- [x] **Step 8: Mutation check**

1. In `run`, change `chain if result.failed else chain + [source]` to
   `chain + [source]`. Run `uv run pytest tests/test_exec.py -q`; expect
   `test_continue_after_failure_resumes_prior_state` to fail. Revert.
2. In `_DRIVER`, delete the `linecache.cache[...]` line. Expect
   `test_python_traceback_is_cell_relative` to fail. Revert.
3. Clear `.pyc` caches (`find . -name __pycache__ -exec rm -rf {} +`) before each
   run, since a same-second same-size edit can serve a stale bytecode file.

- [x] **Step 9: Commit** — `feat(exec)!: independent blocks, continue chains, cell-relative tracebacks`,
  staging `scriptorium/execute.py scriptorium/parse.py scriptorium/galley.py scriptorium/freeze.py tests/test_exec.py`.

---

### Task 3: Render failures in red

**Files:**
- Modify: `themes/base/styles.css` (`:root`, code + executed output block)
- Test: `tests/test_exec.py`

**Interfaces:**
- Consumes: `<pre class="output error">` with `<span class="stderr">` from Task 2.

- [x] **Step 1: Write the failing tests**

```python
def test_failure_renders_error_block(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```{python}\nprint("before")\nint("x")\n```', env=env)
    [html] = _outputs(units)
    assert 'class="output error"' in html and 'class="stderr"' in html
    assert html.index("before") < html.index("stderr")


def test_asis_failure_is_not_parsed_as_markdown(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    units = parse('```python {run}\nprint("# heading")\nraise ValueError("x")\n```', env=env)
    assert any('class="output error"' in h for h in _outputs(units))
    assert not any("<h1" in u.html for u in units)


def test_base_theme_styles_errors():
    from scriptorium.theme import load_theme

    css = load_theme("note").css
    assert "--error:#b42318" in css.replace(" ", "")
    assert "pre.output.error" in css
```

Both parse tests already pass after Task 2 (the HTML landed there); they pin the
behaviour. The CSS test fails.

- [x] **Step 2: Run** `uv run pytest tests/test_exec.py -q` and see the theme test fail.

- [x] **Step 3: Implement the CSS** in `themes/base/styles.css`.

In `:root`, change `--accent:#2563eb; --accent-dark:#1e40af;` to
`--accent:#2563eb; --accent-dark:#1e40af; --error:#b42318;`.

After the `pre.output { ... }` rule add:

```css
pre.output.error { border-left-color:var(--error); }
pre.output.error .stderr { color:var(--error); }
```

- [x] **Step 4: Run** `uv run pytest -q`. Expected: all pass.

- [x] **Step 5: Visual check.** Render the three-block reproduction from the spec
  with the `note`, `book` and `report` themes into `/tmp`, rasterise with
  `pdftoppm -r 70 -png`, and look at the images: red border and red traceback,
  stdout in the normal colour, third block prints `2` once its middle neighbour
  is marked `continue`.

- [x] **Step 6: Commit** — `feat(themes): render failing blocks in red`, staging
  `themes/base/styles.css tests/test_exec.py`.

---

### Task 4: Migrate The Algorithm Codex

**Files (in `/home/apiad/Workspace/repos/books-codex`):**
- Modify: the 18 chapters listed in the spec, adding `continue` flags.

- [x] **Step 1: Dump with the new engine, before marking anything**

Run from `repos/scriptorium`:
`uv run --inexact python /home/apiad/Workspace/.playground/scriptorium-cells/dump.py ../books-codex/scriptorium.yaml /home/apiad/Workspace/.playground/scriptorium-cells/unmarked.json`

Every cell whose `failed` is true in `unmarked.json` needs a chain.

- [x] **Step 2: Mark the chains.** For each failing cell, find the block that
  defines the missing name (earlier in the same chapter) and add `continue` to
  every executed block after it, up to and including the failing cell. Use the
  Quarto form `{python continue}` for `{python}` blocks and add the flag inside the
  braces for native `{run}` blocks.

- [x] **Step 3: Dump again** into `migrated.json` with the same command.

- [x] **Step 4: Compare**

```python
import json
b = json.load(open("baseline.json")); m = json.load(open("migrated.json"))
assert len(b) == len(m) == 159
diff = [i for i, (x, y) in enumerate(zip(b, m)) if x["stdout"] != y["stdout"] or y["failed"]]
print(diff)
```

Expected: `[]`. Any index listed is inspected and fixed before moving on.

- [x] **Step 5: Render the book** with `scriptorium render scriptorium.yaml` and
  confirm no traceback appears: `pdftotext book.pdf - | grep -c Traceback` prints `0`.

- [x] **Step 6: Commit in `repos/books-codex`** —
  `chore(exec): mark continue chains for scriptorium independent cells`, staging
  the modified chapter files and `book.pdf` by name.

---

### Task 5: Documentation and the lecture notes

**Files:**
- Modify: `docs/design.md` §5.2 (the "Locked" paragraph) and §5.3 "Errors" bullet
- Modify: `README.md` (the code bullet near `python {run}`)
- Modify: `CHANGELOG.md` (Unreleased)
- Modify: `docs/superpowers/specs/2026-09-16-independent-cells-design.md` (status line, step 5 wording)
- Modify: `/home/apiad/Workspace/repos/programming/conferences/2026/01-python-basico/notas.md`

- [x] **Step 1: `design.md` §5.2.** Replace the "Locked" paragraph with:

```markdown
**Locked:** blocks are independent by default. Shared state is explicit and local:
a block marked `continue` runs on top of the chain of successful blocks before it,
and a chain never crosses a file boundary or includes a failing block. Noweb
assembly remains the way to share code without replaying it. (Revised 2026-09-16;
see `docs/superpowers/specs/2026-09-16-independent-cells-design.md`.)
```

and in §5.3 change the Errors bullet to say failures render as a red
`output error` block with a cell-relative traceback, with `allow_error=False`
failing the build.

- [x] **Step 2: `README.md`.** Extend the code bullet with one sentence:
  "Blocks run independently; mark a block `continue` to run it on top of the
  blocks before it, and a failing block shows its traceback in red."

- [x] **Step 3: `CHANGELOG.md`.** Under `## [Unreleased]`, add a `### Breaking`
  section above `### Features`:

```markdown
### Breaking

- **Executed blocks are independent; `continue` chains them.** Blocks no longer
  share one accumulated session per file. A block that needs names from an earlier
  one carries `continue` (`{python continue}`, `python {run continue}`). The shared
  session let one failing block re-raise in every later block of the file and
  leak their earlier output; a failing block now never joins a chain. Python
  tracebacks number lines from the block's first line and show the source line,
  and failing blocks render in red (`--error` in the base theme).
```

- [x] **Step 4: Spec status** → `*Status: implemented. 2026-09-16.*`, and step 5
  of the chain semantics → "If the block fails, `chain[L]` becomes the chain the
  block ran on: unchanged for a `continue` block, empty for an unmarked one."

- [x] **Step 5: Run** `uv run pytest -q` (docs-only, but it gates the commit), then
  commit — `docs: independent cells and continue chains`, staging the four doc
  files by name.

- [x] **Step 6: Lecture notes.** In `notas.md`, replace the static text blocks for
  `print(radio)`, `int("3.5")`, `int("hola")` and `"5" + 3` with executed
  `{python}` blocks holding just that code, and drop the `$ python radio.py` /
  `>>>` framing the static blocks carried. Leave the `input` examples and the
  `raices.py` run static. Re-render, rasterise the pages with the four errors and
  look at them. Commit in `repos/programming` —
  `docs(conferences): execute the error examples in lecture 1 notes`, staging
  `notas.md` and `notas.pdf`.
