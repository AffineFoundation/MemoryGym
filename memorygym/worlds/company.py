"""Company financials world template.

Entities: Companies with 10 possible numeric attributes.
Names: 30 prefixes × 20 suffixes = 600 unique companies.
Sectors: 12 industry categories.
Document styles: 4 narrative styles (~250 tokens each).
"""

from __future__ import annotations

from random import Random
from typing import Any

from memorygym.worlds.base import (
    AttrDef, EntitySpec, SentenceTemplate, WorldTemplate, _possessive,
)

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


_SENTENCE_TMPLS: dict[str, list[tuple[str, str]]] = {
    "revenue_m": [
        ("reported annual revenue of {val}", "none"),
        ("saw revenue climb from {distractor} to {val} over the fiscal year",
         "temporal"),
        ("generated {val} in total revenue, compared to {other_name}'s "
         "{other_val}", "comparative"),
    ],
    "profit_margin_pct": [
        ("maintains a profit margin of {val}", "none"),
        ("improved its margin from {distractor} to {val} year-over-year",
         "temporal"),
        ("reported {val} net margin, though operating margin stands at "
         "{distractor}", "qualified"),
    ],
    "employees": [
        ("employs {val} staff members across its global operations", "none"),
        ("expanded from {distractor} to {val} employees during the period",
         "temporal"),
        ("maintains a workforce of {val}, though only {distractor} are "
         "full-time", "qualified"),
    ],
    "market_cap_m": [
        ("carries a market capitalization of {val}", "none"),
        ("market cap rose from {distractor} to {val} this quarter",
         "temporal"),
        ("valued at {val}, outpacing {other_name} at {other_val}",
         "comparative"),
    ],
    "debt_ratio_pct": [
        ("holds a debt-to-equity ratio of {val}", "none"),
        ("saw its debt ratio shift from {distractor} to {val}", "temporal"),
        ("carries {val} total leverage, with {distractor} in short-term "
         "obligations", "qualified"),
    ],
    "rd_spend_pct": [
        ("allocates {val} of revenue to R&D", "none"),
        ("increased R&D spending from {distractor} to {val}", "temporal"),
        ("invests {val} in R&D, compared to {other_name}'s {other_val}",
         "comparative"),
    ],
    "customer_count": [
        ("serves {val} customers worldwide", "none"),
        ("grew its customer base from {distractor} to {val}", "temporal"),
        ("counts {val} total customers, of which {distractor} are "
         "enterprise accounts", "qualified"),
    ],
    "patent_count": [
        ("holds {val} active patents in its portfolio", "none"),
        ("expanded its patent portfolio from {distractor} to {val}",
         "temporal"),
        ("owns {val} patents, versus {other_name}'s {other_val}",
         "comparative"),
    ],
    "offices": [
        ("operates {val} offices globally", "none"),
        ("grew from {distractor} to {val} office locations", "temporal"),
        ("has {val} offices, though only {distractor} are fully staffed",
         "qualified"),
    ],
    "founded_year": [
        ("was established in {val}", "none"),
        ("traces its origins to {val}, having been reorganized from a "
         "{distractor} predecessor", "temporal"),
        ("founded in {val}, predating {other_name}", "comparative"),
    ],
}

_RATIO_PAIRS = [
    ("revenue_m", "employees", "revenue per employee in $M"),
    ("market_cap_m", "revenue_m", "market cap to revenue ratio"),
    ("patent_count", "employees", "patents per thousand employees"),
]


def _fmt(attr: str, val: Any) -> str:
    """Format an attribute value for human-readable display."""
    if attr in ("revenue_m", "market_cap_m"):
        return f"${val:,.1f}M"
    if attr in ("profit_margin_pct", "debt_ratio_pct", "rd_spend_pct"):
        return f"{val:.2f}%"
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

    def _sentence_templates(self):
        return {attr: [SentenceTemplate(t, attr, d) for t, d in tmpls]
                for attr, tmpls in _SENTENCE_TMPLS.items()}

    def _ratio_pairs(self):
        return list(_RATIO_PAIRS)

    def render_document(self, entity: EntitySpec,
                        active_attrs: list[str], rng: Random,
                        other_entities: list[EntitySpec] | None = None
                        ) -> str:
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
        return header + self._render_body(
            entity, active_attrs, rng, other_entities)

    def render_correction(self, entity: EntitySpec, attr: str,
                          old_val: Any, new_val: Any) -> str:
        label = self.attr_label(attr)
        return (
            f"CORRECTION NOTICE: {_possessive(entity.name)} {label} has been "
            f"revised from {_fmt(attr, old_val)} to {_fmt(attr, new_val)} "
            f"following an internal audit."
        )

    def _q_text(self, attr: str, name: str,
                rng: Random | None = None) -> str:
        templates = _Q_TEXTS.get(attr, [f"What is {{name}}'s {attr}?"])
        tmpl = rng.choice(templates) if rng else templates[0]
        return tmpl.format(name=name)
