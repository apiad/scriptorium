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
