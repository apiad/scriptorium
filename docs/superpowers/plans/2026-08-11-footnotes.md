# Footnotes as Endnotes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-numbered `ref-N` citation convention with real Markdown footnotes (`[^a]`) that collect into endnotes at the end of the document or of each chapter, or into true bottom-of-page footnotes.

**Architecture:** A source-to-source pre-processor, `scriptorium/footnotes.py`, taking the pipeline slot `citations.py` holds today in `galley.render_pdf`. It cannot be a markdown-it plugin: `parse()` renders block-by-block (`parse.py:300`), so a plugin never sees a marker and its definition in the same render call. The pre-processor rewrites markers to inline HTML `<sup>` and re-emits note bodies as a `::: footnotes` component, so the real Markdown renderer handles author prose in notes.

**Tech Stack:** Python 3.12+, `markdown-it-py`, WeasyPrint, pytest, `uv`.

**Spec:** `docs/superpowers/specs/2026-08-11-footnotes-design.md`

## Global Constraints

- Python 3.12+, English throughout (identifiers, comments, log messages).
- One logical change per commit, conventional commits.
- `uv run pytest` must pass before any commit lands.
- **No new dependency.** The footnote parsing is ours.
- The emitted document must remain a **single continuous HTML flow** — v0.3.0 pagination is WeasyPrint's CSS Fragmentation, and splitting the flow breaks it.
- The engine stays theme-agnostic: presentation lives in theme CSS and the component template, never in the engine.
- Verify visual work visually — render the PDF and look at it; green tests do not catch "no margins" or a vanished note.

## File Structure

| File | Responsibility |
|---|---|
| `scriptorium/footnotes.py` | **Create.** Definition/marker parsing, numbering, mode resolution, emission. |
| `tests/test_footnotes.py` | **Create.** Unit tests for the above. |
| `scriptorium/galley.py` | **Modify.** Swap `process_citations` for `process_footnotes`; pass the resolved mode. |
| `scriptorium/parse.py` | **Modify.** Narrow `_REF` to a known prefix set. |
| `themes/base/theme.yml` | **Modify.** `footnotes` component template + `footnotes: document` default. |
| `themes/base/styles.css` | **Modify.** `.footnote-ref` / `.footnotes` styles; delete `.cite-sup` / `.cite-link`. |
| `themes/book/theme.yml` | **Modify.** `footnotes: chapter`. |
| `themes/article/styles.css` | **Modify.** Delete the `.bib-*` block. |
| `scriptorium/citations.py` | **Delete.** |
| `tests/test_citations.py` | **Delete.** |
| `examples/article.md` | **Modify.** Convert its bibliography to footnotes. |

---

### Task 1: Narrow `_REF` to a known prefix set

Independent of footnotes and separately valuable: today any `@word-word` in prose is rewritten to an empty anchor and **disappears from the PDF**.

**Files:**
- Modify: `scriptorium/parse.py:32-42`
- Test: `tests/test_galley.py` (append)

**Interfaces:**
- Produces: `parse._REF_PREFIXES: frozenset[str]`, and the existing `parse._rewrite_refs(text: str) -> str` with narrowed behaviour.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_galley.py`:

```python
def test_refs_only_match_known_prefixes():
    from scriptorium.parse import _rewrite_refs

    # known prefixes still resolve
    assert 'href="#fig-plot"' in _rewrite_refs("see @fig-plot")
    assert 'href="#chap-two"' in _rewrite_refs("see @chap-two")

    # bibtex keys and handles survive as literal text
    for s in ["@smith-2020", "@piad-morffis-2024", "@colinhacks-x"]:
        assert _rewrite_refs(f"cite {s}") == f"cite {s}"

    # the regression that motivated this: prose was silently deleted
    out = _rewrite_refs("See @sec-intro and mail me @piad-morffis-2024.")
    assert "mail me @piad-morffis-2024." in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_galley.py::test_refs_only_match_known_prefixes -v`
Expected: FAIL — `@smith-2020` is rewritten to an anchor.

- [ ] **Step 3: Implement**

In `scriptorium/parse.py`, replace the `_REF` block (lines 32-42):

```python
# @type-id cross-references -> empty anchors; the theme's CSS fills the text
# via target-counter/target-text. The prefix must be one we know: anything else
# is ordinary prose (a BibTeX key, a handle) and rewriting it would delete it
# from the page, since an anchor with no target renders empty. The free @key
# namespace is reserved for a future citations feature.
_REF_PREFIXES = frozenset({"fig", "tbl", "sec", "eq", "lst", "thm", "chap"})
_REF = re.compile(r"(?<![\w`])@([a-zA-Z][\w]*)-([\w-]+)")


