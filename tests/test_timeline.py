"""Timeline pre-processor tests."""

from scriptorium.timeline import (
    DateTuple, parse_date, format_date,
    _resolve_group, _group_key, _group_label,
)


# --- parse_date ---

def test_parse_bare_year():
    assert parse_date("1936") == DateTuple(year=1936)

def test_parse_year_month():
    assert parse_date("1936-07") == DateTuple(year=1936, month=7)

def test_parse_full_date():
    assert parse_date("1936-07-28") == DateTuple(year=1936, month=7, day=28)

def test_parse_bce_word():
    assert parse_date("300 BCE") == DateTuple(year=-300)

def test_parse_bce_ascii_minus():
    assert parse_date("-300") == DateTuple(year=-300)

def test_parse_bce_unicode_minus():
    assert parse_date("\u2212300") == DateTuple(year=-300)

def test_parse_bce_with_month():
    assert parse_date("\u2212300-07") == DateTuple(year=-300, month=7)

def test_parse_unrecognised_returns_none():
    assert parse_date("not a date") is None

def test_parse_empty_returns_none():
    assert parse_date("") is None


# --- format_date ---

def test_format_bare_year():
    assert format_date(DateTuple(year=1936)) == "1936"

def test_format_year_month():
    assert format_date(DateTuple(year=1936, month=7)) == "July 1936"

def test_format_full_date():
    assert format_date(DateTuple(year=1936, month=7, day=28)) == "July 28, 1936"

def test_format_bce_year():
    assert format_date(DateTuple(year=-300)) == "300 BCE"

def test_format_bce_with_month():
    assert format_date(DateTuple(year=-300, month=7)) == "July 300 BCE"

def test_format_override_replaces_auto():
    assert format_date(DateTuple(year=1936), override="A summer of invention") == "A summer of invention"


# --- grouping ---

def test_resolve_group_century():
    assert _resolve_group("century") == 100

def test_resolve_group_decade():
    assert _resolve_group("decade") == 10

def test_resolve_group_millennium():
    assert _resolve_group("millennium") == 1000

def test_resolve_group_integer_string():
    assert _resolve_group("50") == 50

def test_resolve_group_integer():
    assert _resolve_group(100) == 100

def test_resolve_group_none():
    assert _resolve_group(None) is None

def test_resolve_group_invalid():
    assert _resolve_group("banana") is None


def test_group_key_ce_century():
    dt = DateTuple(year=1936)
    assert _group_key(dt, 100) == (0, 19)   # 20th century → bucket 19

def test_group_key_bce_century():
    dt = DateTuple(year=-384)
    assert _group_key(dt, 100) == (1, 3)    # 4th century BCE → bucket 3

def test_group_key_bce_first_century():
    dt = DateTuple(year=-50)
    assert _group_key(dt, 100) == (1, 0)    # 1st century BCE → bucket 0


def test_group_label_ce_century():
    assert _group_label(0, 19, 100) == "20th Century"

def test_group_label_ce_decade():
    assert _group_label(0, 193, 10) == "1930s"

def test_group_label_bce_century():
    assert _group_label(1, 3, 100) == "4th Century BCE"

def test_group_label_bce_decade():
    assert _group_label(1, 38, 10) == "380s BCE"

def test_group_label_ce_millennium():
    assert _group_label(0, 1, 1000) == "2nd Millennium"

def test_group_label_bce_millennium():
    assert _group_label(1, 0, 1000) == "1st Millennium BCE"

def test_group_label_ce_custom_n():
    assert _group_label(0, 1, 50) == "50–99"

def test_group_label_bce_custom_n():
    assert _group_label(1, 0, 50) == "50–1 BCE"


# --- Entry + load_entries ---

from scriptorium.timeline import Entry, load_entries

YAML_ENTRIES = {
    "turing-paper": {
        "date": "1936-07-28",
        "label": "Turing publishes On Computable Numbers",
        "description": "A landmark paper.",
        "category": "Theory",
    },
    "shannon-paper": {
        "date": "1948",
        "label": "Shannon founds information theory",
        "date-display": "Postwar summer",
    },
}


def test_load_entries_from_dict():
    entries, warnings = load_entries(YAML_ENTRIES, None)
    assert set(entries) == {"turing-paper", "shannon-paper"}
    assert warnings == []
    e = entries["turing-paper"]
    assert e.date == DateTuple(year=1936, month=7, day=28)
    assert e.label == "Turing publishes On Computable Numbers"
    assert e.description == "A landmark paper."
    assert e.category == "Theory"
    assert e.refs == 0


