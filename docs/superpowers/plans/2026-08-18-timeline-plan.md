# Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `:::timeline` back-of-book section to scriptorium, populated by inline `[>DATE: label]` markers scattered across chapters, sorted chronologically with optional grouping and CSS back-links.

**Architecture:** A new `timeline.py` pre-processor follows the pattern of `glossary.py` exactly — source-to-source rewriting pass on the concatenated book string, collecting events from inline markers, replacing a `:::timeline` placeholder with the generated sorted block. Two-regex sweep (full form + bare form), same fence/code-span guard, same `target-counter` back-link mechanism.

**Tech Stack:** Python 3.12+, `re`, `dataclasses`, `yaml` (already in project), WeasyPrint CSS `target-counter` for page back-links.

**Spec:** `docs/superpowers/specs/2026-08-18-timeline-design.md`

## Global Constraints

- Python 3.12+. English throughout. Conventional commits. `uv run pytest` must pass before any commit.
- Never use `git add -A` or `git add .` — always name paths explicitly.
- Run command: `cd /home/apiad/Workspace/repos/scriptorium && uv run scriptorium render /path/to/project.yaml`
- Test runner: `cd /home/apiad/Workspace/repos/scriptorium && uv run pytest tests/test_timeline.py -v`
- Render baseline (TSOC, for smoke-testing only): `cd /home/apiad/Workspace/repos/scriptorium && uv run scriptorium render /home/apiad/Workspace/repos/books-tsoc/scriptorium.yaml`
- The engine is theme-agnostic: styling lives in CSS, not in Python.
- `:::timeline` (like `:::glossary`) replaces a placeholder block in the source; if no placeholder, the block is appended after the last paragraph.
- Multi-file projects: `project.py` concatenates all files before pre-processing, so `process_timeline` sees the whole book as one string. No cross-file state needed.

---

### Task 1: Date types — `DateTuple`, `parse_date`, `format_date`, grouping helpers

**Files:**
- Create: `scriptorium/timeline.py` (date section only — tasks 2–4 append to this file)
- Create: `tests/test_timeline.py` (date tests only)

