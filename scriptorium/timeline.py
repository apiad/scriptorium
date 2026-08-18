"""Chronological timeline index — inline event markers and a back-of-book section.

A source-to-source pre-processor, like glossary.py and citations.py.
process_timeline() is the entry point; it runs after process_glossary().
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .source import code_spans, fence_spans, in_span, line_offsets, split_frontmatter

# ---------------------------------------------------------------------------
# Date types
# ---------------------------------------------------------------------------

_MONTHS = ["", "January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]

_ORDINALS = {1: "1st", 2: "2nd", 3: "3rd"}


def _ordinal(n: int) -> str:
    return _ORDINALS.get(n, f"{n}th")


@dataclass(order=True)
class DateTuple:
    year: int          # signed: -300 = 300 BCE
    month: int = 0     # 0 = unspecified
    day: int = 0       # 0 = unspecified


_DATE_NUMERIC = re.compile(
    r"^(?P<sign>[−\-])?(?P<year>\d+)"
    r"(?:-(?P<month>\d{2})(?:-(?P<day>\d{2}))?)?$"
)
_DATE_BCE_WORD = re.compile(r"^(?P<year>\d+)\s+BCE$")


def parse_date(s: str) -> "DateTuple | None":
    s = s.strip()
    if not s:
        return None
    m = _DATE_BCE_WORD.match(s)
    if m:
        return DateTuple(year=-int(m.group("year")))
    m = _DATE_NUMERIC.match(s)
    if m:
        sign = -1 if m.group("sign") else 1
        year = sign * int(m.group("year"))
        month = int(m.group("month")) if m.group("month") else 0
        day = int(m.group("day")) if m.group("day") else 0
        return DateTuple(year=year, month=month, day=day)
    return None


def format_date(dt: "DateTuple", override: str | None = None) -> str:
    if override:
        return override
    bce = dt.year < 0
    abs_year = abs(dt.year)
    if dt.month == 0:
        return f"{abs_year} BCE" if bce else str(abs_year)
    month_name = _MONTHS[dt.month]
    if dt.day == 0:
        return f"{month_name} {abs_year} BCE" if bce else f"{month_name} {abs_year}"
    return (f"{month_name} {dt.day}, {abs_year} BCE" if bce
            else f"{month_name} {dt.day}, {abs_year}")


_GROUP_ALIASES = {"century": 100, "decade": 10, "millennium": 1000}


def _resolve_group(g) -> "int | None":
    if g is None:
        return None
    if isinstance(g, str):
        if g in _GROUP_ALIASES:
            return _GROUP_ALIASES[g]
        try:
            return int(g)
        except ValueError:
            return None
    if isinstance(g, int):
        return g
    return None


def _group_key(dt: "DateTuple", n: int) -> "tuple[int, int]":
    """Sort key (bce_flag, bucket); sort ascending for oldest-first order."""
    if dt.year >= 0:
        return (0, dt.year // n)
    # BCE: year -1..-n → bucket 0 (1st BCE), year -(n+1)..-2n → bucket 1, etc.
    return (1, (-dt.year - 1) // n)


def _group_label(bce_flag: int, bucket: int, n: int) -> str:
    if bce_flag == 0:  # CE
        if n == 100:
            return f"{_ordinal(bucket + 1)} Century"
        if n == 1000:
            return f"{_ordinal(bucket + 1)} Millennium"
        if n == 10:
            return f"{bucket * n}s"
        start = bucket * n
        return f"{start}–{start + n - 1}"
    else:  # BCE
        if n == 100:
            return f"{_ordinal(bucket + 1)} Century BCE"
        if n == 1000:
            return f"{_ordinal(bucket + 1)} Millennium BCE"
        if n == 10:
            return f"{bucket * n}s BCE"
        end_bce = (bucket + 1) * n
        start_bce = bucket * n + 1
        return f"{end_bce}–{start_bce} BCE"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Entry:
    key: str
    date: DateTuple | None
    date_display: str | None
    label: str
    description: str
    category: str
    refs: int = 0


def load_entries(spec, base_dir: Path | None) -> tuple[dict[str, Entry], list[str]]:
    """`timeline:` is either a path to a YAML file or an inline dict."""
    if isinstance(spec, str):
        path = Path(spec)
        if base_dir is not None and not path.is_absolute():
            path = base_dir / path
        try:
            spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except OSError as exc:
            return {}, [f"timeline file {spec!r} could not be read: {exc}"]

    if not isinstance(spec, dict):
        return {}, ["`timeline:` is neither a mapping nor a path to one"]

    entries: dict[str, Entry] = {}
    warnings: list[str] = []
    for key, value in spec.items():
        if not isinstance(value, dict):
            warnings.append(f"timeline entry {key!r} is not a mapping")
            continue
        if not value.get("label"):
            warnings.append(f"timeline entry {key!r} has no `label:`")
            continue
        date_val = value.get("date")
        date: DateTuple | None = None
        if date_val is not None:
            date = parse_date(str(date_val))
            if date is None:
                warnings.append(f"timeline entry {key!r} has unrecognised `date:` {date_val!r}")
                continue
        entries[key] = Entry(
            key=key,
            date=date,
            date_display=value.get("date-display"),
            label=value["label"],
            description=value.get("description", ""),
            category=value.get("category", ""),
        )
    return entries, warnings


# ---------------------------------------------------------------------------
# Marker rewriting
# ---------------------------------------------------------------------------

# Full form: [display text]{>CONTENT}  — content ends at first }
_TL_DISPLAY = re.compile(r"\[([^\[\]]*)\]\{>([^}]*)\}", re.DOTALL)
# Bare form: [>CONTENT]  — content ends at first ]
_TL_BARE = re.compile(r"\[>([^\]]*)\]")

# Parses the CONTENT string after >.
# Group 1: date string  Group 2: display-date override  Group 3: key  Group 4: label
_CONTENT_RE = re.compile(
    r"""
    (?P<date>\d+\ BCE|[−\-]?\d+(?:-\d{2}(?:-\d{2})?)?)    # required date (BCE form first)
    (?:\ "(?P<date_display>[^"]*)")?                       # optional "display"
    (?:\ (?P<key>[\w][\w-]*))?                             # optional key
    \ *:\ *(?P<label>.+)                                   # colon + label
    """,
    re.VERBOSE | re.DOTALL,
)
_KEY_ONLY_RE = re.compile(r"^[\w][\w-]*$")


def _slug(date_str: str, label: str) -> str:
    return re.sub(r"[^\w]", "-", f"{date_str}-{label}".lower())[:60].strip("-")


def _parse_content(s: str) -> "tuple[str | None, str | None, str | None, str | None] | None":
    """Return (date_str, date_display, key, label) for date form, or
    (None, None, key, None) for key-only, or None for malformed."""
    s = s.strip()
    m = _CONTENT_RE.match(s)
    if m:
        return m.group("date"), m.group("date_display"), m.group("key"), m.group("label").strip()
    if _KEY_ONLY_RE.match(s):
        return None, None, s, None  # key-only
    return None  # malformed


def mark_events(
    src: str, yaml_entries: dict[str, "Entry"]
) -> "tuple[str, list[Entry], list[str]]":
    """Rewrite timeline markers to anchored spans; return (src, events, warnings)."""
    warnings: list[str] = []
    collected: dict[str, Entry] = {}  # key → Entry; order preserved (Python 3.7+)

    def warn(msg: str) -> None:
        if msg not in warnings:
            warnings.append(msg)

    def make_or_get_entry(
        date_str: "str | None",
        date_display: "str | None",
        key: "str | None",
        label: "str | None",
    ) -> "Entry | None":
        # Key-only: requires YAML entry with date + label
        if date_str is None and key is not None:
            if key not in yaml_entries:
                warn(f"timeline key {key!r} is key-only but has no YAML entry")
                return None
            e = yaml_entries[key]
            if e.date is None:
                warn(f"timeline YAML entry {key!r} has no `date:` (required for key-only marker)")
                return None
            return collected.setdefault(
                key,
                Entry(
                    key=key,
                    date=e.date,
                    date_display=e.date_display or date_display,
                    label=e.label,
                    description=e.description,
                    category=e.category,
                ),
            )

        # Date + label form
        dt = parse_date(date_str or "")
        if dt is None:
            warn(f"timeline marker has unrecognised date {date_str!r}")
            return None

        # Synthesize key from date+label if not explicit
        entry_key = key or _slug(date_str, label or "")

        if entry_key not in collected:
            yaml_e = yaml_entries.get(entry_key) if key else None
            collected[entry_key] = Entry(
                key=entry_key,
                date=dt,
                date_display=date_display,
                label=label or (yaml_e.label if yaml_e else ""),
                description=yaml_e.description if yaml_e else "",
                category=yaml_e.category if yaml_e else "",
            )
        # else: same event seen again — existing entry will have refs incremented

        if key and key not in yaml_entries:
            warn(f"timeline key {key!r} has no YAML entry (event registered from inline data)")

        return collected[entry_key]

    def anchor(display: str, entry: "Entry") -> str:
        entry.refs += 1
        return (
            f'<a class="tl-ref" id="tlref-{entry.key}-{entry.refs}" '
            f'href="#tl-{entry.key}">{display}</a>'
        )

    def process_match(content: str, display: str, literal: str) -> str:
        """Attempt to rewrite one marker. Returns anchor HTML on success, or
        `literal` (the full original matched text) when the marker is invalid."""
        parsed = _parse_content(content)
        if parsed is None:
            warn(f"timeline marker {content!r} is malformed")
            return literal
        date_str, date_display, key, label = parsed
        e = make_or_get_entry(date_str, date_display, key, label)
        if e is None:
            return literal  # warning already issued; leave full original text
        return anchor(display, e)

    def sweep(text: str, pattern: re.Pattern, get_display_content_literal) -> str:
        spans = fence_spans(text) + code_spans(text)
        out, last = [], 0
        for m in pattern.finditer(text):
            if in_span(m.start(), spans):
                continue
            out.append(text[last : m.start()])
            last = m.end()
            display, content, literal = get_display_content_literal(m)
            out.append(process_match(content, display, literal))
        out.append(text[last:])
        return "".join(out)

    # Full form first: [display]{>content} — literal is the full matched text
    src = sweep(src, _TL_DISPLAY, lambda m: (m.group(1), m.group(2), m.group(0)))
    # Bare form: [>content] — display is label after ":", literal is full match
    src = sweep(
        src,
        _TL_BARE,
        lambda m: (
            m.group(1).split(":", 1)[1].strip() if ":" in m.group(1) else m.group(1),
            m.group(1),
            m.group(0),
        ),
    )

    return src, list(collected.values()), warnings
