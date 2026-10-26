"""The HTML book and the docs output find their assets the way themes are found, so an
installed wheel (themes inside the package) works as well as a source checkout."""

from scriptorium.book import READER_DIR
from scriptorium.docs import DOCS_DIR
from scriptorium.theme import THEMES_DIR


def test_reader_and_docs_assets_live_under_the_themes_dir():
    assert READER_DIR == THEMES_DIR / "base" / "reader" and (READER_DIR / "reader.js").is_file()
    assert DOCS_DIR == THEMES_DIR / "base" / "docs" and (DOCS_DIR / "docs.css").is_file()
