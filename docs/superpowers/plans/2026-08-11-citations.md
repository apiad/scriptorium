# Numbered Citations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `[@key]` resolves against an author-declared bibliography, renders as a numbered `[1]`, and collects into a generated references section.

**Architecture:** A source-to-source pre-processor, `scriptorium/citations.py`, running in `galley.render_pdf` immediately after `process_footnotes`. Source-scanning helpers shared with `footnotes.py` are extracted first into `scriptorium/source.py`. Bibliography entries are opaque Markdown prose strings, so numbering is by first appearance and author-date is impossible by construction.

**Tech Stack:** Python 3.12+, `markdown-it-py`, WeasyPrint, pytest, `uv`.

**Spec:** `docs/superpowers/specs/2026-08-11-citations-design.md`

## Global Constraints

- Python 3.12+, English throughout (identifiers, comments, log messages).
- One logical change per commit, conventional commits.
- `uv run pytest` must pass before any commit lands. Run the gate as its **own** command and read pytest's own exit code — never `pytest | tail` chained into `&&`, which hands the chain `tail`'s status.
- **No new dependency.**
- The emitted document must remain a **single continuous HTML flow** — pagination is WeasyPrint's CSS Fragmentation and splitting the flow breaks it.
- The engine stays theme-agnostic: presentation lives in theme CSS and the component template, never in the engine.
- Verify visual work visually — render the PDF and look at it.
- Bibliography entries are **prose strings**. Never parse them for author or year.

## File Structure

| File | Responsibility |
|---|---|
| `scriptorium/source.py` | **Create.** Fence-span scanning, frontmatter splitting, line offsets. Shared by both pre-processors. |
| `scriptorium/citations.py` | **Create.** Span parsing, numbering, `nocite`, emission, placement. |
| `tests/test_citations.py` | **Create.** Unit + render tests for the above. |
| `scriptorium/footnotes.py` | **Modify.** Import from `source.py`; return `(src, warnings)`; audit unresolved markers. |
| `scriptorium/galley.py` | **Modify.** `Report.warnings`; call `process_citations`; `project_meta` parameter. |
| `scriptorium/project.py` | **Modify.** Top-level `bibliography:` / `nocite:` in `scriptorium.yaml`. |
| `scriptorium/cli.py` | **Modify.** Print warnings; pass `project_meta`. |
| `tests/test_footnotes.py` | **Modify.** Task 2 only — signature change. |
| `themes/base/components/references.html` | **Create.** `<section class="references">`. |
| `themes/base/theme.yml` | **Modify.** `references` keep-together hint. |
| `themes/base/styles.css` | **Modify.** `.cite-ref` / `.references`. |
| `examples/article.md` | **Modify.** Demonstrate citations alongside its footnotes. |

---

### Task 1: Extract `source.py` (pure refactor)

The value of this task is that it changes **no behaviour**. The existing footnote
suite is the safety net, so it must pass with **no test file edited**.

**Files:**
- Create: `scriptorium/source.py`
- Modify: `scriptorium/footnotes.py:15-16,26-52,167-178`

**Interfaces:**
- Produces: `source.FENCE`, `source.fence_spans(src) -> list[tuple[int,int]]`, `source.in_span(pos, spans) -> bool`, `source.line_offsets(lines) -> list[int]`, `source.split_frontmatter(src) -> tuple[str, str]`.

- [ ] **Step 1: Create `scriptorium/source.py`**

