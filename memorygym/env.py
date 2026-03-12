"""MemoryGym — OpenEnv-compatible evaluation environment.

Actor class implementing the affinetes OpenEnv interface for containerized
evaluation. Supports both full-run evaluate() and interactive reset/step.

Usage:
    from memorygym.env import Actor
    actor = Actor()
    result = await actor.evaluate(
        model="moonshotai/Kimi-K2.5-TEE",
        seed=42,
        template="company",
    )
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from random import Random
from typing import Any

from affinetes.core.openenv import OpenEnvResponse

from memorygym import __version__
from memorygym.agents.stream_agent import run_stream_agent
from memorygym.memory.backends.chromadb_backend import ChromaDBBackend
from memorygym.protocol import TIERS, compute_axis_scores, trajectory_to_conversation
from memorygym.worlds import ALL_TEMPLATES


class Actor:
    """MemoryGym evaluation actor.

    Implements the OpenEnv interface: reset(), step(), state(), stop(),
    evaluate(). Each episode runs a full memory management evaluation.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        self._episodes: dict[str, dict[str, Any]] = {}

    async def evaluate(
        self,
        model: str,
        base_url: str,
        api_key: str | None = None,
        seed: int = 0,
        template: str = "company",
        tier: str = "lite",
        backend: str = "chromadb",
        timeout: int = 3600,
        task_id: int | None = None,
    ) -> dict:
        """Run a complete evaluation episode.

        Args:
            model: Model name (OpenAI-compatible).
            base_url: API base URL.
            api_key: API key override.
            seed: Random seed for deterministic generation.
            template: World template name.
            tier: Evaluation tier (lite/standard/hard).
            backend: Memory backend.
            timeout: Wall-clock timeout in seconds.
            task_id: Optional task ID (overrides seed/template).

        Returns:
            Result dict: {task_name, score, success, time_taken, extra}.
        """
        start_time = time.time()
        current_key = api_key or self.api_key

        if task_id is not None:
            template = _parse_task_id(task_id)

        if template not in ALL_TEMPLATES:
            raise ValueError(
                f"Unknown template '{template}'. "
                f"Choose from: {', '.join(ALL_TEMPLATES)}")

        tier_cfg = TIERS.get(tier)
        if tier_cfg is None:
            raise ValueError(
                f"Unknown tier '{tier}'. Choose from: {', '.join(TIERS)}")

        try:
            result = _run_evaluation(
                model=model,
                base_url=base_url,
                api_key=current_key,
                seed=seed,
                template_name=template,
                tier_cfg=tier_cfg,
                backend_type=backend,
            )
        except Exception as exc:
            import traceback
            result = {
                "task_name": f"memorygym:{template}:{tier}",
                "score": 0.0,
                "success": False,
                "time_taken": time.time() - start_time,
                "extra": {
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                    "model": model,
                    "seed": seed,
                    "template": template,
                    "tier": tier,
                },
            }

        result["time_taken"] = time.time() - start_time
        return result

    async def reset(
        self,
        task_id: int | None = None,
        seed: int | None = None,
    ) -> OpenEnvResponse:
        """Reset and start a new interactive episode.

        For MemoryGym, interactive mode is not the primary interface.
        Use evaluate() for full evaluation runs.
        """
        episode_id = str(uuid.uuid4())
        seed = seed if seed is not None else 0

        self._episodes[episode_id] = {
            "seed": seed,
            "status": "ready",
            "step_count": 0,
        }

        return OpenEnvResponse(
            observation="MemoryGym episode initialized. "
                        "Use evaluate() for full evaluation runs.",
            reward=0.0,
            done=False,
            episode_id=episode_id,
            info={"seed": seed, "status": "ready"},
        )

    async def step(
        self,
        action: str,
        episode_id: str | None = None,
    ) -> OpenEnvResponse:
        """Process a single action in an interactive episode."""
        if episode_id not in self._episodes:
            return OpenEnvResponse(
                observation="Unknown episode. Call reset() first.",
                reward=0.0,
                done=True,
                episode_id=episode_id,
            )

        ep = self._episodes[episode_id]
        ep["step_count"] += 1

        return OpenEnvResponse(
            observation="Interactive step mode not supported. "
                        "Use evaluate() for full evaluation.",
            reward=0.0,
            done=True,
            episode_id=episode_id,
            info={"step_count": ep["step_count"]},
        )

    async def state(
        self, episode_id: str | None = None,
    ) -> OpenEnvResponse:
        """Get current episode state."""
        if episode_id not in self._episodes:
            return OpenEnvResponse(
                observation="No active episode.",
                reward=0.0,
                done=True,
                episode_id=episode_id,
            )

        ep = self._episodes[episode_id]
        return OpenEnvResponse(
            observation=f"Episode status: {ep['status']}",
            reward=0.0,
            done=ep["status"] == "completed",
            episode_id=episode_id,
            info=ep,
        )

    async def stop(
        self, episode_id: str | None = None,
    ) -> dict[str, Any]:
        """Stop an episode and clean up."""
        if episode_id in self._episodes:
            del self._episodes[episode_id]
        return {"stopped": True, "episode_id": episode_id}


