# HTML Ebook Format — Design Spec

**Status:** revised · **Date:** 2026-08-14 · **Author:** Alex + Claude

---

## 1. Goal

Add a `html` output format to scriptorium that renders a Markdown book as a
single self-contained HTML file that reads beautifully online — two-page spread
on widescreen, single-page on mobile, swipe/click to turn pages, dark/light
toggle, TOC, font size control. The experience is a digital book, not a
scrolling web page.

**Non-goals:** offline/PWA (downstream app responsibility), full-text search
(future), EPUB (separate format, separate spec), full-bleed master pages (V1
fallback only — see §12).

---

## 2. Guiding principle

Lean on the CSS the PDF pipeline already produces. Scriptorium's `break-inside`,
`break-before`, and `break-after` fragmentation rules are column-fragmentation
rules, not print-only — browsers respect them in multi-column layout. The CSS
does the pagination; JavaScript only manages which column-page is currently
visible and persists reader state to localStorage. No DOM measurement, no
paragraph splitting, no JS pagination logic.

---

## 3. Architecture

### 3.1 Pipeline

The HTML path shares setup with the PDF path but diverges in two places before
the emit step:

1. **Footnote mode** — always `"document"` (endnotes), regardless of frontmatter.
   Per-page float footnotes use WeasyPrint-specific CSS with no column equivalent.
   `render_html()` passes the mode explicitly; no frontmatter setting overrides it.
2. **No `fill_toc()`** — the PDF path calls `fill_toc()` to insert an inline TOC
   unit into the stream. The HTML ebook builds its own sidebar TOC from the unit
   scan in `emit_ebook()`. `fill_toc()` is not called on the HTML path.

```
project.load() → process_footnotes(src, "document") → process_citations()
→ process_glossary() → parse.parse() → [execute.execute()] → math render
→ html.emit_ebook(units, theme, meta, options) → str
→ [optionally] html.embed_assets(html, base_path) → str
→ write output file
```

New top-level entry point: **`html.render_html()`** — mirrors `galley.render_pdf()`
in signature and setup. New module: **`scriptorium/html.py`** — does not modify
galley, parse, execute, theme, or any preprocessor.

### 3.2 New entry point

```python
# html.py
def render_html(src: str, out_path: str, base_url: str | None = None,
                theme_name: str | None = None, cwd: str | None = None,
                execute: bool = True, vars: dict | None = None,
                code_root: str | None = None,
                project_meta: dict | None = None) -> None:
    """Top-level entry point — mirrors render_pdf() for the HTML path."""

def emit_ebook(units: list[Unit], theme: Theme, meta: dict,
               options: EbookOptions) -> str:
    """Render unit stream as a self-contained HTML ebook reader."""

def embed_assets(html: str, base_path: str) -> str:
    """Inline local image and font URLs as data URIs (for single-file output)."""
```

`EbookOptions`:
- `embed: bool = True` — inline assets as data URIs
- `book_id: str` — slug used as localStorage namespace (derived from title)

### 3.3 CSS strategy

`emit_ebook` calls `_emit_ebook_css(theme, meta)`, which imports `_emit_css`
from `galley` (explicit cross-module dependency on a private function; acceptable
for V1, refactor candidate if a third consumer appears).

The raw `_emit_css()` output is post-processed:

1. **Strip** all `@page { … }` rules — `@page`, `@page:left`, `@page:right`,
   `@page master-*` (the `@bottom-*` / `@top-*` margin boxes are inside these
   and go with them)
2. **Strip** `.page { … }` and `.page:first-child { … }` blocks — fixed-geometry
   master wrappers have no column equivalent (see §12 for master handling)
3. **Strip** `.slide { … }` and `.slide:last-child { … }` — deck-only rules
4. **Strip** `string-set:` declarations — WeasyPrint-specific
5. **Translate** `break-before:page` → `break-before:column` in all surviving
   rules (`.pagebreak`, `.unit.break-before`)
6. **Append** ebook layout CSS (§4)

Theme typography (fonts, colors, component styles, callouts, tables, code)
passes through unchanged.

**Dark mode CSS.** `_emit_ebook_css` appends a minimal dark token block after
the theme CSS. If the theme directory contains a `dark.css` alongside
`styles.css`, that file's contents are used instead of the minimal fallback:

```css
[data-theme="dark"] {
  --bg: #1a1a1a; --ink: #e5e5e5; --rule: #333; --muted: #888;
  color-scheme: dark;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #1a1a1a; --ink: #e5e5e5; --rule: #333; --muted: #888;
    color-scheme: dark;
  }
}
```

**Font-size control.** `_emit_ebook_css` appends:

