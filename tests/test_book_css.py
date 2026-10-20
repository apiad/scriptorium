"""browser_css: the theme CSS minus what only paged media understands."""

from scriptorium.book import browser_css
from scriptorium.theme import load_theme


def test_page_rules_and_margin_boxes_go():
    css = ("@page{size:a4;@bottom-center{content:counter(page)}} @page master-cover{margin:0} "
           "@page:left{@top-left{content:'x'}} @page :right{margin:0} p{color:red}")
    assert browser_css(css).strip() == "p{color:red}"


def test_page_and_slide_blocks_go_but_pagebreak_stays():
    out = browser_css(".page{width:210mm} .page:first-child{x:1} .slide{x:1} .pagebreak{break-before:page}")
    assert ".page{" not in out and ".page:first-child" not in out and ".slide{" not in out
    assert ".pagebreak{break-before:column}" in out


def test_paged_only_declarations_go_and_the_rule_stays():
    out = browser_css("h1{string-set:chap content();color:blue} "
                      "a.ref-fig::after{content:target-counter(attr(href url),figure)}")
    assert "string-set" not in out and "color:blue" in out
    assert "target-counter" not in out


def test_break_before_page_with_spaces_is_rewritten():
    assert "break-before: column" in browser_css(".x{break-before: page}")


def test_media_blocks_keep_their_rules():
    out = browser_css("@media (max-width:600px){p{color:red}} @font-face{font-family:X;src:url(a.woff2)}")
    assert "@media (max-width:600px){p{color:red}}" in out and "@font-face" in out


def test_comments_with_braces_do_not_confuse_the_scanner():
    out = browser_css("/* { not a block } */ p{color:red} @page{margin:0}")
    assert "p{color:red}" in out and "@page" not in out


def test_real_book_theme_has_nothing_paged_left():
    css = browser_css(load_theme("book").css)
    for paged in ("@page", "target-counter", "target-text", "string-set", "counter(page"):
        assert paged not in css, paged
    assert "@font-face" in css
