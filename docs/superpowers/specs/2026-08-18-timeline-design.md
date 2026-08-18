# Timeline: a chronological index across chapters

*Status: approved, not yet implemented. 2026-08-18. Verified against v0.8.0.*

*The Science of Computation* tells dozens of historical stories across four parts
and nineteen chapters: Euclid in 300 BCE, Aristotle before him, Turing in 1936,
Shannon in 1948, Cook in 1971, and on. Each story lives in the chapter where it
belongs, but a reader finishing the book has no way to see the whole arc in one
place. A back-of-book timeline would give them that.

This design adds a timeline pre-processor to scriptorium — same pattern as
`glossary.py`, `citations.py`, and `footnotes.py`: a source-to-source pass that
rewrites inline markers, collects events, and emits a sorted `:::timeline` block
wherever the author placed a placeholder.

## Goals

- `[>YEAR: Label]` (bare) and `[display text]{>YEAR: Label}` (full) register an
  event and optionally annotate the prose with a back-linkable anchor.
- Dates support year, year-month, year-month-day, and BCE (negative years).
- A display-date override string lets the author render "20 years later" or
  "~2,400 years ago" instead of the raw year.
- An optional `timeline.yaml` enriches events with description and category
  without burdening the inline marker.
- `:::timeline` renders all events sorted chronologically, with optional grouping
  by century, decade, millennium, or every N years.
- Back-links from each timeline entry to the prose page(s) where the event was
  marked — same CSS `target-counter` mechanism the glossary uses.

## Non-goals

- Relative date *computation* ("20 years after event X") — the author writes the
  display string manually; the engine never reads one event's date to produce
  another's label.
- Sub-day granularity (hours, minutes).
- Multiple timelines in one book. One `:::timeline` block per book.
- HTML and EPUB output. Deferred to the HTML/EPUB design.

## Marker syntax

### Bare form

```markdown
[>1936: Turing publishes On Computable Numbers]
```

The label ("Turing publishes On Computable Numbers") also serves as the display
text in the prose. The event is registered and the label text is wrapped in an
anchor so the timeline entry can back-link to this page.

### Full form

```markdown
[Alan Turing's landmark paper]{>1936: Turing publishes On Computable Numbers}
```

The display text in prose is "Alan Turing's landmark paper"; the timeline label
is the separate string after the colon. Follows the `[display]{~key}` pattern
from the glossary exactly, swapping `~key` for `>DATE: LABEL`.

### Display-date override

```markdown
[display]{>1936 "A summer of invention": Turing publishes...}
[>−300 "~2,400 years ago": Euclid systematizes geometry]
```

A quoted string immediately after the date (before the colon) replaces the
auto-rendered date in the timeline entry. The date is still used for sorting.
Without a quoted string, the date renders automatically.

### With YAML key

```markdown
[display]{>1936 turing-paper: Turing publishes On Computable Numbers}
[display]{>turing-paper}
```

An identifier (letters, digits, hyphens) after the date (and after the optional
display-date quote) links the event to a `timeline.yaml` entry. When the key is
the *only* content after `>`, all data (date, label, description, category) come
from the YAML.

## Date format

| Syntax | Meaning | Auto-display |
|--------|---------|--------------|
| `1936` | year CE | "1936" |
| `1936-07` | year + month | "July 1936" |
| `1936-07-28` | full date | "July 28, 1936" |
| `−300` or `300 BCE` | year BCE | "300 BCE" |
| `−300-07` | BCE + month | "July 300 BCE" |

Internally all dates are stored as a `(sign, year, month, day)` tuple and sorted
numerically. BCE years sort before CE years; within a year, earlier months/days
sort first. Unspecified month/day are treated as 0 for sorting (i.e., a bare year
sorts before any month in that year).

`300 BCE` and `−300` are both accepted and treated identically. The canonical
internal form is the signed tuple.

## timeline.yaml (optional)

```yaml
# Keys: lowercase-kebab-case
turing-paper:
  date: 1936-07-28          # required if marker is key-only
  date-display: "A summer breakthrough"  # optional display override
  label: "Turing publishes On Computable Numbers"   # required if marker is key-only
  description: >
    Alan Turing submits "On Computable Numbers, with an Application to the
    Entscheidungsproblem" to the London Mathematical Society. The paper defines
    what computation means, proves the halting problem undecidable, and makes
    every real computer that will ever exist theoretically possible.
  category: "Theory"        # optional; used for visual distinction in theme CSS
```

Fields `date` and `label` are required only when the marker is key-only. When
the marker carries its own date and label, the YAML entry adds `description` and
`category`; inline values take precedence over YAML values for date and label.

If `timeline.yaml` is absent, all events are defined entirely by their inline
markers. The file is never required.

