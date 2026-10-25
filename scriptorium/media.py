"""Audio in documents: which links are audio and where the HTML names them,
the check that every local file exists, the box a PDF prints in place of a
player (linked to the published site), and the copy into an HTML output's
`media/`."""

import hashlib
import re
import shutil
from html import escape, unescape
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

AUDIO_EXT = frozenset({".mp3", ".ogg", ".opus", ".m4a", ".wav", ".flac"})

_FIGURE = re.compile(r'<figure class="audio"(?: id="([^"]*)")?><audio\b[^>]*\bsrc="([^"]*)"[^>]*></audio>')
_ID = re.compile(r'\bid="([^"]+)"')
# an <audio> element; its own src and its <source> tags are the audio. A
# <source> inside <video> or <picture> is not.
_AUDIO = re.compile(r"<audio\b.*?</audio>", re.S)
_SRC_TAG = re.compile(r'(<(?:audio|source)\b[^>]*\bsrc=")([^"]*)(")')


def is_audio(url: str) -> bool:
    """True when the URL's path ends in an audio extension, in any case."""
    return PurePosixPath(urlsplit(url).path).suffix.lower() in AUDIO_EXT


def audio_sources(html: str) -> list[str]:
    """The src of every <audio> tag and of each <source> inside one, in order."""
    return [m.group(2) for a in _AUDIO.finditer(html) for m in _SRC_TAG.finditer(a.group(0))]


class MediaError(ValueError):
    """A document names an audio file that is not there."""


def check_audio(units, base_dir: Path) -> None:
    """Fail on the first local audio file that does not exist, naming the
    chapter (the last `#` heading before it) so a long book says where."""
    from .book import _is_local

    chapter = "(front)"
    for u in units:
        if u.heading_level == 1:
            chapter = u.heading or chapter
        for src in audio_sources(u.html):
            src = unescape(src)
            if _is_local(src) and not (base_dir / unquote(urlsplit(src).path)).is_file():
                raise MediaError(f"audio file {src!r} not found (chapter {chapter!r})")


def _pages(units):
    """Each unit with the slug of the page its chapter becomes: the chapter's
    `#` heading id, made unique with -2, -3…; units before the first chapter
    are on "index"."""
    used: set[str] = set()
    page = "index"
    for u in units:
        if u.heading_level == 1 and u.heading_id:
            page, n = u.heading_id, 2
            while page in used:
                page, n = f"{u.heading_id}-{n}", n + 1
            used.add(page)
        yield u, page


def page_slugs(units) -> dict[str, str]:
    """Each element id, mapped to the slug of its chapter's page."""
    slugs: dict[str, str] = {}
    for u, page in _pages(units):
        for ident in _ID.findall(u.html):
            slugs.setdefault(ident, page)
    return slugs


def link_audio(units, base_url: str) -> None:
    """Give each audio figure what paper can show instead of a player: a
    `.audio-print` line with the file name, linked to the figure on the
    published site when `base_url` is set. It links the page, not the file,
    so the link survives a rebuild that renames the file's hash. The name is
    an attribute the theme CSS shows, not text: a theme that refers to a figure
    by `target-text()` must read the caption alone."""
    for u, page in _pages(units):
        if '<figure class="audio"' not in u.html:
            continue

        def box(m):
            ident, src = m.group(1), m.group(2)
            name = escape(PurePosixPath(unquote(urlsplit(unescape(src)).path)).name)
            if not base_url:
                return m.group(0) + f'<p class="audio-print" data-file="{name}"></p>'
            href = escape(f"{base_url}{page}.html" + (f"#{ident}" if ident else ""))
            return m.group(0) + f'<p class="audio-print"><a href="{href}" data-file="{name}"></a></p>'

        u.html = _FIGURE.sub(box, u.html)


def collect_media(html: str, base_dir: Path, out_dir: Path) -> str:
    """Copy every local audio file into `out_dir/media/`, as it is, and point
    its tag there. Files are named by content, as images are, so a changed
    sound gets a new URL and a sound used twice is stored once."""
    from .book import _is_local

    def sub(m):
        src = unescape(m.group(2))
        if not _is_local(src):
            return m.group(0)
        path = base_dir / unquote(urlsplit(src).path)
        if not path.is_file():
            return m.group(0)
        name = f"media/{hashlib.sha256(path.read_bytes()).hexdigest()[:12]}{path.suffix.lower()}"
        if not (out_dir / name).exists():
            (out_dir / "media").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, out_dir / name)
        return m.group(1) + name + m.group(3)

    return _AUDIO.sub(lambda a: _SRC_TAG.sub(sub, a.group(0)), html)
