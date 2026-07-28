"""Theme loading — directory-backed design systems with inheritance.

A theme is a directory:

    themes/<name>/
      theme.yml          metadata, `extends:`, vars, page geometry, hints, masters
      styles.css         base + component CSS (may @font-face vendored fonts)
      components/*.html   mustache templates ({{prop}} / {{content}})
      masters/*.html      full-page / furniture templates
      assets/…            fonts, images referenced by styles.css (relative urls)

A theme may `extends:` a parent (which may extend its own parent). The chain is
merged base-first: CSS concatenated (child last, so it overrides via the
cascade), components/masters/hints/vars/page merged with the child winning.
Relative `url(assets/…)` in each theme's CSS is rewritten to an absolute
`file://` URL against *that* theme's directory, so vendored fonts resolve
regardless of the document's location.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

THEMES_DIR = Path(__file__).resolve().parent.parent / "themes"

_HOLE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_URL = re.compile(r"url\(\s*(['\"]?)([^)'\"]+)\1\s*\)")


def render_template(tpl: str, props: dict) -> str:
    return _HOLE.sub(lambda m: str(props.get(m.group(1), "")), tpl)


def _rewrite_urls(css: str, root: Path) -> str:
    """Make relative asset URLs absolute against the theme dir (fonts, images)."""
    def sub(m):
        url = m.group(2).strip()
        if url.startswith(("http:", "https:", "data:", "file:", "/")):
            return m.group(0)
        return f"url('file://{(root / url).resolve()}')"
    return _URL.sub(sub, css)


@dataclass
class Theme:
    name: str
    css: str
    meta: dict = field(default_factory=dict)
    components: dict = field(default_factory=dict)  # name -> template html
    masters: dict = field(default_factory=dict)  # name -> template html
    hints: dict = field(default_factory=dict)  # name -> {keep_together, master, ...}
    vars: dict = field(default_factory=dict)  # theme var defaults

    def is_component(self, name: str) -> bool:
        return name in self.components

    def render(self, name: str, props: dict) -> str:
        return render_template(self.components[name], props)

    def hint(self, name: str, key: str, default=None):
        return self.hints.get(name, {}).get(key, default)

    def master_of(self, name: str) -> str | None:
        return self.hint(name, "master")

    def master_template(self, master: str) -> str:
        return self.masters.get(master, "{{content}}")

    def master_classes(self, master: str) -> str:
        return self.meta.get("masters", {}).get(master, {}).get("classes", "")

    def master_furniture(self, master: str) -> str:
        return self.meta.get("masters", {}).get(master, {}).get("furniture", "none")


def _read_dir(path: Path) -> dict:
    out = {}
    if path.is_dir():
        for f in path.glob("*.html"):
            out[f.stem] = f.read_text(encoding="utf-8").strip()
    return out


def _chain(name: str) -> list[Path]:
    """Resolve the extends-chain, base-first, with a cycle guard."""
    chain, seen, cur = [], set(), name
    while cur and cur not in seen:
        seen.add(cur)
        root = THEMES_DIR / cur
        meta = yaml.safe_load((root / "theme.yml").read_text(encoding="utf-8")) or {}
        chain.append((root, meta))
        cur = meta.get("extends")
    chain.reverse()
    return chain


def load_theme(name: str = "report") -> Theme:
    css_parts, components, masters, hints, vars = [], {}, {}, {}, {}
    meta: dict = {}
    for root, m in _chain(name):
        css_file = root / "styles.css"
        if css_file.exists():
            css_parts.append(_rewrite_urls(css_file.read_text(encoding="utf-8"), root))
        components.update(_read_dir(root / "components"))
        masters.update(_read_dir(root / "masters"))
        hints.update(m.get("components", {}) or {})
        vars.update(m.get("vars", {}) or {})
        for k, v in m.items():
            if k in ("masters", "page") and isinstance(v, dict):
                meta.setdefault(k, {}).update(v)
            elif k not in ("components", "vars", "extends"):
                meta[k] = v
    meta["masters"] = meta.get("masters", {})
    return Theme(name=name, css="\n".join(css_parts), meta=meta,
                 components=components, masters=masters, hints=hints, vars=vars)
