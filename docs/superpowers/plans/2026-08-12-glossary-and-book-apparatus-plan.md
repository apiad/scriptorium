# Glossary and Book Apparatus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give scriptorium a glossary, a `css:` project key, and `{.part}` / `{.unnumbered}` heading support, so *Mostly Harmless AI* renders to PDF with no build step of its own.

**Architecture:** `glossary.py` is a source-to-source pre-processor and a structural sibling of `citations.py` — it runs on raw source after footnotes and citations, rewrites `[~key]` / `[display]{~key}` markers into anchored links, and replaces a `::: glossary` placeholder with entries sorted by term. Page back-references are empty anchors filled by CSS `target-counter`, exactly as citation back-links already are. Everything else is theme CSS, because the engine already carries `{.class}` from a heading onto the `<h1>`.

**Tech Stack:** Python 3.12+, `markdown-it-py`, WeasyPrint, PyYAML, pytest. `pypdf` is added to the dev group for one test.

**Spec:** `docs/superpowers/specs/2026-08-12-glossary-and-book-apparatus-design.md`

## Global Constraints

- Python 3.12+, English throughout. One logical change per commit, conventional commits.
- **`uv run pytest` must pass before any commit lands.** Run it, do not assume it.
- The engine is theme-agnostic: numbering, cross-references and look live in **theme CSS, not the engine**. Never add domain logic (chapters, authors, parts) to the engine.
- Verify visual work visually: render the PDF and look at it. A page count is not a check.
- Anchor and class names are fixed by the spec and used across tasks: marker class `gloss-ref`, back-link class `gloss-back`, entry anchor `gloss-<key>`, call-site anchor `glossref-<key>-<n>`.
- Baseline is **v0.7.0**. `{{#glossary-label}}` depends on the hyphen-accepting `_HOLE` / `_SECTION` patterns that landed in `7c82729`; against v0.6.0 this plan does not work.

---

### Task 1: Glossary entry loading

**Files:**
- Create: `scriptorium/glossary.py`
- Test: `tests/test_glossary.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Entry(key: str, term: str, definition: str, refs: int = 0)` dataclass; `load_entries(spec: dict | str, base_dir: Path | None) -> tuple[dict[str, Entry], list[str]]` returning key→Entry and warnings.

- [ ] **Step 1: Write the failing tests**

```python
"""Glossed terms and the back-of-book glossary."""

from pathlib import Path

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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_glossary.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scriptorium.glossary'`

- [ ] **Step 3: Write the module**

Create `scriptorium/glossary.py`:

```python
"""Glossed terms and a back-of-book glossary.

A source-to-source pre-processor, like footnotes.py and citations.py and for the
same reason: parse() renders block by block, so a plugin would never see a marker
and its entry in one render call.

Definitions are opaque Markdown prose, on the same contract as a bibliography
entry: the engine sorts and links them, it never inspects them.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Entry:
    key: str
    term: str
    definition: str
    refs: int = 0


def load_entries(spec, base_dir: Path | None) -> tuple[dict[str, Entry], list[str]]:
    """`glossary:` is either a mapping or a path to a YAML file holding one.

    A path keeps a five-hundred-entry glossary out of the project file; an inline
    mapping keeps a single document from needing a second file.
    """
    if isinstance(spec, str):
        path = Path(spec)
        if base_dir is not None and not path.is_absolute():
            path = base_dir / path
        try:
            spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except OSError as exc:
            return {}, [f"glossary file {spec!r} could not be read: {exc}"]

    if not isinstance(spec, dict):
        return {}, ["`glossary:` is neither a mapping nor a path to one"]

    entries: dict[str, Entry] = {}
    warnings: list[str] = []
    for key, value in spec.items():
        if not isinstance(value, dict) or not value.get("term"):
            warnings.append(f"glossary entry {key!r} has no `term:`")
            continue
        entries[key] = Entry(key=key, term=value["term"],
                             definition=value.get("definition", ""))
    return entries, warnings
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_glossary.py -v`
Expected: 4 passed

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add scriptorium/glossary.py tests/test_glossary.py
git commit -m "feat(glossary): load entries from a mapping or a YAML path"
```

---

### Task 2: Marker rewriting

**Files:**
- Modify: `scriptorium/glossary.py`
- Test: `tests/test_glossary.py`

**Interfaces:**
- Consumes: `Entry`, `load_entries` from Task 1.
- Produces: `mark_terms(src: str, entries: dict[str, Entry]) -> tuple[str, list[str]]`. Mutates `entry.refs` as a side effect — the count is what Task 3 turns into back-links.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_glossary.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_glossary.py -v -k mark or nested or unknown or fence`
Expected: FAIL — `ImportError: cannot import name 'mark_terms'`

