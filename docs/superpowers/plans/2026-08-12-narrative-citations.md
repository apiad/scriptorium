# Narrative Citations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `[+@key]` (author name + numbered mark) and `[-@key]` (author name alone) to scriptorium's citation engine, with the name declared in the bibliography entry rather than parsed out of its prose.

**Architecture:** All engine work lands in `scriptorium/citations.py`, a source-to-source pre-processor that runs at `galley.py:666`, after `process_footnotes`. A bibliography value becomes either a prose string (as today) or an `{author, text}` mapping; a new `_normalise()` collapses both into an internal `_Source`. The `_CITE` pattern grows one optional leading sigil group, and `number_citations` grows three emission branches. Nothing else in the pipeline moves.

**Tech Stack:** Python 3.12+, `re`, `dataclasses`, pytest, WeasyPrint (only in the end-to-end test, via the existing `render_pdf` path).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-12-narrative-citations-design.md`. Read it before Task 1.
- Python 3.12+, English throughout — identifiers, comments, warning strings, test names.
- One logical change per commit, conventional commits.
- **`uv run pytest` must pass before any commit lands** (`AGENTS.md`).
- The engine **never inspects an entry's prose** for an author. A name is read from the declared `author:` field or it does not exist.
- A broken citation stays **visible, never vanished**: the span is left literal and a warning is reported. Never fall back to the key, to the first word of `text:`, or to any derived guess.
- Sigil-less `[@key]` behaviour is frozen. Byte-identical output is a hard requirement checked by test in Task 5, not an aspiration.
- The author string is emitted as **Markdown, unescaped**, exactly as entry bodies already are — so `*Tam et al.*` works, and this is deliberate rather than an oversight.

---

### Task 1: Normalise bibliography entries

**Files:**
- Modify: `scriptorium/citations.py` (add `_Source`, `_normalise`; extend `Entry`)
- Test: `tests/test_citations.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `_Source(text: str, author: str | None)` frozen dataclass; `_normalise(bib: dict) -> tuple[dict[str, _Source], list[str]]`; `Entry` gains `author: str | None = None` as its last field.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_citations.py`:

```python
def test_normalise_reads_a_prose_string_as_text_with_no_author():
    sources, warnings = _normalise({"parnas": "Parnas, D. L. *On the Criteria…*"})

    assert sources["parnas"].text == "Parnas, D. L. *On the Criteria…*"
    assert sources["parnas"].author is None and warnings == []


def test_normalise_reads_a_mapping_entry():
    sources, warnings = _normalise(
        {"tam": {"author": "Tam et al.", "text": "Tam, Z. R., … *Let Me Speak Freely?*"}}
    )

    assert sources["tam"].author == "Tam et al."
    assert sources["tam"].text == "Tam, Z. R., … *Let Me Speak Freely?*"
    assert warnings == []


def test_normalise_drops_a_mapping_with_no_text_and_warns():
    sources, warnings = _normalise({"ghost": {"author": "Nobody"}})

    assert "ghost" not in sources
    assert any("ghost" in w and "text" in w for w in warnings)


def test_normalise_rejects_a_value_that_is_neither_prose_nor_mapping():
    sources, warnings = _normalise({"odd": 42})

    assert "odd" not in sources and any("odd" in w for w in warnings)
```

Extend the import at the top of the file:

```python
from scriptorium.citations import _normalise, number_citations
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_citations.py -k normalise -v`
Expected: FAIL — `ImportError: cannot import name '_normalise'`

- [ ] **Step 3: Write the implementation**

In `scriptorium/citations.py`, add `_Source` and `_normalise` immediately below the `Entry` dataclass, and add the `author` field to `Entry`:

```python
@dataclass
class Entry:
    key: str
    body: str
    number: int
    refs: int = 0
    author: str | None = None


@dataclass(frozen=True)
class _Source:
    """A bibliography value after normalisation: prose, plus an optional name.

    `author` is whatever the author declared, verbatim. It is never derived from
    the key or read out of `text` — deriving it is right for `tam-2024` and
    silently wrong for `willard-2023` (two authors) and `fan-2026` (one), which
    is exactly the class of error a reader notices and the engine cannot see.
    """

    text: str
    author: str | None = None


