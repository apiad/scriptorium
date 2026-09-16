# Independent cells, `continue` chains, and readable errors

*Status: implemented. 2026-09-16.*

Executed code blocks share one accumulated session per file today. That model has
three defects, all reproduced on 2026-09-16 with a three-block document
(`x = 1; print(x)`, then `int("3.5")`, then `print(x + 1)`):

1. **A failing block poisons every later block.** `ExecEnv.run` appends every
   block's source to `session[lang]`, including the one that raised. Each later
   block re-runs the failing source first and raises the same exception. Because
   the exception fires before the sentinel print, the later block's output also
   carries the stdout of every earlier block: the third block above rendered `1`
   followed by the `ValueError` traceback instead of `2`.
2. **Tracebacks are wrong.** Python reads the assembled program on stdin, so the
   traceback says `File "<stdin>", line 4` for a one-line block (the line number
   counts earlier blocks and the sentinel) and shows neither the source line nor
   the `~~~^^^` markers, because there is no source file to read.
3. **Errors look like output.** A failing block renders as the same
   `<pre class="output">` as a successful one, with the accent-coloured border.

The shared session was added in `2c9c416` (2026-07-28) so that *The Algorithm
Codex* would render, overriding the lock in `docs/design.md` §5.2: "No cumulative
session mode — sessions reintroduce hidden order-dependence." This design returns
to independent blocks and makes shared state explicit and local.

## Goals

- Every executed block runs in a clean process by default.
- A block marked `continue` runs on top of the state left by the preceding
  executed block of the same language, and chains form by repeating the mark.
- A failing block never contributes state to a chain.
- Python tracebacks number lines from the block's own first line and show the
  offending source line with its markers.
- A failing block renders visibly as an error, in red, in every theme.
- *The Algorithm Codex* renders with identical cell outputs after migration.

## Non-goals

- Named sessions (`session=name`). `continue` covers every dependency in the
  Codex. Named sessions can be added later on top of chains without breaking them.
- Partial state from a failing block, as Jupyter keeps it. A failing block's state
  is discarded whole.
- Line-accurate tracebacks for bash and node. They get the chain semantics and the
  error styling, not a driver.
- Quarto compatibility for state. Quarto shares state across cells by default;
  after this change a Quarto document that relies on it needs `continue` marks.

## Syntax

`continue` is a bare flag in the fence attributes, in both fence forms:

````markdown
```{python continue}
print(total)
```

```python {run continue}
print(f"| {total} |")
```
````

`parse_fence` in `scriptorium/fence.py` sets a new `Fence.cont: bool` field
(`continue` is a Python keyword, so the field cannot use the name) when `continue`
is in the flags. A `continue` flag on a block that does not run is ignored.

## Chain semantics

`ExecEnv` replaces `session: dict[str, str]` with `chain: dict[str, list[str]]`,
the sources of the successful blocks in the current chain, per language, plus
`ran: set[str]`, the languages that have executed at least one block in the
current file.

For each executed block of language `L`:

1. If the block is not marked `continue`, the chain for `L` is empty for this run.
2. If it is marked `continue` and `L` is not in `ran`, the block runs with an empty
   chain and the environment records a warning (see below).
3. The block runs on top of the chain.
4. If the block succeeds, its source is appended to the chain it ran on, and that
   becomes `chain[L]`. A block not marked `continue` therefore starts a new chain
   of one.
5. If the block fails, `chain[L]` becomes the chain the block ran on: unchanged
   for a `continue` block, empty for an unmarked one. A later `continue` block
   resumes from the state the failed block started from.
6. `L` is added to `ran` either way.

`ExecEnv.reset_session()` keeps its name and its two call sites in `parse.py`
(`\newpage` and `::: newpage`) and clears both `chain` and `ran`. A chain never
crosses a file boundary in a project, because `project.py` separates files with
`\newpage`.

Blocks with `echo=false` still execute, so they join chains like any other block.

### The warning