- [ ] **Step 3: Implement**

Add the import and the function to `scriptorium/glossary.py`:

```python
from .source import fence_spans, in_span

# `[display]{~key}` and the bare `[~key]`. Excluding `[` as well as `]` from the
# display class is what makes the first pattern match the INNERMOST span of a
# nested pair: with `[^\]]*` the scan runs past the inner opening bracket and
# silently pairs the outer display text with the inner key.
_DISPLAY = re.compile(r"\[([^\[\]]*)\]\{~([\w-]+)\}")
_BARE = re.compile(r"\[~([\w-]+)\]")

_MAX_NESTING = 5


def mark_terms(src: str, entries: dict[str, Entry]) -> tuple[str, list[str]]:
    """Rewrite glossary markers to anchored links; return (src, warnings)."""
    warnings: list[str] = []

    def warn(message: str) -> None:
        if message not in warnings:
            warnings.append(message)

    def anchor(display: str, key: str) -> str:
        if key not in entries:
            warn(f"glossary key {key!r} has no entry")
            return display          # the prose survives; the failure is reported
        entry = entries[key]
        entry.refs += 1
        if "<a " in display:
            # A nested pair: an <a> inside an <a> is invalid HTML, so the outer
            # keeps only its anchor. The inner, more specific term stays
            # clickable and the outer entry still collects its page reference.
            return (f'<span class="gloss-ref" '
                    f'id="glossref-{key}-{entry.refs}">{display}</span>')
        return (f'<a class="gloss-ref" id="glossref-{key}-{entry.refs}" '
                f'href="#gloss-{key}">{display}</a>')

    def sweep(text: str, pattern, render) -> tuple[str, int]:
        # fence_spans is recomputed per sweep on purpose: a rewrite moves every
        # offset after it, so spans from an earlier pass no longer line up.
        spans = fence_spans(text)
        out, last, hits = [], 0, 0
        for m in pattern.finditer(text):
            if in_span(m.start(), spans):
                continue
            out.append(text[last:m.start()])
            last = m.end()
            hits += 1
            out.append(render(m))
        out.append(text[last:])
        return "".join(out), hits

    # Only the innermost marker matches, and a replacement contains no brackets,
    # so each pass exposes the next level out. Two levels is all the manuscript
    # has; the cap is a runaway guard, not a limit anyone should reach.
    for _ in range(_MAX_NESTING):
        src, hits = sweep(src, _DISPLAY, lambda m: anchor(m.group(1), m.group(2)))
        if not hits:
            break

    # The bare form carries no display text, so it cannot nest: one pass.
    src, _ = sweep(src, _BARE,
                   lambda m: anchor(entries[m.group(1)].term
                                    if m.group(1) in entries else m.group(1),
                                    m.group(1)))
    return src, warnings
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_glossary.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add scriptorium/glossary.py tests/test_glossary.py
git commit -m "feat(glossary): rewrite [~key] and [display]{~key} to anchored links"
```

---

### Task 3: The glossary section

**Files:**
- Modify: `scriptorium/glossary.py`
- Test: `tests/test_glossary.py`

**Interfaces:**
- Consumes: `Entry`, `load_entries`, `mark_terms`.
- Produces: `process_glossary(src: str, meta: dict, base_dir: Path | None) -> tuple[str, list[str]]` — the single entry point `galley.render_pdf` calls in Task 4.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_glossary.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_glossary.py -v -k process or placeholder or unmentioned`
Expected: FAIL — `ImportError: cannot import name 'process_glossary'`

- [ ] **Step 3: Implement**

Add to `scriptorium/glossary.py` (extend the `.source` import to include `line_offsets` and `split_frontmatter`):

```python
_GLOSS_OPEN = re.compile(r"^:{3,}[ \t]*glossary[ \t]*$")
_GLOSS_CLOSE = re.compile(r"^:{3,}[ \t]*$")


