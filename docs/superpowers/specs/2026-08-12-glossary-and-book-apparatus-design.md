# A glossary, and the last of the book apparatus

*Status: approved, not yet implemented. 2026-08-12. Verified against v0.7.0.*

*Mostly Harmless AI* — 128,000 words, 24 chapters — is moving off Quarto, and
scriptorium is the destination. Quarto is not staying behind for HTML and EPUB:
those renderers land later, in scriptorium, and until they do the book ships as
PDF only. So there is no back-compatibility to keep and the sources are free to
adopt scriptorium-native syntax.

The book already renders. A smoke test on 2026-08-12 put all 24 chapters through
`scriptorium render` with the `book` theme: **273 pages in 36 seconds**, 338 MB
peak, no warnings and no overflow. Quarto's LuaLaTeX PDF of the same manuscript
is 343 pages on letter. Prose, the 600 footnotes as chapter-scoped endnotes with
back-links, the auto-TOC with resolved page numbers, chapter numerals and running
heads all worked untouched.

What did not survive is one feature: **the glossary.** 584 markers over 506 keys,
a 515-entry data table, and a generated back-of-book section whose entries carry
the page numbers where each term appears. Today those markers print literally
into the PDF.

This design adds the glossary to the engine and finishes the `book` theme so the
manuscript needs no build step of its own.

## Goals

- `[~key]` and `[display]{~key}` render a glossed term as a link to its entry.
- `::: glossary` renders every declared entry, alphabetical by term, each with
  the pages where it is glossed.
- The glossary joins the existing apparatus family — footnotes and references —
  rather than inventing a parallel look.
- A book gets its own stylesheet without authoring a theme.
- `{.part}` and `{.unnumbered}` headings behave, so parts are parts and the
  preface stops consuming chapter one.
- A marker inside a heading does not corrupt the table of contents.

## Non-goals

- **HTML and EPUB output.** Deferred, deliberately, to their own designs.
- **Letter dividers** (`A`, `B`, `C` …) inside the glossary. The rendered
  section is 54 pages and would arguably benefit; it is not in this cut.
- **A general index-of-X primitive.** The mechanism here would generalise to
  several back-referenced term lists, but there is one consumer today and the
  contract for several is a design problem best deferred until a second case is
  real.
- **CSL.** Unchanged from `2026-08-11-citations-design.md`.
- **Nested glossing of definition prose.** A definition is prose from the data
  file; markers inside it are not resolved.

## The syntax

### Markers

Two forms:

```markdown
[~tesler-larry]                 the entry's own `term`, verbatim
[*AI effect*]{~ai-effect}       explicit display text, emphasis preserved
```

Both forms exist because the manuscript needs both. Across the 579 markers a
single strict pass resolves — the remaining 5 being the outer halves of nested
pairs, see below — the display text equals the entry's term in only 117 cases,
334 if case and emphasis are ignored. The other 42% are plurals, inflections and partial
phrases ("documented the failure mode") that no bare form can express. Equally,
226 markers carry emphasis, which the bare form cannot produce. So the display
form is the primary syntax and the bare form is sugar for the fifth of call
sites that want the term exactly as declared.

Neither form collides with Markdown: both are consumed by the pre-processor
before `parse()` runs, so `[~key]` never reaches the reference-link parser.

### Nesting

Markers nest. The manuscript has five, of this shape:

```markdown
[*Getty Images v. [Stability AI]{~stability-ai}*]{~getty-v-stability}
```

The rewrite matches the **innermost** span first and repeats to a fixpoint. This
requires excluding `[` as well as `]` from the display-text character class:
with `[^\]]*` the scan runs past the inner opening bracket and pairs the outer
display text with the inner key, silently producing the wrong link.

An anchor inside an anchor is invalid HTML — the parser closes the outer early
and strands a visible `</a>` in the running text, which is exactly what the
smoke test produced before this was handled. So on a nested pair the **inner**
term keeps the `<a>` and the **outer** gets an anchor-only `<span>`: the more
specific term stays clickable, and the outer entry still collects its page
reference.

### Data

`glossary:` accepts either a path, resolved against the project file, or an
inline mapping, so a single document needs no second file:

```yaml
# scriptorium.yaml
glossary: glossary.yaml
```

```yaml
# glossary.yaml
tesler-larry:
  term: "Tesler, Larry"
  definition: "Computer scientist who coined *direct manipulation* and ..."
```

Definitions are Markdown prose, on the same contract as bibliography entries:
the engine never parses them looking for structure.

### Placement

`::: glossary` marks where the section renders, exactly as `::: references` does,
with the same three errors: no placeholder means no section, two placeholders is
an error, an unclosed block is an error.

### Which entries appear

