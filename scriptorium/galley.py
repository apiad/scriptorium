"""galley — the pagination engine: emit -> PDF.

For document themes (article, book, note, report, base) the engine emits a
single-flow HTML document; WeasyPrint's CSS Fragmentation Module handles page
breaks via break-after/inside/before rules — no Python-level bin-packing or
height measurement.

For deck themes the previous measure -> pack -> emit_deck pipeline is preserved
because slides use absolute-positioned fixed-size boxes.
"""

import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from weasyprint import HTML

from .execute import ExecEnv
from .freeze import Freeze
from .highlight import css as hl_css
from .highlight import highlight
from .model import Unit
from .tangle import write as tangle_write
from .theme import Theme, load_theme, render_template

PX_PER_MM = 96 / 25.4
PAGE_W, PAGE_H = 210.0, 297.0
FOOTER_RESERVE = 8.0  # mm kept clear for the stamp on body pages
EPS = 0.5

# named page sizes (mm) — landscape slides for decks
_SIZES = {
    "a4": (210.0, 297.0), "letter": (215.9, 279.4),
    "16:9": (254.0, 142.875), "4:3": (254.0, 190.5),
}


def _mm(v, default=14.0) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r"([\d.]+)", str(v or ""))
    return float(m.group(1)) if m else default


def _page_size(theme: Theme) -> tuple[float, float]:
    s = str(theme.meta.get("page", {}).get("size", "A4")).lower().strip()
    if s in _SIZES:
        return _SIZES[s]
    nums = re.findall(r"([\d.]+)mm", s)
    return (float(nums[0]), float(nums[1])) if len(nums) == 2 else _SIZES["a4"]


@dataclass
class Report:
    n_pages: int
    oversized: list[str]
    page_of: list[int]


def _geom(theme: Theme):
    w, h = _page_size(theme)
    margin = _mm(theme.meta.get("page", {}).get("margin", "14mm"))
    return margin, w - 2 * margin, h - 2 * margin - FOOTER_RESERVE


# module defaults (default theme) so callers/tests can import CONTENT_H
_MARGIN, CONTENT_W, CONTENT_H = _geom(load_theme())


MEASURE_CHUNK = 50  # units per measure render
MEASURE_PAGE_MM = 4000  # moderate measure page; a 50-unit chunk spans a few of
# these, well under WeasyPrint's silent per-render ceiling (~21 pages / ~84000mm)
# that would zero-out a chunk's tail. (An over-tall page is worse, not better.)


def measure(units: list[Unit], theme: Theme, base_url: str | None = None) -> None:
    _, content_w, _ = _geom(theme)
    css = (
        theme.css
        + hl_css()
        + f"@page{{size:{content_w}mm {MEASURE_PAGE_MM}mm;margin:0}}"
        + "html,body,main{margin:0;padding:0;}"
        # flow-root contains child margins so heights are additive and collapse-free
        # (must match emit exactly); break-inside keeps a unit off two measure pages.
        + ".unit{display:flow-root;break-inside:avoid;}"
    )
    idxs = [i for i, u in enumerate(units)
            if not (u.is_break or u.full_page or not u.html.strip())]
    heights: dict[int, float] = {}

    for start in range(0, len(idxs), MEASURE_CHUNK):
        batch = idxs[start : start + MEASURE_CHUNK]
        parts = ["<style>", css, "</style><main>"]
        for i in batch:
            parts.append(f'<div class="unit" data-i="{i}">{units[i].html}</div>')
        parts.append("</main>")
        doc = HTML(string="".join(parts), base_url=base_url).render()
        for page in doc.pages:  # a chunk may still span a few measure pages
            stack = [page._page_box]
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


MIN_CODE_LINES = 4  # widow/orphan minimum when splitting a listing
CODE_OVERHEAD = 11.0  # mm of box chrome (padding + label) per code fragment