def _placeholder(src: str) -> tuple[int, int] | None:
    """Character range of an author-written `::: glossary` block, if any."""
    spans = fence_spans(src)
    lines = src.split("\n")
    offsets = line_offsets(lines)
    found = None
    for i, line in enumerate(lines):
        if not _GLOSS_OPEN.match(line) or in_span(offsets[i], spans):
            continue
        for j in range(i + 1, len(lines)):
            if _GLOSS_CLOSE.match(lines[j]):
                if found is not None:
                    raise ValueError("two `::: glossary` blocks; there can be only one")
                found = (offsets[i], offsets[j] + len(lines[j]) + 1)
                break
        else:
            raise ValueError("`::: glossary` block is never closed")
    return found


def _component(entries: list[Entry]) -> str:
    """Entries as a `::: glossary` component; definitions stay Markdown.

    One blank-line-separated block per entry, so the section renders as many
    paragraphs rather than one wall — and sorted here, not in the theme, because
    alphabetical order is the glossary's contract with the reader.
    """
    items = []
    for entry in sorted(entries, key=lambda e: e.term.lower()):
        # One arrow, then an empty anchor per mention: only the paged renderer
        # knows what page a mention landed on, so target-counter fills them in.
        back = ""
        if entry.refs:
            links = ", ".join(
                f'<a class="gloss-back" href="#glossref-{entry.key}-{k}"></a>'
                for k in range(1, entry.refs + 1))
            back = f" ↩ {links}"
        items.append(f'<span class="gloss-term" id="gloss-{entry.key}"></span>'
                     f"**{entry.term}** — {entry.definition}{back}")
    return "::: glossary\n" + "\n\n".join(items) + "\n:::\n"


def process_glossary(src: str, meta: dict,
                     base_dir: Path | None) -> tuple[str, list[str]]:
    """Entry point: link glossed terms and emit the glossary section."""
    spec = meta.get("glossary")
    if not spec:
        return src, []

    entries, warnings = load_entries(spec, base_dir)
    head, body = split_frontmatter(src)
    marked, mark_warnings = mark_terms(body, entries)
    warnings = warnings + mark_warnings

    if not entries:
        return head + marked, warnings

    block = _component(list(entries.values()))
    at = _placeholder(marked)
    if at:
        return head + marked[: at[0]] + block + marked[at[1]:], warnings
    return head + marked.rstrip() + "\n\n" + block, warnings
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_glossary.py -v`
Expected: 17 passed

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add scriptorium/glossary.py tests/test_glossary.py
git commit -m "feat(glossary): emit the ::: glossary section with page back-links"
```

---

### Task 4: Wire the pre-processor into the render

**Files:**
- Modify: `scriptorium/galley.py:657-668`
- Modify: `scriptorium/project.py:49`
- Test: `tests/test_glossary.py`

**Interfaces:**
- Consumes: `process_glossary` from Task 3.
- Produces: a rendered PDF in which glossed terms are links. `Project.meta` now carries `glossary` alongside `bibliography` and `nocite`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_glossary.py`:

```python
from scriptorium.galley import render_pdf


def test_glossary_reaches_the_pdf(tmp_path):
    src = ("---\ntheme: article\ntitle: T\n"
           "glossary:\n"
           "  ai-effect:\n"
           "    term: \"AI effect\"\n"
           "    definition: \"A solved task stops counting.\"\n"
           "---\n\n# H\n\nThe [~ai-effect] is real.\n\n::: glossary\n:::\n")
    out = tmp_path / "g.pdf"
    render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
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

    import subprocess
    text = subprocess.run(["pdftotext", str(tmp_path / "book.pdf"), "-"],
                          capture_output=True, text=True).stdout
    assert "A pattern." in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_glossary.py -v -k reaches or footnote`
Expected: FAIL — the definition text is absent; the marker prints literally.

- [ ] **Step 3: Wire it in**

In `scriptorium/galley.py`, extend the import block and the pre-processor run (currently lines 657–667):

```python
    from .parse import fill_toc
    from .footnotes import process_footnotes, resolve_footnote_mode
    from .citations import process_citations
    from .glossary import process_glossary

    # Citations run after footnotes on purpose: a [@key] written inside a note
    # body has by then been moved to where the note actually renders, so it is
    # numbered by reading order rather than by where its definition happened to
    # sit in the source. The glossary runs last for exactly the same reason.
    src, warnings = process_footnotes(src, resolve_footnote_mode(meta, theme.meta))
    src, cite_warnings = process_citations(src, meta)
    src, gloss_warnings = process_glossary(src, meta, Path(cwd) if cwd else None)
    warnings = warnings + cite_warnings + gloss_warnings
