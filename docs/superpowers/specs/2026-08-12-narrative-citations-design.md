# Narrative citations — author names in the running text

*Status: approved, not yet implemented. 2026-08-12.*

v0.5.0 shipped `[@key]` → `[1]` against a prose bibliography. That covers the
citation that hangs off the end of a claim. It does not cover the one that *is*
the subject of the sentence:

> **Tam et al.** [9] found that constrained decoding costs reasoning accuracy.

Today an author writing that sentence has to type the name themselves, which
denormalises it across every call site, or fall back to a bare number as the
subject — "[9] found that…" — which no copy editor accepts.

This design adds two sigils, `+` and `-`, that put the author's name in the
running text. It is deliberately *not* the CSL feature: the engine still never
reads a prose entry looking for an author. The author declares the name.

## Goals

- `[+@key]` renders `Tam et al. [9]` — the name, then the ordinary numbered mark.
- `[-@key]` renders `Tam et al.` — the name alone, no mark, no new entry.
- `[@key]` is untouched, and a bibliography of plain strings keeps rendering
  byte-identically.
- A narrative form on an entry with no declared name fails **visibly**, in the
  house manner: the span stays literal and a warning is reported.

## Non-goals — and a correction to the last spec

Still not built: CSL or BibTeX parsing, `.bib` files, page locators, *ibid.*,
notes-bibliography styles, alphabetical-by-author ordering, `2026a` / `2026b`
disambiguation, and any command that emits a year.

**The previous spec's permanence claim needs amending, and this is the point
worth reading.** `2026-08-11-citations-design.md` says:

> Author-date is not deferred — it is impossible by construction. Because an
> entry is an opaque prose string, the engine cannot know which words are the
> author and which the year.

The reasoning is sound and the conclusion is drawn too wide. What is impossible
is for the engine to **extract** an author from prose. It was never impossible
for the author to **declare** one. The invariant that matters — *the engine
never inspects an entry's prose* — survives this feature completely intact; a
declared `author:` is a separate field the engine reads directly, not a parse of
the prose next to it.

So the sentence to retire is "impossible by construction", not the principle
underneath it. Full author-date — `(Tam, 2024)` at every site, alphabetical
ordering, letter disambiguation — genuinely does still need a bibliography
parser and a style engine, and stays open in `tasks.md`. What this feature
claims is narrower: **a name in the running text, next to a numeric mark**,
which is ordinary IEEE/Vancouver narrative citation and needs no style engine at
all.

Deliberately cut during design: a year command (`[@key]` → `2024`). In a numeric
scheme the year does no identifying work — the number does — so emitting it
would duplicate what the entry already says while resolving nothing. When CSL
lands, the year arrives with it, from structured data, which is its proper home.

## Syntax

| Form | Renders | |
|---|---|---|
| `[@tam-2024]` | `[9]` | unchanged |
| `[+@tam-2024]` | `Tam et al. [9]` | `+` **adds** the author |
| `[-@tam-2024]` | `Tam et al.` | `−` **removes** the number |
| `[@a; @b]` | `[9, 2]` | unchanged; multi-key |
| `[+@a; @b]` | — | not supported; stays literal, warns |

The mnemonic is the arithmetic: `+` adds something to the mark, `-` takes the
mark away. The sigil sits *outside* the `@`, so the key itself is untouched and
the existing `_KEY` pattern keeps working unchanged.

**A pandoc user carries one crossed expectation** — there, `-@key` suppresses the
*author* and yields a bare year. The collision is bounded rather than resolved:
scriptorium emits a year nowhere, in any form, so `-@key` can never be mistaken
for having produced one. The alternative was inventing a third sigil with no
mnemonic at all, which reads worse in the source and is harder to remember.

**Multi-key with a sigil is an authoring error, not a concatenation.** `[+@a; @b]`
would have to render "Tam et al. and Fan [9, 2]", and the conjunction is a
language-and-style decision the engine has no business making. It stays literal
and warns, exactly as an unknown key does.

Sigils inside a fenced code block are left alone, like everything else the
pre-processor sees there.

## The bibliography entry — two shapes

An entry is either a string, exactly as today, or a mapping:

```yaml
bibliography:
  yang-2025: 'Yang, J., … (2025). *StructEval…*'      # string — still valid
  tam-2024:
    author: Tam et al.
    text: 'Tam, Z. R., … (2024). *Let Me Speak Freely?…*'
```

`text:` is the prose entry — the same opaque Markdown a string entry carries, and
the only thing that reaches the references section. `author:` is a literal string
the author writes, and it is **never derived**.

That last word is the design decision, so it deserves its reason. Deriving the
name from the key is the tempting shortcut: `tam-2024` → "Tam et al." is right
most of the time. It is wrong for `willard-2023`, which is two authors and wants
"Willard and Louf", and wrong for `fan-2026`, which is one author and must not
say "et al." at all. Both failures are silent, both are in the small set of
things an academic reader actually notices, and a rule that is right most of the
time is precisely the "worse IEEE" the previous spec warned against. A mapping
with two keys costs the author one line and cannot be wrong.

There is no `year:` field. Nothing reads it, and a field nothing reads is an
invitation to fill it in for nothing.

A mapping with an `author:` but no `text:` is a malformed entry: it warns and the
work is treated as absent, since there is nothing to put in the references list.

## Behaviour at the edges

Four rules, each following the module's existing doctrine that a broken citation
stays **visible, never vanished**:

1. **`[+@k]` numbers.** It emits a mark, so it creates or reuses an entry and
   takes a back-link, indistinguishably from `[@k]`.