```python
"""Scan Markdown source without touching fenced code or frontmatter.

Shared by the source-to-source pre-processors (footnotes, citations). Both must
find markers in prose while leaving fenced code alone, and both must hold a
document's frontmatter aside so a `---` fence or a YAML `# comment` is never
mistaken for document content.
"""

import re

FENCE = re.compile(r"^(`{3,}|~{3,}).*$", re.MULTILINE)


def fence_spans(src: str) -> list[tuple[int, int]]:
    """Character ranges covered by fenced code blocks."""
    spans, open_at, marker = [], None, None
    for m in FENCE.finditer(src):
        tick = m.group(1)
        if open_at is None:
            open_at, marker = m.start(), tick
        elif tick[0] == marker[0] and len(tick) >= len(marker):
            spans.append((open_at, m.end()))
            open_at, marker = None, None
    if open_at is not None:
        spans.append((open_at, len(src)))
    return spans


def in_span(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in spans)


def line_offsets(lines: list[str]) -> list[int]:
    """Character offset of each line, for mapping a line index to a position."""
    offsets, pos = [], 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1
    return offsets


def split_frontmatter(src: str) -> tuple[str, str]:
    """(frontmatter block, body) — the same rule parse.frontmatter/_body use."""
    if src.startswith("---\n"):
        end = src.find("\n---", 3)
        if end >= 0:
            nl = src.find("\n", end + 1)
            return (src[: nl + 1], src[nl + 1 :]) if nl >= 0 else (src, "")
    return "", src
```

- [ ] **Step 2: Delete the moved definitions from `footnotes.py`**

Remove these five blocks from `scriptorium/footnotes.py`, leaving everything else:

- the `_FENCE = re.compile(...)` line (line 16)
- `def _fence_spans(...)` through its `return spans`
- `def _in_span(...)` through its `return`
- `def _line_offsets(...)` through its `return offsets`
- `def _split_frontmatter(...)` through its `return "", src`

Keep `_DEF` (line 15) — it is footnote-specific.

- [ ] **Step 3: Import from `source.py` and rewrite the call sites**

Add the import immediately below `from dataclasses import dataclass, field`:

```python
from .source import fence_spans, in_span, line_offsets, split_frontmatter
```

Then rename every call site (there are no other occurrences of these names):

```bash
cd /home/apiad/Workspace/repos/scriptorium
sed -i 's/\b_fence_spans(/fence_spans(/g; s/\b_in_span(/in_span(/g; s/\b_line_offsets(/line_offsets(/g; s/\b_split_frontmatter(/split_frontmatter(/g' scriptorium/footnotes.py
grep -n '_fence_spans\|_in_span\|_line_offsets\|_split_frontmatter\|_FENCE' scriptorium/footnotes.py
```
Expected: the final `grep` prints nothing.

- [ ] **Step 4: Prove the refactor changed no behaviour**

```bash
uv run pytest -q > /tmp/gate.log 2>&1; echo "PYTEST_RC=$?"; tail -2 /tmp/gate.log
git diff --stat tests/
```
Expected: `PYTEST_RC=0`, 72 passed, and `git diff --stat tests/` prints **nothing**.
If any test needed editing, the extraction was not behaviour-preserving — revert and redo it.

- [ ] **Step 5: Commit**

```bash
git add scriptorium/source.py scriptorium/footnotes.py
git commit -m "refactor(source): extract the shared Markdown source scanner

fence_spans/in_span/line_offsets/split_frontmatter move out of footnotes.py
so citations can use them without importing another module's privates.
Behaviour-preserving: the footnote suite passes unedited."
```

---

### Task 2: The warning channel, and make the footnotes spec true

v0.4.0's spec says an unresolved `[^marker]` is "reported". It is not — the code
silently skips it, because `Report` has no warning field and `render_pdf`'s
document path returns none. This task adds the channel and uses it.

**Files:**
- Modify: `scriptorium/galley.py:55-58` (the `Report` dataclass), `scriptorium/galley.py:653-657`, `scriptorium/galley.py:667`
- Modify: `scriptorium/cli.py:44-45,52-53`
- Modify: `scriptorium/footnotes.py` (append `_audit`, change `process_footnotes`)
- Modify: `tests/test_footnotes.py` (signature change — **this is the task that may edit these tests**)

**Interfaces:**
- Consumes: `source.fence_spans`, `source.in_span` from Task 1.
- Produces: `Report.warnings: list[str]`; `footnotes.process_footnotes(src: str, mode: str = "document") -> tuple[str, list[str]]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_footnotes.py`:

```python
def test_unresolved_marker_and_uncited_definition_are_warned():
    out, warnings = process_footnotes("A[^missing] and B[^b]\n\n[^b]: two\n\n[^c]: three\n")

    assert "[^missing]" in out          # still literal, never deleted
    assert any("missing" in w for w in warnings)
    assert any("c" in w and "never referenced" in w for w in warnings)
    assert not any("[^b]" in w for w in warnings)   # b is fine, no noise


def test_render_surfaces_footnote_warnings(tmp_path):
    src = ("---\ntheme: article\ntitle: T\n---\n\n"
           "# H\n\nA claim.[^nope]\n\n[^a]: An orphan note.\n")
    report = render_pdf(src, str(tmp_path / "w.pdf"), execute=False)

    assert any("nope" in w for w in report.warnings)


def test_uncited_definitions_emit_no_empty_section():
    # v0.4.0 emitted a bare `::: footnotes` / `:::` pair here, which renders as
    # an empty ruled band in the PDF.
    out, warnings = process_footnotes("A claim, no marker.\n\n[^a]: An orphan.\n")

    assert "::: footnotes" not in out
    assert any("never referenced" in w for w in warnings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_footnotes.py -k "warned or warnings" -v`
Expected: FAIL — `process_footnotes` returns a `str`, so unpacking raises `ValueError`, and `Report` has no `warnings` attribute.

- [ ] **Step 3: Add `Report.warnings`**

In `scriptorium/galley.py`, line 14 currently reads `from dataclasses import dataclass`.
It must import `field` too:

```python
from dataclasses import dataclass, field
```

Then extend the `Report` dataclass (line 55):

```python
@dataclass
class Report:
    n_pages: int
    oversized: list[str]
    page_of: list[int]
    warnings: list[str] = field(default_factory=list)
```

A default keeps every existing `Report(...)` construction valid.

- [ ] **Step 4: Make the CLI print warnings**

In `scriptorium/cli.py`, both render branches already loop over `report.oversized`.
Add a second loop immediately after each (lines 44-45 and 52-53):

```python
        for w in report.oversized:
            print(f"  ⚠ {w}", file=sys.stderr)
        for w in report.warnings:
            print(f"  ⚠ {w}", file=sys.stderr)
```

- [ ] **Step 5: Audit footnotes and return warnings**

In `scriptorium/footnotes.py`, add this function immediately above `process_footnotes`:

```python
def _audit(body: str, notes: dict[str, Note]) -> list[str]:
    """Markers with no definition, and definitions nobody references."""
    spans = fence_spans(body)
    seen = {m.group(1) for m in _MARK.finditer(body) if not in_span(m.start(), spans)}
    warnings = [f"footnote [^{k}] has no definition" for k in sorted(seen - set(notes))]
    warnings += [f"footnote definition [^{k}] is never referenced"
                 for k in sorted(set(notes) - seen)]
    return warnings
```

Then change `process_footnotes` to return the pair. Its signature line becomes:

```python
def process_footnotes(src: str, mode: str = "document") -> tuple[str, list[str]]:
    """Entry point: rewrite markers and emit notes per `mode`."""
    head, body = split_frontmatter(src)
    body, notes = collect_notes(body)
    warnings = _audit(body, notes)
    if not notes:
        return head + body, warnings
    if mode == "page":
        return head + _inline_notes(body, notes), warnings

    marked, groups = number_and_mark(body, notes, chapter_mode=(mode == "chapter"))
    if mode == "document":
        if not groups[0]:  # definitions exist but nothing cites them
            return head + marked, warnings
        return head + marked.rstrip() + "\n\n" + _component(1, groups[0]), warnings

    starts = _chapter_starts(marked, fence_spans(marked))
    bounds = starts[_lead(marked, starts):] + [len(marked)]
    out, prev = [], 0
    for i, group in enumerate(groups):
        out.append(marked[prev : bounds[i]])
        if group:
            out.append("\n" + _component(i + 1, group) + "\n")
        prev = bounds[i]
    return head + "".join(out), warnings
```

- [ ] **Step 6: Collect the warnings in `render_pdf`**

In `scriptorium/galley.py`, replace the footnote call (around line 656):

```python
    src, warnings = process_footnotes(src, resolve_footnote_mode(meta, theme.meta))
```

The deck branch returns a `Report` built elsewhere, so attach warnings to it; the
document branch builds its own. Replace the two return sites:

```python
    if str(theme.meta.get("mode", "")) == "deck":  # slides: keep measure+pack pipeline
        measure(units, theme, base_url=base_url)
        report = _render_deck(units, theme, meta, out_path, base_url, content_h)
        report.warnings = warnings
        return report

    # Document themes: CSS Fragmentation handles all pagination — no measure, no pack.
    doc = HTML(string=emit(units, theme, meta), base_url=base_url).render()
    doc.write_pdf(out_path)
    return Report(n_pages=len(doc.pages), oversized=[], page_of=[], warnings=warnings)
```

- [ ] **Step 7: Update the existing footnote tests for the new signature**

Five tests call `process_footnotes` expecting a bare string. Take the first element:

```bash
cd /home/apiad/Workspace/repos/scriptorium
sed -i 's/^    out = process_footnotes(\(.*\))$/    out, _ = process_footnotes(\1)/' tests/test_footnotes.py
grep -n 'process_footnotes(' tests/test_footnotes.py
```
One call spans two lines (`test_note_body_keeps_its_markdown`); fix that one by hand:

```python
    out, _ = process_footnotes("A[^a]\n\n[^a]: See **this** and [that](https://x.dev).\n",
                               mode="document")
```

- [ ] **Step 8: Run the full suite**

```bash
uv run pytest -q > /tmp/gate.log 2>&1; echo "PYTEST_RC=$?"; tail -2 /tmp/gate.log
```
Expected: `PYTEST_RC=0`, 75 passed.

- [ ] **Step 9: Commit**

```bash
git add scriptorium/galley.py scriptorium/cli.py scriptorium/footnotes.py tests/test_footnotes.py
git commit -m "feat(warnings): a warning channel, and footnotes finally use it

The v0.4.0 spec said an unresolved [^marker] was reported; it was silently
skipped, because Report carried no warning field and the document render path
returned none. Report gains warnings, the CLI prints them, and footnotes warn
on a marker with no definition and a definition nobody references."
```

---

### Task 3: Parse and number citation spans

**Files:**
- Create: `scriptorium/citations.py`
- Create: `tests/test_citations.py`

**Interfaces:**
- Consumes: `source.fence_spans`, `source.in_span` from Task 1.
- Produces:
  - `Entry` dataclass: `key: str`, `body: str`, `number: int`, `refs: int = 0`.
  - `number_citations(src: str, bib: dict[str, str]) -> tuple[str, list[Entry], list[str]]` — the rewritten source, entries in citation order, and warnings.

**Do not copy the footnote back-link scheme.** `footnotes.py` emits `fnref-C-N`
for a lone reference and `fnref-C-Na` / `-Nb` when there are several — the suffix
appears only when needed, which is exactly why that module needs two passes.
Citations use `citeref-N-K` unconditionally (entry `N`, call site `K`, from 1),
which is why the function below is a single pass with no retroactive rewrite.
This difference is deliberate; the spec records it.

- [ ] **Step 1: Write the failing test**

Create `tests/test_citations.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_citations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scriptorium.citations'`.

- [ ] **Step 3: Implement**

Create `scriptorium/citations.py`:

```python
"""Numbered citations against an author-declared bibliography.

