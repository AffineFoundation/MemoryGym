"""University/higher-education world template.

Entities: Universities with 23 possible attributes (16 numeric + 2 text + 2 enum + 2 list_float + 1 date).
Names: 30 place-words × 20 institution-words = 600 unique universities.
Categories: 8 institution types.
Document styles: 4 narrative styles (~250 tokens each).

Design pressures on base class:
- "Lower is better" attrs (acceptance_rate_pct, student_faculty_ratio) alongside "higher is better" (endowment_b)
- Tightly coupled constraints (enrollment ↔ faculty_count ↔ student_faculty_ratio)
- Two list_float attrs with different temporal patterns (enrollment vs research output)
- Extreme scale range (endowment 0.01B vs alumni 500K vs acceptance 5%)
"""

from __future__ import annotations

from random import Random
from typing import Any

from .base import (
    AttrDef, EntitySpec, SentenceTemplate, WorldTemplate,
    _possessive,
)

_PLACE_WORDS = [
    "Ashford", "Beckham", "Carlisle", "Drayton", "Elmswood",
    "Fairhaven", "Glenfield", "Hartsdale", "Ironbridge", "Kingsport",
    "Lakehurst", "Montclair", "Northwell", "Oakmont", "Pemberton",
    "Queensbury", "Redcliff", "Stonewall", "Thornbury", "Upton",
    "Valecrest", "Whitfield", "Yarborough", "Alderton", "Bramwell",
    "Clarendon", "Dunmore", "Edgeworth", "Foxhall", "Greystone",
]

_INST_WORDS = [
    "University", "College", "Institute", "Academy", "Polytechnic",
    "School", "Seminary", "Conservatory", "Foundation", "Lyceum",
    "Athenaeum", "Faculty", "Campus", "Center", "Hall",
    "Collegium", "Forum", "Guild", "Commons", "Priory",
]

_CATEGORIES = [
    "Liberal Arts", "Engineering", "Research", "Medical",
    "Business", "Comprehensive", "Arts & Design", "Community",
]

_MISSION_STATEMENTS = [
    "dedicated to fostering critical thinking and ethical leadership through a rigorous liberal arts curriculum",
    "committed to advancing STEM innovation and preparing graduates for careers in technology and engineering",
    "focused on interdisciplinary research that addresses global challenges from climate change to public health",
    "nurturing creative expression and design thinking through hands-on studio-based learning environments",
    "providing accessible and affordable education to first-generation college students and working adults",
    "cultivating entrepreneurial mindsets through experiential learning and industry partnerships",
    "preserving cultural heritage while embracing modern pedagogical methods in the humanities and social sciences",
    "training the next generation of healthcare professionals through simulation-based medical education",
    "pioneering online and hybrid learning models that extend educational access to underserved communities",
    "advancing environmental sustainability through campus operations and academic programs in ecology",
    "building bridges between academic theory and professional practice through cooperative education programs",
    "empowering students from diverse backgrounds to become leaders in public service and civic engagement",
    "integrating artificial intelligence and data science across all academic disciplines",
    "developing globally competent graduates through mandatory study-abroad and multilingual programs",
    "championing academic freedom and open inquiry as cornerstones of intellectual development",
    "combining athletic excellence with rigorous academics in a balanced scholar-athlete model",
    "specializing in performing arts education with conservatory-level training in music, theater, and dance",
    "driving economic development in the surrounding region through applied research and workforce training",
    "maintaining a faith-based educational philosophy centered on service, justice, and community engagement",
    "leading in experiential STEM education through undergraduate research opportunities and maker spaces",
]

