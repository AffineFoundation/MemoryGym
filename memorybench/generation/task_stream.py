"""Task stream generation: builds the 25-task sequence for evaluation."""

from __future__ import annotations

import hashlib
import random
from collections import Counter

from memorybench.config import EvalConfig, task_global_id
from memorybench.domains.base import Domain, Entity, Task
from memorybench.evaluation.validators import resolve_entity_name
from memorybench.generation.questions import gen_crossdomain_question, gen_question
from memorybench.generation.scenario import select_domains


# Correction deltas per attribute
DELTA_MAP = {
    "salary": 15000, "age": 2, "performance": 0.5,
    "experience": 3, "team_size": 2,
    "citations": 200, "h_index": 5, "funding": 100000,
    "students": 2, "review_score": 0.5, "papers_count": 10,
    "unit_price": 20.0, "weight_kg": 2.0, "lead_time_days": 5,
    "defect_rate": 1.0, "demand_forecast": 200, "stock_level": 100,
}

# Clamp ranges per attribute (min, max) for perturbed values
_ATTR_RANGES: dict[str, tuple[float, float]] = {
    "salary": (20000, 500000), "age": (18, 80), "performance": (0.0, 10.0),
    "experience": (0, 50), "team_size": (1, 100),
    "citations": (0, 50000), "h_index": (0, 150), "funding": (0, 5_000_000),
    "students": (0, 100), "review_score": (0.0, 10.0), "papers_count": (0, 500),
    "unit_price": (0.01, 10000.0), "weight_kg": (0.01, 5000.0),
    "lead_time_days": (1, 365), "defect_rate": (0.0, 100.0),
    "demand_forecast": (0, 100000), "stock_level": (0, 100000),
}


def _stable_hash_str(s: str) -> int:
    """Deterministic hash using SHA-256, independent of PYTHONHASHSEED."""
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)


def _clamp_attr(attr: str, value: float) -> float:
    """Clamp a perturbed attribute value to its valid range."""
    lo, hi = _ATTR_RANGES.get(attr, (float("-inf"), float("inf")))
    return max(lo, min(hi, value))


def _perturb_kb(kb: dict, domain_name: str, eval_salt: int) -> None:
    """Apply eval-time numerical perturbation to KB attribute values.

    When eval_salt != 0, adds noise exceeding DELTA_MAP × 1.5 to each
    numeric attribute, making pre-computed answers from seed alone invalid.
    Mutates entity attrs in place.
    """
    if eval_salt == 0:
        return
    for entity in kb["entities"]:
        for attr in kb["active_attrs"]:
            val = entity.get(attr)
            if val is None or not isinstance(val, (int, float)):
                continue
            key = f"{entity.name}:{attr}:{domain_name}"
            h = _stable_hash_str(key)
            rng = random.Random(eval_salt ^ h)
            delta = DELTA_MAP.get(attr, 1)
            noise_magnitude = delta * 1.5
            noise = rng.uniform(-noise_magnitude, noise_magnitude)
            # Ensure noise exceeds validator tolerance (5% of value)
            min_noise = abs(val) * 0.06 + delta * 0.5
            if abs(noise) < min_noise:
                noise = min_noise if noise >= 0 else -min_noise
            if isinstance(val, int):
                new_val = int(round(_clamp_attr(attr, val + noise)))
            else:
                new_val = round(_clamp_attr(attr, val + noise), 2)
            entity.attrs[attr] = new_val


def generate_stream(
    seed: int,
    config: EvalConfig | None = None,
    eval_salt: int = 0,
) -> tuple[list[Task], dict, dict, dict[str, Domain], int | None]:
    """Generate a multi-domain task stream.

    Returns:
        (tasks, updates, kbs, dom_map, domain_switch_point)
    """
    if config is None:
        config = EvalConfig()

    rng = random.Random(seed + 5000)
    domains = select_domains(seed, config.n_domains)
    dom_a, dom_b = domains

    # Each domain gets a unique seed so entity names don't collide.
    kb_a = dom_a.generate_kb(seed + dom_a._stable_hash(dom_a.name),
                             config.n_entities_per_domain)
    kb_b = dom_b.generate_kb(seed + dom_b._stable_hash(dom_b.name),
                             config.n_entities_per_domain)

    # Eval-time perturbation: invalidates pre-computed answers from seed
    _perturb_kb(kb_a, dom_a.name, eval_salt)
    _perturb_kb(kb_b, dom_b.name, eval_salt)

    kbs = {dom_a.name: kb_a, dom_b.name: kb_b}
    dom_map = {dom_a.name: dom_a, dom_b.name: dom_b}

    # Generate distractors per domain
    distractors = {
        dom_a.name: dom_a.generate_distractors(rng, kb_a["entities"]),
        dom_b.name: dom_b.generate_distractors(rng, kb_b["entities"]),
    }

    updates = _plan_updates(rng, dom_a, kb_a, dom_b, kb_b)
    tasks, switch_pt = _build_tasks(
        rng, config, dom_a, dom_b, kbs, dom_map, updates, distractors, seed,
    )

    # Answerability check: verify every question's required entities
    # appear in at least one document in the stream.
    _answerability_check(tasks, kbs)

    return tasks, updates, kbs, dom_map, switch_pt


