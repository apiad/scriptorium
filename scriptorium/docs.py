"""The docs output: a static documentation site of scrolling pages.

The units split into pages as the HTML book splits them into chapters, one
page per `#` heading. Each page carries a top bar with search, a sidebar of
parts and chapters, an outline of its sections, and previous and next links.
The theme's CSS is adapted for the browser as the book does; the layout lives
in `themes/base/docs/`.
"""

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .book import (BookReport, _carry_counters, _chapters, _esc, _unit_html, browser_css,
                   collect_css_assets, collect_images, resolve_refs)
from .media import _pages, collect_media

DOCS_DIR = Path(__file__).resolve().parent.parent / "themes" / "base" / "docs"

_HREF = re.compile(r'href="#([^"]+)"')
_ID = re.compile(r'\bid="([^"]+)"')
_SUB_HEADING = re.compile(r'(<h([23])\b[^>]*\bid="([^"]+)"[^>]*>.*?)(</h\2>)', re.S)


@dataclass
class Page:
    slug: str
    title: str
    part: str | None
    units: list
    kind: str  # "index" | "part" | "chapter"


def _content(units) -> list:
    return [u for u in units if not u.is_break]


def pages(units) -> tuple[list[Page], list[dict]]:
    """The pages in reading order and the sidebar tree. Units before the first
    `#` heading go to the index page. A part heading with content under it
    gets a page; one with none is only a label in the sidebar."""
    slug_of = {id(u): page for u, page in _pages(units)}
    if not any(u.heading_level == 1 for u in units):
        return [Page("index", "", None, _content(units), "index")], []
    chunks, _ = _chapters(units)
    out = [Page("index", "", None, [], "index")]
    tree: list[dict] = []
    group = None
    for chunk in chunks:
        head = next((u for u in chunk if u.heading_level == 1), None)
        if head is None:  # the front, before the first chapter
            out[0].units = _content(chunk)
            continue
        slug, title = slug_of[id(head)], head.heading or ""
        if "part" in head.heading_classes:
            has_text = any(u is not head for u in _content(chunk))
            group = {"title": title, "slug": slug if has_text else None, "chapters": []}
            tree.append(group)
            if has_text:
                out.append(Page(slug, title, title, _content(chunk), "part"))
            else:  # kept for its id and the part counter, never written
                out.append(Page(slug, title, title, _content(chunk), "label"))
            continue
        part = group["title"] if group else None
        out.append(Page(slug, title, part, _content(chunk), "chapter"))
        if "unlisted" in head.heading_classes:
            continue
        if group is None:
            group = {"title": None, "slug": None, "chapters": []}
            tree.append(group)
        sections = [{"title": u.heading, "id": u.heading_id}
                    for u in chunk if u.heading_level == 2 and u.heading_id]
        group["chapters"].append({"title": title, "slug": slug, "sections": sections})
    return out, tree


def _link_pages(html: str, here: str, where: dict[str, str]) -> str:
    """Point each `#id` link whose target is on another page at that page."""
    def sub(m):
        page = where.get(m.group(1))
        return m.group(0) if page in (None, here) else f'href="{page}.html#{m.group(1)}"'
    return _HREF.sub(sub, html)


def _sidebar(tree: list[dict], current: str, outline: list) -> str:
    items = []
    for group in tree:
        chapters = []
        for ch in group["chapters"]:
            mine = ch["slug"] == current
            link = (f'<a href="{_esc(ch["slug"])}.html"'
                    + (' aria-current="page"' if mine else "") + f'>{_esc(ch["title"])}</a>')
            subs = ""
            if mine and outline:
                subs = '<ul class="sections">' + "".join(
                    f'<li><a href="#{_esc(i)}">{_esc(t)}</a></li>' for lvl, i, t in outline if lvl == 2) + "</ul>"
            chapters.append(f"<li>{link}{subs}</li>")
        if group["title"] is None:
            items.append("".join(chapters))
            continue
        if group["slug"]:
            label = (f'<a class="part" href="{_esc(group["slug"])}.html"'
                     + (' aria-current="page"' if group["slug"] == current else "")
                     + f'>{_esc(group["title"])}</a>')
        else:
            label = f'<span class="part">{_esc(group["title"])}</span>'
        items.append(f'<li class="part-group">{label}<ul>{"".join(chapters)}</ul></li>')
    return "<ul>" + "".join(items) + "</ul>"


def _contents(tree: list[dict]) -> str:
    """The index page's list of parts and chapters."""
    items = []
    for group in tree:
        chapters = "".join(f'<li><a href="{_esc(c["slug"])}.html">{_esc(c["title"])}</a></li>'
                           for c in group["chapters"])
        if group["title"] is None:
            items.append(chapters)
            continue
        label = (f'<a href="{_esc(group["slug"])}.html">{_esc(group["title"])}</a>' if group["slug"]
                 else _esc(group["title"]))
        items.append(f'<li class="part-group"><span class="part">{label}</span><ul>{chapters}</ul></li>')
    return f'<nav class="contents"><ul>{"".join(items)}</ul></nav>'


