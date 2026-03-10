"""Sports team world template.

Entities: Sports teams with 23 possible attributes (16 numeric + text + 2 enum + date + 3 list_float).
Names: 30 city-like words x 20 mascots = 600 unique teams.
Leagues: 10 sports leagues.
Document styles: 4 narrative styles (~250 tokens each).

Design pressures:
- Mix of percentage (win_pct) and count (roster_size) attrs
- Large range differences: revenue [1M, 5000M] vs roster_size [15, 60]
- "Lower is better" (avg_age for rebuilding) ambiguity tests comprehension
- New dtypes: list_float trends, enum categories, date, text history
"""

from __future__ import annotations

from random import Random
from typing import Any

from .base import (
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

_TEAM_HISTORIES = [
    "Founded as a community club before rising through the ranks to professional status.",
    "Originally a factory workers' team that grew into a regional powerhouse.",
    "Emerged from a merger of two struggling franchises to form a competitive unit.",
    "Started as a college exhibition squad before attracting professional sponsorship.",
    "Built from scratch by a billionaire owner with a vision for championship glory.",
    "Relocated from a smaller market after decades of declining attendance.",
    "Rose from the development league to earn a permanent spot in the top division.",
    "Has a storied tradition of developing young talent through its academy system.",
    "Known for its defensive identity established by a legendary head coach.",
    "Survived a near-bankruptcy in the 1990s to become a financially stable franchise.",
    "Carries a legacy of innovation, having pioneered analytics-driven roster construction.",
    "Built its dynasty around a core of homegrown players who stayed for their entire careers.",
    "Has changed ownership five times, each era bringing a distinct playing philosophy.",
    "Famous for its passionate fan base that consistently sells out home games.",
    "Underwent a complete rebuild after trading away all veteran players for draft capital.",
    "Maintains a fierce cross-town rivalry that defines the local sports culture.",
    "Won its first championship after decades of heartbreaking playoff exits.",
    "Known for blockbuster trades and free-agent signings that reshape the roster annually.",
    "Operates one of the most respected scouting networks in professional sports.",
    "Has a tradition of hiring innovative coaches who later become legends elsewhere.",
]

_ATTR_DEFS = [
    # Original numeric attrs
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
    # New numeric attrs
    AttrDef("playoff_appearances", "int", 0, 30, "", "Playoff appearances"),
    AttrDef("draft_picks", "int", 0, 50, "", "Draft picks"),
    AttrDef("salary_cap_m", "float", 50.0, 300.0, "$M", "Salary cap",
            agg_ops=("average",)),
    AttrDef("social_media_followers", "int", 10000, 5000000, "",
            "Social media followers"),
    AttrDef("stadium_capacity", "int", 10000, 80000, "", "Stadium capacity"),
    AttrDef("injury_count", "int", 0, 30, "", "Injury count"),
    # New dtype attrs
    AttrDef("season_wins", "list_float", min_val=0, max_val=100,
            list_len=5, label="Season wins (last 5)"),
    AttrDef("season_revenue", "list_float", min_val=10, max_val=500,
            list_len=5, label="Season revenue ($M, last 5)"),
    AttrDef("attendance_trend", "list_float", min_val=5000, max_val=60000,
            list_len=5, label="Avg attendance (last 5 seasons)"),
    AttrDef("division", "enum", label="Division",
            choices=["East", "West", "North", "South", "Central"]),
    AttrDef("tier", "enum", label="Tier",
            choices=["major", "minor", "development"]),
    AttrDef("last_championship_date", "date", min_val=1950, max_val=2025,
            label="Last championship date"),
    AttrDef("team_history", "text", label="Team history",
            text_pool=_TEAM_HISTORIES),
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
    # New numeric attrs
    "playoff_appearances": [
        "How many playoff appearances have the {name} made?",
        "What is the {name}'s playoff appearance count?",
        "How many times have the {name} reached the playoffs?",
    ],
    "draft_picks": [
        "How many draft picks do the {name} have?",
        "What is the {name}'s total draft pick count?",
        "How many players have the {name} drafted?",
    ],
    "salary_cap_m": [
        "What is the {name}'s salary cap?",
        "How much salary cap space do the {name} have?",
        "What is the {name}'s total payroll cap?",
    ],
    "social_media_followers": [
        "How many social media followers do the {name} have?",
        "What is the {name}'s social media following?",
        "How large is the {name}'s online fan base?",
    ],
    "stadium_capacity": [
        "What is the {name}'s stadium capacity?",
        "How many seats does the {name}'s stadium hold?",
        "What is the seating capacity of the {name}'s arena?",
    ],
    "injury_count": [
        "How many injuries have the {name} had this season?",
        "What is the {name}'s injury count?",
        "How many players on the {name} are injured?",
    ],
    # New dtype attrs
    "season_wins": [
        "What are the {name}'s season win totals for the last 5 seasons?",
        "List the {name}'s wins over the past 5 seasons.",
    ],
    "season_revenue": [
        "What are the {name}'s revenue figures for the last 5 seasons?",
        "List the {name}'s season-by-season revenue ($M, last 5).",
    ],
    "attendance_trend": [
        "What is the {name}'s average attendance over the last 5 seasons?",
        "List the {name}'s attendance figures for the past 5 seasons.",
    ],
    "division": [
        "What division do the {name} play in?",
        "Which division are the {name} assigned to?",
    ],
    "tier": [
        "What tier are the {name} classified in?",
        "What competitive tier do the {name} belong to?",
    ],
    "last_championship_date": [
        "When did the {name} last win a championship?",
        "What is the date of the {name}'s most recent title?",
    ],
    "team_history": [
        "Describe the {name}'s team history.",
        "What is the background of the {name} franchise?",
        "Tell me about the {name}'s origins and history.",
    ],
}


_SENTENCE_TMPLS: dict[str, list[tuple[str, str]]] = {
    "wins": [
        ("recorded {val} wins this season", "none"),
        ("win counts of {val} and {distractor} across seasons",
         "temporal"),
        ("win tallies of {other_val} and {val} from different "
         "records", "comparative"),
    ],
    "losses": [
        ("suffered {val} losses on the season", "none"),
        ("loss counts of {distractor} and {val} in successive seasons",
         "temporal"),
        ("loss figures of {val} and {other_val} from separate "
         "tallies", "comparative"),
    ],
    "win_pct": [
        ("holds a winning percentage of {val}", "none"),
        ("win rate figures of {val} and {distractor} across periods",
         "temporal"),
        ("win percentages of {other_val} and {val} from different "
         "sources", "comparative"),
    ],
    "points_scored": [
        ("put up {val} points on offense", "none"),
        ("scoring figures of {distractor} and {val} points in different "
         "periods", "temporal"),
        ("point totals of {val} and {distractor} by different counting "
         "methods", "qualified"),
    ],
    "points_allowed": [
        ("allowed {val} points defensively", "none"),
        ("points allowed readings of {val} and {distractor} across "
         "seasons", "temporal"),
        ("defensive point figures of {other_val} and {val} from separate "
         "analyses", "comparative"),
    ],
    "roster_size": [
        ("carries {val} players on the active roster", "none"),
        ("roster counts of {distractor} and {val} players in different "
         "periods", "temporal"),
        ("roster figures of {val} and {distractor} under different "
         "classifications", "qualified"),
    ],
    "avg_age": [
        ("fields a squad with an average age of {val}", "none"),
        ("average age figures of {val} and {distractor} across seasons",
         "temporal"),
        ("average age readings of {val} and {other_val} from different "
         "rosters", "comparative"),
    ],
    "revenue_m": [
        ("generated {val} in total revenue", "none"),
        ("revenue figures of {distractor} and {val} in successive "
         "periods", "temporal"),
        ("revenue amounts of {val} and {other_val} from separate "
         "reports", "comparative"),
    ],
    "attendance_avg": [
        ("draws an average crowd of {val} per game", "none"),
        ("attendance figures of {val} and {distractor} across seasons",
         "temporal"),
        ("attendance counts of {other_val} and {val} from different "
         "sources", "comparative"),
    ],
    "championships": [
        ("has won {val} championships in franchise history", "none"),
        ("championship counts of {distractor} and {val} in different "
         "records", "temporal"),
        ("title counts of {val} and {other_val} from separate "
         "databases", "comparative"),
    ],
    # New numeric attrs
    "playoff_appearances": [
        ("has made {val} playoff appearances", "none"),
        ("playoff appearance counts of {val} and {distractor} across "
         "eras", "temporal"),
        ("playoff figures of {other_val} and {val} from different "
         "records", "comparative"),
    ],
    "draft_picks": [
        ("holds {val} draft picks in total", "none"),
        ("draft pick counts of {distractor} and {val} in different "
         "tallies", "temporal"),
    ],
    "salary_cap_m": [
        ("operates under a salary cap of {val}", "none"),
        ("salary cap figures of {val} and {distractor} across years",
         "temporal"),
        ("payroll amounts of {val} and {other_val} from separate "
         "filings", "comparative"),
    ],
    "social_media_followers": [
        ("boasts {val} social media followers", "none"),
        ("follower counts of {distractor} and {val} across platforms",
         "temporal"),
    ],
    "stadium_capacity": [
        ("plays in a stadium seating {val}", "none"),
        ("stadium capacity figures of {val} and {distractor} in different "
         "reports", "temporal"),
    ],
    "injury_count": [
        ("has dealt with {val} injuries this season", "none"),
        ("injury counts of {distractor} and {val} in successive "
         "periods", "temporal"),
    ],
    # New dtype attrs
    "season_wins": [
        ("posted season win totals of {val} over the last five years", "none"),
    ],
    "season_revenue": [
        ("reported season revenues of {val} over the past five years", "none"),
    ],
    "attendance_trend": [
        ("averaged attendance figures of {val} across the last five seasons",
         "none"),
    ],
    "division": [
        ("competes in the {val} division", "none"),
    ],
    "tier": [
        ("is classified as a {val} tier franchise", "none"),
    ],
    "last_championship_date": [
        ("last won a championship on {val}", "none"),
    ],
    "team_history": [
        ("{val}", "none"),
    ],
}

_RATIO_PAIRS = [
    ("points_scored", "wins", "points scored per win"),
    ("revenue_m", "attendance_avg", "revenue per fan in $M"),
    ("wins", "roster_size", "wins per roster spot"),
    ("salary_cap_m", "roster_size", "salary cap per roster spot in $M"),
    ("revenue_m", "social_media_followers", "revenue per follower in $M"),
    ("stadium_capacity", "attendance_avg", "capacity utilization ratio"),
]


def _fmt(attr: str, val: Any) -> str:
    if attr in ("revenue_m", "salary_cap_m"):
        return f"${val:,.1f}M" if isinstance(val, (int, float)) else str(val)
    if attr == "win_pct":
        return f"{val:.3f}"
    if attr == "avg_age":
        return f"{val:.1f} yrs"
    if attr in ("social_media_followers", "stadium_capacity",
                "attendance_avg"):
        return f"{val:,}" if isinstance(val, (int, float)) else str(val)
    if attr == "season_revenue" and isinstance(val, list):
        return ", ".join(f"${v:,.1f}M" for v in val)
    if attr in ("season_wins", "attendance_trend") and isinstance(val, list):
        return ", ".join(f"{v:,.1f}" for v in val)
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)


