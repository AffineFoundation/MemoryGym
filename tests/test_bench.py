"""Tests for bench.py internal logic and protocol integration.

Simulation invariant tests (perfect=100%, guesser=0%, etc.) live in
test_worlds.py — this file tests internal helpers, CLI output, and
the standard evaluation protocol.
"""

from __future__ import annotations

from memorygym.bench import (
    STRATEGIES,
    TEMPLATES,
    _construct_and_validate,
    _data_available,
    _smart_guess,
    _VALIDATOR,
    run_validation,
    simulate_one,
)
from memorygym.protocol import (
    OFFICIAL_SEEDS,
    TIERS,
    aggregate_results,
    compute_composite,
)
from memorygym.worlds.base import GeneratedQA


# ── _data_available ──


class TestDataAvailable:
    """Data availability check logic."""

    def test_abstention_needs_coverage(self):
        q = GeneratedQA("q", "ABSTAIN", "abstention", ["fake_name"])
        assert _data_available(q, {"a", "b", "c"}, set(), True, 5)
        assert not _data_available(q, {"a"}, set(), True, 5)

    def test_update_needs_applied(self):
        q = GeneratedQA("q", "100", "update", ["Alice"])
        assert _data_available(q, {"Alice"}, {"Alice"}, True, 10)
        assert not _data_available(q, {"Alice"}, set(), True, 10)
        assert not _data_available(q, {"Alice"}, {"Alice"}, False, 10)

    def test_retrieval_needs_entity(self):
        q = GeneratedQA("q", "100", "retrieval", ["Alice"])
        assert _data_available(q, {"Alice"}, set(), True, 10)
        assert not _data_available(q, set(), set(), True, 10)

    def test_always_abstain(self):
        q_abs = GeneratedQA("q", "ABSTAIN", "abstention", ["fake"])
        q_ret = GeneratedQA("q", "100", "retrieval", ["Alice"])
        assert _data_available(q_abs, {"Alice"}, set(), True, 10,
                               always_abstain=True)
        assert not _data_available(q_ret, {"Alice"}, set(), True, 10,
                                   always_abstain=True)


# ── _construct_and_validate ──


class TestConstructAndValidate:
    """Construct answer and validate against GT."""

    def _tmpl_and_world(self):
        tmpl = TEMPLATES["company"]()
        world = tmpl.generate_world(seed=0, n_entities=10)
        return tmpl, world

    def test_retrieval_roundtrip(self):
        """Retrieval answer via _format_value validates against GT."""
        tmpl, world = self._tmpl_and_world()
        e = world.entities[0]
        attr = world.active_attrs[0]
        val = e.get(attr)
        if val is None:
            return  # skip if no value
        q = GeneratedQA(
            "q", str(val), "retrieval", [e.name], source_attr=attr)
        assert _construct_and_validate(
            q, tmpl, world, {e.name}, set(), True, 10)

    def test_unavailable_data_returns_false(self):
        tmpl, world = self._tmpl_and_world()
        q = GeneratedQA("q", "100", "retrieval", ["Alice"], source_attr="revenue")
        assert not _construct_and_validate(
            q, tmpl, world, set(), set(), True, 10)

    def test_abstention_validates(self):
        tmpl, world = self._tmpl_and_world()
        q = GeneratedQA("q", "ABSTAIN", "abstention", ["fake"])
        assert _construct_and_validate(
            q, tmpl, world, {e.name for e in world.entities},
            set(), True, len(world.entities))


# ── _smart_guess ──


class TestSmartGuess:
    """Smart guesser internal logic."""

    def test_returns_string_for_retrieval(self):
        from random import Random
        world = TEMPLATES["company"]().generate_world(seed=0, n_entities=10)
        q = GeneratedQA("What are the revenues?", "1234", "retrieval", ["X"])
        guess = _smart_guess(q, world, Random(0))
        assert guess is None or isinstance(guess, str)

    def test_returns_none_for_abstention(self):
        from random import Random
        world = TEMPLATES["company"]().generate_world(seed=0, n_entities=10)
        q = GeneratedQA("q", "ABSTAIN", "abstention", ["fake"])
        assert _smart_guess(q, world, Random(0)) is None


# ── run_validation ──


class TestRunValidation:
    """Validation check logic."""

    def test_determinism_check(self):
        checks = run_validation({}, ["company"])
        assert checks["[company] determinism"] is True

    def test_full_validation_all_pass(self):
        """Run minimal validation with all strategies on one template."""
        from collections import defaultdict
        agg = defaultdict(list)
        tmpl = TEMPLATES["company"]()
        for seed in range(10):
            for s in STRATEGIES:
                result = simulate_one(tmpl, seed=seed, profile=s)
                agg[s["name"]].append(result)
        checks = run_validation(dict(agg), ["company"])
        for check, passed in checks.items():
            assert passed, f"Validation failed: {check}"


