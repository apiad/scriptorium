# Tasks

Actionable items for scriptorium. One line each; link the spec when there is one.

## Open

- [ ] **Proper CSL citations.** Bibliography entries are prose, optionally with a
      declared `author:` for the narrative forms `[+@key]` / `[-@key]`. What
      remains out of reach is everything that needs *structured* entries:
      author-date marks `(Parnas, 1972)` at every site, alphabetical-by-author
      ordering, `2026a` / `2026b` disambiguation, and entry formatting itself.
      That means a real bibliography parser (`.bib` / CSL-JSON) plus a CSL style
      engine. Its own spec when the time comes. Raised 2026-08-11 while designing
      the prose-entry version; narrowed 2026-08-12 when the narrative forms
      shipped — see `docs/superpowers/specs/2026-08-12-narrative-citations-design.md`.
- [ ] **Inline code is code, for citations and footnotes too.** `glossary.py`
      now skips `` `code` `` spans via `source.code_spans`; `citations.py` and
      `footnotes.py` still protect fenced blocks only, so a `[@key]` or `[^a]`
      written inside a code span is rewritten and injects raw HTML into a
      literal. Same one-line fix in each `finditer` guard. Found 2026-08-12 in
      the glossary acceptance run, where the manuscript glosses a term inside
      `` `kubectl apply --dry-run=server` ``.
- [ ] **Chapter endnotes land on the next chapter's page.** With
      `footnotes: chapter`, the endnotes section is injected before the next `#`
      — which in a project falls *after* the per-file `\newpage`, so a chapter's
      notes open the following chapter's page instead of closing their own.
      Visible throughout *Mostly Harmless AI*; the part-divider case is worked
      around with `break-before: page` on `h1.part`, but chapters still show it.
      Probably wants the endnotes emitted before the break rather than after.
      Found 2026-08-12 in the glossary acceptance run.
- [ ] **A heading with no blank line after it loses its attributes.** `# Title
      {.part}` immediately followed by prose is one block, never reaches
      `_heading_unit`, and silently renders the attribute list as literal text
      with no id, no classes and no TOC entry. Valid CommonMark, and it fails
      quietly. Found 2026-08-12 while migrating the manuscript.
- [x] **Glossary, and the last of the book apparatus.** `[~key]` /
      `[display]{~key}` markers, a `::: glossary` section with page back-links, a
      `css:` project key, and `{.part}` / `{.unnumbered}` in the `book` theme.
      Shipped 2026-08-12 — spec at
      `docs/superpowers/specs/2026-08-12-glossary-and-book-apparatus-design.md`,
      plan at `docs/superpowers/plans/2026-08-12-glossary-and-book-apparatus-plan.md`.
      Acceptance: *Mostly Harmless AI* renders 307 pages in 50 s with no
      warnings, 505 of 515 entries carrying page lists.
- [ ] **HTML and EPUB renderers.** Deferred out of the glossary design above, but
      they are what actually retires Quarto: *Mostly Harmless AI* ships an HTML
      book to books.apiad.net and an EPUB on Gumroad, and until these exist the
      book is PDF-only. Its own spec when the time comes.
- [ ] **Dangling cross-reference warning.** `@fig-missing` (a *known* prefix with
      no target) still renders as an empty anchor. Narrowing `_REF` in v0.4.0
      fixed the silent-deletion case for unknown prefixes; making a known-prefix
      miss warn is the remaining half.
- [ ] **Bare `$` in prose is parsed as inline math.** `dollarmath_plugin` is
      configured with `allow_space=True`, so any two dollar amounts on the same
      line (`costs $2.34 ... and $0.03`) become a math span and render as a black
      bar. Money-heavy documents currently need every `$` escaped as `\$`, which
      is a footgun a market report or invoice will hit on line one. Options:
      require no space after the opening `$` (drop `allow_space`), or refuse to
      open a math span when the character after `$` is a digit followed by a
      digit/comma/period. Found while rendering
      `vault/+/agent_drafts/2026-08-12-frontier-ai-value-report.md` (2026-08-12).
      **Confirmed corrupting a real book the same day.** *Mostly Harmless AI*
      writes `GPT-3 175B at $2M in 2020, GPT-4 at $40M in 2023` in a note; the
      page rendered `GPT-3 175B at ⟨math⟩ 40M in 2023` — the GPT-3 figure and
      the GPT-4 label swallowed. Escaped in that manuscript; the engine is still
      wrong. Note the failure shape, because it raises the priority: it deletes
      prose **silently**, with no warning and a page that looks fine, so only a
      source-to-page comparison catches it.