def _split_code(u: Unit, avail: float) -> tuple[Unit, Unit]:
    """Split a code listing so the first fragment fills `avail`, rest continues."""
    lines = u.code_src.split("\n")
    n = len(lines)
    per = max((u.height_mm - CODE_OVERHEAD) / n, 0.1)  # per-line height, content only
    fit = int((avail - CODE_OVERHEAD) / per)
    fit = max(MIN_CODE_LINES, min(fit, n - MIN_CODE_LINES))
    a, b = "\n".join(lines[:fit]), "\n".join(lines[fit:])
    cont = '<span class="code-file">…continues</span>'
    ua = Unit(html=f'<div class="codeblock">{u.code_label}<span class="code-src">{highlight(a, u.code_lang)}</span></div>',
              name="code", splittable=True, code_src=a, code_lang=u.code_lang, code_label=u.code_label,
              height_mm=fit * per + CODE_OVERHEAD)
    ub = Unit(html=f'<div class="codeblock">{cont}<span class="code-src">{highlight(b, u.code_lang)}</span></div>',
              name="code", splittable=True, code_src=b, code_lang=u.code_lang, code_label=cont,
              height_mm=(n - fit) * per + CODE_OVERHEAD)
    return ua, ub


_TBODY = re.compile(r"^(.*?<tbody[^>]*>)(.*)(</tbody>.*)$", re.S)
_TR = re.compile(r"<tr\b.*?</tr>", re.S)


def _split_code_maybe(u: Unit, avail: float):
    """Split a code listing into `avail` if worthwhile, else None."""
    if u.name != "code" or not u.code_src:
        return None
    n = u.code_src.count("\n") + 1
    if n < 2 * MIN_CODE_LINES:
        return None
    per = max((u.height_mm - CODE_OVERHEAD) / n, 0.1)
    if avail - CODE_OVERHEAD < MIN_CODE_LINES * per:
        return None
    return _split_code(u, avail)


def _split_table(u: Unit, avail: float):
    """Split a too-tall table at row boundaries, repeating the header, else None."""
    if "<table" not in u.html:
        return None
    m = _TBODY.search(u.html)
    if not m:
        return None
    head, body, tail = m.groups()
    rows = _TR.findall(body)
    n = len(rows)
    if n < 2:
        return None
    per = max(u.height_mm / (n + 1), 0.1)  # +1 ≈ the repeated header row
    if avail < 2.5 * per:  # too little room to bother splitting into here
        return None
    fit = max(1, min(int(avail / per) - 1, n - 1))

    def frag(rws, k):
        return Unit(html=head + "".join(rws) + tail, name="prose", height_mm=(k + 1) * per)

    return frag(rows[:fit], fit), frag(rows[fit:], n - fit)


# Matches sentence-ending punctuation followed by whitespace before an uppercase letter,
# handling two HTML-specific patterns that the naive regex misses:
#
#   1. Citation markup between the period and the next sentence:
#        "...text.^<span id="cite-N-k"...></span><a href="#ref-N">N</a>^ Next"
#      The ^…^ block (digits and HTML tags only) is not whitespace and not a bare tag,
#      so (?:<[^>]+>)* never matched it.  We now recognise it explicitly via
#      (?:\^(?:<[^>]+>|[0-9]+)+\^).
#
#   2. Next sentence opening with an HTML tag (e.g. <em>, <strong>):
#        "...gap simultaneously.\n<em>Passive degradation</em>"
#      The lookahead (?=[A-Z]) failed because it saw < not a letter.  We now
#      skip any leading HTML tags in the lookahead prefix via (?:(?:<[^>]+>)\s*)*.
#
# The citation sub-pattern (?:\^(?:<[^>]+>|[0-9]+)+\^) is deliberately strict —
# only digits and tags between carets — so prose like "^some text^" never matches.
_SENT_BOUND = re.compile(
    r"([.!?]"
    r"(?:"
    r"(?:<[^>]+>)"                       # any HTML tag (closing tag after period)
    r"|(?:\^(?:<[^>]+>|[0-9]+)+\^)"     # citation markup: ^<span…><a…>N</a>^
    r"|[^\w\s<^]"                        # other non-word non-space chars (e.g. closing paren)
    r")*)"
    r"\s+"
    r"(?:(?:<[^>]+>)\s*)*"              # skip HTML tags opening the next sentence
    r"(?=[A-Z\(\"\u201c])"
)
MIN_PROSE_SENTENCES = 1   # minimum sentences to keep on each side of a split
_STRIP_TAGS = re.compile(r"<[^>]+>")