```

In `scriptorium/project.py`, add `glossary` to the content keys (line 49):

```python
    meta = {k: spec[k] for k in ("bibliography", "nocite", "glossary") if k in spec}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_glossary.py -v`
Expected: 20 passed

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add scriptorium/galley.py scriptorium/project.py tests/test_glossary.py
git commit -m "feat(glossary): run the pre-processor and carry glossary: through a project"
```

---

### Task 5: The `css:` key

**Files:**
- Modify: `scriptorium/galley.py` (in `render_pdf`, after the `overrides` block around line 636)
- Modify: `scriptorium/project.py:49`
- Test: `tests/test_galley.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `css:` accepted in `scriptorium.yaml` and in document frontmatter, as a string or list of paths.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_galley.py`:

```python
def test_project_css_overrides_the_theme(tmp_path):
    # A book needs its own stylesheet without authoring a theme: load_theme
    # resolves only from scriptorium/themes, so `css:` is the only route in.
    (tmp_path / "book.css").write_text(".gloss-ref { color: #ff0000; }\n", encoding="utf-8")
    (tmp_path / "ch.md").write_text("# H\n\nBody.\n", encoding="utf-8")
    (tmp_path / "scriptorium.yaml").write_text(
        "theme: article\ncss: book.css\nvars:\n  title: T\nfiles:\n  - ch.md\n",
        encoding="utf-8")

    from scriptorium.cli import main
    assert main(["render", str(tmp_path / "scriptorium.yaml")]) == 0
    assert (tmp_path / "book.pdf").exists()


def test_missing_css_file_warns_rather_than_raising(tmp_path):
    src = "---\ntheme: article\ntitle: T\ncss: nope.css\n---\n\n# H\n\nBody.\n"
    out = tmp_path / "c.pdf"
    report = render_pdf(src, str(out), cwd=str(tmp_path), execute=False)

    assert out.exists()
    assert any("nope.css" in w for w in report.warnings)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_galley.py -v -k css`
Expected: FAIL — no warning is produced; `css:` is ignored.

- [ ] **Step 3: Implement**

In `scriptorium/galley.py`, immediately after the existing `overrides` block, add:

```python
    # A project's own stylesheet. load_theme resolves only from scriptorium's
    # themes directory, so without this a book with any custom styling has to
    # author a theme inside this repo. Appended after the theme's own rules so
    # it wins on equal specificity.
    css_warnings: list[str] = []
    css_spec = meta.get("css")
    paths = [css_spec] if isinstance(css_spec, str) else list(css_spec or [])
    for rel in paths:
        path = Path(rel)
        if cwd and not path.is_absolute():
            path = Path(cwd) / path
        try:
            theme.css += "\n" + path.read_text(encoding="utf-8")
        except OSError as exc:
            css_warnings.append(f"css file {rel!r} could not be read: {exc}")
```

Then include them where the warning list is assembled:

```python
    warnings = css_warnings + warnings + cite_warnings + gloss_warnings
```

In `scriptorium/project.py`, add `css` to the content keys:

```python
    meta = {k: spec[k] for k in ("bibliography", "nocite", "glossary", "css") if k in spec}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_galley.py -v -k css`
Expected: 2 passed

- [ ] **Step 5: Prove the CSS actually reaches the page**

A rendered PDF proves nothing about colour on its own. Render a document whose `css:` sets `body { color: #ff0000 }`, open the PDF, and confirm the text is red. Then delete the `css:` line, re-render, and confirm it is black. A stylesheet that is silently dropped passes step 4 but fails this.

- [ ] **Step 6: Run the whole suite and commit**

```bash
uv run pytest
git add scriptorium/galley.py scriptorium/project.py tests/test_galley.py
git commit -m "feat(themes): css: gives a project its own stylesheet"
```

---

### Task 6: Clean heading labels and `.unlisted`

**Files:**
- Modify: `scriptorium/parse.py:77-85` (`_heading_unit`), `scriptorium/parse.py:304` (`fill_toc`)
- Test: `tests/test_parse.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Unit.heading` is plain text with no markup. `fill_toc` skips headings whose classes include `unlisted`.