def _plan_updates(rng, dom_a, kb_a, dom_b, kb_b) -> dict:
    """Plan correction updates for both domains.

    Captures old values at plan time; entity attrs are NOT modified here.
    Documents will render with old values, corrections apply later.
    """
    updates = {}
    for dom, kb, base_task in [(dom_a, kb_a, 6), (dom_b, kb_b, 17)]:
        targets = rng.sample(kb["entities"][:8], min(2, len(kb["entities"])))
        for i, e in enumerate(targets):
            attr = rng.choice(kb["active_attrs"])
            old_val = e.get(attr)
            if old_val is None:
                continue
            delta = DELTA_MAP.get(attr, 1)
            sign = rng.choice([-1, 1])
            if isinstance(old_val, float):
                new_val = round(old_val + sign * delta, 2)
            else:
                new_val = old_val + sign * int(delta)
            updates[e.name] = {
                "attr": attr, "old": old_val, "new": new_val,
                "apply_at_task": base_task + i, "applied": False,
                "domain": dom.name,
            }
    return updates


def _build_tasks(rng, config, dom_a, dom_b, kbs, dom_map, updates,
                 distractors, seed):
    """Build the task stream with phased domain assignments."""
    exposed = {dom_a.name: [], dom_b.name: []}
    entity_idx = {dom_a.name: 0, dom_b.name: 0}
    distractor_idx = {dom_a.name: 0, dom_b.name: 0}
    entity_intro_task: dict[str, int] = {}  # entity name → task_id introduced
    seen_questions: set[str] = set()
    tasks = []
    switch_pt = None

    for tid in range(config.n_tasks):
        # Phase assignment
        if tid < 10:
            dom = dom_a
        elif tid < 12:
            dom = dom_a  # deep phase: updates + hard questions
        elif tid < 20:
            if switch_pt is None:
                switch_pt = tid
            dom = dom_b
        else:
            dom = rng.choice([dom_a, dom_b])  # pressure phase: mixed

        kb = kbs[dom.name]
        active = kb["active_attrs"]
        primary = kb["primary_attr"]

        docs = []
        new_names = []

        # Introduce new entities
        idx = entity_idx[dom.name]
        n_new = min(2, len(kb["entities"]) - idx)
        for _ in range(n_new):
            e = kb["entities"][idx]
            docs.append(dom.render_entity_doc(e, active, rng))
            new_names.append(e.name)
            exposed[dom.name].append(e)
            entity_intro_task[e.name] = tid
            idx += 1
        entity_idx[dom.name] = idx

        # Background noise
        docs.append(rng.choice(dom.BACKGROUND))

        # Mix in distractor documents (~1 per task if available)
        d_idx = distractor_idx[dom.name]
        dom_distractors = distractors.get(dom.name, [])
        if d_idx < len(dom_distractors):
            docs.append(dom_distractors[d_idx].content)
            distractor_idx[dom.name] = d_idx + 1

        # Render correction notice FIRST, then apply update to entity.
        # This ensures entity docs rendered earlier used old values,
        # and GT (from entity.attrs) reflects the updated state.
        for name, upd in updates.items():
            if upd["apply_at_task"] == tid and upd["domain"] == dom.name:
                e = next(
                    (ent for ent in kb["entities"] if ent.name == name), None
                )
                if e:
                    docs.append(dom.render_correction(
                        e, upd["attr"], upd["old"], upd["new"]))
                    e.attrs[upd["attr"]] = upd["new"]
                    upd["applied"] = True

        rng.shuffle(docs)

        # Generate question (with dedup)
        q = None
        if tid >= 20 and rng.random() < config.cross_domain_prob:
            q = gen_crossdomain_question(
                rng, dom_a, dom_b, exposed[dom_a.name],
                exposed[dom_b.name], kbs,
            )
            if q and q.question in seen_questions:
                q = None
            elif q:
                seen_questions.add(q.question)
        if q is None:
            q = gen_question(
                tid, rng, dom, exposed[dom.name], active, primary,
                updates, seen_questions,
            )
        gid = task_global_id(seed, tid, config.n_tasks)
        tasks.append(Task(tid, dom.name, docs, q, new_names, gid))

    # Post-hoc fixup: balance competency distribution toward target ratios.
    # Uses a separate RNG to avoid disrupting the main generation chain.
    rng_fixup = random.Random(seed + 88888)
    _balance_distribution(
        tasks, rng_fixup, dom_a, dom_b, kbs, dom_map,
        exposed, updates, seen_questions, entity_intro_task,
    )

    return tasks, switch_pt


