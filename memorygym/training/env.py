"""Training data interfaces: SFT trajectories and RL environment.

Generate training data from deterministic simulation strategies,
using the same WorldTemplate infrastructure as evaluation.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from random import Random
from typing import Any

from memorygym.protocol import TIERS
from memorygym.simulation import (
    TEMPLATES,
    _construct_and_validate,
    _data_available,
    _VALIDATOR,
)
from memorygym.worlds.base import WorldTemplate


def generate_sft_trajectory(
    template_name: str,
    seed: int,
    strategy: str = "perfect",
    n_entities: int = 60,
    n_questions: int = 20,
    n_corrections: int = 5,
    write_budget: int = 30,
) -> list[dict]:
    """Generate a complete tool-calling trajectory in OpenAI messages format.

    Replays the simulation strategy as explicit tool call sequences:
    - ingest: memory_store calls for each stored entity
    - correction: memory_search + memory_forget + memory_store
    - question: memory_search + submit_answer(ground_truth)

    Args:
        template_name: World template name.
        seed: Random seed for world generation.
        strategy: "perfect" or "strategic".
        n_entities: Number of entities.
        n_questions: Number of questions.
        n_corrections: Number of corrections.
        write_budget: Write budget for system prompt.

    Returns:
        List of message dicts (OpenAI messages format).
    """
    if template_name not in TEMPLATES:
        raise ValueError(f"Unknown template: {template_name}")

    tmpl = TEMPLATES[template_name]()
    world = tmpl.generate_world(seed=seed, n_entities=n_entities)
    rng = Random(seed)

    # Determine store ratio from strategy name
    store_ratio = 1.0 if strategy == "perfect" else 0.7
    applies_updates = True

    # Render documents
    rng_doc = Random(seed)
    all_docs = [(e, tmpl.render_document(e, world.active_attrs, rng_doc))
                for e in world.entities]

    # Storage decision
    rng_store = Random(seed + 111)
    if store_ratio >= 1.0:
        stored_indices = list(range(len(all_docs)))
    else:
        n_store = max(1, int(len(all_docs) * store_ratio))
        stored_indices = sorted(
            rng_store.sample(range(len(all_docs)), n_store))

    stored_names = {all_docs[i][0].name for i in stored_indices}

    # Generate corrections (mutates world)
    rng_correct = Random(seed + 3333)
    corrections = tmpl.generate_corrections(world, rng_correct, n_corrections)

    # Implicit contradictions
    n_contras = max(1, n_corrections // 3)
    exclude_corrected = {c.entity_name for c in corrections}
    rng_contra = Random(seed + 7373)
    contradictions = tmpl.generate_contradictions(
        world, rng_contra, n_contras,
        exclude_entities=exclude_corrected)

    # Generate stream
    rng_stream = Random(seed + 5555)
    stream = tmpl.generate_stream(
        world, rng_stream, corrections, stored_names,
        n_questions=n_questions, entities_per_batch=10,
        contradictions=contradictions,
    )

    # Build system prompt
    from memorygym.agents.stream_agent import SYSTEM_PROMPT
    system_prompt = SYSTEM_PROMPT.format(budget=write_budget)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    total_events = len(stream)
    mem_id_counter = 0
    entity_mem_ids: dict[str, str] = {}  # entity_name → memory_id

    for event_idx, event in enumerate(stream):
        event_type = event["type"]

        if event_type == "ingest":
            # User message: documents
            docs = event["documents"]
            docs_text = "\n\n".join(
                f"[Document {i+1}]\n{doc}" for i, doc in enumerate(docs))
            user_msg = (
                f"=== Event {event_idx+1}/{total_events} [DOCUMENTS] ===\n\n"
                f"**Documents:**\n{docs_text}\n\n"
                "No question. Store important entity data."
            )
            messages.append({"role": "user", "content": user_msg})

            # Assistant response: store each entity that strategy keeps
            tool_calls = []
            for ename in event.get("entity_names", []):
                if ename not in stored_names:
                    continue
                entity = world.get_entity(ename)
                if not entity:
                    continue
                compact = tmpl._compact_document(entity, world.active_attrs)
                content = f"{ename} | {compact}"
                mem_id_counter += 1
                mid = f"mem_{mem_id_counter:03d}"
                entity_mem_ids[ename] = mid
                tool_calls.append(
                    f'<tool_call>{{"name": "memory_store", '
                    f'"arguments": {{"content": "{content}"}}}}</tool_call>'
                )

            if tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": "\n".join(tool_calls),
                })
                messages.append({
                    "role": "user",
                    "content": "\n".join(
                        f"[memory_store] Stored (id={entity_mem_ids[n]}). "
                        f"Budget remaining."
                        for n in event.get("entity_names", [])
                        if n in stored_names and n in entity_mem_ids
                    ),
                })
            else:
                messages.append({
                    "role": "assistant",
                    "content": "These entities are not high priority. "
                               "Skipping to conserve budget.",
                })

        elif event_type == "correction":
            ename = event["entity_name"]
            user_msg = (
                f"=== Event {event_idx+1}/{total_events} [CORRECTION] ===\n\n"
                f"**Correction Notice:**\n{event['notice']}\n\n"
                "Update your stored memories with the corrected value."
            )
            messages.append({"role": "user", "content": user_msg})

            if ename in stored_names and ename in entity_mem_ids:
                old_mid = entity_mem_ids[ename]
                entity = world.get_entity(ename)
                compact = tmpl._compact_document(entity, world.active_attrs)
                content = f"{ename} | {compact}"
                mem_id_counter += 1
                new_mid = f"mem_{mem_id_counter:03d}"
                entity_mem_ids[ename] = new_mid

                assistant_content = (
                    f'<tool_call>{{"name": "memory_search", '
                    f'"arguments": {{"query": "{ename}"}}}}</tool_call>\n'
                    f'<tool_call>{{"name": "memory_forget", '
                    f'"arguments": {{"memory_id": "{old_mid}"}}}}</tool_call>\n'
                    f'<tool_call>{{"name": "memory_store", '
                    f'"arguments": {{"content": "{content}"}}}}</tool_call>'
                )
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({
                    "role": "user",
                    "content": (
                        f"[memory_search] [{old_mid}] {ename} | ...\n"
                        f"[memory_forget] Deleted.\n"
                        f"[memory_store] Stored (id={new_mid})."
                    ),
                })
            else:
                messages.append({
                    "role": "assistant",
                    "content": "Entity not in my memory. No update needed.",
                })

        elif event_type == "noise":
            user_msg = (
                f"=== Event {event_idx+1}/{total_events} [INFO] ===\n\n"
                f"{event['document']}\n\n"
                "This is supplementary information. "
                "Store only if relevant to your tasks."
            )
            messages.append({"role": "user", "content": user_msg})
            messages.append({
                "role": "assistant",
                "content": "This is noise/supplementary info. Skipping.",
            })

        elif event_type == "session_break":
            session_id = event.get("session_id", 2)
            total_sess = event.get("total_sessions", 2)
            user_msg = (
                f"=== Event {event_idx+1}/{total_events} "
                f"[SESSION BREAK] ===\n\n"
                f"Session {session_id}/{total_sess} begins. "
                f"Your conversation context has been reset. "
                f"Your memory backend is preserved — use "
                f"memory_search to recall stored data."
            )
            messages.append({"role": "user", "content": user_msg})
            messages.append({
                "role": "assistant",
                "content": "New session started. "
                "I'll use memory_search to recall data as needed.",
            })

        elif event_type == "question":
            user_msg = (
                f"=== Event {event_idx+1}/{total_events} [QUESTION] ===\n\n"
                f"**Question:**\n{event['question']}\n\n"
                "Search your memory and call submit_answer(answer=\"...\")."
            )
            messages.append({"role": "user", "content": user_msg})

            gt = str(event["answer"])
            required = event.get("required_entities", [])
            competency = event["competency"]

            if competency == "abstention":
                answer = "I don't have enough information"
            elif all(n in stored_names for n in required):
                answer = gt
            else:
                answer = "I don't have enough information"

            # Search then answer
            search_entity = required[0] if required else ""
            if search_entity and search_entity in stored_names:
                assistant_content = (
                    f'<tool_call>{{"name": "memory_search", '
                    f'"arguments": {{"query": "{search_entity}"}}}}</tool_call>'
                )
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({
                    "role": "user",
                    "content": f"[memory_search] Results for {search_entity}...",
                })

            messages.append({
                "role": "assistant",
                "content": (
                    f'<tool_call>{{"name": "submit_answer", '
                    f'"arguments": {{"answer": "{answer}"}}}}</tool_call>'
                ),
            })
            messages.append({
                "role": "user",
                "content": f"[submit_answer] ANSWER_SUBMITTED: {answer}",
            })

    return messages


def export_trajectories(
    n_seeds: int = 10,
    strategy: str = "perfect",
    output_dir: str = "trajectories",
    templates: list[str] | None = None,
) -> list[Path]:
    """Batch export trajectories as JSONL files.

    Format: {"messages": [...]} per line, compatible with OpenAI
    fine-tuning API.

    Returns list of output file paths.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    template_names = templates or list(TEMPLATES.keys())
    output_files = []

    for tname in template_names:
        file_path = out_path / f"{tname}_{strategy}.jsonl"
        with open(file_path, "w") as f:
            for seed in range(n_seeds):
                messages = generate_sft_trajectory(tname, seed, strategy)
                f.write(json.dumps({"messages": messages}) + "\n")
        output_files.append(file_path)

    return output_files


