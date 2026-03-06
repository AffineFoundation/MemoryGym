"""Regression tests for AnswerValidator — locks down anti-cheat behavior.

Each test class covers one validation layer. Tests are named after the
attack vector or edge case they prevent from regressing.
"""

from __future__ import annotations

import pytest

from memorybench.evaluation.validators import (
    AnswerValidator, _normalize_entity, validate_with_fallback,
)

V = AnswerValidator()


# ── _extract_number ──


class TestExtractNumber:
    """Ensure number extraction handles edge cases correctly."""

    def test_plain_integer(self):
        assert V._extract_number("42") == 42.0

    def test_decimal(self):
        assert V._extract_number("42.5") == 42.5

    def test_with_dollar_sign(self):
        assert V._extract_number("$42,000") == 42000.0

    def test_with_commas(self):
        assert V._extract_number("1,234,567") == 1234567.0

    def test_suffix_k(self):
        assert V._extract_number("10K") == 10000.0

    def test_suffix_m(self):
        assert V._extract_number("2.5M") == 2500000.0

    def test_suffix_lowercase_k(self):
        assert V._extract_number("50k") == 50000.0

    def test_dr_period_no_match(self):
        """Bug #1 regression: 'Dr.' must NOT extract a number."""
        with pytest.raises(ValueError):
            V._extract_number("Dr.")

    def test_title_prefix_no_match(self):
        with pytest.raises(ValueError):
            V._extract_number("Dr. Smith")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            V._extract_number("")

    def test_no_digits(self):
        with pytest.raises(ValueError):
            V._extract_number("no numbers here")

    def test_entity_name_with_number(self):
        assert V._extract_number("Agent 47") == 47.0

    def test_first_number_extracted(self):
        """_extract_number returns the first number found."""
        assert V._extract_number("3 items, salary $50,000") == 3.0

    def test_negative_captured(self):
        """Negative sign is captured for temperature and similar values."""
        assert V._extract_number("-42") == -42.0

    def test_negative_decimal(self):
        assert V._extract_number("-6.45") == -6.45

    def test_negative_with_unit_suffix(self):
        """Negative with non-K/M trailing chars (°C) — suffix ignored."""
        assert V._extract_number("-6.5°C") == -6.5

    def test_negative_match_float(self):
        """Negative float GT: -6.5 vs -6.45 within 2% tolerance."""
        assert V._numeric_match("-6.5", "-6.45")

    def test_negative_wrong_sign_fails(self):
        """Positive answer vs negative GT must fail."""
        assert not V._numeric_match("6.5", "-6.45")


# ── _entity_match ──


class TestEntityMatch:
    """Word-overlap entity matching with title stripping."""

    def test_exact_name(self):
        assert V._entity_match("Kelan Frostwick", "Kelan Frostwick")

    def test_with_title_in_gt(self):
        """GT has title 'Dr.' — should still match answer without title."""
        assert V._entity_match("Kelan Frostwick", "Dr. Kelan Frostwick")

    def test_with_title_in_answer(self):
        assert V._entity_match("Dr. Kelan Frostwick", "Kelan Frostwick")

    def test_partial_name_rejected(self):
        """'Frostwick' = 1/2 words of 'Kelan Frostwick' = 50% < 67% → reject."""
        assert not V._entity_match("Frostwick", "Kelan Frostwick")

    def test_single_title_rejected(self):
        """Bug #1 vector: 'Dr.' alone must NOT match 'Dr. Kelan Frostwick'.
        After stripping 'Dr.', the answer is empty → fails."""
        assert not V._entity_match("Dr.", "Dr. Kelan Frostwick")

    def test_wrong_name_rejected(self):
        assert not V._entity_match("Smith Jones", "Kelan Frostwick")

    def test_too_short_rejected(self):
        """Answer shorter than 50% of GT length → rejected."""
        assert not V._entity_match("K", "Kelan Frostwick")

    def test_case_insensitive(self):
        assert V._entity_match("kelan frostwick", "KELAN FROSTWICK")

    def test_parenthetical_stripped(self):
        """Parenthetical suffixes in GT are stripped before matching."""
        assert V._entity_match("Apex Controller", "Apex Controller (Division A)")

    def test_no_overlap(self):
        assert not V._entity_match("Alpha Beta", "Gamma Delta")


# ── _synthesis_match ──


