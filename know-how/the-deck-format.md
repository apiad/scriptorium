# The deck format

*When to reach for it: any work on slides — the deck theme, slide splitting,
slide masters, or aspect ratio.*

A deck is just a theme with `mode: deck` in `theme.yml`. That flips galley from
flowing pages to slides: it still parses, measures, and reuses components/themes —
it only replaces `pack` with `_group_slides` and `emit` with `emit_deck`.

## How content maps to slides (`_group_slides`)

- `#` (h1) → a **section divider** slide.
- `##` (h2) → a new **content** slide; the heading text is the slide title.
- `::: newpage` / `---` → a manual break.
- A full-page master (`::: statement`, `::: closing`, …) → its own slide.
- A title slide is prepended from frontmatter when `title` is set.

## Fit, not flow

Each slide is one fixed box (`page.size: "16:9"` etc.). Content is **measured and
warned** if it exceeds the slide — decks never auto-shrink or auto-continue,
because both look bad; the author trims. Same philosophy as the page drift guard.

## emit_deck

One `<div class="slide {master}">` per group:

- `master == "title"` → render the `title` master from frontmatter, no counter.
- a single full-page-master unit (statement/closing) → render its html directly,
  no counter.
- otherwise → wrap units in `.slide-body` + add the `.slide-counter` (`n / total`).

## The deck theme

`themes/deck` extends `report`, so KPI tiles / finding cards / stat strips drop
onto slides. It sets `page.size: "16:9"`, `toc_depth: 1` (the agenda lists
sections), and provides `title` / `statement` / `closing` masters. The agenda
slide is a normal `::: toc`; slide numbers come from `target-counter`.

## Speaker notes for a deck

`themes/speaker` is the companion, and it is a document theme, not a deck mode:
the flow pipeline paginates it and CSS Fragmentation does the breaks. It sets
`page.size: "16:9"` so a page is the same shape as the slide it describes, and
`h1 { break-before: page }` so one h1 is one slide.

Two traps live in those two lines. `h1:first-of-type` does *not* suppress the
leading break, because `emit` wraps every block in its own `.unit` and so every
h1 is the first of its parent — the rule cancels every break in the document.
Use `.unit:first-child h1`. And a 16:9 page leaves 230mm of column, about 118
characters a line, so the theme caps `.unit` at 180mm and turns hyphenation off;
notes are usually not in the language the hyphenator was handed.

`tests/test_galley.py::test_speaker_theme_gives_one_page_per_h1` pins the page
count against `examples/speaker.md`.

## Adding to a deck

- New slide kind → a master template + a `components:` hint with `master: <name>`
  + `.slide.<name>` CSS. Full-page masters render without a counter automatically.
- New aspect ratio → set `page.size` (`4:3`, or `254mm 190mm`).
- Two-column content → `::: {.two-col}` works today; a distinct left/right panel
  wants its own flex component (not yet built).
