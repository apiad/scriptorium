"""Numbered citations: span parsing, numbering, nocite, emission."""

from scriptorium.citations import _normalise, number_citations

BIB = {
    "parnas": "Parnas, D. L. *On the Criteria…* CACM 15(12), 1972.",
    "vogel": "Vogel, E. F. *Deng Xiaoping…*. Belknap, 2011.",
}

NAMED = {
    "tam": {"author": "Tam et al.", "text": "Tam, Z. R., … *Let Me Speak Freely?*"},
    "fan": {"author": "Fan", "text": "Fan, H. *Capacity, Not Format*."},
    "plain": "Somebody. *A work with no declared author*.",
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
    assert "Parnas, D. L." in out and '<a class="cite-back" href="#citeref-1-1">' in out
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

    assert 'href="#citeref-1-1"' in out and 'href="#citeref-1-2"' in out


def test_back_links_are_one_arrow_and_a_list_of_page_anchors():
    # The page numbers themselves come from CSS target-counter at render time,
    # so the anchors are deliberately empty here. One arrow, not one per site:
    # three identical arrows told the reader nothing.
    out, _ = process_citations("A[@parnas] again[@parnas] thrice[@parnas]\n", META)

    assert out.count("↩") == 1
    assert out.count('class="cite-back"') == 3
    assert '<a class="cite-back" href="#citeref-1-1"></a>, ' \
           '<a class="cite-back" href="#citeref-1-2"></a>' in out


def test_an_uncited_nocite_entry_has_no_back_link_apparatus():
    meta = {"bibliography": BIB, "nocite": ["vogel"]}
    out, _ = process_citations("Only one.[@parnas]\n", meta)

    vogel_line = [ln for ln in out.split("\n") if "Vogel" in ln][0]
    assert "↩" not in vogel_line and "cite-back" not in vogel_line


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


def test_normalise_reads_a_prose_string_as_text_with_no_author():
    sources, warnings = _normalise({"parnas": "Parnas, D. L. *On the Criteria…*"})

    assert sources["parnas"].text == "Parnas, D. L. *On the Criteria…*"
    assert sources["parnas"].author is None and warnings == []


def test_normalise_reads_a_mapping_entry():
    sources, warnings = _normalise(
        {"tam": {"author": "Tam et al.", "text": "Tam, Z. R., … *Let Me Speak Freely?*"}}
    )

    assert sources["tam"].author == "Tam et al."
    assert sources["tam"].text == "Tam, Z. R., … *Let Me Speak Freely?*"
    assert warnings == []


def test_normalise_drops_a_mapping_with_no_text_and_warns():
    sources, warnings = _normalise({"ghost": {"author": "Nobody"}})

    assert "ghost" not in sources
    assert any("ghost" in w and "text" in w for w in warnings)


def test_normalise_rejects_a_value_that_is_neither_prose_nor_mapping():
    sources, warnings = _normalise({"odd": 42})

    assert "odd" not in sources and any("odd" in w for w in warnings)


def test_narrative_citation_puts_the_name_before_the_mark():
    out, entries, warnings = number_citations("[+@tam] found that X.\n", NAMED)

    assert out.startswith('<span class="cite-author">Tam et al.</span> ')
    assert '<a id="citeref-1-1" href="#cite-1">1</a>' in out
    assert [e.key for e in entries] == ["tam"] and warnings == []


def test_narrative_citation_numbers_like_a_plain_one():
    out, entries, _ = number_citations("[+@tam] said it, and again[@tam].\n", NAMED)

    assert len(entries) == 1 and entries[0].refs == 2
    assert out.count(">1</a>") == 2


def test_narrative_citation_on_an_entry_with_no_author_stays_literal_and_warns():
    out, entries, warnings = number_citations("[+@plain] argued.\n", NAMED)

    assert "[+@plain]" in out and "cite-author" not in out
    assert entries == []
    assert any("plain" in w and "author" in w for w in warnings)


def test_narrative_sigil_inside_a_code_fence_is_left_alone():
    src = "Prose.\n\n```markdown\nSee [+@tam] here.\n```\n"
    out, entries, _ = number_citations(src, NAMED)

    assert "[+@tam]" in out and entries == []


def test_author_only_emits_the_name_and_no_mark():
    out, entries, _ = number_citations(
        "[-@tam]'s framework applies.[@tam]\n", NAMED
    )

    assert '<span class="cite-author">Tam et al.</span>\'s framework' in out
    assert out.count("cite-ref") == 1        # only the real citation numbered
    assert len(entries) == 1 and entries[0].refs == 1


def test_author_only_alone_creates_no_entry_and_warns():
    out, entries, warnings = number_citations("[-@tam] is well known.\n", NAMED)

    assert '<span class="cite-author">Tam et al.</span>' in out
    assert entries == []
    assert any("tam" in w and "never cited" in w for w in warnings)


def test_author_only_is_quiet_when_the_work_is_in_nocite():
    _, entries, warnings = number_citations(
        "[-@tam] is well known.\n", NAMED, nocite=["tam"]
    )

    assert entries == [] and warnings == []


def test_author_only_on_an_entry_with_no_author_stays_literal_and_warns():
    out, _, warnings = number_citations("[-@plain] argued.\n", NAMED)

    assert "[-@plain]" in out and "cite-author" not in out
    assert any("plain" in w and "author" in w for w in warnings)


def test_a_sigil_on_a_multi_key_span_stays_literal_and_warns():
    out, entries, warnings = number_citations("[+@tam; @fan] agree.\n", NAMED)

    assert "[+@tam; @fan]" in out          # not half-rewritten
    assert entries == [] and "cite-author" not in out
    assert any("one key" in w for w in warnings)


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


def test_string_entries_render_exactly_as_before():
    # The whole feature is an addition to a shipped format: a document that
    # uses none of it must produce the identical pre-processor output. Asserted
    # on the rewritten source, not on PDF bytes — a PDF carries timestamps and
    # font subset ids, so a byte-compare there fails for unrelated reasons.
    src = "A claim.[@parnas] Another.[@vogel] And again.[@parnas]\n"
    out, entries, warnings = number_citations(src, BIB)

    assert out == (
        'A claim.<span class="cite-ref">'
        '[<a id="citeref-1-1" href="#cite-1">1</a>]</span> '
        'Another.<span class="cite-ref">'
        '[<a id="citeref-2-1" href="#cite-2">2</a>]</span> '
        'And again.<span class="cite-ref">'
        '[<a id="citeref-1-2" href="#cite-1">1</a>]</span>\n'
    )
    assert [(e.key, e.number, e.refs) for e in entries] == [
        ("parnas", 1, 2), ("vogel", 2, 1),   # parnas cited twice, vogel once
    ]
    assert warnings == []


def test_narrative_name_reaches_the_pdf_and_no_sigil_syntax_leaks(tmp_path):
    src = ("---\ntheme: article\ntitle: T\n"
           "bibliography:\n  tam:\n    author: Tam et al.\n"
           "    text: \"Tam, Z. R. Let Me Speak Freely. 2024.\"\n"
           "---\n\n# H\n\n[+@tam] found it, and [-@tam] refined it.\n")
    out = tmp_path / "narr.pdf"
    report = render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert text.count("Tam et al.") == 2      # once per narrative form
    assert "Tam, Z. R." in text               # the entry itself
    assert "[1]" in text                      # the + form still marks
    assert "[+@" not in text and "[-@" not in text
    assert "cite-author" not in text          # the span never leaks as text
    assert report.warnings == []


def test_project_level_mapping_bibliography_reaches_the_render(tmp_path):
    # project.py:49 passes `bibliography` through verbatim, so mapping entries
    # should already work. "No change needed" is a claim, so it gets a test.
    from scriptorium.project import load

    (tmp_path / "a.md").write_text("# One\n\n[+@tam] found it.\n")
    (tmp_path / "scriptorium.yaml").write_text(
        "theme: book\n"
        "bibliography:\n  tam:\n    author: Tam et al.\n"
        "    text: \"Tam, Z. R. Let Me Speak Freely. 2024.\"\n"
        "files: [a.md]\n")
    proj = load(tmp_path / "scriptorium.yaml")

    assert proj.meta["bibliography"]["tam"]["author"] == "Tam et al."
    assert "bibliography" not in proj.vars   # content, not appearance

    out = tmp_path / "b.pdf"
    render_pdf(proj.src, str(out), theme_name=proj.theme, execute=False,
               vars=proj.vars, project_meta=proj.meta)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "Tam et al." in text and "Tam, Z. R." in text


def test_back_links_resolve_to_the_real_page_number(tmp_path):
    # Asserting on the HTML would pass even if target-counter were silently
    # dropped, so this checks the PDF. Two pages, with the only citation on the
    # second, so a resolved number cannot be confused with a constant "1".
    src = ("---\ntheme: article\ntitle: T\n"
           "bibliography:\n  parnas: \"Parnas, D. L. On the Criteria. CACM, 1972.\"\n"
           "---\n\n# H\n\nOpening page.\n\n::: newpage\n:::\n\n"
           "A claim on the second page.[@parnas]\n")
    out = tmp_path / "back.pdf"
    render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "↩ 2" in text, f"back-link page not resolved; got: {text[-200:]!r}"
    assert text.count("↩") == 1


# --- the references label -------------------------------------------------

from scriptorium.theme import render_template


def test_template_resolves_a_hyphenated_hole_and_section():
    # Theme vars are kebab-case by convention (accent-dark, body-font), so the
    # template engine has to accept a hyphen or no var can reach a template.
    tpl = "{{#references-label}}<h2>{{references-label}}</h2>{{/references-label}}!"

    assert render_template(tpl, {"references-label": "References"}) == "<h2>References</h2>!"
    assert render_template(tpl, {}) == "!"


def test_references_section_has_no_heading_without_the_label(tmp_path):
    src = ("---\ntheme: article\ntitle: T\n"
           "bibliography:\n  parnas: \"Parnas, D. L. On the Criteria. CACM, 1972.\"\n"
           "---\n\n# H\n\nA claim.[@parnas]\n")
    out = tmp_path / "nolabel.pdf"
    render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "Parnas, D. L." in text
    assert "References" not in text and "REFERENCES" not in text


def test_references_label_becomes_the_section_heading(tmp_path):
    src = ("---\ntheme: article\ntitle: T\nreferences-label: Bibliografía\n"
           "bibliography:\n  parnas: \"Parnas, D. L. On the Criteria. CACM, 1972.\"\n"
           "---\n\n# H\n\nA claim.[@parnas]\n")
    out = tmp_path / "label.pdf"
    render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "Bibliografía" in text          # the label the author chose, not a baked-in string
    assert "Parnas, D. L." in text
