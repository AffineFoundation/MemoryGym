"""Answer validators: layered matching for LLM-generated answers."""

from __future__ import annotations

import re
from typing import Any, Callable

# Titles/prefixes to strip before word-level matching
_TITLE_PREFIXES = re.compile(
    r"^(dr|mr|mrs|ms|prof|sr|jr)\.?\s+", re.IGNORECASE
)
# Parenthetical suffixes to strip (e.g., "(PhD)", "(Division A)")
_PAREN_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")


def _normalize_entity(name: str) -> str:
    """Strip titles and parenthetical suffixes from an entity name."""
    name = _PAREN_SUFFIX.sub("", name)
    name = _TITLE_PREFIXES.sub("", name)
    return name.strip()


def _tokenize(text: str) -> list[str]:
    """Lowercase tokenize, keeping only alphanumeric words."""
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w]


class AnswerValidator:
    """4-layer answer matching: exact → numeric → synthesis → abstention."""

    # V14: Integer-exact, float-tolerant matching.
    # - Integer GT: exact match only. Years, counts, employees are integers
    #   and the agent should return the precise value. This completely
    #   prevents year/count guessing attacks.
    # - Float GT: 2% relative tolerance. Handles display rounding
    #   ($1,234.5M → 1234.5 or 1235) and aggregation imprecision.
    _TOL_FLOAT = 0.02  # 2% relative tolerance for floats only

    def validate(self, answer: str, ground_truth: Any,
                 question_type: str) -> bool:
        answer = str(answer).strip()
        gt = str(ground_truth).strip()

        if answer.lower() == gt.lower():
            return True

        if question_type in ("retrieval", "update", "aggregation",
                              "cross_category", "ratio", "delta",
                              "relationship_hop", "relationship_chain"):
            if self._numeric_match(answer, ground_truth):
                return True

        if question_type in ("synthesis", "cross_domain", "conditional",
                              "comparison", "multi_hop", "outlier"):
            if self._synthesis_match(answer, gt):
                return True

        if question_type == "abstention":
            return self._abstention_match(answer)

        return False

    def _numeric_match(self, answer: str, gt: Any) -> bool:
        """Match answer against ground truth numerically.

        V14: Integer-exact, float-tolerant.
        - Integer GT (years, counts, employees): exact match required.
          Completely prevents guessing attacks on year ranges.
        - Float GT (revenue, percentages, rates): 2% relative tolerance.
          Handles display rounding and aggregation imprecision.

        Suffix disambiguation: tries both with and without K/M multiplier.
        Domain values already in millions (e.g. revenue_m=498985.9) display
        as "$498,985.9M" — the M is a label, not a multiplier. Trying both
        interpretations lets the rule-based path handle this correctly.
        """
        try:
            gt_num = float(gt) if not isinstance(gt, (int, float)) else gt
            is_int_gt = isinstance(gt, int) or (isinstance(gt, str) and '.' not in gt)
        except (ValueError, TypeError):
            # GT may be formatted (e.g. "$34,620.4M") — extract number
            try:
                gt_num = self._extract_number(str(gt), apply_suffix=False)
                is_int_gt = '.' not in str(gt)
            except ValueError:
                return False

        for apply_suffix in (True, False):
            try:
                ans_num = self._extract_number(answer, apply_suffix=apply_suffix)
                if is_int_gt:
                    if int(round(ans_num)) == int(round(gt_num)):
                        return True
                else:
                    if gt_num == 0:
                        if ans_num == 0:
                            return True
                    elif abs(ans_num - gt_num) / abs(gt_num) <= self._TOL_FLOAT:
                        return True
            except ValueError:
                continue
        return False

    def _entity_match(self, answer: str, gt: str) -> bool:
        """Word-overlap entity match: ≥67% of GT keywords in answer.

        Strips titles (Dr., Prof.) and parenthetical content before matching.
        Answer must be at least 50% the length of GT to prevent single-word tricks.
        """
        gt_norm = _normalize_entity(gt)
        ans_norm = _normalize_entity(answer)

        gt_words = _tokenize(gt_norm)
        if not gt_words:
            return ans_norm.lower() == gt_norm.lower()

        # Length guard: answer too short → reject
        if len(ans_norm) < len(gt_norm) * 0.5:
            return False

        ans_words = set(_tokenize(ans_norm))
        overlap = sum(1 for w in gt_words if w in ans_words)
        return overlap / len(gt_words) >= 0.67

    def _synthesis_match(self, answer: str, gt: str) -> bool:
        """Entity name + numeric value match.

        GT format: "EntityName (value)" — requires BOTH entity name match
        AND numeric value within adaptive tolerance.
        Falls back to entity_match if GT has no parenthetical value.
        """
        paren_match = re.search(r"^(.+?)\s*\(([^)]+)\)\s*$", gt)
        if not paren_match:
            return self._entity_match(answer, gt)

        gt_entity = paren_match.group(1).strip()
        gt_value_str = paren_match.group(2).strip()

        if not self._entity_match(answer, gt_entity):
            return False

        # Reuse _numeric_match for consistent adaptive tolerance
        return self._numeric_match(answer, gt_value_str)

    def _abstention_match(self, answer: str) -> bool:
        """Detect refusal/abstention signals.

        Must contain a refusal phrase AND not contain a numeric guess.
        "Unknown, but I guess 50" → has number → NOT abstention.

        V10: This is the sole authority for abstention (judge skipped),
        so pattern coverage must be comprehensive.
        """
        refusal_patterns = [
            "abstain", "don't know", "dont know", "do not know",
            "not available", "no information", "no data",
            "cannot determine", "can't determine",
            "insufficient data", "not mentioned",
            "no record", "not found", "no such",
            "unknown", "n/a",
            "i don't have", "i dont have",
            "could not find", "couldn't find",
            "no matching", "does not exist", "doesn't exist",
        ]
        a = answer.lower()
        has_refusal = any(p in a for p in refusal_patterns)
        if not has_refusal:
            return False
        # Reject if answer also contains a numeric value (hedged guess)
        has_number = bool(re.search(r"\d", a))
        return not has_number

    def _extract_number(self, text: str, apply_suffix: bool = True) -> float:
        """Extract a number from text. Handles $, K, M, commas.

        When apply_suffix=True, K/M are multipliers (K=×1000, M=×10^6).
        When apply_suffix=False, K/M are ignored (decorative labels).
        """
        text = text.replace(",", "").replace("$", "").strip()
        match = re.search(r"(-?\d[\d]*\.?\d*)\s*([KkMm])?", text)
        if not match:
            raise ValueError(f"No number found in: {text}")
        num = float(match.group(1))
        if apply_suffix:
            suffix = (match.group(2) or "").upper()
            if suffix == "K":
                num *= 1000
            elif suffix == "M":
                num *= 1_000_000
        return num


