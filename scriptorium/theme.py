"""VS1 built-in theme: base CSS, a couple of components, a tiny mustache.

Deliberately minimal — a slim slice of the DiAItu design tokens, using system
fonts to stay offline. VS2 harvests the full component vocabulary into a real
theme directory.
"""

import re

# Vertical rhythm is bottom-only so heights are additive (no margin collapse);
# `.unit{display:flow-root}` contains child margins so a unit's measured
# height equals its contribution to the page. Measure and emit share this CSS.
BASE_CSS = """
:root {
  --slate-900:#0f172a; --slate-700:#334155; --slate-600:#475569;
  --slate-400:#94a3b8; --slate-200:#e2e8f0; --slate-50:#f8fafc;
  --amber:#b45309; --emerald:#047857; --rose:#be123c; --accent:#2563eb;
}
html, body, main { margin:0; padding:0; }
body {
  font-family: system-ui, sans-serif; font-size:10.5pt; line-height:1.55;
  color:var(--slate-900);
  -webkit-print-color-adjust:exact; print-color-adjust:exact;
}
p, ul, ol, table, blockquote, pre, figure { margin:0 0 3mm 0; }
h1 { font-size:26pt; font-weight:800; line-height:1.1; margin:0 0 4mm 0; }
h2 { font-size:18pt; font-weight:800; line-height:1.15; margin:5mm 0 3mm 0; }
h3 { font-size:13pt; font-weight:700; line-height:1.25; margin:4mm 0 2mm 0; }
img { max-width:100%; }
ul, ol { padding-left:6mm; }
table { border-collapse:collapse; width:100%; font-size:9.5pt; }
th, td { border:1px solid var(--slate-200); padding:1.5mm 2.5mm; text-align:left; }
th { background:var(--slate-50); }

.unit { display:flow-root; margin:0 0 4mm 0; }
.unit > *:last-child { margin-bottom:0; }

.keep { display:flow-root; }
.two-col { columns:2; column-gap:8mm; }

.finding-card {
  display:flex; gap:4mm; align-items:flex-start;
  padding:4mm 5mm; border-radius:8px; background:#fff;
  border:1px solid var(--slate-200); border-left:4px solid var(--slate-400);
}
.finding-card.amber   { border-left-color:var(--amber); }
.finding-card.emerald { border-left-color:var(--emerald); }
.finding-card.rose    { border-left-color:var(--rose); }
.finding-card.accent  { border-left-color:var(--accent); }
.finding-card .x {
  width:9mm; height:9mm; border-radius:50%; flex-shrink:0;
  display:flex; align-items:center; justify-content:center;
  font-weight:700; font-size:12pt; background:var(--slate-200);
  color:var(--slate-700);
}
.finding-card.amber   .x { background:#fde68a; color:var(--amber); }
.finding-card.emerald .x { background:#a7f3d0; color:var(--emerald); }
.finding-card.rose    .x { background:#fecdd3; color:var(--rose); }
.finding-card .name   { font-weight:700; font-size:10pt; display:block; margin-bottom:1mm; }
.finding-card .reason { font-size:9pt; color:var(--slate-600); line-height:1.45; }
"""

# Component templates (dumb mustache over HTML). {{content}} is rendered body.
COMPONENTS = {
    "finding-card": (
        '<div class="finding-card {{variant}}">'
        '<div class="x">{{icon}}</div>'
        '<div><span class="name">{{title}}</span>'
        '<span class="reason">{{content}}</span></div>'
        "</div>"
    ),
}

_HOLE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render_template(name: str, props: dict) -> str:
    tpl = COMPONENTS[name]
    return _HOLE.sub(lambda m: str(props.get(m.group(1), "")), tpl)


def is_component(name: str) -> bool:
    return name in COMPONENTS