_NOTABLE_PROGRAMS = [
    "nationally ranked computer science program with a focus on machine learning and cybersecurity research",
    "top-tier business school known for its MBA program, venture capital clinic, and alumni network",
    "award-winning journalism school producing Pulitzer Prize winners and investigative reporting leaders",
    "pioneering biomedical engineering program with direct hospital partnerships and clinical rotations",
    "internationally acclaimed architecture school blending sustainable design with computational methods",
    "leading environmental science program conducting field research across three continents",
    "elite law school with the highest bar passage rate in the state and a renowned moot court tradition",
    "innovative education school redesigning teacher preparation with AI-assisted classroom technologies",
    "world-class astronomy program operating two observatories and collaborating with NASA on exoplanet research",
    "cutting-edge materials science lab that has produced three patents in superconductor technology this decade",
    "highly selective nursing program with a 98% NCLEX pass rate and simulation training center",
    "distinguished philosophy department known for contributions to ethics, epistemology, and political theory",
    "premier fine arts program whose graduates have exhibited at the Venice Biennale and Museum of Modern Art",
    "robust agricultural science program with a 500-acre experimental farm and precision farming research",
    "nationally recognized public health program with expertise in epidemiology and global health policy",
    "groundbreaking quantum computing research center attracting federal and private sector funding",
    "top-ranked music conservatory producing Grammy-nominated performers and composers",
    "acclaimed creative writing program with a literary magazine consistently ranked among the nation's best",
    "leading supply chain management program with partnerships with Fortune 500 logistics companies",
    "distinguished veterinary school with a teaching hospital treating over 20,000 animals annually",
]

_CAMPUS_SETTINGS = ["urban", "suburban", "rural", "small_town"]

_INSTITUTION_TYPES = ["public", "private_nonprofit", "private_forprofit",
                      "community_college"]

_ATTR_DEFS = [
    # int (9)
    AttrDef("enrollment", "int", 500, 60000, "", "Enrollment"),
    AttrDef("faculty_count", "int", 30, 4000, "", "Faculty count"),
    AttrDef("campus_acres", "int", 10, 3000, "", "Campus size (acres)"),
    AttrDef("library_volumes", "int", 50000, 8000000, "", "Library volumes"),
    AttrDef("alumni_count", "int", 5000, 500000, "", "Alumni count"),
    AttrDef("student_clubs", "int", 15, 500, "", "Student clubs"),
    AttrDef("dorm_capacity", "int", 200, 15000, "", "Dorm capacity"),
    AttrDef("ranking", "int", 1, 500, "", "National ranking"),
    AttrDef("avg_sat", "int", 800, 1580, "", "Average SAT score"),
    # float (7)
    AttrDef("endowment_b", "float", 0.01, 50.0, "$B", "Endowment"),
    AttrDef("acceptance_rate_pct", "float", 3.0, 95.0, "%",
            "Acceptance rate", agg_ops=("average",)),
    AttrDef("graduation_rate_pct", "float", 20.0, 99.0, "%",
            "Graduation rate", agg_ops=("average",)),
    AttrDef("tuition_k", "float", 2.0, 65.0, "$K", "Annual tuition"),
    AttrDef("research_funding_m", "float", 0.5, 3000.0, "$M",
            "Research funding"),
    AttrDef("retention_rate_pct", "float", 40.0, 99.0, "%",
            "Retention rate", agg_ops=("average",)),
    AttrDef("employment_rate_pct", "float", 35.0, 99.0, "%",
            "Post-grad employment rate", agg_ops=("average",)),
    # enum (2)
    AttrDef("campus_setting", "enum", label="Campus setting",
            choices=_CAMPUS_SETTINGS),
    AttrDef("institution_type", "enum", label="Institution type",
            choices=_INSTITUTION_TYPES),
    # text (2)
    AttrDef("mission_statement", "text", label="Mission statement",
            text_pool=_MISSION_STATEMENTS),
    AttrDef("notable_programs", "text", label="Notable programs",
            text_pool=_NOTABLE_PROGRAMS),
    # list_float (2)
    AttrDef("enrollment_trend", "list_float", min_val=400, max_val=65000,
            label="Enrollment (last 5 years)", list_len=5),
    AttrDef("research_output", "list_float", min_val=10, max_val=5000,
            label="Research publications (last 5 years)", list_len=5),
    # date (1)
    AttrDef("founded_date", "date", min_val=1636, max_val=2020,
            label="Founded date"),
]

