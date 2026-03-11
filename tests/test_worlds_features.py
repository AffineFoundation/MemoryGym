"""Feature and integration tests for WorldTemplate.

Tests for stream evaluation, scoring invariants, smart guesser ceiling,
comprehension replacement, entity relationships, and contradictions.

Split from test_worlds.py to keep files under 1000 lines.
"""

from __future__ import annotations

import pytest
from collections import Counter
from random import Random

from memorygym.worlds.base import (
    Contradiction, GeneratedQA, World, WorldTemplate,
)
from memorygym.worlds.city import CityWorld
from memorygym.worlds.company import CompanyWorld
from memorygym.worlds.hospital import HospitalWorld
from memorygym.worlds.research import ResearchWorld
from memorygym.worlds.sport import SportWorld
from memorygym.worlds.movie import MovieWorld


def _construct_and_validate(q: GeneratedQA, tmpl: WorldTemplate,
                            world: World, stored_names: set[str],
                            updated_names: set[str],
                            applies_updates: bool,
                            n_total: int = 60) -> bool:
    """Delegate to bench._construct_and_validate."""
    from memorygym.bench import _construct_and_validate as _cv
    return _cv(q, tmpl, world, stored_names, updated_names,
               applies_updates, n_total)


def test_seed_not_in_visible_ids():
    """V11: Seed must not appear in sample ID or task name."""
    from memorygym.worlds.eval_task import worldbench
    task = worldbench(seed=42, template="company", n_entities=20,
                      n_questions=5, write_budget=10, backend="mock")
    # Task name and sample ID must not contain the seed
    assert "42" not in task.name, (
        f"Task name '{task.name}' should not contain seed '42'")
    for sample in task.dataset:
        assert "42" not in sample.id, (
            f"Sample ID '{sample.id}' should not contain seed '42'")


def test_judge_skips_abstention():
    """V10: Abstention uses rule-based validation, not LLM judge.

    In the no-fallback scorer (P4):
    - With judge: abstention → rule-based, all others → judge
    - Without judge: everything → rule-based
    Rule-based _abstention_match is authoritative for abstention.
    """
    from memorygym.evaluation.validators import AnswerValidator
    v = AnswerValidator()

    # Abstention: rule-based validator handles correctly
    assert v.validate("I don't know", "ABSTAIN", "abstention")
    assert not v.validate("42", "ABSTAIN", "abstention")

    # Non-abstention: rule-based is a valid fallback when no judge
    assert v.validate("50000", "50000", "retrieval")
    assert not v.validate("99999", "50000", "retrieval")


def test_stream_interleave():
    """Interleaved stream must produce questions mid-ingest."""
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        for seed in range(5):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng = Random(seed)
            corrections = tmpl.generate_corrections(world, rng, 5)
            stream = tmpl.generate_stream(
                world, rng, corrections,
                stored_names=set(), n_questions=20, entities_per_batch=10)

            types = [e["type"] for e in stream]
            q_count = types.count("question")
            assert q_count == 20, (
                f"{tmpl.name} seed={seed}: expected 20 questions, "
                f"got {q_count}")

            # Mid-stream questions: at least 1 question before last ingest
            last_ingest = max(i for i, t in enumerate(types)
                              if t == "ingest")
            mid_q = sum(1 for i, t in enumerate(types)
                        if t == "question" and i < last_ingest)
            assert mid_q >= 1, (
                f"{tmpl.name} seed={seed}: no mid-stream questions")


@pytest.mark.slow
def test_stream_invariants():
    """Stream mode must preserve core invariants: perfect=100%, guesser=0%."""
    from memorygym.bench import simulate_one_stream, STRATEGIES
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        accs = {}
        for seed in range(5):
            for profile in STRATEGIES:
                r = simulate_one_stream(tmpl, seed, profile, 60, 20, 5)
                accs.setdefault(profile["name"], []).append(r["accuracy"])
        avgs = {n: sum(v) / len(v) for n, v in accs.items()}
        assert avgs["perfect"] == 1.0, (
            f"{tmpl.name}: stream perfect={avgs['perfect']:.0%} != 100%")
        assert avgs["guesser"] == 0.0, (
            f"{tmpl.name}: stream guesser={avgs['guesser']:.0%} != 0%")
        assert avgs["strategic"] > avgs["naive"] + 0.10, (
            f"{tmpl.name}: stream strategic={avgs['strategic']:.0%} "
            f"not > naive={avgs['naive']:.0%} + 10%")


