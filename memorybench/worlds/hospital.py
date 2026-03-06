"""Hospital/healthcare world template.

Entities: Hospitals with operational and quality metrics.
Names: 30 adjectives × 20 nouns = 600 unique hospitals.
Specialties: 10 medical specialties.
Document styles: 4 narrative styles (~250 tokens each).

Design pressures:
- Mix of rate attrs (readmission_pct, mortality_rate) and count attrs (beds, staff)
- "Lower is better" attrs (mortality_rate, wait_time_min) vs "higher is better" (satisfaction)
- Wide scale: beds [10, 2000] vs mortality_rate [0.1, 5.0]
"""

from __future__ import annotations

from random import Random
from typing import Any

from memorybench.worlds.base import (
    AttrDef, EntitySpec, SentenceTemplate, WorldTemplate, _possessive,
)

_ADJECTIVES = [
    "Central", "Memorial", "Regional", "General", "Community", "University",
    "Sacred", "Providence", "Mercy", "Grace", "Summit", "Valley",
    "Lakeside", "Riverside", "Highland", "Coastal", "Prairie", "Mountain",
    "Heritage", "Pioneer", "Beacon", "Horizon", "Northside", "Southgate",
    "Evergreen", "Golden", "Silver", "Pacific", "Atlantic", "Harbor",
]

_NOUNS = [
    "Hospital", "Medical Center", "Health System", "Clinic",
    "Medical Campus", "Care Center", "Health Center", "Institute",
    "Medical Group", "Healthcare", "Infirmary", "Sanatorium",
    "Medical Plaza", "Health Network", "Treatment Center",
    "Wellness Center", "Medical Hub", "Care Campus",
    "Health Alliance", "Medical Park",
]

_SPECIALTIES = [
    "Cardiology", "Oncology", "Neurology", "Orthopedics", "Pediatrics",
    "Emergency Medicine", "Surgery", "Internal Medicine",
    "Obstetrics", "Psychiatry",
]

_ATTR_DEFS = [
    AttrDef("beds", "int", 10, 2000, "", "Beds"),
    AttrDef("staff_count", "int", 50, 15000, "", "Staff"),
    AttrDef("annual_patients", "int", 1000, 500000, "", "Annual patients"),
    AttrDef("readmission_pct", "float", 1.0, 25.0, "%", "Readmission rate",
            agg_ops=("average",)),
    AttrDef("mortality_rate", "float", 0.1, 5.0, "%", "Mortality rate",
            agg_ops=("average",)),
    AttrDef("satisfaction_score", "float", 1.0, 10.0, "/10",
            "Patient satisfaction", agg_ops=("average",)),
    AttrDef("wait_time_min", "int", 5, 300, "min", "Average wait time"),
    AttrDef("operating_rooms", "int", 1, 80, "", "Operating rooms"),
    AttrDef("budget_m", "float", 5.0, 5000.0, "$M", "Annual budget"),
    AttrDef("accreditation_year", "int", 1990, 2025, "", "Accreditation year"),
]

_Q_TEXTS: dict[str, list[str]] = {
    "beds": [
        "How many beds does {name} have?",
        "What is {name}'s total bed capacity?",
        "How many patient beds are available at {name}?",
    ],
    "staff_count": [
        "How many staff members work at {name}?",
        "What is {name}'s total staffing level?",
        "How large is {name}'s workforce?",
    ],
    "annual_patients": [
        "How many patients does {name} treat annually?",
        "What is {name}'s annual patient volume?",
        "How many patients visit {name} each year?",
    ],
    "readmission_pct": [
        "What is {name}'s readmission rate?",
        "What percentage of patients are readmitted at {name}?",
        "How high is the readmission rate at {name}?",
    ],
    "mortality_rate": [
        "What is {name}'s mortality rate?",
        "What mortality rate does {name} report?",
        "How high is {name}'s patient mortality rate?",
    ],
    "satisfaction_score": [
        "What is {name}'s patient satisfaction score?",
        "How do patients rate {name}?",
        "What satisfaction rating does {name} maintain?",
    ],
    "wait_time_min": [
        "What is the average wait time at {name}?",
        "How long do patients wait at {name}?",
        "What is {name}'s average waiting time in minutes?",
    ],
    "operating_rooms": [
        "How many operating rooms does {name} have?",
        "What is {name}'s OR capacity?",
        "How many surgical suites are at {name}?",
    ],
    "budget_m": [
        "What is {name}'s annual budget?",
        "How much is {name}'s operating budget?",
        "What budget does {name} operate with?",
    ],
    "accreditation_year": [
        "When was {name} last accredited?",
        "In what year did {name} receive accreditation?",
        "What year was {name}'s accreditation awarded?",
    ],
}


