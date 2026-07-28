# Themes

A theme is a project template: it brings a point of view (typography, palette,
components, page masters) and honors a shared **customization contract**. Themes
inherit via `extends:`, so the set below is a ladder you build on top of, not a
list of dead ends.

## The default lineup (simple → gorgeous)

| Theme | For | Look |
|---|---|---|
| `base` | (root — not used directly) | the var contract + vendored fonts + correct base styling |
| `note` | conference notes, handouts, minutes | utilitarian sans, mono meta lines, hard title rule |
| `article` | essays, whitepapers, blog→PDF | serif body, sans display, generous margins, accent section rules |
| `report` | business/marketing/pitch | data-forward: covers, section openers, KPI tiles, finding cards, timelines |
| `book` | polished long-form books | classic serif, quiet large chapter numerals, running heads, auto-TOC |

## Customizing (three tiers of effort)

1. **Vars only** — no theme authoring. In a project's `scriptorium.yaml` (or a
   document's frontmatter):

   ```yaml
   theme: report
   vars:
     accent: "#c026d3"
     body-font: "Source Serif 4"
   ```

   The contract: `accent`, `accent-dark`, `ink`, `muted`, `rule`,
   `body-font`, `heading-font`, `mono-font`. Colors and fonts inject as CSS
   custom properties; components and page styling follow.

2. **Inherit + tweak** — a project-local theme dir that `extends:` one of the
   above and overrides a rule or adds a component/master.

3. **New theme** — `extends: base`, build your own vocabulary from the contract up.

## Bundled fonts

`base` vendors Inter (sans), Source Serif 4 (serif), and JetBrains Mono (mono) as
woff2, so any theme is self-contained and a project can switch faces by var with
no network.