All of them, sorted case-insensitively by `term`. Mentioned entries carry a page
list; unmentioned ones simply have none — the manuscript has 17.

This diverges from citations, where only cited works are listed and `nocite:`
opts extras in, and the divergence is deliberate. A bibliography is an
attribution record: listing a work you did not cite misstates the record. A
glossary is a reader's apparatus: a term the body never glossed is still worth
defining, and the book's own preface promises "more than five hundred entries".

### An unknown key

A warning — `glossary key 'foo' has no entry` — and the marker renders as its
display text, or as the bare key for `[~key]`. The prose survives; the failure
is visible in the report, in the house manner.

## The engine

| Change | Where |
|---|---|
| `process_glossary(src, meta, base_dir) -> (src, warnings)` | new `scriptorium/glossary.py` |
| Call it after `process_citations` | `galley.render_pdf` |
| Pass `glossary` and `css` through; resolve paths against the project dir | `project.py` |
| `css:` — a path or list, appended after theme CSS | `galley.render_pdf` |
| Strip tags when building the heading label | `parse._heading_unit` |
| Skip `.unlisted` headings | `parse.fill_toc` |
| `glossary.html` component + apparatus CSS | `themes/base` |

### glossary.py is a sibling, not a new machine

`citations.py` already solves every hard part of this: locating a `:::`
placeholder while ignoring one inside a code fence, emitting back-links as empty
anchors for `target-counter` to fill, and collecting warnings. `glossary.py` is
the same module with a different sort order and no numbering, and should be
written to read as an obvious sibling of it — roughly 150 lines.

It runs **after** footnotes and citations, for the reason citations run after
footnotes: a term glossed inside a footnote body has by then been moved to where
the note actually renders, so its page reference points at the page the reader
will see it on, not at the page where the definition happened to sit in source.

### Why one pass is enough

Two mentions of a term on the same page produce a duplicated page number —
`↩ 45, 45` — because `target-counter` resolves at layout and nothing before
layout knows what page a mention landed on. Removing the duplicate would need a
second full render.

It is not worth it. Measured on the real book: of ~490 page lists scraped from
the rendered glossary, **2 contain a duplicate**. A second 36-second render to
fix four characters in a 329-page book
is the wrong trade, and the alternative — capping back-references per entry —
loses real information to fix a rarer problem than it creates.

### The css: key

A path or list of paths, resolved against the project file (or the document, for
a single-file render), read and appended to `theme.css` after the theme's own
rules so it wins on equal specificity.

This closes a real gap: `load_theme` resolves only from `<scriptorium>/themes/`,
so today a book with any custom styling must either author a theme inside the
scriptorium repo or smuggle a `<style>` block in as content — which the smoke
test did, and which costs a stray blank page. `css:` lets a book keep a
`book.css` next to its `scriptorium.yaml` and leaves the themes generic.

### The heading-label bug

`fill_toc` escapes `Unit.heading`, which holds the **raw source** text of the
heading. Once a marker inside a heading has been rewritten, that raw text
contains an anchor, and the table of contents prints it:

```
Contents
The rise of <a class="gloss-ref" href="#x">machine learning</a>
```

Verified against the engine on 2026-08-12, and re-verified against v0.7.0. The
manuscript has 8 markers on heading lines, so this would have shipped in a real
book's table of contents.

The fix belongs in `_heading_unit`, where the label is built, not in `fill_toc`
— every consumer of `Unit.heading` wants text, and stripping tags at the source
fixes them all at once. This is a pre-existing bug for any inline HTML in a
heading; the glossary is only what exposes it.

Note that no *new* collision is introduced by `{~key}` looking like a heading
attribute block. `_HEAD_ATTR` strips a trailing `{...}` from a heading line, but
the glossary pre-processor has already consumed the marker by then, so a heading
may legitimately end in a marker. This ordering is an invariant worth a test.

## The apparatus contract

Footnotes and references already share a deliberate contract, and the glossary
joins it rather than starting a second one:

- A `<section class="…">` component in `themes/base/components/`.
- A `<name>-label:` var, empty by default *because the label's language is the
  document's business*. When set, the component emits
  `<h2 class="apparatus-title">` and adds `.labelled`, which drops the top rule
  so a heading and a rule do not read as a doubled divider. Precisely: this
  arrived with `references-label` in v0.7.0 and only `references` has one today,
  so the glossary is the second member, not the third.
- That same commit widened the template engine's `_HOLE` and `_SECTION` patterns
  to accept hyphens, because theme vars are kebab-case and until then no var
  could reach a template at all. `{{#glossary-label}}` depends on it; against
  v0.6.0 this design would not have worked.
- A `keep_together: false` hint — these sections outrun a page, and a 54-page
  glossary emphatically does.
