"""Parse Markdown + `:::` fenced-div components into a flat list of Units.

VS1 scope: CommonMark + tables via markdown-it-py; `:::` containers for
`keep` / `newpage` / a themed component (`finding-card`) / generic class divs.
Prose runs split at blank lines into per-block units. Nested containers and
`::: slot` are deferred to a later slice.
"""

import re

from markdown_it import MarkdownIt

from .model import Unit
from .theme import is_component, render_template

_md = MarkdownIt("commonmark").enable("table")

_FENCE = re.compile(r"^(:{3,})\s*(.*?)\s*$")
_ATTR = re.compile(r"""(\#[\w-]+)|(\.[\w-]+)|(\w[\w-]*)=("(?:[^"]*)"|'(?:[^']*)'|\S+)""")


def _parse_info(info: str):
    """Split a `:::` info string into (name, modifiers, attrs)."""
    name, mods, attrs = "", [], {}
    brace = info.find("{")
    head, tail = (info[:brace], info[brace:]) if brace >= 0 else (info, "")
    tokens = head.split()
    if tokens:
        name, mods = tokens[0], tokens[1:]
    for m in _ATTR.finditer(tail):
        if m.group(1):  # #id
            attrs["id"] = m.group(1)[1:]
        elif m.group(2):  # .class
            mods.append(m.group(2)[1:])
        elif m.group(3):  # key=val
            val = m.group(4)
            if val and val[0] in "\"'":
                val = val[1:-1]
            attrs[m.group(3)] = val
    return name, mods, attrs


def _split_nodes(src: str):
    """Top-level scan into ('md', text) and ('container', name, mods, attrs, inner)."""
    lines = src.split("\n")
    nodes, buf, i = [], [], 0
    while i < len(lines):
        m = _FENCE.match(lines[i])
        if m and m.group(2):  # opening fence (has an info string)
            if buf:
                nodes.append(("md", "\n".join(buf)))
                buf = []
            fence, info = m.group(1), m.group(2)
            name, mods, attrs = _parse_info(info)
            depth, j, inner = 1, i + 1, []
            while j < len(lines):
                m2 = _FENCE.match(lines[j])
                if m2:
                    if not m2.group(2) and len(m2.group(1)) >= len(fence):
                        depth -= 1
                        if depth == 0:
                            break
                    elif m2.group(2):
                        depth += 1
                inner.append(lines[j])
                j += 1
            nodes.append(("container", name, mods, attrs, "\n".join(inner)))
            i = j + 1
        else:
            buf.append(lines[i])
            i += 1
    if buf:
        nodes.append(("md", "\n".join(buf)))
    return nodes


def _strip_frontmatter(src: str) -> str:
    if src.startswith("---\n"):
        end = src.find("\n---", 3)
        if end >= 0:
            nl = src.find("\n", end + 1)
            return src[nl + 1 :] if nl >= 0 else ""
    return src


def parse(src: str) -> list[Unit]:
    src = _strip_frontmatter(src)
    units: list[Unit] = []
    for node in _split_nodes(src):
        if node[0] == "md":
            for block in re.split(r"\n\s*\n", node[1]):
                if not block.strip():
                    continue
                if block.strip() == r"\newpage":
                    units.append(Unit(is_break=True, name="newpage"))
                    continue
                units.append(Unit(html=_md.render(block), keep_together=False, name="prose"))
        else:
            _, name, mods, attrs, inner = node
            if name == "newpage":
                units.append(Unit(is_break=True, name="newpage"))
            elif name == "keep":
                units.append(
                    Unit(html=f'<div class="keep">{_md.render(inner)}</div>',
                         keep_together=True, name="keep")
                )
            elif is_component(name):
                props = dict(attrs)
                props.setdefault("variant", " ".join(mods))
                props["content"] = _md.render(inner).strip()
                # unwrap a lone <p> so inline reason text stays inline
                props["content"] = re.sub(r"^<p>(.*)</p>\s*$", r"\1", props["content"], flags=re.S)
                units.append(Unit(html=render_template(name, props),
                                  keep_together=True, name=name))
            else:  # generic class div (Level 0/1)
                classes = " ".join(([name] if name else []) + mods)
                units.append(
                    Unit(html=f'<div class="{classes}">{_md.render(inner)}</div>',
                         keep_together=bool(name), name=name or "div")
                )
    return units
