"""outputs: several renders of one project (PDF sizes, the HTML book)."""

import pytest

from scriptorium.project import ProjectError, load


def _project(tmp_path, yaml_text):
    (tmp_path / "a.md").write_text("# A\n\nHello.\n", encoding="utf-8")
    path = tmp_path / "scriptorium.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    return load(path)


def test_no_outputs_defaults_to_one_pdf(tmp_path):
    p = _project(tmp_path, "theme: book\nfiles: [a.md]\n")
    assert [(o.name, o.format, o.file) for o in p.outputs] == [("pdf", "pdf", "book.pdf")]


def test_outputs_take_names_and_defaults(tmp_path):
    p = _project(tmp_path, """files: [a.md]
outputs:
  print: {format: pdf}
  pocket: {format: pdf, file: small.pdf, page: {size: A5, margin: 14mm}}
  web: {format: html, cover: c.jpg, js: [x.js]}
""")
    by = {o.name: o for o in p.outputs}
    assert [o.name for o in p.outputs] == ["print", "pocket", "web"]
    assert by["print"].file == "print.pdf"
    assert by["pocket"].page == {"size": "A5", "margin": "14mm"}
    assert by["web"].dir == "web" and by["web"].image_max_width == 1600
    assert by["web"].js == ["x.js"] and by["web"].cover == "c.jpg"


def test_kebab_keys_map_to_fields(tmp_path):
    p = _project(tmp_path, "files: [a.md]\noutputs:\n  web: {format: html, image-max-width: 900}\n")
    assert p.outputs[0].image_max_width == 900


def test_unknown_output_key_is_named(tmp_path):
    with pytest.raises(ProjectError, match="web.*colour"):
        _project(tmp_path, "files: [a.md]\noutputs:\n  web: {format: html, colour: red}\n")


def test_a_pdf_key_on_an_html_output_is_refused(tmp_path):
    with pytest.raises(ProjectError, match="web.*page"):
        _project(tmp_path, "files: [a.md]\noutputs:\n  web: {format: html, page: {size: A5}}\n")


def test_unknown_format_is_refused(tmp_path):
    with pytest.raises(ProjectError, match="epub"):
        _project(tmp_path, "files: [a.md]\noutputs:\n  e: {format: epub}\n")


def test_outputs_must_be_a_mapping(tmp_path):
    with pytest.raises(ProjectError, match="outputs"):
        _project(tmp_path, "files: [a.md]\noutputs: [pdf, html]\n")


def _mm(path):
    from pypdf import PdfReader
    box = PdfReader(path).pages[0].mediabox
    return float(box.width) * 25.4 / 72, float(box.height) * 25.4 / 72


def test_page_override_sets_a5_and_leaves_the_theme_alone(tmp_path):
    from scriptorium.galley import render_pdf
    md = "---\ntheme: book\n---\n\nHello.\n"
    render_pdf(md, str(tmp_path / "a5.pdf"), page={"size": "A5"})
    render_pdf(md, str(tmp_path / "a4.pdf"))
    w5, h5 = _mm(tmp_path / "a5.pdf")
    w4, h4 = _mm(tmp_path / "a4.pdf")
    assert abs(w5 - 148) < 0.5 and abs(h5 - 210) < 0.5
    assert abs(w4 - 210) < 0.5 and abs(h4 - 297) < 0.5