def _balance_distribution(tasks, rng, dom_a, dom_b, kbs, dom_map,
                          exposed, updates, seen_questions, entity_intro_task):
    """Replace questions to balance competency distribution toward targets.

    Target counts (out of 25 tasks):
      retrieval ≈ 10, synthesis ≈ 6, abstention ≈ 3, update ≈ 3, cross_domain ≈ 2
    Enforces both minimums and maximums, processing in order of strictest
    eligibility window first.
    """
    # Target counts per competency
    TARGETS = {
        "cross_domain": 2, "abstention": 3, "update": 3,
        "synthesis": 6, "retrieval": 10,
    }

    counts = Counter(
        t.question.competency for t in tasks if t.question
    )

    # Compute the last correction task per domain for update eligibility.
    last_correction = {}
    for u in updates.values():
        d = u["domain"]
        last_correction[d] = max(last_correction.get(d, -1),
                                 u["apply_at_task"])

    # --- Pass 1: Bring under-represented competencies up to target ---

    # 1. Cross-domain (strictest window: tasks 18+)
    shortfall = TARGETS["cross_domain"] - counts.get("cross_domain", 0)
    if shortfall > 0:
        replaceable = _find_replaceable(tasks, min_tid=18, allow_all=True)
        for t in replaceable:
            if shortfall <= 0:
                break
            tid = t.task_id
            filtered_a = [e for e in exposed[dom_a.name]
                          if entity_intro_task.get(e.name, 999) <= tid]
            filtered_b = [e for e in exposed[dom_b.name]
                          if entity_intro_task.get(e.name, 999) <= tid]
            new_q = gen_crossdomain_question(
                rng, dom_a, dom_b, filtered_a, filtered_b, kbs,
            )
            if new_q and new_q.question not in seen_questions:
                seen_questions.add(new_q.question)
                old_comp = t.question.competency
                t.question = new_q
                counts["cross_domain"] += 1
                counts[old_comp] -= 1
                shortfall -= 1

    # 2. Abstention (eligible tasks 10+)
    shortfall = TARGETS["abstention"] - counts.get("abstention", 0)
    if shortfall > 0:
        replaceable = _find_replaceable(tasks, min_tid=10)
        for t in replaceable:
            if shortfall <= 0:
                break
            dom = dom_map[t.domain]
            active = kbs[t.domain]["active_attrs"]
            new_q = dom.gen_abstention_question(rng, exposed[t.domain], active)
            if new_q and new_q.question not in seen_questions:
                seen_questions.add(new_q.question)
                old_comp = t.question.competency
                t.question = new_q
                counts["abstention"] += 1
                counts[old_comp] -= 1
                shortfall -= 1

    # 3. Update (eligible after corrections applied per domain)
    shortfall = TARGETS["update"] - counts.get("update", 0)
    if shortfall > 0:
        replaceable = _find_replaceable(
            tasks, min_tid=0,
            extra_filter=lambda t: t.task_id > last_correction.get(t.domain, 999),
        )
        for t in replaceable:
            if shortfall <= 0:
                break
            dom = dom_map[t.domain]
            new_q = dom.gen_update_question(rng, exposed[t.domain], updates)
            if new_q and new_q.question not in seen_questions:
                seen_questions.add(new_q.question)
                old_comp = t.question.competency
                t.question = new_q
                counts["update"] += 1
                counts[old_comp] -= 1
                shortfall -= 1

    # 4. Synthesis (eligible tasks 3+, need ≥2 exposed entities)
    shortfall = TARGETS["synthesis"] - counts.get("synthesis", 0)
    if shortfall > 0:
        replaceable = _find_replaceable(tasks, min_tid=3)
        for t in replaceable:
            if shortfall <= 0:
                break
            dom = dom_map[t.domain]
            active = kbs[t.domain]["active_attrs"]
            primary = kbs[t.domain]["primary_attr"]
            # Only use entities introduced at or before this task
            avail = [e for e in exposed[t.domain]
                     if entity_intro_task.get(e.name, 999) <= t.task_id]
            if len(avail) < 2:
                continue
            new_q = dom.gen_synthesis_question(rng, avail, active, primary)
            if new_q and new_q.question not in seen_questions:
                seen_questions.add(new_q.question)
                old_comp = t.question.competency
                t.question = new_q
                counts["synthesis"] += 1
                counts[old_comp] -= 1
                shortfall -= 1

    # --- Pass 1.5: Replace ~2 retrieval questions with trick retrieval ---
    # Trick retrieval: phrased like abstention but answer is a real value.
    # This defeats always-abstain guessers.
    n_trick = 2
    retrieval_for_trick = [
        t for t in tasks
        if t.question and t.question.competency == "retrieval"
        and t.task_id >= 5
        and not t.question.is_fallback
    ]
    rng2 = rng  # reuse the fixup rng
    for t in retrieval_for_trick:
        if n_trick <= 0:
            break
        dom = dom_map[t.domain]
        active = kbs[t.domain]["active_attrs"]
        primary = kbs[t.domain]["primary_attr"]
        avail = [e for e in exposed[t.domain]
                 if entity_intro_task.get(e.name, 999) <= t.task_id]
        new_q = dom.gen_trick_retrieval_question(rng2, avail, active, primary)
        if new_q and new_q.question not in seen_questions:
            seen_questions.add(new_q.question)
            t.question = new_q
            # Competency stays "retrieval" — count unchanged
            n_trick -= 1

    # --- Pass 2: Trim over-represented competencies down to target + 2 ---
    # Only trim retrieval (most common fallback) by converting excess to
    # synthesis, which is the most broadly eligible competency.
    max_retrieval = TARGETS["retrieval"] + 2
    excess = counts.get("retrieval", 0) - max_retrieval
    if excess > 0:
        retrieval_tasks = [
            t for t in tasks
            if t.question and t.question.competency == "retrieval"
            and t.task_id >= 3
        ]
        # Replace from the end (later tasks) first
        retrieval_tasks.sort(key=lambda t: -t.task_id)
        for t in retrieval_tasks:
            if excess <= 0:
                break
            dom = dom_map[t.domain]
            active = kbs[t.domain]["active_attrs"]
            primary = kbs[t.domain]["primary_attr"]
            avail = [e for e in exposed[t.domain]
                     if entity_intro_task.get(e.name, 999) <= t.task_id]
            if len(avail) < 2:
                continue
            new_q = dom.gen_synthesis_question(rng, avail, active, primary)
            if new_q and new_q.question not in seen_questions:
                seen_questions.add(new_q.question)
                t.question = new_q
                counts["retrieval"] -= 1
                counts["synthesis"] += 1
                excess -= 1


