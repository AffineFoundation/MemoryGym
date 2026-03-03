"""Inspect AI task definition for MemoryBench v3.

Usage:
    # Run with default settings (random seed):
    inspect eval memorybench/inspect_task/task.py -M openai/gpt-4o

    # Run with specific seed:
    inspect eval memorybench/inspect_task/task.py -M openai/gpt-4o \
        -T seed=42 -T write_budget=30

    # Run with mock backend (faster, for testing):
    inspect eval memorybench/inspect_task/task.py -M openai/gpt-4o \
        -T backend=mock
"""

from __future__ import annotations

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import ChatMessageSystem
from inspect_ai.solver import chain, use_tools

from memorybench.config import EvalConfig
from memorybench.generation.task_stream import generate_stream
from memorybench.inspect_task.scorer import memorybench_scorer
from memorybench.inspect_task.solver import SYSTEM_PROMPT, memorybench_solver
from memorybench.inspect_task.tools import create_memory_tools, submit_answer


def _build_sample(
    seed: int,
    config: EvalConfig,
    backend_type: str = "chromadb",
    eval_salt: int = 0,
) -> tuple[Sample, int | None, int]:
    """Build a single Sample containing all benchmark tasks.

    Returns:
        (sample, switch_point, write_budget)
    """
    tasks, updates, kbs, dom_map, switch_pt = generate_stream(
        seed, config, eval_salt=eval_salt,
    )

    # Serialize tasks for the solver
    benchmark_tasks = []
    for t in tasks:
        task_data = {
            "task_id": t.task_id,
            "global_id": t.global_id,
            "domain": t.domain,
            "documents": t.documents,
        }
        if t.question:
            task_data["question"] = t.question.question
            task_data["ground_truth"] = t.question.answer
            task_data["competency"] = t.question.competency
            task_data["domain"] = t.question.domain
            task_data["required_entities"] = t.question.required_entities
        else:
            task_data["question"] = None
            task_data["ground_truth"] = None
            task_data["competency"] = None
            task_data["required_entities"] = []

        benchmark_tasks.append(task_data)

    # Domain info for metadata
    domain_names = list(dom_map.keys())

    sample = Sample(
        input="MemoryBench Evaluation",
        target=str(seed),
        id=f"memorybench_seed_{seed}",
        metadata={
            "benchmark_tasks": benchmark_tasks,
            "seed": seed,
            "eval_salt": eval_salt,
            "domains": domain_names,
            "n_tasks": config.n_tasks,
            "write_budget": config.write_budget,
            "switch_point": switch_pt,
            "backend_type": backend_type,
        },
    )

    return sample, switch_pt, config.write_budget


@task
def memorybench(
    seed: int | None = None,
    n_tasks: int = 25,
    write_budget: int = 30,
    backend: str = "chromadb",
    eval_salt: int = 0,
) -> Task:
    """MemoryBench v3: Streaming Memory Management Evaluation.

    One eval run = one seed = one complete 25-task stream.
    The agent reads documents, stores selected info to memory,
    and answers questions requiring cross-task retrieval.

    Args:
        seed: Random seed for deterministic task generation.
        n_tasks: Number of tasks in the stream (default 25).
        write_budget: Total memory writes allowed (default 30).
        backend: Memory backend ("chromadb" or "mock").
        eval_salt: Perturbation salt (0 = no perturbation).
    """
    if seed is None:
        raise ValueError(
            "seed is required for reproducible evaluation. "
            "Pass -T seed=<int> when running inspect eval."
        )

    config = EvalConfig(
        n_tasks=n_tasks,
        write_budget=write_budget,
    )

    sample, switch_pt, budget = _build_sample(
        seed, config, backend, eval_salt=eval_salt,
    )
    dataset = MemoryDataset([sample])

    # Create memory tools (shared backend + budget)
    memory_tools, mem_budget = create_memory_tools(
        budget=budget,
        backend_type=backend,
        collection_name=f"memorybench_{seed}",
    )

    system_msg = SYSTEM_PROMPT.format(
        n_tasks=n_tasks,
        budget=budget,
    )

    def _setup_solver():
        """Create solver pipeline with system message + tools."""
        from inspect_ai.solver import system_message as sys_msg

        return chain(
            sys_msg(system_msg),
            use_tools(memory_tools + [submit_answer()]),
            memorybench_solver(
                n_tasks=n_tasks,
                budget=budget,
                mem_budget=mem_budget,
            ),
        )

    return Task(
        dataset=dataset,
        solver=_setup_solver(),
        scorer=memorybench_scorer(switch_point=switch_pt),
        message_limit=n_tasks * 20,  # generous limit for tool calls
        name=f"memorybench_seed_{seed}",
        metadata={
            "seed": seed,
            "eval_salt": eval_salt,
            "backend": backend,
            "write_budget": budget,
        },
    )
