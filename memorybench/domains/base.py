"""Domain abstract base class and shared data types."""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Entity:
    """Universal entity across all domains."""

    name: str
    group: str  # dept / venue / category
    attrs: dict[str, Any] = field(default_factory=dict)

    def get(self, attr: str, default=None):
        return self.attrs.get(attr, default)


@dataclass
class Distractor:
    """Non-queryable document that wastes agent write budget."""

    content: str


@dataclass
class QA:
    question: str
    answer: Any
    competency: str
    domain: str
    required_entities: list[str] = field(default_factory=list)
    is_fallback: bool = False


@dataclass
class Task:
    task_id: int
    domain: str
    documents: list[str]
    question: QA | None
    new_entity_names: list[str] = field(default_factory=list)
    global_id: int | None = None


@dataclass
class TaskResult:
    task_id: int
    competency: str
    domain: str
    is_correct: bool
    agent_answer: Any = None
    expected_answer: Any = None
    question_text: str = ""
    failure_reason: str = ""  # e.g. "no_entity", "attr_missing", "wrong_value"
    search_hits: int = 0  # how many memory entries matched


_HEDGE_PREFIXES = [
    "If the data is available, ",
    "If it was mentioned, ",
    "If you have that information, ",
    "Assuming it was recorded, ",
    "If you recall, ",
]