```css
:root { --body-size: 1rem; }
body  { font-size: var(--body-size); }
```

This injects the variable into the cascade so JS font-size control works even
if the theme does not use `--body-size`. Themes that set an absolute `font-size`
on `body` or `p` will override this — known V1 limitation.

---

## 4. Layout CSS

```css
/* Reader chrome */
:root {
  --toolbar-h: 2.75rem;
  --toc-w: 18rem;
  --spine-gap: 5vw;
  --page-pad: 4vw;
}

*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; overflow: hidden; height: 100%; }

/* Toolbar */
.reader-toolbar {
  position: fixed; top: 0; left: 0; right: 0;
  height: var(--toolbar-h);
  display: flex; align-items: center; gap: .5rem; padding: 0 1rem;
  background: var(--bg); border-bottom: 1px solid var(--rule);
  z-index: 100;
}

/* TOC drawer */
.reader-toc {
  position: fixed; top: var(--toolbar-h); left: 0; bottom: 0;
  width: var(--toc-w); overflow-y: auto;
  background: var(--bg); border-right: 1px solid var(--rule);
  padding: 1rem; z-index: 90;
  transform: translateX(-100%); transition: transform .25s ease;
}
.reader-toc.open { transform: translateX(0); }

/* Clipping viewport */
.reader-viewport {
  position: fixed; top: var(--toolbar-h); left: 0; right: 0; bottom: 0;
  overflow: hidden;
}

/* Column strip — the only moving part */
.ebook-content {
  column-count: 2;
  column-fill: auto;
  column-gap: var(--spine-gap);
  height: 100%;
  padding: 3rem var(--page-pad);
  transition: transform .35s cubic-bezier(.4, 0, .2, 1);
  will-change: transform;
}

/* Fragmentation (same as PDF, browser honours in columns) */
.unit              { break-inside: avoid; }
.unit.break-before { break-before: column; }
.unit.keep         { break-inside: avoid; }
.pagebreak         { break-before: column; display: block; height: 0; }
figure             { break-inside: avoid; }
h1, h2, h3        { break-after: avoid; }

/* Mobile: single column */
@media (max-width: 768px), (orientation: portrait and max-width: 1024px) {
  .ebook-content { column-count: 1; padding: 2rem 1.25rem; }
}
```

Dark-mode and `--body-size` CSS are generated by `_emit_ebook_css` (§3.3) and
appended after this block; they are not part of the static layout string.

---

## 5. HTML shell structure

```html
<!DOCTYPE html>
<html lang="{{lang}}" data-theme="{{default_theme}}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{title}}</title>
  <style>/* theme CSS (filtered) + ebook layout CSS + dark + body-size */</style>
</head>
<body>

<nav class="reader-toolbar">
  <button class="btn-toc" aria-label="Table of contents">☰</button>
  <span class="reader-title">{{title}}</span>
  <span class="reader-spacer"></span>
  <button class="btn-fontdown" aria-label="Decrease font">A−</button>
  <button class="btn-fontup"   aria-label="Increase font">A+</button>
  <button class="btn-theme"    aria-label="Toggle theme">◑</button>
  <span class="reader-page">1 / N</span>
</nav>

<aside class="reader-toc">
  <ul>{{#toc}}<li><a href="#{{id}}">{{text}}</a></li>{{/toc}}</ul>
</aside>

<div class="reader-viewport" id="reader-viewport">
  <div class="ebook-content" id="ebook-content">
    {{units}}
  </div>
</div>

<script>/* ~150 lines, see §6 */</script>
</body>
</html>
```

`{{toc}}` is built by scanning units for h1/h2 headings and reading `heading_id`
and `heading` directly from the `Unit` fields — `parse.py` always sets `heading_id`
for heading units. No ID injection at emit time.

---

## 6. JavaScript

~150 lines, vanilla, no dependencies. Responsibilities:

**Page navigation**
- `calcPages()` — reads `content.scrollWidth / viewport.clientWidth` after layout
- `goToPage(n)` — clamps, sets `content.style.transform`, updates page counter,
  saves to localStorage
- Triggers: keyboard (`←`, `→`, `Space`, `PageUp/Down`), touch swipe (>40px),
  click in left/right 30% of viewport

**TOC jump**
- `Math.floor(el.offsetLeft / viewport.clientWidth)` gives the page index.
  `offsetLeft` in a multi-column strip measures the element's horizontal distance
  from the content div's left edge — no transform removal, no reflow, no flash.
- TOC drawer: toggle `.open` class on `.reader-toc`

