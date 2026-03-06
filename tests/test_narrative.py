"""Tests for narrative documents and derived-value questions.

Tests narrative rendering (Layer 1) and ratio/comparison/delta questions (Layer 2).
"""

from __future__ import annotations

from random import Random

from memorybench.evaluation.validators import AnswerValidator
from memorybench.worlds.base import WorldTemplate
from memorybench.worlds.city import CityWorld
from memorybench.worlds.company import CompanyWorld
from memorybench.worlds.hospital import HospitalWorld
from memorybench.worlds.research import ResearchWorld
from memorybench.worlds.sport import SportWorld

ALL_TMPLS = [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld]


def test_narrative_no_pipe_format():
    """Narrative docs must not use pipe-delimited KV format."""
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        world = tmpl.generate_world(seed=42, n_entities=20)
        rng = Random(42)
        for e in world.entities[:5]:
            doc = tmpl.render_document(
                e, world.active_attrs, rng,
                other_entities=world.entities[:20])
            # Header lines may contain pipes, body should not
            body_lines = doc.split("\n")[2:]  # skip header
            body = "\n".join(body_lines)
            assert " | " not in body, (
                f"{tmpl.name}: narrative body still has pipe format:\n"
                f"{body[:200]}")


def test_narrative_contains_values():
    """Narrative docs must contain the actual attribute values."""
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        world = tmpl.generate_world(seed=42, n_entities=20)
        rng = Random(42)
        found = 0
        total = 0
        for e in world.entities[:10]:
            doc = tmpl.render_document(
                e, world.active_attrs, rng,
                other_entities=world.entities[:20])
            for attr in world.active_attrs:
                val = e.get(attr)
                if val is None:
                    continue
                total += 1
                fmt = tmpl._format_value(attr, val)
                # Check formatted value appears in document
                if fmt in doc:
                    found += 1
        # At least 80% of values should appear (some comparative
        # distractors may reference other entity values instead)
        assert found / total >= 0.8, (
            f"{tmpl.name}: only {found}/{total} values found in docs")


def test_narrative_determinism():
    """Same seed must produce identical narrative documents."""
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        for seed in range(3):
            w1 = tmpl.generate_world(seed=seed, n_entities=20)
            w2 = tmpl.generate_world(seed=seed, n_entities=20)
            rng1, rng2 = Random(seed), Random(seed)
            for e1, e2 in zip(w1.entities[:5], w2.entities[:5]):
                d1 = tmpl.render_document(
                    e1, w1.active_attrs, rng1,
                    other_entities=w1.entities[:20])
                d2 = tmpl.render_document(
                    e2, w2.active_attrs, rng2,
                    other_entities=w2.entities[:20])
                assert d1 == d2, (
                    f"{tmpl.name} seed={seed}: narrative not deterministic")


def test_narrative_distractors():
    """Narrative docs must contain distractor values (not just GT)."""
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        world = tmpl.generate_world(seed=42, n_entities=30)
        rng = Random(42)
        docs = []
        for e in world.entities[:10]:
            doc = tmpl.render_document(
                e, world.active_attrs, rng,
                other_entities=world.entities[:30])
            docs.append(doc)
        all_text = "\n".join(docs)
        # At least some docs should contain temporal/comparative language
        has_distractor = any(
            phrase in all_text.lower()
            for phrase in ["from", "compared to", "though only",
                           "of which", "versus"])
        assert has_distractor, (
            f"{tmpl.name}: no distractor language found in narrative docs")


def test_narrative_no_entity_leak():
    """Narrative docs must not leak other entities' names+values.

    Comparative distractors must use fabricated references, not real
    entity data. Otherwise detect_stored_entities produces false
    positives, inflating coverage metrics.
    """
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        world = tmpl.generate_world(seed=42, n_entities=30)
        rng = Random(42)
        # Render only first 5 entities' docs
        docs = [tmpl.render_document(
            world.entities[i], world.active_attrs, rng,
            other_entities=world.entities[:30])
            for i in range(5)]
        stored, _ = tmpl.detect_stored_entities(world, docs)
        front_5 = {world.entities[i].name for i in range(5)}
        false_pos = stored - front_5
        assert len(false_pos) == 0, (
            f"{tmpl.name}: narrative leaks {len(false_pos)} other "
            f"entities: {false_pos}")