def _parse_task_id(task_id: int) -> str:
    """Map task_id to template name via stable registry.

    task_id is an index into TEMPLATE_REGISTRY (0..N-1).
    Seed is passed separately by the caller.
    """
    from memorygym.worlds import TEMPLATE_REGISTRY
    if task_id < 0 or task_id >= len(TEMPLATE_REGISTRY):
        raise ValueError(
            f"task_id must be 0..{len(TEMPLATE_REGISTRY) - 1}, "
            f"got {task_id}")
    return TEMPLATE_REGISTRY[task_id]


def _run_evaluation(
    model: str,
    base_url: str,
    api_key: str | None,
    seed: int,
    template_name: str,
    tier_cfg: dict,
    backend_type: str = "chromadb",
) -> dict:
    """Run a synchronous evaluation and return result dict."""
    n_entities = tier_cfg["entities"]
    n_questions = tier_cfg["questions"]
    n_corrections = tier_cfg["corrections"]
    write_budget = tier_cfg["write_budget"]

    tmpl_cls = ALL_TEMPLATES[template_name]
    tmpl = tmpl_cls()
    world = tmpl.generate_world(
        seed=seed, n_entities=n_entities,
        eval_salt=tier_cfg.get("eval_salt", 1))

    rng_correct = Random(seed + 3333)
    corrections = tmpl.generate_corrections(world, rng_correct, n_corrections)
    n_contras = max(1, n_corrections // 3)
    exclude_corrected = {c.entity_name for c in corrections}
    rng_contra = Random(seed + 7373)
    contradictions = tmpl.generate_contradictions(
        world, rng_contra, n_contras,
        exclude_entities=exclude_corrected)

    rng_stream = Random(seed + 5555)
    stream = tmpl.generate_stream(
        world, rng_stream, corrections,
        stored_names=set(),
        n_questions=n_questions,
        entities_per_batch=10,
        contradictions=contradictions,
    )

    if backend_type == "markdown":
        from memorygym.memory.backends.markdown_backend import MarkdownBackend
        backend_obj = MarkdownBackend()
    else:
        backend_obj = ChromaDBBackend()

    agent_results, writes_used, stored, eval_error, traj = run_stream_agent(
        model=model,
        stream=stream,
        write_budget=write_budget,
        api_base=base_url,
        api_key=api_key,
        backend=backend_obj,
        world=world,
        template=tmpl,
        seed=seed,
    )

    # Compute scores
    correct = sum(r.correct for r in agent_results)
    total = len(agent_results)
    by_comp: dict[str, list[bool]] = defaultdict(list)
    answer_details = []
    conversation = []

    for r in agent_results:
        by_comp[r.competency].append(r.correct)
        answer_details.append({
            "question": r.question,
            "expected": r.ground_truth,
            "actual": r.answer,
            "score": 1.0 if r.correct else 0.0,
            "is_correct": r.correct,
            "competency": r.competency,
            "purpose": r.purpose,
            "validation_method": r.validation_method,
            "validation_reason": r.validation_reason,
        })

    # Build conversation from trajectory using shared function
    if traj:
        conversation = trajectory_to_conversation(traj)

    stored_names, missed = tmpl.detect_stored_entities(world, stored)

    comp_scores = {
        c: round(sum(v) / len(v), 4) if v else 0.0
        for c, v in by_comp.items()
    }

    # 4-axis scoring via shared function
    axis_scores = compute_axis_scores(
        by_competency=dict(by_comp),
        n_entities=n_entities,
        stored_count=len(stored_names),
        writes_used=writes_used,
        write_budget=write_budget,
    )

    return {
        "task_name": f"memorygym:{template_name}:{n_entities}e:{n_questions}q",
        "score": round(correct / total, 4) if total else 0.0,
        "success": total > 0 and eval_error is None,
        "time_taken": 0.0,  # filled by caller
        "extra": {
            "model": model,
            "backend": backend_type,
            "seed": seed,
            "template": template_name,
            "n_entities": n_entities,
            "n_questions": n_questions,
            "n_corrections": n_corrections,
            "write_budget": write_budget,
            "writes_used": writes_used,
            "stored_entities": len(stored_names),
            "missed_entities": len(missed),
            "per_axis": axis_scores,
            "composite": axis_scores["composite"],
            "by_competency": comp_scores,
            "answer_details": answer_details,
            "conversation": conversation,
            "version": __version__,
        },
    }
