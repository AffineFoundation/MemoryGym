"""Organization domain: employees, departments, HR data."""

from __future__ import annotations

import random

from memorybench.domains.base import Distractor, Domain, Entity
from memorybench.domains.names import person_name_pool

PROJECT_NAMES = [
    "Aurora", "Beacon", "Catalyst", "Dynamo", "Eclipse",
    "Frontier", "Genesis", "Horizon", "Impulse", "Keystone",
    "Lighthouse", "Meridian", "Nexus", "Olympus", "Pinnacle",
]
PROJECT_STATUSES = ["active", "planning", "on-hold", "completed", "review"]
MEETING_TYPES = [
    "Quarterly Review", "Sprint Planning", "Budget Alignment",
    "Strategy Workshop", "Team Sync", "Performance Calibration",
]


class OrgDomain(Domain):
    name = "organization"
    ALL_ATTRS = ["salary", "age", "performance", "experience", "team_size"]
    SYNTHESIS_ENTITY_WORD = "person"
    GROUP_NAMES = [
        "Quantum Systems", "Applied Dynamics", "Integrated Analytics",
        "Neural Computing", "Resonance Engineering",
    ]
    ATTR_SYNONYMS = {
        "salary": {"salary", "earn", "compensation", "$", "annually", "pay"},
        "age": {"age", "old", "years old", "born"},
        "performance": {"performance", "score", "rated", "review score",
                        "performance=", "rating"},
        "experience": {"experience", "years of experience", "tenure",
                       "veteran", "experience=", "been working"},
        "team_size": {"team_size", "team of", "leads a team",
                      "manages a group", "team size", "team_size=",
                      "members", "manage", "headcount", "people",
                      "how large", "size"},
    }
    DOC_TEMPLATES = [
        "{name}, a specialist in the {group} department, {details}.",
        "According to internal records, {name} serves in {group}. {details}.",
        "Within the {group} division, {name} {details}.",
    ]
    BACKGROUND = [
        "The quarterly review process involves multiple stages of assessment "
        "across all divisions of the organization.",
        "Internal communications indicate ongoing restructuring efforts aimed "
        "at improving operational efficiency across departments.",
        "Recent policy updates affect compensation structures and performance "
        "evaluation criteria organization-wide.",
    ]

    def generate_kb(self, seed: int, n_entities: int = 20) -> dict:
        rng = random.Random(seed)
        active, primary = self._select_schema(seed)
        pool = person_name_pool(rng, n_entities)
        entities = []
        for _ in range(n_entities):
            attrs = {}
            if "salary" in active:
                attrs["salary"] = rng.randint(40, 200) * 1000
            if "age" in active:
                attrs["age"] = rng.randint(25, 60)
            if "performance" in active:
                attrs["performance"] = round(rng.uniform(1.5, 5.0), 1)
            if "experience" in active:
                attrs["experience"] = rng.randint(1, 30)
            if "team_size" in active:
                attrs["team_size"] = rng.randint(2, 15)
            entities.append(Entity(
                pool.pop(), rng.choice(self.GROUP_NAMES), attrs,
            ))
        rng.shuffle(entities)
        return {"entities": entities, "active_attrs": active,
                "primary_attr": primary}

    def _render_details(self, e: Entity, active_attrs: list[str]) -> str:
        parts = []
        a = e.attrs
        if "salary" in active_attrs and a.get("salary"):
            parts.append(f"earns ${a['salary']:,} annually")
        if "age" in active_attrs and a.get("age"):
            parts.append(f"is {a['age']} years old")
        if "performance" in active_attrs and a.get("performance"):
            parts.append(f"received a performance score of {a['performance']}")
        if "experience" in active_attrs and a.get("experience"):
            parts.append(f"has {a['experience']} years of experience")
        if "team_size" in active_attrs and a.get("team_size"):
            parts.append(f"leads a team of {a['team_size']}")
        return self._render_detail_list(parts) or "is a valued team member"

    def render_entity_doc(self, entity, active_attrs, rng):
        tmpl = rng.choice(self.DOC_TEMPLATES)
        return tmpl.format(name=entity.name, group=entity.group,
                           details=self._render_details(entity, active_attrs))

    def render_correction(self, entity, attr, old_val, new_val):
        labels = {
            "salary": f"compensation revised from ${old_val:,} to ${new_val:,}",
            "age": f"age corrected from {old_val} to {new_val}",
            "performance": f"performance score updated from {old_val} to {new_val}",
            "experience": f"experience corrected from {old_val} to {new_val} years",
            "team_size": f"team size updated from {old_val} to {new_val}",
        }
        detail = labels.get(attr, f"{attr} changed from {old_val} to {new_val}")
        return f"CORRECTION NOTICE: {entity.name}'s {detail} per latest audit."

    def generate_distractors(self, rng, entities, n=10):
        distractors = []
        for _ in range(min(n, len(entities))):
            lead = rng.choice(entities)
            if rng.random() < 0.6:
                proj_name = rng.choice(PROJECT_NAMES) + f"-{rng.randint(100,999)}"
                text = (
                    f"Project Brief: {proj_name}\n"
                    f"  Lead: {lead.name} | Department: {lead.group}\n"
                    f"  Budget: ${rng.randint(50,500)*1000:,} | "
                    f"Status: {rng.choice(PROJECT_STATUSES)}\n"
                    f"  Team size: {rng.randint(3,20)} members"
                )
            else:
                text = (
                    f"Meeting Notice: {rng.choice(MEETING_TYPES)} "
                    f"— {lead.group}\n"
                    f"  Organized by: {lead.name}\n"
                    f"  Date: 2024-{rng.randint(1,12):02d}-"
                    f"{rng.randint(1,28):02d} | "
                    f"Duration: {rng.choice([1,2,3,4])}h\n"
                    f"  Expected attendees: {rng.randint(5,30)}"
                )
            distractors.append(Distractor(text))
        return distractors

    def _q_text(self, attr, name, rng=None):
        phrasings = {
            "salary": [
                f"What is {name}'s annual salary?",
                f"How much does {name} earn?",
                f"Tell me {name}'s compensation.",
                f"What is the yearly pay for {name}?",
                f"How much is {name} paid annually?",
                f"What compensation does {name} receive?",
                f"Report {name}'s salary figure.",
            ],
            "age": [
                f"How old is {name}?",
                f"What is {name}'s age?",
                f"Tell me how old {name} is.",
                f"What age is {name}?",
                f"How many years old is {name}?",
            ],
            "performance": [
                f"What performance score did {name} receive?",
                f"What is {name}'s performance rating?",
                f"How was {name} rated in the last review?",
                f"Tell me {name}'s review score.",
                f"What rating did {name} get?",
                f"How did {name} score in performance evaluation?",
            ],
            "experience": [
                f"How many years of experience does {name} have?",
                f"What is {name}'s experience level in years?",
                f"How long has {name} been working?",
                f"Tell me {name}'s years of tenure.",
                f"What is {name}'s professional experience duration?",
            ],
            "team_size": [
                f"How many people are on {name}'s team?",
                f"What is the size of {name}'s team?",
                f"How large is the team {name} leads?",
                f"How many members does {name} manage?",
                f"Tell me the headcount of {name}'s group.",
            ],
        }
        opts = phrasings[attr]
        return rng.choice(opts) if rng else opts[0]