def _normalise(bib: dict) -> tuple[dict[str, _Source], list[str]]:
    """Collapse prose-string and mapping entries into one internal shape."""
    sources: dict[str, _Source] = {}
    warnings: list[str] = []
    for key, value in bib.items():
        if isinstance(value, str):
            sources[key] = _Source(text=value)
        elif isinstance(value, dict):
            text = value.get("text")
            if not text:
                warnings.append(f"bibliography entry {key!r} has no `text:`")
                continue
            sources[key] = _Source(text=text, author=value.get("author"))
        else:
            warnings.append(
                f"bibliography entry {key!r} is neither prose nor an "
                f"{{author, text}} mapping"
            )
    return sources, warnings
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_citations.py -v`
Expected: PASS — the 4 new tests plus all 21 existing ones. `Entry` gained a trailing defaulted field, so every existing keyword construction still works.

- [ ] **Step 5: Commit**

```bash
git add scriptorium/citations.py tests/test_citations.py
git commit -m "feat(citations): normalise prose and mapping bibliography entries"
```

---

### Task 2: The `[+@key]` narrative form

**Files:**
- Modify: `scriptorium/citations.py` (`_CITE`, `number_citations`)
- Test: `tests/test_citations.py`

**Interfaces:**
- Consumes: `_Source`, `_normalise` from Task 1.
- Produces: `number_citations(src, bib, nocite=())` — the third parameter is added here and stays unused until Task 3. `_CITE` group 1 is the sigil, `""` when absent.

- [ ] **Step 1: Write the failing tests**

Add a mapping-shaped fixture next to the existing `BIB`, then the tests:

```python
NAMED = {
    "tam": {"author": "Tam et al.", "text": "Tam, Z. R., … *Let Me Speak Freely?*"},
    "fan": {"author": "Fan", "text": "Fan, H. *Capacity, Not Format*."},
    "plain": "Somebody. *A work with no declared author*.",
}


def test_narrative_citation_puts_the_name_before_the_mark():
    out, entries, warnings = number_citations("[+@tam] found that X.\n", NAMED)

    assert out.startswith('<span class="cite-author">Tam et al.</span> ')
    assert '<a id="citeref-1-1" href="#cite-1">1</a>' in out
    assert [e.key for e in entries] == ["tam"] and warnings == []


def test_narrative_citation_numbers_like_a_plain_one():
    out, entries, _ = number_citations("[+@tam] said it, and again[@tam].\n", NAMED)

    assert len(entries) == 1 and entries[0].refs == 2
    assert out.count(">1</a>") == 2


def test_narrative_citation_on_an_entry_with_no_author_stays_literal_and_warns():
    out, entries, warnings = number_citations("[+@plain] argued.\n", NAMED)

    assert "[+@plain]" in out and "cite-author" not in out
    assert entries == []
    assert any("plain" in w and "author" in w for w in warnings)


