"""Inspect AI scorer for WorldBench: 6-axis memory evaluation.

Axes:
- accuracy: overall question accuracy
- storage: retrieval question accuracy (recall + coverage)
- maintenance: update question accuracy, gated by storage coverage
- reasoning: comprehension question accuracy (synthesis/aggregation/conditional)
- efficiency: correct answers per write, baselined on budget
- process: write_rate × accuracy

Composite: weighted sum of all axes.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from inspect_ai.model import get_model
from inspect_ai.scorer import Score, Target, scorer

from memorybench.evaluation.llm_judge import llm_judge_validate
from memorybench.evaluation.validators import (
    AnswerValidator,
    async_validate_with_fallback,
)

log = logging.getLogger(__name__)


@scorer(metrics=[])
def worldbench_scorer(judge_model: str | None = None) -> Any:
    """Score worldbench answers with 6-axis metrics.

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
        # Passed into async_validate_with_fallback — same path as stream_agent.
        judge_fn = None
        if judge_model:
            try:
                judge = get_model(judge_model)

                async def _async_judge(q, gt_, ans, comp):
                    return await llm_judge_validate(judge, q, gt_, ans, comp)

                judge_fn = _async_judge
            except Exception:
                log.warning("Failed to init judge model %s", judge_model)

        # Validate each answer: rule-first, judge-fallback
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

        # ── Compute axes ──
        n_total = len(results)
        n_correct = sum(r["correct"] for r in results)
        accuracy = n_correct / n_total

        # Storage axis: retrieval questions (purpose: recall + coverage)
        storage_rs = [r for r in results if r["competency"] == "retrieval"]
        storage = (sum(r["correct"] for r in storage_rs) / len(storage_rs)
                   if storage_rs else 0.0)

        # Maintenance axis: update questions
        maint_rs = [r for r in results if r["competency"] == "update"]
        maintenance = (sum(r["correct"] for r in maint_rs) / len(maint_rs)
                       if maint_rs else 0.0)

        # Reasoning axis: synthesis + aggregation + conditional
        # NOTE: reasoning mixes LLM computation ability with memory management.
        # For cross-LLM comparison, focus on storage and maintenance axes.
        reason_rs = [r for r in results if r["competency"] in
                     ("synthesis", "aggregation", "conditional")]
        reasoning = (sum(r["correct"] for r in reason_rs) / len(reason_rs)
                     if reason_rs else 0.0)

        # Maintenance: gate on retrieval accuracy (V8: robust against
        # name-only packing — must actually answer retrieval correctly)
        storage_coverage = storage  # empirical, not name-detection
        maintenance = (maintenance
                       * min(storage_coverage / 0.5, 1.0))

        # Efficiency: correct/write ratio × accuracy floor (V7: prevents
        # minimalist strategies from getting max efficiency)
        budget = state.store.get("write_budget", 30)
        ideal_rate = n_total / max(budget, 1)
        if writes_used == 0:
            efficiency = 0.0
        else:
            raw_eff = min(n_correct / writes_used / ideal_rate, 1.0)
            efficiency = raw_eff * accuracy

        # Process: write_rate × accuracy, no search_rate (Fix 2)
        n_questions = len(results)
        write_rate = min(writes_used / max(n_questions * 0.5, 1), 1.0)
        process = write_rate * accuracy

        # Composite: weighted sum with storage axis (Fix 6)
        composite = (0.25 * accuracy + 0.20 * storage + 0.20 * reasoning
                     + 0.15 * maintenance + 0.10 * efficiency
                     + 0.10 * process)

        # Per-competency breakdown
        by_comp: dict[str, list[bool]] = defaultdict(list)
        for r in results:
            by_comp[r["competency"]].append(r["correct"])

        # Per-purpose breakdown
        by_purpose: dict[str, list[bool]] = defaultdict(list)
        for r in results:
            if r["purpose"]:
                by_purpose[r["purpose"]].append(r["correct"])

        # Build flat value dict (Inspect AI requirement)
        value: dict[str, Any] = {
            "composite": round(composite, 4),
            "accuracy": round(accuracy, 4),
            "storage": round(storage, 4),
            "maintenance": round(maintenance, 4),
            "reasoning": round(reasoning, 4),
            "efficiency": round(efficiency, 4),
            "process": round(process, 4),
            "write_rate": round(write_rate, 4),
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
                f"Accuracy={accuracy:.1%}, Storage={storage:.1%}, "
                f"Maintenance={maintenance:.1%} (cov={storage_coverage:.0%}), "
                f"Reasoning={reasoning:.1%}, "
                f"Efficiency={efficiency:.3f}, Process={process:.2f}, "
                f"Composite={composite:.3f}"
            ),
            metadata={"task_details": results},
        )

    return score
