"""Glossed terms and a back-of-book glossary.

A source-to-source pre-processor, like footnotes.py and citations.py and for the
same reason: parse() renders block by block, so a plugin would never see a marker
and its entry in one render call.

Definitions are opaque Markdown prose, on the same contract as a bibliography
entry: the engine sorts and links them, it never inspects them.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .source import fence_spans, in_span

# `[display]{~key}` and the bare `[~key]`. Excluding `[` as well as `]` from the
# display class is what makes the first pattern match the INNERMOST span of a
# nested pair: with `[^\]]*` the scan runs past the inner opening bracket and
# silently pairs the outer display text with the inner key.
_DISPLAY = re.compile(r"\[([^\[\]]*)\]\{~([\w-]+)\}")
_BARE = re.compile(r"\[~([\w-]+)\]")

_MAX_NESTING = 5


@dataclass
class Entry:
    key: str
    term: str
    definition: str
    refs: int = 0


def load_entries(spec, base_dir: Path | None) -> tuple[dict[str, Entry], list[str]]:
    """`glossary:` is either a mapping or a path to a YAML file holding one.

    A path keeps a five-hundred-entry glossary out of the project file; an inline
    mapping keeps a single document from needing a second file.
    """
    if isinstance(spec, str):
        path = Path(spec)
        if base_dir is not None and not path.is_absolute():
            path = base_dir / path
        try:
            spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except OSError as exc:
            return {}, [f"glossary file {spec!r} could not be read: {exc}"]

    if not isinstance(spec, dict):
        return {}, ["`glossary:` is neither a mapping nor a path to one"]

    entries: dict[str, Entry] = {}
    warnings: list[str] = []
    for key, value in spec.items():
        if not isinstance(value, dict) or not value.get("term"):
            warnings.append(f"glossary entry {key!r} has no `term:`")
            continue
        entries[key] = Entry(key=key, term=value["term"],
                             definition=value.get("definition", ""))
    return entries, warnings


def mark_terms(src: str, entries: dict[str, Entry]) -> tuple[str, list[str]]:
    """Rewrite glossary markers to anchored links; return (src, warnings).

    `entry.refs` is incremented as a side effect: the count is what the section
    turns into one back-link per mention.
    """
    warnings: list[str] = []

    def warn(message: str) -> None:
        if message not in warnings:
            warnings.append(message)

    def anchor(display: str, key: str) -> str:
        if key not in entries:
            warn(f"glossary key {key!r} has no entry")
            return display          # the prose survives; the failure is reported
        entry = entries[key]
        entry.refs += 1
        if "<a " in display:
            # A nested pair: an <a> inside an <a> is invalid HTML — the parser
            # closes the outer early and strands a </a> in the running text — so
            # the outer keeps only its anchor. The inner, more specific term
            # stays clickable and the outer entry still collects a page ref.
            return (f'<span class="gloss-ref" '
                    f'id="glossref-{key}-{entry.refs}">{display}</span>')
        return (f'<a class="gloss-ref" id="glossref-{key}-{entry.refs}" '
                f'href="#gloss-{key}">{display}</a>')

    def sweep(text: str, pattern, render) -> tuple[str, int]:
        # fence_spans is recomputed per sweep on purpose: a rewrite moves every
        # offset after it, so spans from an earlier pass no longer line up.
        spans = fence_spans(text)
        out, last, hits = [], 0, 0
        for m in pattern.finditer(text):
            if in_span(m.start(), spans):
                continue
            out.append(text[last:m.start()])
            last = m.end()
            hits += 1
            out.append(render(m))
        out.append(text[last:])
        return "".join(out), hits

    def bare(m):
        key = m.group(1)
        return anchor(entries[key].term if key in entries else key, key)

    # Only the innermost marker matches, and a replacement contains no brackets,
    # so each pass exposes the next level out. Both patterns run every pass:
    # sweeping all the display forms first and the bare form afterwards leaves
    # `[*the [~inner] case*]{~outer}` permanently unmatched, because the outer's
    # display text still holds a bracket when the display sweep gives up, and by
    # the time the bare form clears it there is no display pass left to run. The
    # cap is a runaway guard, not a limit anyone should reach.
    for _ in range(_MAX_NESTING):
        src, display_hits = sweep(src, _DISPLAY,
                                  lambda m: anchor(m.group(1), m.group(2)))
        src, bare_hits = sweep(src, _BARE, bare)
        if not (display_hits or bare_hits):
            break
    return src, warnings
