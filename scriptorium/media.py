"""Audio in documents: which links are audio, and where the HTML names them."""

import re
from pathlib import PurePosixPath
from urllib.parse import urlsplit

AUDIO_EXT = frozenset({".mp3", ".ogg", ".opus", ".m4a", ".wav", ".flac"})

_SRC = re.compile(r'<(audio|source)\b[^>]*\bsrc="([^"]*)"')


def is_audio(url: str) -> bool:
    """True when the URL's path ends in an audio extension, in any case."""
    return PurePosixPath(urlsplit(url).path).suffix.lower() in AUDIO_EXT


def audio_sources(html: str) -> list[str]:
    """The src of every <audio> and <source> tag, in document order."""
    return [m.group(2) for m in _SRC.finditer(html)]
