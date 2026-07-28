# The galley engine

*When to reach for it: any work on pagination, the measure/pack/emit passes, a
layout bug, content overflow, or page-count drift.*

`galley` turns a flat list of `Unit`s into fixed-geometry pages. Three passes,
one shared rendering path so measurement never disagrees with output.

## Measure

Render the content stream once and read each unit's border-box height from
WeasyPrint's box tree (`box.margin_height()`), keyed by a `data-i` attribute.

Two invariants — both learned from real book-scale bugs:

1. **Measure in chunks** (`MEASURE_CHUNK`, `_geom` content width). WeasyPrint
   silently stops paginating a single render past ~21 pages / ~84000 mm, so a big
   document would measure its tail as height 0. Chunk the units so each render
   stays well under that ceiling, and read heights across *all* pages of the
   chunk (`break-inside:avoid` keeps a unit off two measure pages).
2. **`.unit { display:flow-root }`** (injected in both measure and emit CSS).
   Without it, adjacent unit margins collapse *within* the measure render but not
   across `.page` boundaries at emit, so emit runs taller — drift proportional to
   page count. This is an engine invariant, not a theme choice.

## Pack

Greedy fill into a page of height `content_h = page − 2·margin − footer reserve`
(a `deque` so split remainders re-queue):

- **keep-with-next** — a heading won't be the last thing on a page.
- **keep-together** components move whole to the next page rather than split.
- **code / table splitting** — a listing splits at line boundaries (widow/orphan
  minimum, "…continues" marker); a too-tall table splits at row boundaries,
  repeating the header. Prose paragraphs are already fine-grained units.
- **oversize** (taller than a page and unsplittable, e.g. a giant image) → warn +
  overflow; never silently scale or clip.

## Emit

Wrap each page's units in `<div class="page">`, `@page{margin:0}`, one fixed box
per page → PDF. The **page margin is one value**: galley injects `--page-margin`
(from `theme.yml page.margin`) and `base` applies it as `.page` padding, so the
visual inset can't disagree with the content width measure used. Page size is
theme-driven (`_page_size`: `A4`, `letter`, `16:9`, `4:3`, or `WxH`).

## The drift guard

After emit, compare `len(doc.pages)` to the planned page count. **Overflow**
(actual > planned) means a page exceeded its box — content may clip, a real bug.
**Loose** (actual < planned) means measure over-reserved — benign. This guard has
caught every measure regression; keep it.

## Debugging checklist

- Content missing / truncated → check for zero-height units (measure chunk cap)
  and for an unclosed multi-line HTML comment swallowing content.
- Drift → margins collapsing (flow-root), measure/emit CSS asymmetry, or an
  oversize unit.
- "No margin" / wrong size → `--page-margin` and `_page_size` come from
  `theme.yml page`.
