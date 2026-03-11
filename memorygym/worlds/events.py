"""Event generation mixin for WorldTemplate.

Extracted from base.py to keep file sizes under 1000 lines.
Contains: corrections, contradictions, noise, stream generation.
"""

from __future__ import annotations

from random import Random
from typing import Any

from .types import (
    AttrDef, Contradiction, Correction, EntitySpec, GeneratedQA, World,
)


class EventGeneratorMixin:
    """Mixin providing event generation methods for WorldTemplate."""

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

    def _generate_noise_doc(self, rng: Random,
                            known_entities: list[EntitySpec],
                            active_attrs: list[str]) -> str:
        """Generate a noise document that mentions entity names but has
        no complete attribute data. Tests agent's ability to filter noise.
        """
        # Pick 1-3 entity names to mention
        n_mention = min(rng.randint(1, 3), len(known_entities))
        mentioned = rng.sample(known_entities, n_mention)
        names = [e.name for e in mentioned]

        templates = [
            "Internal memo: {names} were discussed in the quarterly review. "
            "No action items were finalized. Follow-up scheduled for next week.",
            "Meeting notes — Participants mentioned {names} in passing "
            "during the strategy session. Details to be confirmed.",
            "News brief: Sources report activity involving {names}. "
            "Exact figures are not yet available pending verification.",
            "Email thread RE: {names} — Please review the attached "
            "documents before the next planning meeting.",
            "Preliminary report draft mentions {names} among others. "
            "Data collection is still in progress.",
        ]
        template = rng.choice(templates)
        name_str = (", ".join(names[:-1]) + " and " + names[-1]
                    if len(names) > 1 else names[0])
        return template.format(names=name_str)

    def generate_stream(
        self, world: World, rng: Random,
        corrections: list[Correction],
        stored_names: set[str],
        n_questions: int,
        entities_per_batch: int | None = None,
        contradictions: list[Contradiction] | None = None,
        n_sessions: int = 1,
    ) -> list[dict]:
        """Generate an interleaved evaluation stream.

        Returns a list of events, each a dict with:
          type: "ingest" | "correction" | "question"
          + type-specific fields

        Stream structure:
          - Entities arrive in batches of entities_per_batch
          - After batch 2+, questions may appear (30% per batch)
          - Corrections arrive based on template's correction_timing
          - Contradictions arrive after corrections
          - Remaining questions come after all entities are ingested
          - Agent never knows what event comes next

        This adds uncertainty pressure: the agent can't adopt
        "store everything first, answer later" because questions
        arrive during ingest.
        """
        if entities_per_batch is None:
            entities_per_batch = self.entities_per_batch
        events: list[dict] = []

        # Build map of original attr values for corrected/contradicted entities
        # so ingest documents render pre-correction values
        _original_attrs: dict[str, dict[str, Any]] = {}
        if corrections:
            for c in corrections:
                _original_attrs.setdefault(c.entity_name, {})[c.attr] = c.old_val
        if contradictions:
            for ct in contradictions:
                _original_attrs.setdefault(ct.entity_name, {})[ct.attr] = ct.old_val

        entities = list(world.entities)
        n_batches = max(1, len(entities) // entities_per_batch)
        # Use template-specific correction timing
        ct_min, ct_max = self.correction_timing
        corr_frac = rng.uniform(ct_min, ct_max)
        correction_batch = max(1, int(n_batches * corr_frac))
        contra_frac = rng.uniform(0.7, 0.9)
        contradiction_batch = min(
            n_batches - 1,
            max(correction_batch + 1, int(n_batches * contra_frac)),
        )

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

        # Schedule noise events (~30% of batches, after batch 1)
        noise_schedule: set[int] = set()
        if n_batches > 2:
            noise_candidates = list(range(1, n_batches))
            rng_noise = Random(rng.randint(0, 2**31))
            rng_noise.shuffle(noise_candidates)
            n_noise = max(1, n_batches // 3)
            noise_schedule = set(noise_candidates[:n_noise])

        for batch_idx in range(n_batches):
            start = batch_idx * entities_per_batch
            end = min(start + entities_per_batch, len(entities))
            batch_entities = entities[start:end]

            # Inject noise before entity batch (tests filtering ability)
            if batch_idx in noise_schedule and introduced:
                noise_doc = self._generate_noise_doc(
                    rng, introduced, world.active_attrs)
                events.append({
                    "type": "noise",
                    "document": noise_doc,
                })

            # Render and emit ingest event (narrative mode)
            docs = []
            for e in batch_entities:
                # Temporarily restore original attrs for rendering
                saved: dict[str, Any] = {}
                if e.name in _original_attrs:
                    for attr, old_val in _original_attrs[e.name].items():
                        if attr in e.attrs:
                            saved[attr] = e.attrs[attr]
                            e.attrs[attr] = old_val

                doc = self.render_document(e, world.active_attrs, rng,
                                          other_entities=batch_entities)
                # Append relationship sentences if any
                if world.relationships:
                    rels = world.get_outgoing(e.name)
                    if rels:
                        rel_lines = [self.render_relationship(r) for r in rels]
                        doc += "\n" + " ".join(rel_lines)
                docs.append(doc)

                # Restore corrected attrs
                for attr, val in saved.items():
                    e.attrs[attr] = val
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
                    "is_contradiction": True,
                })

            # Emit a question if scheduled
            if batch_idx in mid_q_schedule and len(introduced) >= 5:
                q = self._generate_one_question(
                    world, rng, introduced, stored_names,
                    corrections if batch_idx > correction_batch else None,
                )
                if q:
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
            events.append({
                "type": "question",
                "question": q.question,
                "answer": q.answer,
                "competency": q.competency,
                "purpose": q.purpose,
                "required_entities": q.required_entities,
                "source_attr": q.source_attr,
            })

        if n_sessions > 1:
            events = self._insert_session_breaks(
                events, n_sessions, rng, corrections)

        return events

    @staticmethod
    def _insert_session_breaks(
        events: list[dict],
        n_sessions: int,
        rng: Random,
        corrections: list[Correction],
    ) -> list[dict]:
        """Insert session_break events to split the stream into sessions.

        Constraints:
        - Exactly n_sessions-1 breaks are inserted.
        - Breaks are placed between events (never inside a batch).
        - At least 1 correction target must be introduced in a different
          session than its correction event (guarantees cross-session update).
        - Breaks are placed at roughly even intervals (~1/n_sessions).
        """
        if n_sessions <= 1 or not events:
            return events

        n_breaks = n_sessions - 1

        # Find valid break positions: between events, after at least 1 ingest
        # and before the last event.
        # Prefer positions after ingest events for clean session boundaries.
        valid_positions: list[int] = []
        for i in range(1, len(events)):
            valid_positions.append(i)

        if len(valid_positions) < n_breaks:
            return events  # too few events to split

        # Target roughly even splits
        chunk = len(events) / n_sessions
        target_positions: list[int] = []
        for b in range(1, n_sessions):
            target = int(b * chunk)
            # Find nearest valid position
            best = min(valid_positions,
                       key=lambda p: abs(p - target))
            if best not in target_positions:
                target_positions.append(best)

        # Ensure cross-session correction: if all corrections are in the
        # same session as their entity ingest, try to move a break.
        if corrections:
            # Find where correction events are and where their target
            # entities were introduced (ingest events).
            correction_indices: list[int] = []
            entity_ingest_idx: dict[str, int] = {}
            for i, ev in enumerate(events):
                if ev["type"] == "correction":
                    correction_indices.append(i)
                elif ev["type"] == "ingest":
                    for name in ev.get("entity_names", []):
                        if name not in entity_ingest_idx:
                            entity_ingest_idx[name] = i

            # Check if any break separates a correction from its entity
            def has_cross_session_update(breaks: list[int]) -> bool:
                for ci in correction_indices:
                    ename = events[ci].get("entity_name", "")
                    ei = entity_ingest_idx.get(ename)
                    if ei is None:
                        continue
                    for bp in breaks:
                        if ei < bp <= ci or ci < bp <= ei:
                            return True
                return False

            if not has_cross_session_update(target_positions):
                # Try to place a break between entity ingest and correction
                for ci in correction_indices:
                    ename = events[ci].get("entity_name", "")
                    ei = entity_ingest_idx.get(ename)
                    if ei is not None and ei < ci:
                        mid = (ei + ci) // 2 + 1
                        mid = max(1, min(mid, len(events) - 1))
                        if mid not in target_positions:
                            target_positions[0] = mid
                            break

        target_positions.sort()
        # Deduplicate and limit to n_breaks
        seen: set[int] = set()
        unique: list[int] = []
        for p in target_positions:
            if p not in seen:
                seen.add(p)
                unique.append(p)
        target_positions = unique[:n_breaks]

        # Insert session breaks (from end to preserve indices)
        result = list(events)
        for session_num, pos in enumerate(reversed(target_positions), 1):
            actual_session = n_sessions - session_num + 1
            result.insert(pos, {
                "type": "session_break",
                "session_id": actual_session,
                "total_sessions": n_sessions,
            })

        return result

    def _generate_one_question(
        self, world: World, rng: Random,
        introduced: list[EntitySpec],
        stored_names: set[str],
        corrections: list[Correction] | None,
    ) -> GeneratedQA | None:
        """Generate a single random question for mid-stream emission."""
        w = self.question_weights
        t_ret = w.get("retrieval", 0.40)
        t_upd = t_ret + w.get("update", 0.20)
        t_comp = t_upd + w.get("comprehension", 0.25)
        # remainder → abstention

        roll = rng.random()
        if roll < t_ret:
            q = self._gq_retrieval(world, rng, introduced)
            if q:
                name = q.required_entities[0]
                q.purpose = "recall" if name in stored_names else "coverage"
                return q
        elif roll < t_upd and corrections:
            q = self._gq_update(world, rng, corrections)
            if q:
                q.purpose = "update"
                return q
        elif roll < t_comp and len(introduced) >= 5:
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
