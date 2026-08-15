# HTML Ebook Format — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `scriptorium render --format html` that produces a self-contained
single-file HTML ebook reader from any Markdown document or project.

**Architecture:** A new `scriptorium/html.py` module handles all HTML output.
It reuses `_emit_css()` from galley (post-processed to strip print-only rules),
builds a full HTML shell with inline CSS and ~90 lines of vanilla JS, and
optionally inlines all assets as data URIs. The PDF pipeline is untouched.

**Tech Stack:** Python 3.12+, vanilla JS (no transpiler, no bundler), CSS
multi-column fragmentation, data URIs for asset embedding.

**Spec:** `docs/superpowers/specs/2026-08-14-html-ebook-design.md`

## Global Constraints

- Python 3.12+ — use `str | None` union syntax, `match`, walrus operators freely
- No new runtime dependencies — stdlib only (`re`, `base64`, `mimetypes`, `html`, `pathlib`)
- `uv run pytest` must pass before every commit
- All existing tests must remain green — `galley.py`, `parse.py`, `theme.py` are untouched
- English throughout — identifiers, comments, CLI help text
- One logical change per commit, conventional commits

---

## File Map

| Path | Status | Responsibility |
|------|--------|---------------|
| `scriptorium/html.py` | NEW | All HTML output: CSS post-processing, TOC, unit emission, JS, shell, asset embedding, entry point |
| `scriptorium/cli.py` | MODIFY | Add `--format pdf\|html` and `--no-embed` flags; wire `render_html()` |
| `tests/test_html.py` | NEW | All tests for html.py |

No other files are modified.

---

## Task 1: CSS Post-Processor (`_emit_ebook_css`)

**Files:**
- Create: `scriptorium/html.py`
- Create: `tests/test_html.py`

**Interfaces:**
- Consumes: `_emit_css(theme, meta) -> str` from `scriptorium.galley`; `Theme` from `scriptorium.theme`; `load_theme(name) -> Theme` from `scriptorium.theme`
- Produces: `_emit_ebook_css(theme: Theme, meta: dict | None) -> str` — filtered CSS string ready for injection into the ebook `<style>` block

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_html.py
"""Tests for scriptorium.html — HTML ebook output."""

from scriptorium.html import _emit_ebook_css
from scriptorium.theme import load_theme


def test_emit_ebook_css_strips_at_page():
    """No @page rules should survive into ebook CSS."""
    css = _emit_ebook_css(load_theme("report"), {})
    assert "@page" not in css


def test_emit_ebook_css_strips_page_block():
    """Fixed-geometry .page{} blocks must be stripped."""
    css = _emit_ebook_css(load_theme("report"), {})
    assert ".page{" not in css
    assert ".page:first-child" not in css


def test_emit_ebook_css_strips_slide_block():
    """Deck-only .slide{} blocks must be stripped."""
    css = _emit_ebook_css(load_theme("report"), {})
    assert ".slide{" not in css


def test_emit_ebook_css_strips_string_set():
    """WeasyPrint string-set declarations must be stripped."""
    css = _emit_ebook_css(load_theme("report"), {})
    assert "string-set:" not in css


def test_emit_ebook_css_translates_break_before():
    """break-before:page must become break-before:column; no page value survives."""
    css = _emit_ebook_css(load_theme("report"), {})
    assert "break-before:page" not in css
    assert "break-before:column" in css


def test_emit_ebook_css_appends_layout():
    """Layout CSS (column strip, toolbar, viewport) must be present."""
    css = _emit_ebook_css(load_theme("report"), {})
    assert ".ebook-content" in css
    assert ".reader-toolbar" in css
    assert ".reader-viewport" in css


def test_emit_ebook_css_appends_dark_mode():
    """Dark mode block must be appended."""
    css = _emit_ebook_css(load_theme("report"), {})
    assert '[data-theme="dark"]' in css


def test_emit_ebook_css_appends_body_size():
    """--body-size variable and body font-size rule must be appended."""
    css = _emit_ebook_css(load_theme("report"), {})
    assert "--body-size" in css
    assert "body{font-size:var(--body-size)" in css
```

- [ ] **Step 2: Run tests to verify they all fail**

```bash
cd repos/scriptorium && uv run pytest tests/test_html.py -v
```

Expected: `ImportError: cannot import name '_emit_ebook_css' from 'scriptorium.html'`
(module doesn't exist yet — that's correct)

- [ ] **Step 3: Create `scriptorium/html.py` with `_emit_ebook_css`**

```python
"""HTML ebook output — render_html(), emit_ebook(), embed_assets()."""

import base64
import html as _html
import mimetypes
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from .galley import _emit_css, _APPEARANCE, resolve_theme_name
from .model import Unit
from .theme import Theme, THEMES_DIR, load_theme


# ── Layout CSS (static — appended to every ebook) ─────────────────────────

