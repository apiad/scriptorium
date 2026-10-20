import functools
import http.server
import shutil
import threading
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "html-book"


def build_example(dest: Path, replace: tuple[str, str] | None = None) -> Path:
    """Copy the example book to `dest`, optionally change a word, and build its
    web output. Returns the site directory."""
    from scriptorium.cli import main

    shutil.copytree(EXAMPLE, dest, ignore=shutil.ignore_patterns("web", "*.pdf"))
    if replace:
        for md in dest.glob("*.md"):
            md.write_text(md.read_text(encoding="utf-8").replace(*replace), encoding="utf-8")
    assert main(["render", str(dest / "scriptorium.yaml"), "--only", "web"]) == 0
    return dest / "web"


@pytest.fixture(scope="session")
def site(tmp_path_factory):
    return build_example(tmp_path_factory.mktemp("book") / "book")


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="session")
def serve():
    """serve(directory) -> base URL of a local server for that directory."""
    servers = []

    def start(directory: Path) -> str:
        handler = functools.partial(_Quiet, directory=str(directory))
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return f"http://127.0.0.1:{srv.server_address[1]}/"

    yield start
    for s in servers:
        s.shutdown()
