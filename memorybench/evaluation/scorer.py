"""Scoring functions for MemoryBench evaluation."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from memorybench.domains.base import TaskResult

if TYPE_CHECKING:
    from memorybench.simulation.agents import TaskTrace


def compute_accuracy(results: list[TaskResult]) -> float:
    if not results:
        return 0.0
    return sum(r.is_correct for r in results) / len(results)


def compute_trajectory(results: list[TaskResult]) -> float:
    """Learning trajectory: improvement from first to second half.

    Formula: 0.5 + (acc_second - acc_first) / 2
    Neutral = 0.5 (no change), >0.5 = improvement, <0.5 = degradation.
    """
    if len(results) < 4:
        return 0.5
    mid = len(results) // 2
    first_half = results[:mid]
    second_half = results[mid:]
    acc_first = sum(r.is_correct for r in first_half) / len(first_half)
    acc_second = sum(r.is_correct for r in second_half) / len(second_half)
    return 0.5 + (acc_second - acc_first) / 2


def compute_efficiency(results: list[TaskResult], writes_used: int) -> float:
    if writes_used == 0:
        return 0.0
    correct = sum(r.is_correct for r in results)
    raw = correct / writes_used
    return min(raw / 0.5, 1.0)


def compute_adaptability(results: list[TaskResult],
                          switch_point: int | None) -> float:
    if switch_point is None:
        return 0.5
    pre = [r for r in results if r.task_id < switch_point
           and r.task_id >= switch_point - 5]
    post = [r for r in results if r.task_id >= switch_point
            and r.task_id < switch_point + 5]
    if not pre or not post:
        return 0.5
    pre_acc = sum(r.is_correct for r in pre) / len(pre)
    post_acc = sum(r.is_correct for r in post) / len(post)
    if pre_acc == 0:
        return post_acc
    return min(post_acc / pre_acc, 1.0)


def score_by_competency(results: list[TaskResult]) -> dict[str, float]:
    by_comp: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        by_comp[r.competency].append(r.is_correct)
    return {c: sum(v) / len(v) if v else 0.0 for c, v in by_comp.items()}


def score_by_domain(results: list[TaskResult]) -> dict[str, float]:
    by_dom: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        by_dom[r.domain].append(r.is_correct)
    return {d: sum(v) / len(v) if v else 0.0 for d, v in by_dom.items()}


def compute_process_score(traces: list[TaskTrace],
                          writes_used: int = 0) -> float:
    """Harmonic mean of write_rate and search_rate.

    Requires BOTH writing and searching to score well — either one
    being zero forces the result to zero.

    Args:
        traces: Per-task traces with searched_before_answering flags.
        writes_used: Total memory writes used across all tasks.
    """
    answering_traces = [
        t for t in traces if t.searched_before_answering is not None
    ]
    n_questions = len(answering_traces)
    if not n_questions:
        return 0.0
    write_rate = min(writes_used / max(n_questions * 0.5, 1), 1.0)
    search_rate = (
        sum(t.searched_before_answering for t in answering_traces)
        / n_questions
    )
    if write_rate + search_rate > 0:
        return 2 * write_rate * search_rate / (write_rate + search_rate)
    return 0.0
