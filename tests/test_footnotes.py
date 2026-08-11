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