def test_stream_determinism():
    """Same seed must produce identical stream."""
    tmpl = CompanyWorld()
    for seed in range(3):
        w1 = tmpl.generate_world(seed=seed, n_entities=60)
        r1 = Random(seed)
        c1 = tmpl.generate_corrections(w1, r1, 5)
        s1 = tmpl.generate_stream(w1, r1, c1, set(), 20, 10)

        w2 = tmpl.generate_world(seed=seed, n_entities=60)
        r2 = Random(seed)
        c2 = tmpl.generate_corrections(w2, r2, 5)
        s2 = tmpl.generate_stream(w2, r2, c2, set(), 20, 10)

        assert len(s1) == len(s2), f"seed={seed}: stream length differs"
        for i, (a, b) in enumerate(zip(s1, s2)):
            assert a["type"] == b["type"], (
                f"seed={seed} event {i}: type {a['type']} != {b['type']}")
            if a["type"] == "question":
                assert a["question"] == b["question"], (
                    f"seed={seed} event {i}: question differs")
                assert a["answer"] == b["answer"], (
                    f"seed={seed} event {i}: answer differs")


def test_trick_retrieval():
    """Trick retrieval questions exist and have real (non-ABSTAIN) GT."""
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        trick_found = 0
        for seed in range(10):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng = Random(seed + 7777)
            corrections = tmpl.generate_corrections(world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng, world.entities, set(), 20, corrections)
            tricks = [q for q in qs if q.purpose == "trick_retrieval"]
            for q in tricks:
                # GT must be a real value, not ABSTAIN
                assert q.answer != "ABSTAIN", (
                    f"trick_retrieval GT should be real, got ABSTAIN")
                # Competency is retrieval
                assert q.competency == "retrieval"
                # Required entity must exist in world
                entity = world.get_entity(q.required_entities[0])
                assert entity is not None, (
                    f"trick_retrieval entity {q.required_entities[0]} not in world")
            trick_found += len(tricks)
        assert trick_found > 0, (
            f"{tmpl.name}: no trick_retrieval questions across 10 seeds")


def test_eval_salt():
    """eval_salt changes values but preserves entity names and structure."""
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        w0 = tmpl.generate_world(seed=42, n_entities=20, eval_salt=0)
        w1 = tmpl.generate_world(seed=42, n_entities=20, eval_salt=99)

        # Same entity names
        names0 = [e.name for e in w0.entities]
        names1 = [e.name for e in w1.entities]
        assert names0 == names1, f"{tmpl.name}: names differ with salt"

        # Same active attrs
        assert w0.active_attrs == w1.active_attrs

        # Values must differ
        changed = 0
        total = 0
        for e0, e1 in zip(w0.entities, w1.entities):
            for attr in w0.active_attrs:
                v0, v1 = e0.get(attr), e1.get(attr)
                if v0 is not None:
                    total += 1
                    if v0 != v1:
                        changed += 1
        assert changed > total * 0.8, (
            f"{tmpl.name}: only {changed}/{total} values changed with salt")

        # Determinism: same salt → same values
        w2 = tmpl.generate_world(seed=42, n_entities=20, eval_salt=99)
        for e1, e2 in zip(w1.entities, w2.entities):
            for attr in w1.active_attrs:
                assert e1.get(attr) == e2.get(attr), (
                    f"{tmpl.name}: same salt produces different values")


def test_always_abstain_fails():
    """An always-abstain strategy must score 0% on trick_retrieval.

    This is the key anti-hack property: answering "I don't know" to
    everything cannot score perfectly because trick_retrieval questions
    have real answers.
    """
    from memorygym.evaluation.validators import AnswerValidator
    validator = AnswerValidator()

    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        for seed in range(5):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng = Random(seed + 7777)
            corrections = tmpl.generate_corrections(world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng, world.entities, set(), 20, corrections)
            tricks = [q for q in qs if q.purpose == "trick_retrieval"]
            for q in tricks:
                # Always-abstain answer
                result = validator.validate(
                    "I don't have enough information",
                    q.answer, q.competency)
                assert not result, (
                    f"always-abstain scored on trick_retrieval: "
                    f"GT={q.answer}, comp={q.competency}")


