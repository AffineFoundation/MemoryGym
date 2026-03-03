"""Research domain: researchers, publications, academic metrics."""

from __future__ import annotations

import random

from memorybench.domains.base import Distractor, Domain, Entity
from memorybench.domains.names import person_name_pool

VENUES = [
    "ICML", "NeurIPS", "ICLR", "AAAI", "CVPR",
    "ACL", "EMNLP", "KDD", "SIGIR", "WWW",
]

METHODS = [
    "Transformer Networks", "Graph Neural Models", "Diffusion Systems",
    "Contrastive Learning", "Reinforcement Optimization",
    "Variational Inference", "Attention Mechanisms", "Meta-Learning",
]

TOPICS = [
    "Natural Language Understanding", "Computer Vision",
    "Robotic Control", "Drug Discovery", "Climate Modeling",
    "Recommender Systems", "Speech Recognition", "Code Generation",
]


class ResearchDomain(Domain):
    name = "research"
    ALL_ATTRS = ["citations", "h_index", "funding", "students",
                 "review_score", "papers_count"]
    SYNTHESIS_ENTITY_WORD = "researcher"
    GROUP_NAMES = VENUES
    ATTR_SYNONYMS = {
        "citations": {"citations", "cited", "citation count", "times cited",
                      "citations=", "citation total"},
        "h_index": {"h_index", "h-index", "hirsch index", "h index",
                    "h_index="},
        "funding": {"funding", "grant", "research funding", "$", "funding="},
        "students": {"students", "advisees", "doctoral students",
                     "supervises", "students="},
        "review_score": {"review_score", "review score", "peer review",
                         "reviewer rating", "review_score=", "review rating",
                         "scored by reviewers", "reviewers give"},
        "papers_count": {"papers_count", "publications", "published papers",
                         "total papers", "papers_count=", "publication count",
                         "publication total", "papers", "published",
                         "research papers", "authored"},
    }
    DOC_TEMPLATES = [
        "Dr. {name}, affiliated with {group}, published work on {topic} "
        "using {method}. {details}.",
        "Research records show Dr. {name} ({group}) focuses on {topic}. "
        "{details}.",
        "At {group}, Dr. {name} investigates {topic} through {method}. "
        "{details}.",
    ]
    BACKGROUND = [
        "The annual conference proceedings highlight advances in machine "
        "learning and artificial intelligence research.",
        "Funding agencies have announced new priorities for interdisciplinary "
        "research proposals in the upcoming cycle.",
        "Peer review processes continue to evolve with open review trials "
        "gaining traction across major venues.",
    ]

    def generate_kb(self, seed, n_entities=20):
        rng = random.Random(seed)
        active, primary = self._select_schema(seed)
        pool = person_name_pool(rng, n_entities)
        entities = []
        for _ in range(n_entities):
            attrs = {
                "_topic": rng.choice(TOPICS),
                "_method": rng.choice(METHODS),
            }
            if "citations" in active:
                attrs["citations"] = rng.randint(10, 5000)
            if "h_index" in active:
                attrs["h_index"] = rng.randint(3, 80)
            if "funding" in active:
                attrs["funding"] = rng.randint(50, 2000) * 1000
            if "students" in active:
                attrs["students"] = rng.randint(0, 15)
            if "review_score" in active:
                attrs["review_score"] = round(rng.uniform(3.0, 9.5), 1)
            if "papers_count" in active:
                attrs["papers_count"] = rng.randint(5, 200)
            entities.append(Entity(
                f"Dr. {pool.pop()}",
                rng.choice(self.GROUP_NAMES), attrs,
            ))
        rng.shuffle(entities)
        return {"entities": entities, "active_attrs": active,
                "primary_attr": primary}

    def _render_details(self, e, active_attrs):
        parts = []
        a = e.attrs
        if "citations" in active_attrs and a.get("citations"):
            parts.append(f"has {a['citations']} total citations")
        if "h_index" in active_attrs and a.get("h_index"):
            parts.append(f"holds an h-index of {a['h_index']}")
        if "funding" in active_attrs and a.get("funding"):
            parts.append(f"secured ${a['funding']:,} in research funding")
        if "students" in active_attrs and a.get("students"):
            parts.append(f"supervises {a['students']} doctoral students")
        if "review_score" in active_attrs and a.get("review_score"):
            parts.append(f"received a review score of {a['review_score']}")
        if "papers_count" in active_attrs and a.get("papers_count"):
            parts.append(f"published {a['papers_count']} papers")
        return self._render_detail_list(parts) or "is an active researcher"

    def render_entity_doc(self, entity, active_attrs, rng):
        tmpl = rng.choice(self.DOC_TEMPLATES)
        return tmpl.format(
            name=entity.name.replace("Dr. ", ""), group=entity.group,
            topic=entity.attrs.get("_topic", "AI"),
            method=entity.attrs.get("_method", "novel approaches"),
            details=self._render_details(entity, active_attrs),
        )

    def render_correction(self, entity, attr, old_val, new_val):
        labels = {
            "citations": f"citation count corrected from {old_val} to {new_val}",
            "h_index": f"h-index updated from {old_val} to {new_val}",
            "funding": f"funding revised from ${old_val:,} to ${new_val:,}",
            "students": f"student count corrected from {old_val} to {new_val}",
            "review_score": f"review score updated from {old_val} to {new_val}",
            "papers_count": f"publication count corrected from {old_val} to {new_val}",
        }
        detail = labels.get(attr, f"{attr} changed from {old_val} to {new_val}")
        return f"CORRECTION NOTICE: {entity.name}'s {detail} per latest audit."

    WORKSHOP_TOPICS = [
        "Scalable Inference", "Federated Learning", "Causal Discovery",
        "Robustness Guarantees", "Efficient Fine-Tuning",
        "Multimodal Alignment", "Reward Modeling", "Data Curation",
    ]

    def generate_distractors(self, rng, entities, n=10):
        distractors = []
        for _ in range(min(n, len(entities))):
            organizer = rng.choice(entities)
            if rng.random() < 0.5:
                text = (
                    f"Workshop Announcement: {rng.choice(self.WORKSHOP_TOPICS)}\n"
                    f"  Organizer: {organizer.name} ({organizer.group})\n"
                    f"  Submission deadline: 2024-{rng.randint(1,12):02d}-"
                    f"{rng.randint(1,28):02d}\n"
                    f"  Expected submissions: {rng.randint(30,200)}"
                )
            else:
                text = (
                    f"Seminar Series: {rng.choice(TOPICS)}\n"
                    f"  Speaker: {organizer.name}\n"
                    f"  Venue: {organizer.group} {rng.randint(2024,2025)}\n"
                    f"  Duration: {rng.choice([1,2,3])} days"
                )
            distractors.append(Distractor(text))
        return distractors

    def _q_text(self, attr, name, rng=None):
        phrasings = {
            "citations": [
                f"How many citations does {name} have?",
                f"What is {name}'s total citation count?",
                f"Tell me the number of times {name} has been cited.",
                f"How often has {name}'s work been cited?",
                f"What is the citation total for {name}?",
            ],
            "h_index": [
                f"What is {name}'s h-index?",
                f"Tell me the h-index of {name}.",
                f"What Hirsch index does {name} hold?",
                f"Report {name}'s h-index value.",
                f"How high is {name}'s h-index?",
            ],
            "funding": [
                f"How much research funding has {name} secured?",
                f"What is {name}'s total research funding?",
                f"How much grant money has {name} received?",
                f"What funding amount has {name} been awarded?",
                f"Tell me {name}'s total grant funding.",
            ],
            "students": [
                f"How many doctoral students does {name} supervise?",
                f"How many advisees does {name} have?",
                f"What is the count of {name}'s doctoral students?",
                f"How many PhD students work under {name}?",
                f"Tell me how many students {name} advises.",
            ],
            "review_score": [
                f"What review score did {name} receive?",
                f"What is {name}'s peer review rating?",
                f"How was {name}'s paper scored by reviewers?",
                f"Tell me the review rating for {name}.",
                f"What score did reviewers give {name}?",
            ],
            "papers_count": [
                f"How many papers has {name} published?",
                f"What is {name}'s total publication count?",
                f"Tell me how many publications {name} has.",
                f"How many research papers are authored by {name}?",
                f"What is the publication total for {name}?",
            ],
        }
        opts = phrasings[attr]
        return rng.choice(opts) if rng else opts[0]