A `continue` with nothing to continue is almost always a block moved away from
its chain. The render still succeeds and the block runs clean, but `ExecEnv`
appends to a new `warnings: list[str]`, which `render_pdf` in `galley.py` adds to
the report's warnings after `parse` returns. The message quotes the block's first
non-blank source line, since `parse` does not track source line numbers:

```
warning: `continue` block has no earlier python block in this file to continue: print(total)
```

## Run results

`ExecEnv.run(source, lang, cont=False)` returns a `RunResult` dataclass instead of
a string:

```python
@dataclass
class RunResult:
    stdout: str
    stderr: str      # empty on success
    failed: bool
```

`allow_error=False` keeps raising `ExecError` on failure, unchanged.

The freeze cache stores `{"stdout": ..., "stderr": ..., "failed": ...}`. A cached
plain string, written by an older version, reads as `RunResult(stdout=value,
stderr="", failed=False)`, so old caches stay valid. The cache key hashes the
interpreter, the pythonpath, the chain sources and the block source, which is what
the key covers today through the assembled program.

A cache hit must also update the chain, as the current code already does for the
session, and it must do so using the cached `failed` flag.

## Execution

### Python: the driver

When the interpreter for the block's language is the default Python command
(`DEFAULT_INTERPRETERS["python"]`, used for `python` and `py`), the environment
does not send the assembled program. It sends a driver script on stdin that
carries the chain and the block as string literals:

```python
import contextlib, io, linecache, sys, traceback

CHAIN = [...]          # repr() of each chain source
CELL = "..."           # repr() of the block source

ns = {"__name__": "__main__"}
with contextlib.redirect_stdout(io.StringIO()):
    for i, src in enumerate(CHAIN):
        exec(compile(src, f"<chain-{i}>", "exec"), ns)

linecache.cache["<cell>"] = (len(CELL), None, CELL.splitlines(True), "<cell>")
try:
    exec(compile(CELL, "<cell>", "exec"), ns)
except SystemExit as e:
    if e.code not in (None, 0):
        raise
except BaseException as e:
    tb = e.__traceback__
    while tb is not None and tb.tb_frame.f_code.co_filename != "<cell>":
        tb = tb.tb_next
    traceback.print_exception(type(e), e, tb)
    sys.exit(1)
```

What each part buys:

- **Silent chain.** Chain blocks run with stdout discarded, so a block's output
  never includes its predecessors' output. This removes the sentinel marker for
  Python.
- **Cell-relative line numbers.** The block compiles under the filename `<cell>`,
  so line 1 of the traceback is line 1 of the block as the reader sees it.
- **Source lines and markers.** Registering the block in `linecache` lets Python
  3.11+ print the source line and the `~~~^^^` markers.
- **No driver frames.** The traceback starts at the first `<cell>` frame. A frame
  inside an imported module (a tangled `codex` function that raises) still
  appears, because it comes after the first `<cell>` frame. A `SyntaxError` in
  the block has no `<cell>` frame; `tb` ends as `None` and Python prints the
  file, line and caret from the exception itself.
- **`sys.exit()` in a block.** Exit code 0 or `None` counts as success.

A chain block that raises during replay cannot happen in normal use, since only
successful blocks enter a chain. If one does (a nondeterministic block), the
driver's traceback surfaces it and the block counts as failed.

The expected traceback for `int("3.5")`:

```
Traceback (most recent call last):
  File "<cell>", line 1, in <module>
    int("3.5")
    ~~~^^^^^^^
ValueError: invalid literal for int() with base 10: '3.5'
```

### Other languages and custom interpreters

Bash, node, and any interpreter overridden through `execute.interpreters` keep
the current assembly: the chain sources, then the sentinel print, then the block.
They gain the chain semantics (failures are left out, `continue` is explicit) and
the error styling. The sentinel print stays Python syntax for them, as today. A
non-Python chain with a failing block no longer leaks earlier output, because the
failing block is never replayed.

## Rendering

`_code_units` in `parse.py` uses the result:

