"""Tests for Phase 16 new dtypes and question types.

Verifies:
- New dtype generation (text, enum, list_float, date)
- Correction/contradiction mechanisms for new dtypes
- 6 new question types GT correctness
"""

from __future__ import annotations

import re
from random import Random

from memorygym.worlds.company import CompanyWorld
from memorygym.worlds.research import ResearchWorld
from memorygym.worlds.city import CityWorld
from memorygym.worlds.hospital import HospitalWorld
from memorygym.worlds.sport import SportWorld
from memorygym.worlds.movie import MovieWorld

ALL_TMPLS = [CompanyWorld, ResearchWorld, CityWorld, HospitalWorld, SportWorld, MovieWorld]


def test_new_dtype_generation():
    """All new dtypes generate correct types and valid values."""
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        world = tmpl.generate_world(seed=42, n_entities=10)
        for adef in world.attr_defs:
            if adef.name not in world.active_attrs:
                continue
            for e in world.entities:
                val = e.get(adef.name)
                if val is None:
                    continue
                if adef.dtype == "text":
                    assert isinstance(val, str) and len(val) > 5
                elif adef.dtype == "enum":
                    assert val in adef.choices
                elif adef.dtype == "list_float":
                    assert isinstance(val, list) and len(val) == adef.list_len
                    assert all(isinstance(v, (int, float)) for v in val)
                elif adef.dtype == "date":
                    assert re.match(r"\d{4}-\d{2}-\d{2}", val)
                    year = int(val[:4])
                    assert int(adef.min_val) <= year <= int(adef.max_val)
                # Also verify _format_value works
                fmt = tmpl._format_value(adef.name, val)
                assert isinstance(fmt, str) and len(fmt) > 0


def test_corrections_and_contradictions_new_dtypes():
    """Corrections and contradictions produce valid changed values for all dtypes."""
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        world = tmpl.generate_world(seed=42, n_entities=30)
        corrections = tmpl.generate_corrections(world, Random(42), 10)
        assert corrections, f"{tmpl.name}: no corrections"
        for c in corrections:
            assert c.old_val != c.new_val
            assert world.get_entity(c.entity_name).get(c.attr) == c.new_val

        world2 = tmpl.generate_world(seed=42, n_entities=30)
        contradictions = tmpl.generate_contradictions(world2, Random(42), 5)
        assert contradictions, f"{tmpl.name}: no contradictions"
        for ct in contradictions:
            assert ct.old_val != ct.new_val


def test_temporal_trend_gt():
    """temporal_trend 5-level classification matches slope."""
    valid_answers = {"strongly rising", "slightly rising", "flat",
                     "slightly falling", "strongly falling"}
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        world = tmpl.generate_world(seed=42, n_entities=30)
        rng = Random(42)
        for _ in range(50):
            q = tmpl.gen_question(world, rng, "temporal_trend", world.entities)
            if q is None:
                continue
            assert q.answer in valid_answers, (
                f"{TmplClass.__name__}: unexpected answer '{q.answer}'")
            # Verify direction is consistent with slope sign
            vals = world.get_entity(q.required_entities[0]).get(q.source_attr)
            n = len(vals)
            x_mean = (n - 1) / 2
            y_mean = sum(vals) / n
            num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(vals))
            if "rising" in q.answer:
                assert num > 0, "rising answer but negative slope"
            elif "falling" in q.answer:
                assert num < 0, "falling answer but positive slope"
            break


def test_temporal_extreme_gt():
    """temporal_extreme returns valid 1-indexed period."""
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        world = tmpl.generate_world(seed=42, n_entities=30)
        rng = Random(42)
        for _ in range(50):
            q = tmpl.gen_question(world, rng, "temporal_extreme", world.entities)
            if q is None:
                continue
            period = int(q.answer)
            vals = world.get_entity(q.required_entities[0]).get(q.source_attr)
            assert 1 <= period <= len(vals)
            break


def test_text_match_gt():
    """text_match keyword is found in the entity's text attribute."""
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        world = tmpl.generate_world(seed=42, n_entities=30)
        rng = Random(42)
        for _ in range(100):
            q = tmpl.gen_question(world, rng, "text_match", world.entities)
            if q is None:
                continue
            m = re.search(r'"([^"]+)"', q.question)
            if not m:
                continue
            entity = world.get_entity(q.answer)
            assert entity is not None
            assert m.group(1).lower() in entity.get(q.source_attr).lower()
            break


def test_enum_filter_gt():
    """enum_filter answer is a valid entity name."""
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        world = tmpl.generate_world(seed=42, n_entities=30)
        rng = Random(42)
        for _ in range(100):
            q = tmpl.gen_question(world, rng, "enum_filter", world.entities)
            if q is None:
                continue
            assert world.get_entity(q.answer) is not None
            break


def test_new_question_types_no_placeholder_leak():
    """No question text contains unreplaced {placeholders} or empty answers."""
    for TmplClass in ALL_TMPLS:
        tmpl = TmplClass()
        world = tmpl.generate_world(seed=42, n_entities=30)
        rng = Random(42)
        for comp in ["temporal_trend", "temporal_extreme", "text_match",
                     "enum_filter"]:
            for _ in range(50):
                q = tmpl.gen_question(world, rng, comp, world.entities)
                if q is None:
                    continue
                assert "{" not in q.question, f"{tmpl.name}/{comp}: {q.question}"
                assert q.answer
                break