class Domain(ABC):
    """Abstract domain: entity generation, doc rendering, question generation."""

    name: str
    ALL_ATTRS: list[str]
    GROUP_NAMES: list[str]
    ATTR_SYNONYMS: dict[str, set[str]]
    DOC_TEMPLATES: list[str]
    BACKGROUND: list[str]

    @abstractmethod
    def generate_kb(self, seed: int, n_entities: int = 20) -> dict:
        """Returns {entities, active_attrs, primary_attr}."""

    @abstractmethod
    def render_entity_doc(self, entity: Entity, active_attrs: list[str],
                          rng: random.Random) -> str: ...

    @abstractmethod
    def render_correction(self, entity: Entity, attr: str,
                          old_val: Any, new_val: Any) -> str: ...

    # Subclasses set this for synthesis question phrasings
    SYNTHESIS_ENTITY_WORD: str = "entity"  # "person", "researcher", "product"

    @abstractmethod
    def generate_distractors(self, rng: random.Random,
                              entities: list[Entity],
                              n: int = 10) -> list[Distractor]: ...

    @abstractmethod
    def _q_text(self, attr: str, name: str, rng=None) -> str: ...

    def _q_text_mixed(self, attr: str, name: str, rng: random.Random) -> str:
        """Generate question text with 50% chance of hedge prefix.

        Both abstention and trick-retrieval use this, so wording distribution
        is identical — models cannot distinguish them by phrasing.
        """
        base = self._q_text(attr, name, rng)
        if rng.random() < 0.5:
            prefix = rng.choice(_HEDGE_PREFIXES)
            # Lowercase first char of base when prepending hedge
            base = base[0].lower() + base[1:] if base else base
            return prefix + base
        return base

    # ── Shared implementations ──

    def gen_retrieval_question(self, rng, exposed, active_attrs,
                               primary_attr) -> QA | None:
        attr = self._pick_attr(rng, active_attrs, primary_attr)
        cands = [e for e in exposed if e.get(attr)]
        if not cands:
            return None
        e = rng.choice(cands)
        return QA(self._q_text(attr, e.name, rng), e.get(attr), "retrieval",
                  self.name, [e.name])

    def gen_synthesis_question(self, rng, exposed, active_attrs,
                               primary_attr) -> QA | None:
        attr = self._pick_attr(rng, active_attrs, primary_attr)
        cands = [e for e in exposed if e.get(attr)]
        if len(cands) < 2:
            return None
        sel = rng.sample(cands, min(3, len(cands)))
        values = {e.name: e.get(attr) for e in sel}
        best = max(values, key=lambda k: (values[k], k))
        best_val = values[best]
        names = list(values.keys())
        ns = (f"{names[0]} and {names[1]}" if len(names) == 2
              else f"{', '.join(names[:-1])}, and {names[-1]}")
        ew = self.SYNTHESIS_ENTITY_WORD
        q = rng.choice([
            f"Among {ns}, which has the highest {attr}?",
            f"Between {ns}, which {ew} has the greatest {attr}?",
            f"Of {ns}, which ranks highest in {attr}?",
            f"Comparing {ns}, which leads in {attr}?",
            f"Which of {ns} has the top {attr}?",
            f"Which of {ns} scores the most in {attr}?",
            f"Comparing {ns}, which tops the list in {attr}?",
            f"Which of {ns} ranks first in {attr}?",
        ])
        return QA(q, f"{best} ({best_val})", "synthesis", self.name, names)

    def gen_abstention_question(self, rng, exposed,
                                active_attrs) -> QA | None:
        inactive = [a for a in self.ALL_ATTRS if a not in active_attrs]
        if not inactive:
            return None
        e = rng.choice(exposed)
        attr = rng.choice(inactive)
        return QA(self._q_text_mixed(attr, e.name, rng), "ABSTAIN",
                  "abstention", self.name, [e.name])

    def gen_trick_retrieval_question(self, rng, exposed: list[Entity],
                                      active_attrs: list[str],
                                      primary_attr: str) -> QA | None:
        """Generate a retrieval question phrased like an abstention question.

        Uses the same _q_text_mixed as abstention, so wording distribution
        is identical — but asks about an active attribute, so the correct
        answer is a concrete value. An always-abstain guesser will fail these.
        """
        attr = self._pick_attr(rng, active_attrs, primary_attr)
        cands = [e for e in exposed if e.get(attr)]
        if not cands:
            return None
        e = rng.choice(cands)
        return QA(self._q_text_mixed(attr, e.name, rng), e.get(attr),
                  "retrieval", self.name, [e.name])

    def gen_update_question(self, rng, exposed: list[Entity],
                            updates: dict) -> QA | None:
        valid = {n: u for n, u in updates.items()
                 if u["applied"] and any(e.name == n for e in exposed)}
        if not valid:
            return None
        name = rng.choice(list(valid.keys()))
        upd = valid[name]
        attr = upd["attr"]
        q = rng.choice([
            f"What is {name}'s current {attr} after the latest correction?",
            f"Following the recent audit, what is {name}'s updated {attr}?",
            f"{name}'s {attr} was recently revised. What is the new value?",
            f"After the correction notice, what does {name}'s {attr} stand at?",
            f"The records for {name}'s {attr} were amended. What is it now?",
        ])
        return QA(q, upd["new"], "update", self.name, [name])

    def format_structured(self, entity: Entity,
                          active_attrs: list[str]) -> str:
        parts = [entity.name, f"group={entity.group}"]
        for attr in active_attrs:
            val = entity.get(attr)
            if val is not None:
                parts.append(f"{attr}={val}")
        return " | ".join(parts)

    def has_attr_in_text(self, attr: str, text: str) -> bool:
        text_lower = text.lower()
        syns = self.ATTR_SYNONYMS.get(attr, {attr})
        return any(s in text_lower for s in syns)

    @staticmethod
    def _stable_hash(s: str) -> int:
        """Deterministic hash independent of PYTHONHASHSEED."""
        h = 0
        for c in s:
            h = (h * 31 + ord(c)) & 0xFFFFFFFF
        return h

    def _select_schema(self, seed: int):
        rng = random.Random(seed + self._stable_hash(self.name))
        # Cap at len-1 to guarantee at least one attribute is always excluded,
        # forcing adaptive storage strategies.
        n_active = rng.randint(3, len(self.ALL_ATTRS) - 1)
        active = rng.sample(self.ALL_ATTRS, n_active)
        primary = rng.choice(active)
        return active, primary

    def _pick_attr(self, rng, active_attrs: list[str],
                   primary_attr: str) -> str:
        if rng.random() < 0.5:
            return primary_attr
        return rng.choice(active_attrs)

    def _render_detail_list(self, parts: list[str]) -> str:
        if len(parts) >= 2:
            return ", ".join(parts[:-1]) + ", and " + parts[-1]
        return parts[0] if parts else ""
