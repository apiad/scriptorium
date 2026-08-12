"""Tests for block splitting in parse.py — specifically loose-list regrouping."""

from scriptorium.parse import _regroup_lists, _split_md


# ── helpers ──────────────────────────────────────────────────────────────────

def _prose(items) -> list[str]:
    """The prose blocks of a _split_md result, in order."""
    return [b for kind, *rest in ((i[0], *i[1:]) for i in items)
            if kind == "prose" for b in [rest[0]]]


# ── loose ordered lists stay one block ───────────────────────────────────────

def test_loose_ordered_list_is_one_block():
    # The bug this guards: blank-line-separated items each became their own
    # block, so each rendered as a fresh <ol> and "1. 2. 3." came out "1. 1. 1.".
    blocks = ["1. one", "2. two", "3. three"]
    assert _regroup_lists(blocks) == ["1. one\n\n2. two\n\n3. three"]


def test_loose_bullet_list_is_one_block():
    assert _regroup_lists(["- one", "- two"]) == ["- one\n\n- two"]


def test_paren_ordered_marker_counts_as_list():
    assert _regroup_lists(["1) one", "2) two"]) == ["1) one\n\n2) two"]


# ── continuations stay attached to their item ────────────────────────────────

def test_indented_continuation_joins_the_run():
    blocks = ["1. one", "   still item one", "2. two"]
    assert _regroup_lists(blocks) == ["1. one\n\n   still item one\n\n2. two"]


def test_indented_block_without_a_list_is_left_alone():
    # No open run, so an indented block is not swallowed into anything.
    assert _regroup_lists(["   indented"]) == ["   indented"]


# ── prose around lists is untouched ──────────────────────────────────────────

def test_paragraphs_stay_separate():
    assert _regroup_lists(["para one", "para two"]) == ["para one", "para two"]


def test_paragraph_after_list_closes_the_run():
    blocks = ["1. one", "2. two", "after"]
    assert _regroup_lists(blocks) == ["1. one\n\n2. two", "after"]


def test_paragraph_before_list_stays_separate():
    blocks = ["intro", "1. one", "2. two"]
    assert _regroup_lists(blocks) == ["intro", "1. one\n\n2. two"]


def test_two_lists_split_by_prose_do_not_merge():
    blocks = ["1. a", "between", "1. b"]
    assert _regroup_lists(blocks) == ["1. a", "between", "1. b"]


# ── end to end through _split_md ─────────────────────────────────────────────

def test_split_md_keeps_a_loose_list_whole():
    out = [b.strip() for b in _prose(_split_md("intro\n\n1. one\n\n2. two\n"))]
    assert out == ["intro", "1. one\n\n2. two"]


def test_split_md_does_not_merge_a_list_across_a_code_fence():
    # The fence separates the two runs; numbering restarting there is correct.
    items = _split_md("1. one\n\n```\ncode\n```\n\n2. two\n")
    assert [i[0] for i in items] == ["prose", "code", "prose"]


# --- heading labels are text ----------------------------------------------

def test_heading_label_carries_no_markup():
    # The glossary pre-processor rewrites a marker inside a heading into an
    # anchor before parse() sees it; the TOC must not print that markup.
    from scriptorium.parse import _heading_unit

    unit = _heading_unit('# The rise of <a class="gloss-ref" href="#x">machine learning</a>')

    assert unit.heading == "The rise of machine learning"


def test_toc_omits_an_unlisted_heading():
    from scriptorium.parse import fill_toc, parse

    src = "::: toc\n:::\n\n# Kept\n\nBody.\n\n# Hidden {.unlisted}\n\nBody.\n"
    units = fill_toc(parse(src))
    entries = [u.html for u in units if u.name == "toc-entry"]

    assert any("Kept" in e for e in entries)
    assert not any("Hidden" in e for e in entries)
