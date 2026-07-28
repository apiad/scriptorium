# Releasing

*When to reach for it: cutting a new version.*

Atomic: steps 1–5 leave no observable state if they fail; only 6–8 are
irreversible, so they're last.

1. **Preconditions.** Clean tree (`git status --porcelain` empty), on `main`,
   up to date with `origin`.
2. **Pick the bump** from commits since the last tag: any `feat:` → **minor**, a
   `!:` / `BREAKING CHANGE:` → **major**, else **patch**. We're pre-1.0, so a
   feature is a minor (`0.x.0`).
3. **Gate.** `uv run pytest` — must pass.
4. **Bump `version`** in `pyproject.toml` (no leading `v`; the tag gets `v`).
5. **CHANGELOG.md** — move `## [Unreleased]` to `## [vX.Y.Z] - <date>` with a
   fresh `## [Unreleased]` above; group commit subjects into `### Features` /
   `### Fixes` / `### Other`.
6. **Commit** `chore(release): vX.Y.Z`.
7. **Tag + push**: `git tag -a vX.Y.Z -m "…"`, then push `main` and the tag.
8. **Publish**: `gh release create vX.Y.Z --generate-notes --title "vX.Y.Z"`.

## Going public / to PyPI (when ready)

- Confirm no private references anywhere (`grep -rniE` for anything project- or
  person-specific beyond the author name and generic examples).
- `gh repo edit apiad/scriptorium --visibility public`.
- PyPI: `uv build` then `uv publish` (needs a token). Note in the README that
  WeasyPrint pulls system libs and `quickjax` bundles a JS engine.
