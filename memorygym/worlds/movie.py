"""Movie industry world template.

Entities: Movies with 23 possible attributes (16 numeric + text + enum + date + list_float).
Names: 30 adjectives x 20 nouns = 600 unique movie titles.
Genres: 10 genre categories.
Document styles: 4 narrative styles (~250 tokens each).
"""

from __future__ import annotations

from random import Random
from typing import Any

from memorygym.worlds.base import (
    AttrDef, EntitySpec, SentenceTemplate, WorldTemplate, _possessive,
)

_ADJECTIVES = [
    "Silent", "Crimson", "Eternal", "Frozen", "Hidden", "Iron", "Last",
    "Dark", "Golden", "Rising", "Broken", "Burning", "Fallen", "Lost",
    "Midnight", "Shadow", "Steel", "Thunder", "Velvet", "Wild",
    "Neon", "Crystal", "Scarlet", "Silver", "Electric", "Hollow",
    "Savage", "Glass", "Twisted", "Infinite",
]

_NOUNS = [
    "Dawn", "Empire", "Horizon", "Legacy", "Protocol", "Requiem",
    "Storm", "Vanguard", "Witness", "Cipher", "Dominion", "Exodus",
    "Fortress", "Junction", "Meridian", "Paradox", "Reckoning",
    "Threshold", "Vendetta", "Chronicle",
]

_GENRES = [
    "Action", "Drama", "Comedy", "Thriller", "Sci-Fi",
    "Horror", "Romance", "Animation", "Documentary", "Adventure",
]

_DIRECTORS = [
    "Sofia Marchetti", "Raj Patel", "Lena Johansson", "Carlos Mendoza",
    "Yuki Tanaka", "Amara Okafor", "Ethan Blackwell", "Priya Sharma",
    "Viktor Kozlov", "Mei-Ling Chen", "Dante Rossi", "Fatima Al-Hassan",
    "Oscar Lindqvist", "Hana Nakamura", "Tomasz Kowalski",
    "Adaeze Nwosu", "Mikhail Petrov", "Elena Vasquez",
    "Joon-ho Park", "Isabelle Fontaine",
]

_LEAD_ACTORS = [
    "Marcus Rivera", "Zara Okonkwo", "Liam Thornton", "Aisha Kapoor",
    "Nikolai Volkov", "Camille Dubois", "Hiroshi Watanabe", "Elena Ruiz",
    "Sebastian Cross", "Naomi Taniguchi", "Rafael Santos", "Ingrid Larsen",
    "Kwame Asante", "Mila Horvat", "James Whitfield",
    "Yara Mansour", "Henrik Nystrom", "Lucia Bianchi",
    "Dae-jung Kim", "Freya Andersen",
]

_PLOT_SUMMARIES = [
    "A disgraced detective uncovers a conspiracy that threatens to topple the government from within",
    "Two estranged siblings reunite to save their family farm from a ruthless real estate developer",
    "An astronaut stranded on a distant moon must survive using only salvaged alien technology",
    "A young chef enters an underground cooking tournament with life-or-death stakes",
    "After a mysterious signal blankets the Earth, a linguist races to decode its hidden meaning",
    "A retired spy is pulled back into the field when their former protege goes rogue",
    "In a world where memories can be traded, a dealer discovers a memory that could change everything",
    "A group of strangers trapped in a skyscraper must work together to escape a deadly game",
    "A journalist infiltrates a secretive cult and realizes the truth is stranger than fiction",
    "An aging rock star embarks on a final tour while confronting the ghosts of their past",
    "A small-town teacher stumbles upon an ancient artifact that grants impossible wishes",
    "Two rival hackers are forced to collaborate when a rogue AI threatens global infrastructure",
    "A deep-sea expedition discovers a civilization that should not exist beneath the ocean floor",
    "After inheriting a crumbling mansion, a woman uncovers her grandmother's wartime secrets",
    "A bounty hunter in a lawless frontier town faces a moral crisis over their latest target",
    "An Olympic hopeful must overcome personal tragedy and a corrupt system to reach the podium",
    "A time-loop traps a paramedic in the worst day of their career, forcing them to save everyone",
    "In a dystopian megacity, a courier discovers their deliveries fuel an underground revolution",
    "A documentary crew filming endangered wildlife accidentally captures evidence of a crime syndicate",
    "A widowed father and his daughter bond over restoring a vintage airplane for a cross-country race",
]