def _split_prose_maybe(u: Unit, avail: float):
    """Split a prose <p> at a sentence boundary so the first fragment fills `avail`.

    Returns (unit_a, unit_b) or None when the paragraph is too short, the
    available space is too small to be worth splitting, or no sentence boundary
    is found.
    """
    if u.name != "prose":
        return None
    html = u.html.strip()
    if not html.startswith("<p"):
        return None  # headings, lists, blockquotes — keep whole
    if avail < max(0.25 * u.height_mm, 20.0):
        return None  # too little room; moving the whole unit to the next page is better
    m = re.match(r"(<p[^>]*>)(.*?)(</p>)", html, re.S)
    if not m:
        return None
    open_tag, inner, close_tag = m.groups()
    # Collect candidate split positions (offset just after the sentence-ending char + tags)
    bounds: list[int] = []
    for mb in _SENT_BOUND.finditer(inner):
        bounds.append(mb.start() + len(mb.group(1)))
    n = len(bounds)
    lo, hi = MIN_PROSE_SENTENCES - 1, n - MIN_PROSE_SENTENCES
    if lo > hi:
        return None  # too few sentences to leave the minimum on each side
    frac = avail / u.height_mm
    # Estimate heights by plain-text character proportion (tags don't add visual height)
    plain_total = len(_STRIP_TAGS.sub("", inner))
    # Pick the largest k whose char-count fraction fits within avail — consistent with
    # the height estimator below.  The old round(frac*n) picked by sentence-index
    # (uniform-height assumption) which diverges from the char-count estimate when
    # sentences have unequal lengths, causing fragment A to overflow or leave whitespace.
    best_k = lo
    for kk in range(lo, hi + 1):
        if len(_STRIP_TAGS.sub("", inner[:bounds[kk]])) / plain_total <= frac:
            best_k = kk
    k = best_k
    split_pos = bounds[k]
    inner_a = inner[:split_pos]
    inner_b = inner[split_pos:].lstrip()
    if not inner_a or not inner_b:
        return None
    plain_a = len(_STRIP_TAGS.sub("", inner_a))
    frac_a = plain_a / plain_total if plain_total else frac
    ua = Unit(
        html=f"{open_tag}{inner_a}{close_tag}",
        name="prose",
        splittable=True,
        height_mm=u.height_mm * frac_a,
    )
    ub = Unit(
        html=f"{open_tag}{inner_b}{close_tag}",
        name="prose",
        splittable=True,
        height_mm=u.height_mm * (1.0 - frac_a),
    )
    return ua, ub


def pack(units: list[Unit], content_h: float = CONTENT_H) -> tuple[list[list[Unit]], Report]:
    pages: list[list[Unit]] = [[]]
    oversized: list[str] = []
    page_of: list[int] = []
    y = 0.0
    dq = deque(units)

    def new_page():
        nonlocal y
        if pages[-1]:
            pages.append([])
            y = 0.0

    def place(u):
        nonlocal y
        pages[-1].append(u)
        page_of.append(len(pages) - 1)
        y += u.height_mm

    while dq:
        u = dq.popleft()
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
        if u.break_before:
            new_page()
        h, avail = u.height_mm, content_h - y

        # keep-with-next: don't strand a heading at the page foot
        if u.heading and pages[-1] and dq and not dq[0].is_break and not dq[0].full_page:
            nh = dq[0].height_mm
            if y + h + nh > content_h + EPS and h + nh <= content_h + EPS:
                # Lookback split: fill the current page by splitting the last prose
                # paragraph before bumping the heading to the next page.
                last = pages[-1][-1]
                y_before_last = y - last.height_mm
                avail_for_last = content_h - y_before_last
                if last.name == "prose" and last.html.strip().startswith("<p"):
                    s = _split_prose_maybe(last, avail_for_last)
                    if s:
                        pages[-1].pop()
                        y = y_before_last
                        place(s[0])
                        dq.appendleft(u)   # re-queue heading
                        dq.appendleft(s[1])  # fragment B before heading
                        new_page()
                        avail = content_h
                        continue
                new_page()
                avail = content_h

        if h > avail + EPS:  # doesn't fit in the space left on this page
            # 1) gap-fill: code, prose, and tables can all split mid-page
            s = _split_code_maybe(u, avail) or _split_prose_maybe(u, avail) or _split_table(u, avail)
            if s:
                place(s[0]); dq.appendleft(s[1]); new_page(); continue
            # 2) fits whole on a fresh page -> move it there intact
            if h <= content_h + EPS:
                new_page(); dq.appendleft(u); continue
            # 3) taller than a whole page: split (code or table) or overflow-warn
            if pages[-1]:
                new_page()
            s = _split_code_maybe(u, content_h) or _split_table(u, content_h)
            if s:
                place(s[0]); dq.appendleft(s[1]); new_page(); continue
            label = u.name if u.name != "prose" else re.sub(r"<[^>]+>", "", u.html)[:40] + "…"
            oversized.append(f"{label} ({h:.0f}mm > {content_h:.0f}mm)")
            place(u)
            pages.append([])
            y = 0.0
            continue
        place(u)

    if not pages[-1]:
        pages.pop()
    return pages, Report(n_pages=len(pages), oversized=oversized, page_of=page_of)


