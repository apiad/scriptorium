"""Per-document page furniture: `header:` / `footer:` with left/center/right slots."""

import subprocess

import pytest

from scriptorium.galley import render_pdf

# Two pages of body, so "every page" means more than one.
_LONG = "\n\n".join(f"Clause {i}. " + "Words in a clause. " * 40 for i in range(12))


def _pages(pdf) -> list[str]:
    n = int(next(l for l in subprocess.run(["pdfinfo", str(pdf)], capture_output=True,
                                           text=True).stdout.splitlines()
                 if l.startswith("Pages:")).split()[1])
    return [subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), str(pdf), "-"],
                           capture_output=True, text=True).stdout
            for p in range(1, n + 1)]


def _render(tmp_path, front: str, body: str = _LONG, theme: str = "note") -> list[str]:
    out = tmp_path / "f.pdf"
    render_pdf(f"---\ntheme: {theme}\n{front}---\n\n{body}\n", str(out), execute=False)
    return _pages(out)


def test_header_slot_reads_a_frontmatter_key_on_every_page(tmp_path):
    pages = _render(tmp_path, 'contract: "No. 2026-014"\nheader:\n  right: "Contract {contract}"\n')
    assert len(pages) >= 2
    assert all("Contract No. 2026-014" in p for p in pages)


def test_footer_counts_pages_in_any_slot(tmp_path):
    pages = _render(tmp_path, 'footer:\n  center: "Page {page} of {total}"\n')
    n = len(pages)
    assert n >= 2
    assert f"Page 1 of {n}" in pages[0]
    assert f"Page {n} of {n}" in pages[-1]


def test_quotes_in_a_value_do_not_break_the_rule(tmp_path):
    # A double quote ends a CSS string; unescaped, the whole margin box drops.
    pages = _render(tmp_path, "party: 'ACME \"Holdings\" S.A.'\nheader:\n  left: \"{party}\"\n",
                    body="Short.")
    assert 'ACME "Holdings" S.A.' in pages[0]


def test_frontmatter_false_removes_the_theme_default(tmp_path):
    # `formal` ships a page-number footer; a one-page letter can drop it.
    # pdftotext drops the spaces around the slash, so compare without them.
    with_default = _render(tmp_path, "", body="Short.", theme="formal")
    assert "1/1" in "".join(with_default[0].split())
    without = _render(tmp_path, "footer: false\n", body="Short.", theme="formal")
    assert "1/1" not in "".join(without[0].split())


def test_a_non_mapping_is_a_hard_error(tmp_path):
    with pytest.raises(ValueError, match="footer"):
        _render(tmp_path, 'footer: "Page {page}"\n', body="Short.")


def test_full_page_masters_carry_no_furniture(tmp_path):
    # A book's title page is a full-bleed master on a zero-margin @page, so its
    # margin boxes have no room; this guards that it stays that way.
    pages = _render(tmp_path, "title: The Book\nfooter:\n  center: \"FOOTERMARK\"\n",
                    body="::: title\n:::\n\n# One\n\nBody.", theme="book")
    assert "FOOTERMARK" not in pages[0]
    assert "FOOTERMARK" in pages[-1]


def test_a_project_sets_header_and_footer_in_its_yaml(tmp_path):
    # A contract with its annexes is a multi-file project, and the files'
    # frontmatter is stripped, so the yaml is the only place the keys can come from.
    (tmp_path / "body.md").write_text("# Agreement\n\nText.\n", encoding="utf-8")
    (tmp_path / "annex.md").write_text("# Annex A\n\nMore.\n", encoding="utf-8")
    (tmp_path / "scriptorium.yaml").write_text(
        "theme: formal\nvars:\n  contract: X-7\nheader:\n  right: \"Contract {contract}\"\n"
        "footer: false\nfiles:\n  - body.md\n  - annex.md\n", encoding="utf-8")

    from scriptorium.project import load
    proj = load(tmp_path / "scriptorium.yaml")
    out = tmp_path / "p.pdf"
    render_pdf(proj.src, str(out), theme_name=proj.theme, cwd=str(tmp_path),
               execute=False, vars=proj.vars, project_meta=proj.meta)
    pages = _pages(out)
    assert len(pages) == 2
    assert all("Contract X-7" in p for p in pages)
    assert all("1/2" not in "".join(p.split()) and "2/2" not in "".join(p.split())
               for p in pages)
