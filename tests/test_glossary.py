"""Glossed terms and the back-of-book glossary."""

from scriptorium.glossary import Entry, load_entries

GLOSS = {
    "ai-effect": {"term": "AI effect",
                  "definition": "The pattern by which a solved task stops counting."},
    "tesler-larry": {"term": "Tesler, Larry",
                     "definition": "Computer scientist who coined *direct manipulation*."},
}


def test_inline_mapping_becomes_entries():
    entries, warnings = load_entries(GLOSS, None)

    assert set(entries) == {"ai-effect", "tesler-larry"}
    assert entries["ai-effect"].term == "AI effect"
    assert entries["ai-effect"].refs == 0
    assert warnings == []


def test_a_path_is_read_relative_to_the_base_dir(tmp_path):
    (tmp_path / "g.yaml").write_text(
        'ai-effect:\n  term: "AI effect"\n  definition: "A pattern."\n', encoding="utf-8")

    entries, warnings = load_entries("g.yaml", tmp_path)

    assert entries["ai-effect"].term == "AI effect"
    assert warnings == []


def test_an_entry_without_a_term_warns_and_is_dropped():
    entries, warnings = load_entries({"broken": {"definition": "No term."}}, None)

    assert entries == {}
    assert any("broken" in w and "term" in w for w in warnings)


def test_an_unreadable_path_warns_rather_than_raising(tmp_path):
    entries, warnings = load_entries("missing.yaml", tmp_path)

    assert entries == {}
    assert len(warnings) == 1 and "missing.yaml" in warnings[0]
