"""The document language: `lang:` decides the hyphenation dictionary."""

import subprocess

import pytest

from scriptorium.galley import render_pdf

# A column narrower than one word forces a break inside nearly every "desarrollo".
# English patterns break it as de-sar-rol-lo, splitting the Spanish rr;
# Spanish patterns give de-sa-rro-llo.
_BODY = '<div style="width:12mm">' + "desarrollo " * 30 + "</div>\n"


def _lines(tmp_path, front: str, theme: str = "note") -> list[str]:
    out = tmp_path / "l.pdf"
    render_pdf(f"---\ntheme: {theme}\n{front}---\n\n{_BODY}", str(out), execute=False)
    text = subprocess.run(["pdftotext", str(out), "-"], capture_output=True, text=True).stdout
    return [l.strip() for l in text.splitlines() if l.strip()]


def _breaks(lines) -> set[str]:
    # pdftotext writes the inserted hyphen as U+2010
    return {l.split()[-1] for l in lines if l.endswith(("‐", "-"))}


def test_default_is_still_english(tmp_path):
    assert "desar‐" in _breaks(_lines(tmp_path, ""))


def test_frontmatter_lang_hyphenates_spanish_as_spanish(tmp_path):
    breaks = _breaks(_lines(tmp_path, "lang: es\n"))
    assert breaks, "the column is narrow enough that something must break"
    assert "desar‐" not in breaks and "desarrol‐" not in breaks
    assert breaks <= {"de‐", "desa‐", "desarro‐"}


def test_uh_theme_defaults_to_spanish(tmp_path):
    assert "desar‐" not in _breaks(_lines(tmp_path, "", theme="uh"))


def test_a_lang_that_is_not_a_language_tag_is_a_hard_error(tmp_path):
    # it lands inside an HTML attribute
    with pytest.raises(ValueError, match="lang"):
        _lines(tmp_path, "lang: \"es' onload='x\"\n")


def test_a_project_sets_lang_in_its_yaml(tmp_path):
    (tmp_path / "a.md").write_text(_BODY, encoding="utf-8")
    (tmp_path / "scriptorium.yaml").write_text(
        "theme: note\nlang: es\nfiles:\n  - a.md\n", encoding="utf-8")

    from scriptorium.project import load
    proj = load(tmp_path / "scriptorium.yaml")
    out = tmp_path / "p.pdf"
    render_pdf(proj.src, str(out), theme_name=proj.theme, cwd=str(tmp_path),
               execute=False, vars=proj.vars, project_meta=proj.meta)
    text = subprocess.run(["pdftotext", str(out), "-"], capture_output=True, text=True).stdout
    breaks = _breaks(l.strip() for l in text.splitlines() if l.strip())
    assert breaks and "desar‐" not in breaks
