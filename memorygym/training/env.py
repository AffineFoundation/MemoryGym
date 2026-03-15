"""Training data interfaces: SFT trajectories and RL environment.

Generate training data from deterministic simulation strategies,
using the same WorldTemplate infrastructure as evaluation.
"""

from __future__ import annotations

import copy
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
    - ingest: Write calls for each stored entity
    - correction: memory_search + Edit
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
    world = tmpl.generate_world(seed=seed, n_entities=n_entities, eval_salt=1)
    rng = Random(seed)

    # Determine store ratio from strategy name
    store_ratio = 1.0 if strategy == "perfect" else 0.7
    applies_updates = True

    # Render documents
    rng_doc = Random(seed)
    all_docs = [(e, tmpl.render_document(e, world.active_attrs, rng_doc))
                for e in world.entities]

    # Storage decision — cap at write_budget to avoid teaching "ignore budget"
    rng_store = Random(seed + 111)
    if store_ratio >= 1.0:
        # Perfect: rank by importance, take top write_budget
        ranked = sorted(
            range(len(all_docs)),
            key=lambda i: tmpl.entity_importance(all_docs[i][0], world),
            reverse=True,
        )
        stored_indices = sorted(ranked[:write_budget])
    else:
        n_store = min(max(1, int(len(all_docs) * store_ratio)), write_budget)
        stored_indices = sorted(
            rng_store.sample(range(len(all_docs)), n_store))

    stored_names = {all_docs[i][0].name for i in stored_indices}

    # Save original attrs before corrections mutate them
    original_attrs = {e.name: copy.deepcopy(e.attrs) for e in world.entities}

    # Generate corrections (mutates world)
    rng_correct = Random(seed + 3333)
    corrections = tmpl.generate_corrections(world, rng_correct, n_corrections)

    # Ensure corrected entities are stored so SFT demonstrates Edit flow.
    # Swap in corrected entities, evicting lowest-importance stored entities.
    corrected_not_stored = [
        c.entity_name for c in corrections
        if c.entity_name not in stored_names
    ]
    if corrected_not_stored:
        # Rank stored entities by importance (ascending) for eviction
        name_to_importance = {
            all_docs[i][0].name: tmpl.entity_importance(all_docs[i][0], world)
            for i in range(len(all_docs))
        }
        evictable = sorted(
            [n for n in stored_names if n not in {c.entity_name for c in corrections}],
            key=lambda n: name_to_importance.get(n, 0),
        )
        for cname in corrected_not_stored:
            if len(stored_names) >= write_budget and evictable:
                stored_names.discard(evictable.pop(0))
            stored_names.add(cname)

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
    # Corrections fired before entity was ingested — store corrected vals
    fired_corrections: dict[str, list[dict]] = {}

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
                # If correction already fired for this entity, use corrected
                # values (current entity.attrs). Otherwise restore original.
                if ename not in fired_corrections:
                    saved = {}
                    if ename in original_attrs:
                        for attr, val in entity.attrs.items():
                            if attr in original_attrs[ename] and val != original_attrs[ename][attr]:
                                saved[attr] = val
                                entity.attrs[attr] = original_attrs[ename][attr]
                    compact = tmpl._compact_document(entity, world.active_attrs)
                    for attr, val in saved.items():
                        entity.attrs[attr] = val
                else:
                    # Correction seen before ingest — store latest values
                    compact = tmpl._compact_document(entity, world.active_attrs)
                content = f"{ename} | {compact}"
                mem_id_counter += 1
                mid = f"mem_{mem_id_counter:03d}"
                entity_mem_ids[ename] = mid
                tool_calls.append(
                    f'<tool_call>{{"name": "Write", '
                    f'"arguments": {{"content": {json.dumps(content)}}}}}</tool_call>'
                )

            if tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": "\n".join(tool_calls),
                })
                messages.append({
                    "role": "user",
                    "content": "\n".join(
                        f"[Write] Written. "
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
            old_val_str = str(event.get("old_val", ""))
            new_val_str = str(event.get("new_val", ""))
            user_msg = (
                f"=== Event {event_idx+1}/{total_events} [CORRECTION] ===\n\n"
                f"**Correction Notice:**\n{event['notice']}\n\n"
                f"Entity: {ename}\n"
                f"Old value: {old_val_str}\n"
                f"New value: {new_val_str}\n\n"
                f"If you stored data about this entity, use memory_search "
                f"to find it and Edit to update. "
                f"Correction edits do not consume your write budget."
            )
            messages.append({"role": "user", "content": user_msg})

            if ename in stored_names and ename in entity_mem_ids:
                old_val = str(event.get("old_val", ""))
                new_val = str(event.get("new_val", ""))

                assistant_content = (
                    f'<tool_call>{{"name": "memory_search", '
                    f'"arguments": {{"query": {json.dumps(ename)}}}}}</tool_call>\n'
                    f'<tool_call>{{"name": "Edit", '
                    f'"arguments": {{"old_text": {json.dumps(old_val)}, '
                    f'"new_text": {json.dumps(new_val)}}}}}</tool_call>'
                )
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({
                    "role": "user",
                    "content": (
                        f"[memory_search] {ename} | ...\n"
                        f"[Edit] Edited. Budget remaining."
                    ),
                })
            else:
                # Entity not yet ingested — track so ingest uses corrected vals
                fired_corrections.setdefault(ename, []).append(event)
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
                    f'"arguments": {{"query": {json.dumps(search_entity)}}}}}</tool_call>'
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
                    f'"arguments": {{"answer": {json.dumps(answer)}}}}}</tool_call>'
                ),
            })
            messages.append({
                "role": "user",
                "content": f"[submit_answer] ANSWER_SUBMITTED: {answer}",
            })

    # Merge consecutive same-role messages (SFT trainers require strict
    # user/assistant alternation; tool results followed by next event
    # creates consecutive user messages).
    merged: list[dict] = [messages[0]]  # system prompt
    for msg in messages[1:]:
        if merged and msg["role"] == merged[-1]["role"]:
            merged[-1]["content"] += "\n\n---\n\n" + msg["content"]
        else:
            merged.append(msg)
    return merged


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

    action = {"tool": "Write", "args": {"content": "..."}}
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

    def close(self) -> None:
        """Clean up backend resources."""
        if self._backend is not None and hasattr(self._backend, "close"):
            self._backend.close()
            self._backend = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _make_backend(self):
        """Create a fresh backend instance."""
        if self._backend_type == "markdown":
            from memorygym.memory.backends.markdown_backend import MarkdownBackend
            return MarkdownBackend()
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
            remaining = self.write_budget - self._writes_used
            return (
                f"=== Event {idx}/{total} [DOCUMENTS] ===\n\n"
                f"⚠️ Budget: {remaining}/{self.write_budget} writes "
                f"remaining. Be selective — store what matters most.\n\n"
                f"**Documents:**\n{docs_text}\n\n"
                "No question. Store important entity data."
            )
        elif etype == "correction":
            remaining = self.write_budget - self._writes_used
            return (
                f"=== Event {idx}/{total} [CORRECTION] ===\n\n"
                f"**Correction Notice:**\n{event.get('notice', '')}\n\n"
                f"A correction has been issued. Decide how to handle it.\n"
                f"Budget: {remaining} writes remaining."
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
        rng_correct = Random(seed + 3333)
        corrections = self._tmpl.generate_corrections(
            world, rng_correct, self.n_corrections)
        n_contras = max(1, self.n_corrections // 3)
        exclude_corrected = {c.entity_name for c in corrections}
        rng_contra = Random(seed + 7373)
        contradictions = self._tmpl.generate_contradictions(
            world, rng_contra, n_contras,
            exclude_entities=exclude_corrected)
        rng_stream = Random(seed + 5555)
        self._stream = self._tmpl.generate_stream(
            world, rng_stream, corrections,
            stored_names=set(),
            n_questions=self.n_questions,
            entities_per_batch=10,
            contradictions=contradictions,
            n_sessions=self.n_sessions,
        )
        self._event_idx = 0
        self._mem_counter = 0
        # Clean up old backend before creating new one
        if self._backend is not None and hasattr(self._backend, "close"):
            self._backend.close()
        self._backend = self._make_backend()
        self._writes_used = 0
        self._questions_answered = 0
        self._correct_count = 0
        self._by_competency: dict[str, list[bool]] = {}
        self._world = world
        self._correction_searched = False
        self._correction_forgot = False
        self._stored_entity_names = set()

        # Precompute question/correction counts
        self._total_questions = sum(
            1 for e in self._stream if e["type"] == "question")
        self._n_corrections = sum(
            1 for e in self._stream if e["type"] == "correction")

        # F43 (ReMemR1): precompute which entities will be questioned
        # Used for information-gain shaped reward — storing questioned
        # entities is more valuable than storing unquestioned ones.
        self._questioned_entities: set[str] = set()
        for e in self._stream:
            if e["type"] == "question":
                for name in e.get("required_entities", []):
                    self._questioned_entities.add(name)

        if not self._stream:
            return "No events in stream."
        return self._format_event(self._stream[0])

    def step(
        self, action: dict[str, Any],
    ) -> tuple[str, float, bool, dict[str, Any]]:
        """Execute action, return (observation, reward, done, info).

        Actions:
        - {"tool": "Write", "args": {"content": "..."}}
        - {"tool": "Edit", "args": {"old_text": "...", "new_text": "..."}}
        - {"tool": "Read", "args": {}}
        - {"tool": "memory_search", "args": {"query": "..."}}
        - {"tool": "submit_answer", "args": {"answer": "..."}}
        - {"tool": "next"} — advance to next event (for ingest/correction)
        Legacy names (memory_store, memory_forget) accepted for compatibility.
        """
        tool = action.get("tool", "next")
        args = action.get("args", {})
        reward = 0.0
        info: dict[str, Any] = {}
        shaped = self.reward_mode == "shaped"
        current_event = (self._stream[self._event_idx]
                         if self._event_idx < len(self._stream) else None)
        event_type = current_event["type"] if current_event else None

        if tool in ("Write", "memory_store"):
            content = args.get("content", "")
            if not isinstance(content, str):
                content = str(content)
            if len(content) > 2000:
                info["error"] = "Content exceeds 2000 character limit"
            elif self._writes_used >= self.write_budget:
                info["error"] = "Budget exhausted"
                if shaped:
                    reward = -0.05  # Penalty: wasted action on exhausted budget
            else:
                self._mem_counter += 1
                mid = f"mem_{self._mem_counter:03d}"
                if hasattr(self._backend, "write"):
                    self._backend.write(content)
                else:
                    self._backend.store(content, memory_id=mid)
                self._writes_used += 1
                info["memory_id"] = mid
                info["remaining"] = self.write_budget - self._writes_used

                if shaped:
                    # F41 (ToolRLA): multiplicative reward decomposition
                    # One zero factor → zero total reward, preventing
                    # gaming any single dimension.
                    # F43 (ReMemR1): information gain — entities that will
                    # be questioned are worth more than unquestioned ones.
                    if current_event and event_type == "ingest":
                        names = current_event.get("entity_names", [])
                        matched = [n for n in names
                                   if n.lower() in content.lower()]
                        if matched:
                            new_names = [n for n in matched
                                         if n not in self._stored_entity_names]
                            if not new_names:
                                # All duplicates: novelty=0 → penalty
                                reward = -0.1
                            else:
                                # Base reward for storing new entity data
                                reward = 0.3
                                # F43: info gain bonus for questioned entities
                                n_questioned = sum(
                                    1 for n in new_names
                                    if n in self._questioned_entities)
                                if n_questioned > 0:
                                    reward = 0.5  # Higher reward: will be useful
                                # Multi-entity packing bonus (F16/OTC)
                                if len(new_names) > 1:
                                    reward += 0.1 * (len(new_names) - 1)
                            self._stored_entity_names.update(matched)

        elif tool == "Edit":
            old_text = args.get("old_text", "")
            new_text = args.get("new_text", "")
            is_correction = event_type == "correction"
            if not old_text:
                info["error"] = "old_text is required"
            elif not is_correction and self._writes_used >= self.write_budget:
                info["error"] = "Budget exhausted"
                if shaped:
                    reward = -0.05
            else:
                if not is_correction:
                    self._writes_used += 1  # Consume upfront (match eval)
                if hasattr(self._backend, "edit"):
                    ok = self._backend.edit(old_text, new_text)
                    if not ok:
                        if not is_correction:
                            self._writes_used -= 1  # Refund on miss
                        info["edited"] = False
                        info["error"] = "Text not found in memory"
                    else:
                        info["edited"] = True
                        info["remaining"] = (self.write_budget
                                             - self._writes_used)
                        if shaped and is_correction:
                            # F41: multiplicative — correct value is required
                            corr_new = str(current_event.get("new_val", ""))
                            if corr_new in new_text:
                                # Correct value: full reward, bonus if searched
                                reward = 0.6 if self._correction_searched else 0.5
                            else:
                                # Wrong value: value_factor=0 → reward near zero
                                reward = 0.1
                else:
                    # Fallback for ChromaDB: search + forget + store
                    results = self._backend.search(old_text, top_k=1)
                    if results and old_text in results[0]["content"]:
                        self._backend.forget(results[0]["id"])
                        updated = results[0]["content"].replace(
                            old_text, new_text, 1)
                        self._mem_counter += 1
                        mid = f"mem_{self._mem_counter:03d}"
                        self._backend.store(updated, memory_id=mid)
                        info["edited"] = True
                        info["remaining"] = (self.write_budget
                                             - self._writes_used)
                        if shaped and is_correction:
                            corr_new = str(current_event.get("new_val", ""))
                            if corr_new in new_text:
                                reward = 0.6 if self._correction_searched else 0.5
                            else:
                                reward = 0.1
                    else:
                        if not is_correction:
                            self._writes_used -= 1  # Refund on miss
                        info["edited"] = False
                        info["error"] = "Text not found in memory"

        elif tool == "Read":
            if hasattr(self._backend, "read"):
                start = args.get("start_line")
                n = args.get("num_lines")
                content = self._backend.read(start_line=start, num_lines=n)
                info["content"] = content if content else ""
            else:
                entries = self._backend.list()
                info["content"] = "\n".join(
                    e["content"] for e in entries) if entries else ""

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
            if current_event is None:
                info["error"] = "No current event to answer"
                return self._make_obs(), reward, True, info
            event = current_event
            if event["type"] == "question":
                gt = str(event["answer"])
                competency = event["competency"]
                is_correct = _VALIDATOR.validate(answer, gt, competency)
                reward = 1.0 if is_correct else 0.0
                info["correct"] = is_correct
                info["ground_truth"] = gt
                self._questions_answered += 1
                self._by_competency.setdefault(competency, []).append(
                    is_correct)
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
        """Episode reward using 4-axis composite (aligned with eval scoring).

        Uses compute_axis_scores() for consistent reward signal between
        RL training and real evaluation.
        """
        from ..protocol import compute_axis_scores

        if self._total_questions == 0:
            return 0.0
        scores = compute_axis_scores(
            by_competency=self._by_competency,
            n_entities=self.n_entities,
            stored_count=len(self._stored_entity_names),
            writes_used=self._writes_used,
            write_budget=self.write_budget,
        )
        return scores["composite"]
