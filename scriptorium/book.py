"""The HTML book: a static, installable ebook directory built from the units.

The same units a PDF prints from are laid out by a browser's multi-column
layout instead of WeasyPrint's paged media. This module turns the theme's CSS
into what a browser runs, resolves the cross-references that paged media
numbered, collects images and fonts into the site, and writes the reader.
"""

import re

# Declarations only paged media understands. In a browser an unknown function
# invalidates the whole declaration, so a `content: "Chapter " target-counter()`
# would leave the reference empty rather than half-filled.
_PAGED_VALUE = re.compile(r"target-counter\(|target-text\(|counter\(pages?\b|leader\(|string\(")
_PAGED_PROPS = {"string-set", "bookmark-level", "bookmark-label", "page"}
# fixed-size page and slide boxes; the reader has its own full-page block
_DROP_SELECTORS = {".page", ".page:first-child", ".slide", ".slide:last-child"}
# at-rules whose body is more rules, filtered the same way
_NESTED = ("@media", "@supports", "@layer", "@container", "@document")
_BREAK_PAGE = re.compile(r"\b((?:page-)?break-(?:before|after)\s*:\s*)(?:page|always|left|right|recto|verso)\b")


def _strip_comments(css: str) -> str:
    out, i = [], 0
    while i < len(css):
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            i = len(css) if end < 0 else end + 2
            continue
        if css[i] in "\"'":
            j = _string_end(css, i)
            out.append(css[i:j])
            i = j
            continue
        out.append(css[i])
        i += 1
    return "".join(out)


def _string_end(css: str, i: int) -> int:
    q, j = css[i], i + 1
    while j < len(css) and css[j] != q:
        j += 2 if css[j] == "\\" else 1
    return j + 1


def _items(css: str):
    """Top-level (prelude, body) pairs; body is None for a `@import …;` statement."""
    i, n = 0, len(css)
    while i < n:
        start, depth, paren = i, 0, 0
        while i < n:
            c = css[i]
            if c in "\"'":
                i = _string_end(css, i)
                continue
            if c == "(":
                paren += 1
            elif c == ")":
                paren -= 1
            elif c == ";" and depth == 0 and paren == 0:
                stmt = css[start:i].strip()
                i += 1
                if stmt:
                    yield stmt, None
                break
            elif c == "{" and paren == 0:
                if depth == 0:
                    open_at = i
                depth += 1
            elif c == "}" and paren == 0:
                depth -= 1
                if depth == 0:
                    yield css[start:open_at].strip(), css[open_at + 1:i]
                    i += 1
                    break
            i += 1
        else:
            rest = css[start:].strip()
            if rest:
                yield rest, None


def _declarations(body: str) -> list[str]:
    decls, cur, paren, i = [], [], 0, 0
    while i < len(body):
        c = body[i]
        if c in "\"'":
            j = _string_end(body, i)
            cur.append(body[i:j])
            i = j
            continue
        if c == "(":
            paren += 1
        elif c == ")":
            paren -= 1
        if c == ";" and paren == 0:
            decls.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    decls.append("".join(cur))
    return [d for d in decls if d.strip()]


def _filter_rule(body: str) -> str:
    kept = []
    for d in _declarations(body):
        prop, _, value = d.partition(":")
        if prop.strip().lower() in _PAGED_PROPS or _PAGED_VALUE.search(value):
            continue
        kept.append(_BREAK_PAGE.sub(r"\1column", d))
    return ";".join(kept)


def browser_css(css: str) -> str:
    """The theme CSS without what only paged media understands: `@page` rules
    and their margin boxes, page and slide boxes, `string-set`, and contents
    built with `target-counter()` / `target-text()` / `counter(page)`. Page
    breaks become column breaks, since a page of the book is a column."""
    out = []
    for prelude, body in _items(_strip_comments(css)):
        if body is None:
            out.append(prelude + ";")
            continue
        at = prelude.split(None, 1)[0].lower() if prelude.startswith("@") else ""
        if at == "@page":
            continue
        if at in _NESTED:
            out.append(f"{prelude}{{{browser_css(body)}}}")
        elif at:  # @font-face, @keyframes, …: untouched
            out.append(f"{prelude}{{{body}}}")
        elif {s.strip() for s in prelude.split(",")} <= _DROP_SELECTORS:
            continue
        else:
            kept = _filter_rule(body)
            if kept.strip():
                out.append(f"{prelude}{{{kept}}}")
    return "\n".join(out)
