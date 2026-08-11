# Changelog

All notable changes to this project are documented here. Format: Keep a Changelog.

## [Unreleased]

## [v0.3.0] - 2026-08-11

Slides and scholarship: a 16:9 deck format, LaTeX-style citations, and a
pagination engine rebuilt on CSS Fragmentation instead of Python bin-packing.

### Features
- **Deck format** — a theme with `mode: deck` renders 16:9 (or 4:3, or explicit
  `WxH`) slides instead of flowing pages, split at section (`#` → divider) and
  slide (`##` → content) boundaries. Page geometry is theme-driven. Oversized
  slides warn rather than auto-shrink.
- **Deck masters** — `::: toc` becomes an agenda slide listing sections with
  their slide numbers; `statement` gives a full-bleed single-line slide;
  `closing` a final slide with a contact line. The `deck` theme extends
  `report`, so KPI tiles, finding cards, and stat strips drop straight onto
  slides.
- **Citations** — `^[N](#ref-N)^` and `[N](#ref-N)` render as true superscript
  links and gain double-sided hyperlinks: each bibliography entry carries
  back-links (↑ 1, 2, …) to every place it is cited.
- **CSS Fragmentation pagination** — document themes now emit one continuous
  flow and let WeasyPrint break it: `break-after: avoid` on headings,
  `break-inside: avoid` on keep blocks and figures, named `@page` rules for
  full-page masters, `@page` margin boxes for running heads and stamps, and
  `string-set` for automatic running chapter/section titles. Prose flows across
  page boundaries instead of leaving gaps. The deck path keeps the measure/pack
  pipeline.
- **Article typography** — justified text with real hyphenation (`lang` reaches
  pyphen), orphan/widow control, and compact full-width tables that never
  overflow the margin.
- **Frontmatter `vars:`** — a single document can override `accent`, fonts, and
  other theme vars from its own frontmatter, same contract as `scriptorium.yaml`.

### Fixes
- Deck slides no longer fragment onto a second page each — `@page` was adding
  the theme margin on top of the slide's own padding. The reported page count is
  now the PDF's real page count, not the slide count.
- A five-section agenda fits on one slide again (stacked unit gap and entry
  margins were compounding).
- `report`: bold text is visible on dark surfaces (`.cta`, `.page.dark`), `.tier`
  owns its body colour, and `.sec-title` does not hyphenate.
- Headings never hyphenate, with a `.no-hyphen` utility for inline spans.
- Bibliography entries lay out with flexbox, so back-links stay right-aligned on
  the entry's first line instead of wrapping to their own row.
- Full-page masters render from the pre-rendered template HTML.

### Other
- Public README, `AGENTS.md`, and `know-how/` (galley engine, theme authoring,
  deck format, releasing).

## [v0.2.0] - 2026-07-28

The theme system — a small set of archetypes you customize and inherit from,
spanning conference notes to polished books.

### Features
- **Theme inheritance** — `extends:` in `theme.yml` merges a parent's CSS,
  components, masters, and var-defaults (child wins), so a theme is a diff.
- **`base` + a default lineup** (simple → gorgeous): `note` (handouts),
  `article` (essays/whitepapers), `report` (data-forward briefings), `book`
  (classic long-form). Each has a distinct point of view.
- **Customization contract** — `accent`, `body-font`, `heading-font`,
  `mono-font`, etc. injected as CSS custom properties; rebrand a document with
  `vars:` alone, no theme authoring.
- **Vendored fonts that actually embed** — Inter, Source Serif 4, JetBrains Mono
  ship as woff2; relative `@font-face` urls are rewritten to absolute at load
  (they were silently falling back to system fonts before).
- **Template loops** — `{{#list}}…{{/list}}` iterates with per-item scope,
  `{{_n}}` index, and `{{.}}` for scalar lists; sections nest and drop when empty.
- **Academic title block** (article) — title, subtitle, multiple authors with
  numbered affiliations, date, abstract, and keywords, driven from frontmatter.

### Fixes
- The page margin is a single value: galley injects it and `base` applies it as
  `.page` padding, so the visual inset can't disagree with the measured content
  width (some themes were rendering with no margin).

### Other
- Scrubbed all project-specific references — scriptorium is a generic tool.

## [v0.1.0] - 2026-07-28

First release. A Markdown-native document engine that weaves to exact-geometry
paginated PDF, executes code in place, and tangles code to source — validated by
rendering a full 440-page technical book (title/copyright pages, dozens of
chapters and appendices, with every `{python}` cell executed).

### Features
- **galley pagination engine** — measure → pack → emit to exact-geometry A4 pages,
  with a drift guard, keep-with-next headings, and line-splitting for code and
  tables so listings never overflow.
- **Themes as project templates** — directory-backed themes (CSS + components +
  masters); a `marketing` report theme and a `book` theme. Numbering,
  cross-references, and TOC page numbers are pure theme CSS (counters,
  `target-counter`/`target-text`).
- **Execution** — run fenced code in a subshell and splice stdout back
  (Quarto-`{python}` monospace or native `{run}` raw-markdown); shared-kernel
  session state, `PYTHONPATH`, and a freeze cache.
- **Tangle** — `export=` code extraction (illiterate-compatible, byte-exact),
  with provenance labels showing each block's file and line range.
- **Math** — LaTeX `$…$` / `$$…$$` to SVG via quickjax (MathJax in QuickJS,
  pure Python, no Node), freeze-cached.
- **Projects** — `scriptorium.yaml` (theme + vars + file list) with `{{var}}`
  substitution; running heads and auto-TOC.
- **CLI** — `scriptorium render` (document or project) and `scriptorium tangle [--test]`.
