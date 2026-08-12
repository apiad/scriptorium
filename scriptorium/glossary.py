"""Glossed terms and a back-of-book glossary.

A source-to-source pre-processor, like footnotes.py and citations.py and for the
same reason: parse() renders block by block, so a plugin would never see a marker
and its entry in one render call.

Definitions are opaque Markdown prose, on the same contract as a bibliography
entry: the engine sorts and links them, it never inspects them.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Entry:
    key: str
    term: str
    definition: str
    refs: int = 0


def load_entries(spec, base_dir: Path | None) -> tuple[dict[str, Entry], list[str]]:
    """`glossary:` is either a mapping or a path to a YAML file holding one.

    A path keeps a five-hundred-entry glossary out of the project file; an inline
    mapping keeps a single document from needing a second file.
    """
    if isinstance(spec, str):
        path = Path(spec)
        if base_dir is not None and not path.is_absolute():
            path = base_dir / path
        try:
            spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except OSError as exc:
            return {}, [f"glossary file {spec!r} could not be read: {exc}"]

    if not isinstance(spec, dict):
        return {}, ["`glossary:` is neither a mapping nor a path to one"]

    entries: dict[str, Entry] = {}
    warnings: list[str] = []
    for key, value in spec.items():
        if not isinstance(value, dict) or not value.get("term"):
            warnings.append(f"glossary entry {key!r} has no `term:`")
            continue
        entries[key] = Entry(key=key, term=value["term"],
                             definition=value.get("definition", ""))
    return entries, warnings