_STUDIOS = [
    "Paramount", "Warner", "Disney", "Universal", "Sony",
    "Netflix", "A24", "Lionsgate",
]

_CONTENT_RATINGS = ["G", "PG", "PG-13", "R", "NC-17"]

_ATTR_DEFS = [
    # Original numeric attrs
    AttrDef("budget_m", "float", 1, 350, "$M", "Budget"),
    AttrDef("box_office_m", "float", 0.5, 2500, "$M", "Box office"),
    AttrDef("rating", "float", 1.0, 10.0, "/10", "Rating",
            agg_ops=("average",)),
    AttrDef("runtime_min", "int", 70, 240, "min", "Runtime"),
    AttrDef("screens", "int", 50, 5000, "", "Screens"),
    AttrDef("audience_score", "int", 5, 100, "%", "Audience score",
            agg_ops=("average",)),
    AttrDef("critic_score", "int", 5, 100, "%", "Critic score",
            agg_ops=("average",)),
    AttrDef("opening_weekend_m", "float", 0.1, 400, "$M", "Opening weekend"),
    AttrDef("awards_count", "int", 0, 30, "", "Awards"),
    AttrDef("release_year", "int", 1990, 2025, "", "Release year"),
    # New numeric attrs
    AttrDef("sequel_number", "int", 0, 10, "", "Sequel number"),
    AttrDef("streaming_views_m", "float", 0.1, 500, "M", "Streaming views",
            agg_ops=("average",)),
    AttrDef("merchandise_revenue_m", "float", 0, 200, "$M",
            "Merchandise revenue"),
    AttrDef("trailer_views_m", "float", 0.1, 200, "M", "Trailer views"),
    AttrDef("cast_size", "int", 5, 100, "", "Cast size"),
    AttrDef("production_days", "int", 20, 365, "", "Production days"),
    # New dtype attrs
    AttrDef("director", "text", label="Director", text_pool=_DIRECTORS),
    AttrDef("lead_actor", "text", label="Lead actor",
            text_pool=_LEAD_ACTORS),
    AttrDef("plot_summary", "text", label="Plot summary",
            text_pool=_PLOT_SUMMARIES),
    AttrDef("studio", "enum", label="Studio", choices=_STUDIOS),
    AttrDef("content_rating", "enum", label="Content rating",
            choices=_CONTENT_RATINGS),
    AttrDef("release_date", "date", min_val=2000, max_val=2025,
            label="Release date"),
    AttrDef("weekly_box_office", "list_float", min_val=0.5, max_val=200,
            label="Weekly box office ($M, first 4 weeks)", list_len=4),
]