def _find_replaceable(tasks, min_tid=0, extra_filter=None, allow_all=False):
    """Find tasks whose questions can be replaced.

    By default, only retrieval/synthesis are replaceable.
    With allow_all=True, any competency is replaceable (prefers retrieval/synthesis).
    """
    allowed = None if allow_all else ("retrieval", "synthesis")
    candidates = [
        t for t in tasks
        if t.task_id >= min_tid and t.question
        and (allowed is None or t.question.competency in allowed)
        and (extra_filter is None or extra_filter(t))
    ]
    # Priority: retrieval > synthesis > others
    _priority = {"retrieval": 0, "synthesis": 1}
    candidates.sort(key=lambda t: (_priority.get(t.question.competency, 2),
                                   t.task_id))
    return candidates


def _answerability_check(tasks: list[Task], kbs: dict) -> None:
    """Verify every question's required entities appear in the documents.

    Raises AssertionError if any question references an entity whose name
    cannot be found in the task stream's documents.
    """
    all_doc_text = "\n".join(
        doc for task in tasks for doc in task.documents
    )
    entity_names = {
        e.name for kb in kbs.values() for e in kb["entities"]
    }

    for task in tasks:
        if task.question is None:
            continue
        for req_name in task.question.required_entities:
            resolved = resolve_entity_name(req_name, entity_names)
            assert resolved in all_doc_text, (
                f"Answerability failure: entity '{resolved}' required by "
                f"question '{task.question.question}' not found in documents"
            )
