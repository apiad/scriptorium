"""galley — the pagination engine: measure -> pack -> emit.

Measure renders the content stream once at the true body width and reads each
unit's border-box height from WeasyPrint's box tree; pack greedily assigns units
to fixed-height pages honoring keep-together, hard breaks, and full-page masters;
emit generates `.page` boxes (applying the theme's page masters and stamp
furniture) and the final PDF. Measure and emit share the theme CSS.
"""

import re
from dataclasses import dataclass

from weasyprint import HTML

from .model import Unit
from .theme import Theme, load_theme

PX_PER_MM = 96 / 25.4
PAGE_W, PAGE_H = 210.0, 297.0
FOOTER_RESERVE = 8.0  # mm kept clear for the stamp on body pages
EPS = 0.5


def _mm(v, default=14.0) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r"([\d.]+)", str(v or ""))
    return float(m.group(1)) if m else default


@dataclass
class Report:
    n_pages: int
    oversized: list[str]
    page_of: list[int]


def _geom(theme: Theme):
    margin = _mm(theme.meta.get("page", {}).get("margin", "14mm"))
    return margin, PAGE_W - 2 * margin, PAGE_H - 2 * margin - FOOTER_RESERVE


# module defaults (default theme) so callers/tests can import CONTENT_H
_MARGIN, CONTENT_W, CONTENT_H = _geom(load_theme())


def measure(units: list[Unit], theme: Theme, base_url: str | None = None) -> None:
    margin, content_w, _ = _geom(theme)
    css = (
        theme.css
        + f"@page{{size:{content_w}mm 4000mm;margin:0}}"
        + "html,body,main{margin:0;padding:0;}"
    )
    parts = ["<style>", css, "</style><main>"]
    for i, u in enumerate(units):
        if u.is_break or u.full_page or not u.html.strip():
            continue
        parts.append(f'<div class="unit" data-i="{i}">{u.html}</div>')
    parts.append("</main>")
    doc = HTML(string="".join(parts), base_url=base_url).render()

    heights: dict[int, float] = {}
    stack = [doc.pages[0]._page_box]
    while stack:
        box = stack.pop()
        el = getattr(box, "element", None)
        if el is not None:
            di = el.get("data-i")
            if di is not None and int(di) not in heights:
                heights[int(di)] = box.margin_height() / PX_PER_MM
        stack.extend(reversed(getattr(box, "children", []) or []))

    for i, u in enumerate(units):
        if not u.full_page:
            u.height_mm = heights.get(i, 0.0)


def pack(units: list[Unit], content_h: float = CONTENT_H) -> tuple[list[list[Unit]], Report]:
    pages: list[list[Unit]] = [[]]
    oversized: list[str] = []
    page_of: list[int] = []
    y = 0.0

    def new_page():
        nonlocal y
        if pages[-1]:
            pages.append([])
            y = 0.0

    for u in units:
        if u.is_break:
            new_page()
            continue
        if u.full_page:  # cover / section opener: its own page via a master
            new_page()
            pages[-1].append(u)
            page_of.append(len(pages) - 1)
            pages.append([])
            y = 0.0
            continue
        h = u.height_mm
        if u.break_before:
            new_page()
        if h > content_h + EPS:  # oversized: warn + overflow (never silent-scale)
            new_page()
            label = u.name if u.name != "prose" else re.sub(r"<[^>]+>", "", u.html)[:40] + "…"
            oversized.append(f"{label} ({h:.0f}mm > {content_h:.0f}mm)")
            pages[-1].append(u)
            page_of.append(len(pages) - 1)
            pages.append([])
            y = 0.0
            continue
        if y + h > content_h + EPS:
            new_page()
        pages[-1].append(u)
        page_of.append(len(pages) - 1)
        y += h

    if not pages[-1]:
        pages.pop()
    return pages, Report(n_pages=len(pages), oversized=oversized, page_of=page_of)


def _emit_css(theme: Theme) -> str:
    return (
        theme.css
        + "@page{size:A4;margin:0}"
        + f".page{{width:{PAGE_W}mm;height:{PAGE_H}mm;box-sizing:border-box;"
        "overflow:hidden;page-break-after:always}"
        ".page:last-child{page-break-after:auto}"
    )


def emit(pages: list[list[Unit]], theme: Theme, meta: dict | None = None) -> str:
    meta = meta or {}
    title = str(meta.get("title", ""))
    total = len(pages)
    section = title
    out = ["<!DOCTYPE html><html><head><meta charset='utf-8'><style>",
           _emit_css(theme), "</style></head><body>"]

    for n, page in enumerate(pages, 1):
        if len(page) == 1 and page[0].full_page:
            master = page[0].master
            classes = theme.master_classes(master)
            out.append(f'<div class="page {classes}">{page[0].html}</div>')
            continue
        # body page: update running section, wrap units, add stamp
        for u in page:
            if u.heading:
                section = u.heading
        classes = theme.master_classes("body")
        out.append(f'<div class="page {classes}">')
        for u in page:
            out.append(f'<div class="unit">{u.html}</div>')
        if theme.master_furniture("body") == "stamp":
            out.append(
                f'<div class="stamp"><span>{title}</span>'
                f'<span>{section}</span><span>{n} / {total}</span></div>'
            )
        out.append("</div>")

    out.append("</body></html>")
    return "".join(out)


def render_pdf(src: str, out_path: str, base_url: str | None = None,
               theme_name: str = "marketing") -> Report:
    from .parse import frontmatter, parse

    theme = load_theme(theme_name)
    _, _, content_h = _geom(theme)
    units = parse(src, theme)
    measure(units, theme, base_url=base_url)
    pages, report = pack(units, content_h=content_h)
    doc = HTML(string=emit(pages, theme, frontmatter(src)), base_url=base_url).render()
    actual = len(doc.pages)
    if actual != report.n_pages:  # geometry drift: a page overflowed its box
        report.oversized.append(
            f"page-count drift: planned {report.n_pages}, rendered {actual} "
            "(a page overflowed — check a full-page master or an undersized measure)"
        )
    doc.write_pdf(out_path)
    return report