_LAYOUT_CSS = """\
:root{--toolbar-h:2.75rem;--toc-w:18rem;--spine-gap:5vw;--page-pad:4vw}
*,*::before,*::after{box-sizing:border-box}
html,body{margin:0;overflow:hidden;height:100%}
.reader-toolbar{position:fixed;top:0;left:0;right:0;height:var(--toolbar-h);
  display:flex;align-items:center;gap:.5rem;padding:0 1rem;
  background:var(--bg);border-bottom:1px solid var(--rule);z-index:100}
.reader-spacer{flex:1}
.reader-toc{position:fixed;top:var(--toolbar-h);left:0;bottom:0;
  width:var(--toc-w);overflow-y:auto;background:var(--bg);
  border-right:1px solid var(--rule);padding:1rem;z-index:90;
  transform:translateX(-100%);transition:transform .25s ease}
.reader-toc.open{transform:translateX(0)}
.reader-viewport{position:fixed;top:var(--toolbar-h);left:0;right:0;bottom:0;
  overflow:hidden}
.ebook-content{column-count:2;column-fill:auto;column-gap:var(--spine-gap);
  height:100%;padding:3rem var(--page-pad);
  transition:transform .35s cubic-bezier(.4,0,.2,1);will-change:transform}
.unit{break-inside:avoid}
.unit.break-before{break-before:column}
.unit.keep{break-inside:avoid}
.unit.full-page{break-before:column}
.pagebreak{break-before:column;display:block;height:0}
figure{break-inside:avoid}
h1,h2,h3{break-after:avoid}
@media(max-width:768px),(orientation:portrait and max-width:1024px){
  .ebook-content{column-count:1;padding:2rem 1.25rem}}
"""

_DARK_FALLBACK = """\
[data-theme="dark"]{--bg:#1a1a1a;--ink:#e5e5e5;--rule:#333;--muted:#888;color-scheme:dark}
@media(prefers-color-scheme:dark){
  :root:not([data-theme="light"]){--bg:#1a1a1a;--ink:#e5e5e5;--rule:#333;--muted:#888;color-scheme:dark}}
"""

_BODY_SIZE = ":root{--body-size:1rem}body{font-size:var(--body-size)}"


# ── CSS post-processor ─────────────────────────────────────────────────────

# Matches @page rules with up to one level of brace nesting (covers
# @page:left{@top-left{...}} and @page{@bottom-left{...}@bottom-right{...}}).
_AT_PAGE = re.compile(r'@page[^{]*\{(?:[^{}]*|\{[^{}]*\})*\}')
# Matches .page{...} and .page:first-child{...} (no nesting).
_PAGE_BLOCK = re.compile(r'\.page(?::first-child)?\{[^}]*\}')
# Matches .slide{...} and .slide:last-child{...}.
_SLIDE_BLOCK = re.compile(r'\.slide(?::last-child)?\{[^}]*\}')
# Matches standalone rules whose only property is string-set (WeasyPrint-only).
_STRING_SET = re.compile(r'[^{}]+\{string-set:[^}]*\}')


def _emit_ebook_css(theme: Theme, meta: dict | None = None) -> str:
    """Return filtered + extended CSS for the ebook reader."""
    meta = meta or {}
    css = _emit_css(theme, meta)
    css = _AT_PAGE.sub("", css)
    css = _PAGE_BLOCK.sub("", css)
    css = _SLIDE_BLOCK.sub("", css)
    css = _STRING_SET.sub("", css)
    css = css.replace("break-before:page", "break-before:column")

    dark_path = THEMES_DIR / theme.name / "dark.css"
    dark = dark_path.read_text(encoding="utf-8") if dark_path.exists() else _DARK_FALLBACK

    return css + _LAYOUT_CSS + dark + _BODY_SIZE
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_html.py -v
```

Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scriptorium/html.py tests/test_html.py
git commit -m "feat(html): add _emit_ebook_css — CSS post-processor for ebook output"
```

---

## Task 2: Unit Processors (`_build_toc`, `_emit_units`)

**Files:**
- Modify: `scriptorium/html.py` — add `_build_toc`, `_emit_units`
- Modify: `tests/test_html.py` — add tests

**Interfaces:**
- Consumes: `Unit` from `scriptorium.model` — fields used: `heading`, `heading_id`, `heading_level`, `heading_classes`, `is_break`, `full_page`, `break_before`, `keep_together`, `html`
- Produces:
  - `_build_toc(units: list[Unit]) -> list[dict]` — each dict has `{"id": str, "level": int, "text": str}`
  - `_emit_units(units: list[Unit]) -> str` — HTML string of all unit divs

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_html.py

from scriptorium.html import _build_toc, _emit_units
from scriptorium.model import Unit


