"""Question generation logic for task streams."""

from __future__ import annotations

import random

from memorybench.domains.base import Domain, Entity, QA


def gen_question(tid: int, rng: random.Random, dom: Domain,
                 exposed: list[Entity], active: list[str],
                 primary: str, updates: dict,
                 seen: set[str] | None = None) -> QA | None:
    """Generate a unique question for a task. Oversamples 3x and deduplicates."""
    for _ in range(3):
        q = _gen_question_inner(tid, rng, dom, exposed, active, primary, updates)
        if q is None:
            return None
        if seen is None or q.question not in seen:
            if seen is not None:
                seen.add(q.question)
            return q
    return q  # Return last attempt if all 3 are duplicates


def _gen_question_inner(tid: int, rng: random.Random, dom: Domain,
                        exposed: list[Entity], active: list[str],
                        primary: str, updates: dict) -> QA | None:
    """Generate a question for a task based on phase and randomness."""
    if len(exposed) < 2:
        return dom.gen_retrieval_question(rng, exposed, active, primary)

    if tid <= 2:
        return dom.gen_retrieval_question(rng, exposed, active, primary)

    has_updates = any(
        u["applied"] and u["domain"] == dom.name for u in updates.values()
    )

    roll = rng.random()
    if tid >= 18:
        if roll < 0.4:
            return _try_or_fallback(
                dom.gen_synthesis_question(rng, exposed, active, primary),
                dom, rng, exposed, active, primary)
        elif roll < 0.65:
            return _try_or_fallback(
                dom.gen_abstention_question(rng, exposed, active),
                dom, rng, exposed, active, primary)
        elif roll < 0.85 and has_updates:
            return _try_or_fallback(
                dom.gen_update_question(rng, exposed, updates),
                dom, rng, exposed, active, primary)
        else:
            return dom.gen_retrieval_question(rng, exposed, active, primary)
    else:
        if roll < 0.35:
            return dom.gen_retrieval_question(rng, exposed, active, primary)
        elif roll < 0.65:
            return _try_or_fallback(
                dom.gen_synthesis_question(rng, exposed, active, primary),
                dom, rng, exposed, active, primary)
        elif roll < 0.85 and has_updates:
            return _try_or_fallback(
                dom.gen_update_question(rng, exposed, updates),
                dom, rng, exposed, active, primary)
        else:
            return dom.gen_retrieval_question(rng, exposed, active, primary)


def _try_or_fallback(q: QA | None, dom: Domain, rng: random.Random,
                     exposed: list[Entity], active: list[str],
                     primary: str) -> QA | None:
    """Return q if not None, otherwise generate retrieval and mark as fallback."""
    if q is not None:
        return q
    q = dom.gen_retrieval_question(rng, exposed, active, primary)
    if q is not None:
        q.is_fallback = True
    return q


def gen_crossdomain_question(
    rng: random.Random, dom_a: Domain, dom_b: Domain,
    exposed_a: list[Entity], exposed_b: list[Entity],
    kbs: dict,
) -> QA | None:
    """Generate a question requiring info from both domains.

    Type: "Between entity_a's attr_a and entity_b's attr_b, which is larger?"
    Both values must be numeric for comparison.
    """
    if len(exposed_a) < 2 or len(exposed_b) < 2:
        return None

    active_a = kbs[dom_a.name]["active_attrs"]
    active_b = kbs[dom_b.name]["active_attrs"]

    numeric_a = [a for a in active_a
                 if isinstance(exposed_a[0].get(a), (int, float))]
    numeric_b = [a for a in active_b
                 if isinstance(exposed_b[0].get(a), (int, float))]

    if not numeric_a or not numeric_b:
        return None

    attr_a = rng.choice(numeric_a)
    attr_b = rng.choice(numeric_b)

    cands_a = [e for e in exposed_a if e.get(attr_a) is not None]
    cands_b = [e for e in exposed_b if e.get(attr_b) is not None]
    if not cands_a or not cands_b:
        return None

    ea = rng.choice(cands_a)
    eb = rng.choice(cands_b)
    val_a = ea.get(attr_a)
    val_b = eb.get(attr_b)

    if val_a > val_b:
        answer = f"{ea.name} ({val_a})"
    elif val_b > val_a:
        answer = f"{eb.name} ({val_b})"
    else:
        # tie → deterministic by name, use val_a (== val_b)
        answer = f"{max(ea.name, eb.name)} ({val_a})"

    q = rng.choice([
        f"Between {ea.name}'s {attr_a} ({dom_a.name}) and "
        f"{eb.name}'s {attr_b} ({dom_b.name}), which entity has the "
        f"larger value?",
        f"Comparing {ea.name}'s {attr_a} in {dom_a.name} with "
        f"{eb.name}'s {attr_b} in {dom_b.name}, which is greater?",
        f"Who has the bigger number: {ea.name} ({attr_a}, {dom_a.name}) "
        f"or {eb.name} ({attr_b}, {dom_b.name})?",
        f"Consider {ea.name}'s {attr_a} from {dom_a.name} and "
        f"{eb.name}'s {attr_b} from {dom_b.name}. Which value is higher?",
    ])
    return QA(
        q, answer, "cross_domain", "cross_domain",
        [ea.name, eb.name],
    )
