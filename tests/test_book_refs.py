"""resolve_refs: the numbers paged media gave references, as text for a browser."""

from scriptorium.book import resolve_refs
from scriptorium.parse import parse
from scriptorium.theme import load_theme

SRC = """# Intro {.unnumbered #chap-intro}

# Trees {#chap-trees}

## Roots {#sec-roots}

## Walks {#sec-walks}

<figure id="fig-tree"><img src="t.png"><figcaption>A <em>tall</em> tree</figcaption></figure>

See @chap-trees, @sec-walks and @fig-tree. Lost: @fig-none.
"""


def _html(units):
    return "".join(u.html for u in units)


def test_book_refs_resolve_like_the_theme_counters():
    theme = load_theme("book")
    units = parse(SRC, theme)
    warns = resolve_refs(units, theme.meta["html-refs"], {})
    html = _html(units)
    assert ">Chapter 1</a>" in html and ">§1.2</a>" in html and ">“A tall tree”</a>" in html
    assert any("fig-none" in w for w in warns)


def test_base_fig_ref_uses_the_ref_label():
    theme = load_theme("report")
    units = parse('<figure id="fig-a"><figcaption>x</figcaption></figure>\n\nSee @fig-a.', theme)
    resolve_refs(units, theme.meta["html-refs"], {"figure-ref-label": "figura"})
    assert ">figura 1</a>" in _html(units)


def test_ref_label_falls_back_to_the_caption_label():
    theme = load_theme("report")
    units = parse('<figure id="fig-a"><figcaption>x</figcaption></figure>\n\nSee @fig-a.', theme)
    resolve_refs(units, theme.meta["html-refs"], {"figure-label": "Figura"})
    assert ">Figura 1</a>" in _html(units)


def test_a_kind_without_a_format_shows_the_target_text():
    theme = load_theme("report")
    units = parse("## Methods {#sec-methods}\n\nSee @sec-methods.", theme)
    resolve_refs(units, {}, {})
    assert ">Methods</a>" in _html(units)


def test_a_child_theme_keeps_the_parents_formats():
    assert {"chap", "sec", "fig"} <= set(load_theme("book").meta["html-refs"])
    assert "fig" in load_theme("article").meta["html-refs"]
