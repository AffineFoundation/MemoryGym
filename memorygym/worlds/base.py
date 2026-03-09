"""World template abstraction for MemoryGym.

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
from random import Random
from typing import Any

# Data classes live in types.py to avoid circular imports.
# Re-export for backward compatibility.
from .types import (  # noqa: F401
    AttrDef, Contradiction, Correction, EntitySpec, GeneratedQA,
    Relationship, SentenceTemplate, World,
)
from .questions import QuestionGeneratorMixin, _possessive  # noqa: F401
from .questions_advanced import AdvancedQuestionMixin


class WorldTemplate(AdvancedQuestionMixin, QuestionGeneratorMixin, ABC):
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

    def _relationship_types(self) -> list[tuple[str, str, bool]]:
        """Return (relation, description, symmetric) for this domain.

        Override in subclasses to enable relationship generation.
        Empty list = no relationships (backward compatible).
        """
        return []

    def generate_relationships(self, rng: Random,
                               world: World,
                               n_relations: int) -> list[Relationship]:
        """Generate relationships between entities.

        Default: uses _relationship_types() to create random pairings.
        Rules: no self-loops, no duplicates, symmetric stored once.
        """
        rel_types = self._relationship_types()
        if not rel_types:
            return []

        entities = world.entities
        if len(entities) < 2:
            return []

        relationships: list[Relationship] = []
        seen: set[tuple[str, str, str]] = set()

        for _ in range(n_relations * 3):  # oversample, deduplicate
            if len(relationships) >= n_relations:
                break
            rel_name, _, symmetric = rng.choice(rel_types)
            a, b = rng.sample(entities, 2)
            key = (a.name, rel_name, b.name)
            rev_key = (b.name, rel_name, a.name)
            if key in seen or (symmetric and rev_key in seen):
                continue
            seen.add(key)
            relationships.append(Relationship(a.name, rel_name, b.name))

        return relationships

    def render_relationship(self, rel: Relationship) -> str:
        """Render a relationship as a natural-language sentence.

        Override for domain-specific phrasing.
        """
        return (f"{rel.source} has a {rel.relation.replace('_', ' ')} "
                f"relationship with {rel.target}.")

    def _generate_attr_value(self, rng: Random, adef: AttrDef) -> Any:
        """Generate a random value for an attribute definition.

        Handles all dtypes: int, float, text, enum, list_float, date.
        Templates can override generate_entity() for custom logic,
        or call this helper for standard dtype handling.
        """
        if adef.dtype == "int":
            return rng.randint(int(adef.min_val), int(adef.max_val))
        elif adef.dtype == "float":
            return round(rng.uniform(adef.min_val, adef.max_val), 2)
        elif adef.dtype == "enum":
            if not adef.choices:
                raise ValueError(f"enum attr '{adef.name}' has no choices")
            return rng.choice(adef.choices)
        elif adef.dtype == "text":
            if not adef.text_pool:
                return f"Sample text for {adef.name}"
            n_sentences = rng.randint(2, min(5, len(adef.text_pool)))
            parts = rng.sample(adef.text_pool, n_sentences)
            return " ".join(parts)
        elif adef.dtype == "list_float":
            # Fork RNG so list_float pattern complexity doesn't shift
            # subsequent attribute generation.
            sub_seed = rng.randint(0, 2**31)
            return self._generate_list_float(adef, Random(sub_seed))
        elif adef.dtype == "date":
            year = rng.randint(int(adef.min_val), int(adef.max_val))
            month = rng.randint(1, 12)
            day = rng.randint(1, 28)  # safe for all months
            return f"{year:04d}-{month:02d}-{day:02d}"
        else:
            raise ValueError(f"Unknown dtype '{adef.dtype}' for '{adef.name}'")

    def _generate_list_float(self, adef: AttrDef, rng: Random) -> list[float]:
        """Generate a list_float value. Override for domain-specific patterns."""
        base = rng.uniform(adef.min_val, adef.max_val)
        values = []
        for _ in range(adef.list_len):
            change = rng.uniform(-0.2, 0.3) * base
            val = max(adef.min_val, min(adef.max_val, base + change))
            values.append(round(val, 2))
            base = val
        return values

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
            # Per-entity attribute heterogeneity: each entity gets a
            # random subset of global active attrs (5-8 out of 8-9).
            # This prevents models from learning "every entity has
            # exactly N attrs" and forces handling of incomplete data.
            if len(active) > 5:
                n_entity_attrs = rng.randint(
                    max(3, len(active) - 4),  # at least 3, or len-4
                    len(active),               # at most all
                )
                entity_attrs = rng.sample(active, n_entity_attrs)
            else:
                entity_attrs = active
            entities.append(
                self.generate_entity(rng, nm, cat, entity_attrs))

        # Apply eval_salt perturbation
        if eval_salt:
            self._apply_eval_salt(entities, selected, active, eval_salt)

        world = World(
            entities=entities, attr_defs=selected,
            active_attrs=active, categories=self.all_categories,
            seed=seed,
        )

        # Generate relationships if template supports them
        if self._relationship_types():
            rng_rel = Random(seed + 9191)
            n_rels = max(6, n_entities // 3)
            world.relationships = self.generate_relationships(
                rng_rel, world, n_rels)

        return world

    def _apply_eval_salt(self, entities: list[EntitySpec],
                         attr_defs: list[AttrDef],
                         active_attrs: list[str],
                         salt: int) -> None:
        """Perturb attribute values deterministically by salt.

        Handles all dtypes: numeric values are shifted by 5-15% of range,
        list_float elements are perturbed similarly, enum/text are rotated,
        and dates are shifted by random days.
        """
        salt_rng = Random(salt)
        for entity in entities:
            for adef in attr_defs:
                if adef.name not in active_attrs:
                    continue
                val = entity.get(adef.name)
                if val is None:
                    continue

                if adef.dtype in ("int", "float"):
                    # Perturb by 5-15% of the range
                    range_size = adef.max_val - adef.min_val
                    delta = salt_rng.uniform(0.05, 0.15) * range_size
                    direction = salt_rng.choice([-1, 1])
                    new_val = val + direction * delta
                    new_val = max(adef.min_val, min(adef.max_val, new_val))
                    if adef.dtype == "int":
                        new_val = int(round(new_val))
                        if new_val == val:
                            new_val = val + (1 if val < adef.max_val
                                             else -1)
                    else:
                        new_val = round(new_val, 2)
                    entity.attrs[adef.name] = new_val

                elif adef.dtype == "list_float":
                    if not isinstance(val, list):
                        continue
                    range_size = adef.max_val - adef.min_val
                    new_list = []
                    for v in val:
                        delta = salt_rng.uniform(0.05, 0.15) * range_size
                        direction = salt_rng.choice([-1, 1])
                        nv = v + direction * delta
                        nv = max(adef.min_val, min(adef.max_val, nv))
                        new_list.append(round(nv, 2))
                    entity.attrs[adef.name] = new_list

                elif adef.dtype == "enum":
                    if not adef.choices or len(adef.choices) < 2:
                        continue
                    # Rotate to a different choice
                    shift = salt_rng.randint(1, len(adef.choices) - 1)
                    idx = adef.choices.index(val) if val in adef.choices else 0
                    entity.attrs[adef.name] = adef.choices[
                        (idx + shift) % len(adef.choices)]

                elif adef.dtype == "text":
                    if not adef.text_pool or len(adef.text_pool) < 2:
                        continue
                    # Re-sample from pool with salt rng
                    n_parts = salt_rng.randint(
                        2, min(5, len(adef.text_pool)))
                    entity.attrs[adef.name] = " ".join(
                        salt_rng.sample(adef.text_pool, n_parts))

                elif adef.dtype == "date":
                    # Shift date by a random offset within valid range
                    # Parse YYYY-MM-DD, regenerate with salt rng
                    year = salt_rng.randint(
                        int(adef.min_val), int(adef.max_val))
                    month = salt_rng.randint(1, 12)
                    day = salt_rng.randint(1, 28)
                    entity.attrs[adef.name] = (
                        f"{year:04d}-{month:02d}-{day:02d}")

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
            if st.distractor in ("temporal", "comparative", "qualified"):
                if not isinstance(val, (int, float)):
                    sentences.append(
                        f"{self.attr_label(attr)}: {fmt_val}")
                    continue
                # Generate distractor that can be larger or smaller
                # (randomized direction prevents "always pick the bigger
                # number" attack).
                mult = rng.choice([
                    rng.uniform(0.5, 0.9),
                    rng.uniform(1.1, 1.5),
                ])
                other = val * mult
                other = (int(round(other)) if isinstance(val, int)
                         else round(other, 2))
                kwargs["distractor"] = self._format_value(attr, other)
                # For comparative templates, also set other_name/other_val
                kwargs["other_name"] = "a separate estimate"
                kwargs["other_val"] = self._format_value(attr, other)
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

    @staticmethod
    def _perturb_value(rng: Random, adef: AttrDef, old_val: Any) -> Any:
        """Generate a new value different from old_val for corrections."""
        if adef.dtype == "int":
            magnitude = max(1, int(abs(old_val) * rng.uniform(0.1, 0.5)))
            new_val = old_val + rng.choice([-1, 1]) * magnitude
            new_val = max(int(adef.min_val), min(int(adef.max_val), new_val))
            if new_val == old_val:
                new_val = old_val + (1 if old_val < adef.max_val else -1)
            return new_val
        elif adef.dtype == "float":
            delta = old_val * rng.uniform(0.1, 0.5) * rng.choice([-1, 1])
            new_val = round(old_val + delta, 2)
            new_val = max(adef.min_val, min(adef.max_val, new_val))
            if new_val == old_val:
                new_val = round(old_val + 0.1, 2)
            return new_val
        elif adef.dtype == "enum":
            others = [c for c in adef.choices if c != old_val]
            return rng.choice(others) if others else old_val
        elif adef.dtype == "date":
            # Shift date by 30-365 days
            from datetime import date as dt_date, timedelta
            d = dt_date.fromisoformat(old_val)
            shift = rng.randint(30, 365) * rng.choice([-1, 1])
            new_d = d + timedelta(days=shift)
            year_min = int(adef.min_val)
            year_max = int(adef.max_val)
            if new_d.year < year_min:
                new_d = new_d.replace(year=year_min)
            elif new_d.year > year_max:
                new_d = new_d.replace(year=year_max)
            return new_d.isoformat()
        elif adef.dtype == "list_float":
            # Modify the last element
            new_val = list(old_val)
            if new_val:
                idx = len(new_val) - 1
                delta = new_val[idx] * rng.uniform(0.1, 0.5)
                new_val[idx] = round(
                    new_val[idx] + delta * rng.choice([-1, 1]), 2)
                new_val[idx] = max(adef.min_val, min(adef.max_val,
                                                     new_val[idx]))
            return new_val
        elif adef.dtype == "text":
            # Append a correction phrase
            return old_val + " [Updated]"
        else:
            return old_val

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
            # Only correct numeric/enum attrs (text/list/date are
            # too complex for simple correction notices)
            viable = [a for a in world.active_attrs
                      if entity.get(a) is not None]
            correctable = []
            for a in viable:
                ad = next((d for d in world.attr_defs if d.name == a), None)
                if ad and ad.dtype in ("int", "float", "enum"):
                    correctable.append(a)
            if not correctable:
                correctable = viable  # fallback
            attr = rng.choice(correctable)
            old_val = entity.get(attr)
            adef = next(a for a in world.attr_defs if a.name == attr)

            new_val = self._perturb_value(rng, adef, old_val)

            notice = self.render_correction(entity, attr, old_val, new_val)
            entity.attrs[attr] = new_val  # MUTATE world state
            corrections.append(Correction(
                entity_name=entity.name, attr=attr,
                old_val=old_val, new_val=new_val, notice=notice,
            ))

        return corrections

    def generate_contradictions(
        self, world: World, rng: Random, n: int,
        exclude_entities: set[str] | None = None,
    ) -> list[Contradiction]:
        """Generate implicit contradictions and update World state.

        Like corrections, but rendered as normal documents (no CORRECTION
        label). The agent must detect that the same entity appears again
        with a different value and update its memory.

        Mutates entity attributes to new values. After this call,
        world.entities hold the UPDATED values (new GT).

        Args:
            exclude_entities: entity names already used by corrections
                (avoid contradicting the same entity that was corrected).
        """
        exclude = exclude_entities or set()
        contradictions: list[Contradiction] = []
        candidates = [e for e in world.entities
                      if e.name not in exclude
                      and sum(1 for a in world.active_attrs
                              if e.get(a) is not None) >= 2]
        if not candidates:
            return contradictions
        targets = rng.sample(candidates, min(n, len(candidates)))

        for entity in targets:
            viable = [a for a in world.active_attrs
                      if entity.get(a) is not None]
            # Prefer numeric/enum for contradictions
            correctable = []
            for a in viable:
                ad = next((d for d in world.attr_defs if d.name == a), None)
                if ad and ad.dtype in ("int", "float", "enum"):
                    correctable.append(a)
            if not correctable:
                correctable = viable
            attr = rng.choice(correctable)
            old_val = entity.get(attr)
            adef = next(a for a in world.attr_defs if a.name == attr)

            new_val = self._perturb_value(rng, adef, old_val)
            entity.attrs[attr] = new_val  # MUTATE world state
            # Render as a normal document (the entity with updated attrs)
            doc = self.render_document(entity, world.active_attrs, rng)
            contradictions.append(Contradiction(
                entity_name=entity.name, attr=attr,
                old_val=old_val, new_val=new_val, document=doc,
            ))

        return contradictions

    def generate_stream(
        self, world: World, rng: Random,
        corrections: list[Correction],
        stored_names: set[str],
        n_questions: int,
        entities_per_batch: int = 10,
        contradictions: list[Contradiction] | None = None,
    ) -> list[dict]:
        """Generate an interleaved evaluation stream.

        Returns a list of events, each a dict with:
          type: "ingest" | "correction" | "question"
          + type-specific fields

        Stream structure:
          - Entities arrive in batches of entities_per_batch
          - After batch 2+, questions may appear (30% per batch)
          - Corrections arrive at ~60% through entity batches
          - Contradictions arrive at ~80% as normal ingest docs
          - Remaining questions come after all entities are ingested
          - Agent never knows what event comes next

        This adds uncertainty pressure: the agent can't adopt
        "store everything first, answer later" because questions
        arrive during ingest.
        """
        events: list[dict] = []
        entities = list(world.entities)
        n_batches = max(1, len(entities) // entities_per_batch)
        # Randomize correction timing to prevent position-based gaming
        corr_frac = rng.uniform(0.4, 0.7)
        correction_batch = max(1, int(n_batches * corr_frac))
        contra_frac = rng.uniform(0.7, 0.9)
        contradiction_batch = max(correction_batch + 1,
                                  int(n_batches * contra_frac))

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
            docs = []
            for e in batch_entities:
                doc = self.render_document(e, world.active_attrs, rng,
                                          other_entities=batch_entities)
                # Append relationship sentences if any
                if world.relationships:
                    rels = world.get_outgoing(e.name)
                    if rels:
                        rel_lines = [self.render_relationship(r) for r in rels]
                        doc += "\n" + " ".join(rel_lines)
                docs.append(doc)
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
                        "old_val": c.old_val,
                        "new_val": c.new_val,
                    })

            # Emit contradictions at contradiction_batch as normal ingest
            if batch_idx == contradiction_batch and contradictions:
                contra_docs = [ct.document for ct in contradictions]
                contra_names = [ct.entity_name for ct in contradictions]
                events.append({
                    "type": "ingest",
                    "batch": batch_idx + 1,
                    "total_batches": n_batches,
                    "documents": contra_docs,
                    "entity_names": contra_names,
                    "is_contradiction": True,  # internal flag, not shown to agent
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
                        "source_attr": q.source_attr,
                    })
                    questions_emitted += 1

        # Emit remaining questions after all ingest
        remaining = n_questions - questions_emitted
        remaining_qs = self.gen_adaptive_questions(
            world, rng, introduced, stored_names, remaining, corrections,
            contradictions,
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
                "source_attr": q.source_attr,
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
            comp_pool = ([e for e in introduced if e.name in stored_names]
                         if stored_names else introduced)
            q = self._gq_synthesis(world, rng, comp_pool)
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
        contradictions: list[Contradiction] | None = None,
    ) -> list[GeneratedQA]:
        """Generate post-storage adaptive questions.

        Budget allocation (with corrections):
          retrieval 40% | comprehension 25% | update 20% | abstention 15%
        Budget allocation (without corrections):
          retrieval 50% | comprehension 40% | abstention 10%

        Update questions use the same _q_text as retrieval → agent cannot
        distinguish them by wording. The GT is the CORRECTED value.

        Contradiction questions also use identical wording — the GT is
        the contradicted (latest) value. Scored on maintenance axis.
        """
        has_corrections = bool(corrections)
        has_contradictions = bool(contradictions)

        # Trick retrieval: ~2 per evaluation — phrased like abstention
        # but with real GT. Defeats always-abstain strategy.
        n_trick = min(2, max(1, n_questions // 10))

        # Contradiction questions come from the update budget
        n_contradiction = 0
        if has_contradictions:
            n_contradiction = min(len(contradictions),
                                  max(1, n_questions // 10))

        if has_corrections:
            n_update = max(1, round(n_questions * 0.2)) - n_contradiction
            n_update = max(0, min(n_update, len(corrections)))
            n_delta = max(1, n_update // 3) if n_update > 0 else 0
            n_retrieval = round(n_questions * 0.4) - n_trick
            n_abstention = max(1, round(n_questions * 0.15))
            n_comprehension = (n_questions - n_retrieval - n_update
                               - n_abstention - n_trick - n_delta
                               - n_contradiction)
        else:
            n_update = 0
            n_delta = 0
            n_retrieval = round(n_questions * 0.5) - n_trick
            n_abstention = max(1, round(n_questions * 0.1))
            n_comprehension = (n_questions - n_retrieval - n_abstention
                               - n_trick - n_contradiction)

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

        # Contradiction: ask about implicitly-contradicted values.
        # Same wording as retrieval — GT is the latest (contradicted) value.
        # Scored on maintenance axis (tests memory update without explicit notice).
        if has_contradictions:
            used_contra: set[str] = set()
            for _ in range(n_contradiction):
                remaining_ct = [ct for ct in (contradictions or [])
                                if ct.entity_name not in used_contra]
                if not remaining_ct:
                    break
                ct = rng.choice(remaining_ct)
                entity = world.get_entity(ct.entity_name)
                if not entity:
                    continue
                current_val = entity.get(ct.attr)
                if current_val is None:
                    continue
                q = GeneratedQA(
                    self._q_text(ct.attr, ct.entity_name, rng),
                    str(current_val), "update", [ct.entity_name],
                    source_attr=ct.attr,
                )
                q.purpose = "contradiction"
                used_contra.add(ct.entity_name)
                questions.append(q)

        # Comprehension: multi-step reasoning + basic computation.
        # Use stored entities as the candidate pool when available.
        # This ensures comprehension questions test reasoning ability,
        # not whether the agent happened to store the right entities.
        # When stored_names is empty (pre-generation), falls back to
        # introduced (all entities seen so far).
        if stored_names:
            comp_pool = [e for e in introduced if e.name in stored_names]
        else:
            comp_pool = introduced
        comp_types = ["synthesis", "aggregation", "cross_category",
                      "conditional", "ratio", "comparison",
                      "multi_hop", "outlier",
                      "temporal_trend", "temporal_extreme",
                      "text_match", "enum_filter",
                      "multi_constraint"]
        # Add correction-dependent types only if corrections exist
        if has_corrections:
            comp_types.append("counterfactual")
        # Add relationship types only if world has relationships
        if world.relationships:
            comp_types.extend([
                "relationship_lookup", "relationship_hop",
                "relationship_chain", "relationship_count",
                "relationship_filter",
            ])
        rng.shuffle(comp_types)

        # Counterfactual needs corrections, not available — wrap it
        def _counterfactual_wrapper(world, rng, available):
            return self._gq_counterfactual(world, rng, corrections)

        comp_fn_map = {
            "synthesis": self._gq_synthesis,
            "aggregation": self._gq_aggregation,
            "cross_category": self._gq_cross_category,
            "conditional": self._gq_conditional,
            "ratio": self._gq_ratio,
            "comparison": self._gq_comparison,
            "multi_hop": self._gq_multi_hop,
            "outlier": self._gq_outlier,
            "counterfactual": _counterfactual_wrapper,
            "relationship_lookup": self._gq_relationship_lookup,
            "relationship_hop": self._gq_relationship_hop,
            "relationship_chain": self._gq_relationship_chain,
            "relationship_count": self._gq_relationship_count,
            "relationship_filter": self._gq_relationship_filter,
            "temporal_trend": self._gq_temporal_trend,
            "temporal_extreme": self._gq_temporal_extreme,
            "text_match": self._gq_text_match,
            "enum_filter": self._gq_enum_filter,
            "multi_constraint": self._gq_multi_constraint,
        }
        for i in range(n_comprehension):
            q = None
            # Try the assigned type first, then fall back to others
            primary = comp_types[i % len(comp_types)]
            candidates = [primary] + [t for t in comp_types if t != primary]
            for ctype in candidates:
                fn = comp_fn_map[ctype]
                q = fn(world, rng, comp_pool)
                if q:
                    q.purpose = "comprehension"
                    questions.append(q)
                    break

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
