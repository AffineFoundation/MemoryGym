"""Inspect AI scorer for WorldBench: 4-axis memory evaluation.

Axes:
- breadth: retrieval question accuracy (storage breadth)
- maintenance: update question accuracy, gated by storage coverage
- reasoning: comprehension question accuracy (all types)
- efficiency: correct answers per write, normalized to budget

Diagnostic (not in composite):
- abstention_diagnostic: abstention question accuracy

Composite: 0.30×breadth + 0.25×maintenance + 0.25×reasoning + 0.20×efficiency
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from inspect_ai.model import get_model
from inspect_ai.scorer import Score, Target, scorer

from memorygym.evaluation.llm_judge import llm_judge_validate
from memorygym.evaluation.validators import async_validate_with_fallback
from memorygym.protocol import compute_axis_scores

log = logging.getLogger(__name__)


@scorer(metrics=[])
def worldbench_scorer(judge_model: str | None = None) -> Any:
    """Score worldbench answers with 4-axis metrics + abstention diagnostic.

    Validation paths (no fallback — each path is self-contained):
    - With judge: LLM judge validates all non-abstention questions.
      Abstention uses rule-based _abstention_match (V10 authoritative).
      Judge failure = incorrect (fail closed).
    - Without judge: rule-based AnswerValidator for all questions.

    Args:
        judge_model: Model name for LLM judge. None = rules only.
    """
    async def score(state: Any, target: Target) -> Score:
        answers = state.store.get("benchmark_answers", [])
        writes_used = state.store.get("writes_used", 0)

        # Build judge function if configured.
        judge_fn = None
        if judge_model:
            try:
                judge = get_model(judge_model)

                async def _async_judge(q, gt_, ans, comp):
                    return await llm_judge_validate(judge, q, gt_, ans, comp)

                judge_fn = _async_judge
            except Exception:
                log.warning("Failed to init judge model %s", judge_model)

        # Validate each answer
        results: list[dict] = []
        for ans in answers:
            agent_answer = ans.get("answer") or ""
            gt = ans.get("ground_truth")
            competency = ans.get("competency", "retrieval")
            question = ans.get("question", "")

            if gt is None:
                continue

            is_correct, _ = await async_validate_with_fallback(
                agent_answer, str(gt), competency,
                question=question, judge_fn=judge_fn)
            results.append({
                "task_id": ans.get("task_id", 0),
                "competency": competency,
                "purpose": ans.get("purpose", ""),
                "correct": is_correct,
                "agent_answer": agent_answer,
                "ground_truth": str(gt),
                "n_writes": ans.get("n_writes", 0),
                "n_searches": ans.get("n_searches", 0),
            })

        if not results:
            return Score(value=0.0, explanation="No questions answered.")

        # ── Build per-competency lists ──
        by_comp: dict[str, list[bool]] = defaultdict(list)
        for r in results:
            by_comp[r["competency"]].append(r["correct"])

        # ── Compute axes via canonical formula ──
        n_entities = state.store.get("n_entities", 60)
        stored_count = state.store.get("stored_count", 0)
        write_budget = state.store.get("write_budget", 30)

        axes = compute_axis_scores(
            by_competency=dict(by_comp),
            n_entities=n_entities,
            stored_count=stored_count,
            writes_used=writes_used,
            write_budget=write_budget,
        )
        breadth = axes["breadth"]
        maintenance = axes["maintenance"]
        reasoning = axes["reasoning"]
        efficiency = axes["efficiency"]
        composite = axes["composite"]
        abstention_diagnostic = axes["abstention_diagnostic"]
        storage_coverage = stored_count / n_entities if n_entities else 0.0

        # Per-purpose breakdown
        by_purpose: dict[str, list[bool]] = defaultdict(list)
        for r in results:
            if r["purpose"]:
                by_purpose[r["purpose"]].append(r["correct"])

        # Build flat value dict (Inspect AI requirement)
        value: dict[str, Any] = {
            "composite": round(composite, 4),
            "breadth": round(breadth, 4),
            "maintenance": round(maintenance, 4),
            "reasoning": round(reasoning, 4),
            "efficiency": round(efficiency, 4),
            "abstention_diagnostic": round(abstention_diagnostic, 4),
            "storage_coverage": round(storage_coverage, 4),
            "writes_used": writes_used,
            "n_questions": n_total,
            "n_correct": n_correct,
        }
        for k, vs in by_comp.items():
            value[f"comp_{k}"] = round(sum(vs) / len(vs), 4) if vs else 0.0
        for k, vs in by_purpose.items():
            value[f"purp_{k}"] = round(sum(vs) / len(vs), 4) if vs else 0.0

        return Score(
            value=value,
            explanation=(
                f"Breadth={breadth:.1%}, Maintenance={maintenance:.1%} "
                f"(cov={storage_coverage:.0%}), "
                f"Reasoning={reasoning:.1%}, "
                f"Efficiency={efficiency:.3f}, "
                f"Abstention={abstention_diagnostic:.1%}, "
                f"Composite={composite:.3f}"
            ),
            metadata={"task_details": results},
        )

    return score
