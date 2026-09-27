# AGENTS.md

Orientation for agents (and humans) working *in* this repo. Read this first, then
load the `know-how/` doc that matches your task.

## What scriptorium is

A Markdown-native document engine: Markdown (+ a little HTML) → exact-geometry
PDF. `README.md` is the user view; `docs/design.md` is the full design.

## The pipeline (the mental model)

```
documents  Markdown → parse → [tangle | execute] → emit → WeasyPrint → PDF
                                                    └─ CSS Fragmentation paginates
decks      Markdown → parse → [tangle | execute] → measure → pack → emit_deck → PDF
```

**Who paginates, and why it decides where you edit.** For the document themes
(`base`, `note`, `article`, `report`, `book`) there is **no Python pagination**:
`emit()` produces one HTML flow and WeasyPrint's CSS Fragmentation Module breaks
the pages using `break-before/inside/after` and the `@page` rules. `measure()`
and `pack()` **do not run**. Only `deck` themes keep the measure-and-pack
pipeline, because a slide is a fixed-size absolutely-positioned box.

This has been true since `b99dc6a` (2026-08-02, *replace Python bin-packing with
CSS Fragmentation Module*). To change how a document paginates, edit the theme
CSS and `emit()`, never `pack()`. Editing `pack()` for a document produces dead
code that the `pack()` unit tests happily certify.

- **`parse.py`** — markdown-it-py + `:::` components + code fences + math + `@ref`
  → a flat list of `Unit`s (the model in `model.py`).
- **`galley.py`** — `emit()` (one flow, plus `.page` divs for full-page masters),
  `page_fills()` (real per-page fill, read off the box tree **after** the render)
  and the `render_pdf` entry point. `measure()` and `pack()` are still here but
  **only the deck path uses them** (`_group_slides` / `emit_deck`).
- **`execute.py`** — run code in a subshell, splice stdout, per-file session
  state, freeze cache, `PYTHONPATH`.
- **`tangle.py`** — `export=` extraction (illiterate-compatible, byte-exact).
- **`footnotes.py`** — `[^a]` markers + `[^a]: body` definitions → endnotes per
  document/chapter, or GCPM per-page floats. It runs on the **raw source, before
  `parse()`**, and must stay that way: `parse()` renders block by block, so a
  markdown-it plugin would never see a marker and its definition in one render
  call. Presentation lives in `components/footnotes.html` + theme CSS.
- **`citations.py`** — `[@key]` spans against a declared `bibliography:` map →
  a numbered `::: references` section. Runs on the raw source **after**
  `footnotes.py`, so a citation inside a note body is numbered by where the note
  renders. Entries are prose: never parse them for author or year.
- **`glossary.py`** — `[~key]` / `[display]{~key}` markers against a declared
  `glossary:` map → a sorted `::: glossary` section with page back-links. Runs on
  the raw source **after `citations.py`**, so a term glossed inside a note body is
  paged where the note renders. Markers nest; only the innermost matches, and the
  outer of a nested pair keeps an anchor but not a link, because `<a>` inside
  `<a>` is invalid and strands a `</a>` mid-sentence.
- **`source.py`** — the shared source scanner (fence spans, inline code spans,
  frontmatter split) the pre-processors use. `code_spans` exists because a
  marker inside `` `code` `` is code: rewriting one injects raw HTML into a
  literal. **`citations.py` and `footnotes.py` do not yet use it** — see
  `tasks.md`.
- **`mathrender.py`** — LaTeX → SVG via quickjax (no Node).
- **`theme.py`** — theme loading + `extends:` inheritance + the mustache template
  engine (`{{holes}}`, `{{#sections}}` / loops).
- **`project.py`** — `scriptorium.yaml` (concatenate files + inject vars).
- **`themes/`** — `base` + `note` / `article` / `report` / `book` / `deck` / `speaker` / `syalia`.

## Conventions

- Python 3.12+, English throughout. One logical change per commit (conventional
  commits). **`uv run pytest` must pass before any commit lands.**
- The engine is theme-agnostic: **numbering, cross-references, and the look live in
  theme CSS, not in the engine.** Don't add domain logic (authors, chapters) to
  the engine — it belongs in a theme template.
- **Verify visual work visually.** Green tests and a page count do not catch "no
  margins" or the wrong font — render the PDF and check the geometry / embedded
  fonts (`pdffonts`).

## Know-how index — match your task, then load the doc

- Pagination, a gap on a page, a block that jumps → `know-how/the-galley-engine.md`
- Creating or changing a theme, a font/customization issue → `know-how/authoring-a-theme.md`
- The deck / slide format → `know-how/the-deck-format.md`
- Cutting a release → `know-how/releasing.md`
