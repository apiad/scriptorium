"""Scan Markdown source without touching fenced code or frontmatter.

Shared by the source-to-source pre-processors (footnotes, citations). Both must
find markers in prose while leaving fenced code alone, and both must hold a
document's frontmatter aside so a `---` fence or a YAML `# comment` is never
mistaken for document content.
"""

import re

FENCE = re.compile(r"^(`{3,}|~{3,}).*$", re.MULTILINE)


def fence_spans(src: str) -> list[tuple[int, int]]:
    """Character ranges covered by fenced code blocks."""
    spans, open_at, marker = [], None, None
    for m in FENCE.finditer(src):
        tick = m.group(1)
        if open_at is None:
            open_at, marker = m.start(), tick
        elif tick[0] == marker[0] and len(tick) >= len(marker):
            spans.append((open_at, m.end()))
            open_at, marker = None, None
    if open_at is not None:
        spans.append((open_at, len(src)))
    return spans


def in_span(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in spans)


def line_offsets(lines: list[str]) -> list[int]:
    """Character offset of each line, for mapping a line index to a position."""
    offsets, pos = [], 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1
    return offsets


def split_frontmatter(src: str) -> tuple[str, str]:
    """(frontmatter block, body) — the same rule parse.frontmatter/_body use."""
    if src.startswith("---\n"):
        end = src.find("\n---", 3)
        if end >= 0:
            nl = src.find("\n", end + 1)
            return (src[: nl + 1], src[nl + 1 :]) if nl >= 0 else (src, "")
    return "", src
