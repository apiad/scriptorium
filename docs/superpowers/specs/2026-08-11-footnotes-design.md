# Footnotes as endnotes — design

*Status: implemented in v0.4.0. 2026-08-11.*

Scriptorium claims footnote support in two places and delivers it in neither.
`docs/design.md` line 104 lists footnotes among the supported Markdown, and §7.4
commits to endnotes as the default rendering. In fact `parse.py` enables only
`table`, `dollarmath`, `attrs` and `attrs_block` — so `[^a]` and `[^a]: note`
both reach the PDF as literal text.

The gap has a cost outside this repo: the workspace report standard in
`CLAUDE.md` tells authors *not* to use `[^id]` and to hand-number citations as
`^[N](#ref-N)^` with a matching `### N {#ref-N}` section. `citations.py` exists
to serve that hand-rolled convention.

This design replaces both with real Markdown footnotes.

## Goals

- `[^a]` / `[^a]: text` work, with automatic numbering.
- Notes collect into an endnotes section at the end of the **document** or the
  end of each **chapter**, configurable.
- Bottom-of-page footnotes as a third mode, now that they are cheap (see
  *Per-page footnotes* below).
- `citations.py` and the `ref-N` convention are deleted, not deprecated.
- Cross-references stop consuming the `@key` namespace, so a future citations
  feature has somewhere to live — and prose stops silently vanishing.

Non-goals: CSL / BibTeX bibliographies, author-date citation styles, footnotes
inside deck slides beyond what falls out of `document` mode.

## Syntax

Standard Markdown, no new vocabulary:

```markdown
The claim.[^a]

[^a]: The supporting note, with a [link](https://example.com).
```

A note referenced more than once gets one back-link per occurrence — the same
double-sided behaviour `citations.py` provided, kept.

## Configuration

A `footnotes` key, resolved with the precedence already established for `theme:`
and `vars:` — frontmatter wins over the theme:

| Value | Behaviour |
|---|---|
| `document` | one endnotes section at the end of the document |
| `chapter` | one endnotes section before each `#` (h1), numbering restarts at 1 |
| `page` | true bottom-of-page footnotes, via CSS |

Theme defaults, declared in `theme.yml`: `book` → `chapter`; `article`,
`report`, `note`, `deck` → `document`. Resolved by `resolve_footnote_mode` in
`footnotes.py`, reading `frontmatter(src).get("footnotes")` first and falling
back to `theme.meta.get("footnotes", "document")` — mirroring
`resolve_theme_name` in `galley.py`. An unrecognised value is a hard error, not
a silent fallback.

`chapter` is defined by `#` (h1) because that is already what the `book` theme
counts (`counter-increment: chapter` in `themes/book/styles.css`), so "chapter"
means the same thing to footnotes, to running heads, and to cross-references.

## Implementation

### Why not the markdown-it plugin

`mdit_py_plugins.footnote.footnote_plugin` is the obvious tool and it cannot be
used here. `parse()` renders **block by block** — `_md.render(_rewrite_refs(block))`
at `parse.py:300`, once per block — while the plugin resolves references against
definitions collected within a *single* render call. Verified 2026-08-11: given
the marker and the definition in separate calls, the marker renders as literal
`[^a]` text and the definition renders to nothing at all.

Rewriting `parse()` to render the whole document in one pass would dismantle the
unit model the entire engine is built on. So the plugin is out.

### A source-to-source pre-processor

`scriptorium/footnotes.py` takes the pipeline slot `citations.py` holds today in
`galley.render_pdf` — and takes its *shape* too. That `citations.py` was written
as a pre-processor rather than a plugin now reads as a consequence of the same
constraint, not an arbitrary choice.

`process_footnotes(src, mode)` runs on the raw source before `parse()` and:

1. Collects `[^id]: body` definitions (a definition runs to the next blank line
   that is not an indented continuation) and removes them from the flow.
2. Rewrites each `[^id]` marker in order of appearance to
   `<sup class="footnote-ref" id="fnref-N"><a href="#fn-N">N</a></sup>`.
   Inline HTML passes through CommonMark untouched, so no parser change is
   needed. A marker whose definition is missing is left as literal text and
   reported.
3. Emits the collected notes at the boundary the mode dictates.

Because numbering is ours rather than the plugin's, the per-chapter restart is
native: the counter simply resets at each `#`. Ids stay unique across the
document by carrying the chapter index (`fn-2-1`, `fnref-2-1`).

No new dependency is added.

### Emitting the notes

Notes are emitted as a `::: footnotes` component — scriptorium's existing
extension mechanism — whose content is a Markdown ordered list, one item per
note, each carrying an inline anchor and one back-link per reference:

