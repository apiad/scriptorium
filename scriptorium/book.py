"""The HTML book: a static, installable ebook directory built from the units.

The same units a PDF prints from are laid out by a browser's multi-column
layout instead of WeasyPrint's paged media. This module turns the theme's CSS
into what a browser runs, resolves the cross-references that paged media
numbered, collects images and fonts into the site, and writes the reader.
"""

import hashlib
import re
import shutil
from pathlib import Path
from urllib.parse import unquote

# Declarations only paged media understands. In a browser an unknown function
# invalidates the whole declaration, so a `content: "Chapter " target-counter()`
# would leave the reference empty rather than half-filled.
_PAGED_VALUE = re.compile(r"target-counter\(|target-text\(|counter\(pages?\b|leader\(|string\(")
_PAGED_PROPS = {"string-set", "bookmark-level", "bookmark-label", "page"}
# fixed-size page and slide boxes; the reader has its own full-page block
_DROP_SELECTORS = {".page", ".page:first-child", ".slide", ".slide:last-child"}
# at-rules whose body is more rules, filtered the same way
_NESTED = ("@media", "@supports", "@layer", "@container", "@document")
_BREAK_PAGE = re.compile(r"\b((?:page-)?break-(?:before|after)\s*:\s*)(?:page|always|left|right|recto|verso)\b")


def _strip_comments(css: str) -> str:
    out, i = [], 0
    while i < len(css):
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            i = len(css) if end < 0 else end + 2
            continue
        if css[i] in "\"'":
            j = _string_end(css, i)
            out.append(css[i:j])
            i = j
            continue
        out.append(css[i])
        i += 1
    return "".join(out)


def _string_end(css: str, i: int) -> int:
    q, j = css[i], i + 1
    while j < len(css) and css[j] != q:
        j += 2 if css[j] == "\\" else 1
    return j + 1


def _items(css: str):
    """Top-level (prelude, body) pairs; body is None for a `@import …;` statement."""
    i, n = 0, len(css)
    while i < n:
        start, depth, paren = i, 0, 0
        while i < n:
            c = css[i]
            if c in "\"'":
                i = _string_end(css, i)
                continue
            if c == "(":
                paren += 1
            elif c == ")":
                paren -= 1
            elif c == ";" and depth == 0 and paren == 0:
                stmt = css[start:i].strip()
                i += 1
                if stmt:
                    yield stmt, None
                break
            elif c == "{" and paren == 0:
                if depth == 0:
                    open_at = i
                depth += 1
            elif c == "}" and paren == 0:
                depth -= 1
                if depth == 0:
                    yield css[start:open_at].strip(), css[open_at + 1:i]
                    i += 1
                    break
            i += 1
        else:
            rest = css[start:].strip()
            if rest:
                yield rest, None


def _declarations(body: str) -> list[str]:
    decls, cur, paren, i = [], [], 0, 0
    while i < len(body):
        c = body[i]
        if c in "\"'":
            j = _string_end(body, i)
            cur.append(body[i:j])
            i = j
            continue
        if c == "(":
            paren += 1
        elif c == ")":
            paren -= 1
        if c == ";" and paren == 0:
            decls.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    decls.append("".join(cur))
    return [d for d in decls if d.strip()]


def _filter_rule(body: str) -> str:
    kept = []
    for d in _declarations(body):
        prop, _, value = d.partition(":")
        if prop.strip().lower() in _PAGED_PROPS or _PAGED_VALUE.search(value):
            continue
        kept.append(_BREAK_PAGE.sub(r"\1column", d))
    return ";".join(kept)


def browser_css(css: str) -> str:
    """The theme CSS without what only paged media understands: `@page` rules
    and their margin boxes, page and slide boxes, `string-set`, and contents
    built with `target-counter()` / `target-text()` / `counter(page)`. Page
    breaks become column breaks, since a page of the book is a column."""
    out = []
    for prelude, body in _items(_strip_comments(css)):
        if body is None:
            out.append(prelude + ";")
            continue
        at = prelude.split(None, 1)[0].lower() if prelude.startswith("@") else ""
        if at == "@page":
            continue
        if at in _NESTED:
            out.append(f"{prelude}{{{browser_css(body)}}}")
        elif at:  # @font-face, @keyframes, …: untouched
            out.append(f"{prelude}{{{body}}}")
        elif {s.strip() for s in prelude.split(",")} <= _DROP_SELECTORS:
            continue
        else:
            kept = _filter_rule(body)
            if kept.strip():
                out.append(f"{prelude}{{{kept}}}")
    return "\n".join(out)


_ID_TAG = re.compile(r'<(\w+)\b([^>]*?)\bid="([^"]+)"([^>]*)>')
_REF_A = re.compile(r'<a class="ref-(\w+)" href="#([^"]+)"></a>')
_TAGS = re.compile(r"<[^>]+>")
_FIELD = re.compile(r"\{([\w-]+)\}")


def _inner_text(html: str, start: int, tag: str) -> str:
    end = html.find(f"</{tag}>", start)
    return _TAGS.sub("", html[start:end if end >= 0 else start]).strip()


