"""The document model — for VS1, a flat list of atomic units.

An atomic unit is the granularity galley packs at: a paragraph, heading, list,
table, figure, or themed component. In VS1 units are never split internally
(prose line-splitting arrives in a later slice), so the observable effect of
`keep_together` is at the boundary between adjacent units: several paragraphs
are separate units and flow across pages, but a `::: keep` wrapping them is one
unit that moves as a whole.
"""

from dataclasses import dataclass


@dataclass
class Unit:
    html: str = ""
    keep_together: bool = False
    break_before: bool = False
    is_break: bool = False  # a bare `::: newpage` / `\newpage`
    name: str = "block"  # component name or "block"/"prose"
    height_mm: float = 0.0  # filled by galley.measure