def test_build_toc_collects_h1_and_h2():
    units = [
        Unit(html="<h1>Ch 1</h1>", heading="Ch 1", heading_level=1, heading_id="ch1"),
        Unit(html="<h2>Sec 1.1</h2>", heading="Sec 1.1", heading_level=2, heading_id="s1-1"),
        Unit(html="<h3>Deep</h3>", heading="Deep", heading_level=3, heading_id="deep"),
        Unit(html="<p>prose</p>"),
    ]
    toc = _build_toc(units)
    assert len(toc) == 2
    assert toc[0] == {"id": "ch1", "level": 1, "text": "Ch 1"}
    assert toc[1] == {"id": "s1-1", "level": 2, "text": "Sec 1.1"}


def test_build_toc_excludes_unlisted():
    units = [
        Unit(heading="Hidden", heading_level=1, heading_id="h",
             heading_classes=("unlisted",)),
    ]
    assert _build_toc(units) == []


def test_build_toc_excludes_headings_without_id():
    units = [Unit(heading="No ID", heading_level=1, heading_id=None)]
    assert _build_toc(units) == []


def test_emit_units_regular_unit():
    units = [Unit(html="<p>Hello</p>")]
    result = _emit_units(units)
    assert result == '<div class="unit"><p>Hello</p></div>'


def test_emit_units_keep_together():
    units = [Unit(html="<p>x</p>", keep_together=True)]
    assert 'class="unit keep"' in _emit_units(units)


def test_emit_units_break_before():
    units = [Unit(html="<p>x</p>", break_before=True)]
    assert 'class="unit break-before"' in _emit_units(units)


def test_emit_units_is_break():
    units = [Unit(is_break=True)]
    assert _emit_units(units) == '<div class="pagebreak"></div>'


def test_emit_units_full_page():
    """full_page units render as .unit.break-before.full-page — no fixed geometry."""
    units = [Unit(html="<div>Cover</div>", full_page=True, master="cover")]
    result = _emit_units(units)
    assert 'class="unit break-before full-page"' in result
    assert "<div>Cover</div>" in result
    assert "width:" not in result
    assert "height:" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_html.py -k "toc or emit_units" -v
```

Expected: `ImportError: cannot import name '_build_toc'`

- [ ] **Step 3: Add `_build_toc` and `_emit_units` to `scriptorium/html.py`**

Add after the CSS constants (before `_emit_ebook_css`):

```python
# ── TOC and unit emission ──────────────────────────────────────────────────

def _build_toc(units: list[Unit]) -> list[dict]:
    """Scan unit stream for h1/h2 headings and return sidebar TOC entries."""
    return [
        {"id": u.heading_id, "level": u.heading_level, "text": u.heading}
        for u in units
        if u.heading_id and u.heading_level in (1, 2)
        and "unlisted" not in u.heading_classes
    ]


def _emit_units(units: list[Unit]) -> str:
    """Render unit stream to HTML div string (analogous to galley.emit())."""
    parts: list[str] = []
    for u in units:
        if u.is_break:
            parts.append('<div class="pagebreak"></div>')
            continue
        if u.full_page:
            parts.append(f'<div class="unit break-before full-page">{u.html}</div>')
            continue
        cls = ["unit"]
        if u.break_before:
            cls.append("break-before")
        if u.keep_together:
            cls.append("keep")
        parts.append(f'<div class="{" ".join(cls)}">{u.html}</div>')
    return "".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_html.py -v
```

Expected: all tests PASS (Tasks 1 + 2 combined)

- [ ] **Step 5: Commit**

```bash
git add scriptorium/html.py tests/test_html.py
git commit -m "feat(html): add _build_toc and _emit_units"
```

---

## Task 3: HTML Shell + JS (`EbookOptions`, `emit_ebook`)

**Files:**
- Modify: `scriptorium/html.py` — add `_READER_JS`, `EbookOptions`, `emit_ebook`
- Modify: `tests/test_html.py` — add tests

**Interfaces:**
- Consumes: `_emit_ebook_css`, `_build_toc`, `_emit_units` (all from Tasks 1–2)
- Produces: `EbookOptions` dataclass; `emit_ebook(units, theme, meta, options) -> str` — complete self-contained HTML string (before asset embedding)

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_html.py

from scriptorium.html import EbookOptions, emit_ebook


def _make_ebook(units=None, title="Test Book"):
    theme = load_theme("report")
    units = units or [Unit(html="<p>Hello world</p>")]
    options = EbookOptions(embed=False, book_id="test-book")
    return emit_ebook(units, theme, {"title": title}, options)


def test_emit_ebook_is_valid_html():
    html = _make_ebook()
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html


def test_emit_ebook_contains_title():
    html = _make_ebook(title="My Book")
    assert "<title>My Book</title>" in html
    assert "My Book" in html  # also in toolbar


def test_emit_ebook_contains_reader_chrome():
    html = _make_ebook()
    assert 'class="reader-toolbar"' in html
    assert 'class="reader-toc' in html
    assert 'id="reader-viewport"' in html
    assert 'id="ebook-content"' in html


def test_emit_ebook_contains_unit_content():
    html = _make_ebook([Unit(html="<p>The content</p>")])
    assert "<p>The content</p>" in html


def test_emit_ebook_contains_js():
    html = _make_ebook()
    assert "calcPages" in html
    assert "goToPage" in html
    assert "localStorage" in html


def test_emit_ebook_toc_built_from_headings():
    units = [
        Unit(html='<h1 id="ch1">Chapter 1</h1>',
             heading="Chapter 1", heading_level=1, heading_id="ch1"),
        Unit(html="<p>body</p>"),
    ]
    html = _make_ebook(units)
    assert 'href="#ch1"' in html
    assert "Chapter 1" in html


def test_emit_ebook_escapes_title():
    html = _make_ebook(title='<script>alert(1)</script>')
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_emit_ebook_book_id_in_html():
    html = _make_ebook()
    assert 'data-book-id="test-book"' in html
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_html.py -k "emit_ebook or EbookOptions" -v
```