def test_smart_guesser_ceiling():
    """Midpoint/common-value guessing must stay below 5% accuracy.

    The smart_guesser uses domain knowledge about attribute ranges to
    make plausible guesses (midpoints, quartiles). V14's integer-exact
    matching defeats this: random integers almost never match exact GT.
    """
    from memorygym.bench import _smart_guess, _VALIDATOR

    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        correct_total = 0
        question_total = 0
        for seed in range(5):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng_q = Random(seed + 7777)
            corrections = tmpl.generate_corrections(world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng_q, world.entities, set(), 20, corrections)
            guess_rng = Random(seed + 9999)
            for q in qs:
                guess = _smart_guess(q, world, guess_rng)
                if guess and _VALIDATOR.validate(guess, q.answer, q.competency):
                    correct_total += 1
                question_total += 1

        accuracy = correct_total / question_total if question_total else 0
        assert accuracy < 0.05, (
            f"{tmpl.name} smart_guesser accuracy {accuracy:.1%} >= 5%")


def test_validator_handles_formatted_values():
    """Formatted display values must validate against raw GT.

    Covers the K/M suffix bug: _format_value produces "$498,985.9M" but
    GT is "498985.9". Rule-based validator must accept both interpretations.

    Validates that _format_value output (what agents see in documents)
    can be matched against raw GT by the rule-based validator.

    Skips values near 0 where display rounding may exceed 2% tolerance
    (e.g. 0.49 → "0.5%" is 2.04% off — edge case, not a scoring bug).
    """
    from memorygym.evaluation.validators import AnswerValidator
    v = AnswerValidator()

    failures = []
    total = 0
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        world = tmpl.generate_world(seed=42, n_entities=20)
        for e in world.entities[:5]:
            for attr in world.active_attrs:
                val = e.get(attr)
                if val is None:
                    continue
                # Skip near-zero values where rounding exceeds 2% tolerance
                if isinstance(val, (int, float)) and abs(val) < 1:
                    continue
                # Skip non-scalar types (list, etc.) — validated elsewhere
                if isinstance(val, list):
                    continue
                formatted = tmpl._format_value(attr, val)
                gt_str = str(val)
                total += 1
                if not v.validate(formatted, gt_str, "retrieval"):
                    failures.append(
                        f"{tmpl.name}: '{formatted}' vs GT '{gt_str}' "
                        f"({e.name}.{attr})")

    assert len(failures) == 0, (
        f"{len(failures)}/{total} formatted values failed validation:\n"
        + "\n".join(failures[:5]))


def test_relationship_hop_chain_numeric_match():
    """relationship_hop and relationship_chain must use numeric matching.

    GT from _format_value (e.g. "$34,620.4M", "17,976") must match
    stripped numeric answers ("34620.4", "17976").
    """
    from memorygym.evaluation.validators import AnswerValidator
    v = AnswerValidator()

    cases = [
        ("relationship_hop", "$34,620.4M", "34620.4", True),
        ("relationship_hop", "17,976", "17976", True),
        ("relationship_chain", "$1.5M", "1.5", True),
        ("relationship_chain", "42.7%", "42.7", True),
        ("relationship_hop", "$34,620.4M", "99999", False),
    ]
    for qtype, gt, answer, expected in cases:
        result = v.validate(answer, gt, qtype)
        assert result == expected, (
            f"{qtype}: validate({answer!r}, {gt!r}) = {result}, expected {expected}"
        )


def test_km_suffix_guesser_still_zero():
    """K/M-suffix-aware validator must not help smart_guesser break 5%.

    Verifies that trying both suffix interpretations doesn't create
    a new attack vector for midpoint/quartile guessing.
    """
    from memorygym.bench import _smart_guess, _VALIDATOR

    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]:
        tmpl = TmplClass()
        correct_total = 0
        question_total = 0
        for seed in range(5):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng_q = Random(seed + 7777)
            corrections = tmpl.generate_corrections(world, Random(seed + 3333), 5)
            qs = tmpl.gen_adaptive_questions(
                world, rng_q, world.entities, set(), 20, corrections)
            guess_rng = Random(seed + 9999)
            for q in qs:
                guess = _smart_guess(q, world, guess_rng)
                if guess and _VALIDATOR.validate(guess, q.answer, q.competency):
                    correct_total += 1
                question_total += 1

        accuracy = correct_total / question_total if question_total else 0
        assert accuracy < 0.05, (
            f"{tmpl.name} smart_guesser with K/M fix: {accuracy:.1%} >= 5%")


