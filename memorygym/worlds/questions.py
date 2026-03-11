"""Question generation mixin for WorldTemplate.

Extracted from base.py to keep files under 1000 lines.
All methods are designed to be mixed into WorldTemplate via inheritance.
They rely on self._q_text(), self._format_value(), self.attr_label(),
self.entity_word, self.entity_word_plural, self._ratio_pairs(),
self._generate_names(), self.render_document() — all defined on WorldTemplate.
"""

from __future__ import annotations

from random import Random
from typing import Any

from .types import GeneratedQA


def _possessive(name: str) -> str:
    """English possessive form: 'Ravens' → 'Ravens'', 'Chen' → 'Chen's'."""
    return f"{name}'" if name.endswith("s") else f"{name}'s"


class QuestionGeneratorMixin:
    """Mixin providing core question generation methods.

    Advanced methods (relationships, entity detection, comprehension replacement)
    are in questions_advanced.py (AdvancedQuestionMixin).
    """

    def gen_question(self, world: World, rng: Random,
                     competency: str,
                     available: list[EntitySpec],
                     corrections: list | None = None,
                     ) -> GeneratedQA | None:
        """Generate a question of the given competency type."""
        fn = {
            "retrieval": self._gq_retrieval,
            "synthesis": self._gq_synthesis,
            "aggregation": self._gq_aggregation,
            "cross_category": self._gq_cross_category,
            "conditional": self._gq_conditional,
            "abstention": self._gq_abstention,
            "ratio": self._gq_ratio,
            "comparison": self._gq_comparison,
            "multi_hop": self._gq_multi_hop,
            "outlier": self._gq_outlier,
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
        }.get(competency)
        if fn:
            return fn(world, rng, available)
        # Correction-dependent types
        if competency == "delta" and corrections:
            return self._gq_delta(world, rng, corrections)
        if competency == "counterfactual" and corrections:
            return self._gq_counterfactual(world, rng, corrections)
        return None

    def _gq_retrieval(self, world, rng, available):
        attr = rng.choice(world.active_attrs)
        cands = [e for e in available if e.get(attr) is not None]
        if not cands:
            return None
        e = rng.choice(cands)
        return GeneratedQA(
            self._q_text(attr, e.name, rng),
            self._format_value(attr, e.get(attr)), "retrieval", [e.name],
            source_attr=attr,
        )

    def _gq_retrieval_diverse(self, world, rng, available,
                              used_entities: set[str],
                              used_attrs: set[str]):
        """Retrieval with entity/attribute dedup and importance weighting."""
        unused_attrs = [a for a in world.active_attrs if a not in used_attrs]
        attr_pool = unused_attrs if unused_attrs else list(world.active_attrs)
        rng.shuffle(attr_pool)

        for attr in attr_pool:
            cands = [e for e in available if e.get(attr) is not None]
            if not cands:
                continue
            fresh = [e for e in cands if e.name not in used_entities]
            pool = fresh if fresh else cands
            e = self._weighted_choice(pool, world, rng)
            used_attrs.add(attr)
            return GeneratedQA(
                self._q_text(attr, e.name, rng),
                self._format_value(attr, e.get(attr)), "retrieval", [e.name],
                source_attr=attr,
            )
        return None

    def _weighted_choice(self, pool, world, rng):
        """Select entity from pool weighted by importance."""
        if len(pool) <= 1:
            return pool[0] if pool else None
        weights = [self.entity_importance(e, world) for e in pool]
        total = sum(weights)
        if total <= 0:
            return rng.choice(pool)
        r = rng.uniform(0, total)
        cumulative = 0.0
        for e, w in zip(pool, weights):
            cumulative += w
            if r <= cumulative:
                return e
        return pool[-1]

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
            source_attr=attr,
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
        return GeneratedQA(q, str(result), "aggregation", names,
                           source_attr=attr)

    def _gq_cross_category(self, world, rng, available):
        """Cross-category aggregation: top-K entities by one attr, aggregate another.

        Example: "What is the average employee count of the 3 companies
        with the highest revenue?"
        Requires storing entities from multiple categories and cross-referencing.
        """
        numeric = [a for a in world.active_attrs
                   if sum(1 for e in available
                          if isinstance(e.get(a), (int, float))) >= 5]
        if len(numeric) < 2:
            return None
        a_rank, a_agg = rng.sample(numeric, 2)
        l_rank = self.attr_label(a_rank)
        l_agg = self.attr_label(a_agg)
        cands = [e for e in available
                 if isinstance(e.get(a_rank), (int, float))
                 and isinstance(e.get(a_agg), (int, float))]
        if len(cands) < 5:
            return None
        k = rng.choice([3, 4, 5])
        use_top = rng.choice([True, False])
        sorted_cands = sorted(cands, key=lambda e: e.get(a_rank),
                              reverse=use_top)
        top_k = sorted_cands[:k]
        # Ensure they span >1 category (cross-category)
        cats = {e.category for e in top_k}
        if len(cats) < 2:
            return None
        adef = next((a for a in world.attr_defs if a.name == a_agg), None)
        ops = list(adef.agg_ops) if adef and adef.agg_ops else ["total", "average"]
        op = rng.choice(ops)
        values = [e.get(a_agg) for e in top_k]
        if op == "total":
            result = sum(values)
            if isinstance(result, float):
                result = round(result, 2)
        else:
            result = round(sum(values) / len(values), 2)
        names = [e.name for e in top_k]
        direction = "highest" if use_top else "lowest"
        ewp = self.entity_word_plural
        q = rng.choice([
            f"What is the {op} {l_agg} of the {k} {ewp} with the "
            f"{direction} {l_rank}?",
            f"Consider the top {k} {ewp} ranked by {direction} {l_rank}. "
            f"Calculate their {op} {l_agg}.",
        ])
        return GeneratedQA(q, str(result), "cross_category",
                           names, source_attr=a_agg)

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
            source_attr=a2,
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
            self._format_value(c.attr, current_val), "update",
            [c.entity_name], source_attr=c.attr,
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
                    source_attr="",
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
            self._format_value(attr, e.get(attr)), "retrieval", [e.name],
            source_attr=attr,
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
            return GeneratedQA(q, str(result), "ratio", [e.name],
                               source_attr="")
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
        q = (f"Compare {_possessive(e_a.name)} and {_possessive(e_b.name)} "
             f"{label}. Which is higher and what is the difference?")
        return GeneratedQA(
            q, f"{winner} ({diff})", "comparison",
            [e_a.name, e_b.name],
            source_attr=attr,
        )

    def _gq_delta(self, world, rng, corrections):
        """Change amount from a correction."""
        if not corrections:
            return None
        # Only numeric corrections support delta computation
        numeric_corr = [c for c in corrections
                        if isinstance(c.old_val, (int, float))
                        and isinstance(c.new_val, (int, float))]
        if not numeric_corr:
            return None
        c = rng.choice(numeric_corr)
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
            source_attr=c.attr,
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
            source_attr=a2,
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
            source_attr=attr,
        )

    # ── New dtype question types (Phase 16) ──

    def _gq_temporal_trend(self, world, rng, available):
        """Trend direction from list_float: 5-level classification.

        Answers: strongly rising, slightly rising, flat,
        slightly falling, strongly falling.
        Random baseline: 20% (vs 50% for the old binary version).
        """
        list_attrs = [a for a in world.active_attrs
                      if any(isinstance(e.get(a), list) for e in available)]
        if not list_attrs:
            return None
        attr = rng.choice(list_attrs)
        cands = [e for e in available
                 if isinstance(e.get(attr), list) and len(e.get(attr)) >= 3]
        if not cands:
            return None
        e = rng.choice(cands)
        vals = e.get(attr)
        # Normalized slope: slope / mean gives scale-independent rate
        n = len(vals)
        x_mean = (n - 1) / 2
        y_mean = sum(vals) / n
        num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(vals))
        denom = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / denom if denom else 0
        norm_slope = slope / abs(y_mean) if y_mean else 0
        # Classify into 5 levels
        if norm_slope > 0.15:
            answer = "strongly rising"
        elif norm_slope > 0.03:
            answer = "slightly rising"
        elif norm_slope < -0.15:
            answer = "strongly falling"
        elif norm_slope < -0.03:
            answer = "slightly falling"
        else:
            answer = "flat"
        label = self.attr_label(attr)
        q = rng.choice([
            f"Describe the overall trend of {_possessive(e.name)} "
            f"{label} over time.",
            f"How has {_possessive(e.name)} {label} changed across "
            f"the recorded periods?",
            f"What is the direction of {_possessive(e.name)} {label} "
            f"trend?",
        ])
        return GeneratedQA(
            q, answer, "temporal_trend", [e.name],
            purpose="comprehension", source_attr=attr,
        )

    def _gq_temporal_extreme(self, world, rng, available):
        """Which period has the max/min value in a list_float series?"""
        list_attrs = [a for a in world.active_attrs
                      if any(isinstance(e.get(a), list) for e in available)]
        if not list_attrs:
            return None
        attr = rng.choice(list_attrs)
        cands = [e for e in available
                 if isinstance(e.get(attr), list) and len(e.get(attr)) >= 3]
        if not cands:
            return None
        e = rng.choice(cands)
        vals = e.get(attr)
        use_max = rng.choice([True, False])
        if use_max:
            idx = max(range(len(vals)), key=lambda i: vals[i])
        else:
            idx = min(range(len(vals)), key=lambda i: vals[i])
        # Period is 1-indexed
        period = idx + 1
        answer = str(period)
        label = self.attr_label(attr)
        direction = "highest" if use_max else "lowest"
        q = rng.choice([
            f"In which period (1-{len(vals)}) is {_possessive(e.name)} "
            f"{label} the {direction}?",
            f"Looking at {_possessive(e.name)} {label} series, "
            f"which period has the {direction} value?",
        ])
        return GeneratedQA(
            q, answer, "temporal_extreme", [e.name],
            purpose="comprehension", source_attr=attr,
        )

    def _gq_text_match(self, world, rng, available):
        """Which entity's text attribute contains a specific phrase?"""
        text_attrs = [a for a in world.active_attrs
                      if any(isinstance(e.get(a), str) and len(e.get(a)) > 20
                             for e in available)]
        if not text_attrs:
            return None
        attr = rng.choice(text_attrs)
        cands = [e for e in available
                 if isinstance(e.get(attr), str) and len(e.get(attr)) > 20]
        if not cands:
            return None

        def _extract_phrases(text):
            """Extract single words and bigrams as candidate phrases."""
            clean = [w.strip(".,;:!?()\"'") for w in text.split()]
            singles = [w for w in clean if len(w) > 4]
            bigrams = [f"{clean[i]} {clean[i+1]}" for i in range(len(clean) - 1)
                       if len(clean[i]) > 2 and len(clean[i+1]) > 2]
            return bigrams + singles  # prefer bigrams (more unique)

        # Try multiple entities to find a unique phrase
        attempts = rng.sample(cands, min(8, len(cands)))
        for candidate in attempts:
            cand_text = candidate.get(attr)
            phrases = _extract_phrases(cand_text)
            if not phrases:
                continue
            for phrase in rng.sample(phrases, min(10, len(phrases))):
                hits = [c for c in cands
                        if phrase.lower() in c.get(attr).lower()]
                if len(hits) == 1:
                    label = self.attr_label(attr)
                    ewp = self.entity_word_plural
                    q = rng.choice([
                        f"Which {self.entity_word}'s {label} mentions "
                        f"\"{phrase}\"?",
                        f"Among all {ewp}, whose {label} contains "
                        f"\"{phrase}\"?",
                    ])
                    return GeneratedQA(
                        q, candidate.name, "text_match", [candidate.name],
                        purpose="comprehension", source_attr=attr,
                    )
        return None

    def _gq_enum_filter(self, world, rng, available):
        """Filter by enum attribute, then find extreme of a numeric attr."""
        enum_attrs = [a for a in world.active_attrs
                      if any(isinstance(e.get(a), str)
                             and len(e.get(a)) <= 20
                             for e in available)]
        if not enum_attrs:
            return None
        numeric = [a for a in world.active_attrs
                   if any(isinstance(e.get(a), (int, float))
                          for e in available)]
        if not numeric:
            return None
        enum_attr = rng.choice(enum_attrs)
        num_attr = rng.choice(numeric)
        if enum_attr == num_attr:
            return None
        # Group by enum value
        groups: dict[str, list] = {}
        for e in available:
            ev = e.get(enum_attr)
            nv = e.get(num_attr)
            if isinstance(ev, str) and isinstance(nv, (int, float)):
                groups.setdefault(ev, []).append(e)
        eligible = {v: es for v, es in groups.items() if len(es) >= 2}
        if not eligible:
            return None
        enum_val = rng.choice(list(eligible.keys()))
        members = eligible[enum_val]
        use_max = rng.choice([True, False])
        best = (max if use_max else min)(
            members, key=lambda e: e.get(num_attr))
        label_enum = self.attr_label(enum_attr)
        label_num = self.attr_label(num_attr)
        direction = "highest" if use_max else "lowest"
        ewp = self.entity_word_plural
        q = rng.choice([
            f"Among {ewp} with {label_enum} \"{enum_val}\", which has "
            f"the {direction} {label_num}?",
            f"Of all {ewp} whose {label_enum} is \"{enum_val}\", "
            f"name the one with the {direction} {label_num}.",
        ])
        return GeneratedQA(
            q, best.name, "enum_filter",
            [e.name for e in members],
            purpose="comprehension", source_attr=num_attr,
        )

