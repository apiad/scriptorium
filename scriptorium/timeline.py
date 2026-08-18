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
