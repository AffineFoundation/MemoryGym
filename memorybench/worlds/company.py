"""Company financials world template.

Entities: Companies with 10 possible numeric attributes.
Names: 30 prefixes × 20 suffixes = 600 unique companies.
Sectors: 12 industry categories.
Document styles: 4 narrative styles (~250 tokens each).
"""

from __future__ import annotations

from random import Random
from typing import Any

from memorybench.worlds.base import AttrDef, EntitySpec, WorldTemplate

_PREFIXES = [
    "Apex", "Nexus", "Vertex", "Quantum", "Pinnacle", "Atlas", "Zenith",
    "Helix", "Prism", "Nova", "Vortex", "Stratos", "Orion", "Titan",
    "Cobalt", "Onyx", "Argon", "Cipher", "Synth", "Vector",
    "Flux", "Aether", "Nimbus", "Ember", "Photon", "Pulse",
    "Eclipse", "Ionic", "Lumen", "Radiant",
]

_SUFFIXES = [
    "Corp", "Systems", "Industries", "Labs", "Holdings", "Group",
    "Tech", "Solutions", "Dynamics", "Analytics", "Networks",
    "Ventures", "Digital", "Robotics", "Sciences", "Energy",
    "Medical", "Financial", "Materials", "Aerospace",
]

_SECTORS = [
    "Technology", "Healthcare", "Energy", "Finance", "Manufacturing",
    "Aerospace", "Telecom", "Biotech", "Logistics", "Consumer Goods",
    "Mining", "Agriculture",
]

_ATTR_DEFS = [
    AttrDef("revenue_m", "float", 10, 50000, "$M", "Revenue"),
    AttrDef("profit_margin_pct", "float", -15, 40, "%", "Profit margin",
            agg_ops=("average",)),
    AttrDef("employees", "int", 50, 200000, "", "Employees"),
    AttrDef("market_cap_m", "float", 50, 500000, "$M", "Market cap"),
    AttrDef("debt_ratio_pct", "float", 0, 150, "%", "Debt ratio",
            agg_ops=("average",)),
    AttrDef("rd_spend_pct", "float", 0, 30, "%", "R&D spending",
            agg_ops=("average",)),
    AttrDef("customer_count", "int", 100, 5000000, "", "Customers"),
    AttrDef("patent_count", "int", 0, 20000, "", "Patents"),
    AttrDef("offices", "int", 1, 300, "", "Offices"),
    AttrDef("founded_year", "int", 1950, 2023, "", "Founded"),
]

_Q_TEXTS: dict[str, list[str]] = {
    "revenue_m": [
        "What is {name}'s annual revenue?",
        "How much revenue does {name} generate?",
        "What are {name}'s total revenues in millions?",
        "Report {name}'s revenue figure.",
    ],
    "profit_margin_pct": [
        "What is {name}'s profit margin?",
        "What profit margin does {name} maintain?",
        "How profitable is {name} in terms of margin percentage?",
    ],
    "employees": [
        "How many employees does {name} have?",
        "What is {name}'s total headcount?",
        "How large is {name}'s workforce?",
    ],
    "market_cap_m": [
        "What is {name}'s market capitalization?",
        "How much is {name} valued at in the market?",
        "What is the market cap of {name}?",
    ],
    "debt_ratio_pct": [
        "What is {name}'s debt-to-equity ratio?",
        "How leveraged is {name}?",
        "What debt ratio does {name} carry?",
    ],
    "rd_spend_pct": [
        "What percentage of revenue does {name} spend on R&D?",
        "How much does {name} invest in research and development?",
        "What is {name}'s R&D expenditure as a share of revenue?",
    ],
    "customer_count": [
        "How many customers does {name} serve?",
        "What is {name}'s customer base size?",
        "How many active customers does {name} have?",
    ],
    "patent_count": [
        "How many patents does {name} hold?",
        "What is {name}'s patent portfolio size?",
        "How many active patents are registered to {name}?",
    ],
    "offices": [
        "How many offices does {name} operate?",
        "In how many locations does {name} have offices?",
        "What is {name}'s global office count?",
    ],
    "founded_year": [
        "When was {name} founded?",
        "In what year was {name} established?",
        "What year did {name} start operations?",
    ],
}


def _fmt(attr: str, val: Any) -> str:
    """Format an attribute value for human-readable display."""
    if attr in ("revenue_m", "market_cap_m"):
        return f"${val:,.1f}M"
    if attr in ("profit_margin_pct", "debt_ratio_pct", "rd_spend_pct"):
        return f"{val:.1f}%"
    if attr in ("employees", "customer_count", "patent_count"):
        return f"{val:,}"
    return str(val)


class CompanyWorld(WorldTemplate):
    """Company financials — 600 names × 10 attrs × 12 sectors."""

    @property
    def name(self) -> str:
        return "company"

    @property
    def all_attr_defs(self) -> list[AttrDef]:
        return list(_ATTR_DEFS)

    @property
    def all_categories(self) -> list[str]:
        return list(_SECTORS)

    @property
    def entity_word(self) -> str:
        return "company"

    def _generate_names(self, rng: Random, n: int) -> list[str]:
        pool = [(p, s) for p in _PREFIXES for s in _SUFFIXES]
        selected = rng.sample(pool, min(n, len(pool)))
        return [f"{p} {s}" for p, s in selected]

    def generate_entity(self, rng: Random, name: str, category: str,
                        active_attrs: list[str]) -> EntitySpec:
        attrs: dict[str, Any] = {}
        for adef in _ATTR_DEFS:
            if adef.name not in active_attrs:
                continue
            if adef.dtype == "int":
                attrs[adef.name] = rng.randint(
                    int(adef.min_val), int(adef.max_val))
            else:
                attrs[adef.name] = round(
                    rng.uniform(adef.min_val, adef.max_val), 2)
        return EntitySpec(name=name, category=category, attrs=attrs)

    def _format_value(self, attr: str, val: Any) -> str:
        return _fmt(attr, val)

    def render_document(self, entity: EntitySpec,
                        active_attrs: list[str], rng: Random) -> str:
        style = rng.choice(["earnings", "analyst", "profile", "news"])
        header = {
            "earnings": (f"QUARTERLY EARNINGS DISCLOSURE — {entity.name}\n"
                         f"Sector: {entity.category}\n"),
            "analyst": (f"ANALYST COVERAGE REPORT — {entity.name}\n"
                        f"Industry: {entity.category}\n"),
            "profile": (f"COMPANY PROFILE — {entity.name}\n"
                        f"Category: {entity.category}\n"),
            "news": (f"MARKET INTELLIGENCE BRIEF — {entity.name}\n"
                     f"Segment: {entity.category}\n"),
        }[style]
        return header + self._compact_document(entity, active_attrs)

    def render_correction(self, entity: EntitySpec, attr: str,
                          old_val: Any, new_val: Any) -> str:
        label = self.attr_label(attr)
        return (
            f"CORRECTION NOTICE: {entity.name}'s {label} has been revised "
            f"from {_fmt(attr, old_val)} to {_fmt(attr, new_val)} "
            f"following an internal audit."
        )

    def _q_text(self, attr: str, name: str,
                rng: Random | None = None) -> str:
        templates = _Q_TEXTS.get(attr, [f"What is {{name}}'s {attr}?"])
        tmpl = rng.choice(templates) if rng else templates[0]
        return tmpl.format(name=name)