def test_narrative_sigil_inside_a_code_fence_is_left_alone():
    src = "Prose.\n\n```markdown\nSee [+@tam] here.\n```\n"
    out, entries, _ = number_citations(src, NAMED)

    assert "[+@tam]" in out and entries == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_citations.py -k narrative -v`
Expected: FAIL — `[+@tam]` does not match `_CITE`, so it is left literal and `entries == []`; the first assertion on `out.startswith(...)` fails.

- [ ] **Step 3: Write the implementation**

Replace `_CITE` (currently line 21):

```python
# [@a], [@a; @b], and the narrative forms [+@a] / [-@a]. Brackets are still
# required: a bare @key stays literal so citations and cross-references remain
# separable at the parser rather than by convention (see design.md §7.5).
_CITE = re.compile(r"\[([+-]?)@[\w-]+(?:[ \t]*;[ \t]*@[\w-]+)*\]")
```

Replace `number_citations` entirely:

```python
def number_citations(
    src: str, bib: dict, nocite: tuple[str, ...] | list[str] = ()
) -> tuple[str, list[Entry], list[str]]:
    """Rewrite [@key] spans to numbered links; return (src, entries, warnings).

    One pass suffices because a call-site id is always `citeref-N-K`, unlike the
    footnote scheme where the suffix appears only when a note is cited twice.
    The `-` form emits no number, so it needs nothing patched afterwards either.
    """
    sources, warnings = _normalise(bib)
    spans = fence_spans(src)
    entries: dict[str, Entry] = {}
    out, last = [], 0

    def warn(message: str) -> None:
        if message not in warnings:
            warnings.append(message)

    for m in _CITE.finditer(src):
        if in_span(m.start(), spans):
            continue
        sigil = m.group(1)
        keys = _KEY.findall(m.group(0))

        missing = [k for k in keys if k not in sources]
        if missing:
            for k in missing:
                warn(f"citation [@{k}] has no bibliography entry")
            continue  # the whole span stays literal — visible, never vanished

        author = None
        if sigil:
            author = sources[keys[0]].author
            if author is None:
                warn(f"citation [{sigil}@{keys[0]}] is narrative but the entry "
                     f"declares no author")
                continue

        out.append(src[last:m.start()])
        last = m.end()

        links = []
        for k in keys:
            entry = entries.get(k)
            if entry is None:
                entry = entries[k] = Entry(
                    key=k, body=sources[k].text, number=len(entries) + 1,
                    author=sources[k].author,
                )
            entry.refs += 1
            links.append(f'<a id="citeref-{entry.number}-{entry.refs}" '
                         f'href="#cite-{entry.number}">{entry.number}</a>')

        prefix = f'<span class="cite-author">{author}</span> ' if sigil == "+" else ""
        out.append(f'{prefix}<span class="cite-ref">[{", ".join(links)}]</span>')

    out.append(src[last:])
    return "".join(out), list(entries.values()), warnings
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_citations.py -v`
Expected: PASS — all of them. The sigil-less path emits the same bytes as before; the local `warn` helper reproduces the previous de-duplication that was inlined in the `missing` branch.

- [ ] **Step 5: Commit**

```bash
git add scriptorium/citations.py tests/test_citations.py
git commit -m "feat(citations): [+@key] renders the author name before the mark"
```

---

### Task 3: The `[-@key]` author-only form

**Files:**
- Modify: `scriptorium/citations.py` (`number_citations`, `process_citations`)
- Test: `tests/test_citations.py`

**Interfaces:**
- Consumes: everything from Tasks 1–2.
- Produces: `process_citations` now passes `nocite` into `number_citations`; `number_citations` warns about author-only sites whose work is never numbered.

- [ ] **Step 1: Write the failing tests**

```python
def test_author_only_emits_the_name_and_no_mark():
    out, entries, _ = number_citations(
        "[-@tam]'s framework applies.[@tam]\n", NAMED
    )

    assert '<span class="cite-author">Tam et al.</span>\'s framework' in out
    assert out.count("cite-ref") == 1        # only the real citation numbered
    assert len(entries) == 1 and entries[0].refs == 1


def test_author_only_alone_creates_no_entry_and_warns():
    out, entries, warnings = number_citations("[-@tam] is well known.\n", NAMED)

    assert '<span class="cite-author">Tam et al.</span>' in out
    assert entries == []
    assert any("tam" in w and "never cited" in w for w in warnings)


def test_author_only_is_quiet_when_the_work_is_in_nocite():
    _, entries, warnings = number_citations(
        "[-@tam] is well known.\n", NAMED, nocite=["tam"]
    )

    assert entries == [] and warnings == []


def test_author_only_on_an_entry_with_no_author_stays_literal_and_warns():
    out, _, warnings = number_citations("[-@plain] argued.\n", NAMED)

    assert "[-@plain]" in out and "cite-author" not in out
    assert any("plain" in w and "author" in w for w in warnings)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_citations.py -k author_only -v`
Expected: FAIL — Task 2 numbers every matched span, so `[-@tam]` currently renders a mark and creates an entry.

- [ ] **Step 3: Write the implementation**

In `number_citations`, add the author-only collector beside `entries`:

```python
    entries: dict[str, Entry] = {}
    author_only: list[str] = []
```

Insert the `-` branch immediately after `last = m.end()` and before the `links` loop:

```python
        if sigil == "-":
            # No mark, so no entry: a work in the references list with a number
            # nothing points at is worse than no entry. Plain text, not a link —
            # linking would need a number that may not exist yet at this point
            # in the pass, and one pass is worth more than a hyperlink on a name.
            author_only.append(keys[0])
            out.append(f'<span class="cite-author">{author}</span>')
            continue