def test_detect_stored_numeric_variants():
    """detect_stored_entities must find entities stored with various formats.

    Tests that _numeric_variants covers raw, rounded, and decimal formats
    beyond the original _format_value + int(round()) checks.
    """
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=42, n_entities=20)

    # Build documents using raw numeric format (not _format_value)
    raw_docs = []
    for e in world.entities[:10]:
        parts = [e.name]
        for attr in world.active_attrs:
            val = e.get(attr)
            if val is not None:
                parts.append(f"{attr}: {val}")
        raw_docs.append(", ".join(parts))

    stored, missed = tmpl.detect_stored_entities(world, raw_docs)
    assert len(stored) >= 8, (
        f"Raw-format docs detected only {len(stored)} entities, expected ≥8")


@pytest.mark.slow
def test_priority_beats_random():
    """Priority storage (WHAT you store) must outperform random storage.

    Both strategies store exactly 50% of entities with updates enabled.
    Priority selects entities by question likelihood (populated categories,
    attribute completeness, extreme values). This proves that storage
    strategy quality matters — not just storage quantity.
    """
    from memorygym.bench import _entity_priority_score

    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld,
                       HospitalWorld, SportWorld]:
        tmpl = TmplClass()
        priority_wins = 0
        ties = 0
        total = 0
        for seed in range(10):
            world_p = tmpl.generate_world(seed=seed, n_entities=60)
            world_r = tmpl.generate_world(seed=seed, n_entities=60)

            rng_doc_p = Random(seed)
            rng_doc_r = Random(seed)
            all_docs_p = [(e, tmpl.render_document(e, world_p.active_attrs, rng_doc_p))
                          for e in world_p.entities]
            all_docs_r = [(e, tmpl.render_document(e, world_r.active_attrs, rng_doc_r))
                          for e in world_r.entities]

            n_store = max(1, int(len(all_docs_p) * 0.5))

            # Priority: top-N by importance score
            scored = [(i, _entity_priority_score(e, world_p))
                      for i, (e, _) in enumerate(all_docs_p)]
            scored.sort(key=lambda x: -x[1])
            p_docs = [all_docs_p[i][1] for i, _ in scored[:n_store]]

            # Random: random N
            rng_store = Random(seed + 111)
            r_indices = rng_store.sample(range(len(all_docs_r)), n_store)
            r_docs = [all_docs_r[i][1] for i in r_indices]

            p_stored, _ = tmpl.detect_stored_entities(world_p, p_docs)
            r_stored, _ = tmpl.detect_stored_entities(world_r, r_docs)

            # Generate corrections and questions for both
            rng_cp = Random(seed + 3333)
            corrections_p = tmpl.generate_corrections(world_p, rng_cp, 5)
            rng_cr = Random(seed + 3333)
            corrections_r = tmpl.generate_corrections(world_r, rng_cr, 5)

            p_updated = {c.entity_name for c in corrections_p
                         if c.entity_name in p_stored}
            r_updated = {c.entity_name for c in corrections_r
                         if c.entity_name in r_stored}

            rng_qp = Random(seed + 7777)
            qs_p = tmpl.gen_adaptive_questions(
                world_p, rng_qp, world_p.entities, p_stored, 20, corrections_p)
            rng_qr = Random(seed + 7777)
            qs_r = tmpl.gen_adaptive_questions(
                world_r, rng_qr, world_r.entities, r_stored, 20, corrections_r)

            p_correct = sum(1 for q in qs_p
                            if _construct_and_validate(
                                q, tmpl, world_p, p_stored, p_updated, True,
                                len(world_p.entities)))
            r_correct = sum(1 for q in qs_r
                            if _construct_and_validate(
                                q, tmpl, world_r, r_stored, r_updated, True,
                                len(world_r.entities)))

            total += 1
            if p_correct > r_correct:
                priority_wins += 1
            elif p_correct == r_correct:
                ties += 1

        win_rate = priority_wins / total
        assert win_rate >= 0.3 or (priority_wins + ties) / total >= 0.6, (
            f"{tmpl.name}: priority only wins {priority_wins}/{total} seeds "
            f"(ties={ties}) — strategy quality doesn't differentiate")