## scriptorium.yaml configuration

```yaml
timeline: timeline.yaml     # path to optional enrichment file; omit if none
timeline-group: century     # century | decade | millennium | N (integer years)
                            # default: flat (no grouping)
```

`timeline-group: 100` and `timeline-group: century` are equivalent.
`timeline-group: 1000` and `timeline-group: millennium` are equivalent.

## Rendered output

The author places `:::timeline` anywhere in the document (typically back matter,
after the glossary):

```markdown
# Timeline {.unnumbered}

::: timeline
:::
```

The engine replaces this placeholder with the generated block. Without grouping:

```
300 BCE    Euclid systematizes geometry  ↩ p. 12
384 BCE    Aristotle invents formal logic ↩ p. 11
1936       Turing publishes On Computable Numbers  ↩ p. 47, 203
1948       Shannon founds information theory  ↩ p. 89
```

Events are sorted oldest-first (most negative year first). With
`timeline-group: century`:

```
Antiquity (before 0)
  384 BCE   Aristotle invents formal logic  ↩ p. 11
  300 BCE   Euclid systematizes geometry   ↩ p. 12

19th Century
  1854      Boole publishes Laws of Thought  ↩ p. 31

20th Century
  1936      Turing publishes On Computable Numbers  ↩ p. 47, 203
  1948      Shannon founds information theory  ↩ p. 89
```

Group header labels:
- For `millennium`: "1st Millennium CE", "2nd Millennium CE", "1st Millennium BCE", etc.
  BCE millennia count from 0: years −1 to −999 = "1st Millennium BCE", −1000 to −1999 =
  "2nd Millennium BCE".
- For `century`: "19th Century", "20th Century" for CE; "3rd Century BCE", "4th Century BCE"
  for BCE. BCE centuries: years −1 to −99 = "1st Century BCE", −100 to −199 =
  "2nd Century BCE", etc.
- For `decade`: "1930s", "1940s" for CE; "390s BCE", "380s BCE" for BCE.
- For `N`: "YEAR–YEAR+N−1" for CE buckets; "YEAR BCE–YEAR−N+1 BCE" for BCE buckets.

Back-links use the same `target-counter` CSS as the glossary: the engine emits
empty `<a>` anchors per mention; the paged renderer fills in page numbers.

## Implementation

### New file: `scriptorium/timeline.py`

Structure mirrors `glossary.py` (~200 lines):

```
load_entries(spec, base_dir)  →  (dict[str, Entry], warnings)
parse_date(s)                 →  DateTuple | None
format_date(dt, override)     →  str
mark_events(src, entries)     →  (str, list[Event], warnings)
_placeholder(src)             →  (int, int) | None
_component(events, group)     →  str
process_timeline(src, meta, base_dir)  →  (src, warnings)
```

`Entry` holds: `key`, `date`, `date_display`, `label`, `description`, `category`.
`Event` holds: an `Entry` plus `refs` (int, count of back-link anchors).

`mark_events` runs two regex sweeps (full form, bare form) with the same
fence/code-span guard pattern as `glossary.py`. Each match increments `event.refs`
and rewrites the marker to an HTML anchor span.

`_component` sorts events by `(sign, year, month, day)`, groups if configured,
and emits the `:::timeline` block as HTML paragraphs (same contract as
`_component` in `glossary.py`: definitions stay Markdown, rendered by `parse()`).

### Changes to `galley.py` / `project.py`

`process_timeline` is added to the pre-processor chain, after `process_glossary`.
It reads `timeline:` and `timeline-group:` from the project or document meta.

### Theme changes: `themes/book/`

A `timeline` block style: two-column layout (date column + label+backlinks column),
group headers as styled `<h3>`, `category` as a colour-coded class attribute on
each row. Follows the visual family of the `:::glossary` block.

### Tests

- `tests/test_timeline.py` — unit tests for `parse_date`, `format_date`,
  `mark_events`, `_component` (flat and grouped).
- An integration fixture: a two-chapter project with events in both chapters,
  a `:::timeline` placeholder in a third file, rendered and page-counted.
- BCE sorting, display-date override, key-only markers, YAML enrichment, unknown
  keys (warning, anchor kept), malformed dates (warning, marker left as-is).

## Pipeline order

```
footnotes.py → citations.py → glossary.py → timeline.py → parse()
```

`timeline.py` runs last among the pre-processors so a timeline marker can sit
inside a glossed span without double-rewriting.

## Warnings (non-fatal)

- Unknown date format in a marker → warning, marker left as literal text.
- Key referenced in marker has no YAML entry → warning, event still registered
  using inline date and label.
- Marker is key-only but YAML has no matching entry → warning, marker left as
  literal text.
- Two `:::timeline` blocks → error (same contract as glossary).
