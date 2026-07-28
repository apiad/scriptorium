# Changelog

All notable changes to this project are documented here. Format: Keep a Changelog.

## [Unreleased]

## [v0.1.0] - 2026-07-28

First release. A Markdown-native document engine that weaves to exact-geometry
paginated PDF, executes code in place, and tangles code to source — validated by
rendering the full 440-page Algorithm Codex (title/copyright/53 chapters/appendices,
all 149 `{python}` cells executed).

### Features
- **galley pagination engine** — measure → pack → emit to exact-geometry A4 pages,
  with a drift guard, keep-with-next headings, and line-splitting for code and
  tables so listings never overflow.
- **Themes as project templates** — directory-backed themes (CSS + components +
  masters); a `marketing` report theme and a `book` theme. Numbering,
  cross-references, and TOC page numbers are pure theme CSS (counters,
  `target-counter`/`target-text`).
- **Execution** — run fenced code in a subshell and splice stdout back
  (Quarto-`{python}` monospace or native `{run}` raw-markdown); shared-kernel
  session state, `PYTHONPATH`, and a freeze cache.
- **Tangle** — `export=` code extraction (illiterate-compatible, byte-exact),
  with provenance labels showing each block's file and line range.
- **Math** — LaTeX `$…$` / `$$…$$` to SVG via quickjax (MathJax in QuickJS,
  pure Python, no Node), freeze-cached.
- **Projects** — `scriptorium.yaml` (theme + vars + file list) with `{{var}}`
  substitution; running heads and auto-TOC.
- **CLI** — `scriptorium render` (document or project) and `scriptorium tangle [--test]`.