- A hairline `--rule` above, `margin-top: 6mm; padding-top: 3mm`, 9pt / 1.45,
  links in `--accent-dark` with no underline.
- Back-links as **one `↩` followed by page numbers** in tabular figures, filled
  by `target-counter`.

So: `glossary.html` mirrors `references.html` including the `labelled`
conditional; `glossary-label: ""` carries the same rationale; `.gloss-back::after`
reuses the identical declaration as `.cite-back::after`. Naming follows citations
— `.gloss-ref` / `.gloss-back`, `#gloss-<key>` / `#glossref-<key>-<n>`, against
`.cite-ref` / `.cite-back` / `#cite-N` / `#citeref-N-K`.

**One consolidation.** `.footnotes` and `.references` duplicate the rule, margin
and type-scale block. A third member is the moment to collapse it into
`.footnotes, .references, .glossary { … }`. Scoped to the declarations the three
actually share — not a sweep of the stylesheet.

**One divergence.** Footnotes and references are numbered `<ol>`s because their
in-text marker is a number. The glossary's marker *is* the word and lookup is
alphabetical, so it is a term-keyed list, not an ordered one. "Coherent" here
does not mean "also an `<ol>`".

**One exception.** The in-text marker keeps a dotted underline in addition to
the accent colour, where `.cite-ref` has colour alone. `[1]` is distinguishable
by its shape; a glossed term is ordinary words in ordinary prose and needs the
extra affordance, 584 times over.

## The book theme

The engine already carries `{#id .class}` from a heading onto the `<h1>`, so
what remains is CSS:

- `# Foundations {.part}` increments a part counter and takes divider treatment,
  and does **not** increment the chapter counter. Today a part index file
  renders as an ordinary numbered chapter — "Foundations" came out as chapter 4.
- `{.unnumbered}` suppresses both the numeral and the counter, so the preface,
  manifesto and prologue stop consuming chapters 1–3 and *Classical AI* is
  chapter 1 rather than 5.
- A `cover` master and `cover-image` var for the full-bleed cover, which Quarto
  was drawing with a TikZ overlay.
- `.glossary` drops its top rule in `book` only. There the glossary is a chapter
  — `# Glossary {.unnumbered}` followed by `::: glossary` — so the rule would
  double against the chapter title. In `article` and `note`, where the section
  trails the text, the rule stays. Footnotes and references do not have this
  problem: in `book` they are chapter-scoped and sit mid-chapter.

## Testing

Unit tests mirroring `tests/test_citations.py`: both marker forms; a nested pair
resolving inner-link/outer-anchor with balanced tags; an unknown key warning with
the display text preserved; sort order; the three placeholder errors; an entry
with no mentions rendering without a page list; a marker at the end of a heading
line surviving heading-attribute parsing; a glossed heading producing a clean
TOC label.

The integration test asserts on the rendered PDF's **`/Annots` destinations** in
both directions — body → `gloss-<key>`, glossary → `glossref-<key>-<n>`. Not on
a source grep and not on extracted text: a grep passes on styled-but-unlinked
text, and the entire feature is that the link resolves. Only the annotation
proves it. The check gets mutation-tested by breaking `target-counter` and
confirming it goes red, per `AGENTS.md`.

Acceptance is the manuscript itself: it renders without warnings, chapter
numbering starts at 1, parts are dividers, and 498 of the 515 entries carry page
lists.

## After this lands

The `books-mhai` migration is a separate, one-time job, not part of this design
and not a build step: `_filters/glossary_data.lua` becomes `glossary.yaml`, 584
markers are rewritten, `{.part}` and `{.unnumbered}` go on 10 headings, and a
`scriptorium.yaml` plus `book.css` are written. A script run once and thrown
away — the whole point of this design is that the manuscript afterwards needs
nothing but `scriptorium render`.

## Measurements behind this design

All from the 2026-08-12 smoke test on the real manuscript, kept because several
of them decided a design point rather than merely illustrating one.

| Measurement | Value | What it decided |
|---|---|---|
| Full render | 273 pp / 36 s / 338 MB | Migration is viable at all |
| Quarto's PDF | 343 pp (letter) | Comparable output |
| Markers / unique keys / entries | 584 / 506 / 515 | Scale of the feature |
| Display text equals term | 117 of 579 | Both marker forms are needed |
| Markers carrying emphasis | 226 | The bare form cannot be the only one |
| Nested markers | 5 | Fixpoint rewrite, inner keeps the link |
| Markers on heading lines | 8 | The TOC label bug is real, not theoretical |
| Entries never mentioned | 17 of 515 | Unmentioned entries still render |
| Page lists with a duplicate | 2 of ~490 sampled | One render pass, no dedupe |
