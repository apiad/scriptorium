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
