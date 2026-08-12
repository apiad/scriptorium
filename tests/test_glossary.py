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


# --- marker rewriting -----------------------------------------------------

from scriptorium.glossary import mark_terms


def _entries():
    return load_entries(GLOSS, None)[0]


def test_display_form_becomes_an_anchored_link():
    entries = _entries()
    out, warnings = mark_terms("The [*AI effect*]{~ai-effect} is real.\n", entries)

    assert ('<a class="gloss-ref" id="glossref-ai-effect-1" '
            'href="#gloss-ai-effect">*AI effect*</a>') in out
    assert entries["ai-effect"].refs == 1 and warnings == []


def test_bare_form_uses_the_entrys_own_term():
    entries = _entries()
    out, _ = mark_terms("As [~tesler-larry] put it.\n", entries)

    assert '>Tesler, Larry</a>' in out
    assert 'id="glossref-tesler-larry-1"' in out


def test_repeated_mentions_get_distinct_call_site_anchors():
    entries = _entries()
    out, _ = mark_terms("[~ai-effect] and [~ai-effect] again.\n", entries)

    assert 'id="glossref-ai-effect-1"' in out and 'id="glossref-ai-effect-2"' in out
    assert entries["ai-effect"].refs == 2


def test_nested_markers_keep_the_inner_link_and_balance_their_tags():
    # An <a> inside an <a> is invalid: the parser closes the outer early and
    # strands a </a> in the running text. The inner term keeps the link.
    entries = _entries()
    src = "See [*the [~tesler-larry] case*]{~ai-effect}.\n"
    out, warnings = mark_terms(src, entries)

    assert out.count("<a ") == 1
    assert out.count("<a ") == out.count("</a>")
    assert 'href="#gloss-tesler-larry"' in out           # inner is the link
    assert '<span class="gloss-ref" id="glossref-ai-effect-1">' in out  # outer anchors only
    assert entries["ai-effect"].refs == 1                # and still collects a page ref
    assert warnings == []


def test_two_display_forms_nest_the_same_way():
    # The manuscript's actual shape, where both levels carry display text.
    entries = _entries()
    src = "See [*the [Tesler]{~tesler-larry} case*]{~ai-effect}.\n"
    out, warnings = mark_terms(src, entries)

    assert out.count("<a ") == 1 and out.count("</a>") == 1
    assert 'href="#gloss-tesler-larry"' in out
    assert '<span class="gloss-ref" id="glossref-ai-effect-1">' in out
    assert "{~" not in out and warnings == []


def test_unknown_key_warns_and_leaves_readable_text():
    entries = _entries()
    out, warnings = mark_terms("A [thing]{~nope} and [~alsonope].\n", entries)

    assert "thing" in out and "alsonope" in out
    assert "gloss-ref" not in out
    assert len(warnings) == 2


def test_a_marker_inside_a_code_fence_is_left_alone():
    entries = _entries()
    src = "Prose.\n\n```markdown\nSee [~ai-effect] here.\n```\n"
    out, _ = mark_terms(src, entries)

    assert "[~ai-effect]" in out
    assert entries["ai-effect"].refs == 0


# --- the section ----------------------------------------------------------

import pytest

from scriptorium.glossary import process_glossary


def test_section_replaces_the_placeholder_and_sorts_by_term():
    src = "Text with [~tesler-larry] and [~ai-effect].\n\n::: glossary\n:::\n"
    out, warnings = process_glossary(src, {"glossary": GLOSS}, None)

    assert "::: glossary" in out
    body = out.split("::: glossary")[1]
    assert body.index("AI effect") < body.index("Tesler, Larry")   # alphabetical
    assert warnings == []


def test_mentioned_entries_carry_one_arrow_and_an_empty_anchor_per_mention():
    src = "[~ai-effect] then [~ai-effect].\n\n::: glossary\n:::\n"
    out, _ = process_glossary(src, {"glossary": GLOSS}, None)

    assert "↩ " in out
    assert '<a class="gloss-back" href="#glossref-ai-effect-1"></a>' in out
    assert '<a class="gloss-back" href="#glossref-ai-effect-2"></a>' in out


def test_an_unmentioned_entry_is_listed_without_a_page_list():
    src = "[~ai-effect] only.\n\n::: glossary\n:::\n"
    out, _ = process_glossary(src, {"glossary": GLOSS}, None)

    assert "Tesler, Larry" in out                    # still defined for the reader
    assert "glossref-tesler-larry" not in out        # but points nowhere


def test_no_glossary_key_is_a_no_op():
    src = "Plain text.\n"
    out, warnings = process_glossary(src, {}, None)

    assert out == src and warnings == []


def test_two_placeholders_is_an_error():
    src = "::: glossary\n:::\n\n::: glossary\n:::\n"
    with pytest.raises(ValueError, match="only one"):
        process_glossary(src, {"glossary": GLOSS}, None)


def test_an_unclosed_placeholder_is_an_error():
    src = "Text.\n\n::: glossary\n"
    with pytest.raises(ValueError, match="never closed"):
        process_glossary(src, {"glossary": GLOSS}, None)


def test_frontmatter_is_preserved():
    src = "---\ntitle: T\n---\n\n[~ai-effect]\n\n::: glossary\n:::\n"
    out, _ = process_glossary(src, {"glossary": GLOSS}, None)

    assert out.startswith("---\ntitle: T\n---\n")


# --- end to end -----------------------------------------------------------

import subprocess