_Q_TEXTS: dict[str, list[str]] = {
    "budget_m": [
        "What was the production budget of {name}?",
        "How much did {name} cost to make?",
        "What is {name}'s total budget?",
    ],
    "box_office_m": [
        "What is {name}'s total box office gross?",
        "How much did {name} earn at the box office?",
        "What are {name}'s worldwide box office numbers?",
    ],
    "rating": [
        "What is {name}'s overall rating?",
        "How is {name} rated?",
        "What rating did {name} receive?",
    ],
    "runtime_min": [
        "How long is {name}?",
        "What is the runtime of {name}?",
        "How many minutes does {name} run?",
    ],
    "screens": [
        "On how many screens was {name} shown?",
        "What is {name}'s screen count?",
        "How widely was {name} distributed?",
    ],
    "audience_score": [
        "What is {name}'s audience score?",
        "How did audiences rate {name}?",
        "What audience approval did {name} receive?",
    ],
    "critic_score": [
        "What is {name}'s critic score?",
        "How did critics rate {name}?",
        "What critic approval did {name} receive?",
    ],
    "opening_weekend_m": [
        "How much did {name} make on its opening weekend?",
        "What was {name}'s opening weekend gross?",
        "What did {name} earn in its first weekend?",
    ],
    "awards_count": [
        "How many awards has {name} won?",
        "What is {name}'s total award count?",
        "How many accolades did {name} receive?",
    ],
    "release_year": [
        "When was {name} released?",
        "In what year did {name} come out?",
        "What year was {name} released?",
    ],
    "sequel_number": [
        "What sequel number is {name}?",
        "Which installment in the franchise is {name}?",
        "What is {name}'s sequel number?",
    ],
    "streaming_views_m": [
        "How many streaming views has {name} received?",
        "What are {name}'s total streaming views?",
        "How many times has {name} been streamed?",
    ],
    "merchandise_revenue_m": [
        "How much merchandise revenue has {name} generated?",
        "What are {name}'s merchandise sales?",
        "What is {name}'s total merchandise revenue?",
    ],
    "trailer_views_m": [
        "How many views did {name}'s trailer get?",
        "What is {name}'s trailer view count?",
        "How many times was {name}'s trailer watched?",
    ],
    "cast_size": [
        "How many cast members does {name} have?",
        "What is {name}'s cast size?",
        "How large is the cast of {name}?",
    ],
    "production_days": [
        "How many days was {name} in production?",
        "What was {name}'s production duration in days?",
        "How long did it take to film {name}?",
    ],
    "director": [
        "Who directed {name}?",
        "Who is {name}'s director?",
        "Which director helmed {name}?",
    ],
    "lead_actor": [
        "Who is the lead actor in {name}?",
        "Who stars in {name}?",
        "Who plays the lead role in {name}?",
    ],
    "plot_summary": [
        "What is {name} about?",
        "Describe the plot of {name}.",
        "What is the storyline of {name}?",
    ],
    "studio": [
        "Which studio produced {name}?",
        "What studio released {name}?",
        "Who distributed {name}?",
    ],
    "content_rating": [
        "What is {name}'s content rating?",
        "What rating did {name} receive from the MPAA?",
        "What age rating does {name} carry?",
    ],
    "release_date": [
        "What is {name}'s exact release date?",
        "When was {name} officially released?",
        "On what date did {name} premiere?",
    ],
    "weekly_box_office": [
        "What are {name}'s weekly box office figures for the first 4 weeks?",
        "List {name}'s box office earnings for each of its first 4 weeks.",
    ],
}

