"""Company financials world template.

Entities: Companies with 23 possible attributes (19 numeric + text + enum + date + list_float).
Names: 30 prefixes × 20 suffixes = 600 unique companies.
Sectors: 12 industry categories.
Document styles: 4 narrative styles (~250 tokens each).
"""

from __future__ import annotations

from random import Random
from typing import Any

from memorygym.worlds.base import (
    AttrDef, EntitySpec, SentenceTemplate, WorldTemplate,
    _possessive,
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

_BUSINESS_SUMMARIES = [
    "specializes in cloud infrastructure and enterprise SaaS platforms",
    "develops AI-powered automation tools for manufacturing workflows",
    "provides cybersecurity solutions for financial institutions",
    "builds next-generation semiconductor fabrication equipment",
    "operates a global logistics network for e-commerce fulfillment",
    "manufactures precision medical devices for minimally invasive surgery",
    "offers renewable energy storage and grid management systems",
    "creates advanced materials for aerospace and defense applications",
    "delivers data analytics and business intelligence platforms",
    "develops autonomous vehicle navigation and sensor fusion technology",
    "provides telemedicine platforms connecting patients with specialists",
    "builds quantum computing hardware and development tools",
    "manufactures industrial robotics for warehouse automation",
    "offers blockchain-based supply chain verification services",
    "develops gene therapy delivery mechanisms for rare diseases",
    "provides satellite communications for maritime and aviation",
    "builds edge computing infrastructure for IoT deployments",
    "manufactures high-efficiency solar panels and inverters",
    "creates natural language processing tools for enterprise search",
    "develops precision agriculture technology using drone imagery",
]

_RISK_LEVELS = ["low", "moderate", "high", "critical"]

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
    # New numeric attrs
    AttrDef("gross_profit_m", "float", 5, 30000, "$M", "Gross profit"),
    AttrDef("operating_income_m", "float", -5000, 20000, "$M",
            "Operating income"),
    AttrDef("capex_m", "float", 1, 15000, "$M", "Capital expenditure"),
    AttrDef("dividend_yield_pct", "float", 0, 12, "%", "Dividend yield",
            agg_ops=("average",)),
    AttrDef("pe_ratio", "float", 5, 120, "", "P/E ratio",
            agg_ops=("average",)),
    AttrDef("inventory_turnover", "float", 1, 50, "", "Inventory turnover",
            agg_ops=("average",)),
    AttrDef("current_ratio", "float", 0.3, 5.0, "", "Current ratio",
            agg_ops=("average",)),
    AttrDef("ceo_tenure_years", "int", 1, 30, "", "CEO tenure (years)"),
    AttrDef("esg_score", "float", 0, 100, "", "ESG score",
            agg_ops=("average",)),
    # New dtype attrs
    AttrDef("business_summary", "text", label="Business summary",
            text_pool=_BUSINESS_SUMMARIES),
    AttrDef("risk_level", "enum", label="Risk level",
            choices=_RISK_LEVELS),
    AttrDef("ipo_date", "date", min_val=1980, max_val=2024,
            label="IPO date"),
    AttrDef("quarterly_revenue", "list_float", min_val=5, max_val=15000,
            label="Quarterly revenue ($M)", list_len=4),
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
    "gross_profit_m": [
        "What is {name}'s gross profit?",
        "How much gross profit does {name} report?",
    ],
    "operating_income_m": [
        "What is {name}'s operating income?",
        "How much operating income does {name} generate?",
    ],
    "capex_m": [
        "What is {name}'s capital expenditure?",
        "How much does {name} spend on capex?",
    ],
    "dividend_yield_pct": [
        "What is {name}'s dividend yield?",
        "What dividend yield does {name} offer?",
    ],
    "pe_ratio": [
        "What is {name}'s P/E ratio?",
        "What price-to-earnings ratio does {name} have?",
    ],
    "inventory_turnover": [
        "What is {name}'s inventory turnover?",
        "How many times does {name} turn over its inventory?",
    ],
    "current_ratio": [
        "What is {name}'s current ratio?",
        "What liquidity ratio does {name} maintain?",
    ],
    "ceo_tenure_years": [
        "How many years has {name}'s CEO been in the role?",
        "What is the CEO tenure at {name}?",
    ],
    "esg_score": [
        "What is {name}'s ESG score?",
        "How does {name} rate on ESG metrics?",
    ],
    "business_summary": [
        "What does {name} do?",
        "Describe {name}'s core business.",
        "What is {name}'s business focus?",
    ],
    "risk_level": [
        "What is {name}'s risk level?",
        "What risk rating does {name} carry?",
    ],
    "ipo_date": [
        "When did {name} go public?",
        "What is {name}'s IPO date?",
    ],
    "quarterly_revenue": [
        "What are {name}'s quarterly revenue figures?",
        "List {name}'s revenue for the last 4 quarters.",
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
    "gross_profit_m": [
        ("reported gross profit of {val}", "none"),
        ("grew gross profit from {distractor} to {val}", "temporal"),
    ],
    "operating_income_m": [
        ("generated operating income of {val}", "none"),
        ("saw operating income shift from {distractor} to {val}", "temporal"),
    ],
    "capex_m": [
        ("invested {val} in capital expenditure", "none"),
        ("increased capex from {distractor} to {val}", "temporal"),
    ],
    "dividend_yield_pct": [
        ("offers a dividend yield of {val}", "none"),
        ("adjusted its dividend yield from {distractor} to {val}", "temporal"),
    ],
    "pe_ratio": [
        ("trades at a P/E ratio of {val}", "none"),
        ("P/E ratio changed from {distractor} to {val}", "temporal"),
    ],
    "inventory_turnover": [
        ("achieves an inventory turnover of {val}", "none"),
    ],
    "current_ratio": [
        ("maintains a current ratio of {val}", "none"),
    ],
    "ceo_tenure_years": [
        ("has had its current CEO for {val} years", "none"),
    ],
    "esg_score": [
        ("earned an ESG score of {val}", "none"),
        ("improved its ESG score from {distractor} to {val}", "temporal"),
    ],
    "business_summary": [
        ("{val}", "none"),
    ],
    "risk_level": [
        ("is classified at {val} risk level", "none"),
    ],
    "ipo_date": [
        ("went public on {val}", "none"),
    ],
    "quarterly_revenue": [
        ("reported quarterly revenues of {val}", "none"),
    ],
}

_RATIO_PAIRS = [
    ("revenue_m", "employees", "revenue per employee in $M"),
    ("market_cap_m", "revenue_m", "market cap to revenue ratio"),
    ("patent_count", "employees", "patents per thousand employees"),
    ("gross_profit_m", "revenue_m", "gross margin ratio"),
    ("operating_income_m", "revenue_m", "operating margin ratio"),
    ("capex_m", "revenue_m", "capex to revenue ratio"),
]


def _fmt(attr: str, val: Any) -> str:
    """Format an attribute value for human-readable display."""
    if attr in ("revenue_m", "market_cap_m", "gross_profit_m",
                "operating_income_m", "capex_m"):
        return f"${val:,.1f}M" if isinstance(val, (int, float)) else str(val)
    if attr in ("profit_margin_pct", "debt_ratio_pct", "rd_spend_pct",
                "dividend_yield_pct"):
        return f"{val:.2f}%" if isinstance(val, (int, float)) else str(val)
    if attr in ("employees", "customer_count", "patent_count"):
        return f"{val:,}" if isinstance(val, (int, float)) else str(val)
    if attr == "quarterly_revenue" and isinstance(val, list):
        return ", ".join(f"${v:,.1f}M" for v in val)
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

    def _generate_list_float(self, adef, rng):
        """Seasonal pattern: strong Q4 spike, Q1 dip — sawtooth shape."""
        base = rng.uniform(adef.min_val * 0.3, adef.max_val * 0.5)
        seasonal = [0.70, 0.85, 1.00, 1.45]  # Q1-Q4: strong seasonal swing
        values = []
        for i in range(adef.list_len):
            mult = seasonal[i % 4]
            noise = rng.uniform(0.95, 1.05)
            val = max(adef.min_val, min(adef.max_val, base * mult * noise))
            values.append(round(val, 2))
        return values

    def generate_entity(self, rng: Random, name: str, category: str,
                        active_attrs: list[str]) -> EntitySpec:
        attrs: dict[str, Any] = {}
        for adef in _ATTR_DEFS:
            if adef.name not in active_attrs:
                continue
            attrs[adef.name] = self._generate_attr_value(rng, adef)
        # Constraint: employees and revenue should have realistic ratio
        # (per-employee revenue $50K - $2M)
        if "employees" in attrs and "revenue_m" in attrs:
            emp = attrs["employees"]
            rev = attrs["revenue_m"]
            per_emp = (rev * 1_000_000) / emp if emp > 0 else 0
            if per_emp < 50_000 or per_emp > 2_000_000:
                target_per_emp = rng.uniform(100_000, 800_000)
                attrs["revenue_m"] = round(emp * target_per_emp / 1_000_000, 2)
        return EntitySpec(name=name, category=category, attrs=attrs)

    def _format_value(self, attr: str, val: Any) -> str:
        return _fmt(attr, val)

    def _sentence_templates(self):
        return {attr: [SentenceTemplate(t, attr, d) for t, d in tmpls]
                for attr, tmpls in _SENTENCE_TMPLS.items()}

    def _ratio_pairs(self):
        return list(_RATIO_PAIRS)

    def _relationship_types(self):
        return [
            ("supplies_to", "is a supplier of", False),
            ("competes_with", "is a competitor of", True),
        ]

    def render_relationship(self, rel):
        if rel.relation == "supplies_to":
            return (f"{rel.source} is a key supplier to {rel.target}, "
                    f"providing components under a long-term agreement.")
        if rel.relation == "competes_with":
            return (f"{rel.source} and {rel.target} are direct competitors "
                    f"in the same market segment.")
        return super().render_relationship(rel)

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