from scriptorium.galley import render_pdf


def _text(pdf) -> str:
    return subprocess.run(["pdftotext", str(pdf), "-"],
                          capture_output=True, text=True).stdout


def test_glossary_reaches_the_pdf(tmp_path):
    src = ("---\ntheme: article\ntitle: T\n"
           "glossary:\n"
           "  ai-effect:\n"
           "    term: \"AI effect\"\n"
           "    definition: \"A solved task stops counting.\"\n"
           "---\n\n# H\n\nThe [~ai-effect] is real.\n\n::: glossary\n:::\n")
    out = tmp_path / "g.pdf"
    render_pdf(src, str(out), execute=False)

    text = _text(out)
    assert "A solved task stops counting." in text
    assert "{~" not in text and "[~" not in text      # no syntax leaks


def test_a_term_glossed_inside_a_footnote_is_paged_where_the_note_renders(tmp_path):
    # Glossary runs after footnotes for this reason: the marker has by then been
    # moved to where the note actually prints.
    src = ("---\ntheme: article\ntitle: T\n"
           "glossary:\n"
           "  ai-effect:\n    term: \"AI effect\"\n    definition: \"A pattern.\"\n"
           "---\n\n# H\n\nA claim.[^a]\n\n[^a]: See the [~ai-effect].\n")
    out = tmp_path / "fn.pdf"
    report = render_pdf(src, str(out), execute=False)

    assert report.warnings == []
    assert "AI effect" in _text(out)


def test_project_level_glossary_path_reaches_the_render(tmp_path):
    (tmp_path / "g.yaml").write_text(
        'ai-effect:\n  term: "AI effect"\n  definition: "A pattern."\n', encoding="utf-8")
    (tmp_path / "ch.md").write_text("# H\n\nThe [~ai-effect].\n\n::: glossary\n:::\n",
                                    encoding="utf-8")
    (tmp_path / "scriptorium.yaml").write_text(
        "theme: article\nglossary: g.yaml\nvars:\n  title: T\nfiles:\n  - ch.md\n",
        encoding="utf-8")

    from scriptorium.cli import main
    assert main(["render", str(tmp_path / "scriptorium.yaml")]) == 0

    assert "A pattern." in _text(tmp_path / "book.pdf")


# --- the apparatus family -------------------------------------------------

def test_glossary_section_has_no_heading_without_the_label(tmp_path):
    src = ("---\ntheme: article\ntitle: T\n"
           "glossary:\n  ai-effect:\n    term: \"AI effect\"\n    definition: \"A pattern.\"\n"
           "---\n\n# H\n\nThe [~ai-effect].\n\n::: glossary\n:::\n")
    out = tmp_path / "nolabel.pdf"
    render_pdf(src, str(out), execute=False)

    text = _text(out)
    assert "A pattern." in text
    assert "Glossary" not in text and "GLOSSARY" not in text


def test_glossary_label_becomes_the_section_heading(tmp_path):
    src = ("---\ntheme: article\ntitle: T\nglossary-label: Glosario\n"
           "glossary:\n  ai-effect:\n    term: \"AI effect\"\n    definition: \"A pattern.\"\n"
           "---\n\n# H\n\nThe [~ai-effect].\n\n::: glossary\n:::\n")
    out = tmp_path / "label.pdf"
    render_pdf(src, str(out), execute=False)

    # the label the author chose, not a baked-in string
    assert "Glosario" in _text(out)


def test_a_long_glossary_paginates_and_keeps_its_tail(tmp_path):
    gloss = {f"k{i}": {"term": f"Term {i:03d}", "definition": "A definition. " * 12}
             for i in range(120)}
    src = ("---\ntheme: article\ntitle: T\nglossary:\n"
           + "\n".join(f"  {k}:\n    term: \"{v['term']}\"\n"
                       f"    definition: \"{v['definition']}\"" for k, v in gloss.items())
           + "\n---\n\n# H\n\nBody.\n\n::: glossary\n:::\n")
    out = tmp_path / "long.pdf"
    report = render_pdf(src, str(out), execute=False)

    assert report.n_pages > 2                      # it paginated
    assert "Term 119" in _text(out)                # and nothing fell off the end
    assert report.warnings == []


# --- the links, not the styling -------------------------------------------

def _link_dests(pdf_path, page_index):
    import pypdf

    page = pypdf.PdfReader(str(pdf_path)).pages[page_index]
    out = []
    for annot in page.get("/Annots") or []:
        obj = annot.get_object()
        if obj.get("/Subtype") == "/Link" and obj.get("/Dest"):
            out.append(str(obj["/Dest"]))
    return out


def test_the_glossary_links_resolve_in_both_directions(tmp_path):
    # A source or text grep passes on styled-but-dead text. The whole feature is
    # that the link resolves, and only the annotation proves it.
    src = ("---\ntheme: article\ntitle: T\n"
           "glossary:\n  ai-effect:\n    term: \"AI effect\"\n    definition: \"A pattern.\"\n"
           "---\n\n# H\n\nThe [~ai-effect] is real.\n\n::: newpage\n:::\n\n"
           "::: glossary\n:::\n")
    out = tmp_path / "links.pdf"
    render_pdf(src, str(out), execute=False)

    assert "gloss-ai-effect" in _link_dests(out, 0)        # body -> entry
    assert "glossref-ai-effect-1" in _link_dests(out, 1)   # entry -> body
    assert "↩ 1" in _text(out)          # and the back-link resolved to a real page