# ── Unified validation pipeline ──

_VALIDATOR = AnswerValidator()


def validate_with_fallback(
    answer: str,
    ground_truth: str,
    competency: str,
    question: str = "",
    judge_fn: Callable[[str, str, str, str], tuple[bool, str]] | None = None,
) -> tuple[bool, str]:
    """Rule-first, judge-fallback validation.

    1. Abstention → always rule-based (V10 authoritative).
    2. Rule-based pass → accept immediately (no judge call).
    3. Rule-based fail + judge available → ask judge.
    4. Judge failure → fail closed (INCORRECT).

    This saves judge API calls on exact/numeric matches while still
    catching format variants that only a judge can understand.

    Args:
        judge_fn: Callable(question, ground_truth, answer, competency)
                  → (is_correct, reason). None = rules only.
    """
    if competency == "abstention":
        return _VALIDATOR.validate(answer, ground_truth, competency), "rule:abstention"

    if _VALIDATOR.validate(answer, ground_truth, competency):
        return True, "rule:pass"

    if judge_fn is not None:
        try:
            ok, reason = judge_fn(question, ground_truth, answer, competency)
            return ok, f"judge:{reason}"
        except (RuntimeError, ConnectionError, TimeoutError, ValueError) as exc:
            return False, f"judge:failed({exc})"

    return False, "rule:fail"


async def async_validate_with_fallback(
    answer: str,
    ground_truth: str,
    competency: str,
    question: str = "",
    judge_fn: Callable | None = None,
) -> tuple[bool, str]:
    """Async version of validate_with_fallback.

    Same logic as validate_with_fallback but awaits the judge_fn.
    Use this in async contexts (e.g., Inspect AI scorer).
    """
    if competency == "abstention":
        return _VALIDATOR.validate(answer, ground_truth, competency), "rule:abstention"

    if _VALIDATOR.validate(answer, ground_truth, competency):
        return True, "rule:pass"

    if judge_fn is not None:
        try:
            ok, reason = await judge_fn(question, ground_truth, answer, competency)
            return ok, f"judge:{reason}"
        except (RuntimeError, ConnectionError, TimeoutError, ValueError) as exc:
            return False, f"judge:failed({exc})"

    return False, "rule:fail"
