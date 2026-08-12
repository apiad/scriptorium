"""Project model: a scriptorium.yaml is just a theme + vars + a file list.

Assembly = concatenate the listed files (each chapter starts a fresh page) and
merge vars. No structural schema — numbering, cross-references, and the table of
contents live in the theme's CSS (CSS counters, `target-counter`, `target-text`,
`leader()`), which WeasyPrint resolves at render time.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_VAR = re.compile(r"\{\{\s*([\w.-]+)\s*\}\}")


@dataclass
class Project:
    theme: str
    vars: dict
    src: str  # assembled markdown
    base_dir: Path
    code_root: str | None = None
    meta: dict = field(default_factory=dict)  # content keys: bibliography, nocite


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---", 3)
        if end >= 0:
            nl = text.find("\n", end + 1)
            return text[nl + 1 :] if nl >= 0 else ""
    return text


def substitute(text: str, vars: dict) -> str:
    return _VAR.sub(lambda m: str(vars.get(m.group(1), m.group(0))), text)


def load(path: str | Path) -> Project:
    path = Path(path)
    spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    base = path.parent
    theme = spec.get("theme", "book")
    vars = spec.get("vars", {}) or {}
    # content keys, distinct from `vars` (which is the appearance contract and
    # the target of {{substitution}}): a bibliography is content, not styling,
    # and where the notes collect is structure, not styling either.
    meta = {k: spec[k]
            for k in ("bibliography", "nocite", "glossary", "css", "footnotes")
            if k in spec}

    bodies = []
    for i, rel in enumerate(spec.get("files", [])):
        body = _strip_frontmatter((base / rel).read_text(encoding="utf-8"))
        if i > 0:
            bodies.append("\\newpage")  # each file starts a fresh page
        bodies.append(body.strip())
    src = substitute("\n\n".join(bodies), vars)

    code_root = (spec.get("code") or {}).get("root")
    return Project(theme=theme, vars=vars, src=src, base_dir=base,
                   code_root=code_root, meta=meta)
