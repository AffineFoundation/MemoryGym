"""Answer validators: layered matching for LLM-generated answers."""

from __future__ import annotations

import re
from typing import Any

# Titles/prefixes to strip before word-level matching
_TITLE_PREFIXES = re.compile(
    r"^(dr|mr|mrs|ms|prof|sr|jr)\.?\s+", re.IGNORECASE
)
# Parenthetical suffixes to strip (e.g., "(PhD)", "(Division A)")
_PAREN_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")


def resolve_entity_name(name: str, known_names: set[str]) -> str:
    """Resolve a possibly multi-word entity name against known entities.

    Handles names like "Dr. Kelen Frostwick" or "Apex Controller" by
    checking against the known entity set rather than naively splitting.
    """
    for known in known_names:
        if name.startswith(known) or known.startswith(name):
            return known
    return name


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
                              "ratio", "delta"):
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

        Suffix disambiguation (K/M ambiguity) is deferred to LLM judge
        for real evaluations. Rule-based path uses single interpretation
        with K/M always applied as multipliers.
        """
        try:
            gt_num = float(gt) if not isinstance(gt, (int, float)) else gt
            is_int_gt = isinstance(gt, int) or (isinstance(gt, str) and '.' not in gt)

            ans_num = self._extract_number(answer)
            if is_int_gt:
                return int(round(ans_num)) == int(round(gt_num))
            else:
                if gt_num == 0:
                    return ans_num == 0
                return abs(ans_num - gt_num) / abs(gt_num) <= self._TOL_FLOAT
        except (ValueError, ZeroDivisionError):
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

    def _extract_number(self, text: str) -> float:
        """Extract a number from text. Handles $, K, M, commas.

        Always applies suffix multiplier (K=×1000, M=×10^6).
        """
        text = text.replace(",", "").replace("$", "").strip()
        match = re.search(r"(\d[\d]*\.?\d*)\s*([KkMm])?", text)
        if not match:
            raise ValueError(f"No number found in: {text}")
        num = float(match.group(1))
        suffix = (match.group(2) or "").upper()
        if suffix == "K":
            num *= 1000
        elif suffix == "M":
            num *= 1_000_000
        return num