def _shell(page: Page, body: str, *, site_title: str, lang: str, tree: list[dict],
           outline: list, prev: Page | None, next: Page | None, output) -> str:
    title = page.title if page.kind != "index" else site_title
    head_title = _esc(title if title == site_title else f"{title} · {site_title}")
    source = (f'<a class="source" href="{_esc(output.repo_url)}">Source</a>'
              if output.repo_url else "")
    outline_html = ""
    if outline:
        outline_html = ('<aside class="outline"><p>On this page</p><ul>' + "".join(
            f'<li class="h{lvl}"><a href="#{_esc(i)}">{_esc(t)}</a></li>' for lvl, i, t in outline)
            + "</ul></aside>")
    pager = '<nav class="pager">'
    if prev:
        pager += f'<a rel="prev" href="{prev.slug}.html">← {_esc(prev.title or site_title)}</a>'
    if next:
        pager += f'<a rel="next" href="{next.slug}.html">{_esc(next.title or site_title)} →</a>'
    pager += "</nav>"
    scripts = "".join(f'\n<script src="{_esc(js)}" defer></script>' for js in output.js)
    return f"""<!doctype html>
<html lang="{_esc(lang)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{head_title}</title>
<link rel="stylesheet" href="docs.css">
<script src="docs.js" defer></script>{scripts}
</head>
<body class="docs">
<header class="topbar">
<button class="menu" type="button" aria-label="Menu" aria-expanded="false">☰</button>
<a class="site-title" href="index.html">{_esc(site_title)}</a>
<div class="search"><input type="search" placeholder="Search" aria-label="Search" autocomplete="off"><div class="search-results" hidden></div></div>
{source}
</header>
<div class="layout">
<nav class="sidebar" aria-label="Contents">{_sidebar(tree, page.slug, outline)}</nav>
<main>
{body}
{pager}
</main>
{outline_html}
</div>
</body>
</html>
"""


def render_docs(src: str, out_dir: Path, *, output, base_dir: Path, theme_name: str | None = None,
                vars: dict | None = None, project_meta: dict | None = None,
                execute: bool = True, code_root: str | None = None) -> BookReport:
    """Write the docs site for `src` into `out_dir`, replacing what was there."""
    from .emit import _emit_css
    from .render import prepare

    base_dir, out_dir = Path(base_dir), Path(out_dir)
    p = prepare(src, theme_name=theme_name, cwd=str(base_dir), execute=execute,
                vars={**(vars or {}), **output.vars}, code_root=code_root,
                project_meta=project_meta, for_screen=True)
    if str(p.theme.meta.get("mode", "")) == "deck":
        raise ValueError("deck themes have no docs form; render them to PDF")
    warnings = list(p.warnings) + resolve_refs(p.units, p.theme.meta.get("html-refs", {}), p.meta)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    all_pages, tree = pages(p.units)
    # a label part's id leads to the page after it
    where: dict[str, str] = {}
    pending: list[str] = []
    for page in all_pages:
        ids = [i for u in page.units for i in _ID.findall(u.html)]
        if page.kind == "label":
            pending += ids
            continue
        for ident in pending + ids:
            where.setdefault(ident, page.slug)
        pending = []

    first_h1 = next((u.heading for u in p.units if u.heading_level == 1), "")
    site_title = str(p.meta.get("title") or first_h1 or "Documentation")
    lang = str(p.meta.get("lang") or p.theme.meta.get("lang") or "en")

    sections = []
    for page in all_pages:
        html = "".join(_unit_html(u, p.theme) for u in page.units)
        html = _link_pages(html, page.slug, where)
        html = _SUB_HEADING.sub(lambda m: f'{m.group(1)}<a class="anchor" href="#{m.group(3)}">#</a>{m.group(4)}', html)
        sections.append(f'<section class="docs-page {page.kind}">{html}</section>')
    sections = _carry_counters(sections)

    written = [page for page in all_pages if page.kind != "label"]
    for page, section in zip(all_pages, sections):
        if page.kind == "label":
            continue
        n = written.index(page)
        outline = [(u.heading_level, u.heading_id, u.heading or "")
                   for u in page.units if u.heading_level in (2, 3) and u.heading_id]
        body = section
        if page.kind == "index":
            if not any(u.heading_level == 1 for u in page.units):
                body = f'<h1 class="unnumbered docs-title">{_esc(site_title)}</h1>' + body
            body += _contents(tree)
        body, img_warnings = collect_images(body, base_dir, out_dir, output.image_max_width,
                                            output.image_quality)
        warnings += img_warnings
        body = collect_media(body, base_dir, out_dir)
        html = _shell(page, body, site_title=site_title, lang=lang, tree=tree, outline=outline,
                      prev=written[n - 1] if n else None,
                      next=written[n + 1] if n + 1 < len(written) else None, output=output)
        (out_dir / f"{page.slug}.html").write_text(html, encoding="utf-8")

    css = [browser_css(collect_css_assets(_emit_css(p.theme, p.meta), out_dir)),
           (DOCS_DIR / "docs.css").read_text(encoding="utf-8")]
    for rel in output.css:
        try:
            css.append((base_dir / rel).read_text(encoding="utf-8"))
        except OSError as exc:
            warnings.append(f"css file {rel!r} could not be read: {exc}")
    (out_dir / "docs.css").write_text("\n".join(css), encoding="utf-8")
    shutil.copyfile(DOCS_DIR / "docs.js", out_dir / "docs.js")
    for rel in output.js:
        try:
            dst = out_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(base_dir / rel, dst)
        except OSError as exc:
            warnings.append(f"js file {rel!r} could not be copied: {exc}")
    (out_dir / "search.json").write_text("[]\n", encoding="utf-8")

    files = [f for f in out_dir.rglob("*") if f.is_file()]
    return BookReport(files=len(files), bytes=sum(f.stat().st_size for f in files),
                      version="", warnings=warnings)