**Theme toggle**
- Cycles: `auto` → `light` → `dark` → `auto`
- Sets `data-theme` on `<html>`, persists to localStorage

**Font size**
- 5 levels: −2 to +2, maps to `[14, 16, 18, 20, 22]px` on `--body-size`
- After change: wait one rAF for reflow, then `calcPages(); goToPage(current)`

**State persistence** — all state under `ebook:{{book_id}}:` namespace in
localStorage: `page`, `theme`, `fontSize`.

**Resize** — recalculate pages on `window.resize`, clamp current page.

No external requests. No event listeners outside the reader container. Total
minified size target: < 3 KB.

---

## 7. TOC generation

`heading_id` is always set by `parse.py` for heading units; no ID injection or
slug generation needed at emit time.

```python
toc = [
    {"id": u.heading_id, "level": u.heading_level, "text": u.heading}
    for u in units
    if u.heading_id and u.heading_level in (1, 2)
    and "unlisted" not in u.heading_classes
]
```

Rendered as `<ul>` with `h2` entries indented under their `h1` parent.

---

## 8. Asset embedding

`embed_assets(html, base_path)`:

1. Find `<img src="...">` with local (non-`http`, non-`data:`) src
2. Find `url('...')` in `<style>` blocks (fonts, background images)
3. For each: read file, detect MIME type, base64-encode, replace with
   `data:<mime>;base64,<data>`
4. Large files (> 5 MB) emit a warning and are left as relative paths —
   they won't work in single-file mode but won't corrupt the document

Math SVGs from `mathrender.py` are already emitted as inline base64
`<img src="data:image/svg+xml;base64,...">` — no special case needed.

Default: embed on. `--no-embed` skips steps 1–3 and writes output to a
directory (`<stem>/index.html` + `assets/`) instead of a single file.

---

## 9. CLI changes

Extend `scriptorium render` with a `--format` flag:

```
scriptorium render [file.md | scriptorium.yaml] [--format pdf|html] [-o OUTPUT]
```

- `--format pdf` (default): existing behaviour, calls `galley.render_pdf()`
- `--format html`: calls `html.render_html()`; default output `<stem>.html`
- `--no-embed`: paired with `--format html`; output directory + linked assets

---

## 10. What is NOT changed

- `galley.py`, `galley.render_pdf()`, `emit()`, `emit_deck()` — untouched
- `parse.py`, `execute.py`, `theme.py` — untouched
- All existing themes — no changes required; the HTML renderer filters their CSS

**Preprocessors:** `process_citations` and `process_glossary` run unchanged.
`process_footnotes` is called with forced `"document"` mode. `fill_toc()` is
not called on the HTML path.

**Required CSS variable contract** (already satisfied by every theme that extends
`base`): `--bg`, `--ink`, `--rule`, `--muted`, `--heading-font`. These five are
the only variables the reader chrome and the generated dark-mode block reference.

---

## 11. Files created / modified

| Path | Change |
|---|---|
| `scriptorium/html.py` | NEW — `render_html()`, `emit_ebook()`, `embed_assets()`, `_emit_ebook_css()` |
| `scriptorium/cli.py` | add `--format`, `--no-embed` flags; wire `render_html()` |
| `docs/superpowers/specs/2026-08-14-html-ebook-design.md` | this document |

No new theme directories. No new dependencies (vanilla JS, data URIs, no Vite/Svelte).

---

## 12. Resolved decisions

**Masters (full-page covers, section openers).** `emit_ebook` emits `full_page`
units as `<div class="unit break-before full-page">` — the pre-rendered content
is preserved and a column break is forced before the unit, but no fixed geometry
is applied. Visual fidelity of full-bleed masters is not preserved; title text
and section headings render in-flow. Full-bleed ebook master support is a future
enhancement requiring a separate CSS contract.

**Math.** `mathrender.py` emits SVGs as `<img src="data:image/svg+xml;base64,...">`.
Already self-contained; `embed_assets` handles them via the `<img>` regex. No
special case.

**Running heads.** Stripped. Toolbar shows the book title statically. Dynamic
chapter-title tracking in the toolbar is a future enhancement.

**Page number display.** Raw column index: "12 / 84". Chapter context is future.

**Footnotes.** `render_html()` calls `process_footnotes(src, "document")` — the
mode is hardcoded for the HTML path. No frontmatter key can re-enable per-page
float mode for HTML output. Endnotes render at document end as regular flow
content, which is correct for column mode.

**Glossary page back-links.** The glossary preprocessor generates `(p. N)`
back-references. In column mode these column indices are cosmetically meaningless
but syntactically harmless — they render as-is in V1. Suppressing them for the
HTML path is a future enhancement.