def _tpl_to_css_content(tpl: str, meta: dict) -> str:
    """Translate a running-head template to a CSS content value.

    '{chapter} — {section}' → 'string(chapter) " — " string(section)'
    '{title}'               → '"My Document Title"'   (static, inlined)
    '{page} / {total}'      → 'counter(page) " / " counter(pages)'
    """
    _CSS_TOKENS = {
        "chapter": "string(chapter)",
        "section": "string(section)",
        "page":    "counter(page)",
        "total":   "counter(pages)",
    }
    parts = re.split(r"(\{[^}]+\})", tpl)
    css_parts = []
    for part in parts:
        if not part:
            continue
        if part.startswith("{") and part.endswith("}"):
            key = part[1:-1]
            css_parts.append(_CSS_TOKENS.get(key, f'"{meta.get(key, key)}"'))
        else:
            css_parts.append(f'"{part}"')
    return " ".join(css_parts)


def _emit_css(theme: Theme, meta: dict | None = None) -> str:
    meta = meta or {}
    margin, _, _ = _geom(theme)
    w, h = _page_size(theme)
    masters_cfg = theme.meta.get("masters", {})
    body_furniture = theme.master_furniture("body")
    header_cfg = masters_cfg.get("body", {}).get("header")

    parts: list[str] = []

    # ── keep :root custom properties for themes that reference them ──────────
    parts.append(f":root{{--page-margin:{margin}mm}}")
    parts.append(theme.css)
    parts.append(hl_css())

    # ── @page geometry (CSS paged media — replaces fixed .page divs) ─────────
    # deck: .slide is itself page-sized and carries its own padding, so a page
    # margin here would double-count and fragment every slide onto a second page.
    page_margin = 0 if str(theme.meta.get("mode", "")) == "deck" else margin
    parts.append(f"@page{{size:{w}mm {h}mm;margin:{page_margin}mm}}")
    parts.append("html,body{margin:0;padding:0}")

    # ── named pages for full-page masters (margin 0 so element fills page) ───
    for master_name in masters_cfg:
        if master_name not in ("body",):
            parts.append(f"@page master-{master_name}{{margin:0}}")

    # ── full-page master divs: break to own page, fill the full sheet ────────
    parts.append(
        f".page{{break-before:page;break-after:page;"
        f"width:{w}mm;height:{h}mm;box-sizing:border-box;"
        f"position:relative;overflow:hidden}}"
    )
    # suppress the spurious blank page that would precede the very first element
    parts.append(".page:first-child{break-before:auto}")

    # ── string-set: let WeasyPrint track chapter / section automatically ──────
    if body_furniture == "stamp" or header_cfg:
        parts.append("h1{string-set:chapter content()}")
        parts.append("h2{string-set:section content()}")

    # ── page furniture: stamp (footer chapter + page number) ─────────────────
    if body_furniture == "stamp":
        font = "font-family:var(--heading-font),sans-serif;font-size:7.5pt;color:var(--muted)"
        parts.append(
            f"@page{{@bottom-left{{content:string(chapter,first);{font};"
            f"vertical-align:top;padding-top:3mm}}"
            f"@bottom-right{{content:counter(page);{font};"
            f"vertical-align:top;padding-top:3mm}}}}",
        )

    # ── page furniture: running header (verso / recto) ────────────────────────
    if header_cfg:
        font = "font-family:var(--heading-font),sans-serif;font-size:7.5pt;color:var(--muted)"
        verso = header_cfg.get("verso", "")
        recto = header_cfg.get("recto", "")
        if verso:
            css_v = _tpl_to_css_content(verso, meta)
            parts.append(
                f"@page:left{{@top-left{{content:{css_v};{font};"
                f"vertical-align:bottom;padding-bottom:3mm}}}}"
            )
        if recto:
            css_r = _tpl_to_css_content(recto, meta)
            parts.append(
                f"@page:right{{@top-right{{content:{css_r};{font};"
                f"vertical-align:bottom;padding-bottom:3mm}}}}"
            )

    # ── fragmentation rules ───────────────────────────────────────────────────
    parts.extend([
        # headings always stay with the element that follows them
        "h1,h2,h3,h4,h5,h6{break-after:avoid}",
        # author / theme explicit page break
        ".pagebreak{break-before:page;display:block;height:0;margin:0;padding:0}",
        # unit classes
        ".unit{display:flow-root}",
        ".unit.break-before{break-before:page}",
        ".unit.keep{break-inside:avoid}",
        # figures and captions always travel together
        "figure{break-inside:avoid;margin:4mm 0}",
        "figcaption{font-size:8.5pt;color:var(--muted);margin-top:2mm}",
        # images fill the content column width
        ".unit img,figure img{width:100%;height:auto;display:block}",
    ])

    # ── deck: fixed-size slide boxes (unchanged from before) ─────────────────
    parts.extend([
        f".slide{{width:{w}mm;height:{h}mm;box-sizing:border-box;"
        "overflow:hidden;page-break-after:always}",
        ".slide:last-child{page-break-after:auto}",
    ])

    return "".join(parts)