**Interfaces:**
- Produces:
  - `DateTuple(year: int, month: int = 0, day: int = 0)` — `year` is signed (negative = BCE), `month`/`day` are 0 when unspecified. Supports `<` comparison (uses `dataclass(order=True)`).
  - `parse_date(s: str) -> DateTuple | None` — accepts `"1936"`, `"1936-07"`, `"1936-07-28"`, `"300 BCE"`, `"-300"`, `"−300"` (Unicode minus), `"−300-07"`. Returns `None` on unrecognised input.
  - `format_date(dt: DateTuple, override: str | None = None) -> str` — returns `"1936"`, `"July 1936"`, `"July 28, 1936"`, `"300 BCE"`, `"July 300 BCE"`.
  - `_resolve_group(g) -> int | None` — maps `"century"` → 100, `"decade"` → 10, `"millennium"` → 1000, int-string `"50"` → 50, int → int, invalid → `None`.
  - `_group_key(dt: DateTuple, n: int) -> tuple[int, int]` — `(0, bucket)` for CE, `(1, bucket)` for BCE; sorts as oldest-first when events are sorted ascending on this key.
  - `_group_label(bce_flag: int, bucket: int, n: int) -> str` — `"20th Century"`, `"1930s"`, `"3rd Century BCE"`, `"1940–1989"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_timeline.py
"""Timeline pre-processor tests."""

from scriptorium.timeline import (
    DateTuple, parse_date, format_date,
    _resolve_group, _group_key, _group_label,
)


# --- parse_date ---

def test_parse_bare_year():
    assert parse_date("1936") == DateTuple(year=1936)

def test_parse_year_month():
    assert parse_date("1936-07") == DateTuple(year=1936, month=7)

def test_parse_full_date():
    assert parse_date("1936-07-28") == DateTuple(year=1936, month=7, day=28)

def test_parse_bce_word():
    assert parse_date("300 BCE") == DateTuple(year=-300)

def test_parse_bce_ascii_minus():
    assert parse_date("-300") == DateTuple(year=-300)

def test_parse_bce_unicode_minus():
    assert parse_date("\u2212300") == DateTuple(year=-300)

def test_parse_bce_with_month():
    assert parse_date("\u2212300-07") == DateTuple(year=-300, month=7)

def test_parse_unrecognised_returns_none():
    assert parse_date("not a date") is None

def test_parse_empty_returns_none():
    assert parse_date("") is None


# --- format_date ---

def test_format_bare_year():
    assert format_date(DateTuple(year=1936)) == "1936"

def test_format_year_month():
    assert format_date(DateTuple(year=1936, month=7)) == "July 1936"

def test_format_full_date():
    assert format_date(DateTuple(year=1936, month=7, day=28)) == "July 28, 1936"

def test_format_bce_year():
    assert format_date(DateTuple(year=-300)) == "300 BCE"

def test_format_bce_with_month():
    assert format_date(DateTuple(year=-300, month=7)) == "July 300 BCE"

def test_format_override_replaces_auto():
    assert format_date(DateTuple(year=1936), override="A summer of invention") == "A summer of invention"


# --- grouping ---

def test_resolve_group_century():
    assert _resolve_group("century") == 100

def test_resolve_group_decade():
    assert _resolve_group("decade") == 10

def test_resolve_group_millennium():
    assert _resolve_group("millennium") == 1000

def test_resolve_group_integer_string():
    assert _resolve_group("50") == 50

def test_resolve_group_integer():
    assert _resolve_group(100) == 100

def test_resolve_group_none():
    assert _resolve_group(None) is None

def test_resolve_group_invalid():
    assert _resolve_group("banana") is None


def test_group_key_ce_century():
    dt = DateTuple(year=1936)
    assert _group_key(dt, 100) == (0, 19)   # 20th century → bucket 19

def test_group_key_bce_century():
    dt = DateTuple(year=-384)
    assert _group_key(dt, 100) == (1, 3)    # 4th century BCE → bucket 3

def test_group_key_bce_first_century():
    dt = DateTuple(year=-50)
    assert _group_key(dt, 100) == (1, 0)    # 1st century BCE → bucket 0


def test_group_label_ce_century():
    assert _group_label(0, 19, 100) == "20th Century"

def test_group_label_ce_decade():
    assert _group_label(0, 193, 10) == "1930s"

def test_group_label_bce_century():
    assert _group_label(1, 3, 100) == "4th Century BCE"

def test_group_label_bce_decade():
    assert _group_label(1, 38, 10) == "380s BCE"

def test_group_label_ce_millennium():
    assert _group_label(0, 1, 1000) == "2nd Millennium"

def test_group_label_bce_millennium():
    assert _group_label(1, 0, 1000) == "1st Millennium BCE"

def test_group_label_ce_custom_n():
    assert _group_label(0, 1, 50) == "50–99"

def test_group_label_bce_custom_n():
    assert _group_label(1, 0, 50) == "50–1 BCE"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /home/apiad/Workspace/repos/scriptorium && uv run pytest tests/test_timeline.py -v 2>&1 | head -30
```

Expected: `ImportError` (module does not exist yet).

- [ ] **Step 3: Create `scriptorium/timeline.py` with date primitives**

```python
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
        end_bce = (bucket + 1) * n
        if n == 10:
            return f"{end_bce}s BCE"
        start_bce = bucket * n + 1
        return f"{end_bce}–{start_bce} BCE"
```

- [ ] **Step 4: Run tests and confirm they pass**

```bash
cd /home/apiad/Workspace/repos/scriptorium && uv run pytest tests/test_timeline.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR"
```

Expected: all date/grouping tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/apiad/Workspace/repos/scriptorium
git add scriptorium/timeline.py tests/test_timeline.py
git commit -m "feat(timeline): date primitives — DateTuple, parse_date, format_date, grouping"
```

---

### Task 2: Data model + YAML loading — `Entry`, `load_entries`

**Files:**
- Modify: `scriptorium/timeline.py` (append after date section)
- Modify: `tests/test_timeline.py` (append)

**Interfaces:**
- Consumes: `DateTuple`, `parse_date` from Task 1.
- Produces:
  - `Entry(key, date, date_display, label, description, category, refs)` dataclass.
    - `key: str`, `date: DateTuple | None`, `date_display: str | None`, `label: str`, `description: str`, `category: str`, `refs: int = 0`.
  - `load_entries(spec, base_dir) -> (dict[str, Entry], list[str])` — spec is either a path string or an inline dict. Returns keyed entries and warnings. An entry with no `label` is skipped with a warning. `date` is parsed via `parse_date`; invalid date → warning, entry skipped.

- [ ] **Step 1: Append tests to `tests/test_timeline.py`**

```python
# --- Entry + load_entries ---