2. **`[-@k]` does not number.** It emits no mark, so it must not create an entry
   — that would put a work in the references list with a number nothing points
   at. If the work is not cited somewhere else (or listed in `nocite:`), it
   warns.
3. **Either sigil on an entry with no `author:`** leaves the whole span literal
   and warns — `+` and `-` alike, since both need a name and neither has one.
   The engine does not fall back to the key, to the first word of `text:`, or to
   anything else.
4. **`[-@k]` emits plain text, not a link.** Linking the name would mean knowing
   the entry's number, which may not exist yet at that point in the pass. The
   module's docstring records that one pass suffices, and a hyperlink on a name
   the reader can already find by its neighbouring citation is not worth
   trading that for.

Rule 2's warning needs the whole document, not the local site: author-only
call-sites are collected during the pass and checked against the entry table
once it is complete. This does not reintroduce a second rewriting pass — the
output of `[-@k]` never depends on a number, so nothing has to be patched
afterwards.

## Implementation

All of it is in `citations.py` except one theme file. The pipeline position is
unchanged: `galley.py:666` calls `process_citations(src, meta)` immediately after
`process_footnotes`, so a citation inside a note body still numbers by where the
note renders.

### `citations.py`

- **`_CITE`** gains an optional leading sigil:
  `r"\[([+-]?)@[\w-]+(?:[ \t]*;[ \t]*@[\w-]+)*\]"`. `_KEY` is unchanged — the
  sigil is outside the `@`, so key extraction is untouched.
- **`Entry`** gains `author: str | None = None`.
- **A normaliser** runs at the top of `process_citations`, where
  `bib = meta.get("bibliography") or {}` currently assumes `dict[str, str]`. It
  maps each value to `(text, author)`: a string becomes `(value, None)`; a
  mapping reads `text` and `author`. Everything downstream — `_component`,
  `_placeholder`, `nocite` handling — keeps seeing prose bodies and needs no
  change.
- **`number_citations`** grows the three branches. The sigil-less path emits
  exactly the bytes it emits today; this is a hard requirement, checked by test,
  not an aspiration.
- Emission for the two new forms:

  ```html
  <!-- [+@tam-2024] -->
  <span class="cite-author">Tam et al.</span> <span class="cite-ref">[<a …>9</a>]</span>
  <!-- [-@tam-2024] -->
  <span class="cite-author">Tam et al.</span>
  ```

### `project.py`

No change is needed: line 49 already passes `bibliography` through verbatim, so
a multi-file project can carry mapping entries the moment `citations.py`
understands them. "No change needed" is a claim, so it gets a test rather than a
shrug — `test_project_level_bibliography_reaches_the_render` has the shape.

### Themes

`.cite-author` is the theming hook, and it gets **no base rule**. Written out,
an "unstyled hook" is `.cite-author { font: inherit; color: inherit; }` — which
is what a `<span>` already does. That is dead code wearing the costume of
configuration; the class is a hook whether or not `styles.css` mentions it. It
is documented in §7.5 instead, so a theme author can find it. Themes that want
the name distinct add their own rule. `themes/base/styles.css` and
`themes/base/components/references.html` are both untouched.

## Documentation

Two places assert the retired claim and must be rewritten in the same commit as
the code, or the repo contradicts itself. Two more need the ordinary additive
update:

- **`docs/design.md` §7.5** — the "impossible by construction" paragraph, amended
  as argued above: the engine never inspects prose; a declared name is not an
  inspection; full author-date still needs CSL.
- **`tasks.md`** — the *Proper CSL citations* item says author-date is
  "impossible by construction, not deferred". Narrow it to what remains open:
  alphabetical ordering, `2026a`/`2026b`, and entry formatting.
- **`README.md`** — the citation bullet gains the two new forms.
- **`CHANGELOG.md`** — a `### Features` entry under the next version.

## Testing

`tests/test_citations.py` has 21 tests and a clear one-rule-per-test shape to
extend. New coverage, one test per rule above:

- `[+@k]` renders name then mark; `[-@k]` renders name only.
- `[-@k]` alone creates **no** references entry, and warns.
- `[-@k]` alongside a real `[@k]` elsewhere creates one entry and does not warn.
- `[+@k]` on a string entry (no author) stays literal and warns.
- `[+@a; @b]` stays literal and warns.
- A mapping entry with no `text:` warns.
- Sigils inside a code fence are untouched.
- **Back-compat:** for a document with only string entries and only `[@k]` spans,
  the string `number_citations` returns is byte-identical to v0.5.0's. Assert on
  the pre-processor's output, not on PDF bytes — a PDF carries timestamps and
  font subset ids, so a byte-compare there is a test that fails for reasons that
  have nothing to do with citations.
- End-to-end: the author's name reaches the PDF and no sigil syntax leaks —
  `test_citation_text_reaches_the_pdf_and_no_syntax_leaks` is the pattern.
- Project-level: a mapping entry in `scriptorium.yaml` reaches the render.

The back-compat test is the one that matters most, because the whole feature is
an addition to a shipped format. Per `AGENTS.md`, `uv run pytest` must pass
before any commit lands.

## The motivating document

`vault/+/agent_drafts/sota/sota-llm-output-formats-2026-08-11.md` carries 47
markers in the retired `^[N](#ref-N)^ ` convention: 18 trailing, which convert
to plain `[@key]`, and **29 in subject position**, which are exactly what `[+@key]`
is for. It is the acceptance case — after this ships, that document should
convert with no hand-written author names anywhere.
