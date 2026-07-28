"""Run a code block in a subshell and capture stdout.

The subshell contract: feed the (assembled) source on stdin to the language's
interpreter, capture stdout, and hand it back for splicing. No kernel, no state
carried between blocks — state flows through tangled/installed source (the way
the Codex imports its `codex` package) or through noweb assembly.
"""

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


@dataclass
class ExecEnv:
    cwd: str | None = None
    timeout: float = 30.0
    interpreters: dict = field(default_factory=lambda: dict(DEFAULT_INTERPRETERS))
    freeze: object | None = None
    allow_error: bool = False

    def run(self, source: str, lang: str) -> str:
        cmd = self.interpreters.get(lang)
        if cmd is None:
            raise ExecError(f"no interpreter configured for language '{lang}'")
        cache_key = None
        if self.freeze is not None:
            cache_key = self.freeze.key(" ".join(cmd), source)
            hit = self.freeze.get(cache_key)
            if hit is not None:
                return hit
        try:
            proc = subprocess.run(
                cmd, input=source, capture_output=True, text=True,
                cwd=self.cwd, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise ExecError(f"{lang} block timed out after {self.timeout}s") from e
        if proc.returncode != 0 and not self.allow_error:
            raise ExecError(
                f"{lang} block failed (exit {proc.returncode}):\n{proc.stderr.strip()}"
            )
        out = proc.stdout
        if proc.returncode != 0 and self.allow_error:
            out += proc.stderr
        if cache_key is not None:
            self.freeze.set(cache_key, out)
        return out