```markdown
::: footnotes
1. <span id="fn-1"></span>The note body, **markdown intact**. [↩](#fnref-1)
:::
```

This matters: note bodies are author prose containing links, emphasis and code,
and routing them through the component path means the real Markdown renderer
handles them. `citations.py` had to hand-roll a mini-renderer (`_md_fragment`,
with separate regexes for links, bold and italic) precisely because it emitted
final HTML. We do not repeat that.

The `base` theme supplies the `footnotes` component template — as
`themes/base/components/footnotes.html`, since a theme's `components:` YAML key
carries hints (`keep_together`) rather than templates — so themes can restyle or
relabel the section without engine changes. The hint is `keep_together: false`:
an endnotes section is routinely taller than a page.

`document` mode emits one component at the end; `chapter` mode emits one
immediately before each `#` after the first, plus one at the end of the document
for the final chapter. Both preserve the single continuous HTML flow that
v0.3.0's CSS Fragmentation pagination depends on.

The alternative considered was segmenting the source by chapter and parsing each
segment independently. Rejected: it fragments the one-flow model and forces
cross-references, counters and the TOC to be re-stitched across segments.

### Per-page footnotes

WeasyPrint implements CSS GCPM footnotes: an element with `float: footnote` is
pulled to the foot of the page its anchor lands on and auto-numbered. Verified
2026-08-11 on a three-page render — note 1 at the foot of page 1, note 2 at the
foot of page 3.

**But GCPM wants the note's content inline at the anchor**, not in a section
elsewhere. Applying `float: footnote` to a marker floats the *marker* — the
footnote area ends up containing the text `[1]` while the note itself stays in
the body flow. Verified 2026-08-11.

So `page` mode is engine work, not a stylesheet. `process_footnotes` emits the
note body inline at the reference site, wrapped in
`<span class="footnote-inline">`, and emits no marker of its own so WeasyPrint's
generated call is the only one. It reuses the same definition map the other two
modes build, so the incremental cost is small — but it is not free, and the
earlier "CSS only" assessment of it was wrong.

**Limitation, documented rather than solved:** a note referenced more than once
has one body and several call sites. In `page` mode it is inlined at its *first*
reference; later markers render as a plain superscript carrying the same number
rather than duplicating the text. (As built they carry no link: there is one
body on one page, and a cross-page hop to it earns nothing in print.) `document` and `chapter` modes keep the
full multi-back-link behaviour.

Worth recording either way: `docs/design.md` §7.4 rejects per-page footnotes as
circular — "footnote height changes `content_h`". That was true of the Python
bin-packer it was written against. v0.3.0 handed document pagination to
WeasyPrint, so the circularity is now WeasyPrint's to resolve, and it does. §7.4
is corrected as part of this work.

### Styling

`.footnote-ref` and `.footnotes` styles land in `themes/base/styles.css`,
inheriting the superscript look v0.3.0 established for citations: small, raised,
accent-coloured, no underline. Markers carry the bare number — no brackets — so
the output matches the superscript form readers already have.

## Forward compatibility with citations

Footnotes are not citations, and this design deliberately does not build them.
A citation resolves a *key* against a bibliography database and formats it by a
style; a footnote is prose the author wrote at the point of reference. A future
citations feature (`.bib` / CSL-JSON, author-date and numeric styles, a generated
references section) gets its own spec. These are the boundaries it must be able
to rely on.

**Syntax namespace.** `[^id]` belongs to footnotes. `@key` and `[@key]` are
reserved for citations and must not be consumed here.

There is already a conflict, independent of this work. `_REF` in `parse.py`
matches `@type-id` with *any* hyphenated prefix, so common BibTeX keys are
silently rewritten into empty cross-reference anchors — verified 2026-08-11:

| Source | Today |
|---|---|
| `@fig-plot` | cross-reference (intended) |
| `@smith2020` | untouched |
| `@smith-2020` | `<a class="ref-smith" href="#smith-2020">` |
| `[@piad-morffis-2024]` | `<a class="ref-piad" href="#piad-morffis-2024">` |

**This is also a live correctness bug, and it is in scope for this work.** An
`@type-id` with no matching target renders as an *empty* anchor, so the text
disappears from the page. Verified 2026-08-11 — the source

```markdown
See @sec-intro and mail me @piad-morffis-2024.
```

renders in the PDF as `See and mail me .` Any `@word-word` in prose — a BibTeX
key, a GitHub handle, `@okta-`, `@colinhacks-` — is silently deleted. (Fenced
code is safe: fences become units before `_rewrite_refs` runs.)

