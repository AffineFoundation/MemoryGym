"""City/municipality world template.

Entities: Cities with demographic, geographic, and quality-of-life attributes.
Names: 30 nature adjectives × 20 geographic nouns = 600 unique cities.
Regions: 8 geographic regions.
Document styles: 4 narrative styles (~250 tokens each).

Design pressures on base class:
- Negative values (avg_temp_c can be < 0) → tests conditional threshold formatting
- Wide scale differences (population 2M vs transit_score 100)
- "Lower is better" attrs (crime_rate) alongside "higher is better" (income)
"""

from __future__ import annotations

from random import Random
from typing import Any

from memorybench.worlds.base import (
    AttrDef, EntitySpec, SentenceTemplate, WorldTemplate, _possessive,
)

_ADJECTIVES = [
    "Cedar", "Maple", "Birch", "Aspen", "Willow", "Pine", "Elm", "Oak",
    "Holly", "Hazel", "Sage", "Juniper", "Laurel", "Ivy", "Cypress",
    "Magnolia", "Rowan", "Alder", "Spruce", "Fern", "Linden", "Poplar",
    "Yarrow", "Clover", "Briar", "Heath", "Wren", "Finch", "Lark", "Moss",
]

_NOUNS = [
    "Falls", "Ridge", "Creek", "Valley", "Bluff", "Hollow", "Mesa",
    "Brook", "Cove", "Glen", "Harbor", "Point", "Shore", "Pass",
    "Summit", "Bend", "Terrace", "Prairie", "Crossing", "Grove",
]

_REGIONS = [
    "Northlands", "Coastlands", "Highlands", "Plains",
    "Riverlands", "Woodlands", "Drylands", "Islands",
]

_ATTR_DEFS = [
    AttrDef("population", "int", 1000, 2000000, "", "Population"),
    AttrDef("area_km2", "float", 5.0, 1500.0, "km²", "Area"),
    AttrDef("median_income", "int", 20000, 150000, "$", "Median income"),
    AttrDef("elevation_m", "int", 0, 3000, "m", "Elevation"),
    AttrDef("avg_temp_c", "float", -10.0, 35.0, "°C", "Average temperature",
            agg_ops=("average",)),
    AttrDef("hospital_count", "int", 1, 50, "", "Hospitals"),
    AttrDef("school_count", "int", 2, 200, "", "Schools"),
    AttrDef("crime_rate", "float", 0.5, 15.0, "/1K", "Crime rate",
            agg_ops=("average",)),
    AttrDef("green_space_pct", "float", 1.0, 45.0, "%", "Green space",
            agg_ops=("average",)),
    AttrDef("transit_score", "int", 0, 100, "/100", "Transit score",
            agg_ops=("average",)),
]

_Q_TEXTS: dict[str, list[str]] = {
    "population": [
        "What is the population of {name}?",
        "How many people live in {name}?",
        "What is {name}'s total population?",
    ],
    "area_km2": [
        "What is the area of {name} in square kilometers?",
        "How large is {name} in km²?",
        "What is {name}'s total area?",
    ],
    "median_income": [
        "What is the median income in {name}?",
        "How much does the typical resident of {name} earn?",
        "What is {name}'s median household income?",
    ],
    "elevation_m": [
        "What is {name}'s elevation in meters?",
        "At what altitude is {name} situated?",
        "How high above sea level is {name}?",
    ],
    "avg_temp_c": [
        "What is the average temperature in {name}?",
        "What average temperature does {name} experience?",
        "How warm or cold is {name} on average?",
    ],
    "hospital_count": [
        "How many hospitals does {name} have?",
        "What is the number of hospitals in {name}?",
        "How many hospitals serve {name}'s residents?",
    ],
    "school_count": [
        "How many schools are in {name}?",
        "What is {name}'s total school count?",
        "How many schools does {name} operate?",
    ],
    "crime_rate": [
        "What is the crime rate in {name}?",
        "How high is {name}'s crime rate per thousand residents?",
        "What crime rate does {name} report?",
    ],
    "green_space_pct": [
        "What percentage of {name} is green space?",
        "How much green space does {name} have?",
        "What is {name}'s green space coverage?",
    ],
    "transit_score": [
        "What is {name}'s transit score?",
        "How does {name} rate for public transit?",
        "What transit score has {name} achieved?",
    ],
}


