# The HTML book

*When to reach for it: changing the `html` output, the reader in
`themes/base/reader/`, the service worker, or debugging a book that pages,
caches or updates wrongly in a browser.*

`render_book()` (`scriptorium/book.py`) writes a static directory from the same
units a PDF prints from: `index.html`, `book.css`, `reader.js`, `sw.js`,
`manifest.webmanifest`, `icons/`, `img/`, `fonts/`. Every URL is relative, so
the directory works under any path on any static host.

## CSS paginates; JavaScript never measures text

`#book` is one element with a fixed height and `column-width` set to a page's
text width. The browser breaks the text into columns and honours the same
`break-*` rules the PDF uses. The reader only translates the strip by one
screen. The geometry makes a screen a whole number of columns: side padding
`M`, column gap `2M`, so one column plus a gap is the stage width (one page),
or two columns plus two gaps are (a spread). The only measurement is
`getBoundingClientRect()` on an element to learn its column, which reads a
layout the browser already did. Do not add code that measures text to decide
breaks: that is the bug class this design exists to avoid.

## What the theme's CSS becomes

`browser_css()` removes what only paged media runs: `@page` rules (including
`@page:left`), `.page` and `.slide` boxes, `string-set`, and any declaration
using `target-counter()`, `target-text()`, `counter(page)`, `leader()` or
`string()`. In a browser such a function invalidates the whole declaration, so
a reference would render empty. `relative_sizes()` turns `font-size: Npt` into a
share of `--reader-size`, so the size buttons scale headings with the text.

Cross-references are written as text in Python by `resolve_refs()`, counting
chapters, sections and figures as the themes' CSS does. The strings are the
theme's, under `html-refs:` in `theme.yml`, merged through `extends:`.

## Rectos

Multi-column layout cannot start a block on a left or right column. After each
layout, in a spread, the reader inserts a `.blank` page before any chapter
whose heading would land on a left page, walking in document order; a blank
also goes first so the cover is a right-hand page. A full page right before a
chapter heading belongs to that chapter, so an opening illustration faces the
chapter's first page.

## Caches and editions

The cache is named `book:<path>:<version>`. The version is the first 12 hex
digits of sha256 over every file except `sw.js`, so a changed book changes
`sw.js` and the browser installs it, and the worker deletes only caches with
its own path prefix: books on one origin never evict each other. The build is
deterministic (images are named by content, WebP and PNG encodings are stable),
so an unchanged rebuild keeps the version and readers see no notice. A test
pins that; keep it green when adding anything to the site.

With `skipWaiting()`, an open page changes controller as the new worker
starts activating, a moment before its `activate` handler deletes the old
cache. Tests that check deletion must poll, and Playwright's
`wait_for_function` does not await a returned promise.

## Defects the first version had, kept as rules

- An illustration that does not fit under a chapter title jumps to the next
  page and leaves the title alone: opening illustrations are full pages.
- A swipe starting on an image began a native drag and fired `pointercancel`:
  book images are not draggable and `dragstart` is cancelled.
- `::first-letter` on "—¡Mira" enlarges the dash and the bang: the drop cap is
  a class set at build time, only before a letter.
- `#toc` outranked `.panel.open`: panel state uses an attribute on the id rule.
- The update notice never showed on a first visit because "was controlled"
  was read once at load: it is tracked across `controllerchange` events.
- Two `header Cache-Control` rules in one Caddy site: the general one won over
  the `sw.js` one. Use mutually exclusive matchers.

## Cost

Layout is proportional to the book. On a 129,000-word book (861 phone pages)
a font change re-lays everything: 1.05 s on a fast CPU, 4.1 s at 4× CPU
throttling; a page turn is 6 to 18 ms. A book of a few dozen pages costs a
proportional fraction.

## Tests

`tests/test_book_*.py` check the directory; `tests/test_reader_browser.py`
(`-m browser`) drives Chromium at phone and desktop sizes, and skips when none
is found (`SCRIPTORIUM_CHROMIUM` points at one).
