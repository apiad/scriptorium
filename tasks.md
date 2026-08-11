# Tasks

Actionable items for scriptorium. One line each; link the spec when there is one.

## Open

- [ ] **Proper CSL citations.** The v0.4.x citation feature deliberately takes
      bibliography entries as **prose strings**, so it can only ever do numeric
      `[1]` references — author-date `(Parnas, 1972)` is impossible by
      construction, not deferred. Moving to author-date means a real
      bibliography parser (`.bib` / CSL-JSON) plus a CSL style engine, with
      structured author/title/year fields, alphabetical-by-author ordering, and
      `2026a` / `2026b` disambiguation. Its own spec when the time comes.
      Raised 2026-08-11 while designing the prose-entry version.
- [ ] **Dangling cross-reference warning.** `@fig-missing` (a *known* prefix with
      no target) still renders as an empty anchor. Narrowing `_REF` in v0.4.0
      fixed the silent-deletion case for unknown prefixes; making a known-prefix
      miss warn is the remaining half.
