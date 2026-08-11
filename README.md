# Scriptorium

Write Markdown, get a real document.

Scriptorium is a Markdown-native document engine that renders to **exact-geometry
PDF** — with a pagination engine that places content on physical pages under
rules you control, not whatever the flow happened to do. It executes code in
place, tangles code into real source files, renders LaTeX math without Node, and
ships a family of themes from conference notes to polished books to 16:9 slide
decks.

```bash
scriptorium render report.md              # a single document   -> report.pdf
scriptorium render book.yaml              # a multi-file project -> book.pdf
scriptorium render talk.md --theme deck   # override the declared theme
```

A document picks its own theme in frontmatter (`theme: deck`); `--theme` overrides
it, and a project's `scriptorium.yaml` decides for every file it lists.

## Why

Two ways to make a PDF from text, and neither is quite what you want:

- **Quarto / Typst** — easy to author, but the output is a *plain* document.
- **A hand-woven HTML + CSS design system** — beautiful, but every page is placed
  and balanced by hand.

Scriptorium is both: you author in Markdown (plus a little HTML when you want
it), and the engine places the pages with deterministic geometry — so "print to
PDF" yields real, controlled pages.

## Highlights

- **Exact-geometry PDF.** The `galley` engine measures rendered content and packs
  it into fixed pages: keep-together blocks, headings that don't strand, code and
  tables that split cleanly across a break, and a drift guard that catches any
  page that overflows its box.
- **Themes as project templates.** Themes inherit (`extends:`) and customize by
  `accent`, fonts, and other vars — rebrand a document without touching CSS. The
  default lineup spans **note → article → report → book → deck**.
- **Execute code in place.** Run fenced blocks in a subshell and splice stdout
  back as raw Markdown (or monospace, Quarto-style). Shared-kernel session state,
  a freeze cache, and cross-file imports — no Jupyter, no kernels.
- **Tangle.** `export=` code blocks extract into real source files
  (illiterate-compatible), with per-block provenance labels (file + line range).
- **Math without Node.** Inline `$…$` and display `$$…$$` render to SVG via
  quickjax (MathJax in an embedded QuickJS engine) — pure Python, no Node, no
  LaTeX install.
- **CSS-native numbering and cross-references.** Chapter/section numbering, `@ref`
  cross-references, and TOC page numbers are resolved by CSS counters and
  `target-counter` — no numbering pass in the engine.

## Install

Scriptorium is a Python package. It renders through **WeasyPrint**, which needs a
few system libraries (Pango, Cairo, GDK-PixBuf, libffi) — see the
[WeasyPrint install docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation)
for your platform. Then:

```bash
uv pip install git+https://github.com/apiad/scriptorium
# or, from a clone:
uv pip install -e .
```

Requires Python 3.12+. Vendored fonts (Inter, Source Serif 4, JetBrains Mono)
ship with the themes, so output is self-contained.

## Quickstart

A single document:

````markdown
---
title: A Field Guide to Abstractions
---

# Introduction

Some prose. Inline math like $O(\log n)$ just works, and so do
cross-references — see @sec-detail.

## Detail {#sec-detail}

```python {run}
print("| n | n squared |")
print("|---|-----------|")
for n in range(1, 4):
    print(f"| {n} | {n*n} |")
```
````

```bash
scriptorium render guide.md    # theme from frontmatter -> guide.pdf
```

A multi-file project is a `scriptorium.yaml`:

```yaml
theme: book
vars:
  title: The Book
  author: A. Writer
  accent: "#7c3aed"
files:
  - front.md
  - 01-intro.md
  - 02-body.md
code: { root: src }     # tangle target + PYTHONPATH for executed code
```

```bash
scriptorium render scriptorium.yaml     # concatenates the files -> book.pdf
scriptorium tangle scriptorium.yaml     # extract export= code into src/
```

## Themes

Themes are project templates. Point at one and customize with `vars:` — no theme
authoring needed for the common case.

| Theme | For |
|---|---|
| `note` | conference notes, handouts, minutes |
| `article` | essays, whitepapers, papers (title block with authors, affiliations, abstract, keywords) |
| `report` | data-forward briefings — covers, KPI tiles, finding cards, timelines |
| `book` | classic long-form — serif body, chapter numerals, running heads, auto-TOC |
| `deck` | 16:9 slides with report-grade visuals, agenda, section dividers, slide counter |

```yaml
theme: report
vars: { accent: "#0d9488", body-font: "Source Serif 4" }
```

All five `extend` a `base` theme; build your own by extending any of them. See
[`themes/README.md`](themes/README.md).

## Authoring

- **Components** — `::: finding amber {title="Risk"}` renders a theme component;
  `::: {.two-col}` is a plain styled div. Themes ship their own vocabulary.
- **Code** — `python {run}` executes; `{export=path}` tangles; `{run export=path}`
  does both; `{python}` is Quarto-compatible.
- **Math** — `$inline$` and `$$display$$`.
- **Cross-references** — `@type-id` resolves to "Figure 3.2 (p. 41)" via theme
  CSS. The prefix must be one of `fig` `tbl` `sec` `eq` `lst` `thm` `chap`;
  anything else (`@smith-2020`, a handle) stays literal text.
- **Footnotes** — `A claim.[^a]` with `[^a]: The note.` anywhere in the file.
  Numbering is automatic; a note referenced twice gets two back-links.
- **Citations** — `[@key]` and `[@a; @b]` render as `[1]` / `[1, 2]` against a
  `bibliography:` map in frontmatter (or in `scriptorium.yaml` for a project),
  and collect into a references section. Cited works only; add `nocite: [key]`
  for anything you want listed without citing. Entries are Markdown prose, so
  numeric styles only — author-date needs CSL, which is not built.
- **Layout** — `::: keep` (keep-together), `::: newpage`.

Where the notes land is the `footnotes:` key — frontmatter wins over the theme:

| Value | Behaviour |
|---|---|
| `document` | one endnotes section at the end (default; `book` overrides) |
| `chapter` | one section before each `#`, numbering restarts (the `book` default) |
| `page` | true bottom-of-page footnotes |

The full design is in [`docs/design.md`](docs/design.md).

## Status

Current release: **v0.5.0**. Solid and in use: exact-geometry PDF, the theme
system, code execution, tangle, math, footnotes, citations, and the deck format.
On the roadmap: a lean HTML-book renderer and EPUB output, real floats, and CSL
citations.

## License

MIT © Alejandro Piad
