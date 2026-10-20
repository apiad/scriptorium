"""The HTML book's directory: what the example book builds to."""

import re
from pathlib import Path


def _local_urls(site: Path):
    html = (site / "index.html").read_text(encoding="utf-8")
    css = (site / "book.css").read_text(encoding="utf-8")
    urls = re.findall(r'(?:src|href)="([^"#][^"]*)"', html)
    urls += re.findall(r"url\(\s*['\"]?([^)'\"]+)", css)
    return [u for u in urls if not u.startswith(("http:", "https:", "data:"))]


def test_site_has_the_reader_files(site):
    for f in ("index.html", "book.css", "reader.js"):
        assert (site / f).is_file()


def test_every_img_has_dimensions(site):
    html = (site / "index.html").read_text(encoding="utf-8")
    assert re.findall(r"<img(?![^>]*\bwidth=)[^>]*>", html) == []
    assert len(re.findall(r"<img\b", html)) == 3


def test_every_local_url_is_relative_and_exists(site):
    urls = _local_urls(site)
    assert urls
    for url in urls:
        assert not url.startswith(("/", "file:")), url
        assert (site / url).exists(), url


def test_lang_rectos_dropcaps_and_toc(site):
    html = (site / "index.html").read_text(encoding="utf-8")
    assert '<html lang="es"' in html
    assert html.count('<section class="chapter recto">') == 3
    assert re.findall(r'<p class="dropcap">(\w)', html) == ["M", "L", "P"]
    assert '"id": "capítulo-de-la-tormenta"' in html


def test_references_are_text(site):
    html = (site / "index.html").read_text(encoding="utf-8")
    assert '<a class="ref-fig" href="#fig-faro">“El faro de la punta en un día de calma”</a>' in html
    assert '<a class="ref-chap" href="#chap-faro">Chapter 1</a>' in html


def test_css_is_for_a_browser(site):
    css = (site / "book.css").read_text(encoding="utf-8")
    for paged in ("@page", "target-counter", "string-set", "file://"):
        assert paged not in css, paged
    assert "font-size:calc(var(--reader-size)" in css


def test_the_opening_illustration_belongs_to_its_chapter(site):
    html = (site / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<section class="chapter recto"><div class="fullpage"><figure class="fullpage">', html)


def test_single_file_format_html(tmp_path):
    from scriptorium.cli import main
    md = tmp_path / "note.md"
    md.write_text("# Hello\n\nA note.\n", encoding="utf-8")
    assert main(["render", str(md), "--format", "html"]) == 0
    assert (tmp_path / "note" / "index.html").is_file()