_Q_TEXTS: dict[str, list[str]] = {
    "enrollment": [
        "How many students are enrolled at {name}?",
        "What is {name}'s total enrollment?",
        "How large is the student body at {name}?",
    ],
    "faculty_count": [
        "How many faculty members does {name} employ?",
        "What is the size of {name}'s faculty?",
        "How many professors work at {name}?",
    ],
    "campus_acres": [
        "How large is {name}'s campus in acres?",
        "What is {name}'s campus size?",
        "How many acres does {name}'s campus cover?",
    ],
    "library_volumes": [
        "How many volumes does {name}'s library hold?",
        "What is the size of {name}'s library collection?",
        "How many books are in {name}'s library?",
    ],
    "alumni_count": [
        "How many alumni does {name} have?",
        "What is {name}'s total alumni count?",
        "How many graduates has {name} produced?",
    ],
    "student_clubs": [
        "How many student clubs does {name} have?",
        "What is the number of student organizations at {name}?",
        "How many clubs and organizations operate at {name}?",
    ],
    "dorm_capacity": [
        "What is {name}'s dormitory capacity?",
        "How many students can {name} house on campus?",
        "What is {name}'s on-campus housing capacity?",
    ],
    "ranking": [
        "What is {name}'s national ranking?",
        "Where does {name} rank nationally?",
        "What ranking has {name} achieved?",
    ],
    "avg_sat": [
        "What is the average SAT score at {name}?",
        "What SAT score do admitted students at {name} average?",
        "What is {name}'s average SAT?",
    ],
    "endowment_b": [
        "What is {name}'s endowment?",
        "How large is {name}'s endowment fund?",
        "What is the total endowment at {name}?",
    ],
    "acceptance_rate_pct": [
        "What is {name}'s acceptance rate?",
        "What percentage of applicants does {name} admit?",
        "How selective is {name} in admissions?",
    ],
    "graduation_rate_pct": [
        "What is {name}'s graduation rate?",
        "What percentage of students graduate from {name}?",
        "How high is {name}'s completion rate?",
    ],
    "tuition_k": [
        "What is {name}'s annual tuition?",
        "How much does it cost to attend {name} per year?",
        "What tuition does {name} charge?",
    ],
    "research_funding_m": [
        "How much research funding does {name} receive?",
        "What is {name}'s research funding?",
        "How much does {name} receive in research grants?",
    ],
    "retention_rate_pct": [
        "What is {name}'s freshman retention rate?",
        "What percentage of freshmen return for their second year at {name}?",
        "How high is {name}'s retention rate?",
    ],
    "employment_rate_pct": [
        "What is {name}'s post-graduation employment rate?",
        "What percentage of {name} graduates find employment?",
        "How high is the employment rate for {name} graduates?",
    ],
    "campus_setting": [
        "What is {name}'s campus setting?",
        "Is {name} urban, suburban, or rural?",
        "What type of location is {name} in?",
    ],
    "institution_type": [
        "What type of institution is {name}?",
        "Is {name} public or private?",
        "How is {name} classified by institution type?",
    ],
    "mission_statement": [
        "What is {name}'s mission?",
        "Describe {name}'s educational mission.",
        "What does {name} stand for?",
    ],
    "notable_programs": [
        "What is {name} known for academically?",
        "What are {name}'s strongest programs?",
        "Describe {name}'s notable academic programs.",
    ],
    "enrollment_trend": [
        "What has {name}'s enrollment been over the last 5 years?",
        "List {name}'s enrollment trend for the past 5 years.",
    ],
    "research_output": [
        "How many research papers has {name} published over the last 5 years?",
        "List {name}'s research publication count for the past 5 years.",
    ],
    "founded_date": [
        "When was {name} founded?",
        "What is {name}'s founding date?",
        "In what year was {name} established?",
    ],
}