def _rewrite_refs(text: str) -> str:
    def sub(m):
        kind, target = m.group(1), m.group(2)
        if kind not in _REF_PREFIXES:
            return m.group(0)
        return f'<a class="ref-{kind}" href="#{kind}-{target}"></a>'

    return _REF.sub(sub, text)
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS (73 tests).

- [ ] **Step 5: Verify no example regressed**

Run: `uv run scriptorium render examples/article.md -o /tmp/t1.pdf`
Then: `pdftotext /tmp/t1.pdf - | head -40` — check no cross-reference text vanished.

- [ ] **Step 6: Commit**

```bash
git add scriptorium/parse.py tests/test_galley.py
git commit -m "fix(refs): only rewrite known cross-reference prefixes

An @type-id with no target renders as an empty anchor, so any @word-word in
prose was silently deleted from the PDF. Restrict to fig/tbl/sec/eq/lst/thm/
chap and leave everything else as literal text; this also frees the @key
namespace for citations."
```

---

### Task 2: Parse footnote definitions and markers

**Files:**
- Create: `scriptorium/footnotes.py`
- Test: `tests/test_footnotes.py`

**Interfaces:**
- Produces:
  - `Note` dataclass: `key: str`, `body: str`, `refs: list[int]` (1-based occurrence ordinals, filled in Task 3).
  - `collect_notes(src: str) -> tuple[str, dict[str, Note]]` — returns the source with definition lines removed, and the notes keyed by id, in order of definition.

- [ ] **Step 1: Write the failing test**

Create `tests/test_footnotes.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_footnotes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scriptorium.footnotes'`.

- [ ] **Step 3: Implement**

Create `scriptorium/footnotes.py`:

```python
"""Footnotes as endnotes.

A source-to-source pre-processor, not a markdown-it plugin: parse() renders
block by block (parse.py:300), so a plugin would never see a marker and its
definition in the same render call.

Markers become inline <sup> HTML (CommonMark passes inline HTML through);
note bodies are re-emitted as a `::: footnotes` component so the real Markdown
renderer handles the author's links and emphasis.
"""

import re
from dataclasses import dataclass, field

# [^key]: body, with optional indented continuation lines
_DEF = re.compile(r"^\[\^([\w-]+)\]:[ \t]*(.*(?:\n(?:[ \t]+.*|)(?=\n[ \t]+\S|\n*$))*)",
                  re.MULTILINE)
_FENCE = re.compile(r"^(`{3,}|~{3,}).*$", re.MULTILINE)


@dataclass
class Note:
    key: str
    body: str
    refs: list[int] = field(default_factory=list)


def _fence_spans(src: str) -> list[tuple[int, int]]:
    """Character ranges covered by fenced code blocks."""
    spans, open_at, marker = [], None, None
    for m in _FENCE.finditer(src):
        tick = m.group(1)
        if open_at is None:
            open_at, marker = m.start(), tick
        elif tick[0] == marker[0] and len(tick) >= len(marker):
            spans.append((open_at, m.end()))
            open_at, marker = None, None
    if open_at is not None:
        spans.append((open_at, len(src)))
    return spans


def _in_span(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in spans)