The resolution is to restrict `_REF` to a known prefix set, which is Quarto's own
convention and frees the whole `@key` space:

```
fig- tbl- sec- eq- lst- thm- chap-
```

`chap-` is included because it is in real use in the workspace; Quarto's list
alone would have broken existing documents. Anything outside the set is left as
literal text — visible, not vanished. The set lives as a documented module-level
constant in `parse.py`.

A dangling reference *with* a known prefix still renders empty; making that warn
is a follow-up, not part of this work.

**Separate sections, separate counters.** Footnotes emit
`<section class="footnotes">`; a bibliography must emit a distinct container
(`<section class="references">`) with its own counter. A document may carry both
— a Chicago-style paper has explanatory notes *and* a reference list — so
neither may assume it owns "the section at the end". Note that a bibliography is
normally document-final even when `footnotes: chapter` puts notes per chapter;
placement is decided per feature, not shared.

**Reusable note insertion.** In notes-bibliography styles a citation *is* a
footnote. `footnotes.py` therefore exposes note insertion — anchor, body,
back-link, renumber — as a callable primitive rather than a closed
source-to-source transform, so a citation engine can emit into the footnote
apparatus instead of reimplementing it.

**Parallel configuration.** The `footnotes:` key leaves room for a sibling
`citations:` / `bibliography:` key resolved by the same frontmatter-over-theme
precedence.

## Deletion

Removed outright, not deprecated:

- `scriptorium/citations.py` and `tests/test_citations.py`
- the `process_citations` import and call in `galley.render_pdf`
- `.cite-sup` / `.cite-link` in `themes/base/styles.css`
- `.bib-entry` / `.bib-num` / `.bib-body` / `.bib-back` / `.bib-back-link` /
  `.cite-anchor` in `themes/article/styles.css`

Documents still written in the old convention do not crash; they degrade to
visible literal text and a stray `### N` heading.

## Migration

A one-off script in the workspace — **not** shipped in scriptorium, which stays
free of a legacy path for what was only ever a house convention. It rewrites
`^[N](#ref-N)^` → `[^N]` and `### N {#ref-N}` + body → `[^N]: body`.

24 workspace documents match the old convention; most are `vault/x/` archives and
drafts that will never render again. The script runs against live documents only:
`repos/librito-deng-cuba/` and
`vault/Efforts/Areas/University/Mincom/reporte-ia-industria.md`. Each is
re-rendered and compared before and after.

## Documentation

- Workspace `CLAUDE.md`: the report standard currently mandates the `ref-N`
  convention and states that scriptorium does not process `[^id]`. Both become
  false; rewritten to mandate Markdown footnotes.
- `docs/design.md`: §7.4 corrected (endnotes implemented; per-page no longer
  deferred), line 104's footnote claim becomes true.
- `README.md`: per-page footnotes drop off the roadmap; footnote syntax and the
  `footnotes:` knob documented under Authoring.
- `know-how/authoring-a-theme.md`: the `footnotes` theme key.

## Testing

Parsing is ours now, not a dependency's, so it is tested rather than assumed:

- `[^id]` markers and `[^id]: body` definitions are recognised; a definition
  spanning a wrapped line is captured whole; a marker with no definition stays
  literal and is reported; a definition with no marker is reported.
- A `[^id]` inside a fenced code block is left alone.
- Note bodies keep their Markdown — a link and bold text in a note survive to the
  PDF as a link and bold text, not as literal syntax.
- `resolve_footnote_mode` precedence: frontmatter beats `theme.yml` beats the
  `document` default.
- `chapter` mode splits notes into the right chapter, and a note anchored in
  chapter 2 does not appear in chapter 1's section.
- Numbering restarts at 1 in each chapter; ids stay unique across the document
  and every `href` resolves to an `id` that exists.
- A note referenced twice produces two back-links.
- `document` mode leaves one section at the end.
- `page` mode inlines note content and emits no leftover trailing section; a
  render-level test asserts the note text lands on the same page as its anchor.
- An unrecognised `footnotes:` value raises rather than silently defaulting.
- `_REF` narrowing: every prefix in the known set still resolves; `@smith-2020`,
  `@piad-morffis-2024` and `@colinhacks-x` survive as literal text; the
  `See @sec-intro and mail me @piad-morffis-2024.` case keeps its second half.
- Render-level: a book-theme document with notes in two chapters produces two
  `<section class="footnotes">` blocks in the emitted HTML.

Each test must be able to fail: after the suite is green, the chapter-splitting
assertion is mutation-checked by forcing `document` mode and confirming the
chapter test goes red — with a `cmp` that the mutation actually applied.