A source-to-source pre-processor, like footnotes.py and for the same reason:
parse() renders block by block, so a plugin would never see a citation and its
entry in one render call.

Entries are opaque Markdown prose. The engine numbers, orders and links them; it
never inspects them for an author or a year, which is why this is numeric-only
and author-date belongs to a future CSL feature.
"""

import re
from dataclasses import dataclass

from .source import fence_spans, in_span, line_offsets, split_frontmatter

# [@a] or [@a; @b] — brackets are required. A bare @key is deliberately not a
# citation: v0.4.0 narrowed the cross-reference pattern precisely because a loose
# @word rule was rewriting prose into empty anchors. A comma (a page locator)
# fails the match, so the whole span stays literal.
_CITE = re.compile(r"\[@[\w-]+(?:[ \t]*;[ \t]*@[\w-]+)*\]")
_KEY = re.compile(r"@([\w-]+)")


@dataclass
class Entry:
    key: str
    body: str
    number: int
    refs: int = 0


def number_citations(src: str, bib: dict[str, str]) -> tuple[str, list["Entry"], list[str]]:
    """Rewrite [@key] spans to numbered links; return (src, entries, warnings)."""
    spans = fence_spans(src)
    entries: dict[str, Entry] = {}
    warnings: list[str] = []
    out, last = [], 0

    for m in _CITE.finditer(src):
        if in_span(m.start(), spans):
            continue
        keys = _KEY.findall(m.group(0))
        missing = [k for k in keys if k not in bib]
        if missing:
            for k in missing:
                w = f"citation [@{k}] has no bibliography entry"
                if w not in warnings:
                    warnings.append(w)
            continue  # the whole span stays literal — visible, never vanished
        links = []
        for k in keys:
            entry = entries.get(k)
            if entry is None:
                entry = entries[k] = Entry(key=k, body=bib[k], number=len(entries) + 1)
            entry.refs += 1
            links.append(f'<a id="citeref-{entry.number}-{entry.refs}" '
                         f'href="#cite-{entry.number}">{entry.number}</a>')
        out.append(src[last:m.start()])
        out.append(f'<span class="cite-ref">[{", ".join(links)}]</span>')
        last = m.end()

    out.append(src[last:])
    return "".join(out), list(entries.values()), warnings
```

`line_offsets` and `split_frontmatter` are imported now because Task 4 uses them;
if your linter objects to unused imports, add them in Task 4 instead.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_citations.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add scriptorium/citations.py tests/test_citations.py
git commit -m "feat(citations): parse and number [@key] spans"
```

---

### Task 4: Emit the references section

**Files:**
- Modify: `scriptorium/citations.py`
- Modify: `tests/test_citations.py` (append)

**Interfaces:**
- Consumes: `Entry`, `number_citations` from Task 3; `source.line_offsets`, `source.split_frontmatter` from Task 1.
- Produces: `process_citations(src: str, meta: dict) -> tuple[str, list[str]]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_citations.py`:

```python
import pytest

from scriptorium.citations import process_citations

META = {"bibliography": BIB}


def test_document_gets_one_references_component_at_the_end():
    out, warnings = process_citations("A claim.[@parnas]\n", META)

    assert out.count("::: references") == 1
    assert out.index("::: references") > out.index("A claim.")
    assert '<span id="cite-1"></span>' in out
    assert "Parnas, D. L." in out and "[↩](#citeref-1-1)" in out
    assert warnings == []


def test_uncited_entry_is_omitted():
    out, _ = process_citations("Only one.[@parnas]\n", META)

    assert "Parnas" in out and "Vogel" not in out


def test_nocite_adds_an_entry_without_a_citation():
    meta = {"bibliography": BIB, "nocite": ["vogel"]}
    out, _ = process_citations("Only one.[@parnas]\n", meta)

    assert "Parnas" in out and "Vogel" in out
    assert out.index("Parnas") < out.index("Vogel")   # cited first, then nocite


def test_nocite_key_with_no_entry_warns():
    meta = {"bibliography": BIB, "nocite": ["ghost"]}
    _, warnings = process_citations("A[@parnas]\n", meta)

    assert any("ghost" in w for w in warnings)


def test_repeated_citation_gets_a_back_link_each():
    out, _ = process_citations("A[@parnas] again[@parnas]\n", META)

    assert "[↩](#citeref-1-1)" in out and "[↩](#citeref-1-2)" in out


def test_entry_body_keeps_its_markdown():
    meta = {"bibliography": {"x": "See **this** and [that](https://x.dev)."}}
    out, _ = process_citations("A[@x]\n", meta)

    assert "**this**" in out and "[that](https://x.dev)" in out


def test_no_citations_emits_no_section():
    out, warnings = process_citations("Plain prose.\n", META)

    assert "::: references" not in out and warnings == []


def test_author_placed_block_is_filled_in_place():
    src = "A[@parnas]\n\n::: references\n:::\n\n## Appendix\n\nTail.\n"
    out, _ = process_citations(src, META)

    assert out.count("::: references") == 1
    assert out.index("Parnas") < out.index("## Appendix")   # not appended at the end


def test_two_reference_blocks_is_an_error():
    src = "A[@parnas]\n\n::: references\n:::\n\n::: references\n:::\n"
    with pytest.raises(ValueError, match="references"):
        process_citations(src, META)


def test_frontmatter_is_held_aside():
    src = "---\ntitle: T\n---\n\nA[@parnas]\n"
    out, _ = process_citations(src, META)

    assert out.startswith("---\ntitle: T\n---\n")
    assert out.count("::: references") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_citations.py -v`
Expected: FAIL — `ImportError: cannot import name 'process_citations'`.

- [ ] **Step 3: Implement**

Append to `scriptorium/citations.py`:

```python
_REFS_OPEN = re.compile(r"^:{3,}[ \t]*references[ \t]*$")
_REFS_CLOSE = re.compile(r"^:{3,}[ \t]*$")


def _placeholder(src: str) -> tuple[int, int] | None:
    """Character range of an author-written `::: references` block, if any."""
    spans = fence_spans(src)
    lines = src.split("\n")
    offsets = line_offsets(lines)
    found = None
    for i, line in enumerate(lines):
        if not _REFS_OPEN.match(line) or in_span(offsets[i], spans):
            continue
        for j in range(i + 1, len(lines)):
            if _REFS_CLOSE.match(lines[j]):
                if found is not None:
                    raise ValueError("two `::: references` blocks; there can be only one")
                found = (offsets[i], offsets[j] + len(lines[j]) + 1)
                break
        else:
            raise ValueError("`::: references` block is never closed")
    return found


def _component(entries: list[Entry]) -> str:
    """Entries as a `::: references` component; bodies stay Markdown."""
    items = []
    for entry in entries:
        back = " ".join(f"[↩](#citeref-{entry.number}-{k})"
                        for k in range(1, entry.refs + 1))
        items.append(f'{entry.number}. <span id="cite-{entry.number}"></span>'
                     f"{entry.body} {back}".rstrip())
    return "::: references\n" + "\n".join(items) + "\n:::\n"


def process_citations(src: str, meta: dict) -> tuple[str, list[str]]:
    """Entry point: number citations and emit the references section."""
    bib = meta.get("bibliography") or {}
    head, body = split_frontmatter(src)
    marked, entries, warnings = number_citations(body, bib)

    for key in meta.get("nocite") or []:
        if key not in bib:
            warnings.append(f"nocite key {key!r} has no bibliography entry")
        elif not any(e.key == key for e in entries):
            entries.append(Entry(key=key, body=bib[key], number=len(entries) + 1))

    if not entries:
        return head + marked, warnings

    block = _component(entries)
    at = _placeholder(marked)
    if at:
        return head + marked[: at[0]] + block + marked[at[1] :], warnings
    return head + marked.rstrip() + "\n\n" + block, warnings
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_citations.py -v`
Expected: PASS (18 tests).

- [ ] **Step 5: Commit**

```bash
git add scriptorium/citations.py tests/test_citations.py
git commit -m "feat(citations): emit the references section, with nocite and placement"
```

---

### Task 5: Wire into the engine and theme it

**Files:**
- Modify: `scriptorium/galley.py` (the `process_footnotes` call site from Task 2)
- Create: `themes/base/components/references.html`
- Modify: `themes/base/theme.yml`, `themes/base/styles.css`
- Modify: `tests/test_citations.py` (append)

**Interfaces:**
- Consumes: `process_citations` from Task 4.

- [ ] **Step 1: Write the failing render test**

Append to `tests/test_citations.py`:

```python
from scriptorium.galley import render_pdf


def test_citation_text_reaches_the_pdf_and_no_syntax_leaks(tmp_path):
    src = ("---\ntheme: article\ntitle: T\n"
           "bibliography:\n  parnas: \"Parnas, D. L. On the Criteria. CACM, 1972.\"\n"
           "---\n\n# H\n\nA claim.[@parnas]\n")
    out = tmp_path / "c.pdf"
    report = render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "Parnas, D. L." in text
    assert "[@parnas]" not in text
    assert "[1]" in text            # bracketed, not a bare superscript
    assert report.warnings == []


def test_footnotes_and_citations_coexist_with_separate_counters(tmp_path):
    src = ("---\ntheme: article\ntitle: T\n"
           "bibliography:\n  vogel: \"Vogel, E. F. Deng Xiaoping. Belknap, 2011.\"\n"
           "---\n\n# H\n\nA claim[^n] and a source.[@vogel]\n\n"
           "[^n]: An explanatory note.\n")
    out = tmp_path / "both.pdf"
    render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "An explanatory note." in text and "Vogel, E. F." in text
    # both are number 1 of their own sequence
    assert "[1]" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_citations.py -k "pdf or coexist" -v`
Expected: FAIL — `[@parnas]` survives literally, since nothing calls `process_citations`.

- [ ] **Step 3: Wire the engine**

In `scriptorium/galley.py`, extend the import and the call added in Task 2:

```python
    from .parse import fill_toc
    from .footnotes import process_footnotes, resolve_footnote_mode
    from .citations import process_citations

    src, warnings = process_footnotes(src, resolve_footnote_mode(meta, theme.meta))
    src, cite_warnings = process_citations(src, meta)
    warnings = warnings + cite_warnings
```

Citations run **after** footnotes on purpose: a `[@key]` written inside a note
body has by then been moved to where the note actually renders, so it is numbered
by reading order rather than by where its definition happened to sit.

- [ ] **Step 4: Add the component and styles**

Create `themes/base/components/references.html`:

```html
<section class="references">{{content}}</section>
```

In `themes/base/theme.yml`, add the hint to the existing `components:` block
(added in v0.4.0 for `footnotes`) — do not create a second `components:` key:

```yaml
components:
  footnotes:
    keep_together: false   # an endnotes section is often taller than a page
  references:
    keep_together: false   # and so is a reference list
```

In `themes/base/styles.css`, add after the `.footnotes` rules:

```css
/* citation markers + the references section */
.cite-ref { white-space: nowrap; }
.cite-ref a { color: var(--accent-dark); text-decoration: none; border-bottom: none; }
.references { margin-top: 6mm; padding-top: 3mm; border-top: 0.3mm solid var(--rule); }
.references ol { font-size: 9pt; line-height: 1.45; padding-left: 6mm; margin: 0; }
.references li { margin: 0 0 1.5mm 0; }
.references a { color: var(--accent-dark); border-bottom: none; }
```

- [ ] **Step 5: Run the full suite**

```bash
uv run pytest -q > /tmp/gate.log 2>&1; echo "PYTEST_RC=$?"; tail -2 /tmp/gate.log
```
Expected: `PYTEST_RC=0`, 95 passed.

- [ ] **Step 6: Verify visually — this is a visual artifact**

```bash
cat > /tmp/cite-check.md <<'EOF'
---
theme: article
title: Citation check
bibliography:
  parnas: "Parnas, D. L. *On the Criteria To Be Used in Decomposing Systems into Modules.* CACM 15(12), 1972. [ACM](https://dl.acm.org/doi/10.1145/361598.361623)."
  vogel: "Vogel, E. F. *Deng Xiaoping and the Transformation of China*. Belknap, 2011."
nocite: [vogel]
---

# Heading

A claim with one source.[@parnas] A claim with two.[@parnas; @vogel]

An explanatory note lives here too.[^n]

[^n]: Notes and references are different apparatuses.
EOF
uv run scriptorium render /tmp/cite-check.md -o /tmp/cite-check.pdf
pdftoppm -png -r 70 -f 1 -l 1 /tmp/cite-check.pdf /tmp/cite-check
```
Open `/tmp/cite-check-1.png` and **look at it**: citations are `[1]` and `[1, 2]`
on the baseline, the footnote marker is a raised bare numeral, the notes section
and the references section are visibly distinct, both are ruled off, nothing
overlaps, and no `[@key]` or `[^n]` syntax survives anywhere.

- [ ] **Step 7: Commit**

```bash
git add scriptorium/galley.py themes/base/components/references.html \
        themes/base/theme.yml themes/base/styles.css tests/test_citations.py
git commit -m "feat(citations): wire into the engine; base theme component and styles"
```

---

### Task 6: A project-level bibliography

**Files:**
- Modify: `scriptorium/project.py:18-25` (the `Project` dataclass), `scriptorium/project.py:40-56` (`load`)
- Modify: `scriptorium/galley.py:609-619` (`render_pdf` signature and `meta` assembly)
- Modify: `scriptorium/cli.py:39-42`
- Modify: `tests/test_citations.py` (append)

**Interfaces:**
- Consumes: `process_citations` from Task 4.
- Produces: `Project.meta: dict`; `render_pdf(..., project_meta: dict | None = None)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_citations.py`:

```python
def test_project_level_bibliography_reaches_the_render(tmp_path):
    from scriptorium.project import load

    (tmp_path / "a.md").write_text("# One\n\nA claim.[@parnas]\n")
    (tmp_path / "scriptorium.yaml").write_text(
        "theme: book\n"
        "bibliography:\n  parnas: \"Parnas, D. L. On the Criteria. CACM, 1972.\"\n"
        "files: [a.md]\n")
    proj = load(tmp_path / "scriptorium.yaml")

    assert proj.meta["bibliography"]["parnas"].startswith("Parnas")
    assert "bibliography" not in proj.vars   # content, not appearance

    out = tmp_path / "b.pdf"
    render_pdf(proj.src, str(out), theme_name=proj.theme, execute=False,
               vars=proj.vars, project_meta=proj.meta)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "Parnas, D. L." in text and "[@parnas]" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_citations.py -k project -v`
Expected: FAIL — `Project` has no attribute `meta`.

- [ ] **Step 3: Add `Project.meta`**

In `scriptorium/project.py`, extend the dataclass (`field` is already imported
there, at line 10 — no import change needed):

```python
@dataclass
class Project:
    theme: str
    vars: dict
    src: str  # assembled markdown
    base_dir: Path
    code_root: str | None = None
    meta: dict = field(default_factory=dict)  # content keys: bibliography, nocite
```

In `load`, read the content keys and pass them through. After the `vars` line:

```python
    vars = spec.get("vars", {}) or {}
    # content keys, distinct from `vars` (which is the appearance contract and
    # the target of {{substitution}}): a bibliography is content, not styling.
    meta = {k: spec[k] for k in ("bibliography", "nocite") if k in spec}
```

and the return:

```python
    return Project(theme=theme, vars=vars, src=src, base_dir=base,
                   code_root=code_root, meta=meta)
```

- [ ] **Step 4: Thread it through `render_pdf`**

In `scriptorium/galley.py`, add the parameter:

```python
def render_pdf(src: str, out_path: str, base_url: str | None = None,
               theme_name: str | None = None, cwd: str | None = None,
               execute: bool = True, vars: dict | None = None,
               code_root: str | None = None,
               project_meta: dict | None = None) -> Report:
```

and fold it into the meta assembly (a project's chapters have had their
frontmatter stripped, so `frontmatter(src)` is empty there and this is the only
route in):

```python
    meta = {**merged, **(project_meta or {}), **frontmatter(src)}
```

- [ ] **Step 5: Pass it from the CLI**

In `scriptorium/cli.py`, the project branch (around line 39):

```python
            report = render_pdf(proj.src, str(out), base_url=cwd + "/",
                                theme_name=proj.theme, cwd=cwd,
                                execute=not args.no_execute, vars=proj.vars,
                                code_root=proj.code_root, project_meta=proj.meta)
```

- [ ] **Step 6: Run the full suite**

```bash
uv run pytest -q > /tmp/gate.log 2>&1; echo "PYTEST_RC=$?"; tail -2 /tmp/gate.log
```
Expected: `PYTEST_RC=0`, 96 passed.

- [ ] **Step 7: Commit**

```bash
git add scriptorium/project.py scriptorium/galley.py scriptorium/cli.py tests/test_citations.py
git commit -m "feat(citations): scriptorium.yaml takes a top-level bibliography

A book's bibliography is content, so it gets its own key rather than
travelling under vars:, which is the appearance contract."
```

---

### Task 7: Mutation-check the cited-only rule

A test that cannot fail is worse than no test. This proves the uncited-entry
assertion is real.

**Files:** none changed (verification only).

- [ ] **Step 1: Force every declared entry into the list**

```bash
cd /home/apiad/Workspace/repos/scriptorium
cp scriptorium/citations.py /tmp/cite.orig
sed -i 's/    for key in meta.get("nocite") or \[\]:/    for key in list(bib):/' scriptorium/citations.py
cmp -s /tmp/cite.orig scriptorium/citations.py && echo "MUTATION DID NOT APPLY — stop" || echo "mutation applied"
```

- [ ] **Step 2: Confirm the cited-only test goes red**

Run: `uv run pytest tests/test_citations.py -k uncited -q`
Expected: FAIL. If it passes, the test is not testing cited-only — fix it before continuing.

- [ ] **Step 3: Restore and confirm green**

```bash
cp /tmp/cite.orig scriptorium/citations.py
uv run pytest -q > /tmp/gate.log 2>&1; echo "PYTEST_RC=$?"; tail -2 /tmp/gate.log
git status --short
```
Expected: `PYTEST_RC=0`, and `git status --short` clean.

---

### Task 8: Example and documentation

**Files:**
- Modify: `examples/article.md`, `README.md`, `docs/design.md`, `know-how/authoring-a-theme.md`, `AGENTS.md`, `CHANGELOG.md`

- [ ] **Step 1: Give the article example a bibliography**

`examples/article.md` already carries footnotes, so it is the right place to show
both apparatuses side by side. Add to its frontmatter, after `keywords:`:

```yaml
bibliography:
  parnas1972: "Parnas, D. L. *On the Criteria To Be Used in Decomposing Systems into Modules.* Communications of the ACM 15(12), 1972. [dl.acm.org](https://dl.acm.org/doi/10.1145/361598.361623)."
  brooks1975: "Brooks, F. P. *The Mythical Man-Month*. Addison-Wesley, 1975."
```

Then cite them in the body. In the "Hiding a decision, not a mechanism" section,
change the closing sentence of the first paragraph to:

```markdown
The first is a thin coat of paint; the second is a boundary worth
defending.[@parnas1972; @brooks1975]
```

- [ ] **Step 2: Render and look**

```bash
uv run scriptorium render examples/article.md -o /tmp/ex-cite.pdf
pdftoppm -png -r 65 -f 1 -l 3 /tmp/ex-cite.pdf /tmp/ex-cite
```
Open the PNGs. The citation is `[1, 2]` on the baseline; the footnote markers stay
raised superscripts; the notes section and the references section are separate and
each is ruled off; no `[@key]` residue.

- [ ] **Step 3: README**

Under Authoring, after the Footnotes bullet, add:

```markdown
- **Citations** — `[@key]` and `[@a; @b]` render as `[1]` / `[1, 2]` against a
  `bibliography:` map in frontmatter (or in `scriptorium.yaml` for a project),
  and collect into a references section. Cited works only; add `nocite: [key]`
  for anything you want listed without citing. Entries are Markdown prose, so
  numeric styles only — author-date needs CSL, which is not built.
```

- [ ] **Step 4: `docs/design.md`**

Add a `### 7.5 Citations — numbered, prose entries` subsection immediately after
§7.4, stating: `[@key]` / `[@a; @b]`, numbering by first appearance, cited-only
plus `nocite`, a distinct `<section class="references">` with its own counter, and
that prose entries make author-date impossible by construction rather than
deferred — CSL is a separate feature tracked in `tasks.md`.

- [ ] **Step 5: `know-how/authoring-a-theme.md`**

In the Footnotes section, add a paragraph: the `references` component template
lives at `components/references.html`, ships `<section class="references">`, takes
a `keep_together: false` hint for the same reason footnotes do, and is styled via
`.references` and `.cite-ref`.

- [ ] **Step 6: `AGENTS.md`**

Add two entries to the pipeline module list, beside `footnotes.py`:

```markdown
- **`citations.py`** — `[@key]` spans against a declared `bibliography:` map →
  a numbered `::: references` section. Runs on the raw source **after**
  `footnotes.py`, so a citation inside a note body is numbered by where the note
  renders. Prose entries: never parse them for author or year.
- **`source.py`** — the shared source scanner (fence spans, frontmatter split)
  both pre-processors use.
```

- [ ] **Step 7: CHANGELOG**

Under `## [Unreleased]`, add a `### Features` entry for citations and the
`bibliography:` / `nocite:` keys, and a `### Fixes` entry recording that footnote
warnings are now actually emitted (`Report.warnings`), which the v0.4.0 spec
claimed but the code never did.

- [ ] **Step 8: Commit**

```bash
git add examples/article.md README.md docs/design.md know-how/authoring-a-theme.md \
        AGENTS.md CHANGELOG.md
git commit -m "docs: citation syntax, the bibliography: key, and the references component"
```

---

### Task 9: Release v0.5.0

- [ ] **Step 1: Follow `know-how/releasing.md`**

Commits since `v0.4.0` include `feat:`, so this is a **minor** bump → `v0.5.0`.

- [ ] **Step 2: Preconditions and gate**

```bash
git status --porcelain          # must be empty
git rev-parse --abbrev-ref HEAD # must be main
git fetch -q origin && git log --oneline origin/main..HEAD
uv run pytest -q > /tmp/gate.log 2>&1; echo "PYTEST_RC=$?"; tail -2 /tmp/gate.log
```
Expected: clean tree, on `main`, `PYTEST_RC=0`.

- [ ] **Step 3: Bump, changelog, commit, tag, push**

Per `know-how/releasing.md`: set `version = "0.5.0"` in `pyproject.toml`, run
`uv lock` so `uv.lock` follows, move `## [Unreleased]` to `## [v0.5.0] - <date>`
with a fresh `## [Unreleased]` above, update the README status line, then:

```bash
git add pyproject.toml uv.lock CHANGELOG.md README.md
git commit -m "chore(release): v0.5.0"
git tag -a v0.5.0 -m "v0.5.0 — numbered citations and a references section"
git push origin main && git push origin v0.5.0
gh release create v0.5.0 --generate-notes --title "v0.5.0"
```

- [ ] **Step 4: Verify the published artifact, not the working tree**

```bash
rm -rf /tmp/scriptorium-v050
git clone -q --branch v0.5.0 /home/apiad/Workspace/repos/scriptorium /tmp/scriptorium-v050
cd /tmp/scriptorium-v050 && git describe --tags
cat > /tmp/v050.md <<'EOF'
---
theme: article
title: Tag check
bibliography:
  a: "First source, 2020."
  b: "Second source, 2021."
---

# H

One.[@a] Two.[@a; @b]
EOF
uv run --project /tmp/scriptorium-v050 scriptorium render /tmp/v050.md -o /tmp/v050.pdf
pdftotext /tmp/v050.pdf - | grep -c "First source"
```
Expected: `v0.5.0`, a successful render, and the grep printing `1`.

- [ ] **Step 5: Sync the VPS**

```bash
ssh vps 'cd ~/Workspace/repos/scriptorium && git pull --ff-only origin main --tags && git describe --tags'
```
Expected: `v0.5.0`.

- [ ] **Step 6: Update the workspace report standard**

Separate repo, separate commit. In `/home/apiad/Workspace/CLAUDE.md`, the *Report
standard* section documents footnotes as of v0.4.0. Add the citation form beside
it: a `bibliography:` map in frontmatter with `[@key]` in the body, for sources
that belong in a reference list rather than in an explanatory note.

```bash
cd /home/apiad/Workspace
git commit -m "docs(claude): report standard gains the citation form" -- CLAUDE.md
```