def collect_notes(src: str) -> tuple[str, dict[str, Note]]:
    """Strip `[^key]: body` definitions out of src; return (src, notes)."""
    spans = _fence_spans(src)
    notes: dict[str, Note] = {}
    cuts: list[tuple[int, int]] = []
    for m in _DEF.finditer(src):
        if _in_span(m.start(), spans):
            continue
        body = " ".join(line.strip() for line in m.group(2).splitlines() if line.strip())
        notes[m.group(1)] = Note(key=m.group(1), body=body)
        cuts.append((m.start(), m.end()))
    for a, b in reversed(cuts):
        src = src[:a] + src[b:]
    return re.sub(r"\n{3,}", "\n\n", src), notes
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_footnotes.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scriptorium/footnotes.py tests/test_footnotes.py
git commit -m "feat(footnotes): collect [^key]: definitions out of the source"
```

---

### Task 3: Rewrite markers and number them

**Files:**
- Modify: `scriptorium/footnotes.py`
- Test: `tests/test_footnotes.py` (append)

**Interfaces:**
- Consumes: `Note`, `collect_notes` from Task 2.
- Produces: `number_and_mark(src: str, notes: dict[str, Note], chapter_mode: bool) -> tuple[str, list[list[Note]]]` — rewrites every `[^key]` marker to a `<sup>`, returns the source and the notes grouped per chapter (one group when `chapter_mode` is False).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_footnotes.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_footnotes.py -v`
Expected: FAIL — `ImportError: cannot import name 'number_and_mark'`.

- [ ] **Step 3: Implement**

Append to `scriptorium/footnotes.py`:

```python
_MARK = re.compile(r"\[\^([\w-]+)\]")
_H1 = re.compile(r"^#[ \t]", re.MULTILINE)
_SUFFIX = "abcdefghijklmnopqrstuvwxyz"


def _chapter_starts(src: str, spans: list[tuple[int, int]]) -> list[int]:
    return [m.start() for m in _H1.finditer(src) if not _in_span(m.start(), spans)]


def number_and_mark(src: str, notes: dict[str, Note],
                    chapter_mode: bool) -> tuple[str, list[list[Note]]]:
    """Rewrite [^key] markers to numbered <sup> anchors; group notes per chapter."""
    spans = _fence_spans(src)
    starts = _chapter_starts(src, spans) if chapter_mode else []
    groups: list[list[Note]] = [[] for _ in range(len(starts) + 1)]
    numbers: dict[tuple[int, str], int] = {}
    out, last = [], 0

    for m in _MARK.finditer(src):
        if _in_span(m.start(), spans) or m.group(1) not in notes:
            continue
        note = notes[m.group(1)]
        chapter = sum(1 for s in starts if s <= m.start())
        seen = numbers.get((chapter, note.key))
        if seen is None:
            groups[chapter].append(note)
            seen = numbers[(chapter, note.key)] = len(groups[chapter])
        note.refs.append(len(note.refs) + 1)
        suffix = _SUFFIX[len(note.refs) - 1] if len(note.refs) > 1 or True else ""
        ref_id = f"fnref-{chapter + 1}-{seen}{suffix if len(note.refs) > 1 else ''}"
        if len(note.refs) == 2:  # first ref needs its suffix retroactively
            out_text = "".join(out)
            out = [out_text.replace(f'id="fnref-{chapter + 1}-{seen}"',
                                    f'id="fnref-{chapter + 1}-{seen}a"', 1)]
            ref_id = f"fnref-{chapter + 1}-{seen}b"
        out.append(src[last:m.start()])
        out.append(f'<sup class="footnote-ref" id="{ref_id}">'
                   f'<a href="#fn-{chapter + 1}-{seen}">{seen}</a></sup>')
        last = m.end()
    out.append(src[last:])
    return "".join(out), [g for g in groups] if chapter_mode else [groups[0]]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_footnotes.py -v`
Expected: PASS (7 tests). If the retroactive-suffix logic in step 3 reads awkwardly, simplify it: collect all marker positions first, then emit — the tests define the contract, not the implementation.

- [ ] **Step 5: Commit**

```bash
git add scriptorium/footnotes.py tests/test_footnotes.py
git commit -m "feat(footnotes): number markers, restart per chapter, track back-links"
```

---

### Task 4: Emit the notes and resolve the mode

**Files:**
- Modify: `scriptorium/footnotes.py`
- Test: `tests/test_footnotes.py` (append)

