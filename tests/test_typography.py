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

def test_short_para_gets_keep_block():
    out = process_typography(_short_para())
    assert "::: keep" in out


def test_short_para_wrapped_in_keep():
    out = process_typography(_short_para())
    assert out.strip().startswith("::: keep")
    assert out.strip().endswith(":::")


def test_short_para_content_preserved():
    text = _short_para(5)
    out = process_typography(text)
    assert "word word word word word" in out


# ── long paragraph — no wrapping ─────────────────────────────────────────────

def test_long_para_not_wrapped():
    out = process_typography(_long_para())
    assert "::: keep" not in out


def test_long_para_content_preserved():
    words = ["word"] * (SHORT_PARA_WORDS + 5)
    text = " ".join(words)
    out = process_typography(text)
    assert text in out


# ── headings are not wrapped ──────────────────────────────────────────────────

def test_heading_h1_not_wrapped():
    text = "# A short heading"
    out = process_typography(text)
    assert "::: keep" not in out
    assert "# A short heading" in out


def test_heading_h2_not_wrapped():
    out = process_typography("## Section heading")
    assert "::: keep" not in out


def test_heading_h3_not_wrapped():
    out = process_typography("### Subsection")
    assert "::: keep" not in out


# ── \newpage is never wrapped ─────────────────────────────────────────────────

def test_newpage_not_wrapped():
    text = r"\newpage"
    out = process_typography(text)
    assert "::: keep" not in out
    assert r"\newpage" in out


def test_newpage_between_paras_preserved():
    text = f"{_short_para()}\n\n\\newpage\n\n{_short_para()}"
    out = process_typography(text)
    assert r"\newpage" in out
    assert out.count("::: keep") == 2


# ── code fences pass through unchanged ───────────────────────────────────────

def test_code_fence_not_wrapped():
    text = "```python\nx = 1\n```"
    out = process_typography(text)
    assert "::: keep" not in out
    assert "x = 1" in out


def test_tilde_fence_not_wrapped():
    out = process_typography("~~~python\ny = 2\n~~~")
    assert "::: keep" not in out


def test_colon_fence_not_wrapped():
    text = "::: note\nshort text\n:::"
    out = process_typography(text)
    assert "short text" in out
    # the ::: keep wrapper must not appear inside another ::: block
    assert out.count("::: keep") == 0


# ── raw HTML blocks: opening lines are not treated as paragraphs ─────────────

def test_raw_html_opening_line_not_wrapped():
    text = "<div class='custom'></div>"
    out = process_typography(text)
    assert out.strip() == text


# ── blank-line paragraph separation ──────────────────────────────────────────

def test_two_short_paras_both_wrapped():
    text = f"{_short_para()}\n\n{_short_para()}"
    out = process_typography(text)
    assert out.count("::: keep") == 2


def test_short_then_long_para():
    text = f"{_short_para()}\n\n{_long_para()}"
    out = process_typography(text)
    assert out.count("::: keep") == 1


def test_long_then_short_para():
    text = f"{_long_para()}\n\n{_short_para()}"
    out = process_typography(text)
    assert out.count("::: keep") == 1


# ── markdown inside kept paragraph is not escaped ────────────────────────────

def test_bold_markdown_survives_in_keep_block():
    text = "This has **bold** text and more words to stay short."
    out = process_typography(text)
    assert "::: keep" in out
    assert "**bold**" in out  # raw markdown preserved — parse() will render it


def test_newpage_not_counted_in_word_count():
    # \newpage alone is 1 word but must never be wrapped
    out = process_typography(r"\newpage")
    assert "::: keep" not in out


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
    assert out.count("::: keep") == 2
    assert "## Introduction" in out
    assert "print('hello')" in out


def test_short_text_inside_code_fence_not_wrapped():
    out = process_typography("```\nhello world\n```")
    assert "::: keep" not in out


def test_content_after_fence_can_be_wrapped():
    text = f"```\ncode\n```\n\n{_short_para()}"
    out = process_typography(text)
    assert out.count("::: keep") == 1
