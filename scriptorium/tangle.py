"""Tangle: extract `export=` code blocks into real source files.

Subsumes illiterate's core: blocks targeting the same path are concatenated in
document order, joined by a blank line (matching illiterate's output). Headless
`{export}` derives the filename from the document name + language. `test()` is
the CI idempotency check.
"""

from pathlib import Path

from .fence import EXT as _EXT
from .fence import parse_fence
from .parse import _split_md, _split_nodes, _body


def _walk_code(src: str):
    """Yield (Fence, body) for every code fence, descending into containers."""
    for node in _split_nodes(_body(src)):
        if node[0] == "md":
            for kind, *rest in _split_md(node[1]):
                if kind == "code":
                    info, body = rest
                    yield parse_fence(info), body
        else:  # container: recurse into inner
            yield from _walk_code(node[4])


def collect(src: str, doc_stem: str = "doc") -> dict[str, str]:
    """path -> concatenated file contents from all export blocks targeting it."""
    files: dict[str, list[str]] = {}
    for f, body in _walk_code(src):
        if not f.tangles:
            continue
        path = f.export or f"{doc_stem}.{_EXT.get(f.lang, 'txt')}"
        files.setdefault(path, []).append(body)
    # illiterate joins same-target blocks with a single newline, preserving each
    # block's own whitespace; the file ends in exactly one trailing newline.
    return {p: "\n".join(blocks).rstrip("\n") + "\n" for p, blocks in files.items()}


def write(src: str, root: str | Path, doc_stem: str = "doc") -> list[str]:
    root = Path(root)
    written = []
    for rel, content in collect(src, doc_stem).items():
        out = root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        written.append(str(out))
    return written


def test(src: str, root: str | Path, doc_stem: str = "doc") -> list[str]:
    """Return the list of paths that would change (empty == idempotent)."""
    root = Path(root)
    drift = []
    for rel, content in collect(src, doc_stem).items():
        out = root / rel
        if not out.exists() or out.read_text(encoding="utf-8") != content:
            drift.append(rel)
    return drift