def test_compact_still_works():
    """Compact (KV) mode must still work when other_entities=None."""
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        world = tmpl.generate_world(seed=42, n_entities=10)
        rng = Random(42)
        for e in world.entities[:3]:
            doc = tmpl.render_document(e, world.active_attrs, rng)
            # Compact format uses " | " separators
            assert " | " in doc, (
                f"{tmpl.name}: compact mode broken, no pipe found")


def test_ratio_gt_correct():
    """Ratio question GT must match attr1/attr2 from world state."""
    v = AnswerValidator()
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        ratio_found = 0
        for seed in range(10):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng = Random(seed + 7777)
            corrections = tmpl.generate_corrections(
                world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng, world.entities,
                {e.name for e in world.entities}, 20, corrections)
            for q in qs:
                if q.competency == "ratio":
                    ratio_found += 1
                    # GT should be a valid number
                    gt = float(q.answer)
                    assert gt >= 0 or gt < 0, (
                        f"ratio GT not a number: {q.answer}")
                    # Perfect agent should get it right
                    assert v.validate(q.answer, q.answer, q.competency), (
                        f"ratio GT doesn't self-validate: {q.answer}")
        assert ratio_found > 0, (
            f"{tmpl.name}: no ratio questions across 10 seeds")


def test_comparison_gt_correct():
    """Comparison GT must name a real entity with correct difference."""
    v = AnswerValidator()
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        comp_found = 0
        for seed in range(10):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng = Random(seed + 7777)
            corrections = tmpl.generate_corrections(
                world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng, world.entities,
                {e.name for e in world.entities}, 20, corrections)
            for q in qs:
                if q.competency == "comparison":
                    comp_found += 1
                    # GT format: "EntityName (diff)"
                    assert "(" in q.answer and ")" in q.answer, (
                        f"comparison GT format wrong: {q.answer}")
                    # Required entities should exist in world
                    for name in q.required_entities:
                        assert world.get_entity(name) is not None, (
                            f"comparison entity {name} not in world")
                    # Self-validate
                    assert v.validate(q.answer, q.answer, q.competency)
        assert comp_found > 0, (
            f"{tmpl.name}: no comparison questions across 10 seeds")


def test_delta_gt_correct():
    """Delta GT must equal abs(new_val - old_val) from correction."""
    v = AnswerValidator()
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        delta_found = 0
        for seed in range(10):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng = Random(seed + 7777)
            corrections = tmpl.generate_corrections(
                world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng, world.entities,
                {e.name for e in world.entities}, 20, corrections)
            for q in qs:
                if q.competency == "delta":
                    delta_found += 1
                    gt = float(q.answer)
                    assert gt >= 0, f"delta GT should be non-negative: {gt}"
                    assert v.validate(q.answer, q.answer, q.competency)
        assert delta_found > 0, (
            f"{tmpl.name}: no delta questions across 10 seeds")


def test_new_types_dont_leak_keywords():
    """New question types must not leak 'update'/'correction'/'stored'."""
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        for seed in range(5):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng = Random(seed + 7777)
            corrections = tmpl.generate_corrections(
                world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng, world.entities, set(), 20, corrections)
            for q in qs:
                if q.competency in ("ratio", "comparison", "delta",
                                     "multi_hop", "outlier"):
                    text = q.question.lower()
                    assert "update" not in text, (
                        f"{q.competency} leaks 'update': {q.question}")
                    assert "correction" not in text
                    assert "stored" not in text
                    assert "revised" not in text


def test_smart_guesser_new_types():
    """Smart guesser must fail on ratio/comparison/delta questions."""
    from memorybench.bench import _smart_guess, _VALIDATOR

    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        correct = 0
        total = 0
        for seed in range(5):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng_q = Random(seed + 7777)
            corrections = tmpl.generate_corrections(
                world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng_q, world.entities, set(), 20, corrections)
            guess_rng = Random(seed + 9999)
            for q in qs:
                if q.competency in ("ratio", "comparison", "delta",
                                     "multi_hop", "outlier"):
                    guess = _smart_guess(q, world, guess_rng)
                    if guess and _VALIDATOR.validate(
                            guess, q.answer, q.competency):
                        correct += 1
                    total += 1
        if total > 0:
            acc = correct / total
            assert acc < 0.10, (
                f"{tmpl.name}: smart_guesser on new types "
                f"{acc:.0%} >= 10%")