_SENTENCE_TMPLS: dict[str, list[tuple[str, str]]] = {
    "enrollment": [
        ("enrolls {val} students across its programs", "none"),
        ("enrollment figures of {distractor} and {val} across recent "
         "academic years", "temporal"),
        ("student counts of {val} and {other_val} from different "
         "reporting sources", "comparative"),
    ],
    "faculty_count": [
        ("employs {val} full-time faculty members", "none"),
        ("faculty counts of {val} and {distractor} in consecutive "
         "years", "temporal"),
        ("faculty figures of {distractor} and {val} under different "
         "counting criteria", "qualified"),
    ],
    "campus_acres": [
        ("spans a campus of {val} acres", "none"),
        ("campus size figures of {val} and {distractor} in different "
         "surveys", "temporal"),
    ],
    "library_volumes": [
        ("maintains a library collection of {val} volumes", "none"),
        ("library holdings of {distractor} and {val} in separate "
         "cataloging systems", "qualified"),
    ],
    "alumni_count": [
        ("counts {val} living alumni worldwide", "none"),
        ("alumni figures of {val} and {distractor} across reporting "
         "periods", "temporal"),
    ],
    "student_clubs": [
        ("offers {val} student clubs and organizations", "none"),
        ("club counts of {distractor} and {val} in different "
         "academic years", "temporal"),
    ],
    "dorm_capacity": [
        ("provides on-campus housing for {val} students", "none"),
        ("housing capacity figures of {val} and {distractor} before and "
         "after recent construction", "temporal"),
    ],
    "ranking": [
        ("holds a national ranking of {val}", "none"),
        ("ranking positions of {distractor} and {val} in successive "
         "years", "temporal"),
        ("rankings of {val} and {other_val} from different "
         "publications", "comparative"),
    ],
    "avg_sat": [
        ("reports an average SAT score of {val} for admitted students", "none"),
        ("average SAT figures of {val} and {distractor} across admission "
         "cycles", "temporal"),
    ],
    "endowment_b": [
        ("manages an endowment of {val}", "none"),
        ("endowment figures of {distractor} and {val} across fiscal "
         "years", "temporal"),
        ("endowment valuations of {val} and {other_val} from different "
         "accounting methods", "qualified"),
    ],
    "acceptance_rate_pct": [
        ("admits students at a rate of {val}", "none"),
        ("acceptance rates of {val} and {distractor} across admission "
         "cycles", "temporal"),
        ("admission rates of {distractor} and {val} for different "
         "applicant pools", "qualified"),
    ],
    "graduation_rate_pct": [
        ("achieves a graduation rate of {val}", "none"),
        ("graduation rates of {val} and {distractor} for different "
         "cohorts", "temporal"),
    ],
    "tuition_k": [
        ("charges annual tuition of {val}", "none"),
        ("tuition figures of {distractor} and {val} in consecutive "
         "years", "temporal"),
        ("tuition rates of {val} and {other_val} for in-state and "
         "out-of-state students", "comparative"),
    ],
    "research_funding_m": [
        ("secures {val} in annual research funding", "none"),
        ("research funding figures of {distractor} and {val} across "
         "fiscal years", "temporal"),
        ("funding totals of {val} and {other_val} from federal and "
         "private sources", "comparative"),
    ],
    "retention_rate_pct": [
        ("retains {val} of freshmen into their sophomore year", "none"),
        ("retention rates of {val} and {distractor} for different "
         "entering classes", "temporal"),
    ],
    "employment_rate_pct": [
        ("places {val} of graduates in employment within six months", "none"),
        ("employment rates of {distractor} and {val} across graduating "
         "classes", "temporal"),
    ],
    "campus_setting": [
        ("is located in a {val} setting", "none"),
    ],
    "institution_type": [
        ("operates as a {val} institution", "none"),
    ],
    "mission_statement": [
        ("{val}", "none"),
    ],
    "notable_programs": [
        ("is recognized for its {val}", "none"),
    ],
    "enrollment_trend": [
        ("recorded enrollment figures of {val} over the last 5 years",
         "none"),
    ],
    "research_output": [
        ("published {val} research papers over the last 5 years", "none"),
    ],
    "founded_date": [
        ("was established on {val}", "none"),
    ],
}

