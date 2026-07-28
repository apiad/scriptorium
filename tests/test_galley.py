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