```

Replace the return with the end-of-document check:

```python
    out.append(src[last:])

    # Deferred to here, not checked at the call site: whether a work is cited
    # elsewhere is only knowable once the whole document has been walked.
    for key in author_only:
        if key not in entries and key not in nocite:
            warn(f"[-@{key}] names an author but the work is never cited")

    return "".join(out), list(entries.values()), warnings
```

In `process_citations`, pass `nocite` through and read entry text from the normalised sources:

```python
def process_citations(src: str, meta: dict) -> tuple[str, list[str]]:
    """Entry point: number citations and emit the references section."""
    bib = meta.get("bibliography") or {}
    nocite = meta.get("nocite") or []
    head, body = split_frontmatter(src)
    marked, entries, warnings = number_citations(body, bib, nocite)

    # Malformed-entry warnings were already reported by number_citations.
    sources, _ = _normalise(bib)
    for key in nocite:
        if key not in sources:
            warnings.append(f"nocite key {key!r} has no bibliography entry")
        elif not any(e.key == key for e in entries):
            entries.append(Entry(key=key, body=sources[key].text,
                                 number=len(entries) + 1,
                                 author=sources[key].author))

    if not entries:
        return head + marked, warnings

    block = _component(entries)
    at = _placeholder(marked)
    if at:
        return head + marked[: at[0]] + block + marked[at[1] :], warnings
    return head + marked.rstrip() + "\n\n" + block, warnings
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_citations.py -v`
Expected: PASS — all of them, including `test_nocite_adds_an_entry_without_a_citation` and `test_nocite_key_with_no_entry_warns`, which now route through `_normalise`.

- [ ] **Step 5: Commit**

```bash
git add scriptorium/citations.py tests/test_citations.py
git commit -m "feat(citations): [-@key] names an author without numbering it"
```

---

### Task 4: Reject a sigil on a multi-key span

**Files:**
- Modify: `scriptorium/citations.py` (`number_citations`)
- Test: `tests/test_citations.py`

**Interfaces:**
- Consumes: everything from Tasks 1–3.
- Produces: no new symbols; one new guard and one new warning string.

- [ ] **Step 1: Write the failing test**

```python
def test_a_sigil_on_a_multi_key_span_stays_literal_and_warns():
    out, entries, warnings = number_citations("[+@tam; @fan] agree.\n", NAMED)

    assert "[+@tam; @fan]" in out          # not half-rewritten
    assert entries == [] and "cite-author" not in out
    assert any("one key" in w for w in warnings)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_citations.py -k multi_key_span -v`
Expected: FAIL — the span matches, `keys[0]` has an author, so it currently renders "Tam et al. [1, 2]".

- [ ] **Step 3: Write the implementation**

In `number_citations`, insert the guard between the `missing` check and the `author` lookup:

```python
        if sigil and len(keys) > 1:
            # "Tam et al. and Fan [1, 2]" needs a conjunction, and which
            # conjunction is a language-and-style decision the engine has no
            # business making. Authoring error, not a concatenation.
            warn(f"narrative citation [{sigil}@…] takes one key, not {len(keys)}")
            continue
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_citations.py -v`
Expected: PASS — all of them.

- [ ] **Step 5: Commit**

```bash
git add scriptorium/citations.py tests/test_citations.py
git commit -m "feat(citations): a narrative sigil takes exactly one key"
```

---

### Task 5: Integration — back-compat, end-to-end, project-level

**Files:**
- Test: `tests/test_citations.py`

**Interfaces:**
- Consumes: everything from Tasks 1–4. No production code should change in this task. If a test here fails, the fix belongs in the task that introduced the defect.

- [ ] **Step 1: Write the failing tests**

The end-to-end idiom in this file is `render_pdf` (imported at line 150) followed by an inline `subprocess.run(["pdftotext", …])`. There is no shared helper — match what is there.

```python
def test_string_entries_render_exactly_as_before():
    # The whole feature is an addition to a shipped format: a document that
    # uses none of it must produce the identical pre-processor output. Asserted
    # on the rewritten source, not on PDF bytes — a PDF carries timestamps and
    # font subset ids, so a byte-compare there fails for unrelated reasons.
    src = "A claim.[@parnas] Another.[@vogel] And again.[@parnas]\n"
    out, entries, warnings = number_citations(src, BIB)

    assert out == (
        'A claim.<span class="cite-ref">'
        '[<a id="citeref-1-1" href="#cite-1">1</a>]</span> '
        'Another.<span class="cite-ref">'
        '[<a id="citeref-2-1" href="#cite-2">2</a>]</span> '
        'And again.<span class="cite-ref">'
        '[<a id="citeref-1-2" href="#cite-1">1</a>]</span>\n'
    )
    assert [(e.key, e.number, e.refs) for e in entries] == [
        ("parnas", 1, 2), ("vogel", 2, 1),   # parnas cited twice, vogel once
    ]
    assert warnings == []


