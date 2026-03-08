"""Movie industry world template.

Entities: Movies with 10 possible numeric attributes.
Names: 30 adjectives × 20 nouns = 600 unique movie titles.
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

_ATTR_DEFS = [
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
}

_RATIO_PAIRS = [
    ("box_office_m", "budget_m", "box office to budget ratio"),
    ("opening_weekend_m", "screens", "opening weekend per screen in $M"),
    ("awards_count", "runtime_min", "awards per minute of runtime"),
]


def _fmt(attr: str, val: Any) -> str:
    """Format an attribute value for human-readable display."""
    if attr in ("budget_m", "box_office_m", "opening_weekend_m"):
        return f"${val:,.1f}M"
    if attr == "rating":
        return f"{val:.2f}/10"
    if attr in ("audience_score", "critic_score"):
        return f"{val}%"
    if attr == "runtime_min":
        return f"{val} min"
    if attr in ("screens", "awards_count"):
        return f"{val:,}"
    return str(val)


class MovieWorld(WorldTemplate):
    """Movie industry — 600 titles × 10 attrs × 10 genres."""

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
