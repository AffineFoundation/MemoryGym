"""Verify all 20 REASONING_COMPETENCIES can be generated.

Catches missing generators or overly strict preconditions that prevent
a competency type from ever being produced.
"""

from __future__ import annotations

from collections import defaultdict
from random import Random

import pytest

from memorygym.protocol import REASONING_COMPETENCIES
from memorygym.simulation import TEMPLATES


def _make_world_with_corrections(tmpl_cls, seed, n_entities=60):
    """Create a world with corrections for testing question generation."""
    tmpl = tmpl_cls()
    world = tmpl.generate_world(seed=seed, n_entities=n_entities, eval_salt=1)
    rng_c = Random(seed + 3333)
    corrections = tmpl.generate_corrections(world, rng_c, 5)
    return tmpl, world, corrections


class TestReasoningCompetencyCoverage:
    """Every REASONING_COMPETENCIES type must be registered and generatable."""

    def test_all_competencies_in_dispatch_table(self):
        """gen_question() dispatch table covers all 20 reasoning types."""
        tmpl = list(TEMPLATES.values())[0]()
        # gen_question dispatches via dict + special cases
        # We check that calling each competency doesn't return "unknown"
        world = tmpl.generate_world(seed=0, n_entities=60, eval_salt=1)
        rng = Random(0 + 3333)
        corrections = tmpl.generate_corrections(world, rng, 5)
        available = list(world.entities)

        for comp in REASONING_COMPETENCIES:
            # Just verify no KeyError / unhandled competency
            # Result may be None if preconditions not met, that's OK
            rng_q = Random(42)
            tmpl.gen_question(world, rng_q, comp, available, corrections)

    @pytest.mark.parametrize("comp", REASONING_COMPETENCIES)
    def test_competency_generates_at_least_once(self, comp: str):
        """Each competency type succeeds in at least 1 of 10 seeds × 6 templates."""
        generated = False
        for tmpl_name, tmpl_cls in TEMPLATES.items():
            if generated:
                break
            for seed in range(10):
                tmpl, world, corrections = _make_world_with_corrections(
                    tmpl_cls, seed)
                available = list(world.entities)
                rng_q = Random(seed + 7777)
                q = tmpl.gen_question(
                    world, rng_q, comp, available, corrections)
                if q is not None:
                    assert q.competency == comp, \
                        f"Expected competency={comp}, got {q.competency}"
                    generated = True
                    break
        assert generated, \
            f"Competency '{comp}' never generated across 10 seeds × 6 templates"

    def test_adaptive_questions_cover_most_competencies(self):
        """gen_adaptive_questions() produces ≥15 of 20 reasoning types."""
        all_competencies: set[str] = set()
        for tmpl_cls in TEMPLATES.values():
            for seed in range(5):
                tmpl, world, corrections = _make_world_with_corrections(
                    tmpl_cls, seed)
                rng_contra = Random(seed + 7373)
                contradictions = tmpl.generate_contradictions(
                    world, rng_contra, 2)
                stored_names = {e.name for e in world.entities}
                rng_q = Random(seed + 7777)
                questions = tmpl.gen_adaptive_questions(
                    world, rng_q, world.entities, stored_names, 30,
                    corrections, contradictions,
                )
                for q in questions:
                    if q.competency in REASONING_COMPETENCIES:
                        all_competencies.add(q.competency)

        missing = set(REASONING_COMPETENCIES) - all_competencies
        assert len(all_competencies) >= 15, \
            f"Only {len(all_competencies)}/20 competencies generated. " \
            f"Missing: {missing}"