**Why:** `fill_toc` escapes `Unit.heading`, which holds the raw source text. Once a glossary marker inside a heading has been rewritten, that text contains an anchor, and the table of contents prints `<a class="gloss-ref" href="…">machine learning</a>` verbatim. Verified against v0.7.0. The manuscript has 8 markers on heading lines. Fixing it in `_heading_unit` rather than `fill_toc` serves every consumer of `Unit.heading` at once.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_parse.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_parse.py -v -k heading_label or unlisted`
Expected: FAIL — the label still contains `<a class=…>`; the hidden heading is listed.

- [ ] **Step 3: Implement**

In `scriptorium/parse.py`, add near `_slug`:

```python
_TAGS = re.compile(r"<[^>]+>")
```

In `_heading_unit`, strip tags when the label is built and keep the classes on the unit:

```python
    label = _HEADING.match(src).group(1) if _HEADING.match(src) else None
    if label:
        # The label feeds the TOC and any other text consumer, so it must be
        # text. Inline HTML reaches a heading legitimately — the glossary
        # pre-processor puts it there — and escaping it into the TOC prints
        # the markup.
        label = _TAGS.sub("", label)
```

Extend the returned `Unit` so `fill_toc` can see the classes:

```python
    return Unit(html=html, keep_together=False, name="prose",
                heading=label, heading_level=level, heading_id=hid,
                heading_classes=tuple(classes))
```

Add the field to `Unit` in `scriptorium/model.py`:

```python
    heading_classes: tuple[str, ...] = ()
```

In `fill_toc`, skip the unlisted ones:

```python
    heads = [u for u in units
             if u.heading_id and 1 <= u.heading_level <= depth
             and "unlisted" not in u.heading_classes]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_parse.py -v`
Expected: all pass

- [ ] **Step 5: Mutation-check the TOC fix**

Temporarily revert the `_TAGS.sub` line, run the test, and confirm it goes red. Restore it. A test that cannot fail is worth less than none.

- [ ] **Step 6: Run the whole suite and commit**

```bash
uv run pytest
git add scriptorium/parse.py scriptorium/model.py tests/test_parse.py
git commit -m "fix(parse): a heading label is text, and .unlisted stays out of the TOC"
```

---

### Task 7: The glossary joins the apparatus family

**Files:**
- Create: `themes/base/components/glossary.html`
- Modify: `themes/base/theme.yml`, `themes/base/styles.css:127-149`
- Test: `tests/test_glossary.py`

**Interfaces:**
- Consumes: the `::: glossary` component emitted in Task 3.
- Produces: `glossary-label` var; `.gloss-ref`, `.gloss-back`, `.gloss-term`, `.glossary` styling.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_glossary.py`:

```python
def test_glossary_section_has_no_heading_without_the_label(tmp_path):
    src = ("---\ntheme: article\ntitle: T\n"
           "glossary:\n  ai-effect:\n    term: \"AI effect\"\n    definition: \"A pattern.\"\n"
           "---\n\n# H\n\nThe [~ai-effect].\n\n::: glossary\n:::\n")
    out = tmp_path / "nolabel.pdf"
    render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "A pattern." in text
    assert "Glossary" not in text and "GLOSSARY" not in text


def test_glossary_label_becomes_the_section_heading(tmp_path):
    src = ("---\ntheme: article\ntitle: T\nglossary-label: Glosario\n"
           "glossary:\n  ai-effect:\n    term: \"AI effect\"\n    definition: \"A pattern.\"\n"
           "---\n\n# H\n\nThe [~ai-effect].\n\n::: glossary\n:::\n")
    out = tmp_path / "label.pdf"
    render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "Glosario" in text      # the label the author chose, not a baked-in string
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_glossary.py -v -k label`
Expected: FAIL — no `glossary.html` component, so the label never renders.

- [ ] **Step 3: Create the component**

`themes/base/components/glossary.html` — the same shape as `references.html`:

```html
<section class="glossary{{#glossary-label}} labelled{{/glossary-label}}">{{#glossary-label}}<h2 class="apparatus-title">{{glossary-label}}</h2>{{/glossary-label}}{{content}}</section>
```

- [ ] **Step 4: Declare the var and the hint**

In `themes/base/theme.yml`, beside `references-label`:

```yaml
  # Heading for the generated glossary, on the same contract as
  # references-label: empty means no heading, because the label's language is
  # the document's business — "Glossary", "Glosario", whatever the venue wants.
  glossary-label: ""
```

and in the `components:` block:

```yaml
  glossary:
    keep_together: false   # and a five-hundred-entry glossary most of all
```

This hint is not optional. A named `:::` component defaults to `keep_together: True`, which emits `class="keep"` and `break-inside: avoid` — a forty-page unbreakable block.

- [ ] **Step 5: Style it with the family**

In `themes/base/styles.css`, collapse the shared apparatus declarations and add the glossary. Replace the separate `.footnotes` / `.references` rule, margin and type-scale lines with:

