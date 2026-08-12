"""Footnote pre-processing: definitions, markers, numbering, emission."""

from scriptorium.footnotes import collect_notes


def test_collects_definitions_and_strips_them():
    src = "A claim.[^a]\n\n[^a]: The note body.\n\nMore prose.\n"
    out, notes = collect_notes(src)

    assert list(notes) == ["a"]
    assert notes["a"].body == "The note body."
    assert "[^a]: The note body." not in out
    assert "A claim.[^a]" in out and "More prose." in out


def test_definition_captures_wrapped_continuation_lines():
    src = "X[^long]\n\n[^long]: First line\n    second line, indented.\n\nAfter.\n"
    out, notes = collect_notes(src)

    assert notes["long"].body == "First line second line, indented."
    assert "After." in out
    assert "second line" not in out


def test_definition_inside_a_code_fence_is_left_alone():
    src = "Prose.\n\n```markdown\n[^a]: not a real definition\n```\n"
    out, notes = collect_notes(src)

    assert notes == {}
    assert "[^a]: not a real definition" in out


from scriptorium.footnotes import number_and_mark


def test_markers_become_numbered_superscripts():
    src, notes = collect_notes("A[^a] then B[^b]\n\n[^a]: one\n\n[^b]: two\n")
    out, groups = number_and_mark(src, notes, chapter_mode=False)

    assert 'class="footnote-ref" id="fnref-1-1"' in out
    assert 'href="#fn-1-1"' in out and ">1</a>" in out
    assert 'href="#fn-1-2"' in out and ">2</a>" in out
    assert len(groups) == 1 and [n.key for n in groups[0]] == ["a", "b"]


def test_numbering_restarts_in_each_chapter():
    src, notes = collect_notes(
        "# One\n\nA[^a]\n\n# Two\n\nB[^b]\n\n[^a]: one\n\n[^b]: two\n"
    )
    out, groups = number_and_mark(src, notes, chapter_mode=True)

    assert [[n.key for n in g] for g in groups] == [["a"], ["b"]]
    # both are note 1 of their own chapter, but ids stay unique
    assert 'id="fnref-1-1"' in out and 'id="fnref-2-1"' in out
    assert out.count(">1</a>") == 2


def test_repeated_reference_gets_a_back_link_each():
    src, notes = collect_notes("A[^a] and again[^a]\n\n[^a]: one\n")
    out, groups = number_and_mark(src, notes, chapter_mode=False)

    assert notes["a"].refs == [1, 2]
    assert 'id="fnref-1-1a"' in out and 'id="fnref-1-1b"' in out
    assert out.count(">1</a>") == 2  # same number, two call sites


def test_marker_without_a_definition_is_left_literal():
    src, notes = collect_notes("A claim.[^missing]\n")
    out, _ = number_and_mark(src, notes, chapter_mode=False)

    assert "[^missing]" in out
    assert "footnote-ref" not in out


import pytest

from scriptorium.footnotes import process_footnotes, resolve_footnote_mode


def test_mode_precedence_frontmatter_over_theme_over_default():
    assert resolve_footnote_mode({}, {}) == "document"
    assert resolve_footnote_mode({}, {"footnotes": "chapter"}) == "chapter"
    assert resolve_footnote_mode({"footnotes": "page"}, {"footnotes": "chapter"}) == "page"


def test_unknown_mode_raises():
    with pytest.raises(ValueError, match="footnotes"):
        resolve_footnote_mode({"footnotes": "endnote"}, {})


def test_document_mode_emits_one_component_at_the_end():
    out, _ = process_footnotes("A[^a]\n\n[^a]: The note.\n", mode="document")

    assert out.count("::: footnotes") == 1
    assert out.index("::: footnotes") > out.index("A<sup")
    assert '<span id="fn-1-1"></span>' in out
    assert "The note." in out and "[↩](#fnref-1-1)" in out


def test_chapter_mode_emits_a_component_per_chapter():
    src = "# One\n\nA[^a]\n\n# Two\n\nB[^b]\n\n[^a]: one\n\n[^b]: two\n"
    out, _ = process_footnotes(src, mode="chapter")

    assert out.count("::: footnotes") == 2
    # chapter one's notes come before chapter two's heading
    assert out.index("::: footnotes") < out.index("# Two")
    assert "one" in out and "two" in out


def test_page_mode_inlines_the_body_and_emits_no_section():
    out, _ = process_footnotes("A[^a]\n\n[^a]: The note.\n", mode="page")

    assert "::: footnotes" not in out
    assert '<span class="footnote-inline">The note.</span>' in out
    assert "footnote-ref" not in out  # WeasyPrint generates the call


