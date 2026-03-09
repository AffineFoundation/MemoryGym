"""Advanced question generation: relationships, entity detection, comprehension replacement.

Split from questions.py to keep files under 1000 lines.
Methods are mixed into WorldTemplate via AdvancedQuestionMixin.
"""

from __future__ import annotations

from random import Random
from typing import Any

from .types import GeneratedQA


class AdvancedQuestionMixin:
    """Mixin for relationship questions, entity detection, and comprehension replacement."""

    # ── Relationship questions ──

    def _gq_relationship_lookup(self, world, rng, available):
        """Ask who has a specific relationship with a given entity."""
        if not world.relationships:
            return None
        avail_names = {e.name for e in available}
        valid = [r for r in world.relationships
                 if r.source in avail_names and r.target in avail_names]
        if not valid:
            return None
        rel = rng.choice(valid)
        ew = self.entity_word
        rel_phrase = rel.relation.replace("_", " ")
        q = rng.choice([
            f"Name the {ew} that {rel.source} {rel_phrase}.",
            f"Which {ew} has a '{rel_phrase}' relationship with "
            f"{rel.source}?",
        ])
        return GeneratedQA(
            q, rel.target,
            "relationship_lookup",
            [rel.source, rel.target],
            purpose="comprehension",
            source_attr=rel.relation,
        )

    def _gq_relationship_hop(self, world, rng, available):
        """2-step: find related entity, then query its attribute."""
        if not world.relationships:
            return None
        avail_names = {e.name for e in available}
        valid = [r for r in world.relationships
                 if r.source in avail_names and r.target in avail_names]
        if not valid:
            return None

        rng.shuffle(valid)
        for rel in valid:
            target_entity = world.get_entity(rel.target)
            if not target_entity:
                continue
            numeric = [a for a in world.active_attrs
                       if isinstance(target_entity.get(a), (int, float))]
            if not numeric:
                continue
            attr = rng.choice(numeric)
            label = self.attr_label(attr)
            val = target_entity.get(attr)
            fmt_val = self._format_value(attr, val)
            rel_phrase = rel.relation.replace("_", " ")
            ew = self.entity_word
            q = rng.choice([
                f"{rel.source} {rel_phrase} another {ew}. "
                f"What is that {ew}'s {label}?",
                f"Look up the {ew} that {rel.source} {rel_phrase}. "
                f"Report its {label}.",
            ])
            return GeneratedQA(
                q, fmt_val,
                "relationship_hop",
                [rel.source, rel.target],
                purpose="comprehension",
                source_attr=attr,
            )
        return None

    def _gq_relationship_chain(self, world, rng, available):
        """2-hop path: A→B→C, ask about C's attribute."""
        if not world.relationships:
            return None
        avail_names = {e.name for e in available}
        adj: dict[str, list[tuple[str, str]]] = {}
        for r in world.relationships:
            if r.source in avail_names and r.target in avail_names:
                adj.setdefault(r.source, []).append((r.target, r.relation))

        chains = []
        for a, neighbors_a in adj.items():
            for b, r1 in neighbors_a:
                if b in adj:
                    for c, r2 in adj[b]:
                        if c != a:
                            chains.append((a, r1, b, r2, c))
        if not chains:
            return None

        a, r1, b, r2, c = rng.choice(chains)
        c_entity = world.get_entity(c)
        if not c_entity:
            return None
        numeric = [attr for attr in world.active_attrs
                   if isinstance(c_entity.get(attr), (int, float))]
        if not numeric:
            return None
        attr = rng.choice(numeric)
        label = self.attr_label(attr)
        val = c_entity.get(attr)
        fmt_val = self._format_value(attr, val)
        ew = self.entity_word
        r1_phrase = r1.replace("_", " ")
        r2_phrase = r2.replace("_", " ")
        q = rng.choice([
            f"{a} {r1_phrase} {b}. {b} {r2_phrase} another {ew}. "
            f"What is that {ew}'s {label}?",
            f"Follow the chain: {a} {r1_phrase} {b}, then {b} "
            f"{r2_phrase} a third {ew}. Report the third {ew}'s "
            f"{label}.",
        ])
        return GeneratedQA(
            q, fmt_val, "relationship_chain",
            [a, b, c], purpose="comprehension",
            source_attr=attr,
        )

    def _gq_relationship_count(self, world, rng, available):
        """Count outgoing relationships of a given type."""
        if not world.relationships:
            return None
        avail_names = {e.name for e in available}
        groups: dict[tuple[str, str], list[str]] = {}
        for r in world.relationships:
            if r.source in avail_names and r.target in avail_names:
                key = (r.source, r.relation)
                groups.setdefault(key, []).append(r.target)
        valid = [(k, v) for k, v in groups.items() if len(v) >= 2]
        if not valid:
            return None

        (source, relation), targets = rng.choice(valid)
        count = len(targets)
        rel_phrase = relation.replace("_", " ")
        ew = self.entity_word
        q = rng.choice([
            f"How many {ew}s does {source} {rel_phrase}?",
            f"Count the number of {ew}s that {source} {rel_phrase}.",
        ])
        return GeneratedQA(
            q, str(count), "relationship_count",
            [source] + targets, purpose="comprehension",
            source_attr=relation,
        )

    def _gq_relationship_filter(self, world, rng, available):
        """Among an entity's relationships, find the one with max/min attr."""
        if not world.relationships:
            return None
        avail_names = {e.name for e in available}
        groups: dict[tuple[str, str], list[str]] = {}
        for r in world.relationships:
            if r.source in avail_names and r.target in avail_names:
                key = (r.source, r.relation)
                groups.setdefault(key, []).append(r.target)
        valid = [(k, v) for k, v in groups.items() if len(v) >= 2]
        if not valid:
            return None

        (source, relation), targets = rng.choice(valid)
        attr = rng.choice(world.active_attrs)
        target_entities = [world.get_entity(t) for t in targets]
        target_entities = [e for e in target_entities
                          if e and isinstance(e.get(attr), (int, float))]
        if len(target_entities) < 2:
            return None

        use_max = rng.choice([True, False])
        if use_max:
            best = max(target_entities, key=lambda e: e.get(attr))
        else:
            best = min(target_entities, key=lambda e: e.get(attr))
        label = self.attr_label(attr)
        rel_phrase = relation.replace("_", " ")
        ew = self.entity_word
        extreme = "highest" if use_max else "lowest"
        q = rng.choice([
            f"Among all {ew}s that {source} {rel_phrase}, which has "
            f"the {extreme} {label}?",
            f"Of the {ew}s {source} {rel_phrase}, name the one with "
            f"the {extreme} {label}.",
        ])
        return GeneratedQA(
            q, best.name, "relationship_filter",
            [source] + [e.name for e in target_entities],
            purpose="comprehension",
            source_attr=attr,
        )

    # ── Counterfactual and multi-constraint questions ──

    def _gq_counterfactual(self, world, rng, corrections):
        """Ask what a value was BEFORE a correction happened.

        Requires the agent to remember pre-correction values alongside
        current values — tests memory maintenance depth beyond simple updates.
        """
        if not corrections:
            return None
        # Only numeric corrections have unambiguous old values
        numeric_corr = [c for c in corrections
                        if isinstance(c.old_val, (int, float))]
        if not numeric_corr:
            return None
        c = rng.choice(numeric_corr)
        label = self.attr_label(c.attr)
        fmt_old = self._format_value(c.attr, c.old_val)
        ew = self.entity_word
        q = rng.choice([
            f"Before the correction, what was {c.entity_name}'s {label}?",
            f"What was the original {label} for {c.entity_name}, "
            f"prior to the correction?",
            f"If the correction to {c.entity_name}'s {label} had not "
            f"happened, what would the value be?",
        ])
        return GeneratedQA(
            q, fmt_old, "counterfactual",
            [c.entity_name], purpose="comprehension",
            source_attr=c.attr,
        )

    def _gq_multi_constraint(self, world, rng, available):
        """Count entities satisfying 2-3 simultaneous constraints.

        Requires the agent to have stored multiple attributes per entity
        and perform combinatorial filtering — harder than single-attr queries.
        """
        if len(available) < 5:
            return None
        avail_names = {e.name for e in available}

        # Pick 2 numeric attributes for threshold constraints
        numeric_attrs = [a for a in world.active_attrs
                         if any(isinstance(e.get(a), (int, float))
                                for e in available)]
        if len(numeric_attrs) < 2:
            return None
        attrs = rng.sample(numeric_attrs, 2)

        # Pick an enum attribute for category constraint (if available)
        enum_attrs = [a for a in world.active_attrs
                      if any(isinstance(e.get(a), str) and e.get(a)
                             for e in available)
                      and a not in attrs]
        use_enum = bool(enum_attrs) and rng.random() < 0.5

        # Build constraints
        constraints = []
        labels = []
        for attr in attrs:
            vals = [e.get(attr) for e in available
                    if isinstance(e.get(attr), (int, float))]
            if not vals:
                return None
            # Pick a threshold that splits the population ~30-70%
            sorted_vals = sorted(vals)
            idx = len(sorted_vals) // 3
            use_gt = rng.choice([True, False])
            if use_gt:
                threshold = sorted_vals[idx]
                constraints.append((attr, ">", threshold))
                label = self.attr_label(attr)
                labels.append(f"{label} > {self._format_value(attr, threshold)}")
            else:
                threshold = sorted_vals[-(idx + 1)]
                constraints.append((attr, "<", threshold))
                label = self.attr_label(attr)
                labels.append(f"{label} < {self._format_value(attr, threshold)}")

        if use_enum:
            enum_attr = rng.choice(enum_attrs)
            enum_vals = [e.get(enum_attr) for e in available
                         if isinstance(e.get(enum_attr), str) and e.get(enum_attr)]
            if enum_vals:
                enum_val = rng.choice(enum_vals)
                constraints.append((enum_attr, "==", enum_val))
                labels.append(
                    f"{self.attr_label(enum_attr)} = \"{enum_val}\"")

        # Compute GT: count entities matching ALL constraints
        matching = []
        for e in available:
            if e.name not in avail_names:
                continue
            match = True
            for attr, op, threshold in constraints:
                val = e.get(attr)
                if val is None:
                    match = False
                    break
                if op == ">" and not (isinstance(val, (int, float)) and val > threshold):
                    match = False
                    break
                if op == "<" and not (isinstance(val, (int, float)) and val < threshold):
                    match = False
                    break
                if op == "==" and str(val) != str(threshold):
                    match = False
                    break
            if match:
                matching.append(e)

        count = len(matching)
        # Require checking at least 3 entities (prevents vacuous truth for guesser)
        req_entities = list({e.name for e in matching[:5]}
                           | {e.name for e in rng.sample(
                                  available, min(3, len(available)))})
        ew = self.entity_word
        ewp = self.entity_word_plural
        constraint_text = " AND ".join(labels)
        q = rng.choice([
            f"How many {ewp} satisfy: {constraint_text}?",
            f"Count the {ewp} where {constraint_text}.",
        ])
        return GeneratedQA(
            q, str(count), "multi_constraint",
            req_entities,
            purpose="comprehension",
            source_attr=constraints[0][0],
        )

    # ── Entity detection and comprehension replacement ──

    def _numeric_variants(self, attr: str, val: Any) -> list[str]:
        """Generate string variants of a value for fuzzy detection."""
        variants: list[str] = []
        variants.append(self._format_value(attr, val).lower().replace(",", ""))
        if isinstance(val, (int, float)):
            variants.append(str(val).lower())
            variants.append(str(int(round(val))))
            if isinstance(val, float):
                variants.append(f"{val:.1f}")
                variants.append(f"{val:.0f}")
        elif isinstance(val, str):
            variants.append(val.lower())
        elif isinstance(val, list):
            for v in val:
                if isinstance(v, (int, float)):
                    variants.append(str(v))
        return variants

    def detect_stored_entities(
        self, world, stored_contents: list[str],
    ) -> tuple[set[str], set[str]]:
        """Scan stored contents and detect which World entities were stored.

        Anti-hack: requires entity name AND at least one attribute value
        to appear in the SAME stored entry.
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

    def maybe_replace_comprehension(
        self, event: dict, world,
        stored_contents: list[str], rng_seed: int,
    ) -> dict:
        """Replace a comprehension question if required entities aren't stored."""
        comp = event.get("competency", "")
        if comp in ("retrieval", "update", "abstention", "delta"):
            return event

        required = set(event.get("required_entities", []))
        if not required:
            return event

        stored, _ = self.detect_stored_entities(world, stored_contents)
        if required <= stored:
            return event

        stored_pool = [e for e in world.entities if e.name in stored]
        if len(stored_pool) < 2:
            return event

        rng = Random(rng_seed)
        fn_map = {
            "synthesis": self._gq_synthesis,
            "aggregation": self._gq_aggregation,
            "cross_category": self._gq_cross_category,
            "conditional": self._gq_conditional,
            "ratio": self._gq_ratio,
            "comparison": self._gq_comparison,
            "multi_hop": self._gq_multi_hop,
            "outlier": self._gq_outlier,
            "temporal_trend": self._gq_temporal_trend,
            "temporal_extreme": self._gq_temporal_extreme,
            "text_match": self._gq_text_match,
            "enum_filter": self._gq_enum_filter,
            "multi_constraint": self._gq_multi_constraint,
            "relationship_lookup": self._gq_relationship_lookup,
            "relationship_hop": self._gq_relationship_hop,
            "relationship_chain": self._gq_relationship_chain,
            "relationship_count": self._gq_relationship_count,
            "relationship_filter": self._gq_relationship_filter,
        }

        # Try original comp type first, then others
        for attempt_comp in [comp] + [c for c in fn_map if c != comp]:
            fn = fn_map.get(attempt_comp)
            if not fn:
                continue
            q = fn(world, rng, stored_pool)
            if q:
                q.purpose = "comprehension"
                return {
                    "type": "question",
                    "question": q.question,
                    "answer": q.answer,
                    "competency": q.competency,
                    "purpose": q.purpose,
                    "required_entities": q.required_entities,
                    "source_attr": q.source_attr,
                }

        return event
