"""World template abstraction for MemoryBench.

A WorldTemplate defines a complete domain: entity types, attribute schemas,
document styles, question patterns, and ground truth computation.

One template + one seed = one deterministic evaluation dataset.
Combinatorial entity/attribute space makes each template effectively infinite.

Anti-hack by design:
- ALL documents share identical structure (entity + numeric attributes)
- No structural distractors — every document is an entity profile
- Which entities get questioned is unpredictable per seed
- Which attributes get questioned varies per seed
- The agent has NO signal to distinguish "will be asked" from "won't be asked"
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from random import Random
from typing import Any


@dataclass
class AttrDef:
    """Attribute schema definition."""

    name: str
    dtype: str       # "int" or "float"
    min_val: float
    max_val: float
    unit: str = ""   # "$M", "%", etc.
    label: str = ""  # human-readable; defaults to name


@dataclass
class EntitySpec:
    """A generated entity with typed attributes."""

    name: str
    category: str
    attrs: dict[str, Any] = field(default_factory=dict)

    def get(self, attr: str, default=None):
        return self.attrs.get(attr, default)


@dataclass
class GeneratedQA:
    """A question with computable ground truth."""

    question: str
    answer: str
    competency: str
    required_entities: list[str] = field(default_factory=list)
    purpose: str = ""  # "recall", "coverage", "comprehension" (empty = legacy)


@dataclass
class World:
    """Complete deterministic world state from one seed."""

    entities: list[EntitySpec]
    attr_defs: list[AttrDef]
    active_attrs: list[str]
    categories: list[str]
    seed: int

    def get_entity(self, name: str) -> EntitySpec | None:
        for e in self.entities:
            if e.name == name:
                return e
        return None

    def entities_in_category(self, cat: str) -> list[EntitySpec]:
        return [e for e in self.entities if e.category == cat]


class WorldTemplate(ABC):
    """Abstract world template — one implementation = one infinite domain."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def all_attr_defs(self) -> list[AttrDef]: ...

    @property
    @abstractmethod
    def all_categories(self) -> list[str]: ...

    @property
    @abstractmethod
    def entity_word(self) -> str: ...

    @property
    def entity_word_plural(self) -> str:
        """Plural form. Override for irregular plurals."""
        w = self.entity_word
        if w.endswith("y"):
            return w[:-1] + "ies"
        return w + "s"

    @abstractmethod
    def _generate_names(self, rng: Random, n: int) -> list[str]: ...

    @abstractmethod
    def generate_entity(self, rng: Random, name: str, category: str,
                        active_attrs: list[str]) -> EntitySpec: ...

    @abstractmethod
    def render_document(self, entity: EntitySpec,
                        active_attrs: list[str], rng: Random) -> str: ...

    @abstractmethod
    def render_correction(self, entity: EntitySpec, attr: str,
                          old_val: Any, new_val: Any) -> str: ...

    @abstractmethod
    def _q_text(self, attr: str, name: str,
                rng: Random | None = None) -> str: ...

    # ── Concrete: world generation ──

    def generate_world(self, seed: int, n_entities: int,
                       n_active_attrs: int | None = None) -> World:
        """Generate a complete world. Deterministic for a given seed."""
        rng = Random(seed)
        all_defs = self.all_attr_defs

        if n_active_attrs is None:
            # Use most but not all attributes (enables abstention questions)
            n_active_attrs = max(3, len(all_defs) - rng.randint(1, 2))
        n_active_attrs = min(n_active_attrs, len(all_defs))

        selected = rng.sample(all_defs, n_active_attrs)
        active = [a.name for a in selected]
        names = self._generate_names(rng, n_entities)

        entities = []
        for nm in names:
            cat = rng.choice(self.all_categories)
            entities.append(self.generate_entity(rng, nm, cat, active))

        return World(
            entities=entities, attr_defs=selected,
            active_attrs=active, categories=self.all_categories,
            seed=seed,
        )

    def attr_label(self, attr_name: str) -> str:
        """Human-readable attribute label."""
        for a in self.all_attr_defs:
            if a.name == attr_name:
                return a.label or attr_name.replace("_", " ")
        return attr_name.replace("_", " ")

    # ── Concrete: question generation ──

    def gen_question(self, world: World, rng: Random,
                     competency: str,
                     available: list[EntitySpec]) -> GeneratedQA | None:
        """Generate a question of the given competency type."""
        fn = {
            "retrieval": self._gq_retrieval,
            "synthesis": self._gq_synthesis,
            "aggregation": self._gq_aggregation,
            "conditional": self._gq_conditional,
            "abstention": self._gq_abstention,
        }.get(competency)
        return fn(world, rng, available) if fn else None

    def _gq_retrieval(self, world, rng, available):
        attr = rng.choice(world.active_attrs)
        cands = [e for e in available if e.get(attr) is not None]
        if not cands:
            return None
        e = rng.choice(cands)
        return GeneratedQA(
            self._q_text(attr, e.name, rng),
            str(e.get(attr)), "retrieval", [e.name],
        )

    def _gq_synthesis(self, world, rng, available):
        if len(available) < 3:
            return None
        numeric = [a for a in world.active_attrs
                   if any(isinstance(e.get(a), (int, float))
                          for e in available)]
        if not numeric:
            return None
        attr = rng.choice(numeric)
        label = self.attr_label(attr)
        cands = [e for e in available
                 if isinstance(e.get(attr), (int, float))]
        if len(cands) < 3:
            return None
        sel = rng.sample(cands, 3)
        best = max(sel, key=lambda e: e.get(attr))
        names = [e.name for e in sel]
        ns = f"{names[0]}, {names[1]}, and {names[2]}"
        ew = self.entity_word
        q = rng.choice([
            f"Among {ns}, which {ew} has the highest {label}?",
            f"Between {ns}, which {ew} leads in {label}?",
            f"Comparing {ns}, which ranks first in {label}?",
        ])
        return GeneratedQA(
            q, f"{best.name} ({best.get(attr)})", "synthesis", names,
        )

    def _gq_aggregation(self, world, rng, available):
        numeric = [a for a in world.active_attrs
                   if sum(1 for e in available
                          if isinstance(e.get(a), (int, float))) >= 2]
        if not numeric:
            return None
        attr = rng.choice(numeric)
        label = self.attr_label(attr)
        by_cat: dict[str, list] = {}
        for e in available:
            if isinstance(e.get(attr), (int, float)):
                by_cat.setdefault(e.category, []).append(e)
        eligible = {c: es for c, es in by_cat.items() if len(es) >= 2}
        if not eligible:
            return None
        cat = rng.choice(list(eligible.keys()))
        members = eligible[cat]
        op = rng.choice(["total", "average"])
        values = [e.get(attr) for e in members]
        if op == "total":
            result = sum(values)
            if isinstance(result, float):
                result = round(result, 2)
        else:
            result = round(sum(values) / len(values), 2)
        ewp = self.entity_word_plural
        q = rng.choice([
            f"What is the {op} {label} across {cat} {ewp}?",
            f"Calculate the {op} {label} for all {cat} {ewp}.",
        ])
        return GeneratedQA(
            q, str(result), "aggregation", [e.name for e in members],
        )

    def _gq_conditional(self, world, rng, available):
        numeric = [a for a in world.active_attrs
                   if sum(1 for e in available
                          if isinstance(e.get(a), (int, float))) >= 4]
        if len(numeric) < 2:
            return None
        a1, a2 = rng.sample(numeric, 2)
        l1, l2 = self.attr_label(a1), self.attr_label(a2)
        cands = [e for e in available
                 if isinstance(e.get(a1), (int, float))
                 and isinstance(e.get(a2), (int, float))]
        if len(cands) < 4:
            return None
        vals = sorted(e.get(a1) for e in cands)
        threshold = vals[len(vals) // 2]
        filtered = [e for e in cands if e.get(a1) > threshold]
        if len(filtered) < 2:
            return None
        best = max(filtered, key=lambda e: (e.get(a2), e.name))
        ewp = self.entity_word_plural
        q = rng.choice([
            f"Among {ewp} with {l1} above {threshold}, "
            f"which has the highest {l2}?",
            f"Considering only {ewp} whose {l1} exceeds {threshold}, "
            f"who leads in {l2}?",
        ])
        return GeneratedQA(
            q, f"{best.name} ({best.get(a2)})",
            "conditional", [best.name],
        )

    # ── Concrete: post-storage adaptive questioning ──

    def detect_stored_entities(
        self, world: World, stored_contents: list[str],
    ) -> tuple[set[str], set[str]]:
        """Scan stored contents and detect which World entities were stored.

        Default: case-insensitive substring match on entity names.
        Subclasses can override for abbreviations / transformations.

        Returns: (stored_names, missed_names)
        """
        blob = "\n".join(stored_contents).lower()
        stored: set[str] = set()
        missed: set[str] = set()
        for e in world.entities:
            if e.name.lower() in blob:
                stored.add(e.name)
            else:
                missed.add(e.name)
        return stored, missed

    def gen_adaptive_questions(
        self, world: World, rng: Random,
        introduced: list[EntitySpec],
        stored_names: set[str],
        n_questions: int,
    ) -> list[GeneratedQA]:
        """Generate post-storage adaptive questions.

        Question allocation:
        - recall  (~40%): retrieve stored entities (tests retrieval)
        - coverage (~30%): retrieve random entities incl. missed (tests storage quality)
        - comprehension (~30%): synthesis/aggregation/conditional (tests reasoning)

        Recall and coverage both use _gq_retrieval → identical wording → agent
        cannot distinguish them. Final list is shuffled to remove ordering signal.
        """
        stored_ents = [e for e in introduced if e.name in stored_names]
        missed_ents = [e for e in introduced if e.name not in stored_names]

        # Budget allocation (handle edge cases)
        n_recall = round(n_questions * 0.4) if stored_ents else 0
        n_coverage = round(n_questions * 0.3) if missed_ents else 0
        n_comprehension = n_questions - n_recall - n_coverage
        # Redistribute surplus when one pool is empty
        if not stored_ents:
            n_comprehension = n_questions - n_coverage
        if not missed_ents:
            n_comprehension = n_questions - n_recall

        questions: list[GeneratedQA] = []

        # Recall: from stored pool
        for _ in range(n_recall):
            q = self._gq_retrieval(world, rng, stored_ents)
            if q:
                q.purpose = "recall"
                questions.append(q)

        # Coverage: from missed pool
        for _ in range(n_coverage):
            q = self._gq_retrieval(world, rng, missed_ents)
            if q:
                q.purpose = "coverage"
                questions.append(q)

        # Comprehension: synthesis/aggregation/conditional from all
        comp_types = ["synthesis", "aggregation", "conditional"]
        for i in range(n_comprehension):
            ctype = comp_types[i % len(comp_types)]
            fn = {"synthesis": self._gq_synthesis,
                  "aggregation": self._gq_aggregation,
                  "conditional": self._gq_conditional}[ctype]
            q = fn(world, rng, introduced)
            if q:
                q.purpose = "comprehension"
                questions.append(q)

        # Abstention: 1-2 questions
        for _ in range(rng.randint(1, 2)):
            q = self._gq_abstention(world, rng, introduced)
            if q:
                q.purpose = "comprehension"
                questions.append(q)

        rng.shuffle(questions)
        return questions

    def _gq_abstention(self, world, rng, available):
        all_names = {a.name for a in self.all_attr_defs}
        inactive = list(all_names - set(world.active_attrs))
        if not inactive or not available:
            return None
        e = rng.choice(available)
        attr = rng.choice(inactive)
        return GeneratedQA(
            self._q_text(attr, e.name, rng),
            "ABSTAIN", "abstention", [e.name],
        )
