"""The HTML book's directory: what the example book builds to."""

import json
import re
from pathlib import Path


def _all_html(site: Path) -> str:
    return "".join(p.read_text(encoding="utf-8") for p in sorted(site.glob("chapters/*.html")))


def _local_urls(site: Path):
    html = (site / "index.html").read_text(encoding="utf-8") + _all_html(site)
    css = (site / "book.css").read_text(encoding="utf-8")
    urls = re.findall(r'(?:src|href)="([^"#][^"]*)"', html)
    urls += re.findall(r"url\(\s*['\"]?([^)'\"]+)", css)
    return [u for u in urls if not u.startswith(("http:", "https:", "data:"))]


def test_site_has_the_reader_files(site):
    for f in ("index.html", "book.css", "reader.js"):
        assert (site / f).is_file()


def test_one_file_per_chapter_and_a_small_index(site):
    files = sorted(p.name for p in (site / "chapters").iterdir())
    assert files == ["000.html", "001.html", "002.html", "003.html"]
    index = (site / "index.html").read_text(encoding="utf-8")
    assert "Marta" not in index  # the text lives in the chapters
    book = json.loads(re.search(r"window.BOOK = (\{.*?\});</script>", index, re.S).group(1))
    assert [c["file"] for c in book["chapters"]] == [f"chapters/{f}" for f in files]
    assert book["ids"]["fig-faro"] == 1 and book["ids"]["chap-regreso"] == 3
    assert [t["chapter"] for t in book["toc"]] == [1, 2, 3]


def test_chapters_carry_their_counters(site):
    starts = [re.search(r'counter-reset: ([^"]+)"', (site / f"chapters/00{n}.html").read_text()).group(1)
              for n in range(4)]
    assert starts[3] == "chapter 2 part 0 figure 1"


def test_every_img_has_dimensions(site):
    html = _all_html(site)
    assert re.findall(r"<img(?![^>]*\bwidth=)[^>]*>", html) == []
    assert len(re.findall(r"<img\b", html)) == 3


def test_every_local_url_is_relative_and_exists(site):
    urls = _local_urls(site)
    assert urls
    for url in urls:
        assert not url.startswith(("/", "file:")), url
        assert (site / url).exists(), url


def test_lang_rectos_dropcaps_and_toc(site):
    assert '<html lang="es"' in (site / "index.html").read_text(encoding="utf-8")
    html = _all_html(site)
    assert len(re.findall(r'<section [^>]*class="chapter recto">', html)) == 3
    assert re.findall(r'<p class="dropcap">(\w)', html) == ["M", "L", "P"]
    assert '"id": "capítulo-de-la-tormenta"' in (site / "index.html").read_text(encoding="utf-8")


def test_references_are_text(site):
    html = _all_html(site)
    assert '<a class="ref-fig" href="#fig-faro">“El faro de la punta en un día de calma”</a>' in html
    assert '<a class="ref-chap" href="#chap-faro">Chapter 1</a>' in html


def test_css_is_for_a_browser(site):
    css = (site / "book.css").read_text(encoding="utf-8")
    for paged in ("@page", "target-counter", "string-set", "file://"):
        assert paged not in css, paged
    assert "font-size:calc(var(--reader-size)" in css


def test_the_opening_illustration_belongs_to_its_chapter(site):
    html = (site / "chapters/003.html").read_text(encoding="utf-8")
    assert re.search(r'class="chapter recto"><div class="fullpage"><figure class="fullpage">', html)


def test_single_file_format_html(tmp_path):
    from scriptorium.cli import main
    md = tmp_path / "note.md"
    md.write_text("# Hello\n\nA note.\n", encoding="utf-8")
    assert main(["render", str(md), "--format", "html"]) == 0
    assert (tmp_path / "note" / "index.html").is_file()


def test_toc_marks_parts_and_keeps_the_order():
    from scriptorium.book import _chapters
    from scriptorium.parse import parse
    src = ("# Preface {#pre .unnumbered}\n\nx\n\n# North {#p1 .part}\n\n# One {#c1}\n\ny\n\n"
           "# Two {#c2}\n\nz\n\n# South {#p2 .part}\n\n# Three {#c3}\n\nw")
    _, toc = _chapters(parse(src))
    assert [t["id"] for t in toc] == ["pre", "p1", "c1", "c2", "p2", "c3"]
    assert [t.get("part", False) for t in toc] == [False, True, False, False, True, False]


def test_a_book_without_parts_has_no_part_flags(site):
    index = (site / "index.html").read_text(encoding="utf-8")
    book = json.loads(re.search(r"window.BOOK = (\{.*?\});</script>", index, re.S).group(1))
    assert not any("part" in t for t in book["toc"])


def test_toc_part_label_follows_the_last_theme_rule():
    from scriptorium.book import toc_part_css
    css = ('h1.part::before { content: "Part " counter(part, upper-roman); display:block; }\n'
           'h1.part::before { content: "Parte " counter(part, upper-roman); }')
    assert toc_part_css(css) == '#toc-list .toc-part-label::before { content: "Parte " counter(part, upper-roman); }\n'
    assert toc_part_css('h1.part::before { color: red; }') == ""
    assert toc_part_css('h1.part::before { content: none; }') == ""