def test_load_entries_date_display():
    entries, _ = load_entries(YAML_ENTRIES, None)
    assert entries["shannon-paper"].date_display == "Postwar summer"


def test_load_entries_from_yaml_file(tmp_path):
    (tmp_path / "t.yaml").write_text(
        'turing-paper:\n  date: "1936"\n  label: "Turing"\n', encoding="utf-8"
    )
    entries, warnings = load_entries("t.yaml", tmp_path)
    assert "turing-paper" in entries
    assert warnings == []


def test_load_entries_missing_label_warns_and_drops():
    entries, warnings = load_entries({"bad": {"date": "1936"}}, None)
    assert entries == {}
    assert any("bad" in w and "label" in w for w in warnings)


def test_load_entries_invalid_date_warns_and_drops():
    entries, warnings = load_entries({"bad": {"date": "not-a-date", "label": "X"}}, None)
    assert entries == {}
    assert any("bad" in w and "date" in w for w in warnings)


def test_load_entries_missing_file_warns():
    entries, warnings = load_entries("missing.yaml", None)
    assert entries == {}
    assert len(warnings) == 1 and "missing.yaml" in warnings[0]


def test_load_entries_no_date_is_ok():
    # date is optional in YAML; required only for key-only markers
    entries, warnings = load_entries({"ev": {"label": "Some event"}}, None)
    assert "ev" in entries
    assert entries["ev"].date is None
    assert warnings == []


# --- mark_events ---

from scriptorium.timeline import mark_events

_YAML = {
    "turing-paper": Entry(
        key="turing-paper",
        date=DateTuple(year=1936),
        date_display=None,
        label="Turing publishes On Computable Numbers",
        description="",
        category="Theory",
    ),
}


def test_bare_form_registered_and_anchor_emitted():
    src = "In [>1936: Turing invents computation] this happened.\n"
    out, events, warnings = mark_events(src, {})
    assert warnings == []
    assert len(events) == 1
    e = events[0]
    assert e.date == DateTuple(year=1936)
    assert e.label == "Turing invents computation"
    assert e.refs == 1
    assert 'class="tl-ref"' in out
    assert "Turing invents computation" in out


def test_full_form_display_text_in_prose():
    src = "[his landmark paper]{>1936: Turing invents computation} was key.\n"
    out, events, warnings = mark_events(src, {})
    assert "his landmark paper" in out
    assert events[0].label == "Turing invents computation"


def test_yaml_key_merges_category():
    src = "[a paper]{>1936 turing-paper: Turing invents}\n"
    out, events, warnings = mark_events(src, _YAML)
    assert warnings == []
    assert events[0].category == "Theory"


def test_key_only_no_yaml_warns_and_leaves_literal():
    src = "[a paper]{>missing-key}\n"
    out, events, warnings = mark_events(src, {})
    assert any("missing-key" in w for w in warnings)
    assert events == []
    assert "[a paper]" in out


def test_malformed_date_warns_and_leaves_literal():
    src = "[>banana: Some event]\n"
    out, events, warnings = mark_events(src, {})
    assert any("banana" in w for w in warnings)
    assert events == []


def test_same_event_twice_increments_refs():
    src = "[>1936: Turing invents] and [>1936: Turing invents] again.\n"
    out, events, warnings = mark_events(src, {})
    # Same synthetic key → same Entry, refs=2
    assert len(events) == 1
    assert events[0].refs == 2
    assert 'id="tlref-' in out


def test_marker_inside_code_fence_skipped():
    src = "```\n[>1936: Turing invents]\n```\n"
    out, events, _ = mark_events(src, {})
    assert events == []
    assert out == src


def test_marker_inside_inline_code_skipped():
    src = "Use `[>1936: Turing]` to mark events.\n"
    out, events, _ = mark_events(src, {})
    assert events == []


def test_display_date_override_stored_on_entry():
    src = '[>-300 "~2400 years ago": Euclid systematizes geometry]\n'
    out, events, warnings = mark_events(src, {})
    assert warnings == []
    assert events[0].date == DateTuple(year=-300)
    assert events[0].date_display == "~2400 years ago"


def test_bce_date_parsed_correctly():
    src = "[>300 BCE: Euclid systematizes geometry]\n"
    _, events, warnings = mark_events(src, {})
    assert warnings == []
    assert events[0].date == DateTuple(year=-300)


# --- _component and process_timeline ---

from scriptorium.timeline import process_timeline


