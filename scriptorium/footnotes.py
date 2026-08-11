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


_MARK = re.compile(r"\[\^([\w-]+)\]")
_H1 = re.compile(r"^#[ \t]", re.MULTILINE)
_SUFFIX = "abcdefghijklmnopqrstuvwxyz"


def _chapter_starts(src: str, spans: list[tuple[int, int]]) -> list[int]:
    return [m.start() for m in _H1.finditer(src) if not _in_span(m.start(), spans)]


def _lead(src: str, starts: list[int]) -> int:
    """Bucket index of chapter 1 — 1 when the document opens on an `#`, else 0.

    Prose before the first heading is its own bucket; a document that starts
    with a chapter has an empty one, and numbering must skip it.
    """
    return 0 if (not starts or src[: starts[0]].strip()) else 1


def number_and_mark(src: str, notes: dict[str, Note],
                    chapter_mode: bool) -> tuple[str, list[list[Note]]]:
    """Rewrite [^key] markers to numbered <sup> anchors; group notes per chapter.

    Two passes: a back-link suffix is only emitted for notes referenced more
    than once, and that count is not known until every marker has been seen.
    """
    spans = _fence_spans(src)
    starts = _chapter_starts(src, spans) if chapter_mode else []
    lead = _lead(src, starts)
    buckets: list[list[Note]] = [[] for _ in range(len(starts) + 1)]
    scoped_by: dict[tuple[int, str], Note] = {}
    hits: list[tuple[re.Match, int, int, int, Note]] = []

    for m in _MARK.finditer(src):
        if _in_span(m.start(), spans) or m.group(1) not in notes:
            continue
        note = notes[m.group(1)]
        bucket = sum(1 for s in starts if s <= m.start())
        scoped = scoped_by.get((bucket, note.key))
        if scoped is None:
            # a note referenced from two chapters gets one entry per chapter,
            # each with its own back-links; `notes` keeps the global tally.
            scoped = scoped_by[(bucket, note.key)] = Note(key=note.key, body=note.body)
            buckets[bucket].append(scoped)
        scoped.refs.append(len(scoped.refs) + 1)
        note.refs.append(len(note.refs) + 1)
        hits.append((m, bucket + 1 - lead, buckets[bucket].index(scoped) + 1,
                     len(scoped.refs), scoped))

    out, last = [], 0
    for m, chapter, num, occurrence, scoped in hits:
        suffix = _SUFFIX[occurrence - 1] if len(scoped.refs) > 1 else ""
        out.append(src[last:m.start()])
        out.append(f'<sup class="footnote-ref" id="fnref-{chapter}-{num}{suffix}">'
                   f'<a href="#fn-{chapter}-{num}">{num}</a></sup>')
        last = m.end()
    out.append(src[last:])
    return "".join(out), (buckets[lead:] if chapter_mode else [buckets[0]])


MODES = ("document", "chapter", "page")


def resolve_footnote_mode(meta: dict, theme_meta: dict) -> str:
    """Frontmatter wins, then the theme, then `document`."""
    mode = meta.get("footnotes") or theme_meta.get("footnotes") or "document"
    mode = str(mode).strip().lower()
    if mode not in MODES:
        raise ValueError(f"unknown footnotes mode {mode!r}; expected one of {MODES}")
    return mode


def _split_frontmatter(src: str) -> tuple[str, str]:
    """(frontmatter block, body) — same rule parse.frontmatter/_body use.

    The block is held aside: a `---` fence or a YAML `# comment` inside it
    would otherwise read as document content and shift chapter numbering.
    """
    if src.startswith("---\n"):
        end = src.find("\n---", 3)
        if end >= 0:
            nl = src.find("\n", end + 1)
            return (src[: nl + 1], src[nl + 1 :]) if nl >= 0 else (src, "")
    return "", src


def _component(chapter: int, notes: list[Note]) -> str:
    """Notes as a `::: footnotes` component; bodies stay Markdown."""
    items = []
    for n, note in enumerate(notes, 1):
        base = f"fnref-{chapter}-{n}"
        ids = ([base] if len(note.refs) < 2
               else [f"{base}{_SUFFIX[i]}" for i in range(len(note.refs))])
        back = " ".join(f"[↩](#{i})" for i in ids)
        items.append(f'{n}. <span id="fn-{chapter}-{n}"></span>{note.body} {back}')
    return "::: footnotes\n" + "\n".join(items) + "\n:::\n"


def _inline_notes(src: str, notes: dict[str, Note]) -> str:
    """`page` mode: put each note's body inline at its first reference.

    WeasyPrint's GCPM `float: footnote` pulls the element to the foot of the
    page its anchor lands on and generates the call number itself, so we emit
    no marker of our own. A note has one body and therefore one page: a second
    reference gets a plain superscript, not a duplicate of the text.
    """
    spans = _fence_spans(src)
    seen: dict[str, int] = {}
    out, last = [], 0
    for m in _MARK.finditer(src):
        if _in_span(m.start(), spans) or m.group(1) not in notes:
            continue
        note = notes[m.group(1)]
        out.append(src[last:m.start()])
        if note.key in seen:
            out.append(f'<sup class="footnote-ref">{seen[note.key]}</sup>')
        else:
            seen[note.key] = len(seen) + 1
            out.append(f'<span class="footnote-inline">{note.body}</span>')
        last = m.end()
    out.append(src[last:])
    return "".join(out)


def process_footnotes(src: str, mode: str = "document") -> str:
    """Entry point: rewrite markers and emit notes per `mode`."""
    head, body = _split_frontmatter(src)
    body, notes = collect_notes(body)
    if not notes:
        return head + body
    if mode == "page":
        return head + _inline_notes(body, notes)

    marked, groups = number_and_mark(body, notes, chapter_mode=(mode == "chapter"))
    if mode == "document":
        return head + marked.rstrip() + "\n\n" + _component(1, groups[0])

    starts = _chapter_starts(marked, _fence_spans(marked))
    bounds = starts[_lead(marked, starts):] + [len(marked)]
    out, prev = [], 0
    for i, group in enumerate(groups):
        out.append(marked[prev : bounds[i]])
        if group:
            out.append("\n" + _component(i + 1, group) + "\n")
        prev = bounds[i]
    return head + "".join(out)