def resolve_refs(units, formats: dict, vars: dict) -> list[str]:
    """Write each `@kind-id` reference's text into its empty anchor.

    Paged media fills these with `target-counter()`, which browsers do not
    implement. The counting follows the themes' CSS: a chapter is an `h1` that
    is neither `.unnumbered` nor `.part` and restarts the sections, a section
    is an `h2`, a figure is a `<figure id="fig-…">`. The strings come from the
    theme's `html-refs:`; a kind without one shows the target's own text."""
    counters = {"chapter": 0, "section": 0, "figure": 0}
    targets: dict[str, dict] = {}
    for u in units:
        for m in _ID_TAG.finditer(u.html):
            tag, attrs, ident = m.group(1).lower(), m.group(2) + m.group(4), m.group(3)
            classes = re.search(r'class="([^"]*)"', attrs)
            classes = classes.group(1).split() if classes else []
            if tag == "h1" and not {"unnumbered", "part"} & set(classes):
                counters["chapter"] += 1
                counters["section"] = 0
            elif tag == "h2":
                counters["section"] += 1
            elif tag == "figure" and ident.startswith("fig-"):
                counters["figure"] += 1
            if tag == "figure":
                cap = u.html.find("<figcaption", m.end())
                text = _inner_text(u.html, u.html.find(">", cap) + 1, "figcaption") if cap >= 0 else ""
            elif tag == "img":
                alt = re.search(r'alt="([^"]*)"', attrs)
                text = alt.group(1) if alt else ""
            else:
                text = _inner_text(u.html, m.end(), tag)
            targets[ident] = {**counters, "text": text}

    def label(key):
        v = vars.get(key)
        if v is None and key == "figure-ref-label":
            v = vars.get("figure-label")
        return str(v if v is not None else "").strip("\"'")

    warnings = []

    def fill(m):
        kind, ident = m.group(1), m.group(2)
        t = targets.get(ident)
        if t is None:
            warnings.append(f"unresolved reference @{ident}")
            return m.group(0)
        fmt = formats.get(kind, "{text}")
        text = _FIELD.sub(lambda f: str(t[f.group(1)]) if f.group(1) in t else label(f.group(1)), fmt)
        return f'<a class="ref-{kind}" href="#{ident}">{text.strip()}</a>'

    for u in units:
        u.html = _REF_A.sub(fill, u.html)
    return warnings


_IMG = re.compile(r"<img\b[^>]*>")
_SRC = re.compile(r'\bsrc="([^"]*)"')
_SIZE_ATTR = re.compile(r'\s(?:width|height)="[^"]*"')
_RASTER = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
_FONT = {".woff2", ".woff", ".ttf", ".otf"}
_CSS_FILE_URL = re.compile(r"url\(\s*(['\"]?)file://([^)'\"]+)\1\s*\)")


def _is_local(url: str) -> bool:
    return not url.startswith(("http:", "https:", "data:", "//", "#"))


def _webp(src: Path, dst: Path, max_width: int) -> tuple[int, int]:
    from PIL import Image

    with Image.open(src) as im:
        alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        im = im.convert("RGBA" if alpha else "RGB")
        if im.width > max_width:
            im = im.resize((max_width, round(im.height * max_width / im.width)), Image.LANCZOS)
        im.save(dst, "WEBP", quality=80, method=6)
        return im.size


def _svg_size(path: Path) -> tuple[int, int] | None:
    head = path.read_text(encoding="utf-8", errors="replace")[:2000]
    w, h = re.search(r'\bwidth="([\d.]+)', head), re.search(r'\bheight="([\d.]+)', head)
    return (round(float(w.group(1))), round(float(h.group(1)))) if w and h else None


def collect_images(html: str, base_dir: Path, out_dir: Path, max_width: int) -> tuple[str, list[str]]:
    """Copy every local image into `out_dir/img/`, rasters as WebP no wider
    than `max_width`, and rewrite each tag to point there with its intrinsic
    `width` and `height`: an image without them reflows every column after it
    when it loads. Files are named by content, so a build is deterministic and
    an image used twice is stored once."""
    done: dict[Path, tuple[str, tuple[int, int] | None]] = {}
    warnings: list[str] = []

    def sub(m):
        tag = m.group(0)
        src = _SRC.search(tag)
        if not src or not _is_local(src.group(1)):
            return tag
        path = (base_dir / unquote(src.group(1))).resolve()
        if path not in done:
            if not path.is_file():
                warnings.append(f"image {src.group(1)!r} not found")
                return tag
            data = path.read_bytes()
            digest = hashlib.sha256(data + str(max_width).encode()).hexdigest()[:12]
            (out_dir / "img").mkdir(parents=True, exist_ok=True)
            ext = path.suffix.lower()
            if ext in _RASTER:
                name = f"img/{digest}.webp"
                size = _webp(path, out_dir / name, max_width)
            else:
                name = f"img/{digest}{ext}"
                shutil.copyfile(path, out_dir / name)
                size = _svg_size(path) if ext == ".svg" else None
            done[path] = (name, size)
        name, size = done[path]
        tag = _SIZE_ATTR.sub("", tag)
        dims = f' width="{size[0]}" height="{size[1]}"' if size else ""
        return tag.replace(src.group(0), f'src="{name}"{dims}', 1)

    return _IMG.sub(sub, html), warnings


def collect_css_assets(css: str, out_dir: Path) -> str:
    """Copy what the theme CSS loads from disk (fonts, a logo) into the site
    and point the CSS at the copies. Themes reach their assets through
    `file://` URLs (theme.py makes them absolute for WeasyPrint)."""
    taken: dict[str, Path] = {}

    def sub(m):
        path = Path(unquote(m.group(2)))
        if not path.is_file():
            return m.group(0)
        folder = "fonts" if path.suffix.lower() in _FONT else "assets"
        name = f"{folder}/{path.name}"
        if taken.get(name, path) != path:  # two themes, one file name
            name = f"{folder}/{hashlib.sha256(str(path).encode()).hexdigest()[:8]}-{path.name}"
        if name not in taken:
            (out_dir / folder).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, out_dir / name)
            taken[name] = path
        return f"url('{name}')"

    return _CSS_FILE_URL.sub(sub, css)