Expected: `ImportError: cannot import name 'EbookOptions'`

- [ ] **Step 3: Add `_READER_JS`, `EbookOptions`, and `emit_ebook` to `scriptorium/html.py`**

Add `_READER_JS` constant after `_BODY_SIZE`:

```python
_READER_JS = """\
(function(){'use strict';
var vp=document.getElementById('reader-viewport');
var ct=document.getElementById('ebook-content');
var pg=document.querySelector('.reader-page');
var NS='ebook:'+(document.documentElement.dataset.bookId||'book')+':';
var cur=0,tot=1;
function calcPages(){tot=Math.max(1,Math.round(ct.scrollWidth/vp.clientWidth));}
function goToPage(n){
  n=Math.max(0,Math.min(n,tot-1));cur=n;
  ct.style.transform='translateX('+(-n*vp.clientWidth)+'px)';
  pg.textContent=(n+1)+' / '+tot;
  try{localStorage.setItem(NS+'page',n);}catch(_){}
}
function init(){
  calcPages();
  var s=0;try{s=parseInt(localStorage.getItem(NS+'page')||'0',10)||0;}catch(_){}
  goToPage(s);
}
document.addEventListener('keydown',function(e){
  var fwd=e.key==='ArrowRight'||e.key===' '||e.key==='PageDown';
  var back=e.key==='ArrowLeft'||e.key==='PageUp';
  if(fwd||back){e.preventDefault();goToPage(cur+(fwd?1:-1));}
});
vp.addEventListener('click',function(e){
  var x=e.clientX/vp.clientWidth;
  if(x<0.3)goToPage(cur-1);else if(x>0.7)goToPage(cur+1);
});
var tx=0;
vp.addEventListener('touchstart',function(e){tx=e.touches[0].clientX;},{passive:true});
vp.addEventListener('touchend',function(e){
  var dx=tx-e.changedTouches[0].clientX;
  if(Math.abs(dx)>40)goToPage(cur+(dx>0?1:-1));
});
window.addEventListener('resize',function(){calcPages();goToPage(Math.min(cur,tot-1));});
var tocEl=document.querySelector('.reader-toc');
document.querySelector('.btn-toc').addEventListener('click',function(){
  tocEl.classList.toggle('open');
});
tocEl.querySelectorAll('a[href^="#"]').forEach(function(a){
  a.addEventListener('click',function(e){
    e.preventDefault();
    var el=document.getElementById(a.getAttribute('href').slice(1));
    if(el)goToPage(Math.floor(el.offsetLeft/vp.clientWidth));
    tocEl.classList.remove('open');
  });
});
var THEMES=['auto','light','dark'];var ti=0;
try{ti=Math.max(0,THEMES.indexOf(localStorage.getItem(NS+'theme')));}catch(_){}
function applyTheme(){
  var t=THEMES[ti];
  document.documentElement.dataset.theme=t==='auto'?'':t;
  try{localStorage.setItem(NS+'theme',t);}catch(_){}
}
applyTheme();
document.querySelector('.btn-theme').addEventListener('click',function(){
  ti=(ti+1)%THEMES.length;applyTheme();
});
var SIZES=[14,16,18,20,22];var fi=2;
try{var sv=parseInt(localStorage.getItem(NS+'fontSize'),10);
  if(sv>=0&&sv<SIZES.length)fi=sv;}catch(_){}
function applySize(){
  document.documentElement.style.setProperty('--body-size',SIZES[fi]+'px');
  try{localStorage.setItem(NS+'fontSize',fi);}catch(_){}
  requestAnimationFrame(function(){calcPages();goToPage(cur);});
}
applySize();
document.querySelector('.btn-fontdown').addEventListener('click',function(){
  if(fi>0){fi--;applySize();}
});
document.querySelector('.btn-fontup').addEventListener('click',function(){
  if(fi<SIZES.length-1){fi++;applySize();}
});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
else init();
}());"""
```

Add `EbookOptions` dataclass and `emit_ebook` function after `_emit_units`:

```python
@dataclass
class EbookOptions:
    embed: bool = True
    book_id: str = "book"


def emit_ebook(units: list[Unit], theme: Theme, meta: dict,
               options: EbookOptions) -> str:
    """Render unit stream as a self-contained HTML ebook reader string."""
    css = _emit_ebook_css(theme, meta)
    toc = _build_toc(units)
    units_html = _emit_units(units)
    title = _html.escape(str(meta.get("title", "")))
    lang = _html.escape(str(meta.get("lang", "en")))
    book_id = _html.escape(options.book_id)

    toc_items = "".join(
        f'<li class="toc-l{e["level"]}">'
        f'<a href="#{_html.escape(e["id"])}">{_html.escape(e["text"])}</a></li>'
        for e in toc
    )

    return (
        f'<!DOCTYPE html>\n'
        f'<html lang="{lang}" data-theme="auto" data-book-id="{book_id}">\n'
        f'<head>\n'
        f'<meta charset="utf-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{title}</title>\n'
        f'<style>{css}</style>\n'
        f'</head>\n'
        f'<body>\n'
        f'<nav class="reader-toolbar">\n'
        f'  <button class="btn-toc" aria-label="Table of contents">&#9776;</button>\n'
        f'  <span class="reader-title">{title}</span>\n'
        f'  <span class="reader-spacer"></span>\n'
        f'  <button class="btn-fontdown" aria-label="Decrease font">A&#8722;</button>\n'
        f'  <button class="btn-fontup" aria-label="Increase font">A+</button>\n'
        f'  <button class="btn-theme" aria-label="Toggle theme">&#9685;</button>\n'
        f'  <span class="reader-page">1 / 1</span>\n'
        f'</nav>\n'
        f'<aside class="reader-toc"><ul>{toc_items}</ul></aside>\n'
        f'<div class="reader-viewport" id="reader-viewport">\n'
        f'  <div class="ebook-content" id="ebook-content">{units_html}</div>\n'
        f'</div>\n'
        f'<script>{_READER_JS}</script>\n'
        f'</body>\n'
        f'</html>'
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_html.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add scriptorium/html.py tests/test_html.py
git commit -m "feat(html): add EbookOptions and emit_ebook with inline JS reader"
```

---

## Task 4: Asset Inliner (`embed_assets`)

**Files:**
- Modify: `scriptorium/html.py` — add `_read_asset`, `embed_assets`
- Modify: `tests/test_html.py` — add tests

**Interfaces:**
- Consumes: nothing from previous tasks (standalone utility)
- Produces: `embed_assets(html: str, base_path: str) -> str` — replaces local `<img src>` and `url()` in `<style>` blocks with data URIs

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_html.py

from scriptorium.html import embed_assets


def test_embed_assets_embeds_local_img(tmp_path):
    # minimal valid PNG (1×1 pixel)
    png = bytes([
        0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a,  # PNG signature
        0,0,0,0x0d,0x49,0x48,0x44,0x52,            # IHDR chunk
        0,0,0,1,0,0,0,1,8,2,0,0,0,0x90,0x77,0x53,0xde,
        0,0,0,0x0c,0x49,0x44,0x41,0x54,            # IDAT chunk
        0x08,0xd7,0x63,0xf8,0xcf,0xc0,0,0,0,2,0,1,0xe2,0x21,
        0xbc,0x33,0,0,0,0,0x49,0x45,0x4e,0x44,0xae,0x42,0x60,0x82  # IEND
    ])
    img_path = tmp_path / "photo.png"
    img_path.write_bytes(png)

    html = '<img src="photo.png" alt="x">'
    result = embed_assets(html, str(tmp_path))
    assert 'src="data:image/png;base64,' in result
    assert "photo.png" not in result


def test_embed_assets_skips_http_urls():
    html = '<img src="https://example.com/img.png">'
    assert embed_assets(html, "/tmp") == html


def test_embed_assets_skips_data_urls():
    html = '<img src="data:image/png;base64,abc">'
    assert embed_assets(html, "/tmp") == html


def test_embed_assets_skips_missing_file():
    html = '<img src="missing.png">'
    assert embed_assets(html, "/tmp") == html


def test_embed_assets_embeds_url_in_style(tmp_path):
    woff = tmp_path / "font.woff2"
    woff.write_bytes(b"\x00" * 32)
    html = "<style>@font-face{src:url('font.woff2')}</style>"
    result = embed_assets(html, str(tmp_path))
    assert "data:font/woff2;base64," in result
    assert "font.woff2" not in result


def test_embed_assets_skips_absolute_url_in_style():
    html = "<style>@font-face{src:url('file:///usr/share/fonts/x.ttf')}</style>"
    assert embed_assets(html, "/tmp") == html


