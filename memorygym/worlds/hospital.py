"""Hospital/healthcare world template.

Entities: Hospitals with 23 possible attributes (16 numeric + text + enum + date + list_float).
Names: 30 adjectives x 20 nouns = 600 unique hospitals.
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

from .base import (
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

_SPECIALTY_DESCRIPTIONS = [
    "Comprehensive cardiac care center with catheterization labs and electrophysiology suites for advanced heart rhythm disorders",
    "Full-service oncology program offering chemotherapy infusion therapy and radiation treatment across twelve specialized clinics",
    "Neuroscience institute featuring a dedicated stroke unit with rapid intervention protocols and telemetry monitoring systems",
    "Orthopedic center of excellence performing joint replacement surgeries using robotic-assisted navigation technology platforms",
    "Pediatric specialty hospital providing neonatal intensive care with level three certification and family support services",
    "Emergency trauma center operating a helicopter transport program serving a three-hundred-mile radius catchment area network",
    "Surgical innovation hub with hybrid operating rooms combining advanced imaging and minimally invasive procedure capabilities",
    "Internal medicine department managing complex chronic disease cases through integrated multidisciplinary team-based care models",
    "Obstetrics and gynecology center with high-risk pregnancy management and maternal-fetal medicine subspecialty consultation",
    "Psychiatric facility offering inpatient behavioral health treatment with cognitive behavioral therapy and crisis stabilization",
    "Transplant program performing kidney liver and heart procedures with dedicated immunology follow-up and organ procurement",
    "Rehabilitation medicine center providing physical occupational and speech therapy with advanced gait analysis technology",
    "Pulmonology department with dedicated respiratory therapy unit offering ventilator management and sleep disorder diagnostics",
    "Gastroenterology center equipped with advanced endoscopy suites performing diagnostic and therapeutic procedures daily",
    "Dermatology clinic specializing in Mohs surgery for skin cancer treatment with same-day pathology analysis capabilities",
    "Urology department featuring robotic surgery platform for minimally invasive prostate and kidney cancer interventions",
    "Endocrinology center managing diabetes thyroid and metabolic disorders through personalized treatment planning protocols",
    "Rheumatology program providing biologic infusion therapy and clinical trial access for autoimmune disease management",
    "Infectious disease division with negative pressure isolation units and antimicrobial stewardship oversight responsibilities",
    "Pain management center offering interventional procedures including nerve blocks spinal cord stimulation and biofeedback",
]

_PROCEDURE_NOTES = [
    "Performed laparoscopic cholecystectomy with intraoperative cholangiography and uncomplicated recovery",
    "Completed total knee arthroplasty using computer-navigated alignment and cemented fixation",
    "Executed coronary artery bypass grafting with four vessels using left internal mammary artery",
    "Conducted robotic-assisted radical prostatectomy with nerve-sparing bilateral approach",
    "Performed endoscopic retrograde cholangiopancreatography with sphincterotomy and stent placement",
    "Completed craniotomy for meningioma resection with intraoperative MRI navigation guidance",
    "Executed thoracoscopic lobectomy for early-stage non-small cell lung carcinoma treatment",
    "Performed carotid endarterectomy with patch angioplasty under regional cervical block anesthesia",
    "Conducted percutaneous coronary intervention with drug-eluting stent deployment in LAD artery",
    "Completed total hip replacement using anterior approach with cementless acetabular component",
    "Performed laparoscopic Roux-en-Y gastric bypass for morbid obesity with BMI over forty",
    "Executed spinal fusion L4-L5 with pedicle screw fixation and interbody cage placement",
    "Conducted sentinel lymph node biopsy with wide local excision for breast cancer staging",
    "Performed transurethral resection of bladder tumor with blue light cystoscopy guidance",
    "Completed arthroscopic rotator cuff repair with suture anchor fixation and biceps tenodesis",
    "Executed endovascular aneurysm repair with bifurcated stent graft deployment under fluoroscopy",
    "Performed appendectomy via single-incision laparoscopic approach with same-day discharge protocol",
    "Conducted cochlear implant surgery with electrode array insertion and intraoperative telemetry",
    "Completed thyroidectomy with intraoperative nerve monitoring and parathyroid autotransplantation",
    "Performed transsphenoidal pituitary adenoma resection using endoscopic endonasal corridor access",
]

_NOTABLE_ACHIEVEMENTS = [
    "Earned Magnet Recognition for nursing excellence from the American Nurses Credentialing Center",
    "Achieved Leapfrog Group A safety grade for twelve consecutive reporting periods",
    "Received Joint Commission Gold Seal for advanced heart failure program certification",
    "Named top-fifty hospital nationally by US News and World Report ranking system",
    "Established first accredited comprehensive stroke center in the tri-state region",
    "Published landmark clinical trial results in the New England Journal of Medicine",
    "Achieved zero central-line-associated bloodstream infections for eighteen consecutive months",
    "Launched pioneering telehealth program connecting fifty rural clinics to specialists",
    "Received HIMSS Stage Seven designation for electronic medical record adoption maturity",
    "Completed successful separation of conjoined twins with international surgical collaboration",
    "Established organ transplant program performing over two hundred procedures annually",
    "Won Malcolm Baldrige National Quality Award for healthcare performance excellence",
    "Opened new proton therapy center serving cancer patients from across the region",
    "Achieved baby-friendly hospital designation from WHO and UNICEF joint initiative",
    "Developed proprietary sepsis detection algorithm reducing mortality by thirty-five percent",
    "Created residency program producing over five hundred board-certified physicians to date",
    "Implemented hospital-at-home program reducing readmissions by forty percent year over year",
    "Established genomic medicine center offering whole-genome sequencing for precision diagnostics",
    "Received CDC Prevention Epicenters designation for healthcare-associated infection research",
    "Built dedicated veterans care wing with integrated PTSD treatment and rehabilitation",
]

_ACCREDITATION_LEVELS = ["basic", "advanced", "excellence", "research"]

_HOSPITAL_TYPES = ["general", "children", "teaching", "specialty", "psychiatric"]

_ATTR_DEFS = [
    # Original numeric attrs
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
    # New numeric attrs
    AttrDef("icu_beds", "int", 0, 200, "", "ICU beds"),
    AttrDef("er_visits_daily", "int", 10, 500, "", "Daily ER visits"),
    AttrDef("surgery_count_monthly", "int", 50, 2000, "",
            "Monthly surgeries"),
    AttrDef("nurse_ratio", "float", 1.0, 8.0, "", "Nurse-to-patient ratio",
            agg_ops=("average",)),
    AttrDef("avg_stay_days", "float", 1.0, 15.0, "", "Average stay (days)",
            agg_ops=("average",)),
    AttrDef("research_papers", "int", 0, 500, "", "Research papers"),
    # New dtype attrs
    AttrDef("specialty_description", "text", label="Specialty description",
            text_pool=_SPECIALTY_DESCRIPTIONS),
    AttrDef("recent_procedure_note", "text", label="Recent procedure note",
            text_pool=_PROCEDURE_NOTES),
    AttrDef("notable_achievement", "text", label="Notable achievement",
            text_pool=_NOTABLE_ACHIEVEMENTS),
    AttrDef("accreditation_level", "enum", label="Accreditation level",
            choices=_ACCREDITATION_LEVELS),
    AttrDef("hospital_type", "enum", label="Hospital type",
            choices=_HOSPITAL_TYPES),
    AttrDef("last_inspection_date", "date", min_val=2015, max_val=2025,
            label="Last inspection date"),
    AttrDef("patient_trend", "list_float", min_val=1000, max_val=100000,
            label="Annual patients (last 5 years)", list_len=5),
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
    "icu_beds": [
        "How many ICU beds does {name} have?",
        "What is {name}'s ICU bed capacity?",
    ],
    "er_visits_daily": [
        "How many ER visits does {name} handle daily?",
        "What is {name}'s daily emergency room volume?",
    ],
    "surgery_count_monthly": [
        "How many surgeries does {name} perform monthly?",
        "What is {name}'s monthly surgical volume?",
    ],
    "nurse_ratio": [
        "What is {name}'s nurse-to-patient ratio?",
        "How many nurses per patient does {name} maintain?",
    ],
    "avg_stay_days": [
        "What is the average length of stay at {name}?",
        "How many days do patients typically stay at {name}?",
    ],
    "research_papers": [
        "How many research papers has {name} published?",
        "What is {name}'s research publication count?",
    ],
    "specialty_description": [
        "What is {name}'s specialty description?",
        "Describe {name}'s clinical specialty.",
        "What does {name} specialize in?",
    ],
    "recent_procedure_note": [
        "What is {name}'s most recent procedure note?",
        "Describe a recent procedure performed at {name}.",
    ],
    "notable_achievement": [
        "What notable achievement has {name} earned?",
        "What is {name} recognized for?",
    ],
    "accreditation_level": [
        "What is {name}'s accreditation level?",
        "What accreditation tier does {name} hold?",
    ],
    "hospital_type": [
        "What type of hospital is {name}?",
        "What is {name}'s hospital classification?",
    ],
    "last_inspection_date": [
        "When was {name} last inspected?",
        "What is {name}'s most recent inspection date?",
    ],
    "patient_trend": [
        "What is {name}'s annual patient trend over the last 5 years?",
        "List {name}'s patient volume for the past 5 years.",
    ],
}


_SENTENCE_TMPLS: dict[str, list[tuple[str, str]]] = {
    "beds": [
        ("has a capacity of {val} patient beds", "none"),
        ("bed counts of {distractor} and {val} in different reporting "
         "periods", "temporal"),
        ("bed figures of {val} and {distractor} under different "
         "criteria", "qualified"),
    ],
    "staff_count": [
        ("employs {val} medical and administrative staff", "none"),
        ("staff counts of {val} and {distractor} across periods",
         "temporal"),
        ("staffing figures of {other_val} and {val} from separate "
         "reports", "comparative"),
    ],
    "annual_patients": [
        ("treats {val} patients annually", "none"),
        ("patient volume figures of {distractor} and {val} in successive "
         "years", "temporal"),
        ("patient counts of {val} and {distractor} by different "
         "classifications", "qualified"),
    ],
    "readmission_pct": [
        ("reports a readmission rate of {val}", "none"),
        ("readmission rate readings of {val} and {distractor} across "
         "periods", "temporal"),
        ("readmission figures of {val} and {other_val} from different "
         "audits", "comparative"),
    ],
    "mortality_rate": [
        ("maintains a mortality rate of {val}", "none"),
        ("mortality rate figures of {distractor} and {val} in different "
         "reviews", "temporal"),
        ("mortality readings of {other_val} and {val} from separate "
         "assessments", "comparative"),
    ],
    "satisfaction_score": [
        ("earned a patient satisfaction score of {val}", "none"),
        ("satisfaction scores of {val} and {distractor} across survey "
         "rounds", "temporal"),
        ("satisfaction readings of {val} and {other_val} from separate "
         "surveys", "comparative"),
    ],
    "wait_time_min": [
        ("has an average wait time of {val}", "none"),
        ("wait time figures of {distractor} and {val} in different "
         "periods", "temporal"),
        ("wait time readings of {val} and {distractor} by different "
         "measurement methods", "qualified"),
    ],
    "operating_rooms": [
        ("is equipped with {val} operating rooms", "none"),
        ("operating room counts of {val} and {distractor} across "
         "assessments", "temporal"),
        ("OR tallies of {distractor} and {val} under different "
         "classifications", "qualified"),
    ],
    "budget_m": [
        ("operates with an annual budget of {val}", "none"),
        ("budget figures of {distractor} and {val} in successive fiscal "
         "years", "temporal"),
        ("budget amounts of {val} and {other_val} from different "
         "sources", "comparative"),
    ],
    "accreditation_year": [
        ("received its most recent accreditation in {val}", "none"),
        ("accreditation years of {distractor} and {val} in different "
         "records", "temporal"),
        ("accreditation dates of {val} and {other_val} from separate "
         "registries", "comparative"),
    ],
    "icu_beds": [
        ("maintains {val} intensive care unit beds", "none"),
        ("ICU bed counts of {val} and {distractor} across reporting "
         "periods", "temporal"),
        ("ICU bed figures of {other_val} and {val} from separate "
         "counts", "comparative"),
    ],
    "er_visits_daily": [
        ("handles {val} emergency room visits per day", "none"),
        ("daily ER visit counts of {distractor} and {val} in different "
         "periods", "temporal"),
        ("ER visit figures of {val} and {distractor} by different "
         "counting criteria", "qualified"),
    ],
    "surgery_count_monthly": [
        ("performs {val} surgical procedures each month", "none"),
        ("monthly surgery counts of {val} and {distractor} across "
         "periods", "temporal"),
        ("surgery figures of {other_val} and {val} from different "
         "reports", "comparative"),
    ],
    "nurse_ratio": [
        ("maintains a nurse-to-patient ratio of {val}", "none"),
        ("nurse ratio figures of {distractor} and {val} in different "
         "assessments", "temporal"),
    ],
    "avg_stay_days": [
        ("reports an average patient stay of {val} days", "none"),
        ("average stay readings of {val} and {distractor} days across "
         "periods", "temporal"),
    ],
    "research_papers": [
        ("has published {val} peer-reviewed research papers", "none"),
        ("research paper counts of {distractor} and {val} in different "
         "years", "temporal"),
        ("publication figures of {val} and {other_val} from separate "
         "tallies", "comparative"),
    ],
    "specialty_description": [
        ("{val}", "none"),
    ],
    "recent_procedure_note": [
        ("{val}", "none"),
    ],
    "notable_achievement": [
        ("{val}", "none"),
    ],
    "accreditation_level": [
        ("holds {val} accreditation level", "none"),
    ],
    "hospital_type": [
        ("is classified as a {val} hospital", "none"),
    ],
    "last_inspection_date": [
        ("was last inspected on {val}", "none"),
    ],
    "patient_trend": [
        ("recorded annual patient volumes of {val} over the last five years",
         "none"),
    ],
}

_RATIO_PAIRS = [
    ("annual_patients", "beds", "patients per bed"),
    ("staff_count", "beds", "staff per bed"),
    ("budget_m", "annual_patients", "budget per patient in $M"),
    ("surgery_count_monthly", "operating_rooms",
     "monthly surgeries per operating room"),
    ("er_visits_daily", "icu_beds", "daily ER visits per ICU bed"),
    ("research_papers", "staff_count", "research papers per staff member"),
]


def _fmt(attr: str, val: Any) -> str:
    """Format an attribute value for human-readable display."""
    if attr == "budget_m":
        return f"${val:,.1f}M"
    if attr in ("readmission_pct", "mortality_rate"):
        return f"{val:.2f}%"
    if attr == "satisfaction_score":
        return f"{val:.2f}/10"
    if attr == "wait_time_min":
        return f"{val} min"
    if attr in ("accreditation_year",):
        return str(val)
    if attr == "nurse_ratio":
        return f"{val:.2f}" if isinstance(val, float) else str(val)
    if attr == "avg_stay_days":
        return f"{val:.2f} days" if isinstance(val, (int, float)) else str(val)
    if attr == "patient_trend" and isinstance(val, list):
        return ", ".join(f"{v:,.0f}" for v in val)
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)


class HospitalWorld(WorldTemplate):
    """Hospital operations — 600 names × 23 attrs × 10 specialties."""

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

    @property
    def correction_rate(self) -> float:
        return 0.15  # high — frequent status changes

    @property
    def correction_timing(self) -> tuple[float, float]:
        return (0.3, 0.5)  # early corrections — more time to update

    @property
    def question_weights(self) -> dict[str, float]:
        return {
            "retrieval": 0.35,
            "comprehension": 0.20,
            "update": 0.30,          # high — frequent status changes
            "abstention": 0.15,
        }

    def _generate_names(self, rng: Random, n: int) -> list[str]:
        pool = [(a, b) for a in _ADJECTIVES for b in _NOUNS]
        selected = rng.sample(pool, min(n, len(pool)))
        return [f"{a} {b}" for a, b in selected]

    def _generate_list_float(self, adef, rng):
        """Periodic peaks: baseline with seasonal spikes (flu season pattern)."""
        baseline = rng.uniform(adef.min_val * 0.3, adef.max_val * 0.5)
        peak_idx = rng.randint(0, adef.list_len - 1)  # peak year
        values = []
        for i in range(adef.list_len):
            if i == peak_idx:
                spike = rng.uniform(1.4, 1.8)  # 40-80% spike
            elif abs(i - peak_idx) == 1:
                spike = rng.uniform(1.1, 1.3)  # adjacent years elevated
            else:
                spike = rng.uniform(0.9, 1.1)
            val = max(adef.min_val, min(adef.max_val, baseline * spike))
            values.append(round(val, 2))
        return values

    def generate_entity(self, rng: Random, name: str, category: str,
                        active_attrs: list[str]) -> EntitySpec:
        attrs: dict[str, Any] = {}
        for adef in _ATTR_DEFS:
            if adef.name not in active_attrs:
                continue
            attrs[adef.name] = self._generate_attr_value(rng, adef)
        # Constraint: beds >= icu_beds
        if "beds" in attrs and "icu_beds" in attrs:
            if attrs["icu_beds"] > attrs["beds"]:
                attrs["icu_beds"] = rng.randint(0, attrs["beds"] // 5)
        # Constraint: staff_count >= beds * 0.5
        if "staff_count" in attrs and "beds" in attrs:
            min_staff = int(attrs["beds"] * 0.5)
            if attrs["staff_count"] < min_staff:
                attrs["staff_count"] = rng.randint(
                    min_staff, max(min_staff + 1, attrs["beds"] * 3))
        return EntitySpec(name=name, category=category, attrs=attrs)

    def enforce_constraints(self, entity: EntitySpec,
                            active_attrs: list[str],
                            rng: Random) -> None:
        attrs = entity.attrs
        if "beds" in attrs and "icu_beds" in attrs:
            if attrs["icu_beds"] > attrs["beds"]:
                attrs["icu_beds"] = rng.randint(0, attrs["beds"] // 5)
        if "staff_count" in attrs and "beds" in attrs:
            min_staff = int(attrs["beds"] * 0.5)
            if attrs["staff_count"] < min_staff:
                attrs["staff_count"] = rng.randint(
                    min_staff, max(min_staff + 1, attrs["beds"] * 3))

    def _format_value(self, attr: str, val: Any) -> str:
        return _fmt(attr, val)

    def _sentence_templates(self):
        return {attr: [SentenceTemplate(t, attr, d) for t, d in tmpls]
                for attr, tmpls in _SENTENCE_TMPLS.items()}

    def _ratio_pairs(self):
        return list(_RATIO_PAIRS)

    def _relationship_types(self):
        return [
            ("refers_to", "refers patients to", False),
            ("partners_with", "partners with", True),
        ]

    def render_relationship(self, rel):
        if rel.relation == "refers_to":
            return (f"{rel.source} maintains a referral agreement "
                    f"with {rel.target} for specialist care.")
        if rel.relation == "partners_with":
            return (f"{rel.source} and {rel.target} operate a joint "
                    f"research program.")
        return super().render_relationship(rel)

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
