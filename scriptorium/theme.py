"""Theme loading — a directory-backed design system.

A theme is a directory:

    themes/<name>/
      theme.yml          metadata, palette, page geometry, component hints, masters
      styles.css         base + component CSS (may @font-face vendored fonts)
      components/*.html   mustache templates ({{prop}} / {{content}})
      masters/*.html      full-page / furniture templates ({{content}} / tokens)

Component hints (keep_together, master, splittable) live in theme.yml so the
galley engine can consult them without parsing HTML. `master` marks a component
as full-page (cover, section opener) rendered through a master template.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

THEMES_DIR = Path(__file__).resolve().parent.parent / "themes"

_HOLE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render_template(tpl: str, props: dict) -> str:
    return _HOLE.sub(lambda m: str(props.get(m.group(1), "")), tpl)


@dataclass
class Theme:
    name: str
    css: str
    meta: dict = field(default_factory=dict)
    components: dict = field(default_factory=dict)  # name -> template html
    masters: dict = field(default_factory=dict)  # name -> template html
    hints: dict = field(default_factory=dict)  # name -> {keep_together, master, ...}

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


def load_theme(name: str = "marketing") -> Theme:
    root = THEMES_DIR / name
    meta = yaml.safe_load((root / "theme.yml").read_text(encoding="utf-8")) or {}
    css = (root / "styles.css").read_text(encoding="utf-8")
    return Theme(
        name=name,
        css=css,
        meta=meta,
        components=_read_dir(root / "components"),
        masters=_read_dir(root / "masters"),
        hints=meta.get("components", {}) or {},
    )