def test_note_body_keeps_its_markdown():
    out, _ = process_footnotes("A[^a]\n\n[^a]: See **this** and [that](https://x.dev).\n",
                               mode="document")

    assert "**this**" in out and "[that](https://x.dev)" in out


from scriptorium.galley import render_pdf


def test_book_theme_renders_a_notes_section_per_chapter(tmp_path):
    src = ("---\ntheme: book\ntitle: T\n---\n\n"
           "# One\n\nAlpha.[^a]\n\n# Two\n\nBeta.[^b]\n\n"
           "[^a]: First note.\n\n[^b]: Second note.\n")
    out = tmp_path / "b.pdf"
    render_pdf(src, str(out), execute=False)
    assert out.exists() and out.stat().st_size > 1000

    import subprocess
    text = subprocess.run(["pdftotext", "-layout", str(out), "-"],
                          capture_output=True, text=True).stdout
    # chapter one's notes sit with chapter one — not collected at the end,
    # which is exactly what `document` mode would do instead.
    assert text.index("First note.") < text.index("Two")
    assert text.index("Two") < text.index("Second note.")


def test_footnote_text_reaches_the_pdf_and_the_marker_does_not_leak(tmp_path):
    src = ("---\ntheme: article\ntitle: T\n---\n\n"
           "# H\n\nA claim.[^a]\n\n[^a]: The supporting note.\n")
    out = tmp_path / "a.pdf"
    render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "The supporting note." in text
    assert "[^a]" not in text  # no literal marker syntax survived


def test_page_mode_floats_the_note_to_the_foot_of_its_anchors_page(tmp_path):
    def filler(tag, n):
        return "\n\n".join(f"{tag} paragraph {i}. " * 40 for i in range(n))

    src = ("---\ntheme: article\ntitle: T\nfootnotes: page\n---\n\n"
           f"# H\n\n{filler('Before', 10)}\n\nThe late claim.[^a]\n\n"
           f"{filler('After', 10)}\n\n[^a]: Note belonging to the anchor page.\n")
    out = tmp_path / "p.pdf"
    render_pdf(src, str(out), execute=False)

    import subprocess
    pages = subprocess.run(["pdftotext", str(out), "-"],
                           capture_output=True, text=True).stdout.split("\f")
    anchor = [p for p in pages if "The late claim." in p]
    assert len(anchor) == 1, "anchor text not found on exactly one page"
    page = anchor[0]

    # same page as its anchor...
    assert "Note belonging to the anchor page." in page
    # ...and at the foot of it: below the body text that follows the anchor,
    # which an un-floated note (still in the flow) would sit above.
    assert page.rindex("After paragraph") < page.index("Note belonging")


def test_unresolved_marker_and_uncited_definition_are_warned():
    out, warnings = process_footnotes("A[^missing] and B[^b]\n\n[^b]: two\n\n[^c]: three\n")

    assert "[^missing]" in out          # still literal, never deleted
    assert any("missing" in w for w in warnings)
    assert any("c" in w and "never referenced" in w for w in warnings)
    assert not any("[^b]" in w for w in warnings)   # b is fine, no noise


def test_render_surfaces_footnote_warnings(tmp_path):
    src = ("---\ntheme: article\ntitle: T\n---\n\n"
           "# H\n\nA claim.[^nope]\n\n[^a]: An orphan note.\n")
    report = render_pdf(src, str(tmp_path / "w.pdf"), execute=False)

    assert any("nope" in w for w in report.warnings)


def test_uncited_definitions_emit_no_empty_section():
    # v0.4.0 emitted a bare `::: footnotes` / `:::` pair here, which renders as
    # an empty ruled band in the PDF.
    out, warnings = process_footnotes("A claim, no marker.\n\n[^a]: An orphan.\n")

    assert "::: footnotes" not in out
    assert any("never referenced" in w for w in warnings)


# --- the endnotes section can carry a heading -------------------------------

def test_footnotes_label_becomes_the_section_heading(tmp_path):
    # Mirrors test_references_label_becomes_the_section_heading: the label's
    # language belongs to the author, so it is a var, not a baked-in string.
    src = ("---\ntheme: article\ntitle: T\nfootnotes-label: References and Notes\n"
           "---\n\n# H\n\nA claim.[^n]\n\n[^n]: The note body.\n")
    out = tmp_path / "label.pdf"
    render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "References and Notes" in text
    assert "The note body." in text


def test_footnotes_section_is_unlabelled_by_default(tmp_path):
    # Empty default: an endnotes block separated by a rule, as before.
    src = "---\ntheme: article\ntitle: T\n---\n\n# H\n\nA claim.[^n]\n\n[^n]: The note body.\n"
    out = tmp_path / "plain.pdf"
    render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "The note body." in text
    assert "References and Notes" not in text
