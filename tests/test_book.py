"""Running-heads + auto-TOC + project assembly (the book layer)."""

import re

from scriptorium.parse import parse, fill_toc
from scriptorium.project import load


def _hrefs(units):
    return [re.search(r'href="([^"]+)"', u.html).group(1) for u in units if u.name == "toc-entry"]


def test_heading_gets_autoslug_id():
    (u,) = parse("## The Linear Scan")
    assert u.heading_id == "the-linear-scan" and u.heading_level == 2


def test_explicit_heading_id_wins():
    (u,) = parse("# Trees {#chap-trees}")
    assert u.heading_id == "chap-trees" and u.heading_level == 1


def test_fill_toc_lists_headings_with_ids():
    src = "::: toc\n:::\n\n# Ch One {#chap-one}\n\n## Sec A\n\n# Ch Two {#chap-two}"
    hrefs = _hrefs(fill_toc(parse(src)))
    assert hrefs == ["#chap-one", "#sec-a", "#chap-two"]


def test_toc_depth_limits_levels():
    src = "::: toc\n:::\n\n# A {#a}\n\n### Deep {#deep}"
    hrefs = _hrefs(fill_toc(parse(src), depth=1))
    assert "#a" in hrefs and not any("deep" in h for h in hrefs)


def test_project_concatenates_and_substitutes_vars(tmp_path):
    (tmp_path / "a.md").write_text("# {{title}}\n\nbody one")
    (tmp_path / "b.md").write_text("# second")
    (tmp_path / "scriptorium.yaml").write_text(
        "theme: book\nvars: {title: Hello}\nfiles: [a.md, b.md]")
    p = load(tmp_path / "scriptorium.yaml")
    assert p.theme == "book"
    assert "# Hello" in p.src  # var substituted
    assert "\\newpage" in p.src  # files separated by a page break
    assert "# second" in p.src
