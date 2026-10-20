"""Install and offline: manifest, icons, a service worker versioned by content."""

import json
import re

from conftest import build_example


def _assets(site):
    return set(json.loads(re.search(r"const ASSETS = (\[.*?\]);", (site / "sw.js").read_text(), re.S).group(1)))


def _version(site):
    return re.search(r"const VERSION = '([0-9a-f]{12})';", (site / "sw.js").read_text()).group(1)


def _tree(site):
    return {p.relative_to(site).as_posix(): p.read_bytes() for p in sorted(site.rglob("*")) if p.is_file()}


def test_sw_lists_exactly_the_site(site):
    files = {p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file() and p.name != "sw.js"}
    assert _assets(site) == files | {"./"}


def test_two_builds_are_identical_and_a_word_changes_the_version(tmp_path):
    a, b = build_example(tmp_path / "a"), build_example(tmp_path / "b")
    assert _tree(a) == _tree(b)
    c = build_example(tmp_path / "c", replace=("cerillas", "fósforos"))
    assert _version(c) != _version(a)


def test_manifest_fields(site):
    m = json.loads((site / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert m["name"] == "El faro de la punta" and m["lang"] == "es"
    assert m["start_url"] == "./" and m["scope"] == "./" and m["display"] == "standalone"
    assert {i["sizes"] for i in m["icons"]} >= {"192x192", "512x512"}
    assert any(i.get("purpose") == "maskable" for i in m["icons"])
    for i in m["icons"]:
        assert (site / i["src"]).is_file()


def test_index_links_the_manifest_and_icons(site):
    html = (site / "index.html").read_text(encoding="utf-8")
    assert '<link rel="manifest" href="manifest.webmanifest">' in html
    assert 'rel="apple-touch-icon"' in html and 'rel="icon"' in html


def test_book_without_cover_or_images_builds(tmp_path):
    from scriptorium.cli import main
    (tmp_path / "a.md").write_text("# Uno\n\nTexto.\n", encoding="utf-8")
    (tmp_path / "scriptorium.yaml").write_text(
        "theme: book\nvars: {title: Mitos}\nfiles: [a.md]\noutputs:\n  web: {format: html}\n", encoding="utf-8")
    assert main(["render", str(tmp_path / "scriptorium.yaml")]) == 0
    from PIL import Image
    with Image.open(tmp_path / "web/icons/icon-512.png") as im:
        assert im.size == (512, 512)