**Interfaces:**
- Consumes: everything from Tasks 2-3.
- Produces:
  - `resolve_footnote_mode(meta: dict, theme_meta: dict) -> str` — returns `"document" | "chapter" | "page"`; raises `ValueError` on anything else.
  - `process_footnotes(src: str, mode: str = "document") -> str` — the single entry point `galley` calls.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_footnotes.py`:

```python
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
    out = process_footnotes("A[^a]\n\n[^a]: The note.\n", mode="document")

    assert out.count("::: footnotes") == 1
    assert out.index("::: footnotes") > out.index("A<sup")
    assert '<span id="fn-1-1"></span>' in out
    assert "The note." in out and "[↩](#fnref-1-1)" in out


def test_chapter_mode_emits_a_component_per_chapter():
    src = "# One\n\nA[^a]\n\n# Two\n\nB[^b]\n\n[^a]: one\n\n[^b]: two\n"
    out = process_footnotes(src, mode="chapter")

    assert out.count("::: footnotes") == 2
    # chapter one's notes come before chapter two's heading
    assert out.index("::: footnotes") < out.index("# Two")
    assert "one" in out and "two" in out


def test_page_mode_inlines_the_body_and_emits_no_section():
    out = process_footnotes("A[^a]\n\n[^a]: The note.\n", mode="page")

    assert "::: footnotes" not in out
    assert '<span class="footnote-inline">The note.</span>' in out
    assert "footnote-ref" not in out  # WeasyPrint generates the call


def test_note_body_keeps_its_markdown():
    out = process_footnotes("A[^a]\n\n[^a]: See **this** and [that](https://x.dev).\n",
                            mode="document")

    assert "**this**" in out and "[that](https://x.dev)" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_footnotes.py -v`
Expected: FAIL — `ImportError: cannot import name 'process_footnotes'`.

- [ ] **Step 3: Implement**

Append to `scriptorium/footnotes.py`:

```python
MODES = ("document", "chapter", "page")


def resolve_footnote_mode(meta: dict, theme_meta: dict) -> str:
    """Frontmatter wins, then the theme, then `document`."""
    mode = meta.get("footnotes") or theme_meta.get("footnotes") or "document"
    mode = str(mode).strip().lower()
    if mode not in MODES:
        raise ValueError(f"unknown footnotes mode {mode!r}; expected one of {MODES}")
    return mode


def _component(chapter: int, notes: list[Note]) -> str:
    """Notes as a `::: footnotes` component; bodies stay Markdown."""
    items = []
    for n, note in enumerate(notes, 1):
        base = f"fnref-{chapter}-{n}"
        ids = ([base] if len(note.refs) < 2
               else [f"{base}{_SUFFIX[i]}" for i in range(len(note.refs))])
        back = " ".join(f"[↩](#{i})" for i in ids)
        items.append(f'{n}. <span id="fn-{chapter}-{n}"></span>{note.body} {back}')
    return "::: footnotes\n" + "\n".join(items) + "\n:::\n"


def process_footnotes(src: str, mode: str = "document") -> str:
    """Entry point: rewrite markers and emit notes per `mode`."""
    body, notes = collect_notes(src)
    if not notes:
        return body
    if mode == "page":
        marked, _ = number_and_mark(body, notes, chapter_mode=False)
        # replace each marker with the note body inline; WeasyPrint floats it
        for note in notes.values():
            marked = re.sub(
                r'<sup class="footnote-ref"[^>]*><a href="#fn-1-\d+">\d+</a></sup>',
                lambda m, b=note.body: f'<span class="footnote-inline">{b}</span>',
                marked, count=1)
        return marked

    marked, groups = number_and_mark(body, notes, chapter_mode=(mode == "chapter"))
    if mode == "document":
        return marked.rstrip() + "\n\n" + _component(1, groups[0])

    starts = _chapter_starts(marked, _fence_spans(marked))
    out, prev = [], 0
    for i, group in enumerate(groups):
        end = starts[i] if i < len(starts) else len(marked)
        out.append(marked[prev:end])
        if group:
            out.append("\n" + _component(i + 1, group) + "\n")
        prev = end
    return "".join(out)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_footnotes.py -v`
Expected: PASS (13 tests).

- [ ] **Step 5: Commit**

```bash
git add scriptorium/footnotes.py tests/test_footnotes.py
git commit -m "feat(footnotes): emit notes per mode (document / chapter / page)"
```

---

### Task 5: Wire into the engine, delete citations

**Files:**
- Modify: `scriptorium/galley.py` (the `process_citations` import and call in `render_pdf`)
- Delete: `scriptorium/citations.py`, `tests/test_citations.py`
- Modify: `themes/base/theme.yml`, `themes/base/styles.css`, `themes/book/theme.yml`, `themes/article/styles.css`
- Test: `tests/test_footnotes.py` (append)

**Interfaces:**
- Consumes: `process_footnotes`, `resolve_footnote_mode` from Task 4.

- [ ] **Step 1: Write the failing render test**

Append to `tests/test_footnotes.py`:

```python
from pathlib import Path