_SENTENCE_TMPLS: dict[str, list[tuple[str, str]]] = {
    "budget_m": [
        ("was produced on a budget of {val}", "none"),
        ("saw its budget grow from {distractor} to {val} during production",
         "temporal"),
        ("cost {val} to produce, compared to {other_name}'s {other_val}",
         "comparative"),
    ],
    "box_office_m": [
        ("grossed {val} worldwide at the box office", "none"),
        ("climbed from {distractor} to {val} in cumulative earnings",
         "temporal"),
        ("earned {val} globally, outperforming {other_name} at {other_val}",
         "comparative"),
    ],
    "rating": [
        ("holds an overall rating of {val}", "none"),
        ("improved its rating from {distractor} to {val} after "
         "re-evaluation", "temporal"),
        ("scored {val}, though the director's cut received {distractor}",
         "qualified"),
    ],
    "runtime_min": [
        ("runs for {val}", "none"),
        ("was trimmed from {distractor} to {val} for theatrical release",
         "temporal"),
        ("has a total runtime of {val}, including {distractor} of "
         "credits", "qualified"),
    ],
    "screens": [
        ("was shown on {val} screens at peak distribution", "none"),
        ("expanded from {distractor} to {val} screens during its run",
         "temporal"),
        ("screened on {val} screens, versus {other_name}'s {other_val}",
         "comparative"),
    ],
    "audience_score": [
        ("received an audience score of {val}", "none"),
        ("saw audience approval rise from {distractor} to {val}",
         "temporal"),
        ("earned {val} from audiences, compared to {other_name}'s "
         "{other_val}", "comparative"),
    ],
    "critic_score": [
        ("holds a critic score of {val}", "none"),
        ("had its critic score revised from {distractor} to {val}",
         "temporal"),
        ("scored {val} with critics, though the TV version earned "
         "{distractor}", "qualified"),
    ],
    "opening_weekend_m": [
        ("opened with {val} in its first weekend", "none"),
        ("surpassed projections of {distractor} to open at {val}",
         "temporal"),
        ("debuted at {val}, ahead of {other_name}'s {other_val}",
         "comparative"),
    ],
    "awards_count": [
        ("has won {val} awards to date", "none"),
        ("increased its award tally from {distractor} to {val} this "
         "season", "temporal"),
        ("collected {val} awards, beating {other_name}'s {other_val}",
         "comparative"),
    ],
    "release_year": [
        ("was released in {val}", "none"),
        ("was originally announced for {distractor} but released "
         "in {val}", "temporal"),
        ("came out in {val}, the same year as {other_name}",
         "comparative"),
    ],
    "sequel_number": [
        ("is installment number {val} in its franchise", "none"),
        ("was promoted from part {distractor} to part {val} after a "
         "reboot", "temporal"),
    ],
    "streaming_views_m": [
        ("has accumulated {val} streaming views", "none"),
        ("grew from {distractor} to {val} streaming views since launch",
         "temporal"),
        ("reached {val} streams, surpassing {other_name}'s {other_val}",
         "comparative"),
    ],
    "merchandise_revenue_m": [
        ("generated {val} in merchandise revenue", "none"),
        ("boosted merchandise sales from {distractor} to {val}",
         "temporal"),
    ],
    "trailer_views_m": [
        ("had its trailer viewed {val} times", "none"),
        ("saw trailer views jump from {distractor} to {val} after "
         "the Super Bowl spot", "temporal"),
    ],
    "cast_size": [
        ("features a cast of {val} actors", "none"),
        ("expanded its cast from {distractor} to {val} during reshoots",
         "temporal"),
    ],
    "production_days": [
        ("was filmed over {val} days", "none"),
        ("extended production from {distractor} to {val} days due to "
         "weather delays", "temporal"),
    ],
    "director": [
        ("was directed by {val}", "none"),
    ],
    "lead_actor": [
        ("stars {val} in the lead role", "none"),
    ],
    "plot_summary": [
        ("{val}", "none"),
    ],
    "studio": [
        ("was produced by {val} studio", "none"),
    ],
    "content_rating": [
        ("carries a {val} content rating", "none"),
    ],
    "release_date": [
        ("premiered on {val}", "none"),
    ],
    "weekly_box_office": [
        ("earned {val} across its first four weeks", "none"),
    ],
}

_RATIO_PAIRS = [
    ("box_office_m", "budget_m", "box office to budget ratio"),
    ("opening_weekend_m", "screens", "opening weekend per screen in $M"),
    ("awards_count", "runtime_min", "awards per minute of runtime"),
    ("merchandise_revenue_m", "box_office_m",
     "merchandise to box office ratio"),
    ("streaming_views_m", "trailer_views_m",
     "streaming views to trailer views ratio"),
    ("box_office_m", "production_days",
     "box office per production day in $M"),
]


