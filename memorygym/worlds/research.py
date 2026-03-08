"""Research lab world template.

Entities: Researchers with 10 possible numeric attributes.
Names: 25 first × 25 last = 625 unique researchers.
Venues: 10 academic conferences.
Document styles: 4 narrative styles (~250 tokens each).
"""

from __future__ import annotations

from random import Random
from typing import Any

from memorygym.worlds.base import (
    AttrDef, EntitySpec, SentenceTemplate, WorldTemplate, _possessive,
)

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


_SENTENCE_TMPLS: dict[str, list[tuple[str, str]]] = {
    "citations": [
        ("has accumulated {val} citations across all publications", "none"),
        ("citation count grew from {distractor} to {val} this year",
         "temporal"),
        ("holds {val} total citations, outpacing {other_name} at "
         "{other_val}", "comparative"),
    ],
    "h_index": [
        ("maintains an h-index of {val}", "none"),
        ("h-index improved from {distractor} to {val} following recent "
         "publications", "temporal"),
        ("achieved an h-index of {val}, compared to {other_name}'s "
         "{other_val}", "comparative"),
    ],
    "funding_k": [
        ("holds {val} in active research funding", "none"),
        ("secured funding growth from {distractor} to {val}", "temporal"),
        ("manages {val} in grants, though only {distractor} is for current "
         "projects", "qualified"),
    ],
    "students": [
        ("supervises {val} doctoral students", "none"),
        ("student count rose from {distractor} to {val}", "temporal"),
        ("advises {val} PhD students, with {distractor} expected to "
         "graduate this year", "qualified"),
    ],
    "review_score": [
        ("earned an average review score of {val}", "none"),
        ("review scores improved from {distractor} to {val}", "temporal"),
        ("rated {val} by peers, versus {other_name}'s {other_val}",
         "comparative"),
    ],
    "papers": [
        ("has published {val} peer-reviewed papers", "none"),
        ("publication count increased from {distractor} to {val}",
         "temporal"),
        ("authored {val} papers, of which {distractor} are first-author",
         "qualified"),
    ],
    "patents": [
        ("holds {val} patents from research innovations", "none"),
        ("patent portfolio grew from {distractor} to {val}", "temporal"),
        ("owns {val} patents, compared to {other_name}'s {other_val}",
         "comparative"),
    ],
    "collaborators": [
        ("works with {val} research collaborators", "none"),
        ("collaboration network expanded from {distractor} to {val}",
         "temporal"),
        ("maintains {val} collaborators, though only {distractor} are "
         "active this year", "qualified"),
    ],
    "years_active": [
        ("has been active in research for {val} years", "none"),
        ("career spans {val} years in the field", "none"),
        ("active for {val} years, compared to {other_name}'s {other_val}",
         "comparative"),
    ],
    "awards": [
        ("has received {val} academic awards", "none"),
        ("award count rose from {distractor} to {val}", "temporal"),
        ("earned {val} awards, surpassing {other_name}'s {other_val}",
         "comparative"),
    ],
}

_RATIO_PAIRS = [
    ("citations", "papers", "citations per paper"),
    ("funding_k", "students", "funding per student in $K"),
    ("papers", "years_active", "papers per year"),
]


def _fmt(attr: str, val: Any) -> str:
    if attr == "funding_k":
        return f"${val:,.1f}K"
    if attr == "review_score":
        return f"{val:.2f}/10"
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
        # Constrain citations to be consistent with h_index
        # h_index=h means h papers with ≥h citations each → min citations ≈ h²
        if "h_index" in attrs and "citations" in attrs:
            h = attrs["h_index"]
            min_cites = h * h
            max_cites = h * h * 15  # realistic upper bound
            max_cites = min(max_cites, 50000)
            attrs["citations"] = rng.randint(
                max(10, min_cites), max(min_cites + 1, max_cites))
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
            ("collaborates_with", "collaborates with", True),
            ("advised_by", "is advised by", False),
        ]

    def render_relationship(self, rel):
        if rel.relation == "collaborates_with":
            return (f"{rel.source} and {rel.target} have co-authored "
                    f"multiple papers together.")
        if rel.relation == "advised_by":
            return (f"{rel.source} completed doctoral work under the "
                    f"supervision of {rel.target}.")
        return super().render_relationship(rel)

    def render_document(self, entity: EntitySpec,
                        active_attrs: list[str], rng: Random,
                        other_entities: list[EntitySpec] | None = None
                        ) -> str:
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
        return header + self._render_body(
            entity, active_attrs, rng, other_entities)

    def render_correction(self, entity: EntitySpec, attr: str,
                          old_val: Any, new_val: Any) -> str:
        label = self.attr_label(attr)
        return (
            f"CORRECTION: {_possessive(entity.name)} {label} has been updated "
            f"from {_fmt(attr, old_val)} to {_fmt(attr, new_val)} "
            f"following a data reconciliation."
        )

    def _q_text(self, attr: str, name: str,
                rng: Random | None = None) -> str:
        templates = _Q_TEXTS.get(attr, [f"What is {{name}}'s {attr}?"])
        tmpl = rng.choice(templates) if rng else templates[0]
        return tmpl.format(name=name)
