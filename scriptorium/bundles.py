"""Display bundles: what a python block's display() prints, and where it lands.

The driver in execute.py prints each displayed object as JSON between
BUNDLE_START and BUNDLE_END: {"data": {mime: str}, "metadata": {...}}, the
shape of IPython's rich display, bytes as base64.
"""

import json
import re

from .execute import BUNDLE_END, BUNDLE_START

_BUNDLE = re.compile(re.escape(BUNDLE_START) + r"(.*?)" + re.escape(BUNDLE_END), re.S)


def split(stdout: str) -> list:
    """The block's output in order: text runs as str, bundles as dicts."""
    parts, pos = [], 0
    for m in _BUNDLE.finditer(stdout):
        if m.start() > pos:
            parts.append(stdout[pos:m.start()])
        parts.append(json.loads(m.group(1)))
        pos = m.end()
    if pos < len(stdout):
        parts.append(stdout[pos:])
    return parts
