"""The formal theme: vendored Times-metric serif, clause numbering, apparatus."""

import re
import subprocess
from pathlib import Path

from scriptorium.galley import render_pdf
from scriptorium.theme import load_theme

_SRC = """---
theme: formal
bibliography:
  law: "Civil Code, Law No. 59 of 1987."
---

# Agreement

::: clauses

## Object

The object.[@law]

1. First duty.
2. Second duty.

## Price

The price.

1. Paid on signature.

:::
"""


def test_formal_font_urls_resolve_to_vendored_files():
    # pdffonts cannot catch a bad url here: Liberation Serif is a common system
    # font, so a broken @font-face falls back to the installed copy and embeds
    # the same name. Only the vendored files exist on a clean machine.
    css = load_theme("formal").css
    paths = re.findall(r"url\('file://([^']*LiberationSerif[^']*)'\)", css)
    assert len(paths) == 4
    assert all(Path(p).is_file() for p in paths)


def test_formal_numbers_clauses_and_cites(tmp_path):
    out = tmp_path / "f.pdf"
    render_pdf(_SRC, str(out), execute=False)

    text = "".join(subprocess.run(["pdftotext", str(out), "-"],
                                  capture_output=True, text=True).stdout.split())
    assert "1.Object" in text and "2.Price" in text
    assert "1.1Firstduty" in text and "1.2Secondduty" in text
    assert "2.1Paidonsignature" in text      # sub-clauses restart under each clause
    assert "[1]" in text and "CivilCode,LawNo.59of1987." in text