def test_embed_assets_warns_large_file(tmp_path, capsys):
    big = tmp_path / "big.png"
    big.write_bytes(b"\x00" * (6 * 1024 * 1024))  # 6 MB
    html = f'<img src="big.png">'
    result = embed_assets(html, str(tmp_path))
    assert result == html  # not embedded
    captured = capsys.readouterr()
    assert "big.png" in captured.err
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_html.py -k "embed_assets" -v
```

Expected: `ImportError: cannot import name 'embed_assets'`

- [ ] **Step 3: Add `_read_asset` and `embed_assets` to `scriptorium/html.py`**

Add before `emit_ebook`:

```python
# ── Asset embedding ────────────────────────────────────────────────────────

_IMG_SRC = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]+)(")')
_URL_REF = re.compile(r"url\(\s*(['\"]?)([^)'\"]+)\1\s*\)")
_STYLE_BLOCK = re.compile(r'(<style>)(.*?)(</style>)', re.S)
_LARGE_BYTES = 5 * 1024 * 1024


def _read_asset(path: Path) -> tuple[str, str] | None:
    """Return (mime, base64data) for a local asset, or None if missing/too large."""
    if not path.exists():
        return None
    size = path.stat().st_size
    if size > _LARGE_BYTES:
        print(
            f"warning: {path.name} ({size // 1024 // 1024} MB) exceeds 5 MB limit "
            f"— left as relative path",
            file=sys.stderr,
        )
        return None
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode()
    return mime, data


def embed_assets(html: str, base_path: str) -> str:
    """Inline local <img src> and url() references as data URIs."""
    base = Path(base_path)

    def sub_img(m: re.Match) -> str:
        src = m.group(2)
        if src.startswith(("http:", "https:", "data:", "//", "file:")):
            return m.group(0)
        r = _read_asset(base / src)
        return f'{m.group(1)}data:{r[0]};base64,{r[1]}{m.group(3)}' if r else m.group(0)

    def sub_url(m: re.Match) -> str:
        url = m.group(2).strip()
        if url.startswith(("http:", "https:", "data:", "file:", "/")):
            return m.group(0)
        r = _read_asset(base / url)
        if not r:
            return m.group(0)
        q = m.group(1)
        return f"url({q}data:{r[0]};base64,{r[1]}{q})"

    def sub_style(m: re.Match) -> str:
        return m.group(1) + _URL_REF.sub(sub_url, m.group(2)) + m.group(3)

    html = _IMG_SRC.sub(sub_img, html)
    html = _STYLE_BLOCK.sub(sub_style, html)
    return html
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_html.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add scriptorium/html.py tests/test_html.py
git commit -m "feat(html): add embed_assets — data URI inlining for single-file output"
```

---

## Task 5: Entry Point (`render_html`)

**Files:**
- Modify: `scriptorium/html.py` — add `render_html`
- Modify: `tests/test_html.py` — add integration test

**Interfaces:**
- Consumes: all previous functions from html.py; preprocessors from footnotes/citations/glossary; `parse`, `frontmatter` from parse; `ExecEnv` from execute; `Freeze` from freeze; `mathrender`; `tangle_write` from tangle
- Produces: `render_html(src, out_path, ...)` — writes HTML file to disk (returns None)

Note: `render_html` deliberately duplicates the setup code from `galley.render_pdf`
(theme loading, var merging, CSS var overrides, preprocessors, parse). `galley.py`
is untouched per spec §10. The duplication is intentional for V1.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_html.py

from scriptorium.html import render_html


def test_render_html_writes_file(tmp_path):
    src = "---\ntitle: Integration Test\n---\n# Chapter 1\n\nHello world.\n"
    out = tmp_path / "out.html"
    render_html(src, str(out), cwd=str(tmp_path), execute=False)

    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in text
    assert "Integration Test" in text
    assert "Hello world." in text
    assert "calcPages" in text


def test_render_html_skips_fill_toc(tmp_path):
    """The inline TOC block (from fill_toc) must not appear — only the sidebar TOC."""
    src = "---\ntitle: TOC Test\ntoc_depth: 2\n---\n# Chapter 1\n\n::: toc\n:::\n\nText.\n"
    out = tmp_path / "out.html"
    render_html(src, str(out), cwd=str(tmp_path), execute=False)
    text = out.read_text()
    # sidebar TOC link exists
    assert 'href="#' in text
    # but there should be no duplicate chapter entry outside the sidebar
    assert text.count("Chapter 1") <= 2  # title + sidebar entry; not an inline TOC block too


def test_render_html_forces_endnote_mode(tmp_path):
    """Footnotes must render as endnotes, not per-page floats."""
    src = (
        "---\ntitle: Footnote Test\nfootnotes: page\n---\n"
        "Text.[^a]\n\n[^a]: My note.\n"
    )
    out = tmp_path / "out.html"
    render_html(src, str(out), cwd=str(tmp_path), execute=False)
    text = out.read_text()
    assert "My note." in text
    # float: footnote is WeasyPrint-specific CSS — must not appear in HTML output
    assert "float:footnote" not in text
    assert "float: footnote" not in text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_html.py -k "render_html" -v
```

Expected: `ImportError: cannot import name 'render_html'`

- [ ] **Step 3: Add `render_html` to `scriptorium/html.py`**

Add at the bottom of the file:

```python
# ── Top-level entry point ──────────────────────────────────────────────────

def render_html(
    src: str,
    out_path: str,
    base_url: str | None = None,
    theme_name: str | None = None,
    cwd: str | None = None,
    execute: bool = True,
    vars: dict | None = None,
    code_root: str | None = None,
    project_meta: dict | None = None,
    embed: bool = True,
) -> None:
    """Render Markdown source to a self-contained HTML ebook file."""
    from .parse import frontmatter, parse
    from .footnotes import process_footnotes
    from .citations import process_citations
    from .glossary import process_glossary
    from .execute import ExecEnv
    from .freeze import Freeze
    from .tangle import write as tangle_write
    from . import mathrender

    theme = load_theme(resolve_theme_name(src, theme_name))

    merged = {**theme.vars, **(vars or {})}
    meta = {**merged, **(project_meta or {}), **frontmatter(src)}
    merged = {**merged, **(meta.get("vars") or {})}

    def _css_val(k: str, v) -> str:
        v = str(v)
        if k.endswith("-font") and " " in v and v[0] not in "'\"":
            v = f"'{v}'"
        return f"--{k}:{v};"

    overrides = "".join(_css_val(k, merged[k]) for k in _APPEARANCE if k in merged)
    if overrides:
        theme.css += f":root{{{overrides}}}"

    css_spec = meta.get("css")
    for rel in ([css_spec] if isinstance(css_spec, str) else list(css_spec or [])):
        path = Path(rel)
        if cwd and not path.is_absolute():
            path = Path(cwd) / path
        try:
            theme.css += "\n" + path.read_text(encoding="utf-8")
        except OSError:
            pass

    freeze = Freeze(Path(cwd) / ".scriptorium" / "freeze.json") if cwd else None
    mathrender.set_freeze(freeze)

    env = None
    if execute:
        stem = str(meta.get("stem", "doc"))
        if cwd:
            tangle_write(src, cwd, doc_stem=stem)
        pythonpath: list[str] = []
        if cwd and code_root:
            pythonpath = [str((Path(cwd) / code_root).resolve())]
        env = ExecEnv(cwd=cwd, freeze=freeze, pythonpath=pythonpath)
        if isinstance(meta.get("execute"), dict) and meta["execute"].get("interpreters"):
            env.interpreters.update(meta["execute"]["interpreters"])

    # HTML path: always endnote mode regardless of frontmatter
    src, _ = process_footnotes(src, "document")
    src, _ = process_citations(src, meta)
    src, _ = process_glossary(src, meta, Path(cwd) if cwd else None)

    units = parse(src, theme, env, meta=meta)
    # NOTE: fill_toc() is intentionally NOT called — emit_ebook() builds the
    # sidebar TOC directly from the unit stream.

    title_slug = re.sub(r"[^a-z0-9]+", "-",
                        str(meta.get("title", "book")).lower()).strip("-") or "book"
    options = EbookOptions(embed=embed, book_id=title_slug)
    html_out = emit_ebook(units, theme, meta, options)

    if embed:
        asset_base = (
            base_url.removeprefix("file://").rstrip("/")
            if base_url and base_url.startswith("file://")
            else (cwd or ".")
        )
        html_out = embed_assets(html_out, asset_base)

    Path(out_path).write_text(html_out, encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_html.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Run the full suite to confirm nothing regressed**

```bash
uv run pytest -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add scriptorium/html.py tests/test_html.py
git commit -m "feat(html): add render_html entry point"
```

---

## Task 6: CLI Wiring

**Files:**
- Modify: `scriptorium/cli.py:17-57` — add `--format`, `--no-embed` flags and HTML dispatch branch
- Modify: `tests/test_html.py` — add CLI integration tests

**Interfaces:**
- Consumes: `render_html` from `scriptorium.html`; `render_pdf` from `scriptorium.galley` (existing)
- Produces: `scriptorium render input.md --format html` works end-to-end

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_html.py

import subprocess, sys


def test_cli_render_html(tmp_path):
    src = tmp_path / "doc.md"
    src.write_text("---\ntitle: CLI Test\n---\n# Hello\n\nWorld.\n", encoding="utf-8")
    out = tmp_path / "doc.html"
    result = subprocess.run(
        [sys.executable, "-m", "scriptorium", "render", str(src),
         "--format", "html", "-o", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert out.exists()
    text = out.read_text()
    assert "CLI Test" in text
    assert "<!DOCTYPE html>" in text


def test_cli_render_html_no_embed(tmp_path):
    src = tmp_path / "doc.md"
    src.write_text("---\ntitle: NoEmbed\n---\n# Ch\n\nBody.\n", encoding="utf-8")
    out = tmp_path / "doc.html"
    result = subprocess.run(
        [sys.executable, "-m", "scriptorium", "render", str(src),
         "--format", "html", "--no-embed", "-o", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert out.exists()


def test_cli_render_pdf_unchanged(tmp_path):
    """Existing PDF path must be unaffected."""
    src = tmp_path / "doc.md"
    src.write_text("---\ntitle: PDF Test\n---\n# Hello\n\nWorld.\n", encoding="utf-8")
    out = tmp_path / "doc.pdf"
    result = subprocess.run(
        [sys.executable, "-m", "scriptorium", "render", str(src), "-o", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_html.py -k "cli" -v
```

Expected: `cli_render_html` fails with non-zero returncode (unrecognized argument `--format`)

- [ ] **Step 3: Modify `scriptorium/cli.py`**

In the `render` subparser block, add the two new arguments after the existing ones:

```python
# After:  r.add_argument("--theme", ...)
r.add_argument(
    "--format", choices=["pdf", "html"], default="pdf",
    help="output format (default: pdf)",
)
r.add_argument(
    "--no-embed", action="store_true",
    help="with --format html: skip asset embedding (assets stay as relative paths)",
)
```

Replace the render handler block (currently starting at `if args.cmd == "render":`) with:

```python
    if args.cmd == "render":
        if args.format == "html":
            from .html import render_html
            if args.input.suffix in (".yaml", ".yml"):
                from .project import load as load_project
                proj = load_project(args.input)
                out = args.output or (args.input.parent / "book.html")
                cwd = str(args.input.resolve().parent)
                render_html(
                    proj.src, str(out),
                    base_url="file://" + cwd + "/",
                    theme_name=proj.theme, cwd=cwd,
                    execute=not args.no_execute, vars=proj.vars,
                    code_root=proj.code_root, project_meta=proj.meta,
                    embed=not args.no_embed,
                )
            else:
                out = args.output or args.input.with_suffix(".html")
                cwd = str(args.input.resolve().parent)
                render_html(
                    src, str(out),
                    base_url="file://" + cwd + "/",
                    theme_name=args.theme, cwd=cwd,
                    execute=not args.no_execute,
                    embed=not args.no_embed,
                )
            print(f"rendered {out}")
            return 0

        # existing PDF path below — unchanged
        if args.input.suffix in (".yaml", ".yml"):
            ...
```

The rest of the PDF render block stays exactly as it is.

- [ ] **Step 4: Run CLI tests to verify they pass**

```bash
uv run pytest tests/test_html.py -k "cli" -v
```

Expected: all 3 CLI tests PASS

- [ ] **Step 5: Run the full suite**

```bash
uv run pytest -v
```

Expected: all tests PASS, including the full pre-existing suite

- [ ] **Step 6: Commit**

```bash
git add scriptorium/cli.py tests/test_html.py
git commit -m "feat(html): wire --format html and --no-embed into CLI"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Implemented in |
|---|---|
| §3.1 — footnote forced to endnote, no fill_toc | Task 5 (`render_html`) |
| §3.2 — `render_html`, `emit_ebook`, `embed_assets` signatures | Tasks 3–5 |
| §3.3 — CSS post-processing (strip @page, .page, .slide, string-set; translate break-before) | Task 1 |
| §3.3 — dark mode CSS fallback + theme dark.css override | Task 1 |
| §3.3 — `--body-size` injection | Task 1 |
| §4 — layout CSS constants | Task 3 (`_LAYOUT_CSS`) |
| §5 — HTML shell structure | Task 3 (`emit_ebook`) |
| §6 — JS: navigation (keyboard, click, swipe), TOC, theme, font, resize, localStorage | Task 3 (`_READER_JS`) |
| §7 — TOC from `heading_id`/`heading`/`heading_classes` | Task 2 (`_build_toc`) |
| §8 — `<img>` and `url()` embedding, 5 MB warning | Task 4 (`embed_assets`) |
| §9 — CLI `--format pdf\|html`, `--no-embed` | Task 6 |
| §12 — masters as `.unit.break-before.full-page` | Task 2 (`_emit_units`) |
| §12 — math SVGs already inline (no special case) | Task 4 (confirmed in test for embed_assets: `<img src="data:...">` is skipped by the data: guard) |

No gaps found.

**Placeholder scan:** No TBDs, no "implement later", all code blocks show actual implementation.

**Type consistency:**
- `_build_toc` returns `list[dict]` with keys `id`, `level`, `text` — used correctly in `emit_ebook`
- `_emit_units` takes `list[Unit]`, returns `str` — correct in `emit_ebook`
- `EbookOptions` fields `embed: bool`, `book_id: str` — used correctly in `render_html` and `emit_ebook`
- `embed_assets(html: str, base_path: str) -> str` — called correctly in `render_html`
- All Unit fields used (`heading`, `heading_id`, `heading_level`, `heading_classes`, `is_break`, `full_page`, `break_before`, `keep_together`, `html`) — all confirmed present in `model.py`
