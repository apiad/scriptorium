"""display() and rich last expressions in python blocks, and the bundles they print."""

from scriptorium.execute import ExecEnv

RICH = '''
class R:
    def _repr_mimebundle_(self, include=None, exclude=None):
        return {"text/markdown": "**rich**", "text/plain": "R()"}, {"caption": "c"}
'''


def bundles(stdout):
    from scriptorium.bundles import split
    return [b for b in split(stdout) if isinstance(b, dict)]


def test_display_prints_a_bundle(tmp_path):
    res = ExecEnv(cwd=str(tmp_path)).run(RICH + "display(R())\n", "python")
    [b] = bundles(res.stdout)
    assert b["data"]["text/markdown"] == "**rich**" and b["metadata"] == {"caption": "c"}


def test_display_metadata_argument_wins(tmp_path):
    res = ExecEnv(cwd=str(tmp_path)).run(RICH + "display(R(), metadata={'caption': 'd'})\n", "python")
    assert bundles(res.stdout)[0]["metadata"]["caption"] == "d"


def test_rich_last_expression_is_displayed(tmp_path):
    res = ExecEnv(cwd=str(tmp_path)).run(RICH + "R()\n", "python")
    assert len(bundles(res.stdout)) == 1


def test_plain_last_expression_prints_nothing(tmp_path):
    assert ExecEnv(cwd=str(tmp_path)).run("1 + 1\n", "python").stdout == ""


def test_single_repr_methods_are_enough(tmp_path):
    src = "class S:\n    def _repr_svg_(self): return '<svg/>'\nS()\n"
    assert bundles(ExecEnv(cwd=str(tmp_path)).run(src, "python").stdout)[0]["data"] == {"image/svg+xml": "<svg/>"}


def test_traceback_still_numbers_cell_lines(tmp_path):
    res = ExecEnv(cwd=str(tmp_path)).run("x = 1\nraise ValueError('boom')\n", "python")
    assert res.failed and 'File "<cell>", line 2' in res.stdout + res.stderr


SVG_AUDIO = '''
import base64
class V:
    def __init__(self, cap=None): self.cap = cap
    def _repr_mimebundle_(self, include=None, exclude=None):
        md = {"caption": self.cap, "id": "wave"} if self.cap else {}
        return {"image/svg+xml": "<svg xmlns='http://www.w3.org/2000/svg'/>",
                "audio/mpeg": base64.b64encode(b"ID3fake").decode()}, md
'''


def _html(src, tmp_path, env=None):
    from scriptorium.parse import parse
    units = parse(src, env=env or ExecEnv(cwd=str(tmp_path)))
    return units, "".join(u.html for u in units)


def test_image_and_audio_make_one_figure(tmp_path):
    from scriptorium.book import resolve_refs
    from scriptorium.media import audio_sources
    units, html = _html("```python {run}\n" + SVG_AUDIO + "V('A sine')\n```", tmp_path)
    assert html.count("<figure") == 1 and 'id="fig-wave"' in html and "<audio" in html and "A sine" in html
    assert len(list((tmp_path / "build/img").glob("a-sine-*.svg"))) == 1
    assert len(list((tmp_path / "build/audio").glob("a-sine-*.mp3"))) == 1
    assert any(s.endswith(".mp3") for s in audio_sources(html))
    resolve_refs(units, {}, {})  # numbers the figure without complaint


def test_image_only_is_an_image_figure(tmp_path):
    src = "```python {run}\nclass S:\n    def _repr_svg_(self): return '<svg/>'\nS()\n```"
    _, html = _html(src, tmp_path)
    assert "<img" in html and "<audio" not in html


def test_fence_caption_is_the_fallback(tmp_path):
    _, html = _html('```python {run caption="From the fence" id=fig-f}\n' + SVG_AUDIO + "V()\n```", tmp_path)
    assert "From the fence" in html and 'id="fig-f"' in html


