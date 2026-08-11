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