def test_format_roundtrip_in_simulation():
    """Verify _format_value() → validate() roundtrip for all templates.

    For every retrieval/update question, constructing the answer via
    _format_value(attr, val) must pass validation against the GT.
    This catches precision/suffix bugs that would be invisible with
    a boolean _can_answer() shortcut.
    """
    from memorygym.evaluation.validators import AnswerValidator
    validator = AnswerValidator()

    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld,
                       HospitalWorld, SportWorld]:
        tmpl = TmplClass()
        for seed in range(3):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng_correct = Random(seed + 3333)
            corrections = tmpl.generate_corrections(world, rng_correct, 5)
            rng_q = Random(seed + 7777)
            stored = {e.name for e in world.entities}
            questions = tmpl.gen_adaptive_questions(
                world, rng_q, world.entities, stored, 20, corrections)

            for q in questions:
                if q.competency not in ("retrieval", "update"):
                    continue
                if not q.source_attr:
                    continue
                entity = world.get_entity(q.required_entities[0])
                if not entity:
                    continue
                val = entity.get(q.source_attr)
                if val is None:
                    continue
                formatted = tmpl._format_value(q.source_attr, val)
                ok = validator.validate(formatted, q.answer, q.competency)
                assert ok, (
                    f"{tmpl.name} seed={seed}: _format_value({q.source_attr}, "
                    f"{val})={formatted!r} failed validation against "
                    f"GT={q.answer!r} (competency={q.competency})")


def test_adaptive_comprehension():
    """Comprehension questions must only reference stored entities.

    When stored_names is provided, all comprehension questions should
    reference entities within that set. This ensures the reasoning axis
    tests reasoning ability, not storage luck.
    """
    for TmplClass in [CompanyWorld, ResearchWorld, CityWorld,
                       HospitalWorld, SportWorld]:
        tmpl = TmplClass()
        for seed in range(5):
            world = tmpl.generate_world(seed=seed, n_entities=60)
            rng = Random(seed)
            corrections = tmpl.generate_corrections(world, rng, 5)

            # Only store first 30 entities (50% coverage)
            stored = {e.name for e in world.entities[:30]}
            rng_q = Random(seed + 7777)
            questions = tmpl.gen_adaptive_questions(
                world, rng_q, world.entities, stored, 20, corrections)

            comp_types = {"synthesis", "aggregation", "conditional",
                          "ratio", "comparison", "multi_hop", "outlier"}
            for q in questions:
                if q.competency in comp_types:
                    needed = set(q.required_entities)
                    assert needed <= stored, (
                        f"{tmpl.name} seed={seed}: {q.competency} "
                        f"references unstored entities: "
                        f"{needed - stored}")


def test_maybe_replace_comprehension():
    """maybe_replace_comprehension replaces unanswerable questions."""
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=0, n_entities=60)

    # Simulate storing first 30 entities
    stored_contents = []
    for e in world.entities[:30]:
        doc = tmpl._compact_document(e, world.active_attrs)
        stored_contents.append(f"{e.name} | {doc}")

    # Create a question referencing unstored entities
    unstored = world.entities[50]
    bad_event = {
        "type": "question",
        "question": f"What is {unstored.name}'s revenue?",
        "answer": "test",
        "competency": "synthesis",
        "purpose": "comprehension",
        "required_entities": [unstored.name],
        "source_attr": "revenue_m",
    }

    replaced = tmpl.maybe_replace_comprehension(
        bad_event, world, stored_contents, rng_seed=42)

    # Should be replaced with a question about stored entities
    assert replaced is not bad_event, "Question should have been replaced"
    stored_names = {e.name for e in world.entities[:30]}
    new_entities = set(replaced["required_entities"])
    assert new_entities <= stored_names, (
        f"Replacement references unstored: {new_entities - stored_names}")

    # A question with all stored entities should NOT be replaced
    stored_entity = world.entities[0]
    good_event = {
        "type": "question",
        "question": f"What is {stored_entity.name}'s revenue?",
        "answer": "test",
        "competency": "comparison",
        "purpose": "comprehension",
        "required_entities": [stored_entity.name, world.entities[1].name],
        "source_attr": "revenue_m",
    }
    not_replaced = tmpl.maybe_replace_comprehension(
        good_event, world, stored_contents, rng_seed=42)
    assert not_replaced is good_event, "Stored question should not be replaced"


