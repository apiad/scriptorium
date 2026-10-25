import pytest

from scriptorium.book import _carry_counters, render_book, resolve_refs
from scriptorium.media import MediaError, audio_sources, is_audio
from scriptorium.parse import parse
from scriptorium.project import Output, load
from scriptorium.render import prepare, render_html


def _html(src):
    return "".join(u.html for u in parse(src))


def test_an_audio_link_alone_is_a_figure():
    html = _html("![A plucked A3](s/p.mp3)")
    assert '<figure class="audio">' in html
    assert '<audio controls preload="none" src="s/p.mp3"></audio>' in html
    assert "<figcaption>A plucked A3</figcaption>" in html
    assert "<p>" not in html


def test_an_image_link_is_still_an_image():
    html = _html("![Cover](c.png)")
    assert "<img" in html and "<figure" not in html


@pytest.mark.parametrize("ext", ["mp3", "ogg", "opus", "m4a", "wav", "flac", "MP3"])
def test_every_audio_extension(ext):
    assert is_audio(f"a/b.{ext}") and '<figure class="audio">' in _html(f"![x](b.{ext})")


def test_the_id_comes_from_attrs():
    assert '<figure class="audio" id="aud-pluck">' in _html("![x](p.mp3){#aud-pluck}")


def test_an_aud_reference_is_rewritten():
    assert '<a class="ref-aud" href="#aud-pluck"></a>' in _html("Hear @aud-pluck now.")


def test_an_audio_link_in_running_text_is_a_bare_player():
    html = _html("Listen to ![a tone](t.wav) here.")
    assert '<audio controls preload="none" src="t.wav" title="a tone"></audio>' in html
    assert "<figure" not in html


def test_audio_sources_finds_audio_and_source_tags():
    html = '<audio src="a.mp3"></audio><audio controls><source src="b.ogg"></audio>'
    assert audio_sources(html) == ["a.mp3", "b.ogg"]


def test_html_refs_number_audio_apart_from_figures():
    src = ('<figure id="fig-a"><figcaption>F</figcaption></figure>\n\n'
           "![one](1.mp3){#aud-one}\n\n![two](2.mp3){#aud-two}\n\nSee @aud-two.")
    p = prepare(src, execute=False)
    resolve_refs(p.units, p.theme.meta["html-refs"], p.meta)
    html = "".join(u.html for u in p.units)
    assert '<a class="ref-aud" href="#aud-two">Audio 2</a>' in html


def test_carry_counters_carries_audio():
    first = '<section class="chapter"><figure class="audio" id="aud-x"></figure></section>'
    second = '<section class="chapter"><p>next</p></section>'
    assert "audio 1" in _carry_counters([first, second])[1]


def test_the_caption_label_is_in_the_css():
    html, _ = render_html("![one](1.mp3){#aud-one}", execute=False)
    assert 'figure[id^="aud-"]' in html and "--audio-label" in html


def test_a_missing_audio_file_fails_with_its_name_and_chapter(tmp_path):
    with pytest.raises(MediaError, match=r"'gone.mp3' not found \(chapter 'Strings'\)"):
        prepare("# Strings\n\n![x](gone.mp3)", cwd=str(tmp_path), execute=False)


def test_a_remote_audio_file_is_not_checked(tmp_path):
    prepare("![x](https://example.org/a.mp3)", cwd=str(tmp_path), execute=False)


def test_a_frozen_output_naming_a_deleted_file_fails(tmp_path):
    (tmp_path / "t.wav").write_bytes(b"RIFF")
    src = '```python {run}\nprint("![t](t.wav)")\n```'
    prepare(src, cwd=str(tmp_path))
    (tmp_path / "t.wav").unlink()
    with pytest.raises(MediaError, match="t.wav"):
        prepare(src, cwd=str(tmp_path), frozen=True)


def test_base_url_is_a_project_key(tmp_path):
    (tmp_path / "a.md").write_text("# A")
    (tmp_path / "scriptorium.yaml").write_text("base-url: https://example.org/b/\nfiles: [a.md]")
    assert load(tmp_path / "scriptorium.yaml").meta["base-url"] == "https://example.org/b/"


