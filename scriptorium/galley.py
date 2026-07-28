"""galley — the pagination engine: measure -> pack -> emit.

A4 with 14mm margins by default. Measure renders the content stream once at the
true body width and reads each unit's border-box height from WeasyPrint's box
tree; pack greedily assigns units to fixed-height pages honoring keep-together
and hard breaks; emit generates `.page` boxes and the final PDF, so measurement
and output share one rendering path.
"""

from dataclasses import dataclass

from weasyprint import HTML

from .model import Unit
from .theme import BASE_CSS

PX_PER_MM = 96 / 25.4
PAGE_W, PAGE_H = 210.0, 297.0
MARGIN = 14.0
CONTENT_W = PAGE_W - 2 * MARGIN  # 182mm
CONTENT_H = PAGE_H - 2 * MARGIN  # 269mm
EPS = 0.5  # mm slack for sub-pixel rounding


@dataclass
class Report:
    n_pages: int
    oversized: list[str]
    page_of: list[int]  # page index per non-break unit (in unit order)


def _measure_css() -> str:
    return (
        BASE_CSS
        + f"@page {{ size:{CONTENT_W}mm 4000mm; margin:0; }}"
        + "html,body,main{margin:0;padding:0;}"
    )


def measure(units: list[Unit], base_url: str | None = None) -> None:
    """Fill each non-break unit's height_mm from a single tall render."""
    parts = ['<style>', _measure_css(), "</style><main>"]
    for i, u in enumerate(units):
        if u.is_break or not u.html.strip():
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
        h = u.height_mm
        if u.break_before:
            new_page()
        if h > content_h + EPS:  # oversized: warn + overflow (never silent-scale)
            new_page()
            label = u.name if u.name != "prose" else (u.html[:40] + "…")
            oversized.append(f"{label} ({h:.0f}mm > {content_h:.0f}mm)")
            pages[-1].append(u)
            page_of.append(len(pages) - 1)
            pages.append([])
            y = 0.0
            continue
        if y + h > content_h + EPS:  # doesn't fit here -> next page
            new_page()
        pages[-1].append(u)
        page_of.append(len(pages) - 1)
        y += h

    return pages, Report(n_pages=len(pages), oversized=oversized, page_of=page_of)


def _emit_css() -> str:
    return (
        BASE_CSS
        + "@page{size:A4;margin:0;}"
        + f".page{{width:{PAGE_W}mm;height:{PAGE_H}mm;padding:{MARGIN}mm;"
        "box-sizing:border-box;overflow:hidden;background:#fff;"
        "page-break-after:always;}"
        ".page:last-child{page-break-after:auto;}"
    )


def emit(pages: list[list[Unit]]) -> str:
    parts = ["<!DOCTYPE html><html><head><meta charset='utf-8'><style>", _emit_css(), "</style></head><body>"]
    for page in pages:
        parts.append('<div class="page">')
        for u in page:
            parts.append(f'<div class="unit">{u.html}</div>')
        parts.append("</div>")
    parts.append("</body></html>")
    return "".join(parts)


def render_pdf(src: str, out_path: str, base_url: str | None = None) -> Report:
    from .parse import parse

    units = parse(src)
    measure(units, base_url=base_url)
    pages, report = pack(units)
    HTML(string=emit(pages), base_url=base_url).write_pdf(out_path)
    return report