_SENTENCE_TMPLS: dict[str, list[tuple[str, str]]] = {
    "population": [
        ("is home to {val} residents", "none"),
        ("population grew from {distractor} to {val} in the latest census",
         "temporal"),
        ("has a population of {val}, compared to {other_name}'s "
         "{other_val}", "comparative"),
    ],
    "area_km2": [
        ("covers an area of {val}", "none"),
        ("expanded from {distractor} to {val} after recent annexation",
         "temporal"),
        ("spans {val}, though only {distractor} is developed land",
         "qualified"),
    ],
    "median_income": [
        ("reports a median household income of {val}", "none"),
        ("median income rose from {distractor} to {val}", "temporal"),
        ("earns a median of {val}, outpacing {other_name} at {other_val}",
         "comparative"),
    ],
    "elevation_m": [
        ("sits at an elevation of {val}", "none"),
        ("ranges from {distractor} to {val} in elevation across districts",
         "qualified"),
        ("is situated at {val}, higher than {other_name} at {other_val}",
         "comparative"),
    ],
    "avg_temp_c": [
        ("experiences an average temperature of {val}", "none"),
        ("average temperature shifted from {distractor} to {val}",
         "temporal"),
        ("records {val} on average, versus {other_name}'s {other_val}",
         "comparative"),
    ],
    "hospital_count": [
        ("is served by {val} hospitals", "none"),
        ("hospital count increased from {distractor} to {val}", "temporal"),
        ("has {val} hospitals, though only {distractor} offer emergency "
         "services", "qualified"),
    ],
    "school_count": [
        ("operates {val} public and private schools", "none"),
        ("school count grew from {distractor} to {val}", "temporal"),
        ("has {val} schools, of which {distractor} are public", "qualified"),
    ],
    "crime_rate": [
        ("reports a crime rate of {val}", "none"),
        ("crime rate changed from {distractor} to {val}", "temporal"),
        ("has a crime rate of {val}, compared to {other_name}'s "
         "{other_val}", "comparative"),
    ],
    "green_space_pct": [
        ("dedicates {val} of its area to green space", "none"),
        ("green space grew from {distractor} to {val}", "temporal"),
        ("maintains {val} green space, surpassing {other_name}'s "
         "{other_val}", "comparative"),
    ],
    "transit_score": [
        ("achieved a transit score of {val}", "none"),
        ("transit score improved from {distractor} to {val}", "temporal"),
        ("scores {val} for transit, outranking {other_name} at "
         "{other_val}", "comparative"),
    ],
}

_RATIO_PAIRS = [
    ("population", "area_km2", "population density per km²"),
    ("hospital_count", "population", "hospitals per capita"),
    ("school_count", "population", "schools per capita"),
]


def _fmt(attr: str, val: Any) -> str:
    if attr == "population":
        return f"{val:,}"
    if attr == "area_km2":
        return f"{val:,.1f} km²"
    if attr == "median_income":
        return f"${val:,}"
    if attr == "elevation_m":
        return f"{val:,} m"
    if attr == "avg_temp_c":
        return f"{val:.1f}°C"
    if attr == "crime_rate":
        return f"{val:.2f}/1K"
    if attr == "green_space_pct":
        return f"{val:.2f}%"
    if attr == "transit_score":
        return f"{val}/100"
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)


class CityWorld(WorldTemplate):
    """City/municipality — 600 names × 10 attrs × 8 regions."""

    @property
    def name(self) -> str:
        return "city"

    @property
    def all_attr_defs(self) -> list[AttrDef]:
        return list(_ATTR_DEFS)

    @property
    def all_categories(self) -> list[str]:
        return list(_REGIONS)

    @property
    def entity_word(self) -> str:
        return "city"

    @property
    def entity_word_plural(self) -> str:
        return "cities"

    def _generate_names(self, rng: Random, n: int) -> list[str]:
        pool = [(a, b) for a in _ADJECTIVES for b in _NOUNS]
        selected = rng.sample(pool, min(n, len(pool)))
        return [f"{a} {b}" for a, b in selected]

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
        style = rng.choice(["census", "travel", "report", "brief"])
        header = {
            "census": (f"MUNICIPAL DATA RECORD — {entity.name}\n"
                       f"Region: {entity.category}\n"),
            "travel": (f"CITY GUIDE ENTRY — {entity.name}\n"
                       f"Located in: {entity.category}\n"),
            "report": (f"CITY DATA REPORT — {entity.name}\n"
                       f"Administrative region: {entity.category}\n"),
            "brief": (f"URBAN ANALYTICS BRIEF — {entity.name}\n"
                      f"Geographic zone: {entity.category}\n"),
        }[style]
        return header + self._render_body(
            entity, active_attrs, rng, other_entities)

    def render_correction(self, entity: EntitySpec, attr: str,
                          old_val: Any, new_val: Any) -> str:
        label = self.attr_label(attr)
        return (
            f"DATA REVISION: {_possessive(entity.name)} {label} has been "
            f"corrected from {_fmt(attr, old_val)} to {_fmt(attr, new_val)} "
            f"based on updated records."
        )

    def _q_text(self, attr: str, name: str,
                rng: Random | None = None) -> str:
        templates = _Q_TEXTS.get(attr, [f"What is {{name}}'s {attr}?"])
        tmpl = rng.choice(templates) if rng else templates[0]
        return tmpl.format(name=name)