def test_relationship_generation():
    """CompanyWorld generates relationships deterministically."""
    tmpl = CompanyWorld()
    w1 = tmpl.generate_world(seed=42, n_entities=30)
    w2 = tmpl.generate_world(seed=42, n_entities=30)
    assert len(w1.relationships) > 0, "Should generate relationships"
    assert len(w1.relationships) == len(w2.relationships), "Deterministic count"
    for r1, r2 in zip(w1.relationships, w2.relationships):
        assert r1.source == r2.source
        assert r1.relation == r2.relation
        assert r1.target == r2.target
    # No self-loops
    for r in w1.relationships:
        assert r.source != r.target, f"Self-loop: {r.source}"
    # Query methods work
    if w1.relationships:
        name = w1.relationships[0].source
        assert len(w1.get_outgoing(name)) >= 1
        assert len(w1.get_relationships(name)) >= 1


def test_relationship_questions():
    """Relationship question types generate valid questions."""
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=42, n_entities=60)
    assert len(world.relationships) > 0

    rng = Random(42)
    corrections = tmpl.generate_corrections(world, Random(42 + 3333), 5)
    stored = {e.name for e in world.entities}
    qs = tmpl.gen_adaptive_questions(
        world, rng, world.entities, stored, 40, corrections)
    rel_qs = [q for q in qs if "relationship" in q.competency]
    assert len(rel_qs) >= 1, "Should generate at least 1 relationship question"
    valid_rel_types = (
        "relationship_lookup", "relationship_hop",
        "relationship_chain", "relationship_count",
        "relationship_filter",
    )
    for q in rel_qs:
        assert q.competency in valid_rel_types, (
            f"Unknown relationship type: {q.competency}")
        assert len(q.required_entities) >= 2
        assert q.answer, "Answer must not be empty"
        # All entities must exist in world
        for name in q.required_entities:
            assert world.get_entity(name) is not None, f"Unknown entity: {name}"


def test_relationship_gt_correct():
    """Relationship question GT must match actual world data."""
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=42, n_entities=60)
    assert len(world.relationships) > 0

    rng = Random(42)
    corrections = tmpl.generate_corrections(world, Random(42 + 3333), 5)
    stored = {e.name for e in world.entities}
    qs = tmpl.gen_adaptive_questions(
        world, rng, world.entities, stored, 40, corrections)
    rel_qs = [q for q in qs if "relationship" in q.competency]

    for q in rel_qs:
        if q.competency == "relationship_lookup":
            # GT should be target of a real relationship from source
            source = q.required_entities[0]
            outgoing = world.get_outgoing(source)
            assert q.answer in [r.target for r in outgoing], (
                f"lookup GT {q.answer} not in {source}'s outgoing targets")

        elif q.competency == "relationship_count":
            # GT should be a valid integer count
            int(q.answer)  # must not raise

        elif q.competency == "relationship_hop":
            # GT should be a formatted attribute value of the target entity
            target = q.required_entities[1]
            entity = world.get_entity(target)
            assert entity is not None

        elif q.competency == "relationship_filter":
            # GT should be a real entity name
            assert world.get_entity(q.answer) is not None


def test_contradictions():
    """Implicit contradictions mutate world state and generate questions."""
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=42, n_entities=60)
    rng = Random(42)
    corrections = tmpl.generate_corrections(world, rng, 5)
    exclude = {c.entity_name for c in corrections}

    # Snapshot pre-contradiction values
    rng_contra = Random(42 + 7373)
    contras = tmpl.generate_contradictions(
        world, rng_contra, 2, exclude_entities=exclude)

    assert len(contras) == 2
    for ct in contras:
        assert isinstance(ct, Contradiction)
        assert ct.entity_name not in exclude, "Contradiction must not overlap with corrections"
        assert ct.old_val != ct.new_val
        # World state was mutated to new value
        entity = world.get_entity(ct.entity_name)
        assert entity.get(ct.attr) == ct.new_val
        # Document is a regular doc (no CORRECTION label)
        assert "CORRECTION" not in ct.document
        assert ct.entity_name in ct.document

    # Questions about contradicted entities should use updated GT
    stored_names = {e.name for e in world.entities}
    rng_q = Random(42 + 7777)
    questions = tmpl.gen_adaptive_questions(
        world, rng_q, world.entities, stored_names, 20, corrections,
        contras)
    contra_qs = [q for q in questions if q.purpose == "contradiction"]
    assert len(contra_qs) > 0, "Must generate contradiction questions"
    for q in contra_qs:
        assert q.competency == "update"
        entity = world.get_entity(q.required_entities[0])
        # GT must match current world state (formatted)
        expected = tmpl._format_value(q.source_attr, entity.get(q.source_attr))
        assert expected == q.answer


