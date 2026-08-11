# Numbered citations and a references section — design

*Status: approved, not yet implemented. 2026-08-11.*

v0.4.0 shipped footnotes and, in doing so, deliberately left the `@key` / `[@key]`
namespace free and fixed the boundary a citation feature would have to respect:
a distinct `<section class="references">` container with its own counter, because
a document may carry explanatory notes *and* a reference list at once.

This design fills that space with the smallest thing that is actually useful:
`[@key]` resolves against a bibliography the author declares, renders as a
numbered `[1]`, and collects into a generated references section.

## Goals

- `[@key]` and `[@a; @b]` resolve to `[1]` / `[1, 2]`, numbered by first
  appearance.
- A references section is generated — cited works only, plus anything named in
  `nocite`.
- Entries are authored as **Markdown prose** and reach the page through the real
  renderer, exactly as footnote bodies do.
- A document may carry footnotes and citations together, visually and
  structurally distinct.

## Non-goals, and one of them is permanent

Not built here: CSL or BibTeX parsing, `.bib` files, page locators
(`[@vogel, p. 42]`), *ibid.* / *op. cit.*, notes-bibliography styles where a
citation *is* a footnote, alphabetical-by-author ordering, `2026a` / `2026b`
disambiguation.

**Author-date is not deferred — it is impossible by construction.** Because an
entry is an opaque prose string, the engine cannot know which words are the
author and which the year, so it can never render `(Parnas, 1972)`. Reaching
author-date means a real bibliography parser and a style engine; that is a
different feature with its own spec, tracked in `tasks.md`. This is a deliberate
trade: entry *formatting* is precisely what CSL exists to do, and doing it
halfway yields output that reads as a worse IEEE.

## Syntax

| Form | Renders | |
|---|---|---|
| `[@vogel2011]` | `[1]` | the core case |
| `[@parnas1972; @vogel2011]` | `[1, 2]` | keys separated by `;` |
| `@vogel2011` (bare) | — | **not** a citation; left as literal text |
| `[@vogel2011, p. 42]` | — | **not** supported; the whole span stays literal |

Two exclusions are deliberate rather than arbitrary.

**Bare `@key` is rejected on purpose.** v0.4.0 narrowed `_REF` to a known prefix
set precisely because a loose `@word-word` pattern was rewriting ordinary prose
into empty anchors and deleting it from the page. A bare `@key` citation would
reintroduce that class of bug and, worse, would now genuinely collide with the
cross-reference syntax rather than merely resembling it. Requiring brackets keeps
citations and cross-references separable at the parser, not by convention.

**Page locators are rejected because they are not cheap.** `[@vogel, p. 42]`
means one source appears as `[1, p. 42]` and `[1, p. 87]`, which is exactly the
point where a numeric style needs *ibid.* handling or produces something a copy
editor rejects. That belongs with CSL.

A `[@key]` inside a fenced code block is left alone.

## Where the bibliography comes from

A single document declares it in frontmatter:

```yaml
---
theme: article
bibliography:
  parnas1972: "Parnas, D. L. *On the Criteria To Be Used in Decomposing Systems
    into Modules.* CACM 15(12), 1972. [ACM](https://dl.acm.org/doi/10.1145/361598.361623)."
  vogel2011: "Vogel, E. F. *Deng Xiaoping and the Transformation of China*. Belknap, 2011."
nocite: [brooks1975]
---
```

A multi-file project declares it in `scriptorium.yaml`, as a **top-level key**:

```yaml
theme: book
bibliography:
  parnas1972: "…"
files: [01-intro.md, 02-body.md]
```

This requires a small change to `project.py`, and the change is the point.
`project.load()` currently reads only `theme`, `vars`, `files` and `code`, and
`_strip_frontmatter` discards each chapter's frontmatter before concatenating —
so today a project's bibliography could only travel under `vars:`. But `vars:` is
the *appearance* contract (colors, fonts, title strings, `{{substitution}}`
targets); a bibliography is content. `load()` gains `bibliography` and `nocite`,
passed through to the meta the engine already receives, so the author's file says
what it means.

Numbering runs across the whole concatenated document — the same single continuous
flow the pagination depends on — so a book has one reference list and one
sequence, not one per chapter.

