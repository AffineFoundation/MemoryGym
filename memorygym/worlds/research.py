"""Research lab world template.

Entities: Researchers with 21 possible attributes (15 numeric + text + enum + date + 2 list_float).
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

_RESEARCH_FOCUS = [
    "Develops scalable transformer architectures for low-resource language understanding",
    "Investigates causal inference methods for observational healthcare datasets",
    "Designs privacy-preserving federated learning protocols for mobile devices",
    "Explores reinforcement learning strategies for autonomous warehouse robotics",
    "Builds graph neural networks for molecular property prediction in drug design",
    "Studies adversarial robustness of vision models under distribution shift",
    "Develops energy-efficient neural architecture search for edge deployment",
    "Researches multimodal fusion techniques for video understanding tasks",
    "Investigates few-shot learning approaches for rare event detection systems",
    "Designs differentiable rendering pipelines for 3D scene reconstruction",
    "Explores continual learning methods that mitigate catastrophic forgetting",
    "Develops interpretable machine learning models for clinical decision support",
    "Studies self-supervised pretraining strategies for speech recognition systems",
    "Builds distributed optimization algorithms for large-scale recommendation engines",
    "Researches zero-shot cross-lingual transfer using multilingual embeddings",
    "Investigates neural network pruning techniques for real-time inference",
    "Develops probabilistic programming frameworks for Bayesian deep learning",
    "Studies attention mechanisms for long-document summarization and retrieval",
    "Explores sim-to-real transfer methods for dexterous robotic manipulation",
    "Designs knowledge distillation pipelines for compact on-device models",
]

_METHODOLOGY_NOTES = [
    "Primarily uses randomized controlled trials with Bayesian analysis",
    "Combines large-scale simulation with real-world field experiments",
    "Employs mixed-methods research integrating surveys and interviews",
    "Relies on longitudinal cohort studies spanning multiple years",
    "Uses computational modeling validated against empirical benchmarks",
    "Applies meta-analysis techniques across multiple published datasets",
    "Conducts ablation studies with systematic hyperparameter sweeps",
    "Develops formal mathematical proofs supplemented by simulations",
    "Uses ethnographic fieldwork combined with quantitative analysis",
    "Applies causal discovery algorithms to observational data",
    "Employs transfer learning with domain-specific fine-tuning",
    "Relies on A/B testing frameworks for online evaluation",
    "Uses grounded theory methodology for qualitative research",
    "Applies information-theoretic analysis to model behavior",
    "Conducts prospective studies with pre-registered hypotheses",
    "Uses agent-based modeling for complex systems analysis",
    "Employs cross-validation with stratified sampling techniques",
    "Applies topological data analysis to high-dimensional datasets",
    "Uses participatory design methods with stakeholder feedback loops",
    "Conducts systematic literature reviews with PRISMA guidelines",
]

_CAREER_STAGES = ["junior", "mid-career", "senior", "emeritus"]

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
    # New numeric attrs
    AttrDef("grant_count", "int", 0, 50, "", "Grants awarded"),
    AttrDef("phd_supervised", "int", 0, 40, "", "PhDs supervised"),
    AttrDef("conference_talks", "int", 0, 100, "", "Conference talks"),
    AttrDef("industry_projects", "int", 0, 30, "", "Industry projects"),
    AttrDef("review_count", "int", 0, 200, "", "Reviews completed"),
    # New dtype attrs
    AttrDef("publication_years", "list_float", min_val=0, max_val=50,
            list_len=5, label="Publications (last 5 years)"),
    AttrDef("citation_trend", "list_float", min_val=0, max_val=5000,
            list_len=5, label="Citations (last 5 years)"),
    AttrDef("research_focus", "text", label="Research focus",
            text_pool=_RESEARCH_FOCUS),
    AttrDef("methodology_note", "text", label="Methodology note",
            text_pool=_METHODOLOGY_NOTES),
    AttrDef("career_stage", "enum", label="Career stage",
            choices=_CAREER_STAGES),
    AttrDef("tenure_start_date", "date", min_val=1980, max_val=2024,
            label="Tenure start date"),
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
    "grant_count": [
        "How many grants has {name} been awarded?",
        "What is {name}'s total grant count?",
    ],
    "phd_supervised": [
        "How many PhD students has {name} supervised to completion?",
        "What is {name}'s total count of supervised PhDs?",
    ],
    "conference_talks": [
        "How many conference talks has {name} given?",
        "What is {name}'s conference presentation count?",
    ],
    "industry_projects": [
        "How many industry projects has {name} participated in?",
        "What is {name}'s industry collaboration count?",
    ],
    "review_count": [
        "How many paper reviews has {name} completed?",
        "What is {name}'s peer review count?",
    ],
    "publication_years": [
        "What are {name}'s publication counts for the last 5 years?",
        "List {name}'s yearly publication output over the past 5 years.",
    ],
    "citation_trend": [
        "What are {name}'s citation counts for the last 5 years?",
        "List {name}'s yearly citations over the past 5 years.",
    ],
    "research_focus": [
        "What is {name}'s research focus?",
        "Describe {name}'s primary research area.",
        "What does {name} work on?",
    ],
    "methodology_note": [
        "What research methodology does {name} use?",
        "Describe {name}'s methodological approach.",
    ],
    "career_stage": [
        "What is {name}'s career stage?",
        "At what career level is {name}?",
    ],
    "tenure_start_date": [
        "When did {name} start their tenure?",
        "What is {name}'s tenure start date?",
    ],
}


_SENTENCE_TMPLS: dict[str, list[tuple[str, str]]] = {
    "citations": [
        ("has accumulated {val} citations across all publications", "none"),
        ("citation counts of {distractor} and {val} across reporting "
         "periods", "temporal"),
        ("citation tallies of {val} and {other_val} in separate "
         "databases", "comparative"),
    ],
    "h_index": [
        ("maintains an h-index of {val}", "none"),
        ("h-index readings of {val} and {distractor} in different "
         "assessments", "temporal"),
        ("h-index values of {other_val} and {val} from separate "
         "analyses", "comparative"),
    ],
    "funding_k": [
        ("holds {val} in active research funding", "none"),
        ("funding figures of {distractor} and {val} across periods",
         "temporal"),
        ("grant amounts of {val} and {distractor} by different "
         "categorizations", "qualified"),
    ],
    "students": [
        ("supervises {val} doctoral students", "none"),
        ("student counts of {val} and {distractor} in different terms",
         "temporal"),
        ("student tallies of {distractor} and {val} under different "
         "criteria", "qualified"),
    ],
    "review_score": [
        ("earned an average review score of {val}", "none"),
        ("review scores of {distractor} and {val} across evaluation "
         "rounds", "temporal"),
        ("review ratings of {val} and {other_val} from separate "
         "panels", "comparative"),
    ],
    "papers": [
        ("has published {val} peer-reviewed papers", "none"),
        ("publication counts of {val} and {distractor} across periods",
         "temporal"),
        ("paper tallies of {distractor} and {val} by different counting "
         "methods", "qualified"),
    ],
    "patents": [
        ("holds {val} patents from research innovations", "none"),
        ("patent counts of {distractor} and {val} in different filings",
         "temporal"),
        ("patent holdings of {val} and {other_val} in separate "
         "records", "comparative"),
    ],
    "collaborators": [
        ("works with {val} research collaborators", "none"),
        ("collaborator counts of {val} and {distractor} across periods",
         "temporal"),
        ("collaboration figures of {distractor} and {val} by different "
         "definitions", "qualified"),
    ],
    "years_active": [
        ("has been active in research for {val} years", "none"),
        ("career spans {val} years in the field", "none"),
        ("career lengths of {other_val} and {val} years in different "
         "records", "comparative"),
    ],
    "awards": [
        ("has received {val} academic awards", "none"),
        ("award counts of {distractor} and {val} in different periods",
         "temporal"),
        ("award tallies of {val} and {other_val} from separate "
         "sources", "comparative"),
    ],
    "grant_count": [
        ("has been awarded {val} research grants", "none"),
        ("grant counts of {val} and {distractor} across periods",
         "temporal"),
        ("grant figures of {other_val} and {val} in separate "
         "databases", "comparative"),
    ],
    "phd_supervised": [
        ("has supervised {val} PhD students to completion", "none"),
        ("PhD supervision counts of {distractor} and {val} in different "
         "records", "temporal"),
        ("doctoral graduate tallies of {val} and {other_val} from "
         "separate counts", "comparative"),
    ],
    "conference_talks": [
        ("has delivered {val} talks at international conferences", "none"),
        ("conference talk counts of {val} and {distractor} across "
         "periods", "temporal"),
    ],
    "industry_projects": [
        ("has participated in {val} industry-funded projects", "none"),
        ("industry project counts of {distractor} and {val} in different "
         "tallies", "temporal"),
    ],
    "review_count": [
        ("has completed {val} peer reviews for journals and conferences",
         "none"),
        ("peer review counts of {val} and {distractor} in successive "
         "periods", "temporal"),
    ],
    "publication_years": [
        ("reported yearly publication counts of {val}", "none"),
    ],
    "citation_trend": [
        ("recorded yearly citation counts of {val}", "none"),
    ],
    "research_focus": [
        ("{val}", "none"),
    ],
    "methodology_note": [
        ("{val}", "none"),
    ],
    "career_stage": [
        ("is at the {val} career stage", "none"),
    ],
    "tenure_start_date": [
        ("began tenure on {val}", "none"),
    ],
}

_RATIO_PAIRS = [
    ("citations", "papers", "citations per paper"),
    ("funding_k", "students", "funding per student in $K"),
    ("papers", "years_active", "papers per year"),
    ("grant_count", "years_active", "grants per year active"),
    ("conference_talks", "papers", "talks per paper"),
]


def _fmt(attr: str, val: Any) -> str:
    if attr == "funding_k":
        return f"${val:,.1f}K"
    if attr == "review_score":
        return f"{val:.2f}/10"
    if attr in ("publication_years", "citation_trend") and isinstance(val, list):
        return ", ".join(f"{v:,.1f}" for v in val)
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)


class ResearchWorld(WorldTemplate):
    """Research domain — 625 names × 21 attrs × 10 venues."""

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

    @property
    def correction_rate(self) -> float:
        return 0.08  # moderate-low — publications rarely revised

    @property
    def correction_timing(self) -> tuple[float, float]:
        return (0.4, 0.7)  # standard timing

    @property
    def question_weights(self) -> dict[str, float]:
        return {
            "retrieval": 0.30,
            "comprehension": 0.35,   # high — citation/impact reasoning
            "update": 0.20,
            "abstention": 0.15,
        }

    def _generate_names(self, rng: Random, n: int) -> list[str]:
        pool = [(f, l) for f in _FIRST for l in _LAST]
        selected = rng.sample(pool, min(n, len(pool)))
        return [f"{f} {l}" for f, l in selected]

    def _generate_list_float(self, adef, rng):
        """Impact curve: rise then plateau (publications/citations grow then level off)."""
        peak = rng.uniform(adef.max_val * 0.4, adef.max_val * 0.8)
        values = []
        for i in range(adef.list_len):
            # Logistic-like growth: rapid early rise, then saturation
            t = (i + 1) / adef.list_len
            growth = peak * (1 - (1 - t) ** 2)  # quadratic rise toward peak
            noise = rng.uniform(0.85, 1.15)
            val = max(adef.min_val, min(adef.max_val, growth * noise))
            values.append(round(val, 2))
        return values

    def generate_entity(self, rng: Random, name: str, category: str,
                        active_attrs: list[str]) -> EntitySpec:
        attrs: dict[str, Any] = {}
        for adef in _ATTR_DEFS:
            if adef.name not in active_attrs:
                continue
            attrs[adef.name] = self._generate_attr_value(rng, adef)
        # Constrain citations to be consistent with h_index
        # h_index=h means h papers with >=h citations each -> min citations ~ h^2
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
            ("cites", "cites work of", False),
        ]

    def render_relationship(self, rel):
        if rel.relation == "collaborates_with":
            return (f"{rel.source} and {rel.target} have co-authored "
                    f"multiple papers together.")
        if rel.relation == "advised_by":
            return (f"{rel.source} completed doctoral work under the "
                    f"supervision of {rel.target}.")
        if rel.relation == "cites":
            return (f"{rel.source} frequently cites the work of "
                    f"{rel.target} in recent publications.")
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