_RATIO_PAIRS = [
    ("endowment_b", "enrollment", "endowment per student"),
    ("research_funding_m", "faculty_count", "research funding per faculty"),
    ("enrollment", "faculty_count", "student-to-faculty ratio"),
    ("library_volumes", "enrollment", "library volumes per student"),
    ("alumni_count", "enrollment", "alumni-to-student ratio"),
    ("dorm_capacity", "enrollment", "housing coverage ratio"),
]


def _fmt(attr: str, val: Any) -> str:
    """Format an attribute value for human-readable display."""
    if attr == "endowment_b":
        return f"${val:,.2f}B" if isinstance(val, (int, float)) else str(val)
    if attr == "research_funding_m":
        return f"${val:,.1f}M" if isinstance(val, (int, float)) else str(val)
    if attr == "tuition_k":
        return f"${val:,.2f}K" if isinstance(val, (int, float)) else str(val)
    if attr in ("acceptance_rate_pct", "graduation_rate_pct",
                "retention_rate_pct", "employment_rate_pct"):
        return f"{val:.2f}%" if isinstance(val, (int, float)) else str(val)
    if attr in ("enrollment", "faculty_count", "library_volumes",
                "alumni_count", "dorm_capacity", "avg_sat"):
        return f"{val:,}" if isinstance(val, (int, float)) else str(val)
    if attr == "campus_acres":
        return f"{val:,} acres" if isinstance(val, (int, float)) else str(val)
    if attr == "ranking":
        return f"#{val}" if isinstance(val, (int, float)) else str(val)
    if attr == "enrollment_trend" and isinstance(val, list):
        return ", ".join(f"{v:,.0f}" for v in val)
    if attr == "research_output" and isinstance(val, list):
        return ", ".join(f"{v:,.0f}" for v in val)
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)


