"""Tests for the citations pre-processing transform (citations.py)."""

import re

from scriptorium.citations import process_citations


_SMALL_DOC = """\
First sentence.^[1](#ref-1)^ Second.^[2](#ref-2)^ Third.^[1](#ref-1)^

Also plain form [2](#ref-2) here.

## References

### 1 {#ref-1}
Smith, J. (2023). *A paper*. Journal. [https://example.com](https://example.com)

### 2 {#ref-2}
Jones, A. (2024). *Another paper*. Conference.
"""


def _result():
    return process_citations(_SMALL_DOC)


# ── Pass 1: in-text citation anchors ────────────────────────────────────────

def test_first_occurrence_of_ref1_gets_anchor_cite_1_1():
    out = _result()
    # The anchor span must appear before the link in the source
    assert 'id="cite-1-1"' in out


def test_second_occurrence_of_ref1_gets_anchor_cite_1_2():
    out = _result()
    assert 'id="cite-1-2"' in out


def test_first_occurrence_of_ref2_gets_anchor_cite_2_1():
    out = _result()
    assert 'id="cite-2-1"' in out


def test_plain_link_form_also_gets_anchor():
    # [2](#ref-2) (not wrapped in ^) should also receive an anchor
    out = _result()
    assert 'id="cite-2-2"' in out  # second occurrence of ref-2


def test_citation_links_still_point_to_ref_anchors():
    # After pass 1, links remain as markdown syntax [N](#ref-N) (the full
    # markdown parser converts them to href= later in the pipeline).
    out = _result()
    assert "(#ref-1)" in out
    assert "(#ref-2)" in out


# ── Pass 2: bibliography back-links ─────────────────────────────────────────

def test_bib_entry_div_present_for_ref1():
    out = _result()
    assert 'id="ref-1"' in out
    assert 'class="bib-entry"' in out


def test_bib_ref1_has_back_link_to_cite_1_1():
    out = _result()
    assert 'href="#cite-1-1"' in out


def test_bib_ref1_has_back_link_to_cite_1_2():
    out = _result()
    assert 'href="#cite-1-2"' in out


def test_bib_ref2_has_back_link_to_cite_2_1():
    out = _result()
    assert 'href="#cite-2-1"' in out


def test_bib_ref2_has_back_link_to_cite_2_2():
    out = _result()
    assert 'href="#cite-2-2"' in out


def test_bib_body_contains_citation_text():
    out = _result()
    assert "Smith, J." in out
    assert "Jones, A." in out


def test_bib_body_renders_markdown_link():
    out = _result()
    assert '<a href="https://example.com">' in out


def test_bib_body_renders_italic():
    out = _result()
    assert "<em>A paper</em>" in out


def test_original_heading_format_removed():
    out = _result()
    # The raw ### N {#ref-N} form must not appear in the output
    assert "### 1 {#ref-1}" not in out
    assert "### 2 {#ref-2}" not in out


# ── Ordering guarantee ───────────────────────────────────────────────────────

def test_cite_anchors_appear_in_document_order():
    out = _result()
    pos_1_1 = out.index('id="cite-1-1"')
    pos_2_1 = out.index('id="cite-2-1"')
    pos_1_2 = out.index('id="cite-1-2"')
    # cite-1-1 comes before cite-2-1, which comes before cite-1-2
    assert pos_1_1 < pos_2_1 < pos_1_2


# ── Idempotence: no double-processing ───────────────────────────────────────

def test_uncited_reference_has_no_back_links():
    doc = """\
No citations here.

### 5 {#ref-5}
Uncited author.
"""
    out = process_citations(doc)
    assert 'id="ref-5"' in out
    # bib-back span should be absent (no occurrences)
    assert 'class="bib-back"' not in out
