# Changelog

All notable changes to this project are documented here. Format: Keep a Changelog.

## [Unreleased]

### Fixes
- **Back-links carry the page they point at.** A reference cited four times used
  to end in four identical `↩` marks, which told the reader nothing about where
  the citations were. The apparatus is now one arrow followed by the page number
  of each call site (`↩ 4, 7, 12`), resolved by CSS `target-counter` — the same
  mechanism the `book` theme already uses for cross-references and its TOC.

## [v0.6.0] - 2026-08-12

Narrative citations: the author's name in the running text, declared rather
than parsed.

### Features
- **Narrative citations.** `[+@key]` renders the author's name before the
  numbered mark (`Tam et al. [1]`); `[-@key]` renders the name alone, with no
  mark and no references entry. Both read a declared `author:` from an
  `{author, text}` bibliography entry — the engine never parses a name out of
  entry prose, and never derives one from the key. Prose-string entries and bare
  `[@key]` are unchanged. A sigil on an entry with no `author:`, or on a
  multi-key span, leaves the span literal and warns.
- **Bibliography entries take a mapping.** A value may stay a prose string or
  become `{author, text}`. `text:` is the prose that reaches the references
  section; `author:` is the literal name the narrative forms emit, so "et al."
  versus "and" versus a single surname is the author's decision rather than a
  heuristic on the key.

### Fixes
- **A loose list is one block, so its numbering survives.** Prose is split on
  blank lines to measure paragraphs independently, but a loose list is
  blank-line separated by definition, so each item became its own `<ol>` and
  "1. 2. 3." rendered as "1. 1. 1.", with continuation paragraphs detached from
  their item.
- **Inline code never hyphenates.** `FechaRetiro` broken across a narrow table
  column came out as `FechaRe-tiro`; in a document whose subject is the exact
  column names that is a wrong answer, not a blemish. Wrapping is still allowed
  — the token splits without a character being invented.

### Other
- The claim that author-date was "impossible by construction" is retired from
  the module docstring, `docs/design.md` §7.5, `tasks.md` and the README. What
  is impossible is *extraction* from prose; *declaration* was never ruled out.
  The open CSL item is narrowed to what still needs structured entries and a
  style engine: author-date marks everywhere, alphabetical ordering, and
  `2026a` / `2026b` disambiguation.

## [v0.5.0] - 2026-08-11

Citations: `[@key]` against an author-declared bibliography, collected into
a references section distinct from the footnote apparatus.

### Features
- **Numbered citations.** `[@key]` and `[@a; @b]` resolve against a
  `bibliography:` map declared in frontmatter — or, for a multi-file project, as
  a top-level key in `scriptorium.yaml` — and render as `[1]` / `[1, 2]`,
  collecting into a generated references section. Cited works only, numbered by
  first appearance, with `nocite:` for anything to be listed without citing.
  Entries are Markdown prose, so their links and emphasis survive to the page.
  Notes and references are separate apparatuses: distinct sections, distinct
  counters, bracketed `[1]` versus a bare superscript.
- **`Report.warnings`**, printed by the CLI beside the oversize warnings.
  Document renders previously emitted no warnings at all.

### Fixes
- **Footnote problems are now actually reported.** The v0.4.0 design said an
  unresolved `[^marker]` was reported; it was silently skipped, because there
  was no channel to report it on. A marker with no definition and a definition
  nobody references both warn now.
- **No more empty notes section.** A document whose only footnote definition was
  never cited emitted a bare `::: footnotes` block, which rendered as an empty
  ruled band.

## [v0.4.0] - 2026-08-11

Footnotes: real Markdown `[^id]` notes as endnotes or page-bottom floats,
replacing the hand-numbered house convention.

### Features
- **Markdown footnotes.** `[^a]` markers with `[^a]: body` definitions, numbered
  automatically, collected into an endnotes section at the end of the document
  or of each chapter — or floated to the foot of the page. The mode is the
  `footnotes:` key (`document` | `chapter` | `page`), frontmatter over theme;
  `book` defaults to `chapter`. Note bodies keep their Markdown, and a note
  referenced twice gets a back-link per call site.
- **Per-page footnotes**, via WeasyPrint's CSS GCPM `float: footnote`. The
  design previously rejected these as circular; that applied to the Python
  bin-packer v0.3.0 replaced.

### Fixes
- **Cross-references no longer delete prose.** `@type-id` matched *any*
  hyphenated prefix and rewrote it to an anchor with no target, which renders
  empty — so `@smith-2020`, `@piad-morffis-2024` or a GitHub handle silently
  vanished from the PDF. Only `fig` `tbl` `sec` `eq` `lst` `thm` `chap` are
  rewritten now; everything else stays literal text, which also frees the `@key`
  namespace for a future citations feature.

### Removed
- `citations.py` and the hand-numbered `^[N](#ref-N)^` / `### N {#ref-N}` house
  convention it served, with its `.cite-*` and `.bib-*` CSS. Markdown footnotes
  replace it outright. Documents still written the old way degrade to visible
  literal text, not a crash.

## [v0.3.1] - 2026-08-11

### Fixes
- **A document can declare its own theme.** `theme:` in frontmatter was ignored —
  the theme was loaded before the frontmatter was read, so every single-file
  render used `--theme` or fell back to `report`. `scriptorium render talk.md`
  on a deck therefore produced a flowed report, not slides. Resolution order is
  now explicit (`--theme`, or a project's `scriptorium.yaml`) → frontmatter
  `theme:` → default.
- Every file in `examples/` declares its theme, so the examples render correctly
  straight from the README with no flag.

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