def test_the_print_box_links_to_the_figure_on_the_site(tmp_path):
    (tmp_path / "p.mp3").write_bytes(b"x")
    p = prepare("# Strings {#strings}\n\n![Pluck](p.mp3){#aud-pluck}", cwd=str(tmp_path),
                execute=False, project_meta={"base-url": "https://example.org/b/"})
    html = "".join(u.html for u in p.units)
    assert 'href="https://example.org/b/strings.html#aud-pluck"' in html
    assert "p.mp3" in html


def _book(tmp_path, src, **kw):
    out = tmp_path / "web"
    render_book(src, out, output=Output(name="web", format="html", **kw), base_dir=tmp_path,
                execute=False)
    return out


def test_audio_is_copied_by_content_and_used_once(tmp_path):
    (tmp_path / "my tone.mp3").write_bytes(b"abc")
    out = _book(tmp_path, "# A\n\n![one](my%20tone.mp3)\n\n![two](my%20tone.mp3)")
    files = list((out / "media").iterdir())
    assert len(files) == 1 and files[0].suffix == ".mp3"
    text = "".join(p.read_text() for p in (out / "chapters").iterdir())
    assert text.count(f'src="media/{files[0].name}"') == 2


def test_media_is_not_precached_by_default(tmp_path):
    (tmp_path / "t.mp3").write_bytes(b"abc")
    out = _book(tmp_path, "# A\n\n![t](t.mp3)")
    assert '"media/' not in (out / "sw.js").read_text()


def test_offline_media_precaches_audio(tmp_path):
    (tmp_path / "t.mp3").write_bytes(b"abc")
    out = _book(tmp_path, "# A\n\n![t](t.mp3)", offline_media=True)
    assert '"media/' in (out / "sw.js").read_text()


def test_a_book_reference_names_the_caption_alone(tmp_path):
    import subprocess

    from scriptorium.galley import render_pdf

    (tmp_path / "p.mp3").write_bytes(b"x")
    out = tmp_path / "b.pdf"
    render_pdf("# Strings\n\nSee @aud-pluck.\n\n![A plucked A3](p.mp3){#aud-pluck}",
               str(out), theme_name="book", cwd=str(tmp_path), execute=False)
    text = subprocess.run(["pdftotext", str(out), "-"], capture_output=True, text=True,
                          check=True).stdout
    assert "“A plucked A3” (p." in " ".join(text.split())
    assert "p.mp3" in text


def test_a_video_source_is_not_audio(tmp_path):
    html = '<video controls><source src="clip.mp4"></video><audio><source src="a.ogg"></audio>'
    assert audio_sources(html) == ["a.ogg"]
    (tmp_path / "a.ogg").write_bytes(b"x")
    prepare(html, cwd=str(tmp_path), execute=False)


def test_the_cli_reports_a_missing_audio_file_in_one_line(tmp_path, capsys):
    from scriptorium.cli import main

    doc = tmp_path / "d.md"
    doc.write_text("# Strings\n\n![x](gone.mp3)")
    assert main(["render", str(doc), "--html", "--no-execute"]) == 2
    err = capsys.readouterr().err
    assert err == "scriptorium: audio file 'gone.mp3' not found (chapter 'Strings')\n"


def test_an_inline_player_prints_its_caption_and_file(tmp_path):
    import subprocess

    from scriptorium.galley import render_pdf

    (tmp_path / "tone.wav").write_bytes(b"x")
    out = tmp_path / "i.pdf"
    render_pdf("Inline: listen to ![a tone](tone.wav) here.", str(out),
               cwd=str(tmp_path), execute=False)
    text = " ".join(subprocess.run(["pdftotext", str(out), "-"], capture_output=True,
                                   text=True, check=True).stdout.split())
    assert "a tone" in text and "tone.wav" in text


def test_a_base_url_without_a_slash_still_links_the_page(tmp_path):
    (tmp_path / "p.mp3").write_bytes(b"x")
    p = prepare("# Strings {#strings}\n\n![Pluck](p.mp3){#aud-pluck}", cwd=str(tmp_path),
                execute=False, project_meta={"base-url": "https://example.org/b"})
    html = "".join(u.html for u in p.units)
    assert 'href="https://example.org/b/strings.html#aud-pluck"' in html
