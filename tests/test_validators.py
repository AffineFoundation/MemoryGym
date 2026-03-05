"""Regression tests for AnswerValidator — locks down anti-cheat behavior.

Each test class covers one validation layer. Tests are named after the
attack vector or edge case they prevent from regressing.
"""

from __future__ import annotations

import pytest

from memorybench.evaluation.validators import AnswerValidator, _normalize_entity

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

    def test_negative_not_captured(self):
        """Current regex does not capture sign; absolute value returned."""
        assert V._extract_number("-42") == 42.0


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
