"""Pre-processing transform for short-paragraph keep-together.

Wraps prose paragraphs with fewer than SHORT_PARA_WORDS words in a
``::: keep`` block so the scriptorium packer treats them as atomic units.

Using ``::: keep`` (not raw ``<div>``) means markdown-it-py still processes
the content inside — bold, math, inline code, ``\\newpage`` etc. all work
correctly. Raw ``<div>`` blocks would be treated as HTML blocks and bypass
inline markdown rendering.

Only plain paragraph text is touched — headings, code fences, ::: blocks,
raw HTML blocks, and ``\\newpage`` markers are passed through unchanged.
"""

import re

SHORT_PARA_WORDS = 60

# A "fence" marker: any line that opens/closes a code fence or ::: block.
_FENCE_OPEN = re.compile(r"^(`{3,}|~{3,}|:{3,})\s*\S*", re.MULTILINE)
_FENCE_CLOSE_CODE = re.compile(r"^(`{3,}|~{3,})\s*$", re.MULTILINE)
_FENCE_CLOSE_COMP = re.compile(r"^:{3,}\s*$", re.MULTILINE)

# Lines we must not touch even in paragraph position.
_HEADING = re.compile(r"^#{1,6}\s")
_HTML_BLOCK = re.compile(r"^\s*<[a-zA-Z/!]")
_NEWPAGE = re.compile(r"^\\newpage\s*$")


def process_typography(text: str) -> str:
    """Wrap short prose paragraphs in a ``::: keep`` container.

    A "short paragraph" is a block of consecutive non-blank lines that:
    - is not inside a code fence or ::: block
    - does not start with a heading marker, raw-HTML tag, or ``\\newpage``
    - has fewer than SHORT_PARA_WORDS words (counted on the raw markdown text)
    """
    lines = text.split("\n")
    out: list[str] = []
    fence_depth = 0
    fence_char: str | None = None

    para_lines: list[str] = []

    def flush_para() -> None:
        nonlocal para_lines
        if not para_lines:
            return
        block = "\n".join(para_lines)
        word_count = len(block.split())
        if word_count < SHORT_PARA_WORDS:
            out.append(f"::: keep\n{block}\n:::")
        else:
            out.append(block)
        para_lines = []

    for line in lines:
        # --- fence tracking ---
        if fence_depth == 0:
            m = _FENCE_OPEN.match(line)
            if m:
                flush_para()
                fence_char = m.group(1)
                fence_depth = 1
                out.append(line)
                continue
        else:
            opener = fence_char or ""
            close_pat = _FENCE_CLOSE_COMP if opener.startswith(":") else _FENCE_CLOSE_CODE
            if close_pat.match(line):
                fence_depth = 0
                fence_char = None
            out.append(line)
            continue

        # --- outside fences ---
        stripped = line.strip()

        if not stripped:
            flush_para()
            out.append(line)
        elif _HEADING.match(line) or _HTML_BLOCK.match(line) or _NEWPAGE.match(stripped):
            flush_para()
            out.append(line)
        else:
            para_lines.append(line)

    flush_para()
    return "\n".join(out)
