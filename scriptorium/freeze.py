"""Freeze cache: content-hash of (interpreter + source) -> captured stdout.

Unchanged code blocks never re-run. VS3 uses a JSON file next to the document;
the design (§5.3) calls for beaver — swap the backend here when hardening,
the interface (get/set) stays the same.
"""

import hashlib
import json
from pathlib import Path


class Freeze:
    def __init__(self, path: Path | None):
        self.path = path
        self._data = {}
        if path and path.exists():
            try:
                self._data = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    @staticmethod
    def key(interpreter: str, source: str) -> str:
        return hashlib.sha256(f"{interpreter}\0{source}".encode()).hexdigest()

    def get(self, key: str):
        return self._data.get(key)

    def set(self, key: str, value: str):
        self._data[key] = value
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data))
