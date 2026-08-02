"""Tests for the typography pre-processing transform (typography.py)."""

from scriptorium.typography import process_typography, SHORT_PARA_WORDS


# ── helpers ──────────────────────────────────────────────────────────────────

def _short_para(n: int = 10) -> str:
    """Return a paragraph with exactly n words."""
    return " ".join(["word"] * n)


def _long_para(n: int = SHORT_PARA_WORDS + 5) -> str:
    """Return a paragraph with n words (≥ SHORT_PARA_WORDS)."""
    return " ".join(["word"] * n)


# ── short paragraph wrapping ─────────────────────────────────────────────────

def test_short_para_gets_break_inside_avoid():
    text = _short_para()
    out = process_typography(text)
    assert 'break-inside:avoid' in out


def test_short_para_wrapped_in_div():
    text = _short_para()
    out = process_typography(text)
    assert out.startswith('<div style="break-inside:avoid">')
    assert out.strip().endswith("</div>")


def test_short_para_content_preserved():
    text = _short_para(5)
    out = process_typography(text)
    assert "word word word word word" in out


# ── long paragraph — no wrapping ─────────────────────────────────────────────

def test_long_para_not_wrapped():
    text = _long_para()
    out = process_typography(text)
    assert 'break-inside:avoid' not in out


def test_long_para_content_preserved():
    words = ["word"] * (SHORT_PARA_WORDS + 5)
    text = " ".join(words)
    out = process_typography(text)
    assert text in out


# ── headings are not wrapped ──────────────────────────────────────────────────

def test_heading_h1_not_wrapped():
    text = "# A short heading"
    out = process_typography(text)
    assert 'break-inside:avoid' not in out
    assert "# A short heading" in out


def test_heading_h2_not_wrapped():
    text = "## Section heading"
    out = process_typography(text)
    assert 'break-inside:avoid' not in out


def test_heading_h3_not_wrapped():
    text = "### Subsection"
    out = process_typography(text)
    assert 'break-inside:avoid' not in out


# ── code fences pass through unchanged ───────────────────────────────────────

def test_code_fence_not_wrapped():
    text = "```python\nx = 1\n```"
    out = process_typography(text)
    assert 'break-inside:avoid' not in out
    assert "x = 1" in out


def test_tilde_fence_not_wrapped():
    text = "~~~python\ny = 2\n~~~"
    out = process_typography(text)
    assert 'break-inside:avoid' not in out


def test_colon_fence_not_wrapped():
    text = "::: note\nshort text\n:::"
    out = process_typography(text)
    assert 'break-inside:avoid' not in out
    assert "short text" in out


# ── raw HTML blocks: opening lines are not treated as paragraphs ─────────────

def test_raw_html_opening_line_not_wrapped():
    # A line that starts with an HTML tag is not wrapped as a paragraph.
    # The tag line itself passes through directly.
    text = "<div class='custom'></div>"
    out = process_typography(text)
    # The single-line HTML block is not wrapped in break-inside:avoid
    assert out.strip() == text


# ── blank-line paragraph separation ──────────────────────────────────────────

def test_two_short_paras_both_wrapped():
    text = f"{_short_para()}\n\n{_short_para()}"
    out = process_typography(text)
    assert out.count('break-inside:avoid') == 2


def test_short_then_long_para():
    text = f"{_short_para()}\n\n{_long_para()}"
    out = process_typography(text)
    assert out.count('break-inside:avoid') == 1


def test_long_then_short_para():
    text = f"{_long_para()}\n\n{_short_para()}"
    out = process_typography(text)
    assert out.count('break-inside:avoid') == 1


# ── mixed document ────────────────────────────────────────────────────────────

def test_mixed_document():
    text = (
        "## Introduction\n\n"
        f"{_short_para()}\n\n"
        "```python\nprint('hello')\n```\n\n"
        f"{_long_para()}\n\n"
        f"{_short_para(15)}\n"
    )
    out = process_typography(text)
    # Only the two short prose paragraphs should be wrapped
    assert out.count('break-inside:avoid') == 2
    # Heading is untouched
    assert "## Introduction" in out
    # Code fence is untouched
    assert "print('hello')" in out


# ── content inside code fences is not counted as short paragraphs ─────────────

def test_short_text_inside_code_fence_not_wrapped():
    text = "```\nhello world\n```"
    out = process_typography(text)
    assert 'break-inside:avoid' not in out


def test_content_after_fence_can_be_wrapped():
    text = f"```\ncode\n```\n\n{_short_para()}"
    out = process_typography(text)
    assert out.count('break-inside:avoid') == 1
