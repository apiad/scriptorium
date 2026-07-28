"""Parse Markdown + `:::` components + code fences into a flat list of Units.

Base: CommonMark + tables (markdown-it-py). Components and page masters come
from the active theme. Code fences carry directives (run / export= / name=,
see fence.py): a run block executes in a subshell and its stdout is spliced
back — as monospace (Quarto `{lang}`) or as re-parsed markdown (native `{run}`).
An optional ExecEnv enables execution; without it, code is shown, not run.
"""

import re
from html import escape

import yaml
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin

from .fence import EXT, parse_fence
from .highlight import highlight
from .mathrender import render_display, render_inline
from .model import Unit
from .theme import Theme, load_theme, render_template

_md = MarkdownIt("commonmark").enable("table").use(dollarmath_plugin, allow_space=True, double_inline=True)
_md.renderer.rules["math_inline"] = lambda t, i, o, e: render_inline(t[i].content)
_md.renderer.rules["math_inline_double"] = lambda t, i, o, e: render_display(t[i].content)
_md.renderer.rules["math_block"] = lambda t, i, o, e: render_display(t[i].content)
_md.renderer.rules["math_block_label"] = lambda t, i, o, e: render_display(t[i].content)

_TRANSPARENT = {"tinted", "group"}
_FENCE = re.compile(r"^(:{3,})\s*(.*?)\s*$")
_CODEFENCE = re.compile(r"^(`{3,}|~{3,})(.*)$")
_ATTR = re.compile(r"""(\#[\w-]+)|(\.[\w-]+)|(\w[\w-]*)=("[^"]*"|'[^']*'|\S+)""")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")


def _parse_info(info: str):
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
        if m and m.group(2):
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


def _split_md(text: str):
    """Split an md region into ('prose', text) and ('code', info, body), keeping
    fenced code blocks whole (they may contain blank lines)."""
    lines = text.split("\n")
    items, buf, i = [], [], 0

    def flush():
        for b in re.split(r"\n\s*\n", "\n".join(buf)):
            if b.strip():
                items.append(("prose", b))
        buf.clear()

    while i < len(lines):
        m = _CODEFENCE.match(lines[i])
        if m:
            flush()
            fence, info = m.group(1), m.group(2)
            close = re.compile(rf"^{re.escape(fence[0])}{{{len(fence)},}}\s*$")
            j, body = i + 1, []
            while j < len(lines) and not close.match(lines[j]):
                body.append(lines[j])
                j += 1
            items.append(("code", info, "\n".join(body)))
            i = j + 1
        else:
            buf.append(lines[i])
            i += 1
    flush()
    return items


def _unwrap_p(html: str) -> str:
    return re.sub(r"^<p>(.*)</p>\s*$", r"\1", html.strip(), flags=re.S)


def _render_fragment(src: str, theme: Theme) -> str:
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


def _tangle_target(f, stem: str) -> str:
    return f.export or f"{stem}.{EXT.get(f.lang, 'txt')}"


def _code_units(info, body, theme, env, cursor, stem) -> list[Unit]:
    f = parse_fence(info)
    units: list[Unit] = []
    # advance the per-file line cursor for any block that tangles (even if hidden)
    label = ""
    if f.tangles:
        path = _tangle_target(f, stem)
        n = body.count("\n") + 1 if body else 0
        start = cursor.get(path, 0) + 1
        end = start + n - 1
        cursor[path] = end
        label = f'<span class="code-file">{escape(path)} · L{start}–{end}</span>'
    if f.echo:
        block = f'<span class="code-src">{highlight(body, f.lang)}</span>'
        units.append(Unit(html=f'<div class="codeblock">{label}{block}</div>', name="code",
                          splittable=True, code_src=body, code_lang=f.lang, code_label=label))
    if f.run and env is not None:
        out = env.run(body, f.lang)
        if out.strip():
            if f.output_mode == "code":
                units.append(Unit(html=f'<pre class="output">{escape(out)}</pre>', name="output"))
            else:  # asis: stdout is raw markdown, re-parsed
                units.extend(parse(out, theme, env))
    return units


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


def parse(src: str, theme: Theme | None = None, env=None) -> list[Unit]:
    theme = theme or load_theme()
    meta = frontmatter(src)
    stem = str(meta.get("stem", "doc"))
    cursor: dict[str, int] = {}
    units: list[Unit] = []
    for node in _split_nodes(_body(src)):
        if node[0] == "md":
            for kind, *rest in _split_md(node[1]):
                if kind == "code":
                    units.extend(_code_units(rest[0], rest[1], theme, env, cursor, stem))
                    continue
                block = rest[0]
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
            if name in _TRANSPARENT:
                units.extend(parse(inner, theme, env))
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
