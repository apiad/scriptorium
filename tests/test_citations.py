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
