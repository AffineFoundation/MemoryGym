"""Sports team world template.

Entities: Sports teams with performance and financial attributes.
Names: 30 city-like words × 20 mascots = 600 unique teams.
Leagues: 10 sports leagues.
Document styles: 4 narrative styles (~250 tokens each).

Design pressures:
- Mix of percentage (win_pct) and count (roster_size) attrs
- Large range differences: revenue [1M, 5000M] vs roster_size [15, 60]
- "Lower is better" (avg_age for rebuilding) ambiguity tests comprehension
"""

from __future__ import annotations

from random import Random
from typing import Any

from memorygym.worlds.base import (
    AttrDef, EntitySpec, SentenceTemplate, WorldTemplate, _possessive,
)

_CITIES = [
    "Metro", "Capital", "Crown", "Phoenix", "Thunder", "Storm",
    "Liberty", "Empire", "Pacific", "Atlantic", "Nordic", "Solar",
    "Coastal", "Mountain", "River", "Delta", "Summit", "Iron",
    "Steel", "Crimson", "Azure", "Obsidian", "Titan", "Vanguard",
    "Apex", "Horizon", "Lunar", "Stellar", "Tempest", "Granite",
]

_MASCOTS = [
    "Lions", "Eagles", "Wolves", "Bears", "Hawks", "Panthers",
    "Falcons", "Sharks", "Tigers", "Vipers", "Stallions", "Rams",
    "Cougars", "Jaguars", "Cobras", "Ravens", "Mustangs", "Bison",
    "Foxes", "Orcas",
]

_LEAGUES = [
    "Premier League", "Division One", "National Conference",
    "Eastern League", "Western Conference", "Continental League",
    "Pacific Division", "Atlantic Conference", "Central League",
    "Championship Series",
]

_ATTR_DEFS = [
    AttrDef("wins", "int", 0, 120, "", "Wins"),
    AttrDef("losses", "int", 0, 120, "", "Losses"),
    AttrDef("win_pct", "float", 0.0, 1.0, "", "Win percentage",
            agg_ops=("average",)),
    AttrDef("points_scored", "int", 100, 10000, "", "Points scored"),
    AttrDef("points_allowed", "int", 100, 10000, "", "Points allowed"),
    AttrDef("roster_size", "int", 15, 60, "", "Roster size"),
    AttrDef("avg_age", "float", 20.0, 35.0, "yrs", "Average age",
            agg_ops=("average",)),
    AttrDef("revenue_m", "float", 1.0, 5000.0, "$M", "Revenue"),
    AttrDef("attendance_avg", "int", 1000, 100000, "", "Average attendance"),
    AttrDef("championships", "int", 0, 30, "", "Championships"),
]

_Q_TEXTS: dict[str, list[str]] = {
    "wins": [
        "How many wins do the {name} have?",
        "What is the {name}'s win total?",
        "How many games have the {name} won?",
    ],
    "losses": [
        "How many losses do the {name} have?",
        "What is the {name}'s loss count?",
        "How many games have the {name} lost?",
    ],
    "win_pct": [
        "What is the {name}'s winning percentage?",
        "What win rate do the {name} maintain?",
        "How often do the {name} win?",
    ],
    "points_scored": [
        "How many points have the {name} scored?",
        "What is the {name}'s total points scored?",
        "What offensive output do the {name} have?",
    ],
    "points_allowed": [
        "How many points have the {name} allowed?",
        "What is the {name}'s points against total?",
        "How many points have opponents scored against the {name}?",
    ],
    "roster_size": [
        "How many players are on the {name}'s roster?",
        "What is the {name}'s roster size?",
        "How large is the {name}'s squad?",
    ],
    "avg_age": [
        "What is the average age of the {name}'s players?",
        "How old are the {name}'s players on average?",
        "What is the {name}'s average roster age?",
    ],
    "revenue_m": [
        "What is the {name}'s annual revenue?",
        "How much revenue do the {name} generate?",
        "What are the {name}'s total revenues?",
    ],
    "attendance_avg": [
        "What is the {name}'s average attendance?",
        "How many fans attend {name} games on average?",
        "What average crowd size do the {name} draw?",
    ],
    "championships": [
        "How many championships have the {name} won?",
        "What is the {name}'s championship count?",
        "How many titles do the {name} hold?",
    ],
}


