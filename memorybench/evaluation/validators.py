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
    """5-layer answer matching: exact → numeric → synthesis → entity → abstention."""

    def validate(self, answer: str, ground_truth: Any,
                 question_type: str) -> bool:
        answer = str(answer).strip()
        gt = str(ground_truth).strip()

        # Layer 1: exact match
        if self._exact_match(answer, gt):
            return True

        # Layer 2: numeric tolerance (retrieval, update)
        if question_type in ("retrieval", "update"):
            if self._numeric_match(answer, ground_truth, tolerance=0.05):
                return True

        # Layer 3: synthesis/cross_domain — entity name + numeric value
        if question_type in ("synthesis", "cross_domain"):
            if self._synthesis_match(answer, gt):
                return True

        # Layer 4: abstention detection
        if question_type == "abstention":
            return self._abstention_match(answer)

        return False

    def _exact_match(self, answer: str, gt: str) -> bool:
        return answer.lower() == gt.lower()

    def _numeric_match(self, answer: str, gt: Any,
                       tolerance: float = 0.05) -> bool:
        """Extract numbers and compare within tolerance."""
        try:
            ans_num = self._extract_number(answer)
            gt_num = float(gt) if not isinstance(gt, (int, float)) else gt
            if gt_num == 0:
                return ans_num == 0
            return abs(ans_num - gt_num) / abs(gt_num) <= tolerance
        except (ValueError, ZeroDivisionError):
            return False

    def _entity_match(self, answer: str, gt: str) -> bool:
        """Word-overlap entity match: ≥50% of GT keywords in answer.

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
        return overlap / len(gt_words) >= 0.50

    def _synthesis_match(self, answer: str, gt: str) -> bool:
        """Synthesis/cross_domain match: entity name + numeric value.

        GT format: "EntityName (value)" — requires BOTH entity name match
        AND numeric value match (±5%).
        Falls back to entity_match if GT has no parenthetical value.
        """
        # Parse GT: "EntityName (value)"
        paren_match = re.search(r"^(.+?)\s*\(([^)]+)\)\s*$", gt)
        if not paren_match:
            # No value in GT — fall back to entity match only
            return self._entity_match(answer, gt)

        gt_entity = paren_match.group(1).strip()
        gt_value_str = paren_match.group(2).strip()

        # Check 1: entity name must match
        if not self._entity_match(answer, gt_entity):
            return False

        # Check 2: numeric value must appear in answer (±5%)
        try:
            gt_num = self._extract_number(gt_value_str)
        except ValueError:
            # Non-numeric value — just check entity match
            return True

        try:
            ans_num = self._extract_number(answer)
            if gt_num == 0:
                return ans_num == 0
            return abs(ans_num - gt_num) / abs(gt_num) <= 0.05
        except ValueError:
            return False

    def _abstention_match(self, answer: str) -> bool:
        """Detect refusal/abstention signals.

        Must contain a refusal phrase AND not contain a numeric guess.
        "Unknown, but I guess 50" → has number → NOT abstention.
        """
        refusal_patterns = [
            "abstain", "don't know", "not available", "no information",
            "cannot determine", "insufficient data", "not mentioned",
            "no record", "unknown", "i don't have",
        ]
        a = answer.lower()
        has_refusal = any(p in a for p in refusal_patterns)
        if not has_refusal:
            return False
        # Reject if answer also contains a numeric value (hedged guess)
        has_number = bool(re.search(r"\d", a))
        return not has_number

    def _extract_number(self, text: str) -> float:
        """Extract a number from text. Handles $, K, M, commas."""
        text = text.replace(",", "").replace("$", "").strip()
        # Require at least one digit to avoid matching bare dots (e.g. "Dr.")
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
