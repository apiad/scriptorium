# AGENTS.md

Orientation for agents (and humans) working *in* this repo. Read this first, then
load the `know-how/` doc that matches your task.

## What scriptorium is

A Markdown-native document engine: Markdown (+ a little HTML) → exact-geometry
PDF. `README.md` is the user view; `docs/design.md` is the full design.

## The pipeline (the mental model)

```
Markdown → parse → [tangle | execute] → measure → pack → emit → PDF
                                          (deck mode: group-into-slides)
```

- **`parse.py`** — markdown-it-py + `:::` components + code fences + math + `@ref`
  → a flat list of `Unit`s (the model in `model.py`).
- **`galley.py`** — the core. `measure` (unit heights from WeasyPrint's box tree,
  in chunks) → `pack` (fixed pages: keep-together, code/table splitting, oversize
  warn, drift guard) → `emit` (page divs → PDF). Also the **deck** path
  (`_group_slides` / `emit_deck`) and the `render_pdf` entry point.
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
- **`source.py`** — the shared source scanner (fence spans, frontmatter split)
  both pre-processors use.
- **`mathrender.py`** — LaTeX → SVG via quickjax (no Node).
- **`theme.py`** — theme loading + `extends:` inheritance + the mustache template
  engine (`{{holes}}`, `{{#sections}}` / loops).
- **`project.py`** — `scriptorium.yaml` (concatenate files + inject vars).
- **`themes/`** — `base` + `note` / `article` / `report` / `book` / `deck`.

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

- Pagination / measure / a layout or overflow bug → `know-how/the-galley-engine.md`
- Creating or changing a theme, a font/customization issue → `know-how/authoring-a-theme.md`
- The deck / slide format → `know-how/the-deck-format.md`
- Cutting a release → `know-how/releasing.md`
