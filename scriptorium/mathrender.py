"""Render LaTeX math to self-contained SVG via quickjax (MathJax v4 in QuickJS).

Pure Python, no Node, no LaTeX install. Each SVG carries its own glyph paths and
a computed `vertical-align`, so inline math sits on the text baseline and scales
with font-size. Results are memoized in-process and, when a freeze store is set,
persisted across builds (3,000+ equations render once, then never again).
"""

from html import escape

import quickjax

_cache: dict[str, str] = {}
_freeze = None


def set_freeze(freeze) -> None:
    global _freeze
    _freeze = freeze


def _render(tex: str, display: bool) -> str:
    key = f"math\0{int(display)}\0{tex}"
    if key in _cache:
        return _cache[key]
    if _freeze is not None:
        hit = _freeze.get(key)
        if hit is not None:
            _cache[key] = hit
            return hit
    try:
        svg = quickjax.render(tex, display=display)
    except Exception:
        svg = f'<code class="math-err">{escape(tex)}</code>'
    if display:
        svg = f'<div class="math-display">{svg}</div>'
    _cache[key] = svg
    if _freeze is not None:
        _freeze.set(key, svg)
    return svg


def render_inline(tex: str) -> str:
    return _render(tex, False)


def render_display(tex: str) -> str:
    return _render(tex, True)