class MemoryEnv:
    """Step-based RL environment wrapping WorldTemplate.generate_stream().

    Interface:
        reset(seed) → observation (text description of first event)
        step(action) → (observation, reward, done, info)

    action = {"tool": "memory_store", "args": {"content": "..."}}
    reward = +1.0 for correct answer, 0.0 otherwise
    done = True when all events processed

    Does NOT depend on gym — but interface is compatible.
    """

    def __init__(
        self,
        template_name: str = "company",
        tier: str | None = None,
        seed: int = 0,
        n_entities: int | None = None,
        n_questions: int | None = None,
        n_corrections: int | None = None,
        write_budget: int | None = None,
        eval_salt: int = 0,
        reward_mode: str = "binary",
        backend_type: str = "chromadb",
    ):
        if reward_mode not in ("binary", "shaped"):
            raise ValueError(f"reward_mode must be 'binary' or 'shaped', got '{reward_mode}'")
        self.template_name = template_name
        self._default_seed = seed
        self._eval_salt = eval_salt
        self.reward_mode = reward_mode

        # Tier overrides explicit params
        if tier is not None:
            if tier not in TIERS:
                raise ValueError(
                    f"Unknown tier '{tier}'. Choose from: "
                    f"{', '.join(TIERS)}")
            tc = TIERS[tier]
            self.n_entities = n_entities or tc["entities"]
            self.n_questions = n_questions or tc["questions"]
            self.n_corrections = n_corrections or tc["corrections"]
            self.write_budget = write_budget or tc["write_budget"]
            self.n_sessions = tc.get("n_sessions", 1)
        else:
            self.n_entities = n_entities or 60
            self.n_questions = n_questions or 20
            self.n_corrections = n_corrections or 5
            self.write_budget = write_budget or 30
            self.n_sessions = 1

        self._tmpl: WorldTemplate | None = None
        self._stream: list[dict] = []
        self._event_idx: int = 0
        self._mem_counter: int = 0
        self._writes_used: int = 0
        self._questions_answered: int = 0
        self._correct_count: int = 0
        self._total_questions: int = 0
        # Shaped reward tracking
        self._correction_searched: bool = False
        self._correction_forgot: bool = False
        self._stored_entity_names: set[str] = set()

        self._backend_type = backend_type
        self._backend = self._make_backend()

    def _make_backend(self):
        """Create a fresh backend instance."""
        from memorygym.memory.backends.chromadb_backend import ChromaDBBackend
        return ChromaDBBackend(
            collection_name=f"memenv_{uuid.uuid4().hex[:8]}")

    def current_observation(self) -> str:
        """Return formatted text of the current event.

        Public API for adapters — avoids accessing _stream/_event_idx.
        """
        if self._event_idx >= len(self._stream):
            return ""
        return self._format_event(self._stream[self._event_idx])

    def _format_event(self, event: dict) -> str:
        """Format an event dict as human-readable text."""
        etype = event["type"]
        total = len(self._stream)
        idx = self._event_idx + 1

        if etype == "ingest":
            docs = event.get("documents", [])
            docs_text = "\n\n".join(
                f"[Document {i+1}]\n{d}" for i, d in enumerate(docs))
            n_ents = len(event.get("entity_names", []))
            remaining = self.write_budget - self._writes_used
            suggested = max(0, min(n_ents, remaining - self._n_corrections))
            return (
                f"=== Event {idx}/{total} [DOCUMENTS] ===\n\n"
                f"⚠️ Budget: {remaining}/{self.write_budget} writes "
                f"remaining. Corrections coming: {self._n_corrections}.\n"
                f"   Suggestion: store ≤{suggested} from this batch.\n\n"
                f"**Documents:**\n{docs_text}\n\n"
                "No question. Store important entity data."
            )
        elif etype == "correction":
            return (
                f"=== Event {idx}/{total} [CORRECTION] ===\n\n"
                f"**Correction Notice:**\n{event.get('notice', '')}\n\n"
                "Update your stored memories with the corrected value."
            )
        elif etype == "question":
            return (
                f"=== Event {idx}/{total} [QUESTION] ===\n\n"
                f"**Question:**\n{event.get('question', '')}\n\n"
                "Search your memory and call submit_answer."
            )
        elif etype == "noise":
            return (
                f"=== Event {idx}/{total} [INFO] ===\n\n"
                f"{event.get('document', '')}\n\n"
                "This is supplementary information. "
                "Store only if relevant to your tasks."
            )
        elif etype == "session_break":
            session_id = event.get("session_id", 2)
            total_sess = event.get("total_sessions", 2)
            return (
                f"=== Event {idx}/{total} [SESSION BREAK] ===\n\n"
                f"Session {session_id}/{total_sess} begins. "
                f"Your conversation context has been reset. "
                f"Your memory backend is preserved — use "
                f"memory_search to recall stored data."
            )
        return f"=== Event {idx}/{total} [DONE] ==="

    def reset(self, seed: int | None = None) -> str:
        """Reset environment. Returns first event as text observation."""
        seed = seed if seed is not None else self._default_seed
        tmpl_cls = TEMPLATES[self.template_name]
        self._tmpl = tmpl_cls()
        world = self._tmpl.generate_world(
            seed=seed, n_entities=self.n_entities,
            eval_salt=self._eval_salt)
        rng = Random(seed)
        corrections = self._tmpl.generate_corrections(
            world, rng, self.n_corrections)
        n_contras = max(1, self.n_corrections // 3)
        exclude_corrected = {c.entity_name for c in corrections}
        rng_contra = Random(seed + 7373)
        contradictions = self._tmpl.generate_contradictions(
            world, rng_contra, n_contras,
            exclude_entities=exclude_corrected)
        self._stream = self._tmpl.generate_stream(
            world, rng, corrections,
            stored_names=set(),
            n_questions=self.n_questions,
            entities_per_batch=10,
            contradictions=contradictions,
            n_sessions=self.n_sessions,
        )
        self._event_idx = 0
        self._mem_counter = 0
        # Reset backend
        self._backend = self._make_backend()
        self._writes_used = 0
        self._questions_answered = 0
        self._correct_count = 0
        self._world = world
        self._correction_searched = False
        self._correction_forgot = False
        self._stored_entity_names = set()

        # Precompute question/correction counts
        self._total_questions = sum(
            1 for e in self._stream if e["type"] == "question")
        self._n_corrections = sum(
            1 for e in self._stream if e["type"] == "correction")

        if not self._stream:
            return "No events in stream."
        return self._format_event(self._stream[0])

    def step(
        self, action: dict[str, Any],
    ) -> tuple[str, float, bool, dict[str, Any]]:
        """Execute action, return (observation, reward, done, info).

        Actions:
        - {"tool": "memory_store", "args": {"content": "..."}}
        - {"tool": "memory_search", "args": {"query": "..."}}
        - {"tool": "memory_forget", "args": {"memory_id": "..."}}
        - {"tool": "submit_answer", "args": {"answer": "..."}}
        - {"tool": "next"} — advance to next event (for ingest/correction)
        """
        tool = action.get("tool", "next")
        args = action.get("args", {})
        reward = 0.0
        info: dict[str, Any] = {}
        shaped = self.reward_mode == "shaped"
        current_event = (self._stream[self._event_idx]
                         if self._event_idx < len(self._stream) else None)
        event_type = current_event["type"] if current_event else None

        if tool == "memory_store":
            if self._writes_used >= self.write_budget:
                info["error"] = "Budget exhausted"
                if shaped:
                    reward = -0.05  # Penalty: wasted action on exhausted budget
            else:
                self._mem_counter += 1
                mid = f"mem_{self._mem_counter:03d}"
                content = args.get("content", "")
                # Coerce to string — small models may produce lists or other types
                if not isinstance(content, str):
                    content = str(content)
                self._backend.store(content, memory_id=mid)
                self._writes_used += 1
                info["memory_id"] = mid
                info["remaining"] = self.write_budget - self._writes_used

                if shaped:
                    # Reward for storing content with entity names
                    if current_event and event_type == "ingest":
                        names = current_event.get("entity_names", [])
                        matched = [n for n in names
                                   if n.lower() in content.lower()]
                        if matched:
                            # Check for duplicates
                            is_dup = any(n in self._stored_entity_names
                                         for n in matched)
                            if is_dup:
                                reward = -0.1  # Penalty: duplicate wastes budget
                            else:
                                reward = 0.3  # Good: stored new entity data
                            self._stored_entity_names.update(matched)
                    elif event_type == "correction":
                        # Storing during correction after search+forget = correction flow
                        if self._correction_searched and self._correction_forgot:
                            reward = 0.5  # Good: completed correction flow
                            self._correction_searched = False
                            self._correction_forgot = False

        elif tool == "memory_search":
            query = args.get("query", "")
            results = self._backend.search(query, top_k=5)
            info["results"] = [
                {"id": r["id"], "content": r["content"]}
                for r in results
            ]
            if shaped and event_type == "correction":
                if not self._correction_searched:
                    reward = 0.1  # Good: immediately searched after correction
                self._correction_searched = True

        elif tool == "memory_forget":
            mid = args.get("memory_id", "")
            deleted = self._backend.forget(mid)
            info["deleted"] = deleted
            if deleted and shaped and event_type == "correction":
                self._correction_forgot = True

        elif tool == "submit_answer":
            answer = args.get("answer", "")
            event = self._stream[self._event_idx]
            if event["type"] == "question":
                gt = str(event["answer"])
                competency = event["competency"]
                is_correct = _VALIDATOR.validate(answer, gt, competency)
                reward = 1.0 if is_correct else 0.0
                info["correct"] = is_correct
                info["ground_truth"] = gt
                self._questions_answered += 1
                if is_correct:
                    self._correct_count += 1
            # Advance after answering
            self._event_idx += 1

        elif tool == "next":
            # Reset correction tracking when advancing past a correction event
            if shaped and event_type == "correction":
                self._correction_searched = False
                self._correction_forgot = False
            self._event_idx += 1

        done = self._event_idx >= len(self._stream)

        # Episode stats always included
        info["episode_stats"] = {
            "writes_used": self._writes_used,
            "budget_remaining": self.write_budget - self._writes_used,
            "questions_answered": self._questions_answered,
            "correct_count": self._correct_count,
            "total_questions": self._total_questions,
        }

        if done:
            obs = "Episode complete."
        else:
            obs = self._format_event(self._stream[self._event_idx])
        return obs, reward, done, info

    def get_verifiable_reward(self) -> float:
        """Episode accuracy for GRPO outcome reward.

        Returns correct_count / total_questions plus efficiency bonus in
        shaped mode. Shaped per-step rewards are orthogonal to this.
        """
        if self._total_questions == 0:
            return 0.0
        base = self._correct_count / self._total_questions
        # Efficiency bonus: reward high info-density per write
        if self.reward_mode == "shaped" and self._writes_used > 0:
            unique_stored = len(self._stored_entity_names)
            efficiency_bonus = min(unique_stored / self._writes_used, 1.0) * 0.2
            base += efficiency_bonus
        return base
