"""Inspect AI scorer for MemoryBench: 4-dimensional evaluation + LLM judge."""

from __future__ import annotations

import logging
from typing import Any

from inspect_ai.model import get_model
from inspect_ai.scorer import Score, Target, scorer

from memorybench.domains.base import TaskResult
from memorybench.evaluation.llm_judge import llm_judge_validate
from memorybench.evaluation.scorer import (
    compute_accuracy,
    compute_adaptability,
    compute_efficiency,
    compute_trajectory,
    score_by_competency,
    score_by_domain,
)
from memorybench.evaluation.validators import AnswerValidator

log = logging.getLogger(__name__)


@scorer(metrics=[])
def memorybench_scorer(
    switch_point: int | None = None,
    judge_model: str | None = None,
) -> Any:
    """Score all task answers and compute 4-dimensional metrics.

    Two-pass validation:
    1. Rule-based (AnswerValidator)
    2. LLM judge fallback for non-empty answers that failed rules

    Args:
        switch_point: Task ID where domain switches (for adaptability).
        judge_model: Model name for LLM judge (e.g. "openai/gpt-4o-mini").
            If None, LLM judge is disabled and only rule-based scoring is used.
    """
    validator = AnswerValidator()

    async def score(state: Any, target: Target) -> Score:
        answers = state.store.get("benchmark_answers", [])
        writes_used = state.store.get("writes_used", 0)

        # Initialize judge model if configured
        judge = None
        if judge_model:
            try:
                judge = get_model(judge_model)
            except Exception:
                log.warning("Failed to initialize judge model %s", judge_model)

        results: list[TaskResult] = []
        details: list[dict] = []

        for ans in answers:
            agent_answer = ans.get("answer") or ""
            gt = ans.get("ground_truth")
            competency = ans.get("competency", "retrieval")
            domain = ans.get("domain", "unknown")
            task_id = ans.get("task_id", 0)
            question = ans.get("question", "")

            if gt is None:
                continue

            # Pass 1: rule-based validation
            rule_correct = validator.validate(agent_answer, gt, competency)
            judge_correct = None
            judge_reason = ""

            # Pass 2: LLM judge fallback
            if not rule_correct and agent_answer.strip() and judge:
                try:
                    judge_correct, judge_reason = await llm_judge_validate(
                        judge, question, str(gt), agent_answer, competency,
                    )
                except Exception as exc:
                    log.warning("LLM judge failed for task %d: %s",
                                task_id, exc)

            is_correct = rule_correct or (judge_correct is True)

            results.append(TaskResult(
                task_id=task_id,
                competency=competency,
                domain=domain,
                is_correct=is_correct,
            ))
            detail = {
                "task_id": task_id,
                "competency": competency,
                "domain": domain,
                "agent_answer": agent_answer,
                "ground_truth": str(gt),
                "correct": is_correct,
                "rule_correct": rule_correct,
            }
            if judge_correct is not None:
                detail["judge_correct"] = judge_correct
                detail["judge_reason"] = judge_reason
            details.append(detail)

        if not results:
            return Score(
                value=0.0,
                explanation="No questions answered.",
            )

        acc = compute_accuracy(results)
        traj = compute_trajectory(results)
        eff = compute_efficiency(results, max(writes_used, 1))
        adapt = compute_adaptability(results, switch_point)

        # Process score: harmonic mean of write_rate and search_rate.
        # Requires BOTH writing and searching to score well.
        answering = [
            a for a in answers
            if a.get("searched_before_answering") is not None
        ]
        n_questions = len(answering)
        write_rate = min(writes_used / max(n_questions * 0.5, 1), 1.0)
        search_rate = (
            sum(a["searched_before_answering"] for a in answering)
            / n_questions
            if n_questions else 0.0
        )
        if write_rate + search_rate > 0:
            process = 2 * write_rate * search_rate / (write_rate + search_rate)
        else:
            process = 0.0

        # Multiplicative composite: accuracy gates everything.
        memory_quality = (
            0.20 * traj
            + 0.25 * eff
            + 0.15 * adapt
            + 0.40 * process
        )
        composite = acc * memory_quality

        by_comp = score_by_competency(results)
        by_dom = score_by_domain(results)

        # Score.value must be flat (no nested dicts)
        value = {
            "composite": round(composite, 4),
            "accuracy": round(acc, 4),
            "trajectory": round(traj, 4),
            "efficiency": round(eff, 4),
            "adaptability": round(adapt, 4),
            "process": round(process, 4),
            "memory_quality": round(memory_quality, 4),
            "write_rate": round(write_rate, 4),
            "search_rate": round(search_rate, 4),
            "writes_used": writes_used,
            "n_questions": len(results),
            "n_correct": sum(r.is_correct for r in results),
        }
        for k, v in by_comp.items():
            value[f"comp_{k}"] = round(v, 4)
        for k, v in by_dom.items():
            value[f"dom_{k}"] = round(v, 4)

        return Score(
            value=value,
            explanation=(
                f"Accuracy={acc:.1%}, Trajectory={traj:.3f}, "
                f"Efficiency={eff:.3f}, Adaptability={adapt:.3f}, "
                f"Process={process:.2f} (W={write_rate:.2f},S={search_rate:.2f}), "
                f"MemQ={memory_quality:.3f}, Composite={composite:.3f}"
            ),
            metadata={"task_details": details},
        )

    return score
