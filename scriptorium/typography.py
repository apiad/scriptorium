"""Pre-processing transform for short-paragraph keep-together.

Wraps prose paragraphs with fewer than SHORT_PARA_WORDS words in a
``<div style="break-inside:avoid">…</div>`` block so WeasyPrint will not
split them across pages.

Only plain paragraph text is touched — headings, code fences, ::: blocks,
and raw HTML blocks are passed through unchanged.
"""

import re

SHORT_PARA_WORDS = 60

# A "fence" marker: any line that opens/closes a code fence or ::: block.
# We skip everything inside these regions.
_FENCE_OPEN = re.compile(r"^(`{3,}|~{3,}|:{3,})\s*\S*", re.MULTILINE)
_FENCE_CLOSE_CODE = re.compile(r"^(`{3,}|~{3,})\s*$", re.MULTILINE)
_FENCE_CLOSE_COMP = re.compile(r"^:{3,}\s*$", re.MULTILINE)

# A line that is a heading (ATX style) or a setext underline, or starts with
# a raw-HTML tag — we don't touch these even when they appear in paragraph position.
_HEADING = re.compile(r"^#{1,6}\s")
_HTML_BLOCK = re.compile(r"^\s*<[a-zA-Z/!]")


def process_typography(text: str) -> str:
    """Wrap short prose paragraphs in a break-inside:avoid container.

    A "short paragraph" is a block of consecutive non-blank lines that:
    - is not inside a code fence or ::: block
    - does not start with a heading marker or raw-HTML tag
    - has fewer than SHORT_PARA_WORDS words (counted on the raw markdown text)
    """
    lines = text.split("\n")
    out: list[str] = []
    fence_depth = 0  # >0 means we're inside a fenced region
    fence_char: str | None = None  # the opening char sequence length marker

    # We process line by line, collecting paragraph runs.
    para_lines: list[str] = []  # lines of the current paragraph
    para_start: int = 0         # index into `out` where this para starts

    def flush_para():
        """Decide whether to wrap the buffered paragraph."""
        nonlocal para_lines
        if not para_lines:
            return
        block = "\n".join(para_lines)
        word_count = len(block.split())
        if word_count < SHORT_PARA_WORDS:
            out.append(f'<div style="break-inside:avoid">\n{block}\n</div>')
        else:
            out.append(block)
        para_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # --- fence tracking ---
        if fence_depth == 0:
            m = _FENCE_OPEN.match(line)
            if m:
                flush_para()
                fence_char = m.group(1)
                fence_depth = 1
                out.append(line)
                i += 1
                continue
        else:
            # inside a fenced region — look for the matching closer
            opener = fence_char or ""
            if opener.startswith(":"):
                close_pat = _FENCE_CLOSE_COMP
            else:
                close_pat = _FENCE_CLOSE_CODE
            if close_pat.match(line):
                fence_depth = 0
                fence_char = None
            out.append(line)
            i += 1
            continue

        # --- outside fences ---
        stripped = line.strip()

        if not stripped:
            # blank line: end of a paragraph
            flush_para()
            out.append(line)
        elif _HEADING.match(line) or _HTML_BLOCK.match(line):
            # heading or raw HTML block: don't touch, don't merge into para
            flush_para()
            out.append(line)
        else:
            # continuation of a paragraph
            para_lines.append(line)

        i += 1

    flush_para()
    return "\n".join(out)
