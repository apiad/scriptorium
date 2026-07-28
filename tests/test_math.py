"""VS4 acceptance: LaTeX math renders to SVG via quickjax, inline and display."""

from scriptorium.parse import parse
from scriptorium import mathrender


def test_inline_math_becomes_svg():
    (unit,) = parse(r"The cost is $O(\log n)$ per operation.")
    assert "<svg" in unit.html
    assert "vertical-align" in unit.html  # quickjax self-baselines inline math


def test_display_math_is_centered_block():
    units = parse("A prefix identity:\n\n$$a = b - c$$")
    html = "".join(u.html for u in units)
    assert 'class="math-display"' in html and "<svg" in html


def test_tricky_bitwise_notation_renders():
    (unit,) = parse(r"lowest bit: $i \mathbin{\&} -i$")
    assert "<svg" in unit.html and "math-err" not in unit.html


def test_math_is_cached():
    mathrender._cache.clear()
    a = mathrender.render_inline(r"x^2 + y^2")
    b = mathrender.render_inline(r"x^2 + y^2")
    assert a == b
    assert f"math\x00{0}\x00x^2 + y^2" in mathrender._cache
