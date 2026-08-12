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
- [ ] **Dangling cross-reference warning.** `@fig-missing` (a *known* prefix with
      no target) still renders as an empty anchor. Narrowing `_REF` in v0.4.0
      fixed the silent-deletion case for unknown prefixes; making a known-prefix
      miss warn is the remaining half.
