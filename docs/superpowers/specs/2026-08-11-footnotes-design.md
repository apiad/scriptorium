# Footnotes as endnotes — design

*Status: approved, not yet implemented. 2026-08-11.*

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

Non-goals: CSL / BibTeX bibliographies, author-date citation styles, footnotes
inside deck slides beyond what falls out of `document` mode.

## Syntax

Standard Markdown, no new vocabulary:

```markdown
The claim.[^a]

[^a]: The supporting note, with a [link](https://example.com).
```

A note referenced more than once gets one back-link per occurrence — the
double-sided behaviour `citations.py` hand-rolled, provided natively by the
plugin.

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

### Parsing

Enable `mdit_py_plugins.footnote.footnote_plugin` in the `MarkdownIt` chain in
`parse.py`. It emits in-text markers as
`<sup class="footnote-ref"><a href="#fn1" id="fnref1">[1]</a></sup>` and a
single trailing `<section class="footnotes"><ol class="footnotes-list">…</ol></section>`
with a `↩︎` back-ref per occurrence.

### Relocation

A new module `scriptorium/footnotes.py`, occupying the pipeline slot
`citations.py` currently holds in `galley.render_pdf`.

The plugin always emits one section at end-of-document. For `chapter` mode the
engine splits it: walk the rendered units in order, note which `fnrefN` ids
appear between one `#` and the next, cut the matching `<li>` items out of the
trailing section, renumber them from 1 within the chapter, and insert a
`<section class="footnotes">` immediately before the next `#` unit (and at the
end for the final chapter). Marker text and `id`/`href` pairs are rewritten
together so links stay resolvable — ids are namespaced per chapter (`fn2-1`,
`fnref2-1`) to keep them unique across the document.

`document` mode leaves the plugin's output where it is. Both modes preserve the
single continuous HTML flow that v0.3.0's CSS Fragmentation pagination depends
on — no change to how pages are broken.

The alternative considered was segmenting the source by chapter and parsing each
segment independently, which would make per-chapter numbering free. Rejected: it
fragments the one-flow model and forces cross-references, counters and the TOC
to be re-stitched across segments.

### Per-page footnotes

WeasyPrint implements CSS GCPM footnotes: an element with `float: footnote` is
pulled to the foot of the page its anchor lands on and auto-numbered. Verified
2026-08-11 on a three-page render — note 1 at the foot of page 1, note 2 at the
foot of page 3.

**But GCPM wants the note's content inline at the anchor**, and the plugin puts
only a marker there, with the content in a trailing section. Applying
`float: footnote` to the plugin's `.footnote-ref` floats the *marker* — the
footnote area ends up containing the text `[1]` while the note itself stays in
the body flow. Verified 2026-08-11 against the plugin's exact HTML.

So `page` mode is engine work, not a stylesheet: `footnotes.py` moves each
`<li>`'s content back inline, wrapped in a `<span class="footnote-inline">`, and
drops the plugin's `<sup>` marker so WeasyPrint's generated call is the only one.
It reuses the same note→reference map the `chapter` splitter builds, so the
incremental cost over the other two modes is small — but it is not free, and the
earlier "CSS only" assessment of it was wrong.

**Limitation, documented rather than solved:** a note referenced more than once
has one body and several call sites. In `page` mode it is inlined at its *first*
reference; later markers render as a plain superscript linking to that page's
note rather than duplicating the text. `document` and `chapter` modes keep the
full multi-back-link behaviour.

Worth recording either way: `docs/design.md` §7.4 rejects per-page footnotes as
circular — "footnote height changes `content_h`". That was true of the Python
bin-packer it was written against. v0.3.0 handed document pagination to
WeasyPrint, so the circularity is now WeasyPrint's to resolve, and it does. §7.4
is corrected as part of this work.

### Styling

`.footnote-ref` and `.footnotes` styles land in `themes/base/styles.css`,
inheriting the superscript look v0.3.0 established for citations: small, raised,
accent-coloured, no underline. The plugin renders markers as `[1]`; the brackets
are suppressed in CSS so the output matches the existing superscript form.

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

The plugin's own parsing is upstream's concern. The tests cover this repo's
logic:

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
- Render-level: a book-theme document with notes in two chapters produces two
  `<section class="footnotes">` blocks in the emitted HTML.

Each test must be able to fail: after the suite is green, the chapter-splitting
assertion is mutation-checked by forcing `document` mode and confirming the
chapter test goes red — with a `cmp` that the mutation actually applied.