class UniversityWorld(WorldTemplate):
    """University/higher-education — 600 names × 23 attrs × 8 categories."""

    @property
    def name(self) -> str:
        return "university"

    @property
    def all_attr_defs(self) -> list[AttrDef]:
        return list(_ATTR_DEFS)

    @property
    def all_categories(self) -> list[str]:
        return list(_CATEGORIES)

    @property
    def entity_word(self) -> str:
        return "university"

    @property
    def entity_word_plural(self) -> str:
        return "universities"

    @property
    def correction_rate(self) -> float:
        return 0.10  # moderate — rankings and enrollment shift annually

    @property
    def correction_timing(self) -> tuple[float, float]:
        return (0.4, 0.7)  # standard

    @property
    def question_weights(self) -> dict[str, float]:
        return {
            "retrieval": 0.35,       # stable institutional data
            "comprehension": 0.30,   # ranking/ratio reasoning
            "update": 0.20,          # moderate corrections
            "abstention": 0.15,
        }

    def _generate_names(self, rng: Random, n: int) -> list[str]:
        pool = [(p, s) for p in _PLACE_WORDS for s in _INST_WORDS]
        selected = rng.sample(pool, min(n, len(pool)))
        return [f"{p} {s}" for p, s in selected]

    def _generate_list_float(self, adef, rng):
        if adef.name == "enrollment_trend":
            # Smooth monotonic: steady growth or slight decline
            start = rng.uniform(adef.min_val * 0.3, adef.max_val * 0.7)
            growth = rng.uniform(-0.02, 0.06)
            values = []
            for i in range(adef.list_len):
                val = start * (1 + growth) ** i
                noise = rng.uniform(0.98, 1.02)
                val = max(adef.min_val, min(adef.max_val, val * noise))
                values.append(round(val, 2))
            return values
        # research_output: logistic growth curve (slow → fast → plateau)
        base = rng.uniform(adef.min_val * 0.5, adef.max_val * 0.3)
        peak_mult = rng.uniform(1.5, 3.0)
        mid = adef.list_len / 2
        values = []
        for i in range(adef.list_len):
            # Sigmoid-like growth
            t = (i - mid) / max(1, mid)
            sigmoid = 1 / (1 + 2.718 ** (-2 * t))
            val = base * (1 + (peak_mult - 1) * sigmoid)
            noise = rng.uniform(0.95, 1.05)
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

        # Constraint 1: student/faculty ratio should be realistic (8:1 to 25:1)
        if "enrollment" in attrs and "faculty_count" in attrs:
            enr = attrs["enrollment"]
            fac = attrs["faculty_count"]
            ratio = enr / fac if fac > 0 else 999
            if ratio < 8 or ratio > 25:
                target_ratio = rng.uniform(10, 20)
                attrs["faculty_count"] = max(30, round(enr / target_ratio))

        # Constraint 2: dorm_capacity ≤ enrollment
        if "dorm_capacity" in attrs and "enrollment" in attrs:
            if attrs["dorm_capacity"] > attrs["enrollment"]:
                attrs["dorm_capacity"] = rng.randint(
                    max(200, attrs["enrollment"] // 5),
                    attrs["enrollment"],
                )

        # Constraint 3: low acceptance → high SAT, high acceptance → lower SAT
        if "acceptance_rate_pct" in attrs and "avg_sat" in attrs:
            acc = attrs["acceptance_rate_pct"]
            # Map acceptance rate to SAT range: 3%→1500+, 95%→900-
            expected_sat = int(1580 - (acc / 100) * 700)
            jitter = rng.randint(-50, 50)
            attrs["avg_sat"] = max(800, min(1580, expected_sat + jitter))

        # Constraint 4: graduation ≥ retention (logically)
        if ("graduation_rate_pct" in attrs
                and "retention_rate_pct" in attrs):
            if attrs["graduation_rate_pct"] > attrs["retention_rate_pct"] + 5:
                attrs["retention_rate_pct"] = min(
                    99.0,
                    attrs["graduation_rate_pct"] + rng.uniform(2, 10),
                )

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
            ("partner_of", "has a research partnership with", True),
            ("conference_rival", "competes athletically against", True),
        ]

    def render_relationship(self, rel):
        if rel.relation == "partner_of":
            return (f"{rel.source} and {rel.target} maintain a joint "
                    f"research partnership with faculty exchange programs.")
        if rel.relation == "conference_rival":
            return (f"{rel.source} and {rel.target} are long-standing "
                    f"athletic conference rivals.")
        return super().render_relationship(rel)

    def render_document(self, entity: EntitySpec,
                        active_attrs: list[str], rng: Random,
                        other_entities: list[EntitySpec] | None = None
                        ) -> str:
        style = rng.choice(["profile", "admissions", "review", "brief"])
        header = {
            "profile": (f"UNIVERSITY PROFILE — {entity.name}\n"
                        f"Type: {entity.category}\n"),
            "admissions": (f"ADMISSIONS DATA REPORT — {entity.name}\n"
                           f"Category: {entity.category}\n"),
            "review": (f"INSTITUTIONAL REVIEW — {entity.name}\n"
                       f"Classification: {entity.category}\n"),
            "brief": (f"CAMPUS ASSESSMENT BRIEF — {entity.name}\n"
                      f"Sector: {entity.category}\n"),
        }[style]
        return header + self._render_body(
            entity, active_attrs, rng, other_entities)

    def render_correction(self, entity: EntitySpec, attr: str,
                          old_val: Any, new_val: Any) -> str:
        label = self.attr_label(attr)
        return (
            f"DATA UPDATE: {_possessive(entity.name)} {label} has been "
            f"revised from {_fmt(attr, old_val)} to {_fmt(attr, new_val)} "
            f"following the latest institutional report."
        )

    def _q_text(self, attr: str, name: str,
                rng: Random | None = None) -> str:
        templates = _Q_TEXTS.get(attr, [f"What is {{name}}'s {attr}?"])
        tmpl = rng.choice(templates) if rng else templates[0]
        return tmpl.format(name=name)