from scriptorium.timeline import Entry, load_entries

YAML_ENTRIES = {
    "turing-paper": {
        "date": "1936-07-28",
        "label": "Turing publishes On Computable Numbers",
        "description": "A landmark paper.",
        "category": "Theory",
    },
    "shannon-paper": {
        "date": "1948",
        "label": "Shannon founds information theory",
        "date-display": "Postwar summer",
    },
}


def test_load_entries_from_dict():
    entries, warnings = load_entries(YAML_ENTRIES, None)
    assert set(entries) == {"turing-paper", "shannon-paper"}
    assert warnings == []
    e = entries["turing-paper"]
    assert e.date == DateTuple(year=1936, month=7, day=28)
    assert e.label == "Turing publishes On Computable Numbers"
    assert e.description == "A landmark paper."
    assert e.category == "Theory"
    assert e.refs == 0


def test_load_entries_date_display():
    entries, _ = load_entries(YAML_ENTRIES, None)
    assert entries["shannon-paper"].date_display == "Postwar summer"


def test_load_entries_from_yaml_file(tmp_path):
    (tmp_path / "t.yaml").write_text(
        'turing-paper:\n  date: "1936"\n  label: "Turing"\n', encoding="utf-8"
    )
    entries, warnings = load_entries("t.yaml", tmp_path)
    assert "turing-paper" in entries
    assert warnings == []


def test_load_entries_missing_label_warns_and_drops():
    entries, warnings = load_entries({"bad": {"date": "1936"}}, None)
    assert entries == {}
    assert any("bad" in w and "label" in w for w in warnings)


def test_load_entries_invalid_date_warns_and_drops():
    entries, warnings = load_entries({"bad": {"date": "not-a-date", "label": "X"}}, None)
    assert entries == {}
    assert any("bad" in w and "date" in w for w in warnings)


def test_load_entries_missing_file_warns():
    entries, warnings = load_entries("missing.yaml", None)
    assert entries == {}
    assert len(warnings) == 1 and "missing.yaml" in warnings[0]


def test_load_entries_no_date_is_ok():
    # date is optional in YAML; required only for key-only markers
    entries, warnings = load_entries({"ev": {"label": "Some event"}}, None)
    assert "ev" in entries
    assert entries["ev"].date is None
    assert warnings == []
```

- [ ] **Step 2: Run tests to confirm new ones fail**

```bash
cd /home/apiad/Workspace/repos/scriptorium && uv run pytest tests/test_timeline.py -v -k "load_entries or Entry" 2>&1 | head -20
```

Expected: `ImportError` for `Entry`, `load_entries`.

- [ ] **Step 3: Append to `scriptorium/timeline.py`**

```python
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
```

- [ ] **Step 4: Run and confirm all tests pass**

```bash
cd /home/apiad/Workspace/repos/scriptorium && uv run pytest tests/test_timeline.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR"
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/apiad/Workspace/repos/scriptorium
git add scriptorium/timeline.py tests/test_timeline.py
git commit -m "feat(timeline): Entry dataclass and load_entries from YAML"
```

---

### Task 3: Marker rewriting — `mark_events`

**Files:**
- Modify: `scriptorium/timeline.py` (append)
- Modify: `tests/test_timeline.py` (append)

**Interfaces:**
- Consumes: `Entry`, `DateTuple`, `parse_date`, `load_entries` from Tasks 1–2. `fence_spans`, `code_spans`, `in_span` from `source.py`.
- Produces:
  - `mark_events(src: str, yaml_entries: dict[str, Entry]) -> tuple[str, list[Entry], list[str]]`
    - Rewrites all `[>DATE: label]` (bare) and `[display]{>DATE: label}` (full) markers.
    - Returns: (rewritten source, list of collected Entry objects in order of first appearance, warnings).
    - Each collected entry has `refs` ≥ 1.
    - Markers inside fenced blocks or inline code are left as-is.
    - For markers with a YAML key, merges inline date/label with YAML description/category.
    - Unknown YAML key: warning, event still registered from inline data.
    - Key-only marker (`[display]{>key}`) with no matching YAML entry: warning, marker left as literal text.
    - Malformed date: warning, marker left as literal text.

**HTML output per marker (in-prose anchor):**
```html
<a class="tl-ref" id="tlref-{key}-{refs}" href="#tl-{key}">{display}</a>
```

**Synthetic key** for markers without an explicit YAML key:
```python
re.sub(r"[^\w]", "-", f"{date_str}-{label}".lower())[:60].strip("-")
```

- [ ] **Step 1: Append tests**

```python
# --- mark_events ---