def test_narrative_name_reaches_the_pdf_and_no_sigil_syntax_leaks(tmp_path):
    src = ("---\ntheme: article\ntitle: T\n"
           "bibliography:\n  tam:\n    author: Tam et al.\n"
           "    text: \"Tam, Z. R. Let Me Speak Freely. 2024.\"\n"
           "---\n\n# H\n\n[+@tam] found it, and [-@tam] refined it.\n")
    out = tmp_path / "narr.pdf"
    report = render_pdf(src, str(out), execute=False)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert text.count("Tam et al.") == 2      # once per narrative form
    assert "Tam, Z. R." in text               # the entry itself
    assert "[1]" in text                      # the + form still marks
    assert "[+@" not in text and "[-@" not in text
    assert "cite-author" not in text          # the span never leaks as text
    assert report.warnings == []


def test_project_level_mapping_bibliography_reaches_the_render(tmp_path):
    # project.py:49 passes `bibliography` through verbatim, so mapping entries
    # should already work. "No change needed" is a claim, so it gets a test.
    from scriptorium.project import load

    (tmp_path / "a.md").write_text("# One\n\n[+@tam] found it.\n")
    (tmp_path / "scriptorium.yaml").write_text(
        "theme: book\n"
        "bibliography:\n  tam:\n    author: Tam et al.\n"
        "    text: \"Tam, Z. R. Let Me Speak Freely. 2024.\"\n"
        "files: [a.md]\n")
    proj = load(tmp_path / "scriptorium.yaml")

    assert proj.meta["bibliography"]["tam"]["author"] == "Tam et al."
    assert "bibliography" not in proj.vars   # content, not appearance

    out = tmp_path / "b.pdf"
    render_pdf(proj.src, str(out), theme_name=proj.theme, execute=False,
               vars=proj.vars, project_meta=proj.meta)

    import subprocess
    text = subprocess.run(["pdftotext", str(out), "-"],
                          capture_output=True, text=True).stdout
    assert "Tam et al." in text and "Tam, Z. R." in text
```

- [ ] **Step 2: Run the tests to verify they fail or pass honestly**

Run: `uv run pytest tests/test_citations.py -k "exactly_as_before or reaches_the_pdf or project_level" -v`
Expected: the back-compat and project-level tests should **pass immediately** — that is the point of writing them. The end-to-end sigil test fails only if something leaked.

If the back-compat test fails, Task 2 or 3 changed frozen output: fix `citations.py`, do not adjust the expected string.

- [ ] **Step 3: Verify the tests can actually fail**

A test that cannot fail is worth less than none. Temporarily break `citations.py` — change the `cite-author` span to `cite-name` — and confirm the end-to-end test goes red. Then revert the break.

Run: `uv run pytest tests/test_citations.py -k reaches_the_pdf -v`
Expected: FAIL while broken, PASS after revert.

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest`
Expected: PASS, entire suite.

- [ ] **Step 5: Commit**

```bash
git add tests/test_citations.py
git commit -m "test(citations): back-compat, end-to-end and project-level coverage"
```

---

### Task 6: Documentation and the theme hook

**Files:**
- Modify: `docs/design.md` (§7.5)
- Modify: `tasks.md` (the *Proper CSL citations* item)
- Modify: `README.md` (the citation bullet)
- Modify: `CHANGELOG.md` (a `### Features` entry)

**Interfaces:**
- Consumes: the shipped behaviour from Tasks 1–5.
- Produces: nothing code depends on.

- [ ] **Step 1: Do NOT add a CSS rule — document the hook instead**

