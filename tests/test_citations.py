"""Numbered citations: span parsing, numbering, nocite, emission."""

from scriptorium.citations import number_citations

BIB = {
    "parnas": "Parnas, D. L. *On the Criteria…* CACM 15(12), 1972.",
    "vogel": "Vogel, E. F. *Deng Xiaoping…*. Belknap, 2011.",
}


def test_single_citation_becomes_a_bracketed_number():
    out, entries, warnings = number_citations("A claim.[@parnas]\n", BIB)

    assert '<span class="cite-ref">[' in out
    assert '<a id="citeref-1-1" href="#cite-1">1</a>' in out
    assert [e.key for e in entries] == ["parnas"]
    assert entries[0].refs == 1 and warnings == []


def test_multi_key_span_renders_one_bracket_pair():
    out, entries, _ = number_citations("Both.[@parnas; @vogel]\n", BIB)

    assert '<a id="citeref-1-1" href="#cite-1">1</a>, ' \
           '<a id="citeref-2-1" href="#cite-2">2</a>]' in out
    assert out.count('<span class="cite-ref">') == 1
    assert [e.number for e in entries] == [1, 2]


def test_numbering_follows_first_appearance():
    out, entries, _ = number_citations("B[@vogel] then A[@parnas]\n", BIB)

    assert [(e.key, e.number) for e in entries] == [("vogel", 1), ("parnas", 2)]


def test_repeated_key_keeps_one_number_and_counts_call_sites():
    out, entries, _ = number_citations("A[@parnas] and again[@parnas]\n", BIB)

    assert len(entries) == 1 and entries[0].refs == 2
    assert 'id="citeref-1-1"' in out and 'id="citeref-1-2"' in out
    assert out.count(">1</a>") == 2


def test_unknown_key_leaves_the_whole_span_literal_and_warns():
    out, entries, warnings = number_citations("A[@nope] and B[@parnas; @gone]\n", BIB)

    assert "[@nope]" in out
    assert "[@parnas; @gone]" in out          # not half-rewritten
    assert entries == []                      # parnas was never really cited
    assert any("nope" in w for w in warnings) and any("gone" in w for w in warnings)


def test_citation_inside_a_code_fence_is_left_alone():
    src = "Prose.\n\n```markdown\nSee [@parnas] here.\n```\n"
    out, entries, _ = number_citations(src, BIB)

    assert "[@parnas]" in out and entries == []


def test_page_locator_is_not_a_citation():
    out, entries, _ = number_citations("A[@parnas, p. 42]\n", BIB)

    assert "[@parnas, p. 42]" in out and entries == []


def test_bare_at_key_is_not_a_citation():
    out, entries, _ = number_citations("Mail @parnas about it.\n", BIB)

    assert "@parnas" in out and "cite-ref" not in out and entries == []


import pytest

from scriptorium.citations import process_citations

META = {"bibliography": BIB}


def test_document_gets_one_references_component_at_the_end():
    out, warnings = process_citations("A claim.[@parnas]\n", META)

    assert out.count("::: references") == 1
    assert out.index("::: references") > out.index("A claim.")
    assert '<span id="cite-1"></span>' in out
    assert "Parnas, D. L." in out and "[↩](#citeref-1-1)" in out
    assert warnings == []


def test_uncited_entry_is_omitted():
    out, _ = process_citations("Only one.[@parnas]\n", META)

    assert "Parnas" in out and "Vogel" not in out


def test_nocite_adds_an_entry_without_a_citation():
    meta = {"bibliography": BIB, "nocite": ["vogel"]}
    out, _ = process_citations("Only one.[@parnas]\n", meta)

    assert "Parnas" in out and "Vogel" in out
    assert out.index("Parnas") < out.index("Vogel")   # cited first, then nocite


def test_nocite_key_with_no_entry_warns():
    meta = {"bibliography": BIB, "nocite": ["ghost"]}
    _, warnings = process_citations("A[@parnas]\n", meta)

    assert any("ghost" in w for w in warnings)


def test_repeated_citation_gets_a_back_link_each():
    out, _ = process_citations("A[@parnas] again[@parnas]\n", META)

    assert "[↩](#citeref-1-1)" in out and "[↩](#citeref-1-2)" in out


def test_entry_body_keeps_its_markdown():
    meta = {"bibliography": {"x": "See **this** and [that](https://x.dev)."}}
    out, _ = process_citations("A[@x]\n", meta)

    assert "**this**" in out and "[that](https://x.dev)" in out


def test_no_citations_emits_no_section():
    out, warnings = process_citations("Plain prose.\n", META)

    assert "::: references" not in out and warnings == []


def test_author_placed_block_is_filled_in_place():
    src = "A[@parnas]\n\n::: references\n:::\n\n## Appendix\n\nTail.\n"
    out, _ = process_citations(src, META)

    assert out.count("::: references") == 1
    assert out.index("Parnas") < out.index("## Appendix")   # not appended at the end


def test_two_reference_blocks_is_an_error():
    src = "A[@parnas]\n\n::: references\n:::\n\n::: references\n:::\n"
    with pytest.raises(ValueError, match="references"):
        process_citations(src, META)


def test_frontmatter_is_held_aside():
    src = "---\ntitle: T\n---\n\nA[@parnas]\n"
    out, _ = process_citations(src, META)

    assert out.startswith("---\ntitle: T\n---\n")
    assert out.count("::: references") == 1


from scriptorium.galley import render_pdf


def test_citation_text_reaches_the_pdf_and_no_syntax_leaks(tmp_path):
    src = ("---\ntheme: article\ntitle: T\n"
           "bibliography:\n  parnas: \"Parnas, D. L. On the Criteria. CACM, 1972.\"\n"
           "---\n\n# H\n\nA claim.[@parnas]\n")
    out = tmp_path / "c.pdf"
    report = render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "Parnas, D. L." in text
    assert "[@parnas]" not in text
    assert "[1]" in text            # bracketed, not a bare superscript
    assert report.warnings == []


def test_footnotes_and_citations_coexist_with_separate_counters(tmp_path):
    src = ("---\ntheme: article\ntitle: T\n"
           "bibliography:\n  vogel: \"Vogel, E. F. Deng Xiaoping. Belknap, 2011.\"\n"
           "---\n\n# H\n\nA claim[^n] and a source.[@vogel]\n\n"
           "[^n]: An explanatory note.\n")
    out = tmp_path / "both.pdf"
    render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "An explanatory note." in text and "Vogel, E. F." in text
    # both are number 1 of their own sequence
    assert "[1]" in text


def test_project_level_bibliography_reaches_the_render(tmp_path):
    from scriptorium.project import load

    (tmp_path / "a.md").write_text("# One\n\nA claim.[@parnas]\n")
    (tmp_path / "scriptorium.yaml").write_text(
        "theme: book\n"
        "bibliography:\n  parnas: \"Parnas, D. L. On the Criteria. CACM, 1972.\"\n"
        "files: [a.md]\n")
    proj = load(tmp_path / "scriptorium.yaml")

    assert proj.meta["bibliography"]["parnas"].startswith("Parnas")
    assert "bibliography" not in proj.vars   # content, not appearance

    out = tmp_path / "b.pdf"
    render_pdf(proj.src, str(out), theme_name=proj.theme, execute=False,
               vars=proj.vars, project_meta=proj.meta)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "Parnas, D. L." in text and "[@parnas]" not in text
