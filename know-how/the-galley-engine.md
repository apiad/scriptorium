# The galley engine

*When to reach for it: a gap on a page, a block that jumps to the next page,
page-count questions, or any work on the deck pipeline.*

## Read this first

**Document themes do not paginate in Python.** For `base`, `note`, `article`,
`report` and `book`, `emit()` produces one HTML flow and WeasyPrint's CSS
Fragmentation Module breaks the pages. `measure()` and `pack()` never run. This
changed in `b99dc6a` (2026-08-02) and the module docstring of `galley.py` says
so in its third line.

Only **deck** themes still run measure → pack → `emit_deck`, because a slide is
a fixed-size absolutely-positioned box.

The practical consequence: to change how a document paginates, edit the theme
CSS and `emit()`. Editing `pack()` for a document yields dead code, and the
`pack()` unit tests will pass anyway because they call `pack()` directly. Verify
a pagination change by rendering a real document and looking at the PDF.

## Documents

Breaks come from theme CSS: `break-inside: avoid` on `.keep` and on themed
components, `break-before` on `.break-before`, `orphans` / `widows` on prose.
Page geometry comes from `@page` (size from `theme.yml page.size`, margin from
`page.margin`). Full-page masters are `.page` divs bound to a named `@page`.

**There are no page floats.** WeasyPrint does not implement GCPM page floats, so
a block that cannot split and does not fit in the remaining space moves whole to
the next page and leaves a gap. The engine will not reflow around it.

`page_fills(doc)` returns `(used_mm, available_mm)` per page, measured on the
rendered box tree: it walks each `page._page_box`, skips the `@page` margin
boxes, and takes the lowest content bottom edge. Set `SCRIPTORIUM_DEBUG_FILL=1`
to dump the table while rendering. Use it to find gaps; fix them by resizing the
block or moving text, not by changing the engine.

## Decks: measure

Render the content stream once and read each unit's border-box height from
WeasyPrint's box tree (`box.margin_height()`), keyed by a `data-i` attribute.

Two invariants, both learned from real bugs:

1. **Measure in chunks** (`MEASURE_CHUNK`, `_geom` content width). WeasyPrint
   silently stops paginating a single render past ~21 pages / ~84000 mm, so a
   big document would measure its tail as height 0. Chunk the units so each
   render stays well under that ceiling, and read heights across *all* pages of
   the chunk (`break-inside:avoid` keeps a unit off two measure pages).
2. **`.unit { display:flow-root }`** (injected in both measure and emit CSS).
   Without it, adjacent unit margins collapse *within* the measure render but
   not across `.page` boundaries at emit, so emit runs taller.

## Decks: pack

Greedy fill into a page of height `content_h = page − 2·margin − footer
reserve` (a `deque` so split remainders re-queue):

- **keep-with-next** — a heading won't be the last thing on a page.
- **keep-together** components move whole to the next page rather than split.
- **code / table splitting** — a listing splits at line boundaries (widow/orphan
  minimum, "…continues" marker); a too-tall table splits at row boundaries,
  repeating the header.
- **oversize** (taller than a page and unsplittable) → warn + overflow; never
  silently scale or clip.

## Emit

Wrap the content in `.unit` divs (documents) or per-slide boxes (decks). The
**page margin is one value**: galley injects `--page-margin` from `theme.yml
page.margin` and `base` applies it, so the visual inset cannot disagree with the
geometry. Page size is theme-driven (`_page_size`: `A4`, `letter`, `16:9`,
`4:3`, or `WxH`).

## Debugging checklist

- A gap on a page → `SCRIPTORIUM_DEBUG_FILL=1` and read `page_fills`. It is a
  block that did not fit; resize it or move text. There are no floats.
- Content missing / truncated → an unclosed multi-line HTML comment swallowing
  content; in decks, also zero-height units from the measure chunk cap.
- "No margin" / wrong size → `--page-margin` and `_page_size` come from
  `theme.yml page`.
- A pagination change that "works" but the PDF disagrees → you edited the deck
  path for a document. See *Read this first*.
