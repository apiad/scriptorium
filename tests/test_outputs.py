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


def _two_pdf_project(tmp_path):
    (tmp_path / "a.md").write_text("# A\n\nHello.\n", encoding="utf-8")
    path = tmp_path / "scriptorium.yaml"
    path.write_text("""theme: book
files: [a.md]
outputs:
  print: {format: pdf}
  pocket: {format: pdf, file: small.pdf, page: {size: A5}}
""", encoding="utf-8")
    return path


def test_render_builds_every_output(tmp_path, capsys):
    from scriptorium.cli import main
    proj = _two_pdf_project(tmp_path)
    assert main(["render", str(proj)]) == 0
    assert (tmp_path / "print.pdf").exists() and (tmp_path / "small.pdf").exists()
    assert abs(_mm(tmp_path / "small.pdf")[0] - 148) < 0.5
    out = capsys.readouterr().out
    assert "print:" in out and "pocket:" in out


def test_only_builds_one(tmp_path):
    from scriptorium.cli import main
    proj = _two_pdf_project(tmp_path)
    assert main(["render", str(proj), "--only", "pocket"]) == 0
    assert not (tmp_path / "print.pdf").exists() and (tmp_path / "small.pdf").exists()


def test_dash_o_with_several_outputs_is_refused(tmp_path, capsys):
    from scriptorium.cli import main
    proj = _two_pdf_project(tmp_path)
    assert main(["render", str(proj), "-o", str(tmp_path / "x.pdf")]) == 2
    assert "--only" in capsys.readouterr().err


def test_dash_o_with_one_selected_output_writes_there(tmp_path):
    from scriptorium.cli import main
    proj = _two_pdf_project(tmp_path)
    assert main(["render", str(proj), "--only", "print", "-o", str(tmp_path / "x.pdf")]) == 0
    assert (tmp_path / "x.pdf").exists()


def test_only_with_an_unknown_name_lists_the_names(tmp_path, capsys):
    from scriptorium.cli import main
    proj = _two_pdf_project(tmp_path)
    assert main(["render", str(proj), "--only", "web"]) == 2
    assert "print, pocket" in capsys.readouterr().err


def test_project_without_outputs_still_writes_book_pdf(tmp_path):
    from scriptorium.cli import main
    (tmp_path / "a.md").write_text("# A\n\nHello.\n", encoding="utf-8")
    (tmp_path / "scriptorium.yaml").write_text("theme: book\nfiles: [a.md]\n", encoding="utf-8")
    assert main(["render", str(tmp_path / "scriptorium.yaml")]) == 0
    assert (tmp_path / "book.pdf").exists()