- **Success.** Unchanged. Code mode emits `<pre class="output">`; asis mode
  re-parses stdout as Markdown.
- **Failure, either mode.** Emit
  `<pre class="output error">{escape(stdout)}<span class="stderr">{escape(stderr)}</span></pre>`.
  An asis block that fails therefore shows its traceback in the error block
  instead of feeding it to the Markdown parser. Stdout printed before the failure
  stays visible in the normal output colour.

`themes/base/styles.css` gains an `--error` variable next to `--accent` and one
rule:

```css
--error: #b42318;

pre.output.error { border-left-color: var(--error); }
pre.output.error .stderr { color: var(--error); }
```

`pre.output.error` is more specific than the `pre.output` rules in the `book` and
`report` themes, so both inherit the red border without edits. A theme changes the
colour by redefining `--error`.

## Migrating The Algorithm Codex

A measurement on 2026-09-16 (`.playground/scriptorium-cells/measure.py` in the
workspace) ran each of the Codex's 159 executed cells in isolation, with
`PYTHONPATH` set to the tangled `src/`. 129 pass. 30 fail with `NameError`, across
18 chapters (`03_sort`, `08_memory`, `11_queue`, `12_hash`, `13_bloom`,
`15_binary_trees`, `16_bst`, `17_avl`, `18_treap`, `22_fenwick`, `23_brute`,
`25_kmp`, `26_boyer_moore`, `27_rabin_karp`, `29_suffix_array`, `31_graph_rep`,
`33_dfs`, `34_dijkstra`).

The migration adds `continue` to every executed block from the block after the
one that defines a missing name up to the last block that uses it. Blocks that do
not need the mark do not get it.

Verification does not depend on reading the PDF:

1. Before any engine change, dump every executed cell's output from the Codex
   with the current engine, keyed by file and cell index, to a JSON file.
2. After the engine change and the migration, dump again with the new engine.
3. The two dumps must be identical for every cell that succeeds in the first dump.
   A cell that failed before the change is listed and inspected by hand; its
   output is allowed to change only by gaining the new traceback format.

The Codex commit lands in `repos/books-codex` after the scriptorium release it
depends on.

## Tests

Written first, in `tests/test_exec.py`, and each must fail against the current
engine before the implementation lands:

- An unmarked block after a block that defines `x` gets `NameError`.
- A chain of three blocks marked `continue` sees names from all earlier links.
- A `continue` block after a failing block sees the state from before the failure
  and prints its own output only.
- A failing Python block's traceback contains `line 1`, the block's source line,
  and no `<stdin>` or driver frame.
- A `SyntaxError` block reports the block's own line number.
- A failing block renders with `class="output error"` and a `stderr` span; a
  failing asis block renders the same way.
- A `continue` block with no earlier block in the file runs clean and produces one
  warning; a `continue` right after `\newpage` does too.
- The freeze cache round-trips `failed=True`, and a legacy string entry reads as a
  success.
- `sys.exit(0)` in a block counts as success.

`test_session_state_shared_across_blocks` is replaced by the chain test;
`test_session_resets_on_newpage` keeps its intent with `continue` added to its
second block.

Mutation check before commit: make the environment append failing blocks to the
chain, and confirm the failure-recovery test goes red; make the driver skip the
`linecache` registration, and confirm the traceback test goes red.

## Documentation and release

- `docs/design.md` §5.2: replace the "Locked" paragraph with this model and its
  reason. Shared state is explicit and local to the block that needs it, and noweb
  assembly remains the way to share code without replaying it.
- `README.md`: document `continue` next to `{run}`.
- `CHANGELOG.md`: a breaking-change entry under Unreleased. The next release is
  v0.10.0 (current: v0.9.0).
- `repos/programming/conferences/2026/01-python-basico/notas.md`: turn the static
  `int("3.5")`, `int("hola")`, `"5" + 3` and `print(radio)` tracebacks back into
  executed blocks and re-render, as the acceptance check on a real document. The
  examples that read from `input` stay static.
