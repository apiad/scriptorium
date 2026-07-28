"""Parse a fenced code block's info string into a Fence directive.

Recognized forms (attributes combine freely):

    ```python                     shown source, not run
    ```python {run}               run in a subshell, splice stdout (native: asis)
    ```{python}                   Quarto-compat: run, output as monospace code
    ```python {export=src/x.py}   tangle body into a file
    ```python {name=frag}         named noweb fragment (definition)
    ```python {run echo=false}    run but hide the source
    ```python {run output=code}   force monospace output (default asis for native)

Default output mode differs by syntax: Quarto `{lang}` blocks default to `code`
(monospace, matching Quarto), native `{run}` blocks default to `asis` (stdout
spliced as raw markdown and re-parsed — the house model).
"""

import re
from dataclasses import dataclass

_KV = re.compile(r"""(\w[\w-]*)=("[^"]*"|'[^']*'|\S+)""")


@dataclass
class Fence:
    lang: str = ""
    run: bool = False
    export: str | None = None  # explicit path
    export_headless: bool = False  # bare {export}
    name: str | None = None  # noweb fragment name
    echo: bool = True  # show the source?
    output_mode: str = "asis"  # "asis" | "code"

    @property
    def tangles(self) -> bool:
        return self.export is not None or self.export_headless


def _attrs(text: str):
    kv = {m.group(1): m.group(2).strip("\"'") for m in _KV.finditer(text)}
    consumed = _KV.sub(" ", text)
    flags = {t for t in consumed.split() if re.fullmatch(r"[\w-]+", t)}
    return flags, kv


def parse_fence(info: str) -> Fence:
    info = info.strip()
    f = Fence()
    if info.startswith("{"):  # Quarto-style ```{python ...}
        inner = info[1 : info.rfind("}")] if "}" in info else info[1:]
        parts = inner.split(None, 1)
        f.lang = parts[0] if parts else ""
        attr_text = parts[1] if len(parts) > 1 else ""
        f.run = True
        f.output_mode = "code"
    else:  # ```python {..}
        b = info.find("{")
        head = (info[:b] if b >= 0 else info).split()
        f.lang = head[0] if head else ""
        attr_text = info[b + 1 : info.rfind("}")] if b >= 0 else ""

    flags, kv = _attrs(attr_text)
    if "run" in flags:
        f.run = True
    f.export = kv.get("export")
    if "export" in flags and f.export is None:
        f.export_headless = True
    f.name = kv.get("name")
    if kv.get("echo") == "false" or "echo=false" in attr_text:
        f.echo = False
    f.output_mode = kv.get("output", f.output_mode)
    return f
