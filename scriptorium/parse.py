"""Parse Markdown + `:::` fenced-div components into a flat list of Units.

Base: CommonMark + tables (markdown-it-py). Components and page masters come
from the active theme; `:::` containers render recursively (a grid can contain
tiles). A component whose theme hint carries a `master` becomes a full-page
unit (cover, section opener). Frontmatter feeds master/stamp metadata.
"""

import re

import yaml
from markdown_it import MarkdownIt

from .model import Unit
from .theme import Theme, load_theme, render_template

_md = MarkdownIt("commonmark").enable("table")

# wrappers that carry no box of their own: their children become top-level units
_TRANSPARENT = {"tinted", "group"}

_FENCE = re.compile(r"^(:{3,})\s*(.*?)\s*$")
_ATTR = re.compile(r"""(\#[\w-]+)|(\.[\w-]+)|(\w[\w-]*)=("[^"]*"|'[^']*'|\S+)""")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")


def _parse_info(info: str):
    """Split a `:::` info string into (name, modifiers, attrs)."""
    name, mods, attrs = "", [], {}
    brace = info.find("{")
    head, tail = (info[:brace], info[brace:]) if brace >= 0 else (info, "")
    tokens = head.split()
    if tokens:
        name, mods = tokens[0], tokens[1:]
    for m in _ATTR.finditer(tail):
        if m.group(1):
            attrs["id"] = m.group(1)[1:]
        elif m.group(2):
            mods.append(m.group(2)[1:])
        elif m.group(3):
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
        if m and m.group(2):  # opening fence (has info)
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


def _unwrap_p(html: str) -> str:
    return re.sub(r"^<p>(.*)</p>\s*$", r"\1", html.strip(), flags=re.S)


def _render_fragment(src: str, theme: Theme) -> str:
    """Recursively render a chunk (markdown + nested components) to HTML."""
    parts = []
    for node in _split_nodes(src):
        if node[0] == "md":
            if node[1].strip():
                parts.append(_md.render(node[1]))
        else:
            _, name, mods, attrs, inner = node
            parts.append(_component_html(name, mods, attrs, inner, theme))
    return "".join(parts)


def _component_html(name, mods, attrs, inner, theme: Theme) -> str:
    if name == "keep":
        return f'<div class="keep">{_render_fragment(inner, theme)}</div>'
    if theme.is_component(name):
        props = dict(attrs)
        props.setdefault("variant", " ".join(mods))
        props["content"] = _unwrap_p(_render_fragment(inner, theme))
        return theme.render(name, props)
    classes = " ".join(([name] if name else []) + mods)
    return f'<div class="{classes}">{_render_fragment(inner, theme)}</div>'


def frontmatter(src: str) -> dict:
    if src.startswith("---\n"):
        end = src.find("\n---", 3)
        if end >= 0:
            try:
                return yaml.safe_load(src[4:end]) or {}
            except yaml.YAMLError:
                return {}
    return {}


def _body(src: str) -> str:
    if src.startswith("---\n"):
        end = src.find("\n---", 3)
        if end >= 0:
            nl = src.find("\n", end + 1)
            return src[nl + 1 :] if nl >= 0 else ""
    return src


def parse(src: str, theme: Theme | None = None) -> list[Unit]:
    theme = theme or load_theme()
    meta = frontmatter(src)
    units: list[Unit] = []
    for node in _split_nodes(_body(src)):
        if node[0] == "md":
            for block in re.split(r"\n\s*\n", node[1]):
                if not block.strip():
                    continue
                if block.strip() == r"\newpage":
                    units.append(Unit(is_break=True, name="newpage"))
                    continue
                hm = _HEADING.match(block)
                units.append(
                    Unit(html=_md.render(block), keep_together=False, name="prose",
                         heading=hm.group(1) if hm else None)
                )
        else:
            _, name, mods, attrs, inner = node
            if name == "newpage":
                units.append(Unit(is_break=True, name="newpage"))
                continue
            if name in _TRANSPARENT:  # unwrap: children become top-level units
                units.extend(parse(inner, theme))
                continue
            master = theme.master_of(name)
            if master:
                props = dict(attrs)
                props.setdefault("variant", " ".join(mods))
                for k in ("title", "org", "org_sub", "date", "edition", "addr"):
                    props.setdefault(k, str(meta.get(k, "")))
                props["content"] = _unwrap_p(_render_fragment(inner, theme))
                html = render_template(theme.master_template(master), props)
                units.append(Unit(html=html, full_page=True, master=master, name=name))
            else:
                keep = name == "keep" or theme.hint(name, "keep_together", bool(name))
                units.append(
                    Unit(html=_component_html(name, mods, attrs, inner, theme),
                         keep_together=bool(keep), name=name or "div")
                )
    return units