from scriptorium.timeline import mark_events

_YAML = {
    "turing-paper": Entry(
        key="turing-paper",
        date=DateTuple(year=1936),
        date_display=None,
        label="Turing publishes On Computable Numbers",
        description="",
        category="Theory",
    ),
}


def test_bare_form_registered_and_anchor_emitted():
    src = "In [>1936: Turing invents computation] this happened.\n"
    out, events, warnings = mark_events(src, {})
    assert warnings == []
    assert len(events) == 1
    e = events[0]
    assert e.date == DateTuple(year=1936)
    assert e.label == "Turing invents computation"
    assert e.refs == 1
    assert 'class="tl-ref"' in out
    assert "Turing invents computation" in out


def test_full_form_display_text_in_prose():
    src = "[his landmark paper]{>1936: Turing invents computation} was key.\n"
    out, events, warnings = mark_events(src, {})
    assert "his landmark paper" in out
    assert events[0].label == "Turing invents computation"


def test_yaml_key_merges_category():
    src = "[a paper]{>1936 turing-paper: Turing invents}\n"
    out, events, warnings = mark_events(src, _YAML)
    assert warnings == []
    assert events[0].category == "Theory"


def test_key_only_no_yaml_warns_and_leaves_literal():
    src = "[a paper]{>missing-key}\n"
    out, events, warnings = mark_events(src, {})
    assert any("missing-key" in w for w in warnings)
    assert events == []
    assert "[a paper]" in out


def test_malformed_date_warns_and_leaves_literal():
    src = "[>banana: Some event]\n"
    out, events, warnings = mark_events(src, {})
    assert any("banana" in w for w in warnings)
    assert events == []


def test_same_event_twice_increments_refs():
    src = "[>1936: Turing invents] and [>1936: Turing invents] again.\n"
    out, events, warnings = mark_events(src, {})
    # Same synthetic key → same Entry, refs=2
    assert len(events) == 1
    assert events[0].refs == 2
    assert 'id="tlref-' in out


def test_marker_inside_code_fence_skipped():
    src = "```\n[>1936: Turing invents]\n```\n"
    out, events, _ = mark_events(src, {})
    assert events == []
    assert out == src


def test_marker_inside_inline_code_skipped():
    src = "Use `[>1936: Turing]` to mark events.\n"
    out, events, _ = mark_events(src, {})
    assert events == []


def test_display_date_override_stored_on_entry():
    src = '[>"~2400 years ago": Euclid systematizes geometry]\n'
    out, events, warnings = mark_events(src, {})
    assert warnings == []
    assert events[0].date_display == "~2400 years ago"


def test_bce_date_parsed_correctly():
    src = "[>300 BCE: Euclid systematizes geometry]\n"
    _, events, warnings = mark_events(src, {})
    assert warnings == []
    assert events[0].date == DateTuple(year=-300)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /home/apiad/Workspace/repos/scriptorium && uv run pytest tests/test_timeline.py -v -k "mark_events" 2>&1 | head -20