_SENTENCE_TMPLS: dict[str, list[tuple[str, str]]] = {
    "wins": [
        ("recorded {val} wins this season", "none"),
        ("improved from {distractor} to {val} wins", "temporal"),
        ("tallied {val} wins, ahead of {other_name}'s {other_val}",
         "comparative"),
    ],
    "losses": [
        ("suffered {val} losses on the season", "none"),
        ("losses increased from {distractor} to {val}", "temporal"),
        ("recorded {val} losses, versus {other_name}'s {other_val}",
         "comparative"),
    ],
    "win_pct": [
        ("holds a winning percentage of {val}", "none"),
        ("win rate climbed from {distractor} to {val}", "temporal"),
        ("maintains {val} win rate, outpacing {other_name} at "
         "{other_val}", "comparative"),
    ],
    "points_scored": [
        ("put up {val} points on offense", "none"),
        ("scoring improved from {distractor} to {val} points", "temporal"),
        ("scored {val}, of which {distractor} came in the second half",
         "qualified"),
    ],
    "points_allowed": [
        ("allowed {val} points defensively", "none"),
        ("points allowed changed from {distractor} to {val}", "temporal"),
        ("conceded {val} points, compared to {other_name}'s {other_val}",
         "comparative"),
    ],
    "roster_size": [
        ("carries {val} players on the active roster", "none"),
        ("roster expanded from {distractor} to {val} players", "temporal"),
        ("has {val} players, though only {distractor} are starters",
         "qualified"),
    ],
    "avg_age": [
        ("fields a squad with an average age of {val}", "none"),
        ("average age shifted from {distractor} to {val}", "temporal"),
        ("averages {val} in age, compared to {other_name}'s {other_val}",
         "comparative"),
    ],
    "revenue_m": [
        ("generated {val} in total revenue", "none"),
        ("revenue grew from {distractor} to {val}", "temporal"),
        ("earned {val}, surpassing {other_name}'s {other_val}",
         "comparative"),
    ],
    "attendance_avg": [
        ("draws an average crowd of {val} per game", "none"),
        ("attendance grew from {distractor} to {val}", "temporal"),
        ("averages {val} fans, compared to {other_name}'s {other_val}",
         "comparative"),
    ],
    "championships": [
        ("has won {val} championships in franchise history", "none"),
        ("championship count grew from {distractor} to {val}", "temporal"),
        ("holds {val} titles, ahead of {other_name}'s {other_val}",
         "comparative"),
    ],
}

_RATIO_PAIRS = [
    ("points_scored", "wins", "points scored per win"),
    ("revenue_m", "attendance_avg", "revenue per fan in $M"),
    ("wins", "roster_size", "wins per roster spot"),
]


def _fmt(attr: str, val: Any) -> str:
    if attr == "revenue_m":
        return f"${val:,.1f}M"
    if attr == "win_pct":
        return f"{val:.3f}"
    if attr == "avg_age":
        return f"{val:.1f} yrs"
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)


class SportWorld(WorldTemplate):
    """Sports teams — 600 names × 10 attrs × 10 leagues."""

    @property
    def name(self) -> str:
        return "sport"

    @property
    def all_attr_defs(self) -> list[AttrDef]:
        return list(_ATTR_DEFS)

    @property
    def all_categories(self) -> list[str]:
        return list(_LEAGUES)

    @property
    def entity_word(self) -> str:
        return "team"

    def _generate_names(self, rng: Random, n: int) -> list[str]:
        pool = [(c, m) for c in _CITIES for m in _MASCOTS]
        selected = rng.sample(pool, min(n, len(pool)))
        return [f"{c} {m}" for c, m in selected]

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
        # Derive win_pct from wins/losses to avoid contradiction
        if "win_pct" in attrs and "wins" in attrs and "losses" in attrs:
            total = attrs["wins"] + attrs["losses"]
            attrs["win_pct"] = round(attrs["wins"] / total, 3) if total > 0 else 0.0
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
        style = rng.choice(["scouting", "stats", "preview", "recap"])
        header = {
            "scouting": (f"SCOUTING REPORT — {entity.name}\n"
                         f"League: {entity.category}\n"),
            "stats": (f"SEASON STATISTICS — {entity.name}\n"
                      f"Conference: {entity.category}\n"),
            "preview": (f"TEAM PREVIEW — {entity.name}\n"
                        f"Division: {entity.category}\n"),
            "recap": (f"PERFORMANCE RECAP — {entity.name}\n"
                      f"Competition: {entity.category}\n"),
        }[style]
        return header + self._render_body(
            entity, active_attrs, rng, other_entities)

    def render_correction(self, entity: EntitySpec, attr: str,
                          old_val: Any, new_val: Any) -> str:
        label = self.attr_label(attr)
        return (
            f"STAT CORRECTION: {_possessive(entity.name)} {label} has been "
            f"revised from {_fmt(attr, old_val)} to {_fmt(attr, new_val)} "
            f"after an official review."
        )

    def _q_text(self, attr: str, name: str,
                rng: Random | None = None) -> str:
        templates = _Q_TEXTS.get(attr, [f"What is {{name}}'s {attr}?"])
        tmpl = rng.choice(templates) if rng else templates[0]
        return tmpl.format(name=name)