The spec called for an "unstyled hook" in `themes/base/styles.css` beside
`.cite-ref` (line 124). Written out, that rule is
`.cite-author { font: inherit; color: inherit; }` — which is what a `<span>`
already does. It is dead code that only looks like configuration, so it is not
added.

`.cite-author` still exists in the emitted HTML and is still the theming hook;
it simply needs no base rule to be one. Record it in `docs/design.md` §7.5
(Step 2 below) so a theme author can find it, and leave `styles.css` untouched.

- [ ] **Step 2: Rewrite the retired claim in `docs/design.md` §7.5**

Replace the paragraph beginning "**Entries are opaque Markdown prose, and that is the defining trade.**" with:

```markdown
**Entries are opaque Markdown prose, and that is the defining trade.** The engine
numbers, orders and links them; it never inspects them for an author or a year.

What that rules out is *extraction*, not *declaration*. An entry may be written
as an `{author, text}` mapping, and the declared name is what the narrative forms
`[+@key]` (name, then mark) and `[-@key]` (name alone) emit — the engine reads a
field, never the prose beside it. Full author-date — `(Tam, 2024)` at every site,
alphabetical ordering, `2026a` / `2026b` disambiguation — does still need a real
bibliography parser (`.bib` / CSL-JSON) and a style engine, and remains a separate
feature tracked in `tasks.md`. The trade is unchanged: entry *formatting* is
exactly what CSL exists to do, and doing it halfway produces output that reads as
a worse IEEE.

There is deliberately no command that emits a year. In a numeric scheme the
number does the identifying, so a year would duplicate what the entry already
says while resolving nothing.

The name is emitted as `<span class="cite-author">`, which is the theming hook;
the base stylesheet gives it no rule, because body prose is what it should be.
```

- [ ] **Step 3: Narrow the `tasks.md` item**

Replace the *Proper CSL citations* bullet with:

```markdown
- [ ] **Proper CSL citations.** Bibliography entries are prose, optionally with a
      declared `author:` for the narrative forms (v0.6.0). What remains out of
      reach is everything that needs *structured* entries: author-date marks
      `(Parnas, 1972)` at every site, alphabetical-by-author ordering, `2026a` /
      `2026b` disambiguation, and entry formatting itself. That means a real
      bibliography parser (`.bib` / CSL-JSON) plus a CSL style engine. Its own
      spec when the time comes. Raised 2026-08-11; narrowed 2026-08-12 when the
      narrative forms shipped.
```

- [ ] **Step 4: Extend the README citation bullet**

Add to the `- **Citations**` bullet in `README.md`:

```markdown
  Narrative forms put the author's name in the running text: `[+@key]` renders
  `Tam et al. [1]` and `[-@key]` renders `Tam et al.` alone. Both need the entry
  written as a mapping with an `author:` field; a plain prose entry keeps working
  and supports `[@key]` as before.
```

- [ ] **Step 5: Add the CHANGELOG entry**

Under the next version's `### Features`:

```markdown
- **Narrative citations.** `[+@key]` renders the author's name before the
  numbered mark (`Tam et al. [1]`); `[-@key]` renders the name alone, with no
  mark and no references entry. Both read a declared `author:` from an
  `{author, text}` bibliography entry — the engine never parses a name out of
  entry prose. Prose-string entries and bare `[@key]` are unchanged.
```

- [ ] **Step 6: Verify the docs match the code**

Run: `uv run pytest`
Expected: PASS.

Then render the repo's own example to confirm the CSS hook does not disturb existing output:

Run: `uv run scriptorium render examples/article.md`
Expected: renders without warnings; the references section looks as it did.

- [ ] **Step 7: Commit**

```bash
git add docs/design.md tasks.md README.md CHANGELOG.md
git commit -m "docs(citations): narrative forms, and narrow the CSL claim to what remains"
```

---

## Acceptance

The motivating document is `vault/+/agent_drafts/sota/sota-llm-output-formats-2026-08-11.md` in the Workspace repo — 47 markers in the retired `^[N](#ref-N)^` convention, 18 trailing and 29 in subject position. After this plan ships, converting it should require no hand-written author names: the 18 become `[@key]`, the 29 become `[+@key]`, and every name comes from the bibliography.

That conversion is **not part of this plan** — it is a separate change to a different repo, and it needs the `author:` fields authored for all 13 works first.
