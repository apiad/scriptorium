"""Images become WebP with their size written in; theme fonts are copied in."""

from PIL import Image

from scriptorium.book import collect_css_assets, collect_images
from scriptorium.theme import load_theme


def _png(path, w, h):
    Image.new("RGB", (w, h), (200, 120, 40)).save(path)


def test_raster_becomes_webp_with_dimensions(tmp_path):
    _png(tmp_path / "my pic.png", 3000, 1500)
    html, _ = collect_images('<img src="my pic.png"><img src="my%20pic.png" width="10">',
                             tmp_path, tmp_path / "out", 1600)
    files = list((tmp_path / "out/img").iterdir())
    assert len(files) == 1 and files[0].suffix == ".webp"
    assert html.count(f'src="img/{files[0].name}"') == 2
    assert html.count('width="1600" height="800"') == 2 and 'width="10"' not in html


def test_small_images_keep_their_size(tmp_path):
    _png(tmp_path / "a.png", 400, 300)
    html, _ = collect_images('<img src="a.png">', tmp_path, tmp_path / "out", 1600)
    assert 'width="400" height="300"' in html


def test_collection_is_byte_identical_twice(tmp_path):
    _png(tmp_path / "a.png", 800, 600)
    collect_images('<img src="a.png">', tmp_path, tmp_path / "o1", 1600)
    collect_images('<img src="a.png">', tmp_path, tmp_path / "o2", 1600)
    (f1,), (f2,) = [list((tmp_path / d / "img").iterdir()) for d in ("o1", "o2")]
    assert f1.name == f2.name and f1.read_bytes() == f2.read_bytes()


def test_svg_is_copied_and_remote_and_data_urls_are_left_alone(tmp_path):
    (tmp_path / "d.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"/>')
    src = '<img src="d.svg"><img src="https://x.org/a.png"><img src="data:image/png;base64,AA==">'
    html, warns = collect_images(src, tmp_path, tmp_path / "out", 1600)
    assert 'src="img/' in html and html.endswith('<img src="https://x.org/a.png"><img src="data:image/png;base64,AA==">')
    assert warns == [] and next((tmp_path / "out/img").iterdir()).suffix == ".svg"


def test_missing_image_warns_and_keeps_src(tmp_path):
    html, warns = collect_images('<img src="nope.png">', tmp_path, tmp_path / "out", 1600)
    assert 'src="nope.png"' in html and "nope.png" in warns[0]


def test_theme_fonts_are_copied_and_relative(tmp_path):
    css = collect_css_assets(load_theme("book").css, tmp_path)
    assert "file://" not in css and "url('fonts/" in css
    assert any(p.suffix == ".woff2" for p in (tmp_path / "fonts").iterdir())


def test_quality_changes_the_file_and_lazy_marks_the_tag(tmp_path):
    Image.effect_noise((800, 600), 60).convert("RGB").save(tmp_path / "n.png")
    hi, _ = collect_images('<img src="n.png">', tmp_path, tmp_path / "hi", 1600)
    lo, _ = collect_images('<img src="n.png">', tmp_path, tmp_path / "lo", 1600, quality=40, lazy=True)
    (a,), (b,) = list((tmp_path / "hi/img").iterdir()), list((tmp_path / "lo/img").iterdir())
    assert a.name != b.name and b.stat().st_size < a.stat().st_size
    assert 'loading="lazy"' in lo and 'loading=' not in hi