def _fill_tokens(tpl: str, mapping: dict) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(mapping.get(m.group(1), "")), tpl)


def emit(units: list[Unit], theme: Theme, meta: dict | None = None) -> str:
    """Emit a single-flow HTML document; CSS Fragmentation handles page breaks."""
    meta = meta or {}
    out = [
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><style>",
        _emit_css(theme, meta),
        "</style></head><body>",
    ]

    for u in units:
        if u.is_break:
            out.append('<div class="pagebreak"></div>')
            continue

        if u.full_page:
            # Full-page master (cover, section opener, back cover…): wrap in a
            # fixed-size .page div assigned to the master's named @page rule.
            # u.html is already fully rendered by the parser (template + content
            # substituted); never re-render here or {{content}} gets lost.
            classes = theme.master_classes(u.master)
            master_page = f"master-{u.master}" if u.master else ""
            page_attr = f' style="page:{master_page}"' if master_page else ""
            out.append(f'<div class="page {classes}"{page_attr}>{u.html}</div>')
            continue

        # Regular flow unit
        cls = ["unit"]
        if u.break_before:
            cls.append("break-before")
        if u.keep_together:
            cls.append("keep")
        out.append(f'<div class="{" ".join(cls)}">{u.html}</div>')

    out.append("</body></html>")
    return "".join(out)


def _group_slides(units: list[Unit], has_title: bool):
    """Split the unit stream into slides. A section heading (h1) is a divider
    slide; a slide heading (h2) starts a content slide; ::: newpage / --- forces a
    break; a full-page component is its own slide. Returns [(master, [units])]."""
    slides: list[tuple[str, list[Unit]]] = []
    cur: list[Unit] = []
    cur_master = "content"

    def flush():
        nonlocal cur
        if cur:
            slides.append((cur_master, cur))
            cur = []

    if has_title:
        slides.append(("title", []))
    for u in units:
        if u.is_break:
            flush()
        elif u.full_page:
            flush()
            slides.append((u.master or "content", [u]))
        elif u.heading and u.heading_level == 1:
            flush()
            slides.append(("section", [u]))
        elif u.heading and u.heading_level == 2:
            flush()
            cur = [u]
        else:
            cur.append(u)
    flush()
    return slides


