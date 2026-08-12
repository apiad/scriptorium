"""VS1 acceptance: parsing granularity, keep-together packing, real PDF render."""

from pathlib import Path

from scriptorium.galley import CONTENT_H, emit, pack, render_pdf
from scriptorium.model import Unit
from scriptorium.parse import parse


def test_keep_fuses_blocks_into_one_unit():
    two_blocks = "![img](x.png)\n\n**Figure 1.** caption."
    prose = parse(two_blocks)
    kept = parse(f"::: keep\n{two_blocks}\n:::")

    assert len(prose) == 2 and all(not u.keep_together for u in prose)
    assert len(kept) == 1 and kept[0].keep_together


def test_keep_unit_moves_wholesale_when_it_does_not_fit():
    # Fill most of a page, then a tall keep unit that cannot fit in the remainder.
    filler = Unit(html="<p>x</p>", height_mm=CONTENT_H - 30)
    keep = Unit(html='<div class="keep">big</div>', keep_together=True, height_mm=60)
    pages, report = pack([filler, keep])

    assert report.page_of == [0, 1]  # keep pushed to a fresh page
    assert pages[1][0] is keep and len(pages[1]) == 1


def test_newpage_forces_a_break():
    a = Unit(html="<p>a</p>", height_mm=20)
    brk = Unit(is_break=True)
    b = Unit(html="<p>b</p>", height_mm=20)
    pages, report = pack([a, brk, b])

    assert report.n_pages == 2
    assert report.page_of == [0, 1]


def test_oversized_unit_is_flagged_not_clipped():
    huge = Unit(html="<p>huge</p>", keep_together=True, height_mm=CONTENT_H + 100, name="giant")
    pages, report = pack([huge])

    assert report.oversized and "giant" in report.oversized[0]
    assert huge in pages[0]  # overflowed, still emitted


def test_finding_renders_template():
    (unit,) = parse('::: finding amber {icon=A title="Risk"}\nbody text\n:::')
    assert 'class="finding amber"' in unit.html and unit.keep_together
    assert ">A<" in unit.html and "Risk" in unit.html and "body text" in unit.html


def test_cover_is_full_page_master():
    (unit,) = parse('::: cover {title="Acme"}\nA market brief.\n:::')
    assert unit.full_page and unit.master == "cover"
    assert "Acme" in unit.html


def test_nested_grid_renders_children():
    src = '::: kpi-dash three\n::: kpi amber {label=TAM value=$4.2M sub=2027}\n:::\n:::'
    (unit,) = parse(src)
    assert 'class="kpi-dash three"' in unit.html
    assert 'class="kpi amber"' in unit.html and "$4.2M" in unit.html


def test_render_pdf_produces_pages(tmp_path):
    src = Path("examples/report.md").read_text(encoding="utf-8")
    out = tmp_path / "report.pdf"
    report = render_pdf(src, str(out), base_url="examples/")

    assert out.exists() and out.stat().st_size > 1000
    assert report.n_pages >= 2
    assert report.oversized == []


def test_heading_not_orphaned_at_page_foot():
    filler = Unit(html="<p>x</p>", height_mm=CONTENT_H - 10)
    head = Unit(html="<h2>H</h2>", heading="H", height_mm=8)
    body = Unit(html="<p>b</p>", height_mm=30)
    pages, report = pack([filler, head, body])
    assert pages[1][0] is head  # heading pushed to page 2 with its content, not stranded


def test_long_code_splits_across_pages():
    filler = Unit(html="<p>x</p>", height_mm=CONTENT_H - 40)
    lines = "\n".join(f"line{i}" for i in range(40))
    code = Unit(html="<pre/>", name="code", splittable=True, code_src=lines,
                code_lang="python", height_mm=200)
    pages, report = pack([filler, code])
    assert report.n_pages >= 2
    assert any(u.name == "code" for u in pages[0])  # part 1 fills the gap
    assert any(u.name == "code" for u in pages[1])  # part 2 continues


def test_tall_table_splits_by_rows_repeating_header():
    rows = "".join(f"<tr><td>{i}</td></tr>" for i in range(40))
    html = f"<table><thead><tr><th>H</th></tr></thead><tbody>{rows}</tbody></table>"
    tall = Unit(html=html, name="prose", height_mm=CONTENT_H + 90)  # taller than a page
    pages, report = pack([tall])
    frags = [u for p in pages for u in p if "<table" in u.html]
    assert report.n_pages >= 2 and len(frags) >= 2
    assert all("<thead>" in u.html for u in frags)  # header repeated on each fragment


