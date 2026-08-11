# Authoring a theme

*When to reach for it: creating a new theme, changing an existing one, adding a
component or master, or debugging a customization / font issue.*

A theme is a directory under `themes/<name>/`:

```
themes/<name>/
  theme.yml           metadata, extends:, vars, page geometry, hints, masters
  styles.css          the look (CSS)
  components/*.html    inline component templates ({{prop}} / {{content}})
  masters/*.html       full-page templates (cover, title, section, …)
  assets/…             fonts, images referenced by styles.css (relative urls)
```

## Inheritance

`extends: <parent>` in `theme.yml` merges the chain base-first: CSS concatenated
(child last, so it overrides via the cascade), and components / masters / vars /
`page` / component-hints merged with the child winning. So a theme is a *diff* —
`note` and `article` are small deltas on `base`; `deck` extends `report` to reuse
its component vocabulary.

## How a theme gets picked

`resolve_theme_name` in `galley.py`: an explicit theme wins (`--theme`, or a
project's `scriptorium.yaml theme:`), then the document's own frontmatter
`theme:`, then `DEFAULT_THEME`. A single `.md` that renders standalone should
declare its theme in frontmatter — every file in `examples/` does.

## The customization contract (vars)

Every theme honors these, injected as CSS custom properties:

`accent`, `accent-dark`, `ink`, `muted`, `rule`, `body-font`, `heading-font`,
`mono-font`.

Declare defaults in `theme.yml vars:`; a project's `scriptorium.yaml vars:`
overrides them. So `theme: report` + `vars: {accent: "#0d9488"}` rebrands with no
theme authoring. Use `var(--accent)` etc. in your CSS; don't hardcode colors you
want customizable.

## Components and masters

- **Component** — `::: name mods {attrs}` → a mustache template in
  `components/name.html`. Props default to the document's frontmatter (so
  `{{author}}` works), overridden by `{attrs}`; `{{content}}` is the rendered
  body. Register keep-together in `theme.yml components:`.
- **Master** — a full-page template in `masters/`, triggered by a component whose
  hint has `master: <name>` (it renders as its own page). `theme.yml masters:`
  sets each master's `classes` and `furniture` (`stamp` = the footer).

## Footnotes

`theme.yml` takes a top-level `footnotes:` key — `document` (the `base` default),
`chapter`, or `page`. A document's frontmatter `footnotes:` overrides it; an
unrecognised value is a hard error, not a silent fallback. `book` sets `chapter`
because notes belong with their chapter, not 300 pages away.

The engine emits collected notes as a `::: footnotes` component, so
`components/footnotes.html` is a normal component template you can restyle or
relabel — `base` ships `<section class="footnotes">{{content}}</section>` and the
content is a plain `<ol>`. Style `.footnotes` / `.footnote-ref` in your CSS; for
`page` mode style `.footnote-inline` and the `@page { @footnote { … } }` area.
Leave the hint at `keep_together: false`: an endnotes section is routinely taller
than a page, and keeping it together would overflow it.

## Citations

Citations work the same way and are a *separate* apparatus: the engine emits
collected entries as a `::: references` component, so `components/references.html`
is a normal template you can restyle. `base` ships
`<section class="references">{{content}}</section>` with the same
`keep_together: false` hint, for the same reason.

Style `.references` and `.cite-ref` in your CSS. Keep them visually distinct from
the footnote apparatus — `base` renders citations as bracketed `[1]` on the
baseline and footnotes as bare raised numerals, which is what lets a document
carry both without the reader having to guess which sequence a mark belongs to.

## The template engine (mustache-lite)

- `{{key}}` — a hole (lists join with commas).
- `{{#key}}…{{/key}}` — a section: iterates when `key` is a list (item fields join
  the scope, `{{_n}}` = 1-based index, `{{.}}` = the item for scalar lists),
  renders once for a truthy scalar, drops when empty. Sections nest. This is how
  the `article` title block renders multiple authors with numbered affiliations.

## Gotchas

- **Font urls must resolve.** Use relative `url('assets/fonts/x.woff2')` in
  `@font-face`; the loader rewrites them to absolute `file://` against the theme
  dir. A vendored font referenced by a bad url silently falls back to a system
  font — verify with `pdffonts` on the output that your font actually embedded.
- **Multi-word font names** are quoted when injected as a var, but write your CSS
  fallbacks with an appropriate generic (`serif` vs `sans-serif`).
- **Don't set `.page { padding }`** — the margin comes from `theme.yml page.margin`
  via `--page-margin`. Full-page masters override padding via their own classes.
- **CSS only** for numbering / cross-references — use counters and
  `target-counter(attr(href url), page)`, not engine logic.