_SENTENCE_TMPLS: dict[str, list[tuple[str, str]]] = {
    "beds": [
        ("has a capacity of {val} patient beds", "none"),
        ("bed count increased from {distractor} to {val}", "temporal"),
        ("operates {val} beds, though only {distractor} are currently "
         "staffed", "qualified"),
    ],
    "staff_count": [
        ("employs {val} medical and administrative staff", "none"),
        ("staffing grew from {distractor} to {val}", "temporal"),
        ("has {val} total staff, compared to {other_name}'s {other_val}",
         "comparative"),
    ],
    "annual_patients": [
        ("treats {val} patients annually", "none"),
        ("patient volume rose from {distractor} to {val}", "temporal"),
        ("sees {val} patients per year, of which {distractor} are "
         "outpatient", "qualified"),
    ],
    "readmission_pct": [
        ("reports a readmission rate of {val}", "none"),
        ("readmission rate changed from {distractor} to {val}", "temporal"),
        ("has {val} readmission rate, versus {other_name}'s {other_val}",
         "comparative"),
    ],
    "mortality_rate": [
        ("maintains a mortality rate of {val}", "none"),
        ("mortality rate shifted from {distractor} to {val}", "temporal"),
        ("records {val} mortality, compared to {other_name}'s "
         "{other_val}", "comparative"),
    ],
    "satisfaction_score": [
        ("earned a patient satisfaction score of {val}", "none"),
        ("satisfaction improved from {distractor} to {val}", "temporal"),
        ("rated {val} by patients, outperforming {other_name} at "
         "{other_val}", "comparative"),
    ],
    "wait_time_min": [
        ("has an average wait time of {val}", "none"),
        ("wait times changed from {distractor} to {val}", "temporal"),
        ("averages {val} wait, though emergency cases wait only "
         "{distractor}", "qualified"),
    ],
    "operating_rooms": [
        ("is equipped with {val} operating rooms", "none"),
        ("OR count grew from {distractor} to {val}", "temporal"),
        ("has {val} operating rooms, of which {distractor} are for "
         "outpatient procedures", "qualified"),
    ],
    "budget_m": [
        ("operates with an annual budget of {val}", "none"),
        ("budget increased from {distractor} to {val}", "temporal"),
        ("runs on {val}, compared to {other_name}'s {other_val}",
         "comparative"),
    ],
    "accreditation_year": [
        ("received its most recent accreditation in {val}", "none"),
        ("was accredited in {val}, updating from {distractor}", "temporal"),
        ("accredited in {val}, alongside {other_name}", "comparative"),
    ],
}

_RATIO_PAIRS = [
    ("annual_patients", "beds", "patients per bed"),
    ("staff_count", "beds", "staff per bed"),
    ("budget_m", "annual_patients", "budget per patient in $M"),
]


def _fmt(attr: str, val: Any) -> str:
    if attr == "budget_m":
        return f"${val:,.1f}M"
    if attr in ("readmission_pct", "mortality_rate"):
        return f"{val:.2f}%"
    if attr == "satisfaction_score":
        return f"{val:.2f}/10"
    if attr == "wait_time_min":
        return f"{val} min"
    if attr == "accreditation_year":
        return str(val)
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)


class HospitalWorld(WorldTemplate):
    """Hospital operations — 600 names × 10 attrs × 10 specialties."""

    @property
    def name(self) -> str:
        return "hospital"

    @property
    def all_attr_defs(self) -> list[AttrDef]:
        return list(_ATTR_DEFS)

    @property
    def all_categories(self) -> list[str]:
        return list(_SPECIALTIES)

    @property
    def entity_word(self) -> str:
        return "hospital"

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
        style = rng.choice(["accreditation", "annual", "quality", "summary"])
        header = {
            "accreditation": (f"ACCREDITATION REPORT — {entity.name}\n"
                              f"Specialty: {entity.category}\n"),
            "annual": (f"ANNUAL PERFORMANCE REVIEW — {entity.name}\n"
                       f"Department: {entity.category}\n"),
            "quality": (f"QUALITY METRICS REPORT — {entity.name}\n"
                        f"Primary service: {entity.category}\n"),
            "summary": (f"FACILITY DATA SUMMARY — {entity.name}\n"
                        f"Focus area: {entity.category}\n"),
        }[style]
        return header + self._render_body(
            entity, active_attrs, rng, other_entities)

    def render_correction(self, entity: EntitySpec, attr: str,
                          old_val: Any, new_val: Any) -> str:
        label = self.attr_label(attr)
        return (
            f"DATA UPDATE: {_possessive(entity.name)} {label} has been "
            f"corrected from {_fmt(attr, old_val)} to {_fmt(attr, new_val)} "
            f"following a quality review."
        )

    def _q_text(self, attr: str, name: str,
                rng: Random | None = None) -> str:
        templates = _Q_TEXTS.get(attr, [f"What is {{name}}'s {attr}?"])
        tmpl = rng.choice(templates) if rng else templates[0]
        return tmpl.format(name=name)