```css
/* the apparatus sections: endnotes, references, glossary */
.footnotes, .references, .glossary {
  margin-top: 6mm; padding-top: 3mm; border-top: 0.3mm solid var(--rule);
}
.footnotes.labelled, .references.labelled, .glossary.labelled {
  border-top: none; padding-top: 0;
}
.footnotes ol, .references ol, .glossary p {
  font-size: 9pt; line-height: 1.45; margin: 0;
}
.footnotes ol, .references ol { padding-left: 6mm; }
.footnotes li, .references li, .glossary p { margin: 0 0 1.5mm 0; }
.footnotes a, .references a, .glossary a { color: var(--accent-dark); border-bottom: none; }

/* A glossed term is ordinary words, not a bracketed number, so it carries an
   underline the citation mark does not need. */
.gloss-ref { color: var(--accent-dark); text-decoration: none;
             border-bottom: 0.4pt dotted currentColor; }
.cite-back::after, .gloss-back::after {
  content: target-counter(attr(href url), page);
  font-variant-numeric: tabular-nums;
}
```

Keep `.apparatus-title` and the existing `.cite-ref` / `.footnote-ref` marker rules as they are.

- [ ] **Step 5b: Verify the consolidation changed nothing**

Render `examples/article.md` before and after, and compare the two PDFs page for page. The references and footnotes sections must look identical — this refactor is meant to be invisible.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_glossary.py -v`
Expected: all pass

- [ ] **Step 7: Run the whole suite and commit**

```bash
uv run pytest
git add themes/base/components/glossary.html themes/base/theme.yml themes/base/styles.css tests/test_glossary.py
git commit -m "feat(themes): the glossary joins the apparatus family"
```

---

### Task 8: Parts and unnumbered chapters in the `book` theme

**Files:**
- Modify: `themes/book/styles.css:6-27`
- Test: `tests/test_book.py`

**Interfaces:**
- Consumes: `heading_classes` from Task 6 (only indirectly — the classes already reach the `<h1>` via `_heading_unit`).
- Produces: `{.part}` and `{.unnumbered}` heading behaviour in `book`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_book.py`:

```python
def test_front_matter_and_parts_do_not_consume_chapter_numbers(tmp_path):
    from scriptorium.galley import render_pdf

    src = ("---\ntheme: book\ntitle: T\n---\n\n"
           "# Preface {.unnumbered}\n\nBody.\n\n"
           "# Foundations {.part}\n\nBody.\n\n"
           "# Classical AI\n\nBody.\n")
    out = tmp_path / "b.pdf"
    render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    # Compare whitespace-insensitively: pdftotext's line breaks between a
    # numeral and its title are a layout detail, not the thing under test.
    compact = "".join(text.split())
    # The first real chapter is 1, not 3: neither the preface nor the part
    # increments the chapter counter.
    assert "1ClassicalAI" in compact
    assert "PartIFoundations" in compact
    assert "1Preface" not in compact and "2Preface" not in compact
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_book.py -v -k parts`
Expected: FAIL — *Classical AI* is chapter 3 and no part label appears.

- [ ] **Step 3: Implement**

In `themes/book/styles.css`, extend the counter reset on `body`:

```css
  counter-reset: chapter part;
```

and add after the existing `h1::before` rule:

```css
/* Front matter and part dividers are headings, not chapters: neither takes a
   chapter number, so the first real chapter is 1. */
h1.unnumbered { counter-increment: none; }
h1.unnumbered::before { content: none; }

h1.part { counter-increment: part; }
h1.part::before {
  content: "Part " counter(part, upper-roman);
  font-size: 18pt; font-weight: 600; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--accent); margin-bottom: 4mm;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_book.py -v -k parts`
Expected: PASS

- [ ] **Step 5: Look at the pages**

Render the test document and open the PDF. Confirm the preface has no numeral, the part page reads "Part I / Foundations" and looks like a divider rather than a chapter, and *Classical AI* carries the numeral 1.

- [ ] **Step 6: Run the whole suite and commit**

```bash
uv run pytest
git add themes/book/styles.css tests/test_book.py
git commit -m "feat(book): {.part} and {.unnumbered} keep chapter numbering honest"
```

---

### Task 9: The glossary as a chapter in `book`

**Files:**
- Modify: `themes/book/styles.css`
- Test: manual visual check

**Interfaces:**
- Consumes: `.glossary` from Task 7, `{.unnumbered}` from Task 8.
- Produces: glossary presentation inside a book.