## Implementation

### `source.py` — the shared scanner

`citations.py` needs three things `footnotes.py` already has: fenced-code span
scanning, frontmatter splitting, and line-offset bookkeeping. Rather than reach
into another module's privates, those move to a new `scriptorium/source.py`:

```
FENCE / fence_spans(src) / in_span(pos, spans) / line_offsets(lines)
split_frontmatter(src) -> (head, body)
```

Its purpose states cleanly: *scan Markdown source without touching fenced code or
frontmatter.* Nothing else moves. In particular `_SUFFIX` and the letter-suffix
back-link ids stay private to `footnotes.py`, because citations do not reuse that
scheme — see below.

The left-to-right two-pass rewrite is a *shape* both modules follow, not shared
code. Citations need no chapter bucketing and no retroactive suffixing, so
abstracting the loop would cost more in indirection than it saves.

The refactor is mechanical, and the existing footnote suite is what holds it in
place: **it must stay green across the extraction with no test edited.**

The alternatives were folding citations into `footnotes.py` — one file serving
two features whose sources of truth differ (source text versus a frontmatter map)
— and importing `footnotes.py`'s underscore names, which couples the new module
to the old one's internals.

### Two back-link id schemes, on purpose

Footnotes emit `fnref-C-N` for a single reference and `fnref-C-Na` / `-Nb` when
there are several: the suffix appears only when it has to, which is why the
implementation needs two passes.

Citations do not inherit that. A call site is always `citeref-N-K` — entry `N`,
call site `K`, both always present, `K` counting from 1. It is simpler, it needs
no retroactive rewrite, and there is no back-compatibility reason to copy the
footnote scheme. Recorded here so the difference reads as a decision rather than
drift.

### The transform

`process_citations(src: str, meta: dict) -> tuple[str, list[str]]` — the rewritten
source and any warnings (see *Reporting* below):

1. Read `meta["bibliography"]` (a `key -> prose` map) and `meta["nocite"]`. With
   no bibliography and no citations, return the source untouched.
2. Split frontmatter aside.
3. Scan `[@a]` / `[@a; @b]` spans outside fenced code, left to right. Assign each
   newly-seen key the next number; record every call site for back-links.
4. Rewrite each span. One span becomes one `<span class="cite-ref">`; the
   brackets are literal text inside it, and each key contributes one anchor
   carrying its own call-site id:

   ```html
   <span class="cite-ref">[<a id="citeref-1-1" href="#cite-1">1</a>]</span>
   <span class="cite-ref">[<a id="citeref-1-2" href="#cite-1">1</a>,
                           <a id="citeref-2-1" href="#cite-2">2</a>]</span>
   ```

   Putting the id on the anchor rather than the wrapper is what makes a multi-key
   span work: each key needs its own back-link target, and there is only one
   wrapper.
5. Append `nocite` entries, in declared order, after the cited ones.
6. Emit the references component.

A span naming any unknown key is left entirely literal — the whole `[@a; @b]`, not
a half-rewritten fragment — and warned about. This mirrors a footnote marker with
no definition: visible, never vanished.

### Reporting — and a gap this closes

The v0.4.0 footnotes spec says an unresolved marker is "reported". **It is not.**
`number_and_mark` silently skips a marker whose key is unknown, and
`collect_notes` never mentions a definition nobody cited. The claim shipped
without a mechanism behind it, because there was no mechanism to use:
`Report` carries only `oversized`, and `render_pdf`'s document path returns it
empty — document renders emit no warnings at all today.

So this work adds the channel and then uses it:

- `Report` gains `warnings: list[str]`.
- `cli.py` prints them exactly as it already prints `oversized`.
- `process_citations` and `process_footnotes` both return `(src, warnings)`;
  `render_pdf` collects both into the `Report`.
- Footnotes retroactively warn on a marker with no definition and on a definition
  nobody references — making the v0.4.0 spec's claim true.

This is the one part of the work that **deliberately edits existing footnote
tests**, since `process_footnotes`' signature changes. Keep it a separate commit
from the `source.py` extraction, whose whole point is that the suite passes
untouched.

### Pipeline order