def test_deck_groups_slides_by_headings():
    from scriptorium.galley import _group_slides
    us = [Unit(html="<h1>Part</h1>", heading="Part", heading_level=1),
          Unit(html="<h2>A</h2>", heading="A", heading_level=2),
          Unit(html="<p>a</p>"),
          Unit(html="<h2>B</h2>", heading="B", heading_level=2),
          Unit(html="<p>b</p>"),
          Unit(is_break=True),
          Unit(html="<p>c</p>")]
    slides = _group_slides(us, has_title=True)
    assert [m for m, _ in slides] == ["title", "section", "content", "content", "content"]
    assert len(slides[3][1]) == 2  # slide "B": the h2 + its paragraph


def test_frontmatter_theme_is_honoured_and_explicit_wins():
    from scriptorium.galley import DEFAULT_THEME, resolve_theme_name
    deck_doc = "---\ntheme: deck\ntitle: T\n---\n\n# S\n"

    assert resolve_theme_name(deck_doc) == "deck"           # frontmatter beats the default
    assert resolve_theme_name(deck_doc, "book") == "book"   # --theme beats frontmatter
    assert resolve_theme_name("# no frontmatter\n") == DEFAULT_THEME


def test_render_pdf_uses_the_theme_named_in_frontmatter(tmp_path):
    # Reachability: examples/deck.md declares `theme: deck`, so rendering it with
    # no explicit theme must produce 16:9 slides, not A4 pages of the default theme.
    src = Path("examples/deck.md").read_text(encoding="utf-8")
    declared = render_pdf(src, str(tmp_path / "declared.pdf"), base_url="examples/",
                          execute=False)
    overridden = render_pdf(src, str(tmp_path / "overridden.pdf"), base_url="examples/",
                            theme_name="report", execute=False)

    assert declared.n_pages == 12  # the deck path emits one page per slide
    assert overridden.n_pages != declared.n_pages  # --theme really did override


def test_refs_only_match_known_prefixes():
    from scriptorium.parse import _rewrite_refs

    # known prefixes still resolve
    assert 'href="#fig-plot"' in _rewrite_refs("see @fig-plot")
    assert 'href="#chap-two"' in _rewrite_refs("see @chap-two")

    # bibtex keys and handles survive as literal text
    for s in ["@smith-2020", "@piad-morffis-2024", "@colinhacks-x"]:
        assert _rewrite_refs(f"cite {s}") == f"cite {s}"

    # the regression that motivated this: prose was silently deleted
    out = _rewrite_refs("See @sec-intro and mail me @piad-morffis-2024.")
    assert "mail me @piad-morffis-2024." in out


# --- a project's own stylesheet -------------------------------------------

def test_project_css_changes_the_rendered_geometry(tmp_path):
    # A book needs its own stylesheet without authoring a theme: load_theme
    # resolves only from scriptorium/themes, so `css:` is the only route in.
    # Asserting the PDF merely exists would pass with the feature ripped out, so
    # this asserts a rule that visibly changes the output: a much larger body
    # font has to spill the same prose onto more pages.
    body = "# H\n\n" + ("Prose that fills the page. " * 60 + "\n\n") * 3
    (tmp_path / "ch.md").write_text(body, encoding="utf-8")
    (tmp_path / "big.css").write_text("body { font-size: 34pt; }\n", encoding="utf-8")

    plain = "---\ntheme: article\ntitle: T\n---\n\n" + body
    styled = "---\ntheme: article\ntitle: T\ncss: big.css\n---\n\n" + body

    before = render_pdf(plain, str(tmp_path / "a.pdf"), cwd=str(tmp_path), execute=False)
    after = render_pdf(styled, str(tmp_path / "b.pdf"), cwd=str(tmp_path), execute=False)

    assert after.n_pages > before.n_pages
    assert after.warnings == []


def test_project_file_accepts_css(tmp_path):
    (tmp_path / "book.css").write_text("body { color: #b91c1c; }\n", encoding="utf-8")
    (tmp_path / "ch.md").write_text("# H\n\nBody.\n", encoding="utf-8")
    (tmp_path / "scriptorium.yaml").write_text(
        "theme: article\ncss: book.css\nvars:\n  title: T\nfiles:\n  - ch.md\n",
        encoding="utf-8")

    from scriptorium.cli import main
    assert main(["render", str(tmp_path / "scriptorium.yaml")]) == 0
    assert (tmp_path / "book.pdf").exists()


def test_missing_css_file_warns_rather_than_raising(tmp_path):
    src = "---\ntheme: article\ntitle: T\ncss: nope.css\n---\n\n# H\n\nBody.\n"
    out = tmp_path / "c.pdf"
    report = render_pdf(src, str(out), cwd=str(tmp_path), execute=False)

    assert out.exists()
    assert any("nope.css" in w for w in report.warnings)
