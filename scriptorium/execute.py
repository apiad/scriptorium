"""Run a code block in a subshell and capture stdout.

The subshell contract: feed the (assembled) source on stdin to the language's
interpreter, capture stdout, and hand it back for splicing. No kernel, no state
carried between blocks — state flows through tangled/installed source (a document
importing a package it tangled) or through noweb assembly, or (for cells within a
document) through accumulated per-file session state.
"""

import os
import subprocess
from dataclasses import dataclass, field

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


_MARK = "\x00SCRIPTORIUM_CELL\x00"


@dataclass
class ExecEnv:
    cwd: str | None = None
    timeout: float = 30.0
    interpreters: dict = field(default_factory=lambda: dict(DEFAULT_INTERPRETERS))
    freeze: object | None = None
    allow_error: bool = True  # capture a failing block's traceback vs crashing the build
    pythonpath: list = field(default_factory=list)  # dirs prepended for imports
    session: dict = field(default_factory=dict)  # per-language accumulated source

    def reset_session(self) -> None:
        """New document/chapter: forget prior cells (Quarto resets state per file)."""
        self.session.clear()

    def _env(self) -> dict:
        if not self.pythonpath:
            return None
        env = dict(os.environ)
        existing = env.get("PYTHONPATH", "")
        parts = list(self.pythonpath) + ([existing] if existing else [])
        env["PYTHONPATH"] = os.pathsep.join(parts)
        return env

    def run(self, source: str, lang: str) -> str:
        cmd = self.interpreters.get(lang)
        if cmd is None:
            raise ExecError(f"no interpreter configured for language '{lang}'")
        # emulate a shared kernel: prepend prior cells' source, but capture only
        # this cell's stdout (everything after a sentinel print).
        prior = self.session.get(lang, "")
        full = f"{prior}\nprint({_MARK!r}, end='')\n{source}" if prior else source

        cache_key = None
        if self.freeze is not None:
            cache_key = self.freeze.key(" ".join(cmd) + "|".join(self.pythonpath), full)
            hit = self.freeze.get(cache_key)
        else:
            hit = None

        if hit is not None:
            out = hit
        else:
            try:
                proc = subprocess.run(
                    cmd, input=full, capture_output=True, text=True,
                    cwd=self.cwd, timeout=self.timeout, env=self._env(),
                )
            except subprocess.TimeoutExpired as e:
                raise ExecError(f"{lang} block timed out after {self.timeout}s") from e
            out = proc.stdout
            if _MARK in out:
                out = out.split(_MARK, 1)[1]
            if proc.returncode != 0:
                if not self.allow_error:
                    raise ExecError(
                        f"{lang} block failed (exit {proc.returncode}):\n{proc.stderr.strip()}")
                out += proc.stderr
            if cache_key is not None:
                self.freeze.set(cache_key, out)

        # accumulate this cell into the session regardless of cache outcome
        self.session[lang] = f"{prior}\n{source}" if prior else source
        return out