def emit_deck(slides, theme: Theme, meta: dict) -> str:
    total = len(slides)
    out = ["<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><style>",
           _emit_css(theme), "</style></head><body>"]
    for n, (master, units) in enumerate(slides, 1):
        out.append(f'<div class="slide {master}">')
        if master == "title":
            out.append(render_template(theme.master_template("title"), dict(meta)))
        elif len(units) == 1 and units[0].full_page:
            out.append(units[0].html)  # statement / closing / other full-slide masters
        else:
            out.append('<div class="slide-body">')
            for u in units:
                out.append(f'<div class="unit">{u.html}</div>')
            out.append("</div>")
            out.append(f'<div class="slide-counter">{n} / {total}</div>')
        out.append("</div>")
    out.append("</body></html>")
    return "".join(out)


def _render_deck(units, theme, meta, out_path, base_url, content_h) -> Report:
    slides = _group_slides(units, has_title=bool(meta.get("title")))
    oversized = []
    for i, (master, us) in enumerate(slides, 1):
        if master in ("title", "section"):
            continue
        tot = sum(u.height_mm for u in us if not u.full_page)
        if tot > content_h + EPS:
            oversized.append(f"slide {i} overflows ({tot:.0f}mm > {content_h:.0f}mm) — trim it")
    doc = HTML(string=emit_deck(slides, theme, meta), base_url=base_url).render()
    if len(doc.pages) != len(slides):
        oversized.append(f"slide-count drift: planned {len(slides)}, rendered {len(doc.pages)}")
    doc.write_pdf(out_path)
    # report what was actually rendered, not what was planned — otherwise a
    # fragmented slide is invisible in the success line.
    return Report(n_pages=len(doc.pages), oversized=oversized, page_of=[])


# var names that become CSS custom properties (the customization contract)
_APPEARANCE = {
    "accent", "accent-dark", "brand", "brand-dark", "ink", "muted", "rule",
    "body-font", "heading-font", "mono-font",
}


def render_pdf(src: str, out_path: str, base_url: str | None = None,
               theme_name: str = "report", cwd: str | None = None,
               execute: bool = True, vars: dict | None = None,
               code_root: str | None = None) -> Report:
    from .parse import frontmatter, parse

    theme = load_theme(theme_name)
    _, _, content_h = _geom(theme)
    # theme var defaults, overridden by project vars, then by per-doc frontmatter
    merged = {**theme.vars, **(vars or {})}
    meta = {**merged, **frontmatter(src)}

    def _css_val(k, v):
        v = str(v)
        # multi-word font-family names must be quoted to be a valid CSS value
        if k.endswith("-font") and " " in v and v[0] not in "'\"":
            v = f"'{v}'"
        return f"--{k}:{v};"

    overrides = "".join(_css_val(k, merged[k]) for k in _APPEARANCE if k in merged)
    if overrides:
        theme.css += f":root{{{overrides}}}"

    # freeze cache serves both executed code and rendered math
    freeze = Freeze(Path(cwd) / ".scriptorium" / "freeze.json") if cwd else None
    from . import mathrender
    mathrender.set_freeze(freeze)

    env = None
    if execute:
        # tangle export= blocks first so executed blocks can import them
        stem = str(meta.get("stem", "doc"))
        if cwd:
            tangle_write(src, cwd, doc_stem=stem)
        pythonpath = []
        if cwd and code_root:
            pythonpath = [str((Path(cwd) / code_root).resolve())]
        env = ExecEnv(cwd=cwd, freeze=freeze, pythonpath=pythonpath)
        if isinstance(meta.get("execute"), dict) and meta["execute"].get("interpreters"):
            env.interpreters.update(meta["execute"]["interpreters"])

    from .parse import fill_toc
    from .citations import process_citations

    src = process_citations(src)
    units = parse(src, theme, env, meta=meta)
    units = fill_toc(units, depth=int(meta.get("toc_depth", 2)))

    if str(theme.meta.get("mode", "")) == "deck":  # slides: keep measure+pack pipeline
        measure(units, theme, base_url=base_url)
        return _render_deck(units, theme, meta, out_path, base_url, content_h)

    # Document themes: CSS Fragmentation handles all pagination — no measure, no pack.
    doc = HTML(string=emit(units, theme, meta), base_url=base_url).render()
    doc.write_pdf(out_path)
    return Report(n_pages=len(doc.pages), oversized=[], page_of=[])