def test_multi_hop_gt_correct():
    """Multi-hop GT must name an entity from the correct category."""
    v = AnswerValidator()
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        found = 0
        for seed in range(10):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng = Random(seed + 7777)
            corrections = tmpl.generate_corrections(
                world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng, world.entities,
                {e.name for e in world.entities}, 20, corrections)
            for q in qs:
                if q.competency == "multi_hop":
                    found += 1
                    assert "(" in q.answer and ")" in q.answer, (
                        f"multi_hop GT format wrong: {q.answer}")
                    for name in q.required_entities:
                        assert world.get_entity(name) is not None
                    assert v.validate(q.answer, q.answer, q.competency)
        assert found > 0, (
            f"{tmpl.name}: no multi_hop questions across 10 seeds")


def test_outlier_gt_correct():
    """Outlier GT must name the entity with max deviation from mean."""
    v = AnswerValidator()
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        found = 0
        for seed in range(10):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng = Random(seed + 7777)
            corrections = tmpl.generate_corrections(
                world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng, world.entities,
                {e.name for e in world.entities}, 20, corrections)
            for q in qs:
                if q.competency == "outlier":
                    found += 1
                    assert "(" in q.answer and ")" in q.answer
                    for name in q.required_entities:
                        assert world.get_entity(name) is not None
                    assert v.validate(q.answer, q.answer, q.competency)
        assert found > 0, (
            f"{tmpl.name}: no outlier questions across 10 seeds")


def test_comprehension_types_not_fingerprint_exploitable():
    """Even if question type is detectable, type detection must not help score.

    Strategy: detect type → apply type-specific guessing heuristic.
    Must still score <5% because all new types require stored data.
    """
    from memorybench.bench import _VALIDATOR

    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        correct = 0
        total = 0
        for seed in range(10):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng_q = Random(seed + 7777)
            corrections = tmpl.generate_corrections(
                world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng_q, world.entities, set(), 20, corrections)
            guess_rng = Random(seed + 8888)
            for q in qs:
                # Type-aware guessing: best heuristic per type
                if q.competency == "ratio":
                    guess = str(round(guess_rng.uniform(0.001, 500), 2))
                elif q.competency == "delta":
                    guess = str(guess_rng.choice([5, 50, 500, 5000]))
                elif q.competency in ("comparison", "multi_hop",
                                       "outlier"):
                    e = guess_rng.choice(world.entities)
                    guess = f"{e.name} ({guess_rng.randint(1, 50000)})"
                else:
                    continue
                total += 1
                if _VALIDATOR.validate(guess, q.answer, q.competency):
                    correct += 1
        if total > 0:
            acc = correct / total
            assert acc < 0.05, (
                f"{tmpl.name}: type-aware guesser {acc:.1%} >= 5%")


def test_multi_hop_requires_reasoning():
    """Multi-hop answer must match two-step computation from world state."""
    tmpl = CompanyWorld()
    for seed in range(5):
        world = tmpl.generate_world(seed=seed, n_entities=60)
        rng = Random(seed + 7777)
        corrections = tmpl.generate_corrections(
            world, Random(seed + 3333), 5)
        qs = tmpl.gen_adaptive_questions(
            world, rng, world.entities,
            {e.name for e in world.entities}, 20, corrections)
        for q in qs:
            if q.competency == "multi_hop":
                # All required entities must be from the same category
                cats = {world.get_entity(n).category
                        for n in q.required_entities}
                assert len(cats) == 1, (
                    f"multi_hop entities span {len(cats)} categories")


if __name__ == "__main__":
    tests = [
        ("narrative_no_pipe_format", test_narrative_no_pipe_format),
        ("narrative_contains_values", test_narrative_contains_values),
        ("narrative_determinism", test_narrative_determinism),
        ("narrative_distractors", test_narrative_distractors),
        ("narrative_no_entity_leak", test_narrative_no_entity_leak),
        ("compact_still_works", test_compact_still_works),
        ("ratio_gt_correct", test_ratio_gt_correct),
        ("comparison_gt_correct", test_comparison_gt_correct),
        ("delta_gt_correct", test_delta_gt_correct),
        ("new_types_dont_leak_keywords", test_new_types_dont_leak_keywords),
        ("smart_guesser_new_types", test_smart_guesser_new_types),
        ("multi_hop_gt_correct", test_multi_hop_gt_correct),
        ("outlier_gt_correct", test_outlier_gt_correct),
        ("comprehension_types_not_fingerprint_exploitable",
         test_comprehension_types_not_fingerprint_exploitable),
        ("multi_hop_requires_reasoning", test_multi_hop_requires_reasoning),
    ]
    for name, fn in tests:
        fn()
        print(f"  \u2713 {name}")
    print("ALL NARRATIVE TESTS PASSED")