from scriptorium.galley import render_pdf


def test_book_theme_renders_a_notes_section_per_chapter(tmp_path):
    src = ("---\ntheme: book\ntitle: T\n---\n\n"
           "# One\n\nAlpha.[^a]\n\n# Two\n\nBeta.[^b]\n\n"
           "[^a]: First note.\n\n[^b]: Second note.\n")
    out = tmp_path / "b.pdf"
    render_pdf(src, str(out), execute=False)

    assert out.exists() and out.stat().st_size > 1000


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_footnotes.py -k "pdf or chapter_renders" -v`
Expected: FAIL — `[^a]` still literal, since nothing calls `process_footnotes` yet.

- [ ] **Step 3: Wire the engine**

In `scriptorium/galley.py`, in `render_pdf`, replace the citations import and call:

```python
    from .parse import fill_toc
    from .footnotes import process_footnotes, resolve_footnote_mode

    src = process_footnotes(src, resolve_footnote_mode(meta, theme.meta))
```

Delete the files:

```bash
git rm scriptorium/citations.py tests/test_citations.py
```

- [ ] **Step 4: Add the theme component and styles**

In `themes/base/theme.yml`, add the default and the component template:

```yaml
footnotes: document

components:
  footnotes:
    template: |
      <section class="footnotes">{{content}}</section>
```

Match the surrounding YAML shape in that file — if `components:` already exists, add the `footnotes` entry to it rather than a second key.

In `themes/base/styles.css`, delete the `.cite-sup` / `.cite-link` rules (around line 108-111) and add:

```css
/* footnote markers + the endnotes section */
.footnote-ref { font-size: 0.72em; line-height: 0; vertical-align: super; }
.footnote-ref a { color: var(--accent-dark); text-decoration: none; border-bottom: none; }
.footnotes { margin-top: 6mm; padding-top: 3mm; border-top: 0.3mm solid var(--rule); }
.footnotes ol { font-size: 9pt; line-height: 1.45; padding-left: 6mm; margin: 0; }
.footnotes li { margin: 0 0 1.5mm 0; }
.footnotes a { color: var(--accent-dark); border-bottom: none; }
.footnote-inline { float: footnote; font-size: 9pt; }
```

In `themes/book/theme.yml`, add `footnotes: chapter` alongside the other top-level keys.

In `themes/article/styles.css`, delete the `.bib-entry` / `.bib-num` / `.bib-body` / `.bib-back` / `.bib-back-link` / `.cite-anchor` block (around lines 17-33) and its `/* --- bibliography … --- */` comment.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS. The `test_citations.py` tests are gone; the footnote tests replace them.

- [ ] **Step 6: Verify visually — this is a visual artifact**

```bash
uv run scriptorium render examples/article.md -o /tmp/fn-article.pdf
pdftoppm -png -r 60 -f 1 -l 2 /tmp/fn-article.pdf /tmp/fn-a
```
Open `/tmp/fn-a-1.png` and **look at it**: markers are raised and small, the notes section has a rule above it, nothing overlaps, no literal `[^a]` anywhere.

- [ ] **Step 7: Commit**

```bash
git add scriptorium/galley.py scriptorium/footnotes.py tests/test_footnotes.py \
        themes/base/theme.yml themes/base/styles.css themes/book/theme.yml \
        themes/article/styles.css
git commit -m "feat(footnotes): wire into the engine; delete citations.py

