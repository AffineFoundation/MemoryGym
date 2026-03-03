"""Global configuration for MemoryBench v3."""

from dataclasses import dataclass


@dataclass
class EvalConfig:
    """All parameters validated in PoC (30 seeds, 9/9 checks pass)."""

    n_tasks: int = 25
    n_entities_per_domain: int = 25
    write_budget: int = 50
    max_writes_per_task: int = 3
    n_domains: int = 2  # select 2 from 3

    # Cross-domain questions in pressure phase (tasks 20+)
    cross_domain_prob: float = 0.3

    # Scoring
    efficiency_baseline: float = 0.5  # correct/write ratio for score=1.0


def task_global_id(seed: int, task_index: int,
                   n_tasks: int = 25) -> int:
    """Map (seed, task_index) to a unique global task ID."""
    return seed * n_tasks + task_index


def task_from_global_id(global_id: int,
                        n_tasks: int = 25) -> tuple[int, int]:
    """Recover (seed, task_index) from a global task ID."""
    seed, task_index = divmod(global_id, n_tasks)
    return seed, task_index
