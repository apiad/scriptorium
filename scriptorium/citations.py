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

# [@a] or [@a; @b] — brackets are required. A bare @key is deliberately not a
# citation: v0.4.0 narrowed the cross-reference pattern precisely because a loose
# @word rule was rewriting prose into empty anchors. A comma (a page locator)
# fails the match, so the whole span stays literal.
_CITE = re.compile(r"\[@[\w-]+(?:[ \t]*;[ \t]*@[\w-]+)*\]")
_KEY = re.compile(r"@([\w-]+)")


@dataclass
class Entry:
    key: str
    body: str
    number: int
    refs: int = 0


def number_citations(src: str, bib: dict[str, str]) -> tuple[str, list[Entry], list[str]]:
    """Rewrite [@key] spans to numbered links; return (src, entries, warnings).

    One pass suffices because a call-site id is always `citeref-N-K`, unlike the
    footnote scheme where the suffix appears only when a note is cited twice.
    """
    spans = fence_spans(src)
    entries: dict[str, Entry] = {}
    warnings: list[str] = []
    out, last = [], 0

    for m in _CITE.finditer(src):
        if in_span(m.start(), spans):
            continue
        keys = _KEY.findall(m.group(0))
        missing = [k for k in keys if k not in bib]
        if missing:
            for k in missing:
                w = f"citation [@{k}] has no bibliography entry"
                if w not in warnings:
                    warnings.append(w)
            continue  # the whole span stays literal — visible, never vanished
        links = []
        for k in keys:
            entry = entries.get(k)
            if entry is None:
                entry = entries[k] = Entry(key=k, body=bib[k], number=len(entries) + 1)
            entry.refs += 1
            links.append(f'<a id="citeref-{entry.number}-{entry.refs}" '
                         f'href="#cite-{entry.number}">{entry.number}</a>')
        out.append(src[last:m.start()])
        out.append(f'<span class="cite-ref">[{", ".join(links)}]</span>')
        last = m.end()

    out.append(src[last:])
    return "".join(out), list(entries.values()), warnings
