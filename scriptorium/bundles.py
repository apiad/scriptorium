"""Display bundles: what a python block's display() prints, and where it lands.

The driver in execute.py prints each displayed object as JSON between
BUNDLE_START and BUNDLE_END: {"data": {mime: str}, "metadata": {...}}, the
shape of IPython's rich display, bytes as base64.
"""

import base64
import hashlib
import json
import re
from html import escape
from pathlib import Path

from .execute import BUNDLE_END, BUNDLE_START

_BUNDLE = re.compile(re.escape(BUNDLE_START) + r"(.*?)" + re.escape(BUNDLE_END), re.S)


def split(stdout: str) -> list:
    """The block's output in order: text runs as str, bundles as dicts."""
    parts, pos = [], 0
    for m in _BUNDLE.finditer(stdout):
        if m.start() > pos:
            parts.append(stdout[pos:m.start()])
        parts.append(json.loads(m.group(1)))
        pos = m.end()
    if pos < len(stdout):
        parts.append(stdout[pos:])
    return parts


def _slug(caption: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", caption.lower()).strip("-")[:60].rstrip("-")
    return slug or "view"


def _write(outdir: Path, sub: str, caption: str, ext: str, data: bytes) -> str:
    rel = Path("build") / sub / f"{_slug(caption)}-{hashlib.sha256(data).hexdigest()[:8]}.{ext}"
    path = outdir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)
    return rel.as_posix()


def _site_html(data: dict, outdir: Path, caption: str, ident: str) -> str:
    """The bundle's own HTML, its audio written as a file in place of its data URI, and the
    id on its outermost <figure> so the figure is numbered like an image with audio."""
    page = data["text/html"]
    for mime, ext in (("audio/mpeg", "mp3"), ("audio/wav", "wav")):
        if mime in data:
            path = _write(outdir, "audio", caption, ext, base64.b64decode(data[mime]))
            page = page.replace(f"data:{mime};base64,{data[mime]}", path)
    if ident and page.lstrip().startswith("<figure"):
        ident = ident if ident.startswith("fig-") else "fig-" + ident
        page = re.sub(r"<figure\b", f'<figure id="{escape(ident)}"', page.lstrip(), count=1)
    return "\n" + page + "\n\n"


def place(bundle: dict, outdir: Path, fallback: dict | None = None, site: bool = False) -> str:
    """Markdown or raw HTML for one bundle, writing its image and audio under outdir/build.

    Preference: text/markdown; on a site (the docs format), the HTML of a bundle whose
    metadata asks for it with "site": "html"; an image and/or audio as files (one figure
    when both); text/html; text/plain as output. Caption and id come from the bundle's
    metadata, else from fallback (the block's attributes)."""
    data = bundle.get("data", {})
    meta = {k: v for k, v in (fallback or {}).items() if v}
    meta.update({k: v for k, v in (bundle.get("metadata") or {}).items() if v})
    caption, ident = meta.get("caption", ""), meta.get("id", "")
    if "text/markdown" in data:
        return data["text/markdown"] + "\n\n"
    if site and meta.get("site") == "html" and "text/html" in data:
        return _site_html(data, outdir, caption, ident)
    img = audio = None
    if "image/svg+xml" in data:
        img = _write(outdir, "img", caption, "svg", data["image/svg+xml"].encode())
    elif "image/png" in data:
        img = _write(outdir, "img", caption, "png", base64.b64decode(data["image/png"]))
    for mime, ext in (("audio/mpeg", "mp3"), ("audio/wav", "wav")):
        if mime in data:
            audio = _write(outdir, "audio", caption, ext, base64.b64decode(data[mime]))
            break
    if img or audio:
        if ident and not ident.startswith(("fig-", "aud-")):
            ident = ("fig-" if img else "aud-") + ident
        if img and audio:
            id_attr = f' id="{escape(ident)}"' if ident else ""
            cap = f"<figcaption>{escape(caption)}</figcaption>" if caption else ""
            return (f'\n<figure class="view"{id_attr}><img src="{img}" alt="{escape(caption)}">'
                    f'<audio controls preload="none" src="{audio}"></audio>{cap}</figure>\n\n')
        alt = caption.replace("[", "\\[").replace("]", "\\]")
        return f"\n\n![{alt}]({img or audio})" + (f"{{#{ident}}}" if ident else "") + "\n\n"
    if "text/html" in data:
        return "\n" + data["text/html"] + "\n\n"
    return f'\n<pre class="output">{escape(data.get("text/plain", ""))}</pre>\n\n'