# ── result schema ──


class TestResultSchema:
    """Simulation result dict structure."""

    def test_result_has_required_keys(self):
        profile = {"name": "perfect", "store_ratio": 1.0, "applies_updates": True}
        result = simulate_one(TEMPLATES["company"](), seed=0, profile=profile)
        required = {"strategy", "template", "seed", "accuracy", "correct",
                    "total", "stored", "missed", "doc_chars",
                    "by_purpose", "by_competency", "details"}
        assert required <= set(result.keys())


# ── Protocol ──


class TestProtocol:
    """Standard evaluation protocol."""

    def test_tiers_have_required_keys(self):
        for name, tier in TIERS.items():
            for key in ("entities", "questions", "corrections", "write_budget"):
                assert key in tier, f"{name} missing {key}"

    def test_hard_tier_same_budget_more_entities(self):
        assert TIERS["hard"]["entities"] > TIERS["standard"]["entities"]
        assert TIERS["hard"]["write_budget"] == TIERS["standard"]["write_budget"]

    def test_aggregate_results_mean_stderr(self):
        per_seed = [
            {"composite": 0.5, "breadth": 0.6, "maintenance": 0.4,
             "reasoning": 0.5, "efficiency": 0.3,
             "abstention_diagnostic": 0.2},
            {"composite": 0.7, "breadth": 0.8, "maintenance": 0.6,
             "reasoning": 0.7, "efficiency": 0.5,
             "abstention_diagnostic": 0.4},
        ]
        result = aggregate_results(per_seed)
        assert result["composite"]["mean"] == 0.6
        assert result["composite"]["stderr"] > 0
        assert result["breadth"]["mean"] == 0.7

    def test_compute_composite_weights_sum_to_one(self):
        c = compute_composite(1.0, 1.0, 1.0, 1.0)
        assert abs(c - 1.0) < 0.001

    def test_compute_composite_zero(self):
        assert compute_composite(0.0, 0.0, 0.0, 0.0) == 0.0

    def test_eval_scorer_no_crash(self):
        """eval_scorer.py must not crash with valid mocked state (Phase 28 regression)."""
        import asyncio
        from memorygym.worlds.eval_scorer import worldbench_scorer

        class MockStore:
            def __init__(self, data):
                self._d = data
            def get(self, key, default=None):
                return self._d.get(key, default)

        class MockState:
            def __init__(self, store_data):
                self.store = MockStore(store_data)

        scorer_fn = worldbench_scorer(judge_model=None)
        state = MockState({
            "benchmark_answers": [
                {"question": "What is X?", "answer": "42",
                 "ground_truth": "42", "competency": "retrieval",
                 "purpose": "retrieval", "task_id": 0},
                {"question": "What is Y?", "answer": "wrong",
                 "ground_truth": "100", "competency": "retrieval",
                 "purpose": "retrieval", "task_id": 1},
            ],
            "writes_used": 5,
            "n_entities": 30,
            "stored_count": 10,
            "write_budget": 15,
        })
        from inspect_ai.scorer import Target
        result = asyncio.run(scorer_fn(state, Target("dummy")))
        assert result.value["n_questions"] == 2
        assert result.value["n_correct"] == 1
        assert "composite" in result.value
        assert "breadth" in result.value

    def test_official_seeds(self):
        assert OFFICIAL_SEEDS == list(range(10))


# ── CLI ──


class TestCLIOutput:
    """CLI output and JSON format."""

    def test_json_output(self, tmp_path):
        """JSON output has required schema."""
        import json
        from memorygym.bench import main
        outfile = tmp_path / "results.json"
        ret = main(["--seed", "0", "--template", "company",
                     "--strategy", "perfect", "guesser",
                     "-o", str(outfile)])
        assert ret == 0
        data = json.loads(outfile.read_text())
        assert "config" in data
        assert "summary" in data
        assert "per_seed" in data
        assert data["summary"]["perfect"]["accuracy"] == 1.0
        assert data["summary"]["guesser"]["accuracy"] == 0.0

    def test_validate_returns_1_on_failure(self):
        from memorygym.bench import main
        ret = main(["--seed", "0", "--template", "company",
                     "--strategy", "guesser", "--validate"])
        assert ret == 1

    def test_tier_lite_config(self):
        from memorygym.bench import parse_args, _resolve_config
        args = parse_args(["--tier", "lite"])
        entities, questions, corrections, budget = _resolve_config(args)
        assert (entities, questions, corrections, budget) == (30, 10, 3, 15)

    def test_tier_hard_config(self):
        from memorygym.bench import parse_args, _resolve_config
        args = parse_args(["--tier", "hard"])
        entities, questions, corrections, budget = _resolve_config(args)
        assert (entities, questions, corrections, budget) == (120, 40, 10, 30)
