import pytest
from scriptorium.book import _carry_counters, resolve_refs
from scriptorium.media import audio_sources, is_audio
from scriptorium.parse import parse
from scriptorium.render import render_html


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
    from scriptorium.render import prepare
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
