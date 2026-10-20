# The HTML book

*When to reach for it: changing the `html` output, the reader in
`themes/base/reader/`, the service worker, or debugging a book that pages,
caches or updates wrongly in a browser.*

`render_book()` (`scriptorium/book.py`) writes a static directory from the same
units a PDF prints from: `index.html`, `chapters/NNN.html`, `book.css`,
`reader.js`, `sw.js`, `manifest.webmanifest`, `icons/`, `img/`, `fonts/`. Every URL is relative, so
the directory works under any path on any static host.

## One chapter at a time

Each chapter is its own file and its own column strip; chapter 0 is the front
(cover and title page). `index.html` carries the TOC, which chapter holds each
id (so a link or a `#hash` loads its chapter first) and each chapter's length.
The reader lays out only the open chapter. It counts the other chapters' pages
in `#measure`, a hidden strip with the same size and the same `.book` rules,
one chapter per idle moment, caches the counts per geometry, font size and
edition, and estimates from length until then (the page total shows `~`).

Because each chapter is laid out alone, the themes' CSS counters would restart
in every chapter. `_carry_counters()` gives each section a `counter-reset` with
the chapter, part and figure values the chapters before it reached.

Splitting was not optional. With the whole book in `index.html`, an 861-page
book took 1.2 s just to parse its 1 MB, and 2.8 s more for the theme's styles
and the columns, before anything showed; a font change re-laid every page.

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

## Heavy books

The worker precaches every file, so by default a reader downloads every image
on the first visit. An illustrated book sets `offline-images: false`: `img/`
leaves the precache, each tag gets `loading="lazy"`, and the worker caches an
image the first time it is fetched, so pages already read keep their images
offline. `image-quality` (default 80) and `image-max-width` set the WebP. The
counting strip `#measure` sits far off screen: Chrome fetches a lazy image
within about a screen of the viewport even inside `visibility:hidden`, and at
`-200vw` a phone fetched the first image of every chapter.

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

On a 129,000-word book (861 pages at 390×844), on a fast CPU and at 4× CPU
throttling: ready to read in 0.44 s / 0.70 s, a font change in 28 / 66 ms,
crossing into a chapter in 8–21 / 35–110 ms, every page counted in the
background after 2.7 / 7.7 s. With one strip for the whole book the same book
took 3.7 / 11.6 s to open and 1.05 / 4.1 s per font change.

## Tests

`tests/test_book_*.py` check the directory; `tests/test_reader_browser.py`
(`-m browser`) drives Chromium at phone and desktop sizes, and skips when none
is found (`SCRIPTORIUM_CHROMIUM` points at one).