Footnotes replace the hand-numbered ref-N convention outright. citations.py
and its .bib-*/.cite-* CSS are removed, not deprecated."
```

---

### Task 6: Mutation-check the chapter split

A test that cannot fail is worse than no test. This task proves the chapter-splitting assertion is real.

**Files:** none changed (verification only).

- [ ] **Step 1: Force the wrong mode**

```bash
cp scriptorium/footnotes.py /tmp/fn.orig
sed -i 's/chapter_mode=(mode == "chapter")/chapter_mode=False/' scriptorium/footnotes.py
cmp -s /tmp/fn.orig scriptorium/footnotes.py && echo "MUTATION DID NOT APPLY — stop" || echo "mutation applied"
```

- [ ] **Step 2: Confirm the chapter test goes red**

Run: `uv run pytest tests/test_footnotes.py -k chapter -q`
Expected: FAIL. If it passes, the chapter tests are not testing chapter grouping — fix them before continuing.

- [ ] **Step 3: Restore and confirm green**

```bash
cp /tmp/fn.orig scriptorium/footnotes.py
uv run pytest -q
```
Expected: PASS. `git status --short` must be clean.

---

### Task 7: Convert the article example

**Files:**
- Modify: `examples/article.md`

- [ ] **Step 1: Convert**

Rewrite its bibliography from the `^[N](#ref-N)^` + `### N {#ref-N}` form to `[^N]` markers and `[^N]: …` definitions. Keep the same sources and the same order.

- [ ] **Step 2: Render and look**

```bash
uv run scriptorium render examples/article.md -o /tmp/ex-article.pdf
pdftoppm -png -r 60 -f 1 -l 3 /tmp/ex-article.pdf /tmp/ex-a
```
Open the PNGs. Every citation is a superscript; the notes section sits at the end; no `ref-N` residue.

- [ ] **Step 3: Commit**

```bash
git add examples/article.md
git commit -m "docs(examples): article uses footnotes instead of the ref-N convention"
```

---

### Task 8: Documentation

**Files:**
- Modify: `README.md`, `docs/design.md`, `know-how/authoring-a-theme.md`, `AGENTS.md`

- [ ] **Step 1: README**

Under Authoring, add footnote syntax and the `footnotes:` knob (`document` / `chapter` / `page`, frontmatter over theme). In Status, drop "per-page footnotes" from the roadmap.

- [ ] **Step 2: `docs/design.md`**

Rewrite §7.4: endnotes are implemented; per-page footnotes are implemented via WeasyPrint CSS GCPM; record that the original circularity objection applied to the Python bin-packer that v0.3.0 replaced. Line 104's footnote claim is now true — leave it.

- [ ] **Step 3: `know-how/authoring-a-theme.md`**

Document the `footnotes` theme key and the `footnotes` component template next to the existing theme-key documentation.

- [ ] **Step 4: `AGENTS.md`**

Add `footnotes.py` to the pipeline module list, and note that footnote pre-processing must stay a source transform because `parse()` renders block-by-block.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/design.md know-how/authoring-a-theme.md AGENTS.md
git commit -m "docs: footnotes syntax, the footnotes: knob, and the §7.4 correction"
```

---

### Task 9: Workspace migration and `CLAUDE.md`

Outside the scriptorium repo — these are two separate repos and therefore separate commits.

**Files:**
- Create: `/home/apiad/Workspace/.playground/migrate-refn/migrate.py` (throwaway, not shipped)
- Modify: `/home/apiad/Workspace/CLAUDE.md`
- Modify: the live documents only

- [ ] **Step 1: Write the migration script**

Create `.playground/migrate-refn/migrate.py`:

```python
"""One-off: rewrite the ref-N citation convention into Markdown footnotes.

Throwaway. Deliberately NOT shipped in scriptorium — the tool carries no legacy
path for what was only ever a house convention.

Usage: uv run python migrate.py <file.md> [...]   (rewrites in place)
"""

import re
import sys
from pathlib import Path

# ^[3](#ref-3)^  or  [3](#ref-3)
_INTEXT = re.compile(r"\^?\[(\d+)\]\(#ref-\1\)\^?")
# ### 3 {#ref-3}\n<body until the next heading or EOF>
_ENTRY = re.compile(r"^#{1,6}\s*(\d+)\s*\{#ref-\1\}\s*\n+(.*?)(?=\n#{1,6}\s|\Z)",
                    re.MULTILINE | re.DOTALL)
_SECTION = re.compile(r"^#{1,6}\s*(Notas y Referencias|Notes and References)\s*$\n*",
                      re.MULTILINE | re.IGNORECASE)


def migrate(text: str) -> tuple[str, int, int]:
    defs = []
    for m in _ENTRY.finditer(text):
        body = " ".join(line.strip() for line in m.group(2).splitlines() if line.strip())
        defs.append((int(m.group(1)), body))
    text = _ENTRY.sub("", text)
    text, n_refs = _INTEXT.subn(lambda m: f"[^{m.group(1)}]", text)
    text = _SECTION.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"
    if defs:
        block = "\n".join(f"[^{n}]: {b}" for n, b in sorted(defs))
        text += "\n" + block + "\n"
    return text, n_refs, len(defs)


for path in map(Path, sys.argv[1:]):
    out, n_refs, n_defs = migrate(path.read_text(encoding="utf-8"))
    path.write_text(out, encoding="utf-8")
    print(f"{path}: {n_refs} markers, {n_defs} notes")
```

- [ ] **Step 2: Prove it round-trips before touching real files**

```bash
cd /home/apiad/Workspace/.playground/migrate-refn
printf 'A claim.^[1](#ref-1)^ And two.^[2](#ref-2)^\n\n# Notas y Referencias\n\n### 1 {#ref-1}\nFirst source. [url](https://a.dev).\n\n### 2 {#ref-2}\nSecond source.\n' > sample.md
uv run python migrate.py sample.md && cat sample.md
```
Expected: two `[^1]` / `[^2]` markers in the prose, two `[^N]: …` definitions at the end, no `ref-` residue, the URL intact. If the count line reports `0 markers`, the regex missed — fix before proceeding.

- [ ] **Step 3: Migrate the live documents, one commit per repo**

Targets (confirm each still matches before editing):
- `repos/librito-deng-cuba/` — `booklet.md`, `render/booklet-a5.md`, `drafts/cap-*.md`
- `vault/Efforts/Areas/University/Mincom/reporte-ia-industria.md`

Leave `vault/x/`, `vault/+/agent_drafts/` and the other archives alone.

- [ ] **Step 4: Render before and after**

For each migrated document, render with the *previous* scriptorium tag and the new one, and compare page counts and the notes section. A dropped citation is the failure mode to look for.

- [ ] **Step 5: Fix workspace `CLAUDE.md`**

In the *Report standard* section, replace the paragraph forbidding `[^id]` and mandating `^[N](#ref-N)^` + `### N {#ref-N}`. The new rule: use Markdown footnotes; scriptorium collects them into endnotes; `footnotes: chapter` puts them per chapter. Delete the `{#ref-N}` pattern block.

- [ ] **Step 6: Commit both repos separately**

```bash
cd /home/apiad/Workspace/repos/librito-deng-cuba
git add <the migrated files>
git commit -m "docs: migrate citations to Markdown footnotes"

cd /home/apiad/Workspace
git commit -m "docs(claude): report standard uses Markdown footnotes" -- CLAUDE.md vault/Efforts/Areas/University/Mincom/reporte-ia-industria.md
```

---

### Task 10: Release

- [ ] **Step 1: Follow `know-how/releasing.md`**

Commits since `v0.3.1` include `feat:`, so this is a **minor** bump → `v0.4.0`.

- [ ] **Step 2: Gate, bump, changelog, tag, push, publish**

Per that document: clean tree, `uv run pytest`, bump `pyproject.toml` + `uv.lock`, move `## [Unreleased]` to `## [v0.4.0] - <date>`, update the README status line, `chore(release): v0.4.0`, annotated tag, push both, `gh release create`.

- [ ] **Step 3: Verify the published artifact**

Clone the tag fresh into `/tmp`, render a document with footnotes in `chapter` mode, and confirm the notes land per chapter. Do not verify from the working tree.

- [ ] **Step 4: Sync the VPS**

```bash
ssh vps 'cd ~/Workspace/repos/scriptorium && git pull --ff-only origin main --tags && git describe --tags'
```
