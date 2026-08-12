"""Numbered citations against an author-declared bibliography.

A source-to-source pre-processor, like footnotes.py and for the same reason:
parse() renders block by block, so a plugin would never see a citation and its
entry in one render call.

Entries are opaque Markdown prose. The engine numbers, orders and links them; it
never inspects them for an author or a year, which is why this is numeric-only
and author-date belongs to a future CSL feature.
"""

import re
from dataclasses import dataclass

from .source import fence_spans, in_span, line_offsets, split_frontmatter

# [@a], [@a; @b], and the narrative forms [+@a] / [-@a] — brackets are required.
# A bare @key is deliberately not a citation: v0.4.0 narrowed the cross-reference
# pattern precisely because a loose @word rule was rewriting prose into empty
# anchors, and requiring brackets keeps citations and cross-references separable
# at the parser. A comma (a page locator) fails the match, so the whole span
# stays literal. Group 1 is the sigil, "" when absent.
_CITE = re.compile(r"\[([+-]?)@[\w-]+(?:[ \t]*;[ \t]*@[\w-]+)*\]")
_KEY = re.compile(r"@([\w-]+)")


@dataclass
class Entry:
    key: str
    body: str
    number: int
    refs: int = 0
    author: str | None = None


@dataclass(frozen=True)
class _Source:
    """A bibliography value after normalisation: prose, plus an optional name.

    `author` is whatever the author declared, verbatim. It is never derived from
    the key or read out of `text` — deriving it is right for `tam-2024` and
    silently wrong for `willard-2023` (two authors) and `fan-2026` (one), which
    is exactly the class of error a reader notices and the engine cannot see.
    """

    text: str
    author: str | None = None


def _normalise(bib: dict) -> tuple[dict[str, _Source], list[str]]:
    """Collapse prose-string and mapping entries into one internal shape."""
    sources: dict[str, _Source] = {}
    warnings: list[str] = []
    for key, value in bib.items():
        if isinstance(value, str):
            sources[key] = _Source(text=value)
        elif isinstance(value, dict):
            text = value.get("text")
            if not text:
                warnings.append(f"bibliography entry {key!r} has no `text:`")
                continue
            sources[key] = _Source(text=text, author=value.get("author"))
        else:
            warnings.append(
                f"bibliography entry {key!r} is neither prose nor an "
                f"{{author, text}} mapping"
            )
    return sources, warnings


def number_citations(
    src: str, bib: dict, nocite: tuple[str, ...] | list[str] = ()
) -> tuple[str, list[Entry], list[str]]:
    """Rewrite [@key] spans to numbered links; return (src, entries, warnings).

    One pass suffices because a call-site id is always `citeref-N-K`, unlike the
    footnote scheme where the suffix appears only when a note is cited twice.
    The `-` form emits no number, so it needs nothing patched afterwards either.
    """
    sources, warnings = _normalise(bib)
    spans = fence_spans(src)
    entries: dict[str, Entry] = {}
    author_only: list[str] = []
    out, last = [], 0

    def warn(message: str) -> None:
        if message not in warnings:
            warnings.append(message)

    for m in _CITE.finditer(src):
        if in_span(m.start(), spans):
            continue
        sigil = m.group(1)
        keys = _KEY.findall(m.group(0))

        missing = [k for k in keys if k not in sources]
        if missing:
            for k in missing:
                warn(f"citation [@{k}] has no bibliography entry")
            continue  # the whole span stays literal — visible, never vanished

        author = None
        if sigil:
            author = sources[keys[0]].author
            if author is None:
                warn(f"citation [{sigil}@{keys[0]}] is narrative but the entry "
                     f"declares no author")
                continue

        out.append(src[last:m.start()])
        last = m.end()

        if sigil == "-":
            # No mark, so no entry: a work in the references list with a number
            # nothing points at is worse than no entry. Plain text, not a link —
            # linking would need a number that may not exist yet at this point
            # in the pass, and one pass is worth more than a hyperlink on a name.
            author_only.append(keys[0])
            out.append(f'<span class="cite-author">{author}</span>')
            continue

        links = []
        for k in keys:
            entry = entries.get(k)
            if entry is None:
                entry = entries[k] = Entry(
                    key=k, body=sources[k].text, number=len(entries) + 1,
                    author=sources[k].author,
                )
            entry.refs += 1
            links.append(f'<a id="citeref-{entry.number}-{entry.refs}" '
                         f'href="#cite-{entry.number}">{entry.number}</a>')

        prefix = f'<span class="cite-author">{author}</span> ' if sigil == "+" else ""
        out.append(f'{prefix}<span class="cite-ref">[{", ".join(links)}]</span>')

    out.append(src[last:])

    # Deferred to here, not checked at the call site: whether a work is cited
    # elsewhere is only knowable once the whole document has been walked.
    for key in author_only:
        if key not in entries and key not in nocite:
            warn(f"[-@{key}] names an author but the work is never cited")

    return "".join(out), list(entries.values()), warnings


_REFS_OPEN = re.compile(r"^:{3,}[ \t]*references[ \t]*$")
_REFS_CLOSE = re.compile(r"^:{3,}[ \t]*$")


def _placeholder(src: str) -> tuple[int, int] | None:
    """Character range of an author-written `::: references` block, if any."""
    spans = fence_spans(src)
    lines = src.split("\n")
    offsets = line_offsets(lines)
    found = None
    for i, line in enumerate(lines):
        if not _REFS_OPEN.match(line) or in_span(offsets[i], spans):
            continue
        for j in range(i + 1, len(lines)):
            if _REFS_CLOSE.match(lines[j]):
                if found is not None:
                    raise ValueError("two `::: references` blocks; there can be only one")
                found = (offsets[i], offsets[j] + len(lines[j]) + 1)
                break
        else:
            raise ValueError("`::: references` block is never closed")
    return found


def _component(entries: list[Entry]) -> str:
    """Entries as a `::: references` component; bodies stay Markdown."""
    items = []
    for entry in entries:
        back = " ".join(f"[↩](#citeref-{entry.number}-{k})"
                        for k in range(1, entry.refs + 1))
        items.append(f'{entry.number}. <span id="cite-{entry.number}"></span>'
                     f"{entry.body} {back}".rstrip())
    return "::: references\n" + "\n".join(items) + "\n:::\n"


def process_citations(src: str, meta: dict) -> tuple[str, list[str]]:
    """Entry point: number citations and emit the references section."""
    bib = meta.get("bibliography") or {}
    nocite = meta.get("nocite") or []
    head, body = split_frontmatter(src)
    marked, entries, warnings = number_citations(body, bib, nocite)

    # Malformed-entry warnings were already reported by number_citations.
    sources, _ = _normalise(bib)
    for key in nocite:
        if key not in sources:
            warnings.append(f"nocite key {key!r} has no bibliography entry")
        elif not any(e.key == key for e in entries):
            entries.append(Entry(key=key, body=sources[key].text,
                                 number=len(entries) + 1,
                                 author=sources[key].author))

    if not entries:
        return head + marked, warnings

    block = _component(entries)
    at = _placeholder(marked)
    if at:
        return head + marked[: at[0]] + block + marked[at[1] :], warnings
    return head + marked.rstrip() + "\n\n" + block, warnings