def _make_src(body: str) -> str:
    return body


def test_no_config_and_no_placeholder_is_noop():
    # No timeline: key, no timeline-group:, no :::timeline placeholder →
    # markers must be left as literal text (feature not opted in).
    src = "Some [>1936: Turing invents computation] prose.\n"
    out, warnings = process_timeline(src, {}, None)
    assert warnings == []
    assert out == src   # marker untouched


def test_timeline_section_appended_when_placeholder_present():
    src = (
        "Some [>1936: Turing invents computation] prose.\n\n"
        "::: timeline\n:::\n"
    )
    out, warnings = process_timeline(src, {}, None)
    assert warnings == []
    assert "Turing invents computation" in out
    assert "1936" in out
    assert "::: timeline" in out


def test_events_sorted_oldest_first():
    src = (
        "[>1948: Shannon] and [>1936: Turing] appeared.\n\n"
        "::: timeline\n:::\n"
    )
    out, _ = process_timeline(src, {}, None)
    tl_start = out.index("::: timeline")
    turing_pos = out.index("Turing", tl_start)
    shannon_pos = out.index("Shannon", tl_start)
    assert turing_pos < shannon_pos   # 1936 before 1948


def test_bce_event_sorts_before_ce():
    src = (
        "[>1936: Turing] and [>300 BCE: Euclid] mentioned.\n\n"
        "::: timeline\n:::\n"
    )
    out, _ = process_timeline(src, {}, None)
    tl_start = out.index("::: timeline")
    assert out.index("Euclid", tl_start) < out.index("Turing", tl_start)


def test_group_by_century_inserts_headers():
    src = (
        "[>1854: Boole] [>1936: Turing] [>300 BCE: Euclid] text.\n\n"
        "::: timeline\n:::\n"
    )
    out, _ = process_timeline(src, {"timeline-group": "century"}, None)
    assert "3rd Century BCE" in out
    assert "19th Century" in out
    assert "20th Century" in out


def test_display_date_override_rendered():
    src = '[>-300 "~2400 years ago": Euclid] mentioned.\n\n::: timeline\n:::\n'
    out, _ = process_timeline(src, {}, None)
    tl_start = out.index("::: timeline")
    assert "~2400 years ago" in out[tl_start:]


def test_back_links_emitted():
    src = "[>1936: Turing] prose.\n\n::: timeline\n:::\n"
    out, _ = process_timeline(src, {}, None)
    assert 'class="tl-back"' in out


def test_two_timeline_blocks_raise():
    src = "::: timeline\n:::\n\n::: timeline\n:::\n"
    import pytest
    with pytest.raises(ValueError, match="two"):
        process_timeline(src, {}, None)


def test_yaml_enrichment_via_meta(tmp_path):
    (tmp_path / "tl.yaml").write_text(
        'turing-paper:\n  date: "1936"\n  label: "Turing publishes"\n  category: "Theory"\n',
        encoding="utf-8",
    )
    src = "[a paper]{>1936 turing-paper: Turing publishes}\n\n::: timeline\n:::\n"
    out, warnings = process_timeline(src, {"timeline": "tl.yaml"}, tmp_path)
    assert warnings == []
    assert "Turing publishes" in out


# --- Integration smoke test ---

import textwrap


def test_renders_without_error(tmp_path):
    """Smoke: a one-file project with timeline markers renders to PDF."""
    from scriptorium.project import load as load_project
    from scriptorium.galley import render_pdf

    md = tmp_path / "book.md"
    md.write_text(textwrap.dedent("""\
        # Chapter One

        In [>1936: Turing defines computability] things changed.

        Later [>1948: Shannon founds information theory] happened.

        # Timeline {.unnumbered}

        ::: timeline
        :::
    """), encoding="utf-8")

    proj_path = tmp_path / "book.yaml"
    proj_path.write_text(textwrap.dedent("""\
        theme: book
        timeline-group: century
        vars:
          title: Test Book
          author: Test
        files:
          - book.md
    """), encoding="utf-8")

    proj = load_project(proj_path)
    out_pdf = tmp_path / "book.pdf"
    cwd = str(proj_path.resolve().parent)
    report = render_pdf(
        proj.src, str(out_pdf),
        base_url=cwd + "/",
        theme_name=proj.theme,
        cwd=cwd,
        execute=False,
        vars=proj.vars,
        code_root=proj.code_root,
        project_meta=proj.meta,
    )
    assert out_pdf.exists()
    assert report.n_pages > 0
