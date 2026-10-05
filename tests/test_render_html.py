import pytest

from scriptorium.render import prepare, render_html


DOC = """---
theme: book
---

# Embeddings

Words are symbols.[^a] Math $x^2$ too.

1. one

2. two

::: note
inside
:::

[^a]: A footnote body.
"""


def test_render_html_returns_a_whole_document():
    html, warnings = render_html(DOC, execute=False)
    assert html.startswith("<!DOCTYPE html>")
    assert "<style>" in html and "</body></html>" in html
    assert '<h1 id="embeddings">Embeddings</h1>' in html
    assert 'class="footnote-ref"' in html          # preprocessors ran
    assert "<svg" in html                           # math rendered
    assert '<div class="note">' in html             # component rendered
    assert warnings == []


def test_render_html_keeps_raw_html_blocks_in_order():
    src = ('# T\n\nA.\n\n<span class="m" data-b="1"></span>\n\n'
           'B.\n\n<span class="m" data-b="2"></span>\n')
    html, _ = render_html(src, execute=False)
    a, m1, b, m2 = (html.index(s) for s in ("<p>A.</p>", 'data-b="1"', "<p>B.</p>", 'data-b="2"'))
    assert a < m1 < b < m2


def test_render_html_drops_html_comments():
    html, _ = render_html("# T\n\nA.\n\n<!-- @alex\nnote\n-->\n", execute=False)
    assert "@alex" not in html


def test_render_html_refuses_deck_themes():
    with pytest.raises(ValueError, match="deck"):
        render_html("---\ntheme: deck\n---\n\n# Slide\n", execute=False)


def test_prepare_exposes_units_and_theme():
    p = prepare(DOC, execute=False)
    assert p.theme.name == "book"
    assert any(u.heading == "Embeddings" for u in p.units)
