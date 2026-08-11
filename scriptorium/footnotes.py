"""Footnotes as endnotes.

A source-to-source pre-processor, not a markdown-it plugin: parse() renders
block by block (parse.py:300), so a plugin would never see a marker and its
definition in the same render call.

Markers become inline <sup> HTML (CommonMark passes inline HTML through);
note bodies are re-emitted as a `::: footnotes` component so the real Markdown
renderer handles the author's links and emphasis.
"""

import re
from dataclasses import dataclass, field

_DEF = re.compile(r"^\[\^([\w-]+)\]:[ \t]*(.*)$")
_FENCE = re.compile(r"^(`{3,}|~{3,}).*$", re.MULTILINE)


@dataclass
class Note:
    key: str
    body: str
    refs: list[int] = field(default_factory=list)


def _fence_spans(src: str) -> list[tuple[int, int]]:
    """Character ranges covered by fenced code blocks."""
    spans, open_at, marker = [], None, None
    for m in _FENCE.finditer(src):
        tick = m.group(1)
        if open_at is None:
            open_at, marker = m.start(), tick
        elif tick[0] == marker[0] and len(tick) >= len(marker):
            spans.append((open_at, m.end()))
            open_at, marker = None, None
    if open_at is not None:
        spans.append((open_at, len(src)))
    return spans


def _in_span(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in spans)


def _line_offsets(lines: list[str]) -> list[int]:
    offsets, pos = [], 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1
    return offsets


def _is_continuation(line: str) -> bool:
    return bool(line.strip()) and line[:1].isspace()


def collect_notes(src: str) -> tuple[str, dict[str, Note]]:
    """Strip `[^key]: body` definitions out of src; return (src, notes).

    A definition runs to the next blank line that is not followed by an
    indented continuation, so a note wrapped across several lines is captured
    whole. Definitions inside a code fence are prose, not notes.
    """
    spans = _fence_spans(src)
    lines = src.split("\n")
    offsets = _line_offsets(lines)
    notes: dict[str, Note] = {}
    dropped: set[int] = set()

    i = 0
    while i < len(lines):
        m = _DEF.match(lines[i])
        if not m or _in_span(offsets[i], spans):
            i += 1
            continue
        parts, dropped_here = [m.group(2).strip()], [i]
        j = i + 1
        while j < len(lines):
            line = lines[j]
            if line.strip():
                if not _is_continuation(line):
                    break
                parts.append(line.strip())
            elif not (j + 1 < len(lines) and _is_continuation(lines[j + 1])):
                break
            dropped_here.append(j)
            j += 1
        notes[m.group(1)] = Note(key=m.group(1), body=" ".join(p for p in parts if p))
        dropped.update(dropped_here)
        i = j

    kept = "\n".join(line for n, line in enumerate(lines) if n not in dropped)
    return re.sub(r"\n{3,}", "\n\n", kept), notes
