"""Tests for bench.py simulation logic.

Validates the simulation engine produces correct results for
each strategy, and that the validation checks are comprehensive.
"""

from __future__ import annotations

from memorybench.bench import (
    STRATEGIES,
    TEMPLATES,
    _can_answer,
    _smart_guess,
    _VALIDATOR,
    run_validation,
    simulate_one,
    simulate_one_stream,
)
from memorybench.worlds.base import GeneratedQA


# ── simulate_one ──


class TestSimulateOne:
    """Core simulation produces correct results."""

    def test_perfect_100_pct(self):
        profile = {"name": "perfect", "store_ratio": 1.0, "applies_updates": True}
        for name, cls in TEMPLATES.items():
            result = simulate_one(cls(), seed=0, profile=profile)
            assert result["accuracy"] == 1.0, f"{name} perfect != 100%"

    def test_guesser_0_pct(self):
        profile = {"name": "guesser", "store_ratio": 0.0, "applies_updates": False}
        for name, cls in TEMPLATES.items():
            result = simulate_one(cls(), seed=0, profile=profile)
            assert result["accuracy"] == 0.0, f"{name} guesser != 0%"

    def test_strategic_gt_naive(self):
        strat = {"name": "strategic", "store_ratio": 0.7, "applies_updates": True}
        naive = {"name": "naive", "store_ratio": 0.4, "applies_updates": False}
        for name, cls in TEMPLATES.items():
            s = simulate_one(cls(), seed=0, profile=strat)
            n = simulate_one(cls(), seed=0, profile=naive)
            assert s["accuracy"] > n["accuracy"], (
                f"{name}: strategic {s['accuracy']:.0%} <= naive {n['accuracy']:.0%}")

    def test_result_has_required_keys(self):
        profile = {"name": "perfect", "store_ratio": 1.0, "applies_updates": True}
        result = simulate_one(TEMPLATES["company"](), seed=0, profile=profile)
        required = {"strategy", "template", "seed", "accuracy", "correct",
                    "total", "stored", "missed", "doc_chars",
                    "by_purpose", "by_competency", "details"}
        assert required <= set(result.keys())

    def test_determinism(self):
        profile = {"name": "strategic", "store_ratio": 0.7, "applies_updates": True}
        r1 = simulate_one(TEMPLATES["company"](), seed=42, profile=profile)
        r2 = simulate_one(TEMPLATES["company"](), seed=42, profile=profile)
        assert r1["accuracy"] == r2["accuracy"]
        assert r1["details"] == r2["details"]


# ── simulate_one_stream ──


class TestSimulateOneStream:
    """Stream simulation mode."""

    def test_perfect_stream(self):
        profile = {"name": "perfect", "store_ratio": 1.0, "applies_updates": True}
        result = simulate_one_stream(TEMPLATES["company"](), seed=0, profile=profile)
        assert result["accuracy"] == 1.0

    def test_guesser_stream(self):
        profile = {"name": "guesser", "store_ratio": 0.0, "applies_updates": False}
        result = simulate_one_stream(TEMPLATES["company"](), seed=0, profile=profile)
        assert result["accuracy"] == 0.0


# ── _can_answer ──


class TestCanAnswer:
    """Binary answer prediction logic."""

    def test_abstention_needs_coverage(self):
        q = GeneratedQA("q", "ABSTAIN", "abstention", ["fake_name"])
        assert _can_answer(q, {"a", "b", "c"}, set(), True, 5)
        assert not _can_answer(q, {"a"}, set(), True, 5)

    def test_update_needs_applied(self):
        q = GeneratedQA("q", "100", "update", ["Alice"])
        assert _can_answer(q, {"Alice"}, {"Alice"}, True, 10)
        assert not _can_answer(q, {"Alice"}, set(), True, 10)
        assert not _can_answer(q, {"Alice"}, {"Alice"}, False, 10)

    def test_retrieval_needs_entity(self):
        q = GeneratedQA("q", "100", "retrieval", ["Alice"])
        assert _can_answer(q, {"Alice"}, set(), True, 10)
        assert not _can_answer(q, set(), set(), True, 10)

    def test_always_abstain(self):
        q_abs = GeneratedQA("q", "ABSTAIN", "abstention", ["fake"])
        q_ret = GeneratedQA("q", "100", "retrieval", ["Alice"])
        assert _can_answer(q_abs, {"Alice"}, set(), True, 10,
                           always_abstain=True)
        assert not _can_answer(q_ret, {"Alice"}, set(), True, 10,
                               always_abstain=True)


# ── _smart_guess ──


class TestSmartGuess:
    """Smart guesser produces plausible but incorrect answers."""

    def test_returns_string_for_retrieval(self):
        from random import Random
        world = TEMPLATES["company"]().generate_world(seed=0, n_entities=10)
        q = GeneratedQA("What are the revenues?", "1234", "retrieval", ["X"])
        guess = _smart_guess(q, world, Random(0))
        # May or may not find attribute, but should return something
        assert guess is None or isinstance(guess, str)

    def test_returns_none_for_abstention(self):
        from random import Random
        world = TEMPLATES["company"]().generate_world(seed=0, n_entities=10)
        q = GeneratedQA("q", "ABSTAIN", "abstention", ["fake"])
        assert _smart_guess(q, world, Random(0)) is None

    def test_guess_fails_validation(self):
        """Smart guesses should almost never pass validation."""
        from random import Random
        tmpl = TEMPLATES["company"]()
        world = tmpl.generate_world(seed=0, n_entities=60)
        rng = Random(7777)
        corrections = tmpl.generate_corrections(world, Random(3333), 5)
        qs = tmpl.gen_adaptive_questions(
            world, rng, world.entities, set(), 20, corrections)
        guess_rng = Random(9999)
        passes = sum(
            1 for q in qs
            if (g := _smart_guess(q, world, guess_rng))
            and _VALIDATOR.validate(g, q.answer, q.competency)
        )
        assert passes <= 1, f"Smart guesser passed {passes}/20"


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
        for s in STRATEGIES:
            result = simulate_one(tmpl, seed=0, profile=s)
            agg[s["name"]].append(result)
        checks = run_validation(dict(agg), ["company"])
        for check, passed in checks.items():
            assert passed, f"Validation failed: {check}"


class TestCLIOutput:
    """CLI output and JSON format."""

    def test_json_output(self, tmp_path):
        """JSON output has required schema."""
        import json
        from memorybench.bench import main
        outfile = tmp_path / "results.json"
        ret = main(["--seed", "0", "--template", "company",
                     "--strategy", "perfect", "guesser",
                     "-o", str(outfile)])
        assert ret == 0
        data = json.loads(outfile.read_text())
        assert "config" in data
        assert "summary" in data
        assert "per_seed" in data
        assert "perfect" in data["summary"]
        assert "guesser" in data["summary"]
        assert data["summary"]["perfect"]["accuracy"] == 1.0
        assert data["summary"]["guesser"]["accuracy"] == 0.0

    def test_validate_returns_1_on_failure(self):
        """Validation with missing strategies returns exit code 1."""
        from memorybench.bench import main
        ret = main(["--seed", "0", "--template", "company",
                     "--strategy", "guesser", "--validate"])
        assert ret == 1  # fails because perfect/strategic/naive missing
