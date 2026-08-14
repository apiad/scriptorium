# HTML Ebook Format — Design Spec

**Status:** approved · **Date:** 2026-08-14 · **Author:** Alex + Claude

---

## 1. Goal

Add a `html` output format to scriptorium that renders a Markdown book as a
single self-contained HTML file that reads beautifully online — two-page spread
on widescreen, single-page on mobile, swipe/click to turn pages, dark/light
toggle, TOC, font size control. The experience is a digital book, not a
scrolling web page.

**Non-goals:** offline/PWA (downstream app responsibility), full-text search
(future), EPUB (separate format, separate spec).

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

Identical to PDF up to `emit()`:

```
project.load() → preprocessors (footnotes, citations, glossary)
→ parse.parse() → execute.execute() → math render
→ html.emit_ebook(units, theme, meta, options) → str
→ [optionally] html.embed_assets(html, base_path) → str
→ write output file
```

New module: **`scriptorium/html.py`** — no changes to the existing parse/execute/galley
pipeline. `galley.render_pdf()` is untouched.

### 3.2 New entry point

```python
# html.py
def emit_ebook(units: list[Unit], theme: Theme, meta: dict, options: EbookOptions) -> str:
    """Render unit stream as a self-contained HTML ebook reader."""

def embed_assets(html: str, base_path: str) -> str:
    """Inline local image and font URLs as data URIs (for single-file output)."""
```

`EbookOptions`:
- `embed: bool = True` — inline assets as data URIs
- `book_id: str` — slug used as localStorage namespace (derived from title)

### 3.3 CSS strategy

`emit_ebook` calls `_emit_ebook_css(theme, meta)` which reuses `_emit_css()` but
post-processes the result:

1. **Strip** all `@page { … }` rules (including `@page master-*`)
2. **Strip** `@bottom-*` and `@top-*` margin box rules (running heads)
3. **Strip** fixed `.page { width: Nmm; height: Nmm }` geometry
4. **Translate** `break-before: page` → `break-before: column` (column context)
5. **Append** ebook layout CSS (see §4)

Theme typography (fonts, colors, component styles, callouts, tables, code) passes
through unchanged — the HTML output looks like the PDF, just flowing into the
viewport instead of a fixed page size.

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
.unit          { break-inside: avoid; }
.unit.break-before { break-before: column; }
.unit.keep     { break-inside: avoid; }
.pagebreak     { break-before: column; display: block; height: 0; }
figure         { break-inside: avoid; }
h1, h2, h3    { break-after: avoid; }

/* Mobile: single column */
@media (max-width: 768px), (orientation: portrait and max-width: 1024px) {
  .ebook-content { column-count: 1; padding: 2rem 1.25rem; }
}

/* Dark mode (data-theme attribute, toggled by JS) */
[data-theme="dark"] { color-scheme: dark; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { color-scheme: dark; }
}
```

Dark/light colors come from the existing theme CSS variable contract
(`--bg`, `--ink`, `--rule`, etc.) extended with a dark variant via
`[data-theme="dark"]` overrides appended after the theme CSS.

Font size is a CSS custom property `--body-size` on `:root`; theme CSS uses it
as `font-size: var(--body-size, 1rem)` (or the renderer injects a wrapper rule
at emit time).

---

## 5. HTML shell structure

```html
<!DOCTYPE html>
<html lang="{{lang}}" data-theme="{{default_theme}}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{title}}</title>
  <style>/* theme CSS (filtered) + ebook layout CSS */</style>
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
    <!-- same unit HTML as emit() produces -->
    {{units}}
  </div>
</div>

<script>/* ~150 lines, see §6 */</script>
</body>
</html>
```

`{{toc}}` is generated by the renderer: scan units for headings at h1/h2 level,
collect their text and IDs. Heading IDs are added by `parse.py` (or injected
at emit time if not already present).

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
- Temporarily remove transform, read `el.getBoundingClientRect()` relative to
  content origin, restore transform, compute page index, call `goToPage()`
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

In `emit_ebook()`, before emitting units, scan for heading units:

```python
toc = []
for u in units:
    if u.heading and u.heading_level in (1, 2):
        slug = slugify(u.heading_text)
        ensure_id(u, slug)  # inject id= into u.html if missing
        toc.append({"id": slug, "level": u.heading_level, "text": u.heading_text})
```

The TOC is injected into the reader shell as an `<ul>` with `h2` entries
indented under their `h1` parent.

---

## 8. Asset embedding

`embed_assets(html, base_path)`:

1. Find `<img src="...">` with local (non-`http`, non-`data:`) src
2. Find `url('...')` in `<style>` blocks (fonts, background images)
3. For each: read file, detect MIME type, base64-encode, replace with
   `data:<mime>;base64,<data>`
4. Large files (> 5 MB) emit a warning and are left as relative paths with a
   comment — they won't work in truly single-file mode but won't corrupt the
   document either

Default: embed on. Flag `--no-embed` skips step 1-3 and writes output to a
directory (`<stem>/index.html` + `assets/`) instead of a single file.

---

## 9. CLI changes

Extend `scriptorium render` with a `--format` flag:

```
scriptorium render [file.md | scriptorium.yaml] [--format pdf|html] [-o OUTPUT]
```

- `--format pdf` (default): existing behaviour
- `--format html`: invoke `html.emit_ebook()`; default output `<stem>.html`
- `--no-embed`: paired with `--format html`; output directory + linked assets

Per `docs/design.md §14`, the positional form `scriptorium render html` is
also acceptable — implementation may support both.

---

## 10. What is NOT changed

- `galley.py`, `galley.render_pdf()`, `emit()`, `emit_deck()` — untouched
- `parse.py`, `execute.py`, `theme.py`, all preprocessors — untouched
- All existing themes — no changes required; the HTML renderer filters their CSS

The only requirement on themes is that they expose `--bg`, `--ink`, `--rule`
CSS variables (already in the base theme contract) so the reader chrome can
use them.

---

## 11. Files created / modified

| Path | Change |
|---|---|
| `scriptorium/html.py` | NEW — `emit_ebook()`, `embed_assets()`, `_emit_ebook_css()`, `_build_toc()` |
| `scriptorium/__main__.py` (or `cli.py`) | add `--format`, `--no-embed` flags |
| `docs/superpowers/specs/2026-08-14-html-ebook-design.md` | this document |

No new theme directories. No new dependencies (vanilla JS, data URIs, no Vite/Svelte).

---

## 12. Open questions (deferred to implementation)

- Should masters (cover, section opener) render in HTML mode? Likely: yes, as
  `<div class="page master-cover">` with the master's HTML, forced column break
  before/after. Worth verifying that CSS columns handles full-bleed masters
  acceptably.
- Math: quickjax SVGs inline fine as `<img src="data:image/svg+xml;base64,...">`.
  Confirm that `embed_assets()` catches these or that they're already inlined
  by the math renderer.
- Running heads (`@bottom-*` / `@top-*`): stripped. Could add a fixed position
  chapter title display in the toolbar instead. Defer.
- Page number display: "12 / 84" (column index) vs "Ch 2" vs both. Start with
  raw column index; chapter context is a future enhancement.