- [ ] **Step 1: Add the overrides**

In `themes/book/styles.css`:

```css
/* In a book the glossary is a chapter — `# Glossary {.unnumbered}` followed by
   `::: glossary` — so the apparatus rule would double against the chapter
   title. In article/note, where the section trails the text, the rule stays. */
.glossary { border-top: none; padding-top: 0; margin-top: 0; }
.glossary p { text-indent: 0; }      /* body paragraphs are indented; entries are not */
```

- [ ] **Step 2: Render and look**

```bash
cd examples/book && uv run scriptorium render scriptorium.yaml
```

Add a `glossary:` and a `# Glossary {.unnumbered}` / `::: glossary` chapter to the example project first. Open the PDF: entries must be flush left, not indented, and there must be no stray rule under the chapter title.

- [ ] **Step 3: Run the whole suite and commit**

```bash
uv run pytest
git add themes/book/styles.css examples/book/
git commit -m "feat(book): the glossary reads as a chapter, not a trailing section"
```

---

### Task 10: A cover master for `book`

**Files:**
- Create: `themes/book/masters/cover.html`
- Modify: `themes/book/theme.yml`, `themes/book/styles.css`
- Test: `tests/test_book.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `::: cover` full-page component driven by a `cover-image` var.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_book.py`:

```python
def test_cover_master_renders_a_full_page(tmp_path):
    from scriptorium.galley import render_pdf

    import base64
    # The canonical 1x1 transparent PNG — a real decodable image, because
    # WeasyPrint drops one it cannot parse and the page count would still be 2.
    (tmp_path / "c.png").write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGA"
        "hKmMIQAAAABJRU5ErkJggg=="))
    src = ("---\ntheme: book\ntitle: T\ncover-image: c.png\n---\n\n"
           "::: cover\n:::\n\n# One\n\nBody.\n")
    out = tmp_path / "cov.pdf"
    report = render_pdf(src, str(out), base_url=str(tmp_path) + "/",
                        cwd=str(tmp_path), execute=False)

    assert report.n_pages == 2      # the cover is its own page
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_book.py -v -k cover`
Expected: FAIL — `::: cover` is an unknown component and renders as a plain div, so the page count is 1.

- [ ] **Step 3: Create the master**

`themes/book/masters/cover.html`:

```html
<img class="cover-img" src="{{cover-image}}" alt="">
```

In `themes/book/theme.yml`, under `masters:` and `components:`:

```yaml
  cover:     { classes: "coverpage", furniture: none }
```
```yaml
  cover: { master: cover }
```

and add the var beside `title`:

```yaml
  cover-image: ""
```

In `themes/book/styles.css`:

```css
/* The cover is the one page with no margin: the artwork is the page. */
.page.coverpage { padding: 0; overflow: hidden; }
.cover-img { width: 100%; height: 100%; object-fit: cover; display: block; }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_book.py -v -k cover`
Expected: PASS

- [ ] **Step 5: Verify it visually with a real image**