class SportWorld(WorldTemplate):
    """Sports teams — 600 names x 23 attrs x 10 leagues."""

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

    @property
    def correction_rate(self) -> float:
        return 0.12  # high — frequent stat updates

    @property
    def correction_timing(self) -> tuple[float, float]:
        return (0.3, 0.6)  # mid-early corrections

    @property
    def question_weights(self) -> dict[str, float]:
        return {
            "retrieval": 0.35,
            "comprehension": 0.25,
            "update": 0.25,          # high — frequent stat updates
            "abstention": 0.15,
        }

    def _generate_names(self, rng: Random, n: int) -> list[str]:
        pool = [(c, m) for c in _CITIES for m in _MASCOTS]
        selected = rng.sample(pool, min(n, len(pool)))
        return [f"{c} {m}" for c, m in selected]

    def _generate_list_float(self, adef, rng):
        """Streak pattern: high volatility with momentum (win/loss streaks)."""
        val = rng.uniform(adef.min_val * 0.2, adef.max_val * 0.8)
        momentum = 0.0
        values = []
        for _ in range(adef.list_len):
            # Momentum carries forward (streaks), but can reverse sharply
            if rng.random() < 0.3:
                momentum = rng.uniform(-0.3, 0.3) * val  # reversal
            else:
                momentum *= rng.uniform(0.5, 1.5)  # momentum persists
            change = momentum + rng.uniform(-0.15, 0.15) * val
            val = max(adef.min_val, min(adef.max_val, val + change))
            values.append(round(val, 2))
        return values

    def generate_entity(self, rng: Random, name: str, category: str,
                        active_attrs: list[str]) -> EntitySpec:
        attrs: dict[str, Any] = {}
        for adef in _ATTR_DEFS:
            if adef.name not in active_attrs:
                continue
            attrs[adef.name] = self._generate_attr_value(rng, adef)
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

    def _relationship_types(self):
        return [
            ("rival_of", "is a rival of", True),
            ("farm_team_of", "is a farm team of", False),
        ]

    def render_relationship(self, rel):
        if rel.relation == "rival_of":
            return (f"{rel.source} and {rel.target} have a historic "
                    f"rivalry spanning multiple seasons.")
        if rel.relation == "farm_team_of":
            return (f"{rel.source} serves as the developmental affiliate "
                    f"of {rel.target}.")
        return super().render_relationship(rel)

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