```

- [ ] **Step 3: Append marker rewriting to `scriptorium/timeline.py`**

```python
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
    (?P<date>[−\-]?\d+(?:-\d{2}(?:-\d{2})?)?|\d+\ BCE)  # required date
    (?:\ "(?P<date_display>[^"]*)")?                       # optional "display"
    (?:\ (?P<key>[\w][\w-]*))?                             # optional key
    \ *:\ *(?P<label>.+)                                   # colon + label
    """,
    re.VERBOSE | re.DOTALL,
)
_KEY_ONLY_RE = re.compile(r"^[\w][\w-]*$")


def _slug(date_str: str, label: str) -> str:
    return re.sub(r"[^\w]", "-", f"{date_str}-{label}".lower())[:60].strip("-")


def _parse_content(s: str) -> "tuple[str|None, str|None, str|None, str|None] | None":
    """Return (date_str, date_display, key, label) or ('key-only', None, key, None)."""
    s = s.strip()
    m = _CONTENT_RE.match(s)
    if m:
        return m.group("date"), m.group("date_display"), m.group("key"), m.group("label").strip()
    if _KEY_ONLY_RE.match(s):
        return None, None, s, None  # key-only
    return None  # malformed


def mark_events(
    src: str, yaml_entries: dict[str, Entry]
) -> tuple[str, list[Entry], list[str]]:
    """Rewrite timeline markers to anchored spans; return (src, events, warnings)."""
    warnings: list[str] = []
    collected: dict[str, Entry] = {}   # key → Entry; order preserved (Python 3.7+)

    def warn(msg: str) -> None:
        if msg not in warnings:
            warnings.append(msg)

    def make_or_get_entry(
        date_str: str | None,
        date_display: str | None,
        key: str | None,
        label: str | None,
        content: str,
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
            return collected.setdefault(key, Entry(
                key=key, date=e.date, date_display=e.date_display or date_display,
                label=e.label, description=e.description, category=e.category,
            ))

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
        else:
            # Same event seen again — just return existing entry for ref-bump
            pass

        if key and key not in yaml_entries:
            warn(f"timeline key {key!r} has no YAML entry (event registered from inline data)")

        return collected[entry_key]

    def anchor(display: str, entry: Entry) -> str:
        entry.refs += 1
        return (f'<a class="tl-ref" id="tlref-{entry.key}-{entry.refs}" '
                f'href="#tl-{entry.key}">{display}</a>')

    def process_match(content: str, display: str) -> str:
        parsed = _parse_content(content)
        if parsed is None:
            warn(f"timeline marker {content!r} is malformed")
            return display  # leave display text, drop marker syntax
        date_str, date_display, key, label = parsed
        e = make_or_get_entry(date_str, date_display, key, label, content)
        if e is None:
            return display  # warning already issued; leave prose text intact
        return anchor(display, e)

    def sweep(text: str, pattern, get_display_and_content) -> str:
        spans = fence_spans(text) + code_spans(text)
        out, last = [], 0
        for m in pattern.finditer(text):
            if in_span(m.start(), spans):
                continue
            out.append(text[last:m.start()])
            last = m.end()
            display, content = get_display_and_content(m)
            out.append(process_match(content, display))
        out.append(text[last:])
        return "".join(out)

    # Full form first: [display]{>content}
    src = sweep(src, _TL_DISPLAY,
                lambda m: (m.group(1), m.group(2)))
    # Bare form: [>content] — display text is the label (everything after first colon)
    src = sweep(src, _TL_BARE,
                lambda m: (m.group(1).split(":", 1)[1].strip()
                           if ":" in m.group(1) else m.group(1),
                           m.group(1)))

    return src, list(collected.values()), warnings
```

Note: for the bare form, the display text is extracted from the label portion of the content (everything after the last `:`). The `sweep` lambda for `_TL_BARE` does a quick extract — `process_match` re-parses the full content string to get the proper label.

- [ ] **Step 4: Run tests**

```bash
cd /home/apiad/Workspace/repos/scriptorium && uv run pytest tests/test_timeline.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR"
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/apiad/Workspace/repos/scriptorium
git add scriptorium/timeline.py tests/test_timeline.py
git commit -m "feat(timeline): mark_events — inline marker rewriting and event collection"
```

---

### Task 4: Section generation + entry point — `_placeholder`, `_component`, `process_timeline`

**Files:**
- Modify: `scriptorium/timeline.py` (append)
- Modify: `tests/test_timeline.py` (append)

**Interfaces:**
- Consumes: all of Tasks 1–3.
- Produces:
  - `process_timeline(src: str, meta: dict, base_dir: Path | None) -> tuple[str, list[str]]`
    — the public entry point, same signature as `process_glossary`.

- [ ] **Step 1: Append tests**

```python
# --- _component and process_timeline ---

from scriptorium.timeline import process_timeline


def _make_src(body: str) -> str:
    return body


def test_no_config_and_no_placeholder_is_noop():
    # No timeline: key, no timeline-group:, no :::timeline placeholder →
    # markers must be left as literal text (feature not opted in).
    src = "Some [>1936: Turing invents computation] prose.\n"
    out, warnings = process_timeline(src, {}, None)
    assert warnings == []
    assert out == src   # marker untouched


def test_timeline_section_appended_when_placeholder_present():
    src = (
        "Some [>1936: Turing invents computation] prose.\n\n"
        "::: timeline\n:::\n"
    )
    out, warnings = process_timeline(src, {}, None)
    assert warnings == []
    assert "Turing invents computation" in out
    assert "1936" in out
    assert "::: timeline" in out


def test_events_sorted_oldest_first():
    src = (
        "[>1948: Shannon] and [>1936: Turing] appeared.\n\n"
        "::: timeline\n:::\n"
    )
    out, _ = process_timeline(src, {}, None)
    turing_pos = out.index("Turing")
    shannon_pos = out.index("Shannon")
    assert turing_pos < shannon_pos   # 1936 before 1948


def test_bce_event_sorts_before_ce():
    src = (
        "[>1936: Turing] and [>300 BCE: Euclid] mentioned.\n\n"
        "::: timeline\n:::\n"
    )
    out, _ = process_timeline(src, {}, None)
    assert out.index("Euclid") < out.index("Turing")


def test_group_by_century_inserts_headers():
    src = (
        "[>1854: Boole] [>1936: Turing] [>300 BCE: Euclid] text.\n\n"
        "::: timeline\n:::\n"
    )
    out, _ = process_timeline(src, {"timeline-group": "century"}, None)
    assert "3rd Century BCE" in out
    assert "19th Century" in out
    assert "20th Century" in out


def test_display_date_override_rendered():
    src = '[>"~2400 years ago": Euclid] mentioned.\n\n::: timeline\n:::\n'
    out, _ = process_timeline(src, {}, None)
    assert "~2400 years ago" in out


def test_back_links_emitted():
    src = "[>1936: Turing] prose.\n\n::: timeline\n:::\n"
    out, _ = process_timeline(src, {}, None)
    assert 'class="tl-back"' in out


def test_two_timeline_blocks_raise():
    src = "::: timeline\n:::\n\n::: timeline\n:::\n"
    import pytest
    with pytest.raises(ValueError, match="two"):
        process_timeline(src, {}, None)


def test_yaml_enrichment_via_meta(tmp_path):
    (tmp_path / "tl.yaml").write_text(
        'turing-paper:\n  date: "1936"\n  label: "Turing publishes"\n  category: "Theory"\n',
        encoding="utf-8",
    )
    src = "[a paper]{>1936 turing-paper: Turing publishes}\n\n::: timeline\n:::\n"
    out, warnings = process_timeline(src, {"timeline": "tl.yaml"}, tmp_path)
    assert warnings == []
    assert "Turing publishes" in out
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /home/apiad/Workspace/repos/scriptorium && uv run pytest tests/test_timeline.py -v -k "process_timeline or component or placeholder" 2>&1 | head -20
```

- [ ] **Step 3: Append to `scriptorium/timeline.py`**

```python
# ---------------------------------------------------------------------------
# Section generation
# ---------------------------------------------------------------------------

_TL_OPEN = re.compile(r"^:{3,}[ \t]*timeline[ \t]*$")
_TL_CLOSE = re.compile(r"^:{3,}[ \t]*$")


def _placeholder(src: str) -> "tuple[int, int] | None":
    """Character range of an author-written `:::timeline` block, if any."""
    spans = fence_spans(src)
    lines = src.split("\n")
    offsets = line_offsets(lines)
    found = None
    for i, line in enumerate(lines):
        if not _TL_OPEN.match(line) or in_span(offsets[i], spans):
            continue
        for j in range(i + 1, len(lines)):
            if _TL_CLOSE.match(lines[j]):
                if found is not None:
                    raise ValueError("two `:::timeline` blocks; there can be only one")
                found = (offsets[i], offsets[j] + len(lines[j]) + 1)
                break
        else:
            raise ValueError("`:::timeline` block is never closed")
    return found


def _component(events: list[Entry], group_n: "int | None") -> str:
    """Events as a `:::timeline` component, sorted chronologically."""
    if not events:
        return ""

    # Sort oldest-first: most negative year first
    sorted_events = sorted(events, key=lambda e: (e.date.year, e.date.month, e.date.day)
                           if e.date else (float("inf"), 0, 0))

    items = []
    current_group_key = None

    for entry in sorted_events:
        if entry.date is None:
            continue  # safety: entries without dates are skipped in the section

        if group_n is not None:
            gk = _group_key(entry.date, group_n)
            if gk != current_group_key:
                current_group_key = gk
                header = _group_label(gk[0], gk[1], group_n)
                items.append(f'<h3 class="tl-group">{header}</h3>')

        date_str = format_date(entry.date, entry.date_display)
        back = ""
        if entry.refs:
            links = ", ".join(
                f'<a class="tl-back" href="#tlref-{entry.key}-{k}"></a>'
                for k in range(1, entry.refs + 1)
            )
            back = f" ↩ {links}"
        desc = f"\n\n{entry.description}" if entry.description else ""
        cat = f' data-category="{entry.category}"' if entry.category else ""
        items.append(
            f'<span class="tl-entry" id="tl-{entry.key}"{cat}></span>'
            f"**{date_str}** — {entry.label}{back}{desc}"
        )

    return "::: timeline\n" + "\n\n".join(items) + "\n:::\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def process_timeline(
    src: str, meta: dict, base_dir: "Path | None"
) -> tuple[str, list[str]]:
    """Rewrite timeline markers and inject the timeline section.

    Activates when any of: `timeline:` in meta, `timeline-group:` in meta,
    or a `:::timeline` placeholder exists in the source. If none, returns early
    so markers in documents that have not opted into a timeline are left as-is.
    """
    spec = meta.get("timeline")
    group_raw = meta.get("timeline-group")
    warnings: list[str] = []

    head, body = split_frontmatter(src)

    # Cheap activation check — avoid rewriting when the feature is not in use
    try:
        has_placeholder = _placeholder(body) is not None
    except ValueError as exc:
        return src, [str(exc)]

    if not spec and not group_raw and not has_placeholder:
        return src, []

    yaml_entries, load_warnings = load_entries(spec, base_dir) if spec else ({}, [])
    warnings += load_warnings

    group_n = _resolve_group(group_raw)
    if group_raw is not None and group_n is None:
        warnings.append(f"timeline-group {group_raw!r} is not valid; using flat order")

    marked, events, mark_warnings = mark_events(body, yaml_entries)
    warnings = warnings + mark_warnings

    if not events:
        return head + marked, warnings

    block = _component(events, group_n)
    at = _placeholder(marked)
    if at:
        return head + marked[: at[0]] + block + marked[at[1] :], warnings
    return head + marked.rstrip() + "\n\n" + block, warnings
```

- [ ] **Step 4: Run all tests**

```bash
cd /home/apiad/Workspace/repos/scriptorium && uv run pytest tests/test_timeline.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR"
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/apiad/Workspace/repos/scriptorium
git add scriptorium/timeline.py tests/test_timeline.py
git commit -m "feat(timeline): _component, process_timeline — section generation and entry point"
```

---

### Task 5: Pipeline wiring — `galley.py` + `project.py`

**Files:**
- Modify: `scriptorium/galley.py` lines ~672–684 (pre-processor chain)
- Modify: `scriptorium/project.py` (add `timeline` and `timeline-group` to meta pass-through)

**Interfaces:**
- Consumes: `process_timeline(src, meta, base_dir) -> (src, warnings)` from Task 4.
- Produces: `process_timeline` called in the render pipeline; `timeline` and `timeline-group` keys from `scriptorium.yaml` available in `meta`.

- [ ] **Step 1: Write a failing integration smoke test**

```python
# append to tests/test_timeline.py

import subprocess, sys, textwrap
from pathlib import Path


def test_renders_without_error(tmp_path):
    """Smoke: a one-file project with timeline markers renders to PDF."""
    md = tmp_path / "book.md"
    md.write_text(textwrap.dedent("""\
        # Chapter One

        In [>1936: Turing defines computability] things changed.

        Later [>1948: Shannon founds information theory] happened.

        # Timeline {.unnumbered}

        ::: timeline
        :::
    """), encoding="utf-8")

    proj = tmp_path / "book.yaml"
    proj.write_text(textwrap.dedent(f"""\
        theme: book
        timeline-group: century
        vars:
          title: Test Book
          author: Test
        files:
          - book.md
    """), encoding="utf-8")

    out_pdf = tmp_path / "book.pdf"
    result = subprocess.run(
        [sys.executable, "-m", "scriptorium", "render", str(proj), "--output", str(out_pdf)],
        cwd="/home/apiad/Workspace/repos/scriptorium",
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert out_pdf.exists()
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /home/apiad/Workspace/repos/scriptorium && uv run pytest tests/test_timeline.py::test_renders_without_error -v 2>&1 | tail -15
```

Expected: test passes (pipeline doesn't choke) but markers are not processed (literal text in PDF). This confirms wiring is needed, not that the feature is broken.

Actually: the markers will just appear as literal text since `process_timeline` is not yet called. The test may pass trivially — that's fine; it will be a real smoke test once wired.

- [ ] **Step 3: Add `timeline` + `timeline-group` to `project.py` meta pass-through**

In `scriptorium/project.py`, find the `meta = {k: spec[k] for k in (...) if k in spec}` line and add the new keys:

```python
    meta = {k: spec[k]
            for k in ("bibliography", "nocite", "glossary", "css", "footnotes",
                      "timeline", "timeline-group")
            if k in spec}
```

- [ ] **Step 4: Wire `process_timeline` into `galley.py`**

In `scriptorium/galley.py`, find the pre-processor block (around line 672):

```python
    from .parse import fill_toc
    from .footnotes import process_footnotes, resolve_footnote_mode
    from .citations import process_citations
    from .glossary import process_glossary
```

Add the import:

```python
    from .timeline import process_timeline
```

And after the `process_glossary` line (around line 683):

```python
    src, gloss_warnings = process_glossary(src, meta, Path(cwd) if cwd else None)
```

Add:

```python
    src, tl_warnings = process_timeline(src, meta, Path(cwd) if cwd else None)
```

And extend the warnings accumulation on the next line:

```python
    warnings = css_warnings + warnings + cite_warnings + gloss_warnings + tl_warnings
```

- [ ] **Step 5: Run full test suite**

```bash
cd /home/apiad/Workspace/repos/scriptorium && uv run pytest -v 2>&1 | tail -20
```

Expected: all PASS (including the integration smoke test).

- [ ] **Step 6: Commit**

```bash
cd /home/apiad/Workspace/repos/scriptorium
git add scriptorium/galley.py scriptorium/project.py
git commit -m "feat(timeline): wire process_timeline into render pipeline"
```

---

### Task 6: Theme — CSS, component HTML, theme.yml

**Files:**
- Create: `themes/base/components/timeline.html`
- Modify: `themes/base/styles.css`
- Modify: `themes/base/theme.yml`
- Modify: `themes/book/styles.css`

**Interfaces:**
- Consumes: `:::timeline` component block emitted by `_component`.
- Produces: styled timeline section in PDF: date column left, label+back-links right, group headers between groups.

- [ ] **Step 1: Create `themes/base/components/timeline.html`**

```html
<section class="timeline">{{content}}</section>
```

- [ ] **Step 2: Add timeline to `themes/base/theme.yml`**

In `themes/base/theme.yml`, find the `components:` section and add alongside `glossary`:

```yaml
  timeline:
    keep_together: false
```

- [ ] **Step 3: Add base CSS to `themes/base/styles.css`**

Append after the glossary block (find `.glossary a { color: var(--accent-dark) ... }`):

```css
/* --- timeline --- */
.timeline { margin-top: 6mm; padding-top: 3mm; border-top: 0.3mm solid var(--rule); }
.timeline.labelled { border-top: none; padding-top: 0; }
.tl-group { font-size: 10pt; font-variant: small-caps; letter-spacing: 0.04em;
            color: var(--accent-dark); margin: 4mm 0 1.5mm 0; border-bottom: 0.2mm solid var(--rule); }
.timeline p { font-size: 9pt; line-height: 1.45; margin: 0 0 1.5mm 0; text-indent: 0; }
.timeline a { color: var(--accent-dark); border-bottom: none; }
/* Back-links: page numbers filled by target-counter (same as glossary) */
.tl-back::after { content: target-counter(attr(href url), page);
                  font-variant-numeric: tabular-nums; }
```

- [ ] **Step 4: Add book-theme override to `themes/book/styles.css`**

Append after the `.glossary` block in `themes/book/styles.css`:

```css
/* timeline in a book: same treatment as glossary — its own chapter */
.timeline { border-top: none; padding-top: 0; margin-top: 0; }
```

- [ ] **Step 5: Run full suite + render TSOC smoke test**

```bash
cd /home/apiad/Workspace/repos/scriptorium && uv run pytest -v 2>&1 | tail -10
```

Then render a real book to verify visual output (PDF must open and show a Timeline section with dated entries and page back-links):

```bash
cd /home/apiad/Workspace/repos/scriptorium
uv run scriptorium render /home/apiad/Workspace/repos/books-tsoc/scriptorium.yaml 2>&1 | tail -5
```

TSOC has no timeline markers yet — it will render cleanly with no timeline section. That is correct.

- [ ] **Step 6: Commit**

```bash
cd /home/apiad/Workspace/repos/scriptorium
git add themes/base/components/timeline.html themes/base/styles.css themes/base/theme.yml themes/book/styles.css
git commit -m "feat(timeline): theme CSS and component HTML — book and base"
```

- [ ] **Step 7: Push**

```bash
cd /home/apiad/Workspace/repos/scriptorium && git push origin main
```