class TestSynthesisMatch:
    """Synthesis/cross_domain: entity name + numeric value required."""

    def test_exact_gt_format(self):
        """GT format 'Name (value)' with exact answer passes via exact match."""
        assert V.validate(
            "Kelan Frostwick (145000)",
            "Kelan Frostwick (145000)",
            "synthesis",
        )

    def test_natural_language_answer(self):
        """LLM-style answer with entity name and exact value."""
        assert V._synthesis_match(
            "Kelan Frostwick earns $145,000",
            "Kelan Frostwick (145000)",
        )

    def test_entity_only_rejected(self):
        """Guesser attack: entity name without numeric value → reject."""
        assert not V._synthesis_match(
            "Kelan Frostwick",
            "Kelan Frostwick (145000)",
        )

    def test_number_only_rejected(self):
        """Guesser attack: random number without entity name → reject."""
        assert not V._synthesis_match(
            "47382",
            "Kelan Frostwick (145000)",
        )

    def test_wrong_entity_rejected(self):
        assert not V._synthesis_match(
            "Smith Jones earns $145,000",
            "Kelan Frostwick (145000)",
        )

    def test_wrong_value_rejected(self):
        """Correct entity but value outside 5% tolerance → reject."""
        assert not V._synthesis_match(
            "Frostwick earns $200,000",
            "Kelan Frostwick (145000)",
        )

    def test_value_within_tolerance_float(self):
        """Float GT: 2% tolerance applies. 145000.0 × 1.01 = 146450."""
        assert V._synthesis_match(
            "Kelan Frostwick earns $146,000",
            "Kelan Frostwick (145000.0)",
        )

    def test_integer_value_exact_required(self):
        """V14: Integer GT in synthesis requires exact numeric match."""
        assert not V._synthesis_match(
            "Kelan Frostwick earns $150,000",
            "Kelan Frostwick (145000)",
        )

    def test_abstention_on_synthesis_rejected(self):
        """Guesser abstention phrase on synthesis question → reject."""
        assert not V._synthesis_match(
            "I don't have enough information",
            "Kelan Frostwick (145000)",
        )

    def test_no_paren_in_gt_fallback(self):
        """If GT has no parenthetical value, fall back to entity match."""
        assert V._synthesis_match("Kelan Frostwick", "Kelan Frostwick")


# ── _abstention_match ──


class TestAbstentionMatch:
    """Abstention detection: refusal phrase + no numeric guess."""

    def test_clean_refusal(self):
        assert V._abstention_match("I don't know")

    def test_standard_abstention(self):
        assert V._abstention_match("I don't have enough information")

    def test_unknown(self):
        assert V._abstention_match("Unknown")

    def test_hedged_guess_rejected(self):
        """Bug #2 regression: refusal + number → NOT abstention."""
        assert not V._abstention_match("Unknown, but I guess 50")

    def test_number_with_refusal_rejected(self):
        assert not V._abstention_match("I don't know, maybe 42")

    def test_pure_number_rejected(self):
        """No refusal phrase → not abstention."""
        assert not V._abstention_match("47382")

    def test_entity_name_rejected(self):
        assert not V._abstention_match("Kelan Frostwick")

    def test_confident_answer_rejected(self):
        assert not V._abstention_match("The answer is definitely 100")


# ── validate() integration ──


class TestValidateIntegration:
    """End-to-end validation covering guesser attack vectors."""

    # Guesser attack: random int on retrieval
    def test_guesser_random_int_on_retrieval(self):
        assert not V.validate("47382", "50000", "retrieval")

    # Guesser attack: random int that happens to be close
    def test_guesser_lucky_number_on_retrieval(self):
        """Even if guesser number is within 5%, it passes — this is by design.
        The probability is ~0.01%, so it doesn't affect the <5% threshold."""
        assert V.validate("50000", "50000", "retrieval")

    # Guesser attack: entity name on synthesis
    def test_guesser_entity_on_synthesis(self):
        assert not V.validate(
            "Kelan Frostwick", "Kelan Frostwick (145000)", "synthesis"
        )

    # Guesser attack: random int on synthesis
    def test_guesser_int_on_synthesis(self):
        assert not V.validate("47382", "Kelan Frostwick (145000)", "synthesis")

    # Guesser attack: abstention on trick retrieval
    def test_guesser_abstention_on_retrieval(self):
        """Trick retrieval: question phrased like abstention but GT is numeric."""
        assert not V.validate(
            "I don't have enough information", "50000", "retrieval"
        )

    # Guesser attack: abstention on non-abstention
    def test_guesser_abstention_on_synthesis(self):
        assert not V.validate(
            "I don't have enough information",
            "Kelan Frostwick (145000)",
            "synthesis",
        )

    # Legitimate answers
    def test_legitimate_retrieval_exact(self):
        assert V.validate("50000", "50000", "retrieval")

    def test_legitimate_retrieval_formatted(self):
        assert V.validate("$50,000", "50000", "retrieval")

    def test_legitimate_retrieval_with_k(self):
        assert V.validate("50K", "50000", "retrieval")

    def test_legitimate_synthesis(self):
        assert V.validate(
            "Kelan Frostwick (145000)",
            "Kelan Frostwick (145000)",
            "synthesis",
        )

    def test_legitimate_abstention(self):
        assert V.validate(
            "I don't have enough information", "ABSTAIN", "abstention"
        )

    def test_legitimate_update(self):
        assert V.validate("55", "55", "update")

    def test_legitimate_cross_domain(self):
        assert V.validate(
            "Alice Chen (85000)", "Alice Chen (85000)", "cross_domain"
        )


# ── _normalize_entity ──


