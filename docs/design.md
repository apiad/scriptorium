# Scriptorium — Design

**Status:** design (pre-implementation) · **Date:** 2026-07-28 · **Author:** Alex + Claude

A Markdown-native document engine that replaces Quarto for everything except
scientific papers (where LaTeX still wins). One source document fans out to a
lean **HTML book**, an **exact-geometry paginated PDF**, and an **EPUB**; it
**tangles** code to real source files (subsuming [illiterate](https://github.com/apiad/illiterate));
and it **executes** code blocks in place. Its distinguishing capability is a
pagination engine — `galley` — that measures rendered content and packs it into
physical pages with deterministic geometry, so "print to PDF" yields real pages
laid out under rules the author controls, not whatever the flow happened to do.

The reference bar for output quality is a hand-crafted, design-system report —
~100 hand-placed A4 pages with covers, section openers, KPI tiles, finding
cards, and the rest of a rich component vocabulary. The goal: author that with
pure Markdown + a little HTML, and let the engine place the pages.

---

## 0. Table of contents

1. Vision and scope
2. Architecture: one model, three renderers, an execution stage
3. Authoring language (the component grammar)
4. Themes and the component contract
5. Execution runtime
6. Tangle (illiterate subsumed)
7. The `galley` pagination engine
8. Page masters and PDF furniture
9. Cross-references and numbering
10. Math pipeline
11. Project / book model
12. Renderers: HTML, PDF, EPUB
13. Citations and bibliography
14. CLI and build workflow
15. Extensibility
16. Technology stack and repo layout
17. Phased delivery (vertical slices)
18. Open questions / defaults to confirm

---

## 1. Vision and scope

Scriptorium is the successor to a split toolchain we want to unify:

- **Markdown → Quarto/Typst** — a *plain* PDF. Easy to author, ordinary-looking.
- **Hand-woven HTML → WeasyPrint** — a gorgeous design system, but every page
  hand-placed and hand-balanced to fit 297 mm.
- **A Rust tangle tool** (`illiterate`-style) — `export=`, noweb fragments, `--test`.
- **Quarto `type: book`** — HTML website first, then PDF, then EPUB, with
  executable code and cross-references.

Scriptorium fuses these into one tool. **In scope:** design-system reports,
paginated PDF with exact geometry, HTML books (lean), EPUB, executable code,
tangle, cross-references, math, citations-as-endnotes. **Out of scope:**
scientific papers destined for LaTeX/journal submission — those stay in LaTeX.

**Non-negotiables** (our conventions):

- Markdown is canonical; every output is regenerable from it.
- Citations render as **numbered endnotes with clickable anchors** by default
  (never per-page footnotes — Typst mis-places them).
- English is the artifact default; per-document `lang:` localizes generated
  labels ("Figure" → "Figura", "Algorithm" → "Algoritmo").

---

## 2. Architecture: one model, three renderers, an execution stage

```
Markdown + ::: components + math + fenced blocks (run / export= / name=)
        │
   [parse]  ──────────────►  one AST  (markdown-it-py + plugins)
        │
   [assemble]  noweb <<frag>> expansion   (feeds tangle AND execute)
        ├──► [tangle]   export= → real source files            (illiterate's job)
        └──► [execute]  run → subshell → stdout spliced raw → re-parsed
                 │  (enriched AST: outputs inline, so heights are knowable)
                 ├──► [HTML book]   lean: content + nav + theme + vendored search
                 ├──► [galley PDF]  measure → pack → emit, exact geometry
                 └──► [EPUB]        reflowable
```

**Ordering matters:** execution enriches the AST *before* any renderer runs,
because an executed figure's height is unknown until it runs, and `galley`'s
measure pass needs final heights. There is no lazy execution during layout.

`scriptorium` is the system; `galley` is its pagination pass; tangle is absorbed
illiterate; execute is the subshell-splice model.

---

## 3. Authoring language (the component grammar)

### 3.1 Base layer — everything Markdown has today

CommonMark + GFM + scholarly extensions, assembled from `markdown-it-py`
plugins (we assemble a parser, we do not write one):

- Headings, emphasis/strong, blockquotes, HR, links, images
- Lists: ordered, unordered, task lists (`- [ ]`)
- Tables (GFM), footnotes, definition lists, strikethrough, autolinks
- Fenced + inline code
- Math: inline `$…$`, display `$$…$$`
- Attributes on any element (Pandoc-style): `# Title {#intro .no-toc}`,
  `![](f.png){width=8cm}`, ` ```python {run export=x.py} `

### 3.2 Escape hatch — raw HTML

Raw HTML passes through verbatim (CommonMark already permits it). Added rule for
**galley**: a raw-HTML block is one **opaque atomic unit** — measured as-is,
**kept together** by default (we don't understand its internals), unless it
carries `{splittable}`. This is the graceful-degradation valve when the
component grammar isn't enough.

### 3.3 Inline components — spans

`[text]{.class}` → `<span class="class">text</span>`. If the theme registers the
name as an inline component (`badge`), it gets the component template; otherwise
it's a plain styled span. Example:

```
risk is [elevated]{.rose} this quarter, see [§3]{.ref}, tagged [NEW]{.badge .amber}
```

### 3.4 Block components — the `:::` grammar

One unified header:

```
::: <name> <modifier…> {#id key=val key="quoted val"}
markdown body  ← the content slot
:::
```

- **`<name>`** — a component the theme must define. Bare `:::` with only
  `{.class}` and no name = a plain classed div.
- **`<modifier…>`** — bare words = variant classes (`amber`, `three`).
- **`{…}`** — explicit scalar props / attributes (plain text).
- **body** — full Markdown → the `{{content}}` slot.
- **nesting** — deeper fences with more colons (`::::` wraps `:::`).

**Three power levels** (each drawn from the report theme's vocabulary):

**Level 0 — pure CSS group** (theme ships only CSS):
```
::: {.two-col}
long prose that flows into two columns…
:::
```

**Level 1 — scalar props + one content slot** (the 90 % case):
```
::: finding-card amber {icon=A title="Regulatory risk"}
The import framework does not yet cover the relevant hardware.
:::
```
Template:
```html
<div class="finding-card {{variant}}">
  <div class="x">{{icon}}</div>
  <div><span class="name">{{title}}</span>
       <span class="reason">{{content}}</span></div>
</div>
```

**Level 2 — containers + named slots** (rare: multi-region components like
`cover`, `section-opener`):
```
::: cover
::: slot wordmarks
![](assets/logo.png){.di}
:::
::: slot tag
Market Brief — June 2026
:::
:::
```
`::: slot <name>` fills a named slot; everything outside a slot is `{{content}}`.

**Decisions locked:** props are scalar plain-text + one Markdown content slot,
with `::: slot` as the escape for multi-region components (not every prop holds
Markdown); modifiers map straight to CSS classes (no whitelist ceremony).

### 3.5 Built-in layout primitives (engine-level, always available)

Independent of any theme, because they are layout mechanics, not design:

- `::: newpage` (or `\newpage`) — hard page break
- `::: keep` — keep-together wrapper for ad-hoc (non-component) blocks
- `::: columns {n=2}` — column flow
- `::: float {to=top}` — float a figure (hook designed now; full float logic
  deferred past v1, see §7)

Everything else is theme-supplied.

---

## 4. Themes and the component contract

A theme is a directory scriptorium loads:

```
themes/report/
  theme.yml            # metadata, extends: base, fonts, page geometry
  styles.css           # design tokens + component CSS (lifted from the reports)
  components/
    finding-card.html  # template: {{prop}} / {{content}} / {{slot:name}} holes
    kpi-tile.html
    cover.html         # a page-master component
  page-masters/        # cover, section-opener, running header/footer
```

Each component declares **layout hints the galley engine consumes**, as a
sidecar or front-matter on the template:

```yaml
# kpi-dash
variants: [two, three, four]
keep_together: true      # never split across a page
break_before: false
splittable: false
```

`keep_together: true` on `finding-card` / `kpi-dash` is exactly what makes
galley move the whole tile to the next page instead of orphaning it — the author
never thinks about it. This is the join between the component system and the
pagination engine.

**Template language: dumb mustache over HTML** (`{{prop}}`, `{{content}}`,
`{{slot:name}}`) — deliberately not a real templating engine. The existing
design system *is already HTML*; a theme author lifts their hand-written
component HTML almost verbatim and pokes a few holes. Lowest friction, matches
the artifacts we already have.

Themes **extend** a base (default: the `base` theme's tokens) so reports and books
share a coherent visual language. A book theme ships `callout` / `aside` /
`theorem` / `exercise`; the report theme ships `finding-card` /
`kpi-tile` / `timeline` / `compare-table`. Same engine, different vocabulary —
"custom tags shipped with themes."

### 4.1 The theme is a project template

A theme is not just styling — it carries everything that makes a document a
*book* vs a *report* vs an *article*: masters, components, CSS numbering
(counters), cross-reference formats (`target-counter`/`target-text`), page
furniture, and a documented **`vars`** block (identity vars the masters
interpolate + appearance vars bound to CSS custom properties). The project
supplies files + var overrides; the theme supplies the shape. Swap the theme,
same content becomes a different kind of document. See §11.

---

## 5. Execution runtime

### 5.1 The model

A runnable block is executed in a **subshell**; its **stdout is captured,
spliced back into the document as raw source text, then re-parsed as Markdown.**
That is the whole contract. Zero magic — no `__repr__`, no figure protocol, no
kernels, no dependencies. A block emits its own renderable text: a figure → the
block writes `fig.png` and prints `![](fig.png)`; a table → prints a Markdown
table; a component → prints `::: finding-card …`. Any language works, because
stdout is just text.

### 5.2 State flows through source assembly, not a live process

A fresh subshell per block shares no state. State flows via the **noweb model**
(the same `<<...>>` assembly illiterate uses for tangle), extended to execution:
a runnable block includes the fragments it needs and runs the assembled whole.

```
```python {name=setup}
class FenwickTree: ...
```

```python {run <<setup>>}     ← assembles setup + this body, runs as one program
t = FenwickTree(8); print(t.prefix(5))
```
```

`<<...>>` assembly feeds **all three** consumers uniformly — shown source,
`export=` tangle file, executed program. No hidden kernel, fully reproducible,
deterministic. The cost (re-running assembled setup repeats imports/compute) is
absorbed by the freeze cache.

**Locked:** assembly-only state model. No cumulative "session" mode — sessions
reintroduce hidden order-dependence.

### 5.3 Mechanics

- **Interpreter map:** language tag → command (`python`→`python -`,
  `bash`→`bash`, `node`→`node -`), plus `{.exec cmd="…"}` raw escape. Body → stdin.
- **Freeze cache:** content-hash of *(assembled source + interpreter)* →
  captured stdout, stored in **beaver**. Unchanged blocks never re-run (Quarto
  `freeze: auto` semantics, no kernel).
- **Working directory:** the document's directory (natural relative asset
  read/write); configurable per project.
- **Errors:** nonzero exit / stderr → build fails loud by default;
  `{run allow-error}` captures stderr into the doc instead (teaching "here's the
  exception").
- **Timeout:** per block, default 30 s, overridable.
- **Display control:** `echo=false` hides source and keeps output; `output=false`
  runs but suppresses the splice (side-effect-only, e.g. a block that only writes
  a figure file referenced elsewhere).

---

## 6. Tangle (illiterate subsumed)

Scriptorium reimplements illiterate's tangle stage in Python (tangle is string
assembly; we lose the Rust single-binary but gain one fence parser for the whole
system). Features carried over verbatim:

- `{export=path}` — concatenate block body into a real file, in document order.
- `{export}` — headless magic: filename from the Markdown file name + language.
- `{name=frag}` + `<<frag>>` — noweb fragments (define out of order, assemble
  correctly). Same assembly used by execution (§5.2).
- `scriptorium tangle --test` — CI idempotency check; nonzero exit if regenerated
  files would differ.

`illiterate` the repo becomes the archived predecessor; its README points here.

---

## 7. The `galley` pagination engine

The core IP. Three passes, one shared rendering path so measurement never drifts
from output.

### 7.1 Measure

Render the **post-execution** content stream into a single WeasyPrint page of
`size: 210mm auto` (unbounded height) at the true body width, each block already
wrapped in its final component HTML. Walk `document.pages[0]._page_box` and read
every **atomic unit's** `position_y` + border-box height (px → mm at 96 dpi).

Atomic units = paragraph, heading, list, table, figure, themed component. Per
unit we also carry: `keep_together`, `break_before`, `keep_with_next` (headings),
`splittable` + child-boundary offsets (list items / table rows / line boxes),
float directives.

**Measure pass = emit pass minus the page-boxing** — literally one code path, so
heights are exact.

### 7.2 Pack (greedy + one-unit lookahead)

`content_h = page_h − margins − header/footer reserve`. Walk units, track fill `y`:

- `break_before` / `::: newpage` → flush page, start new.
- Fits (`y + h ≤ content_h`) → place, `y += h`.
- Doesn't fit:
  - **heading (keep-with-next):** if heading + next unit won't co-fit in the
    remaining space, break *before* the heading — no heading orphaned at a page
    foot.
  - **keep_together, ≤ one page:** flush, place whole on a fresh page.
  - **keep_together, > one page:** *oversized* → emit a diagnostic and
    **overflow** (do not silently scale or clip). Theme may opt into split.
  - **splittable:** break at the last child boundary (row / list item / line box)
    that fits; carry the remainder. Enforce **widow/orphan minimums** (≥ 2 lines
    each side); tables **repeat the header row** on continuation.
- **Floats** (`::: float {to=top}`): pulled from linear flow, assigned to the
  top/bottom band of the page their anchor lands on; body fills the remainder.
  Hook designed now; full float logic lands post-v1.

**Locked:** oversized keep-together → warn + overflow (never silent scale);
floats deferred past v1.

### 7.3 Emit

Wrap each computed page's units in `<div class="page" data-master="…">`, apply
its page master, final render with `@page { size: A4; margin: 0 }` and each
`.page` a fixed 297 mm box — i.e. we generate exactly the hand-woven structure
the reports use today. Geometry matches the plan to a sub-pixel epsilon (reserve
~1 mm slack).

### 7.4 Footnotes — endnotes by default

True bottom-of-page footnotes are circular (footnote height changes `content_h`,
which changes which page the reference lands on). The house report standard
favors **endnotes** (a references section at the end) over per-page
footnotes. So scriptorium adopts **endnotes** (per-chapter or per-document) as
the default, sidestepping the circularity and matching convention. True per-page
footnotes are an opt-in later feature with iterative re-layout.

---

## 8. Page masters and PDF furniture

Because we emit our own `.page` divs under `@page { margin: 0 }`, we draw
furniture *inside* each page div (as the hand-crafted reports do), not via
WeasyPrint margin-boxes. A **page master** is a named (geometry + furniture) set
the theme ships:

| Master | Furniture | Use |
|---|---|---|
| `cover` | none, full-bleed, `no-padding` | title page |
| `section-opener` | none | full-page chapter/section opener |
| `body` | running header + footer + page number | default content |
| `blank` | number only | spacers |

- **Furniture = theme partials** rendered per page with resolved tokens:
  `{{page_number}}`, `{{page_total}}`, `{{chapter_title}}`, `{{section_title}}`.
  **Running heads resolve in the emit pass** — the pack pass already knows which
  section each page falls in, so "current chapter" per page is free.
- **Master selection:** structure + theme rules (`level-1 heading →
  section-opener then body`), overridable per element (`# Title {.master=body}`);
  front matter picks the cover master.
- **Geometry:** theme declares page size and margins; `@page { size: A4;
  margin: 0 }` + `.page` padding produce margins; full-bleed elements escape
  padding via the `no-padding` master.

**Locked:** bleed / crop-marks for real print deferred; screen-PDF first.

---

## 9. Numbering and cross-references — pure CSS

**The engine owns no numbering.** Chapter/section numbers, cross-reference text,
and TOC page numbers are all generated by the *theme's stylesheet* and resolved
by WeasyPrint at render time. This was verified to work through galley's own
`.page`-div structure (`@page{margin:0}` + explicit page boxes).

- **Numbering: CSS counters.** `h1{counter-increment:chapter} h1::before{content:"Chapter " counter(chapter)}`.
  Counters increment in document order, so they compose with measure-pack for
  free. `number_depth` and localized labels ("Figure"/"Figura") are just which
  levels the theme's CSS numbers and what text it emits.
- **References: `target-counter` / `target-text`.** The engine turns `@type-id`
  into an *empty* anchor `<a class="ref-type" href="#type-id"></a>` and assigns
  the target's id; the theme's CSS fills it:
  `a.ref-chap::after { content: "Chapter " target-counter(attr(href url), chapter) " (p. " target-counter(attr(href url), page) ")" }`.
  Number *and* page are WeasyPrint-resolved. Format/prefix per type is the
  theme's choice; hierarchical "3.2" is two `target-counter`s.
- **TOC page numbers:** a TOC entry is a link; theme CSS adds
  `content: leader('.') target-counter(attr(href url), page)`. The engine only
  emits the heading link-list; the dotted page numbers are CSS.

So the engine's whole job here is: **assign ids to headings/figures, and rewrite
`@type-id` into type-classed anchors.** No numbering pass, no ref-resolution
pass. Verified: `@chap-trees` → "Chapter 2 (p. 3)" with zero engine numbering.

The one book-craft item that *isn't* pure CSS in our architecture is **running
heads** (we use `@page{margin:0}` and draw furniture inside `.page` divs, so
`string-set`/`@page @top` don't apply): the theme supplies a template string +
CSS class, and galley fills it per page at emit — the same mechanism as the
stamp footer.

---

## 10. Math pipeline

- Parse `$…$` / `$$…$$` (markdown-it `dollarmath` plugin).
- **Renderer: quickjax** — real MathJax v4 running inside an embedded QuickJS
  engine, **in-process, pure Python, no Node and no LaTeX install**. Each call
  returns a self-contained SVG (own glyph paths + a computed `vertical-align`,
  so inline math baselines and scales with font-size). Used for both PDF (SVG
  embedded directly) and HTML.
- **No Node dependency.** The earlier plan (Node + KaTeX) is dropped: quickjax
  gives MathJax-grade fidelity with zero external runtime, which keeps the whole
  toolchain Python-only and reproducible. WeasyPrint has no native MathML, so
  SVG is the path regardless. (ziamath, a pure-Python STIX-font renderer, was
  evaluated and rejected — it needs a baseline heuristic and collides on shared
  SVG glyph IDs under WeasyPrint.)
- **Cache:** rendered SVGs are memoized in-process and persisted in the freeze
  store (keyed `math\0<display>\0<latex>`), so a math-dense book renders each
  equation once, then serves it from cache on rebuild.
- **Equation numbering:** display equations get `@eq` counters and a number
  gutter (later slice).

---

## 11. Project model — concat + vars (the theme is the template)

There is **no `kind: book|report|article`** and no structural role schema. A
project is just a **theme + variables + a list of files**; the theme (its CSS,
masters, and components) *is* the template that makes the same content render as
a book, a report, or an article. Structure lives in theme CSS (counters,
`break-before`, `h1`-as-chapter-opener), not in the engine.

```yaml
# scriptorium.yaml
theme: book
vars:
  title: A Field Guide to Algorithms
  author: Alejandro Piad-Morffis
  brand: "#7c3aed"
code: { root: src }          # tangle target + PYTHONPATH for execution
files:
  - front/index.md
  - 01_search.md
  - 02_binary.md
  - appendix-python.md
```

- **Assembly** = concatenate the listed files (each file starts a fresh page),
  strip per-file frontmatter, and substitute `{{var}}` over the result. A single
  file with no project still renders against the theme's default flow — today's
  behavior, unchanged.
- **Vars are theme-specific and flow two ways:** into masters via `{{var}}`
  (title page, running heads) and into CSS as custom properties (`:root{--brand:…}`)
  so a project rethemes without editing CSS. The theme declares its vars +
  defaults in `theme.yml`; the project overrides. Nothing is engine-hardcoded.
- **Engine additions over single-doc:** file concat + `{{var}}` substitution,
  heading-id assignment + `@ref` rewriting, TOC link-list emission, running-head
  emit-fill. That's it.

A `book`, `report`, and `article` differ only in *which theme* they point at.
Verified with `examples/book/` (2-chapter project → 3-page PDF, CSS numbering,
`@chap-trees` → "Chapter 2 (p. 3)").

---

## 12. Renderers: HTML, PDF, EPUB

### 12.1 HTML book (lean — the fork-1 call)

Multipage (one HTML per chapter) or single-page, theme-selectable. Sidebar nav
from structure, TOC, prev/next, anchors, dark/light toggle, and vendored
client-side **search** (a prebuilt index + a small lib like MiniSearch —
*not* a clone of Quarto's website infra). Math via server-side KaTeX. Components
render through the same theme templates (HTML target). Responsive; assets copied
to the output tree. Deliberately lean: if it can carry books.apiad.net, great;
if not, Quarto stays for HTML-only while scriptorium still wins on PDF.

### 12.2 PDF

`galley` (§7) + page masters (§8). The differentiated output.

### 12.3 EPUB

Reflowable: chapters → XHTML, `package.opf`, `nav.xhtml`, embedded fonts, cover.
Components render to an EPUB-safe HTML+CSS subset (no `@page` geometry). Math as
MathML with SVG fallback. Lowest priority; built last.

---

## 13. Citations and bibliography

- Syntax: `[@key]` / `@key`, with a `.bib` or CSL-JSON source.
- **Default mode:** citations resolve to **numbered endnotes with clickable
  anchors**, matching a common report convention (a `# References` section, anchors
  `{#ref-N}`, superscript links). This automates what is currently done by hand.
- **Academic mode:** CSL author-date + a formatted bibliography, for books that
  want it.

---

## 14. CLI and build workflow

- `scriptorium render [target]` — all outputs or one (`pdf` / `html` / `epub`).
- `scriptorium watch` — rebuild on change (replaces the `entr`-based makefile).
- `scriptorium tangle [--test]` — illiterate mode: write `export=` files; `--test`
  is the CI idempotency check.
- `scriptorium new <kind>` — scaffold a document / report / book.
- **Incremental:** freeze cache for execution + math SVG + measured heights,
  keyed by content hash in beaver → fast rebuilds. `--no-cache` to force.

---

## 15. Extensibility

Themes are the primary extension surface. Beyond them, a minimal **filter** seam:
Python functions that run over the AST (a Pandoc-Lua-filter analog, in Python).
Kept small for v1; the seam is documented so custom directives/transforms have a
home without forking the engine.

---

## 16. Technology stack and repo layout

- **Python 3.12+**, `markdown-it-py` (parse), **WeasyPrint** (measure + PDF),
  **Node + KaTeX** (math → SVG, build-time only), **beaver** (freeze/measure
  cache), a tiny mustache renderer for component templates, `typer`/`click` (CLI).

```
scriptorium/
  scriptorium/
    parse/            # markdown-it-py assembly, ::: directives, attrs
    model/            # the document AST
    assemble.py       # noweb <<frag>> expansion
    exec/             # subshell execution + freeze cache
    tangle/           # export= / name= / --test  (illiterate subsumed)
    galley/           # measure → pack → emit  (the pagination engine)
    math/             # KaTeX → SVG / HTML
    xref/             # numbering + reference resolution
    themes/           # theme loading, mustache, layout hints
    render/
      html.py
      pdf.py
      epub.py
    cli.py
  themes/
    base/             # foundation: var contract + vendored fonts + base styling
    note/             # utilitarian notes/handouts
    article/          # polished single document (serif body, sans display)
    report/           # data-forward report (cover, KPI tiles, finding cards…)
    book/             # classic long-form book (serif, chapter numerals, TOC)
  docs/
    design.md         # this document
  tests/
```

---

## 17. Phased delivery (vertical slices)

Each slice is a thin end-to-end path with a concrete acceptance artifact.

- **VS1 — the engine loop.** ✅ measure → pack → emit → exact-geometry A4 PDF;
  `::: keep` / `::: newpage`. Verified 2-page PDF.
- **VS2 — the design system.** ✅ directory-backed theme system + `marketing`
  report theme (cover, KPI tiles, finding cards, timelines), page masters, drift guard.
  Verified 11-page report from Markdown.
- **VS3 — execute + tangle.** ✅ subshell execute (Quarto-monospace vs native
  raw-splice) + freeze cache + tangle (`export=`, illiterate-compatible,
  reproduces `fenwick.py` byte-exact) + Pygments + **export provenance labels**
  (file + exact line range).
- **VS4 — math.** ✅ quickjax (MathJax-in-QuickJS, **no Node**), inline + display,
  freeze-cached. Real `22_fenwick.qmd` renders to an 11-page PDF.
- **Pagination polish.** ✅ keep-with-next headings; code line-splitting (code is
  narrative, not a float).
- **Project model.** ✅ `scriptorium.yaml` = theme + vars + files; `book` theme
  with CSS-native numbering + `target-counter` cross-refs. Verified 2-chapter
  book, `@chap-trees` → "Chapter 2 (p. 3)".
- **Next — running heads + auto-TOC** (emit-fill + `::: toc` link-list), then the
  a full multi-chapter book build (PYTHONPATH wiring for cross-chapter imports).
- **Later — VS5 HTML book** (lean renderer + search); **VS6** EPUB, CSL citations,
  opt-in `::: float` for figures, per-page footnotes.

---

## 18. Open questions / defaults to confirm

Locked in conversation: component grammar (§3), theme contract (§4), execution
model + assembly-only state (§5), tangle scope (§6), galley passes + oversized
warn-overflow + deferred floats (§7), page masters + deferred bleed (§8).

Defaults set here in the lighter layers, open to veto on review:

1. **Cross-ref prefixes** (`sec`/`fig`/`tbl`/`lst`/`eq`) and chapter-scoped
   numbering (§9) — Quarto-compatible; confirm the prefix set.
2. ~~Node+KaTeX for math~~ — **resolved: quickjax** (MathJax in QuickJS,
   pure-Python, no Node). Toolchain stays Python-only. See §10.
3. **`scriptorium.yml`** as the project file with `document`/`report`/`book`
   kinds (§11) — confirm the name and the `structure:` shape.
4. **Lean HTML search** via a vendored JS index lib (§12.1) — confirm we're not
   chasing Quarto's full website search.
5. **Citations default to numbered endnotes**, CSL as opt-in (§13) — confirm.
6. **EPUB is genuinely last** (§17 VS6) — confirm it's not needed earlier for any
   book.
