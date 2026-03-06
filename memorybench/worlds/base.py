"""World template abstraction for MemoryBench.

A WorldTemplate defines a complete domain: entity types, attribute schemas,
document styles, question patterns, and ground truth computation.

One template + one seed = one deterministic evaluation dataset.
Combinatorial entity/attribute space makes each template effectively infinite.

Design principles:
- ALL documents share identical structure → no format-based hacking
- Document volume >> write budget → compression is necessary
- Corrections mutate world state → memory maintenance is testable
- Questions test different abilities: precision, organization, maintenance
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
    agg_ops: tuple[str, ...] = ("total", "average")  # valid aggregation ops


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
    purpose: str = ""  # "recall", "coverage", "comprehension", "update", ...


@dataclass
class SentenceTemplate:
    """Narrative sentence template embedding an attribute value with distractors."""

    template: str       # Format string: {val}, {distractor}, {other_name}, {other_val}
    attr: str           # Primary attribute name
    distractor: str     # "temporal" | "comparative" | "qualified" | "none"


@dataclass
class Correction:
    """A correction event that mutates world state."""

    entity_name: str
    attr: str
    old_val: Any
    new_val: Any
    notice: str  # rendered correction document


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


def _possessive(name: str) -> str:
    """English possessive form: 'Ravens' → 'Ravens'', 'Chen' → 'Chen's'."""
    return f"{name}'" if name.endswith("s") else f"{name}'s"


class WorldTemplate(ABC):
    """Abstract world template — one implementation = one infinite domain.

    Evaluation flow:
      generate_world(seed) → World
        → render_document() → agent sees narrative docs (large volume)
        → agent stores (under write budget → must compress)
        → generate_corrections() → correction notices → agent updates memory
        → detect_stored_entities() → stored/missed sets
        → gen_adaptive_questions() → questions + GT (from mutated World state)
    """

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
                        active_attrs: list[str], rng: Random,
                        other_entities: list[EntitySpec] | None = None
                        ) -> str: ...

    @abstractmethod
    def render_correction(self, entity: EntitySpec, attr: str,
                          old_val: Any, new_val: Any) -> str: ...

    @abstractmethod
    def _q_text(self, attr: str, name: str,
                rng: Random | None = None) -> str: ...

    @abstractmethod
    def _format_value(self, attr: str, val: Any) -> str:
        """Format an attribute value for display. Subclasses must implement."""
        ...

    @abstractmethod
    def _sentence_templates(self) -> dict[str, list[SentenceTemplate]]:
        """Return {attr_name: [SentenceTemplate, ...]} for narrative docs."""
        ...

    @abstractmethod
    def _ratio_pairs(self) -> list[tuple[str, str, str]]:
        """Return (attr1, attr2, label) triples for ratio questions."""
        ...

    # ── Concrete: world generation ──

    def generate_world(self, seed: int, n_entities: int,
                       n_active_attrs: int | None = None,
                       eval_salt: int = 0) -> World:
        """Generate a complete world. Deterministic for a given seed+salt.

        Args:
            eval_salt: Perturb numeric values to invalidate pre-computed
                answers for a given seed. Same seed + different salt →
                same entities/structure but different numeric values.
        """
        rng = Random(seed)
        all_defs = self.all_attr_defs

        if n_active_attrs is None:
            n_active_attrs = max(3, len(all_defs) - rng.randint(1, 2))
        n_active_attrs = min(n_active_attrs, len(all_defs))

        selected = rng.sample(all_defs, n_active_attrs)
        active = [a.name for a in selected]
        names = self._generate_names(rng, n_entities)

        entities = []
        for nm in names:
            cat = rng.choice(self.all_categories)
            entities.append(self.generate_entity(rng, nm, cat, active))

        # Apply eval_salt perturbation
        if eval_salt:
            self._apply_eval_salt(entities, selected, active, eval_salt)

        return World(
            entities=entities, attr_defs=selected,
            active_attrs=active, categories=self.all_categories,
            seed=seed,
        )

    def _apply_eval_salt(self, entities: list[EntitySpec],
                         attr_defs: list[AttrDef],
                         active_attrs: list[str],
                         salt: int) -> None:
        """Perturb numeric attribute values deterministically by salt.

        Maintains relative ordering and value ranges, but shifts values
        enough that pre-computed answers for salt=0 become wrong.
        """
        salt_rng = Random(salt)
        for entity in entities:
            for adef in attr_defs:
                if adef.name not in active_attrs:
                    continue
                val = entity.get(adef.name)
                if val is None:
                    continue
                # Perturb by 5-15% of the range
                range_size = adef.max_val - adef.min_val
                delta = salt_rng.uniform(0.05, 0.15) * range_size
                direction = salt_rng.choice([-1, 1])
                new_val = val + direction * delta
                new_val = max(adef.min_val, min(adef.max_val, new_val))
                if adef.dtype == "int":
                    new_val = int(round(new_val))
                    if new_val == val:
                        new_val = val + (1 if val < adef.max_val else -1)
                else:
                    new_val = round(new_val, 2)
                entity.attrs[adef.name] = new_val

    def attr_label(self, attr_name: str) -> str:
        """Human-readable attribute label."""
        for a in self.all_attr_defs:
            if a.name == attr_name:
                return a.label or attr_name.replace("_", " ")
        return attr_name.replace("_", " ")

    # ── Concrete: compact document helper ──

    def _compact_document(self, entity: EntitySpec,
                          active_attrs: list[str]) -> str:
        """Render entity attributes as compact key-value line.

        Volume pressure comes from entity quantity, not document padding.
        All entities share identical structure (anti-hack).
        """
        parts = []
        for attr in active_attrs:
            val = entity.get(attr)
            if val is not None:
                label = self.attr_label(attr)
                parts.append(f"{label}: {self._format_value(attr, val)}")
        return " | ".join(parts)

    # ── Concrete: narrative document ──

    def _render_narrative(self, entity: EntitySpec,
                          active_attrs: list[str], rng: Random,
                          other_entities: list[EntitySpec]) -> str:
        """Render entity as narrative prose with embedded distractors."""
        templates_map = self._sentence_templates()
        sentences = []
        for attr in active_attrs:
            val = entity.get(attr)
            if val is None:
                continue
            attr_tmpls = templates_map.get(attr)
            if not attr_tmpls:
                label = self.attr_label(attr)
                sentences.append(
                    f"{label}: {self._format_value(attr, val)}")
                continue
            st = rng.choice(attr_tmpls)
            fmt_val = self._format_value(attr, val)
            kwargs: dict[str, str] = {"val": fmt_val,
                                      "label": self.attr_label(attr)}
            if st.distractor == "temporal" and isinstance(val, (int, float)):
                old = val * rng.uniform(0.5, 0.9)
                old = (int(round(old)) if isinstance(val, int)
                       else round(old, 2))
                kwargs["distractor"] = self._format_value(attr, old)
            elif st.distractor == "comparative":
                # Use a fabricated peer reference — never a real entity
                # name+value, to avoid leaking detectable data.
                if isinstance(val, (int, float)):
                    peer_val = val * rng.uniform(0.6, 1.4)
                    peer_val = (int(round(peer_val))
                                if isinstance(val, int)
                                else round(peer_val, 2))
                    kwargs["other_name"] = "the industry average"
                    kwargs["other_val"] = self._format_value(
                        attr, peer_val)
                else:
                    sentences.append(
                        f"{self.attr_label(attr)}: {fmt_val}")
                    continue
            elif (st.distractor == "qualified"
                  and isinstance(val, (int, float))):
                partial = val * rng.uniform(0.6, 0.9)
                partial = (int(round(partial)) if isinstance(val, int)
                           else round(partial, 2))
                kwargs["distractor"] = self._format_value(attr, partial)
            try:
                sentences.append(st.template.format(**kwargs))
            except KeyError:
                sentences.append(
                    f"{self.attr_label(attr)}: {fmt_val}")
        rng.shuffle(sentences)
        paragraphs = []
        i = 0
        while i < len(sentences):
            n = min(rng.choice([2, 3]), len(sentences) - i)
            chunk = sentences[i:i + n]
            paragraphs.append(
                ". ".join(s.rstrip(".") for s in chunk) + ".")
            i += n
        return "\n\n".join(paragraphs)

    def _render_body(self, entity: EntitySpec,
                     active_attrs: list[str], rng: Random,
                     other_entities: list[EntitySpec] | None = None
                     ) -> str:
        """Render body: narrative if other_entities given, else compact KV."""
        if other_entities is not None:
            return self._render_narrative(
                entity, active_attrs, rng, other_entities)
        return self._compact_document(entity, active_attrs)

    # ── Concrete: corrections ──

    def generate_corrections(
        self, world: World, rng: Random, n: int,
    ) -> list[Correction]:
        """Generate corrections and update World state in place.

        Mutates entity attributes to new values. Returns correction notices.
        After this call, world.entities hold the UPDATED values (new GT).
        """
        corrections: list[Correction] = []
        candidates = [e for e in world.entities
                      if sum(1 for a in world.active_attrs
                             if e.get(a) is not None) >= 2]
        if not candidates:
            return corrections
        targets = rng.sample(candidates, min(n, len(candidates)))

        for entity in targets:
            viable = [a for a in world.active_attrs
                      if entity.get(a) is not None]
            attr = rng.choice(viable)
            old_val = entity.get(attr)
            adef = next(a for a in world.attr_defs if a.name == attr)

            # Perturb value by 10-50%
            if adef.dtype == "int":
                magnitude = max(1, int(abs(old_val) * rng.uniform(0.1, 0.5)))
                new_val = old_val + rng.choice([-1, 1]) * magnitude
                new_val = max(int(adef.min_val), min(int(adef.max_val), new_val))
                if new_val == old_val:
                    new_val = old_val + (1 if old_val < adef.max_val else -1)
            else:
                delta = old_val * rng.uniform(0.1, 0.5) * rng.choice([-1, 1])
                new_val = round(old_val + delta, 2)
                new_val = max(adef.min_val, min(adef.max_val, new_val))
                if new_val == old_val:
                    new_val = round(old_val + 0.1, 2)

            notice = self.render_correction(entity, attr, old_val, new_val)
            entity.attrs[attr] = new_val  # MUTATE world state
            corrections.append(Correction(
                entity_name=entity.name, attr=attr,
                old_val=old_val, new_val=new_val, notice=notice,
            ))

        return corrections

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
            "ratio": self._gq_ratio,
            "comparison": self._gq_comparison,
            "multi_hop": self._gq_multi_hop,
            "outlier": self._gq_outlier,
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

    def _gq_retrieval_diverse(self, world, rng, available,
                              used_entities: set[str],
                              used_attrs: set[str]):
        """Retrieval with entity and attribute deduplication."""
        unused_attrs = [a for a in world.active_attrs if a not in used_attrs]
        attr_pool = unused_attrs if unused_attrs else list(world.active_attrs)
        rng.shuffle(attr_pool)

        for attr in attr_pool:
            cands = [e for e in available if e.get(attr) is not None]
            if not cands:
                continue
            fresh = [e for e in cands if e.name not in used_entities]
            pool = fresh if fresh else cands
            e = rng.choice(pool)
            used_attrs.add(attr)
            return GeneratedQA(
                self._q_text(attr, e.name, rng),
                str(e.get(attr)), "retrieval", [e.name],
            )
        return None

    def _gq_synthesis(self, world, rng, available):
        if len(available) < 5:
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
        if len(cands) < 5:
            return None
        sel = rng.sample(cands, 5)
        use_max = rng.choice([True, False])
        target = (max if use_max else min)(sel, key=lambda e: e.get(attr))
        names = [e.name for e in sel]
        ns = f"{names[0]}, {names[1]}, {names[2]}, {names[3]}, and {names[4]}"
        ew = self.entity_word
        if use_max:
            q = rng.choice([
                f"Among {ns}, which {ew} has the highest {label}?",
                f"Between {ns}, which {ew} leads in {label}?",
                f"Comparing {ns}, which ranks first in {label}?",
            ])
        else:
            q = rng.choice([
                f"Among {ns}, which {ew} has the lowest {label}?",
                f"Between {ns}, which {ew} has the least {label}?",
                f"Comparing {ns}, which ranks last in {label}?",
            ])
        return GeneratedQA(
            q, f"{target.name} ({target.get(attr)})", "synthesis", names,
        )

    _MAX_AGG_MEMBERS = 4

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
        if len(members) > self._MAX_AGG_MEMBERS:
            members = rng.sample(members, self._MAX_AGG_MEMBERS)
        adef = next((a for a in world.attr_defs if a.name == attr), None)
        ops = list(adef.agg_ops) if adef and adef.agg_ops else ["total", "average"]
        op = rng.choice(ops)
        values = [e.get(attr) for e in members]
        if op == "total":
            result = sum(values)
            if isinstance(result, float):
                result = round(result, 2)
        else:
            result = round(sum(values) / len(values), 2)
        names = [e.name for e in members]
        if len(names) == 2:
            ns = f"{names[0]} and {names[1]}"
        else:
            ns = ", ".join(names[:-1]) + f", and {names[-1]}"
        q = rng.choice([
            f"What is the {op} {label} across {ns}?",
            f"Calculate the {op} {label} for {ns}.",
        ])
        return GeneratedQA(q, str(result), "aggregation", names)

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

    def _gq_update(self, world, rng, corrections):
        """Ask about a corrected attribute. GT = updated (current) value."""
        if not corrections:
            return None
        c = rng.choice(corrections)
        entity = world.get_entity(c.entity_name)
        if not entity:
            return None
        # GT is the current (corrected) value in world state
        current_val = entity.get(c.attr)
        if current_val is None:
            return None
        return GeneratedQA(
            self._q_text(c.attr, c.entity_name, rng),
            str(current_val), "update", [c.entity_name],
        )

    def _gq_abstention(self, world, rng, available):
        """Ask about a fictitious entity using an active attribute.

        The agent cannot distinguish "entity I didn't store" from
        "entity that never existed" — only high-coverage agents can
        confidently answer ABSTAIN.
        """
        existing = {e.name for e in world.entities}
        decoy_rng = Random(rng.randint(0, 2**31))
        for _ in range(100):
            candidates = self._generate_names(decoy_rng, 1)
            if candidates[0] not in existing:
                attr = rng.choice(world.active_attrs)
                return GeneratedQA(
                    self._q_text(attr, candidates[0], rng),
                    "ABSTAIN", "abstention", [candidates[0]],
                )
        return None

    def _gq_trick_retrieval(self, world, rng, available):
        """Ask about a real entity using abstention-like phrasing.

        Phrased as if the agent might want to abstain ("Do you have
        any data on..."), but the GT is a real value from a real entity.
        Defeats always-abstain strategies: if the agent always says
        "I don't know", it will fail these questions.
        """
        attr = rng.choice(world.active_attrs)
        cands = [e for e in available if e.get(attr) is not None]
        if not cands:
            return None
        e = rng.choice(cands)
        # Use the standard _q_text — identical wording to retrieval/update
        return GeneratedQA(
            self._q_text(attr, e.name, rng),
            str(e.get(attr)), "retrieval", [e.name],
        )

    # ── Concrete: derived-value questions ──

    def _gq_ratio(self, world, rng, available):
        """Ratio question: attr1/attr2 for one entity."""
        pairs = self._ratio_pairs()
        if not pairs:
            return None
        rng.shuffle(pairs)
        for a1, a2, label in pairs:
            if a1 not in world.active_attrs or a2 not in world.active_attrs:
                continue
            cands = [e for e in available
                     if isinstance(e.get(a1), (int, float))
                     and isinstance(e.get(a2), (int, float))
                     and e.get(a2) != 0]
            if not cands:
                continue
            e = rng.choice(cands)
            result = round(e.get(a1) / e.get(a2), 2)
            q = rng.choice([
                f"What is {_possessive(e.name)} {label}?",
                f"Calculate {_possessive(e.name)} {label}.",
                f"How much is {_possessive(e.name)} {label}?",
            ])
            return GeneratedQA(q, str(result), "ratio", [e.name])
        return None

    def _gq_comparison(self, world, rng, available):
        """Comparison: which of two entities has higher attr, and by how much."""
        numeric = [a for a in world.active_attrs
                   if sum(1 for e in available
                          if isinstance(e.get(a), (int, float))) >= 2]
        if not numeric:
            return None
        attr = rng.choice(numeric)
        label = self.attr_label(attr)
        cands = [e for e in available
                 if isinstance(e.get(attr), (int, float))]
        if len(cands) < 2:
            return None
        e_a, e_b = rng.sample(cands, 2)
        v_a, v_b = e_a.get(attr), e_b.get(attr)
        if v_a >= v_b:
            winner, diff = e_a.name, v_a - v_b
        else:
            winner, diff = e_b.name, v_b - v_a
        if isinstance(v_a, int):
            diff = int(round(diff))
        else:
            diff = round(diff, 2)
        ew = self.entity_word
        q = (f"Does {e_a.name} or {e_b.name} have higher "
             f"{label}? By how much?")
        return GeneratedQA(
            q, f"{winner} ({diff})", "comparison",
            [e_a.name, e_b.name],
        )

    def _gq_delta(self, world, rng, corrections):
        """Change amount from a correction."""
        if not corrections:
            return None
        c = rng.choice(corrections)
        entity = world.get_entity(c.entity_name)
        if not entity:
            return None
        label = self.attr_label(c.attr)
        delta = abs(c.new_val - c.old_val)
        if isinstance(c.old_val, int):
            delta = int(round(delta))
        else:
            delta = round(delta, 2)
        q = rng.choice([
            f"What is the difference between {_possessive(c.entity_name)} "
            f"old and new {label}?",
            f"How much did {_possessive(c.entity_name)} "
            f"{label} shift?",
            f"Calculate the change in {_possessive(c.entity_name)} "
            f"{label}.",
        ])
        return GeneratedQA(
            q, str(delta), "delta", [c.entity_name],
        )

    def _gq_multi_hop(self, world, rng, available):
        """Two-step reasoning: find best category, then find extreme in it.

        Step 1: Compute average of attr1 per category.
        Step 2: In the top category, find entity with min/max attr2.
        Requires agent to store multiple entities per category.
        """
        numeric = [a for a in world.active_attrs
                   if sum(1 for e in available
                          if isinstance(e.get(a), (int, float))) >= 4]
        if len(numeric) < 2:
            return None
        a1, a2 = rng.sample(numeric, 2)
        l1, l2 = self.attr_label(a1), self.attr_label(a2)
        # Group by category, need ≥2 entities per category
        by_cat: dict[str, list[EntitySpec]] = {}
        for e in available:
            if (isinstance(e.get(a1), (int, float))
                    and isinstance(e.get(a2), (int, float))):
                by_cat.setdefault(e.category, []).append(e)
        eligible = {c: es for c, es in by_cat.items() if len(es) >= 2}
        if len(eligible) < 2:
            return None
        # Step 1: category with highest average attr1
        cat_avgs = {c: sum(e.get(a1) for e in es) / len(es)
                    for c, es in eligible.items()}
        use_max_cat = rng.choice([True, False])
        best_cat = (max if use_max_cat else min)(
            cat_avgs, key=cat_avgs.get)
        # Step 2: in that category, find extreme of attr2
        use_max_entity = rng.choice([True, False])
        target = (max if use_max_entity else min)(
            eligible[best_cat], key=lambda e: e.get(a2))
        all_names = [e.name for e in eligible[best_cat]]
        cat_dir = "highest" if use_max_cat else "lowest"
        ent_dir = "highest" if use_max_entity else "lowest"
        ewp = self.entity_word_plural
        ew = self.entity_word
        q = rng.choice([
            f"Among {ewp} in the group with the {cat_dir} "
            f"average {l1}, which {ew} has the {ent_dir} {l2}?",
            f"Considering {ewp} whose group averages the "
            f"{cat_dir} {l1}, which has the {ent_dir} {l2}?",
            f"In the sector averaging the {cat_dir} {l1}, "
            f"which {ew} has the {ent_dir} {l2}?",
        ])
        return GeneratedQA(
            q, f"{target.name} ({target.get(a2)})",
            "multi_hop", all_names,
        )

    def _gq_outlier(self, world, rng, available):
        """Find the entity whose attr deviates most from group mean.

        Requires computing mean of 5 values, then finding max |val - mean|.
        """
        if len(available) < 5:
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
        if len(cands) < 5:
            return None
        sel = rng.sample(cands, 5)
        values = [e.get(attr) for e in sel]
        mean = sum(values) / len(values)
        # Find max absolute deviation
        outlier = max(sel, key=lambda e: abs(e.get(attr) - mean))
        deviation = abs(outlier.get(attr) - mean)
        if isinstance(values[0], int):
            deviation = round(deviation, 1)
        else:
            deviation = round(deviation, 2)
        names = [e.name for e in sel]
        ns = ", ".join(names[:-1]) + f", and {names[-1]}"
        ew = self.entity_word
        q = rng.choice([
            f"Among {ns}, which {ew}'s {label} differs most "
            f"from the average of the group?",
            f"Comparing {ns}, whose {label} is furthest "
            f"from the mean?",
            f"Between {ns}, which {ew} has the most unusual "
            f"{label} relative to the others?",
        ])
        return GeneratedQA(
            q, f"{outlier.name} ({deviation})",
            "outlier", names,
        )

    # ── Concrete: post-storage adaptive questioning ──

    def _numeric_variants(self, attr: str, val: Any) -> list[str]:
        """Generate string variants of a value for fuzzy detection.

        Covers formatted display, raw numeric, rounded integer, and
        common decimal representations an agent might use when compressing.
        """
        variants: list[str] = []
        variants.append(self._format_value(attr, val).lower().replace(",", ""))
        if isinstance(val, (int, float)):
            variants.append(str(val).lower())
            variants.append(str(int(round(val))))
            if isinstance(val, float):
                variants.append(f"{val:.1f}")
                variants.append(f"{val:.0f}")
        return variants

    def detect_stored_entities(
        self, world: World, stored_contents: list[str],
    ) -> tuple[set[str], set[str]]:
        """Scan stored contents and detect which World entities were stored.

        Anti-hack: requires entity name AND at least one attribute value
        to appear in the SAME stored entry. Name-only packing without
        values won't inflate coverage. Checks multiple value representations
        (formatted, raw, rounded, decimal) to handle agent compression
        and backend reformulation.
        """
        stored: set[str] = set()
        missed: set[str] = set()
        for e in world.entities:
            name_lower = e.name.lower()
            found = False
            for content in stored_contents:
                cl = content.lower().replace(",", "")
                if name_lower not in content.lower():
                    continue
                for a in world.active_attrs:
                    val = e.get(a)
                    if val is None:
                        continue
                    variants = self._numeric_variants(a, val)
                    if any(v in cl for v in variants):
                        found = True
                        break
                if found:
                    break
            (stored if found else missed).add(e.name)
        return stored, missed

    def generate_stream(
        self, world: World, rng: Random,
        corrections: list[Correction],
        stored_names: set[str],
        n_questions: int,
        entities_per_batch: int = 10,
    ) -> list[dict]:
        """Generate an interleaved evaluation stream.

        Returns a list of events, each a dict with:
          type: "ingest" | "correction" | "question"
          + type-specific fields

        Stream structure:
          - Entities arrive in batches of entities_per_batch
          - After batch 2+, questions may appear (30% per batch)
          - Corrections arrive at ~60% through entity batches
          - Remaining questions come after all entities are ingested
          - Agent never knows what event comes next

        This adds uncertainty pressure: the agent can't adopt
        "store everything first, answer later" because questions
        arrive during ingest.
        """
        events: list[dict] = []
        entities = list(world.entities)
        n_batches = max(1, len(entities) // entities_per_batch)
        correction_batch = max(1, int(n_batches * 0.6))

        # Track introduced entities for question generation
        introduced: list[EntitySpec] = []
        questions_emitted = 0

        # Decide how many questions to emit during ingest (~40%)
        n_mid_questions = max(1, int(n_questions * 0.4))
        mid_q_schedule: set[int] = set()
        if n_batches > 2:
            # Distribute mid-stream questions across batches 2+
            possible = list(range(2, n_batches))
            rng_sched = Random(rng.randint(0, 2**31))
            rng_sched.shuffle(possible)
            for i in range(min(n_mid_questions, len(possible))):
                mid_q_schedule.add(possible[i])

        for batch_idx in range(n_batches):
            start = batch_idx * entities_per_batch
            end = min(start + entities_per_batch, len(entities))
            batch_entities = entities[start:end]

            # Render and emit ingest event (narrative mode)
            docs = [self.render_document(e, world.active_attrs, rng,
                                         other_entities=batch_entities)
                    for e in batch_entities]
            events.append({
                "type": "ingest",
                "batch": batch_idx + 1,
                "total_batches": n_batches,
                "documents": docs,
                "entity_names": [e.name for e in batch_entities],
            })
            introduced.extend(batch_entities)

            # Emit corrections at correction_batch
            if batch_idx == correction_batch and corrections:
                for c in corrections:
                    events.append({
                        "type": "correction",
                        "notice": c.notice,
                        "entity_name": c.entity_name,
                        "attr": c.attr,
                    })

            # Emit a question if scheduled
            if batch_idx in mid_q_schedule and len(introduced) >= 5:
                q = self._generate_one_question(
                    world, rng, introduced, stored_names,
                    corrections if batch_idx > correction_batch else None,
                )
                if q:
                    # NOTE: 'purpose' is for scoring only. NEVER include in agent-facing prompts.
                    events.append({
                        "type": "question",
                        "question": q.question,
                        "answer": q.answer,
                        "competency": q.competency,
                        "purpose": q.purpose,
                        "required_entities": q.required_entities,
                    })
                    questions_emitted += 1

        # Emit remaining questions after all ingest
        remaining = n_questions - questions_emitted
        remaining_qs = self.gen_adaptive_questions(
            world, rng, introduced, stored_names, remaining, corrections,
        )
        for q in remaining_qs:
            # NOTE: 'purpose' is for scoring only. NEVER include in agent-facing prompts.
            events.append({
                "type": "question",
                "question": q.question,
                "answer": q.answer,
                "competency": q.competency,
                "purpose": q.purpose,
                "required_entities": q.required_entities,
            })

        return events

    def _generate_one_question(
        self, world: World, rng: Random,
        introduced: list[EntitySpec],
        stored_names: set[str],
        corrections: list[Correction] | None,
    ) -> GeneratedQA | None:
        """Generate a single random question for mid-stream emission."""
        # Weighted choice: retrieval-heavy during mid-stream
        roll = rng.random()
        if roll < 0.5:
            q = self._gq_retrieval(world, rng, introduced)
            if q:
                name = q.required_entities[0]
                q.purpose = "recall" if name in stored_names else "coverage"
                return q
        elif roll < 0.75 and corrections:
            q = self._gq_update(world, rng, corrections)
            if q:
                q.purpose = "update"
                return q
        elif roll < 0.90 and len(introduced) >= 5:
            q = self._gq_synthesis(world, rng, introduced)
            if q:
                q.purpose = "comprehension"
                return q
        # Fallback: abstention
        q = self._gq_abstention(world, rng, introduced)
        if q:
            q.purpose = "abstention"
            return q
        return None

    def gen_adaptive_questions(
        self, world: World, rng: Random,
        introduced: list[EntitySpec],
        stored_names: set[str],
        n_questions: int,
        corrections: list[Correction] | None = None,
    ) -> list[GeneratedQA]:
        """Generate post-storage adaptive questions.

        Budget allocation (with corrections):
          retrieval 40% | comprehension 25% | update 20% | abstention 15%
        Budget allocation (without corrections):
          retrieval 50% | comprehension 40% | abstention 10%

        Update questions use the same _q_text as retrieval → agent cannot
        distinguish them by wording. The GT is the CORRECTED value.
        """
        has_corrections = bool(corrections)

        # Trick retrieval: ~2 per evaluation — phrased like abstention
        # but with real GT. Defeats always-abstain strategy.
        n_trick = min(2, max(1, n_questions // 10))

        if has_corrections:
            n_update = max(1, round(n_questions * 0.2))
            n_update = min(n_update, len(corrections))
            n_delta = max(1, n_update // 3)
            n_retrieval = round(n_questions * 0.4) - n_trick
            n_abstention = max(1, round(n_questions * 0.15))
            n_comprehension = (n_questions - n_retrieval - n_update
                               - n_abstention - n_trick - n_delta)
        else:
            n_update = 0
            n_delta = 0
            n_retrieval = round(n_questions * 0.5) - n_trick
            n_abstention = max(1, round(n_questions * 0.1))
            n_comprehension = n_questions - n_retrieval - n_abstention - n_trick

        questions: list[GeneratedQA] = []

        # Retrieval: deduped entities and attributes
        used_entities: set[str] = set()
        used_attrs: set[str] = set()
        for _ in range(n_retrieval):
            q = self._gq_retrieval_diverse(
                world, rng, introduced, used_entities, used_attrs)
            if q:
                name = q.required_entities[0]
                q.purpose = "recall" if name in stored_names else "coverage"
                used_entities.add(name)
                questions.append(q)

        # Update: ask about corrected values (same wording as retrieval!)
        used_correction_entities: set[str] = set()
        for _ in range(n_update):
            # Avoid asking same corrected entity twice
            remaining = [c for c in (corrections or [])
                         if c.entity_name not in used_correction_entities]
            if not remaining:
                break
            q = self._gq_update(world, rng, remaining)
            if q:
                q.purpose = "update"
                used_correction_entities.add(q.required_entities[0])
                questions.append(q)

        # Delta: change amount from corrections (~25% of update budget)
        if has_corrections and n_delta > 0:
            used_delta_entities: set[str] = set()
            for _ in range(n_delta):
                remaining_c = [c for c in (corrections or [])
                               if c.entity_name not in used_delta_entities]
                if not remaining_c:
                    break
                q = self._gq_delta(world, rng, remaining_c)
                if q:
                    q.purpose = "comprehension"
                    used_delta_entities.add(q.required_entities[0])
                    questions.append(q)

        # Comprehension: multi-step reasoning + basic computation
        comp_types = ["synthesis", "aggregation", "conditional",
                      "ratio", "comparison", "multi_hop", "outlier"]
        rng.shuffle(comp_types)
        for i in range(n_comprehension):
            ctype = comp_types[i % len(comp_types)]
            fn = {"synthesis": self._gq_synthesis,
                  "aggregation": self._gq_aggregation,
                  "conditional": self._gq_conditional,
                  "ratio": self._gq_ratio,
                  "comparison": self._gq_comparison,
                  "multi_hop": self._gq_multi_hop,
                  "outlier": self._gq_outlier}[ctype]
            q = fn(world, rng, introduced)
            if q:
                q.purpose = "comprehension"
                questions.append(q)

        # Abstention
        for _ in range(n_abstention):
            q = self._gq_abstention(world, rng, introduced)
            if q:
                q.purpose = "abstention"
                questions.append(q)

        # Trick retrieval: looks like abstention, but GT is real
        for _ in range(n_trick):
            q = self._gq_trick_retrieval(world, rng, introduced)
            if q:
                name = q.required_entities[0]
                q.purpose = "trick_retrieval"
                questions.append(q)

        rng.shuffle(questions)
        return questions