class TestNormalizeEntity:
    """Title and parenthetical stripping."""

    def test_strip_dr(self):
        assert _normalize_entity("Dr. Kelan Frostwick") == "Kelan Frostwick"

    def test_strip_prof(self):
        assert _normalize_entity("Prof. Smith") == "Smith"

    def test_strip_parenthetical(self):
        assert _normalize_entity("Apex Controller (Division A)") == "Apex Controller"

    def test_strip_both(self):
        assert _normalize_entity("Dr. Smith (PhD)") == "Smith"

    def test_no_strip_needed(self):
        assert _normalize_entity("Kelan Frostwick") == "Kelan Frostwick"

    def test_title_without_name_preserved(self):
        """'Dr.' alone → NOT stripped (regex requires trailing space + name)."""
        result = _normalize_entity("Dr.")
        assert result == "Dr."


# ── K/M suffix handling ──


class TestKMSuffixHandling:
    """K/M as decorative labels vs multipliers — both interpretations tried."""

    def test_m_label_on_retrieval(self):
        """Agent copies display format '$498,985.9M' — M is a label, not ×10^6."""
        assert V.validate("$498,985.9M", "498985.9", "retrieval")

    def test_m_multiplier_on_retrieval(self):
        """Agent uses M as multiplier: '2.5M' means 2,500,000."""
        assert V.validate("2.5M", "2500000", "retrieval")

    def test_k_label_on_retrieval(self):
        """Agent copies display format '150K' where GT is 150000."""
        assert V.validate("150K", "150000", "retrieval")

    def test_k_label_raw_on_retrieval(self):
        """Agent writes '150K' but GT is raw 150 (K is label)."""
        assert V.validate("150K", "150", "retrieval")

    def test_m_label_float_gt(self):
        """Float GT with M-label answer within 2% tolerance."""
        assert V.validate("$1,234.5M", "1234.5", "retrieval")

    def test_m_label_integer_gt(self):
        """Integer GT with M-label answer — exact match on raw digits."""
        assert V.validate("$1987M", "1987", "retrieval")

    def test_no_suffix_unchanged(self):
        """Plain number without suffix — behavior unchanged."""
        assert V.validate("498985.9", "498985.9", "retrieval")
        assert V.validate("498986", "498985.9", "retrieval")  # ~0% off float

    def test_guesser_still_fails(self):
        """K/M suffix doesn't help guesser: wrong number is still wrong."""
        assert not V.validate("$999,999.9M", "498985.9", "retrieval")
        assert not V.validate("100K", "498985.9", "retrieval")

    def test_extract_number_apply_suffix_false(self):
        """apply_suffix=False ignores K/M."""
        assert V._extract_number("2.5M", apply_suffix=False) == 2.5
        assert V._extract_number("50K", apply_suffix=False) == 50.0

    def test_extract_number_apply_suffix_true(self):
        """apply_suffix=True applies K/M (default behavior)."""
        assert V._extract_number("2.5M", apply_suffix=True) == 2500000.0
        assert V._extract_number("50K", apply_suffix=True) == 50000.0


# ── validate_with_fallback ──


class TestValidateWithFallback:
    """Rule-first, judge-fallback pipeline."""

    def test_rule_pass_skips_judge(self):
        """If rule passes, judge is never called."""
        calls = []
        def spy_judge(q, gt, ans, comp):
            calls.append(1)
            return True, "judge"
        ok, reason = validate_with_fallback(
            "50000", "50000", "retrieval", judge_fn=spy_judge)
        assert ok
        assert reason == "rule:pass"
        assert len(calls) == 0

    def test_rule_fail_calls_judge(self):
        """If rule fails, judge is consulted."""
        def fake_judge(q, gt, ans, comp):
            return True, "format_variant"
        ok, reason = validate_with_fallback(
            "about fifty thousand", "50000", "retrieval",
            question="What is X?", judge_fn=fake_judge)
        assert ok
        assert "judge:" in reason

    def test_judge_fail_closed(self):
        """Judge exception → fail closed (INCORRECT)."""
        def broken_judge(q, gt, ans, comp):
            raise RuntimeError("API down")
        ok, reason = validate_with_fallback(
            "about fifty thousand", "50000", "retrieval",
            judge_fn=broken_judge)
        assert not ok
        assert "failed" in reason

    def test_no_judge_rule_only(self):
        """Without judge, pure rule-based."""
        ok, reason = validate_with_fallback("50000", "50000", "retrieval")
        assert ok
        assert reason == "rule:pass"

        ok, reason = validate_with_fallback("wrong", "50000", "retrieval")
        assert not ok
        assert reason == "rule:fail"

    def test_abstention_always_rule(self):
        """Abstention never calls judge (V10 authoritative)."""
        calls = []
        def spy_judge(q, gt, ans, comp):
            calls.append(1)
            return True, "judge"
        ok, _ = validate_with_fallback(
            "I don't know", "ABSTAIN", "abstention", judge_fn=spy_judge)
        assert ok
        assert len(calls) == 0

    def test_km_label_passes_rule(self):
        """K/M label fix means rule handles it — no judge needed."""
        calls = []
        def spy_judge(q, gt, ans, comp):
            calls.append(1)
            return True, "judge"
        ok, reason = validate_with_fallback(
            "$498,985.9M", "498985.9", "retrieval", judge_fn=spy_judge)
        assert ok
        assert reason == "rule:pass"
        assert len(calls) == 0