def _fmt(attr: str, val: Any) -> str:
    """Format an attribute value for human-readable display."""
    if attr in ("budget_m", "box_office_m", "opening_weekend_m",
                "merchandise_revenue_m"):
        return f"${val:,.1f}M" if isinstance(val, (int, float)) else str(val)
    if attr == "rating":
        return f"{val:.2f}/10"
    if attr in ("audience_score", "critic_score"):
        return f"{val}%"
    if attr == "runtime_min":
        return f"{val} min"
    if attr in ("screens", "awards_count", "cast_size", "production_days",
                "sequel_number"):
        return f"{val:,}" if isinstance(val, (int, float)) else str(val)
    if attr in ("streaming_views_m", "trailer_views_m"):
        return (f"{val:,.1f}M views"
                if isinstance(val, (int, float)) else str(val))
    if attr == "weekly_box_office" and isinstance(val, list):
        return ", ".join(f"${v:,.1f}M" for v in val)
    return str(val)


class MovieWorld(WorldTemplate):
    """Movie industry — 600 titles x 23 attrs x 10 genres."""

    @property
    def name(self) -> str:
        return "movie"

    @property
    def all_attr_defs(self) -> list[AttrDef]:
        return list(_ATTR_DEFS)

    @property
    def all_categories(self) -> list[str]:
        return list(_GENRES)

    @property
    def entity_word(self) -> str:
        return "movie"

    def _generate_names(self, rng: Random, n: int) -> list[str]:
        pool = [(a, noun) for a in _ADJECTIVES for noun in _NOUNS]
        selected = rng.sample(pool, min(n, len(pool)))
        return [f"{a} {noun}" for a, noun in selected]

    def generate_entity(self, rng: Random, name: str, category: str,
                        active_attrs: list[str]) -> EntitySpec:
        attrs: dict[str, Any] = {}
        for adef in _ATTR_DEFS:
            if adef.name not in active_attrs:
                continue
            attrs[adef.name] = self._generate_attr_value(rng, adef)

        # Constraint: opening weekend cannot exceed total box office
        if ("opening_weekend_m" in attrs and "box_office_m" in attrs
                and attrs["opening_weekend_m"] > attrs["box_office_m"]):
            attrs["box_office_m"] = round(
                attrs["opening_weekend_m"] * rng.uniform(1.1, 3.0), 2)

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
            ("sequel_of", "is a sequel of", False),
            ("shares_universe_with", "shares a universe with", True),
        ]

    def render_relationship(self, rel):
        if rel.relation == "sequel_of":
            return (f"{rel.source} is a direct sequel to {rel.target}, "
                    f"continuing the storyline.")
        if rel.relation == "shares_universe_with":
            return (f"{rel.source} and {rel.target} take place in the "
                    f"same cinematic universe.")
        return super().render_relationship(rel)

    def render_document(self, entity: EntitySpec,
                        active_attrs: list[str], rng: Random,
                        other_entities: list[EntitySpec] | None = None
                        ) -> str:
        style = rng.choice(["review", "boxoffice", "profile", "festival"])
        header = {
            "review": (f"FILM REVIEW — {entity.name}\n"
                       f"Genre: {entity.category}\n"),
            "boxoffice": (f"BOX OFFICE REPORT — {entity.name}\n"
                          f"Category: {entity.category}\n"),
            "profile": (f"FILM PROFILE — {entity.name}\n"
                        f"Genre: {entity.category}\n"),
            "festival": (f"FESTIVAL SCREENING NOTES — {entity.name}\n"
                         f"Genre: {entity.category}\n"),
        }[style]
        return header + self._render_body(
            entity, active_attrs, rng, other_entities)

    def render_correction(self, entity: EntitySpec, attr: str,
                          old_val: Any, new_val: Any) -> str:
        label = self.attr_label(attr)
        return (
            f"CORRECTION NOTICE: {_possessive(entity.name)} {label} has been "
            f"revised from {_fmt(attr, old_val)} to {_fmt(attr, new_val)} "
            f"following updated reporting."
        )

    def _q_text(self, attr: str, name: str,
                rng: Random | None = None) -> str:
        templates = _Q_TEXTS.get(attr, [f"What is {{name}}'s {attr}?"])
        tmpl = rng.choice(templates) if rng else templates[0]
        return tmpl.format(name=name)