def test_lite_tier_contradictions_not_lost():
    """Bug fix: contradiction_batch must not exceed n_batches (lite tier)."""
    from memorygym.worlds.city import CityWorld
    tmpl = CityWorld()  # city has lowest correction_rate → late corrections
    world = tmpl.generate_world(seed=42, n_entities=30, eval_salt=1)
    rng_c = Random(42 + 3333)
    corrections = tmpl.generate_corrections(world, rng_c, 3)
    rng_contra = Random(42 + 7373)
    contradictions = tmpl.generate_contradictions(world, rng_contra, 1)
    rng_s = Random(42 + 5555)
    stream = tmpl.generate_stream(
        world, rng_s, corrections, set(), 10,
        contradictions=contradictions,
    )
    contra_events = [e for e in stream if e.get("is_contradiction")]
    assert len(contra_events) >= 1, \
        "Lite tier must include contradiction events in stream"


def test_mid_question_weights_match_template():
    """Mid-stream questions should respect template question_weights."""
    from memorygym.worlds.hospital import HospitalWorld
    from memorygym.worlds.city import CityWorld

    def _count_mid_q_types(tmpl_cls, seed=42, n_runs=20):
        counts = {"recall": 0, "coverage": 0, "update": 0,
                  "comprehension": 0, "abstention": 0}
        for s in range(seed, seed + n_runs):
            tmpl = tmpl_cls()
            world = tmpl.generate_world(seed=s, n_entities=60, eval_salt=1)
            rng_c = Random(s + 3333)
            corrections = tmpl.generate_corrections(world, rng_c, 5)
            rng_s = Random(s + 5555)
            stream = tmpl.generate_stream(
                world, rng_s, corrections,
                {e.name for e in world.entities}, 20,
            )
            for e in stream:
                if e["type"] == "question" and e.get("purpose") in counts:
                    counts[e["purpose"]] += 1
        return counts

    hospital_counts = _count_mid_q_types(HospitalWorld)
    city_counts = _count_mid_q_types(CityWorld)

    # Hospital has update=0.30, city has update=0.10
    # Hospital should generate more update questions than city
    h_total = sum(hospital_counts.values()) or 1
    c_total = sum(city_counts.values()) or 1
    h_update_frac = hospital_counts["update"] / h_total
    c_update_frac = city_counts["update"] / c_total
    assert h_update_frac > c_update_frac, \
        f"Hospital update fraction ({h_update_frac:.2f}) should exceed " \
        f"city ({c_update_frac:.2f})"


if __name__ == "__main__":
    tests = [
        test_seed_not_in_visible_ids,
        test_judge_skips_abstention,
        test_stream_interleave,
        test_stream_invariants,
        test_stream_determinism,
        test_trick_retrieval,
        test_always_abstain_fails,
        test_eval_salt,
        test_smart_guesser_ceiling,
        test_validator_handles_formatted_values,
        test_km_suffix_guesser_still_zero,
        test_detect_stored_numeric_variants,
        test_priority_beats_random,
        test_format_roundtrip_in_simulation,
        test_adaptive_comprehension,
        test_maybe_replace_comprehension,
        test_relationship_generation,
        test_relationship_questions,
        test_relationship_gt_correct,
        test_contradictions,
        test_lite_tier_contradictions_not_lost,
        test_mid_question_weights_match_template,
    ]
    print("Running feature tests...")
    for t in tests:
        t()
        print(f"  ✓ {t.__name__}")
    print("ALL TESTS PASSED")