Render a document whose `cover-image` is an actual cover (the manuscript's `covers/mhai-cover-v4.jpg` will do) and open page 1. It must be full-bleed — no white margin on any edge. A page count of 2 does not prove that.

- [ ] **Step 6: Run the whole suite and commit**

```bash
uv run pytest
git add themes/book/masters/cover.html themes/book/theme.yml themes/book/styles.css tests/test_book.py
git commit -m "feat(book): a cover master puts the artwork on page one"
```

---

### Task 11: Prove the links resolve in the PDF

**Files:**
- Modify: `pyproject.toml` (dev group)
- Test: `tests/test_glossary.py`

**Interfaces:**
- Consumes: everything above.
- Produces: the acceptance check for the whole feature.

**Why a new dependency:** every other PDF-level test in this repo asserts on `pdftotext` output, and for citations that works because the mark is the visible text `↩ 2`. A glossary's forward link carries **no text of its own** — it is the word in the sentence — so no text assertion can distinguish a working link from coloured, underlined, dead text. Only the PDF's link annotations can, and reading those needs `pypdf`.

- [ ] **Step 1: Add the dev dependency**

In `pyproject.toml`:

```toml
[dependency-groups]
dev = ["pytest>=8", "pypdf>=5"]
```

Run: `uv sync`

- [ ] **Step 2: Write the failing test**

Append to `tests/test_glossary.py`:

```python
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

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "↩ 1" in text          # and the back-link resolved to a real page
```

- [ ] **Step 3: Run the test to verify it passes**

Run: `uv run pytest tests/test_glossary.py -v -k both_directions`
Expected: PASS

- [ ] **Step 4: Mutation-check it**

Temporarily change `.gloss-back::after` in `themes/base/styles.css` to `content: "x"`. Run the test and confirm the `↩ 1` assertion fails. Then temporarily drop the `href` from the anchor in `mark_terms` and confirm the first assertion fails. Restore both. A gate that cannot fail licenses shipping.

- [ ] **Step 5: Run the whole suite and commit**

```bash
uv run pytest
git add pyproject.toml uv.lock tests/test_glossary.py
git commit -m "test(glossary): assert the link annotations, not the styling"
```

---

### Task 12: Acceptance against the real manuscript

**Files:**
- None in this repo. Read-only against `../books-mhai`.

**Interfaces:**
- Consumes: the whole feature.
- Produces: a go/no-go on the design's acceptance criteria.

- [ ] **Step 1: Build a throwaway project**

Convert `../books-mhai/_filters/glossary_data.lua` to YAML and rewrite the 584 markers in a scratch copy under `.playground/`. This is the one-time migration the spec describes — it does not belong in either repo yet.

`~/Workspace/.playground/mhai-scriptorium/prep.py` already does most of this, from the smoke test that produced the spec's measurements: it parses `glossary_data.lua` without a Lua interpreter and rewrites the spans. Two things in it are now wrong and must be changed before reuse — it emits the old `gls-` / `gb-` anchor names rather than `gloss-` / `glossref-`, and its `HEAD_ATTR` pass strips the braces off any marker that ends a heading line, silently destroying 8 of them. That second bug is what surfaced the TOC defect in Task 6.

- [ ] **Step 2: Render it**

```bash
uv run scriptorium render scriptorium.yaml
```

- [ ] **Step 3: Check the acceptance criteria**

- Renders with no warnings.
- Chapter numbering starts at 1; the three front-matter chapters carry no numeral.
- The three part index files render as part dividers, not chapters.
- 498 of the 515 entries carry a page list.
- The table of contents contains no `<` anywhere.

- [ ] **Step 4: Open the PDF and look at it**

Page 1 (cover), the TOC, a part divider, a chapter opener, a body page with glossed terms, and two glossary pages. Green tests do not catch "the glossary is indented" or "the part divider looks like a chapter".

- [ ] **Step 5: Report**

If every criterion holds, the feature is done and the `books-mhai` migration can be planned as its own piece of work. If not, file what failed — do not patch the manuscript to make the engine look good.

---

### Task 13: Documentation

**Files:**
- Modify: `README.md` (the Authoring section), `CHANGELOG.md`, `docs/design.md`, `AGENTS.md`, `tasks.md`

- [ ] **Step 1: README**

In the Authoring bullet list, after the Citations bullet:

```markdown
- **Glossary** — `[~key]` renders the term as declared; `[display]{~key}` supplies
  its own text. Entries come from `glossary:` — a mapping, or a path to a YAML
  file of one — and collect into a `::: glossary` section, alphabetical by term,
  each with the pages where it appears. `glossary-label:` gives the section a
  heading; empty means none.
```

Add `css:` to the project-file example:

```yaml
theme: book
css: book.css          # a project's own stylesheet, after the theme's
glossary: glossary.yaml
```

- [ ] **Step 2: AGENTS.md**

Add `glossary.py` to the pipeline list, beside `citations.py`:

```markdown
- **`glossary.py`** — `[~key]` / `[display]{~key}` markers against a declared
  `glossary:` map → a sorted `::: glossary` section with page back-links. Runs on
  the raw source **after `citations.py`**, so a term glossed inside a note body is
  paged where the note renders. Markers nest; only the innermost matches, and the
  outer of a nested pair keeps an anchor but not a link.
```

- [ ] **Step 3: CHANGELOG**

Under a new `## Unreleased` heading, with `### Added` and `### Fixed` sections covering: the glossary, the `css:` key, `{.part}` / `{.unnumbered}` in `book`, the cover master, and the heading-label fix.

- [ ] **Step 4: docs/design.md**

Add a glossary section beside the citations one, stating the pipeline position and the nesting rule.

- [ ] **Step 5: tasks.md**

Tick the glossary item and link this plan.

- [ ] **Step 6: Commit**

```bash
git add README.md AGENTS.md CHANGELOG.md docs/design.md tasks.md
git commit -m "docs(glossary): document the glossary, css: and the book apparatus"
```
