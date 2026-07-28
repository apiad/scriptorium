"""Syntax highlighting via Pygments (pure-Python, no extra system deps).

`highlight(code, lang)` returns an HTML block; `css()` returns the style sheet
(emitted once into the theme CSS). Falls back to a plain `<pre>` on any error.
"""

from html import escape

from pygments import highlight as _hl
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

_FORMATTER = HtmlFormatter(nowrap=False, cssclass="hl")


def css() -> str:
    return _FORMATTER.get_style_defs(".hl")


def highlight(code: str, lang: str) -> str:
    try:
        lexer = get_lexer_by_name(lang or "text")
    except ClassNotFound:
        return f'<pre class="hl"><code>{escape(code)}</code></pre>'
    return _hl(code, lexer, _FORMATTER)
