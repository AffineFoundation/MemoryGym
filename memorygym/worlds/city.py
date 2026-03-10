"""City/municipality world template.

Entities: Cities with 23 possible attributes (18 numeric + text + enum + date + list_float).
Names: 30 nature adjectives x 20 geographic nouns = 600 unique cities.
Regions: 8 geographic regions.
Document styles: 4 narrative styles (~250 tokens each).

Design pressures on base class:
- Negative values (avg_temp_c can be < 0) -> tests conditional threshold formatting
- Wide scale differences (population 2M vs transit_score 100)
- "Lower is better" attrs (crime_rate) alongside "higher is better" (income)
"""

from __future__ import annotations

from random import Random
from typing import Any

from .base import (
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

_CITY_DESCRIPTIONS = [
    "a thriving metropolitan hub known for its vibrant arts scene and world-class dining establishments",
    "a coastal gem with pristine beaches and a bustling port that drives regional maritime commerce",
    "a historic center of learning home to prestigious universities and cutting-edge research institutes",
    "a rapidly modernizing urban area investing heavily in smart city infrastructure and green energy",
    "a mountainside retreat celebrated for its clean air, outdoor recreation, and alpine architecture",
    "a major transportation crossroads connecting regional trade routes with modern rail and highway networks",
    "a cultural melting pot where diverse communities have shaped a unique culinary and artistic identity",
    "a former industrial powerhouse now reinventing itself as a technology and innovation corridor",
    "a garden city renowned for its extensive parks system and commitment to environmental sustainability",
    "a riverfront settlement with a storied past in river trade and a growing modern services economy",
    "a fast-growing satellite city absorbing overflow from nearby megacities with affordable housing options",
    "a compact walkable city that prioritizes cycling infrastructure and public transit over car traffic",
    "a desert oasis that has transformed arid land into a flourishing agricultural and tourism destination",
    "a northern outpost with extreme seasonal variation that attracts adventure tourists year-round",
    "a lakeside community known for freshwater fisheries, waterfront festivals, and boat manufacturing",
    "a planned city built from scratch with modernist architecture and efficient grid-based street layout",
    "a tropical port city with a thriving export economy centered on fruits, spices, and textiles",
    "a hilltop fortress town preserving medieval heritage while embracing renewable energy initiatives",
    "a sprawling suburban city with expansive shopping districts and family-oriented residential communities",
    "a tech-forward smart city piloting autonomous transit, digital governance, and open data platforms",
]

_CLIMATE_ZONES = ["tropical", "arid", "temperate", "continental", "polar"]

_CITY_TYPES = ["capital", "port", "industrial", "cultural", "tech_hub",
               "resort"]

_ATTR_DEFS = [
    AttrDef("population", "int", 1000, 2000000, "", "Population"),
    AttrDef("area_km2", "float", 5.0, 1500.0, "km\u00b2", "Area"),
    AttrDef("median_income", "int", 20000, 150000, "$", "Median income"),
    AttrDef("elevation_m", "int", 0, 3000, "m", "Elevation"),
    AttrDef("avg_temp_c", "float", -10.0, 35.0, "\u00b0C", "Average temperature",
            agg_ops=("average",)),
    AttrDef("hospital_count", "int", 1, 50, "", "Hospitals"),
    AttrDef("school_count", "int", 2, 200, "", "Schools"),
    AttrDef("crime_rate", "float", 0.5, 15.0, "/1K", "Crime rate",
            agg_ops=("average",)),
    AttrDef("green_space_pct", "float", 1.0, 45.0, "%", "Green space",
            agg_ops=("average",)),
    AttrDef("transit_score", "int", 0, 100, "/100", "Transit score",
            agg_ops=("average",)),
    # New numeric attrs
    AttrDef("gdp_per_capita", "float", 1000, 80000, "$", "GDP per capita"),
    AttrDef("air_quality_index", "int", 10, 300, "", "Air quality index"),
    AttrDef("unemployment_pct", "float", 1.0, 25.0, "%", "Unemployment rate",
            agg_ops=("average",)),
    AttrDef("tourism_visitors", "int", 10000, 5000000, "", "Tourism visitors"),
    AttrDef("housing_price_index", "float", 50, 500, "", "Housing price index"),
    AttrDef("internet_speed_mbps", "float", 5, 1000, "Mbps",
            "Internet speed"),
    AttrDef("literacy_rate_pct", "float", 40, 100, "%", "Literacy rate",
            agg_ops=("average",)),
    AttrDef("life_expectancy", "float", 40, 90, "", "Life expectancy",
            agg_ops=("average",)),
    # New dtype attrs
    AttrDef("climate_zone", "enum", label="Climate zone",
            choices=_CLIMATE_ZONES),
    AttrDef("city_type", "enum", label="City type",
            choices=_CITY_TYPES),
    AttrDef("founding_date", "date", min_val=500, max_val=2000,
            label="Founding date"),
    AttrDef("city_description", "text", label="City description",
            text_pool=_CITY_DESCRIPTIONS),
    AttrDef("population_trend", "list_float", min_val=50000, max_val=5000000,
            label="Population (last 5 years)", list_len=5),
]

_Q_TEXTS: dict[str, list[str]] = {
    "population": [
        "What is the population of {name}?",
        "How many people live in {name}?",
        "What is {name}'s total population?",
    ],
    "area_km2": [
        "What is the area of {name} in square kilometers?",
        "How large is {name} in km\u00b2?",
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
    "gdp_per_capita": [
        "What is {name}'s GDP per capita?",
        "How much GDP per person does {name} produce?",
        "What is the per-capita GDP of {name}?",
    ],
    "unemployment_pct": [
        "What is {name}'s unemployment rate?",
        "How high is unemployment in {name}?",
        "What percentage of {name}'s workforce is unemployed?",
    ],
    "air_quality_index": [
        "What is {name}'s air quality index?",
        "How does {name} score on air quality?",
        "What AQI does {name} report?",
    ],
    "tourism_visitors": [
        "How many tourists visit {name} annually?",
        "What is {name}'s annual tourism visitor count?",
        "How many tourism visitors does {name} receive?",
    ],
    "housing_price_index": [
        "What is {name}'s housing price index?",
        "How does {name} rate on the housing price index?",
        "What housing price index does {name} have?",
    ],
    "internet_speed_mbps": [
        "What is the average internet speed in {name}?",
        "How fast is {name}'s internet connection?",
        "What internet speed does {name} offer in Mbps?",
    ],
    "life_expectancy": [
        "What is the life expectancy in {name}?",
        "How long do residents of {name} live on average?",
        "What is {name}'s average life expectancy?",
    ],
    "literacy_rate_pct": [
        "What is {name}'s literacy rate?",
        "What percentage of {name}'s population is literate?",
        "How high is the literacy rate in {name}?",
    ],
    "climate_zone": [
        "What climate zone is {name} in?",
        "What type of climate does {name} have?",
    ],
    "city_type": [
        "What type of city is {name}?",
        "How is {name} classified by city type?",
    ],
    "founding_date": [
        "When was {name} founded?",
        "What is {name}'s founding date?",
    ],
    "city_description": [
        "How would you describe {name}?",
        "What is {name} known for?",
        "Give a description of {name}.",
    ],
    "population_trend": [
        "What has {name}'s population been over the last 5 years?",
        "List {name}'s population trend for the past 5 years.",
    ],
}


_SENTENCE_TMPLS: dict[str, list[tuple[str, str]]] = {
    "population": [
        ("is home to {val} residents", "none"),
        ("population figures of {distractor} and {val} across census "
         "periods", "temporal"),
        ("population counts of {val} and {other_val} from separate "
         "surveys", "comparative"),
    ],
    "area_km2": [
        ("covers an area of {val}", "none"),
        ("area measurements of {val} and {distractor} in different "
         "surveys", "temporal"),
        ("area figures of {distractor} and {val} by different boundary "
         "definitions", "qualified"),
    ],
    "median_income": [
        ("reports a median household income of {val}", "none"),
        ("median income figures of {distractor} and {val} across reporting "
         "years", "temporal"),
        ("median income readings of {val} and {other_val} from different "
         "sources", "comparative"),
    ],
    "elevation_m": [
        ("sits at an elevation of {val}", "none"),
        ("elevation readings of {val} and {distractor} by different "
         "measurement methods", "qualified"),
        ("elevation figures of {other_val} and {val} in separate "
         "surveys", "comparative"),
    ],
    "avg_temp_c": [
        ("experiences an average temperature of {val}", "none"),
        ("average temperature readings of {val} and {distractor} across "
         "periods", "temporal"),
        ("temperature averages of {val} and {other_val} from different "
         "stations", "comparative"),
    ],
    "hospital_count": [
        ("is served by {val} hospitals", "none"),
        ("hospital counts of {distractor} and {val} in different "
         "periods", "temporal"),
        ("hospital tallies of {val} and {distractor} under different "
         "criteria", "qualified"),
    ],
    "school_count": [
        ("operates {val} public and private schools", "none"),
        ("school counts of {val} and {distractor} across census years",
         "temporal"),
        ("school figures of {distractor} and {val} by different counting "
         "methods", "qualified"),
    ],
    "crime_rate": [
        ("reports a crime rate of {val}", "none"),
        ("crime rate figures of {distractor} and {val} in successive "
         "reports", "temporal"),
        ("crime rate readings of {val} and {other_val} from different "
         "agencies", "comparative"),
    ],
    "green_space_pct": [
        ("dedicates {val} of its area to green space", "none"),
        ("green space percentages of {val} and {distractor} across "
         "assessments", "temporal"),
        ("green space figures of {other_val} and {val} in separate "
         "analyses", "comparative"),
    ],
    "transit_score": [
        ("achieved a transit score of {val}", "none"),
        ("transit score readings of {distractor} and {val} in different "
         "evaluations", "temporal"),
        ("transit scores of {val} and {other_val} from separate "
         "rankings", "comparative"),
    ],
    "gdp_per_capita": [
        ("produces a GDP per capita of {val}", "none"),
        ("GDP per capita figures of {val} and {distractor} across fiscal "
         "years", "temporal"),
        ("per capita GDP readings of {other_val} and {val} from different "
         "estimates", "comparative"),
    ],
    "unemployment_pct": [
        ("has an unemployment rate of {val}", "none"),
        ("unemployment figures of {distractor} and {val} in different "
         "quarters", "temporal"),
        ("unemployment rates of {val} and {other_val} from separate "
         "reports", "comparative"),
    ],
    "air_quality_index": [
        ("records an air quality index of {val}", "none"),
        ("air quality index readings of {val} and {distractor} across "
         "seasons", "temporal"),
        ("AQI values of {other_val} and {val} from different monitoring "
         "networks", "comparative"),
    ],
    "tourism_visitors": [
        ("attracts {val} tourists annually", "none"),
        ("tourism figures of {distractor} and {val} visitors in different "
         "years", "temporal"),
        ("visitor counts of {val} and {other_val} from separate "
         "agencies", "comparative"),
    ],
    "housing_price_index": [
        ("has a housing price index of {val}", "none"),
        ("housing price index readings of {val} and {distractor} across "
         "quarters", "temporal"),
    ],
    "internet_speed_mbps": [
        ("offers average internet speeds of {val}", "none"),
        ("internet speed figures of {distractor} and {val} in different "
         "tests", "temporal"),
    ],
    "life_expectancy": [
        ("has a life expectancy of {val} years", "none"),
        ("life expectancy readings of {val} and {distractor} across study "
         "periods", "temporal"),
        ("life expectancy figures of {other_val} and {val} from separate "
         "studies", "comparative"),
    ],
    "literacy_rate_pct": [
        ("achieves a literacy rate of {val}", "none"),
        ("literacy rate figures of {distractor} and {val} in different "
         "assessments", "temporal"),
    ],
    "climate_zone": [
        ("is situated in a {val} climate zone", "none"),
    ],
    "city_type": [
        ("is classified as a {val} city", "none"),
    ],
    "founding_date": [
        ("was founded on {val}", "none"),
    ],
    "city_description": [
        ("{val}", "none"),
    ],
    "population_trend": [
        ("recorded population figures of {val} over the last 5 years", "none"),
    ],
}

_RATIO_PAIRS = [
    ("population", "area_km2", "population density per km\u00b2"),
    ("hospital_count", "population", "hospitals per capita"),
    ("school_count", "population", "schools per capita"),
    ("gdp_per_capita", "median_income", "GDP-to-income ratio"),
    ("tourism_visitors", "population", "tourists per resident"),
]


def _fmt(attr: str, val: Any) -> str:
    if attr == "population":
        return f"{val:,}"
    if attr == "area_km2":
        return f"{val:,.2f} km\u00b2"
    if attr in ("median_income", "gdp_per_capita"):
        return f"${val:,.2f}" if isinstance(val, float) else f"${val:,}"
    if attr == "elevation_m":
        return f"{val:,} m"
    if attr == "avg_temp_c":
        return f"{val:.2f}\u00b0C"
    if attr == "crime_rate":
        return f"{val:.2f}/1K"
    if attr in ("green_space_pct", "unemployment_pct", "literacy_rate_pct"):
        return f"{val:.2f}%"
    if attr == "transit_score":
        return f"{val}/100"
    if attr in ("tourism_visitors", "air_quality_index"):
        return f"{val:,}"
    if attr == "housing_price_index":
        return f"{val:.1f}"
    if attr == "internet_speed_mbps":
        return f"{val:.1f} Mbps"
    if attr == "life_expectancy":
        return f"{val:.1f} years"
    if attr == "population_trend" and isinstance(val, list):
        return ", ".join(f"{v:,.0f}" for v in val)
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)


class CityWorld(WorldTemplate):
    """City/municipality -- 600 names x 23 attrs x 8 regions."""

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

    @property
    def correction_rate(self) -> float:
        return 0.05  # low — stable municipal data

    @property
    def correction_timing(self) -> tuple[float, float]:
        return (0.5, 0.8)  # late corrections — data rarely changes

    @property
    def question_weights(self) -> dict[str, float]:
        return {
            "retrieval": 0.45,       # high — stable data, recall matters
            "comprehension": 0.30,   # trend analysis for city data
            "update": 0.10,          # low — few corrections
            "abstention": 0.15,
        }

    def _generate_names(self, rng: Random, n: int) -> list[str]:
        pool = [(a, b) for a in _ADJECTIVES for b in _NOUNS]
        selected = rng.sample(pool, min(n, len(pool)))
        return [f"{a} {b}" for a, b in selected]

    def _generate_list_float(self, adef, rng):
        """Smooth monotonic trend: steady growth or decline with low noise."""
        start = rng.uniform(adef.min_val * 0.3, adef.max_val * 0.7)
        growth_rate = rng.uniform(-0.03, 0.08)  # mostly growth, some decline
        values = []
        for i in range(adef.list_len):
            val = start * (1 + growth_rate) ** i
            noise = rng.uniform(0.98, 1.02)  # very low noise
            val = max(adef.min_val, min(adef.max_val, val * noise))
            values.append(round(val, 2))
        return values

    def generate_entity(self, rng: Random, name: str, category: str,
                        active_attrs: list[str]) -> EntitySpec:
        attrs: dict[str, Any] = {}
        for adef in _ATTR_DEFS:
            if adef.name not in active_attrs:
                continue
            attrs[adef.name] = self._generate_attr_value(rng, adef)
        # Constraint: population density and infrastructure scale
        if "population" in attrs and "area_km2" in attrs:
            pop = attrs["population"]
            area = attrs["area_km2"]
            density = pop / area if area > 0 else 0
            # Keep density in realistic range (50-30000 per km²)
            if density < 50:
                attrs["area_km2"] = round(pop / rng.uniform(200, 2000), 1)
            elif density > 30000:
                attrs["area_km2"] = round(pop / rng.uniform(5000, 15000), 1)
        if "population" in attrs and "hospital_count" in attrs:
            pop = attrs["population"]
            # ~1 hospital per 20K-80K people
            attrs["hospital_count"] = max(1, rng.randint(
                max(1, pop // 80000), max(2, pop // 20000)))
        if "population" in attrs and "school_count" in attrs:
            pop = attrs["population"]
            # ~1 school per 3K-10K people
            attrs["school_count"] = max(2, rng.randint(
                max(2, pop // 10000), max(3, pop // 3000)))
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
            ("neighbor_of", "is a neighbor of", True),
            ("trades_with", "trades with", True),
        ]

    def render_relationship(self, rel):
        if rel.relation == "neighbor_of":
            return (f"{rel.source} and {rel.target} share a common "
                    f"border and maintain joint infrastructure.")
        if rel.relation == "trades_with":
            return (f"{rel.source} has an active trade corridor "
                    f"with {rel.target}.")
        return super().render_relationship(rel)

    def render_document(self, entity: EntitySpec,
                        active_attrs: list[str], rng: Random,
                        other_entities: list[EntitySpec] | None = None
                        ) -> str:
        style = rng.choice(["census", "travel", "report", "brief"])
        header = {
            "census": (f"MUNICIPAL DATA RECORD -- {entity.name}\n"
                       f"Region: {entity.category}\n"),
            "travel": (f"CITY GUIDE ENTRY -- {entity.name}\n"
                       f"Located in: {entity.category}\n"),
            "report": (f"CITY DATA REPORT -- {entity.name}\n"
                       f"Administrative region: {entity.category}\n"),
            "brief": (f"URBAN ANALYTICS BRIEF -- {entity.name}\n"
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