def test_output_follows_call_order(tmp_path):
    src = SVG_AUDIO + "print('before')\ndisplay(V('x'))\nprint('after')\n"
    _, html = _html("```python {run echo=false}\n" + src + "```", tmp_path)
    assert html.index("before") < html.index("<figure") < html.index("after")


def test_two_bundles_and_fence_caption_warn(tmp_path):
    env = ExecEnv(cwd=str(tmp_path))
    _html('```python {run caption="c"}\n' + SVG_AUDIO + "display(V(), V())\n```", tmp_path, env)
    assert any("caption" in w for w in env.warnings)


def test_frozen_build_writes_the_files(tmp_path):
    import shutil
    from scriptorium.freeze import Freeze
    fz = Freeze(tmp_path / "f.json")
    src = "```python {run}\n" + SVG_AUDIO + "V('A sine')\n```"
    _html(src, tmp_path, ExecEnv(cwd=str(tmp_path), freeze=fz))
    shutil.rmtree(tmp_path / "build")
    _html(src, tmp_path, ExecEnv(cwd=str(tmp_path), freeze=fz, frozen=True))
    assert len(list((tmp_path / "build/img").glob("*.svg"))) == 1
    assert len(list((tmp_path / "build/audio").glob("*.mp3"))) == 1


def test_a_failing_block_shows_its_bundles_as_text(tmp_path):
    src = "```python {run echo=false}\n" + SVG_AUDIO + "display(V('x'))\nraise ValueError('boom')\n```"
    _, html = _html(src, tmp_path)
    assert "SCRIPTORIUM_BUNDLE" not in html and "ID3" not in html and "\x00" not in html
    assert "boom" in html


def test_an_image_after_printed_text_stands_alone(tmp_path):
    src = ("```python {run echo=false}\nclass S:\n    def _repr_svg_(self): return '<svg/>'\n"
           "print('Intro text')\ndisplay(S(), metadata={'caption': 'a', 'id': 'fig-a'})\n```")
    _, html = _html(src, tmp_path)
    assert "Intro text <img" not in html and "Intro text\n<img" not in html


SITE_HTML = '''
import base64
MP3 = base64.b64encode(b"ID3fake").decode()
class W:
    def _repr_mimebundle_(self, include=None, exclude=None):
        html = ('<figure class="widget"><div>drawn</div>\\n<audio controls src="data:audio/mpeg;base64,' + MP3 +
                '"></audio><figcaption>A widget</figcaption>\\n<script>\\nvar x = 1 < 2 && 3 > 2;\\n</script></figure>')
        return ({"text/html": html, "image/svg+xml": "<svg xmlns='http://www.w3.org/2000/svg'/>", "audio/mpeg": MP3},
                {"caption": "A widget", "id": "w", "site": "html"})
'''


def test_a_site_shows_the_bundles_own_html_with_its_audio_as_a_file(tmp_path):
    from scriptorium.book import resolve_refs
    from scriptorium.media import audio_sources
    env = ExecEnv(cwd=str(tmp_path), site_html=True)
    units, html = _html("```python {run echo=false}\n" + SITE_HTML + "W()\n```", tmp_path, env)
    assert '<figure id="fig-w" class="widget">' in html and "drawn" in html and "<img" not in html
    assert "data:audio" not in html and html.count("<figure") == 1 and html.count("A widget") == 1
    assert "var x = 1 < 2 && 3 > 2;" in html  # the script reaches the page as written
    [src] = audio_sources(html)
    assert src.startswith("build/audio/a-widget-") and (tmp_path / src).read_bytes() == b"ID3fake"
    resolve_refs(units, {}, {})


def test_print_and_the_reader_ignore_the_site_key(tmp_path):
    _, html = _html("```python {run echo=false}\n" + SITE_HTML + "W()\n```", tmp_path)
    assert '<figure class="view" id="fig-w">' in html and "<img" in html and "drawn" not in html