In `galley.render_pdf`, `process_citations` runs **immediately after**
`process_footnotes`, and the order is a decision, not an accident.

Footnote definitions conventionally sit at the end of the file while their notes
render where the mode dictates — in `chapter` mode, next to the chapter that
cites them. Running footnotes first means a `[@key]` written inside a note body
has already been moved to that rendered position, so it is numbered by where the
reader meets it. Running citations first would number it by where its *definition*
happened to sit in the source, which is not reading order.

It also puts the two generated sections in the conventional order: body, then
notes, then references.

### Emission and theming

Entries are emitted as a `::: references` component — the same extension
mechanism footnotes use — whose content is a Markdown ordered list, one item per
entry, each carrying an inline anchor and one back-link per call site:

```markdown
::: references
1. <span id="cite-1"></span>Parnas, D. L. *On the Criteria…* [↩](#citeref-1-1) [↩](#citeref-1-2)
:::
```

Routing entries through the component path means the real Markdown renderer
handles the author's links and emphasis. `themes/base/components/references.html`
ships `<section class="references">{{content}}</section>` with a
`keep_together: false` hint, because a reference list is routinely taller than a
page.

**Placement.** By default the component is appended at the end of the document.
If the author has written a bare `::: references` / `:::` pair themselves, that
one is filled in place and nothing is appended — so a book can put the list
before its appendices. Detection is a line matching `:::+ references` outside a
fenced span, with the matching close fence; the transform replaces the whole
block. Two such blocks is an error, not a silent pick.

### Appearance

Citations render as bracketed baseline `[1]`; footnotes stay bare superscript.
A document carrying both is then unambiguous at a glance, and the structural
separation the footnotes design fixed — distinct sections, distinct counters — is
visible rather than merely true. `.cite-ref` and `.references` styles land in
`themes/base/styles.css` alongside `.footnote-ref` and `.footnotes`.

## Behaviour

| Case | Result |
|---|---|
| `[@missing]` | whole span literal, warned |
| `[@known; @missing]` | whole span literal, warned |
| declared, never cited, not in `nocite` | omitted from the list |
| `nocite` names an undeclared key | warned; nothing emitted for it |
| no citations and no `nocite` | no section emitted |
| `[@key]` inside a fenced code block | untouched |
| same key cited three times | one entry, `[1]` at each site, three back-links |
| footnotes present too | separate section, separate counter, `[1]` vs `¹` |

## Documentation

- `README.md` — citation syntax and the `bibliography:` / `nocite:` keys under
  Authoring; drop "CSL citations" from the roadmap only when CSL ships, not now.
- `docs/design.md` — a new subsection beside §7.4, stating the prose-entry trade
  and why author-date is out.
- `know-how/authoring-a-theme.md` — the `references` component and its CSS hooks.
- `AGENTS.md` — `citations.py` and `source.py` in the pipeline module list.
- Workspace `CLAUDE.md` — the report standard gains the citation form beside the
  footnote form.

## Testing

- `[@a]` and `[@a; @b]` are recognised and numbered by first appearance.
- A key cited three times yields one entry, the same number at each site, and
  three back-links.
- `[@missing]` and `[@known; @missing]` stay literal in full.
- A `[@a]` inside a fenced code block is untouched.
- Entry prose keeps its Markdown — a link and bold text survive to the PDF as a
  link and bold text.
- `nocite` entries appear, after the cited ones, in declared order; an undeclared
  `nocite` key is warned about.
- A declared-but-uncited entry does **not** appear.
- A project's top-level `scriptorium.yaml` `bibliography:` reaches the render.
- Render-level: reference text reaches the PDF and no `[@key]` syntax leaks.
- Coexistence: a document with both apparatuses emits one
  `<section class="footnotes">` and one `<section class="references">`, with
  independent numbering.
- Order: a `[@key]` written inside a footnote body in `chapter` mode is numbered
  by where the note renders, not where its definition sat.
- The footnote suite stays green across the `source.py` extraction, unedited.

Each test must be able to fail. After the suite is green, the cited-only
assertion is mutation-checked by making the emitter include every declared entry
and confirming the uncited-entry test goes red — with a `cmp` proving the
mutation applied.
