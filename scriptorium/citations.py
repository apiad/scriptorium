"""Pre-processing transform for double-sided citation hyperlinks.

Given a markdown string using the hand-written citation convention:

  In text:          ^[N](#ref-N)^    (superscript form — ^ are literal chars)
                 or [N](#ref-N)      (plain link form)
  In bibliography:  ### N {#ref-N}
                    Citation body text on the next paragraph.

The transform rewrites the document so that:

1. Each citation occurrence gets a unique anchor injected as an inline HTML
   span before the link:
     ^[N](#ref-N)^  ->  ^<span id="cite-N-1"></span>[N](#ref-N)^

2. Each bibliography heading + its following paragraph are fused into a
   hanging-indent HTML block that carries:
   - the anchor span so forward citation links still resolve
   - the number label
   - back-links to every in-text occurrence (↑ for first, 2, 3, … for rest)
   - the citation body text (with markdown links and emphasis rendered)
"""

import re
from collections import defaultdict

# Matches either citation form in a single left-to-right pass.
# Group 1 = full superscript match; groups 2,3 = label,ref for superscript.
# Group 4 = full plain match;       groups 5,6 = label,ref for plain.
_COMBINED = re.compile(
    r"(\^\[(\d+)\]\(#ref-(\d+)\)\^)"        # superscript: ^[N](#ref-N)^
    r"|"
    r"(?<!\^)(\[(\d+)\]\(#ref-(\d+)\))"     # plain: [N](#ref-N)
)

# Matches a bibliography heading followed by its body paragraph.
# Heading: ### N {#ref-N}   (any heading level 1–6, optional trailing space)
# Body: everything up to the next bib heading or end of string.
_BIB_BLOCK = re.compile(
    r"^#{1,6}\s+(\d+)\s*\{#ref-(\d+)\}\s*\n"   # heading line
    r"((?:(?!#{1,6}\s+\d+\s*\{#ref-\d+\}).)*)", # body: up to next bib heading
    re.MULTILINE | re.DOTALL,
)

# Minimal markdown inline renderers for citation body text.
_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_MD_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_MD_ITALIC = re.compile(r"\*([^*]+)\*")
_MD_ITALIC2 = re.compile(r"_([^_]+)_")


def _md_fragment(text: str) -> str:
    """Render a single-paragraph markdown string to inline HTML."""
    text = _MD_LINK.sub(r'<a href="\2">\1</a>', text)
    text = _MD_BOLD.sub(r"<strong>\1</strong>", text)
    text = _MD_ITALIC.sub(r"<em>\1</em>", text)
    text = _MD_ITALIC2.sub(r"<em>\1</em>", text)
    return text.strip()


def process_citations(text: str) -> str:
    """Rewrite *text* (raw markdown) to add double-sided citation links.

    Pass 1 — insert a unique ``<span id="cite-N-k">`` before each in-text
             citation occurrence (preserving the existing link).
    Pass 2 — replace each bibliography ``### N {#ref-N}`` heading + its
             following paragraph with an HTML hanging-indent ``.bib-entry``
             block that includes back-links to every in-text occurrence.
    """

    # --- Pass 1: unique anchors on every in-text citation ------------------
    counters: dict[str, int] = defaultdict(int)
    occurrences: dict[str, list[int]] = defaultdict(list)

    def _dispatch(m: re.Match) -> str:
        if m.group(1):              # superscript form: ^[N](#ref-N)^
            label, ref = m.group(2), m.group(3)
            counters[ref] += 1
            n = counters[ref]
            occurrences[ref].append(n)
            anchor = f'<span id="cite-{ref}-{n}" class="cite-anchor"></span>'
            return f"^{anchor}[{label}](#ref-{ref})^"
        else:                       # plain form: [N](#ref-N)
            label, ref = m.group(5), m.group(6)
            counters[ref] += 1
            n = counters[ref]
            occurrences[ref].append(n)
            anchor = f'<span id="cite-{ref}-{n}" class="cite-anchor"></span>'
            return f"{anchor}[{label}](#ref-{ref})"

    text = _COMBINED.sub(_dispatch, text)

    # --- Pass 2: replace bibliography blocks with HTML ---------------------
    def _replace_bib(m: re.Match) -> str:
        label, ref = m.group(1), m.group(2)
        body = m.group(3).strip()

        occ = occurrences.get(ref, [])
        if occ:
            first, rest = occ[0], occ[1:]
            parts = [f'<a class="bib-back-link" href="#cite-{ref}-{first}">↑ {first}</a>']
            for k in rest:
                parts.append(f'<a class="bib-back-link" href="#cite-{ref}-{k}">{k}</a>')
            back_inner = " ".join(parts)
        else:
            back_inner = ""

        body_html = _md_fragment(body)
        num_html = f'<span id="ref-{ref}" class="bib-num">{label}.</span>'
        back_html = f'<span class="bib-back">{back_inner}</span>' if back_inner else ""
        return (
            f'\n<div class="bib-entry">'
            f"{num_html}"
            f'<span class="bib-body">{body_html}</span>'
            f"{back_html}"
            f"</div>\n"
        )

    text = _BIB_BLOCK.sub(_replace_bib, text)
    return text
