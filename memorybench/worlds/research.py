"""Research lab world template.

Entities: Researchers with 10 possible numeric attributes.
Names: 25 first × 25 last = 625 unique researchers.
Venues: 10 academic conferences.
Document styles: 4 narrative styles (~250 tokens each).
"""

from __future__ import annotations

from random import Random
from typing import Any

from memorybench.worlds.base import AttrDef, EntitySpec, WorldTemplate

_FIRST = [
    "Alice", "Bob", "Clara", "David", "Elena", "Frank", "Grace", "Henry",
    "Irene", "James", "Karen", "Leo", "Maria", "Nathan", "Olivia",
    "Peter", "Quinn", "Rachel", "Samuel", "Teresa", "Ursula", "Victor",
    "Wendy", "Xavier", "Yuki",
]

_LAST = [
    "Chen", "Kim", "Singh", "Mueller", "Santos", "Tanaka", "Park",
    "Nakamura", "Zhang", "Liu", "Patel", "Nguyen", "Ali", "Hansen",
    "Costa", "Rossi", "Wolf", "Berg", "Sato", "Lee",
    "Johansson", "Fischer", "Martin", "Clark", "Reed",
]

_VENUES = [
    "ICML", "NeurIPS", "ICLR", "AAAI", "CVPR",
    "ACL", "EMNLP", "KDD", "SIGIR", "WWW",
]

_ATTR_DEFS = [
    AttrDef("citations", "int", 10, 50000, "", "Citations"),
    AttrDef("h_index", "int", 1, 100, "", "H-index", agg_ops=("average",)),
    AttrDef("funding_k", "float", 10, 5000, "$K", "Funding"),
    AttrDef("students", "int", 0, 30, "", "Doctoral students"),
    AttrDef("review_score", "float", 1.0, 10.0, "", "Review score",
            agg_ops=("average",)),
    AttrDef("papers", "int", 5, 500, "", "Papers published"),
    AttrDef("patents", "int", 0, 50, "", "Patents held"),
    AttrDef("collaborators", "int", 2, 200, "", "Collaborators"),
    AttrDef("years_active", "int", 1, 40, "", "Years active"),
    AttrDef("awards", "int", 0, 25, "", "Awards received"),
]

_Q_TEXTS: dict[str, list[str]] = {
    "citations": [
        "How many citations does {name} have?",
        "What is {name}'s total citation count?",
        "How frequently is {name}'s work cited?",
    ],
    "h_index": [
        "What is {name}'s h-index?",
        "What h-index has {name} achieved?",
        "How high is {name}'s h-index?",
    ],
    "funding_k": [
        "How much research funding does {name} hold?",
        "What is {name}'s total grant funding?",
        "How much funding has {name} secured?",
    ],
    "students": [
        "How many doctoral students does {name} supervise?",
        "What is {name}'s PhD student count?",
        "How many PhD students work with {name}?",
    ],
    "review_score": [
        "What is {name}'s average review score?",
        "How do peers rate {name}'s review quality?",
        "What review score does {name} maintain?",
    ],
    "papers": [
        "How many papers has {name} published?",
        "What is {name}'s publication count?",
        "How many publications does {name} have?",
    ],
    "patents": [
        "How many patents does {name} hold?",
        "What is {name}'s patent count?",
    ],
    "collaborators": [
        "How many collaborators does {name} work with?",
        "What is the size of {name}'s collaboration network?",
    ],
    "years_active": [
        "How many years has {name} been active in research?",
        "What is {name}'s career length in years?",
    ],
    "awards": [
        "How many awards has {name} received?",
        "What is {name}'s award count?",
    ],
}


def _fmt(attr: str, val: Any) -> str:
    if attr == "funding_k":
        return f"${val:,.1f}K"
    if attr == "review_score":
        return f"{val:.1f}/10"
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)


class ResearchWorld(WorldTemplate):
    """Research domain — 625 names × 10 attrs × 10 venues."""

    @property
    def name(self) -> str:
        return "research"

    @property
    def all_attr_defs(self) -> list[AttrDef]:
        return list(_ATTR_DEFS)

    @property
    def all_categories(self) -> list[str]:
        return list(_VENUES)

    @property
    def entity_word(self) -> str:
        return "researcher"

    def _generate_names(self, rng: Random, n: int) -> list[str]:
        pool = [(f, l) for f in _FIRST for l in _LAST]
        selected = rng.sample(pool, min(n, len(pool)))
        return [f"{f} {l}" for f, l in selected]

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
        style = rng.choice(["bio", "profile", "news", "review"])
        header = {
            "bio": (f"RESEARCHER BIO — {entity.name}\n"
                    f"Venue: {entity.category}\n"),
            "profile": (f"RESEARCHER PROFILE — {entity.name}\n"
                        f"Affiliation: {entity.category}\n"),
            "news": (f"ACADEMIC SPOTLIGHT — {entity.name}\n"
                     f"Conference: {entity.category}\n"),
            "review": (f"PEER REVIEW SUMMARY — {entity.name}\n"
                       f"Primary venue: {entity.category}\n"),
        }[style]
        return header + self._compact_document(entity, active_attrs)

    def render_correction(self, entity: EntitySpec, attr: str,
                          old_val: Any, new_val: Any) -> str:
        label = self.attr_label(attr)
        return (
            f"CORRECTION: {entity.name}'s {label} has been updated "
            f"from {_fmt(attr, old_val)} to {_fmt(attr, new_val)} "
            f"following a data reconciliation."
        )

    def _q_text(self, attr: str, name: str,
                rng: Random | None = None) -> str:
        templates = _Q_TEXTS.get(attr, [f"What is {{name}}'s {attr}?"])
        tmpl = rng.choice(templates) if rng else templates[0]
        return tmpl.format(name=name)
