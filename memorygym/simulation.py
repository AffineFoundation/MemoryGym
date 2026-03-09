"""Simulation engine for system self-testing.

NOT an evaluation path. Simulates deterministic strategies (perfect, guesser,
strategic, etc.) to verify scoring invariants: perfect=100%, guesser=0%,
strategic > naive, etc.

For real agent evaluation, use:
- stream_agent (bench.py --model): real LLM + real backend
- eval_task (Inspect AI): real LLM + real backend
"""

from __future__ import annotations

from collections import defaultdict
from random import Random

from memorygym.evaluation.validators import AnswerValidator
from memorygym.worlds import ALL_TEMPLATES
from memorygym.worlds.base import (
    EntitySpec, GeneratedQA, World, WorldTemplate,
)

TEMPLATES = ALL_TEMPLATES

STRATEGIES = [
    {"name": "perfect", "store_ratio": 1.0, "applies_updates": True},
    {"name": "strategic", "store_ratio": 0.7, "applies_updates": True},
    {"name": "priority_strategic", "store_ratio": 0.5,
     "applies_updates": True, "priority_store": True},
    {"name": "random_strategic", "store_ratio": 0.5,
     "applies_updates": True},
    {"name": "naive", "store_ratio": 0.4, "applies_updates": False},
    {"name": "guesser", "store_ratio": 0.0, "applies_updates": False},
    {"name": "abstainer", "store_ratio": 1.0, "applies_updates": True,
     "always_abstain": True},
    {"name": "smart_guesser", "store_ratio": 0.0, "applies_updates": False,
     "smart_guess": True},
]


_VALIDATOR = AnswerValidator()


def _entity_priority_score(entity: EntitySpec, world: World) -> float:
    """Score entity by question likelihood.

    Higher score = more likely to appear in questions.
    Factors:
    - Category population: entities in larger categories are more likely
      to appear in aggregation/synthesis/comparison questions.
    - Attribute completeness: entities with more non-None attributes
      are more useful for ratio/conditional questions.
    - Extremeness: entities with extreme values (top/bottom 20%) are
      more likely targets for synthesis (max/min) and outlier questions.
    """
    score = 0.0
    # Category population bonus
    cat_size = len(world.entities_in_category(entity.category))
    score += min(cat_size, 10)  # cap at 10

    # Attribute completeness
    n_attrs = sum(1 for a in world.active_attrs
                  if entity.get(a) is not None)
    score += n_attrs * 0.5

    # Extremeness: count how many attributes this entity ranks in
    # top/bottom 20% among all entities
    for attr in world.active_attrs:
        val = entity.get(attr)
        if not isinstance(val, (int, float)):
            continue
        all_vals = sorted(e.get(attr) for e in world.entities
                          if isinstance(e.get(attr), (int, float)))
        if len(all_vals) < 5:
            continue
        rank = sum(1 for v in all_vals if v <= val)
        percentile = rank / len(all_vals)
        if percentile <= 0.2 or percentile >= 0.8:
            score += 2.0  # extreme value bonus

    return score


def _smart_guess(q: GeneratedQA, world: World, rng: Random) -> str | None:
    """Generate a plausible guess for a question without stored data.

    Simulates a sophisticated attacker who:
    - Uses midpoint of attribute ranges for numeric questions
    - Picks random entity names for synthesis questions
    - Tries common values (median years, round numbers)
    Returns None if no guess strategy applies.
    """
    if q.competency == "abstention":
        return None  # smart guesser knows it can't win abstention

    # Try to identify the attribute from the question
    for adef in world.attr_defs:
        label = adef.label or adef.name.replace("_", " ")
        if label.lower() in q.question.lower():
            # Found the attribute — guess midpoint
            mid = (adef.min_val + adef.max_val) / 2
            if adef.dtype == "int":
                # Try several common values: midpoint, quartiles, common years
                guesses = [
                    int(mid),
                    int(adef.min_val + (adef.max_val - adef.min_val) * 0.25),
                    int(adef.min_val + (adef.max_val - adef.min_val) * 0.75),
                ]
                return str(rng.choice(guesses))
            else:
                # Float: guess midpoint with some noise
                noise = rng.uniform(-0.01, 0.01) * (adef.max_val - adef.min_val)
                return str(round(mid + noise, 2))

    # Synthesis: guess a random entity name with a midpoint value
    if q.competency in ("synthesis", "conditional"):
        e = rng.choice(world.entities)
        return f"{e.name} (1000)"

    # Comparison/multi_hop/outlier: guess entity name + value
    if q.competency in ("comparison", "multi_hop", "outlier"):
        e = rng.choice(world.entities)
        return f"{e.name} ({rng.choice([10, 100, 1000])})"

    # Ratio: guess a ratio (product of ranges makes this extremely unlikely)
    if q.competency == "ratio":
        return str(round(rng.uniform(0.01, 100), 2))

    # Delta: guess a change amount
    if q.competency == "delta":
        return str(rng.choice([10, 50, 100, 500, 1000]))

    # Aggregation: guess a round number
    if q.competency == "aggregation":
        return str(rng.choice([100, 500, 1000, 5000, 10000]))

    # Default: guess a round number
    return str(rng.choice([100, 1000, 10000, 50000]))


def _data_available(
    q: GeneratedQA,
    stored_names: set[str],
    updated_names: set[str],
    applies_updates: bool,
    n_total: int,
    always_abstain: bool = False,
) -> bool:
    """Check whether the simulated agent has the data to answer."""
    if always_abstain:
        return q.competency == "abstention"

    if q.competency == "abstention":
        coverage = len(stored_names) / max(n_total, 1)
        return coverage >= 0.5

    if q.competency in ("update", "delta"):
        entity = q.required_entities[0]
        if entity not in stored_names:
            return False
        if not applies_updates:
            return False
        return entity in updated_names

    return all(name in stored_names for name in q.required_entities)


def _construct_and_validate(
    q: GeneratedQA,
    tmpl: WorldTemplate,
    world: World,
    stored_names: set[str],
    updated_names: set[str],
    applies_updates: bool,
    n_total: int,
    always_abstain: bool = False,
) -> bool:
    """Simulate answer construction then validate against GT.

    For retrieval/update questions with a source_attr, constructs the answer
    via _format_value() so format bugs (precision, suffix) are caught.
    For comprehension questions, uses GT directly (simulation assumes perfect
    computation if data is available — this tests the scoring system, not
    agent reasoning).
    """
    if not _data_available(q, stored_names, updated_names, applies_updates,
                           n_total, always_abstain):
        return False

    # Abstention: agent says "I don't have enough information"
    if q.competency == "abstention":
        return _VALIDATOR.validate(
            "I don't have enough information", q.answer, q.competency)

    # Retrieval / update with known source_attr: construct via _format_value
    if q.competency in ("retrieval", "update") and q.source_attr:
        entity = world.get_entity(q.required_entities[0])
        if entity:
            val = entity.get(q.source_attr)
            if val is not None:
                constructed = tmpl._format_value(q.source_attr, val)
                return _VALIDATOR.validate(constructed, q.answer, q.competency)

    # Comprehension / derived / no source_attr: validate GT against itself
    # (simulation assumes perfect computation if data is available)
    return _VALIDATOR.validate(q.answer, q.answer, q.competency)


def simulate_one(
    tmpl: WorldTemplate,
    seed: int,
    profile: dict,
    n_entities: int = 60,
    n_questions: int = 20,
    n_corrections: int = 5,
    eval_salt: int = 0,
) -> dict:
    """Run one strategy on one seed. Returns result dict."""
    world = tmpl.generate_world(seed=seed, n_entities=n_entities,
                                eval_salt=eval_salt)
    rng_doc = Random(seed)

    # Render documents
    all_docs = [(e, tmpl.render_document(e, world.active_attrs, rng_doc))
                for e in world.entities]
    total_doc_chars = sum(len(doc) for _, doc in all_docs)

    # Storage decision
    rng_store = Random(seed + 111)
    ratio = profile["store_ratio"]
    if ratio >= 1.0:
        stored_docs = [doc for _, doc in all_docs]
    elif ratio <= 0.0:
        stored_docs = []
    elif profile.get("priority_store"):
        # Priority storage: score entities by question likelihood,
        # store the top-N. Proves WHAT you store matters.
        n_store = max(1, int(len(all_docs) * ratio))
        scored = [(i, _entity_priority_score(e, world))
                  for i, (e, _) in enumerate(all_docs)]
        scored.sort(key=lambda x: -x[1])
        indices = [i for i, _ in scored[:n_store]]
        stored_docs = [all_docs[i][1] for i in indices]
    else:
        n_store = max(1, int(len(all_docs) * ratio))
        indices = rng_store.sample(range(len(all_docs)), n_store)
        stored_docs = [all_docs[i][1] for i in indices]

    stored_names, missed_names = tmpl.detect_stored_entities(world, stored_docs)

    # Corrections (mutates world!)
    rng_correct = Random(seed + 3333)
    corrections = tmpl.generate_corrections(world, rng_correct, n_corrections)

    # Which corrections applied
    updated_names: set[str] = set()
    if profile["applies_updates"]:
        for c in corrections:
            if c.entity_name in stored_names:
                updated_names.add(c.entity_name)

    # Generate questions
    rng_q = Random(seed + 7777)
    questions = tmpl.gen_adaptive_questions(
        world, rng_q, world.entities, stored_names, n_questions, corrections)

    # Evaluate
    correct = 0
    by_purpose: dict[str, list[bool]] = defaultdict(list)
    by_comp: dict[str, list[bool]] = defaultdict(list)
    details: list[dict] = []
    is_smart_guesser = profile.get("smart_guess", False)
    guess_rng = Random(seed + 9999)

    for q in questions:
        if is_smart_guesser:
            # Smart guesser: generate a plausible guess, validate against GT
            guess = _smart_guess(q, world, guess_rng)
            if guess:
                ok = _VALIDATOR.validate(guess, q.answer, q.competency)
            else:
                ok = False
        else:
            ok = _construct_and_validate(
                q, tmpl, world, stored_names, updated_names,
                profile["applies_updates"],
                n_total=len(world.entities),
                always_abstain=profile.get("always_abstain", False))
        if ok:
            correct += 1
        by_purpose[q.purpose].append(ok)
        by_comp[q.competency].append(ok)
        details.append({
            "question": q.question,
            "answer": q.answer,
            "competency": q.competency,
            "purpose": q.purpose,
            "correct": ok,
        })

    total = len(questions)
    accuracy = correct / total if total else 0.0

    return {
        "strategy": profile["name"],
        "template": tmpl.name,
        "seed": seed,
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "stored": len(stored_names),
        "missed": len(missed_names),
        "doc_chars": total_doc_chars,
        "by_purpose": {p: (sum(v), len(v)) for p, v in by_purpose.items()},
        "by_competency": {c: (sum(v), len(v)) for c, v in by_comp.items()},
        "details": details,
    }


def simulate_one_stream(
    tmpl: WorldTemplate,
    seed: int,
    profile: dict,
    n_entities: int = 60,
    n_questions: int = 20,
    n_corrections: int = 5,
    eval_salt: int = 0,
) -> dict:
    """Run one strategy using interleaved stream. Returns result dict."""
    world = tmpl.generate_world(seed=seed, n_entities=n_entities,
                                eval_salt=eval_salt)
    rng_doc = Random(seed)

    # Render documents (for storage simulation)
    all_docs = []
    for e in world.entities:
        doc = tmpl.render_document(e, world.active_attrs, rng_doc)
        if world.relationships:
            rels = world.get_outgoing(e.name)
            if rels:
                rel_lines = [tmpl.render_relationship(r) for r in rels]
                doc += "\n" + " ".join(rel_lines)
        all_docs.append((e, doc))
    total_doc_chars = sum(len(doc) for _, doc in all_docs)

    # Storage decision (same as non-stream)
    rng_store = Random(seed + 111)
    ratio = profile["store_ratio"]
    if ratio >= 1.0:
        stored_docs = [doc for _, doc in all_docs]
    elif ratio <= 0.0:
        stored_docs = []
    elif profile.get("priority_store"):
        n_store = max(1, int(len(all_docs) * ratio))
        scored = [(i, _entity_priority_score(e, world))
                  for i, (e, _) in enumerate(all_docs)]
        scored.sort(key=lambda x: -x[1])
        indices = [i for i, _ in scored[:n_store]]
        stored_docs = [all_docs[i][1] for i in indices]
    else:
        n_store = max(1, int(len(all_docs) * ratio))
        indices = rng_store.sample(range(len(all_docs)), n_store)
        stored_docs = [all_docs[i][1] for i in indices]

    stored_names, missed_names = tmpl.detect_stored_entities(world, stored_docs)

    # Corrections (mutates world!)
    rng_correct = Random(seed + 3333)
    corrections = tmpl.generate_corrections(world, rng_correct, n_corrections)

    updated_names: set[str] = set()
    if profile["applies_updates"]:
        for c in corrections:
            if c.entity_name in stored_names:
                updated_names.add(c.entity_name)

    # Generate interleaved stream
    rng_stream = Random(seed + 5555)
    stream = tmpl.generate_stream(
        world, rng_stream, corrections, stored_names,
        n_questions=n_questions, entities_per_batch=10,
    )

    # Extract questions from stream and evaluate
    correct = 0
    by_purpose: dict[str, list[bool]] = defaultdict(list)
    by_comp: dict[str, list[bool]] = defaultdict(list)
    details: list[dict] = []
    questions_seen = 0
    is_smart_guesser = profile.get("smart_guess", False)
    guess_rng = Random(seed + 9999)

    for event in stream:
        if event["type"] != "question":
            continue
        questions_seen += 1

        q = GeneratedQA(
            question=event["question"],
            answer=event["answer"],
            competency=event["competency"],
            required_entities=event.get("required_entities", []),
            purpose=event.get("purpose", ""),
            source_attr=event.get("source_attr", ""),
        )

        if is_smart_guesser:
            guess = _smart_guess(q, world, guess_rng)
            ok = _VALIDATOR.validate(guess, q.answer, q.competency) if guess else False
        else:
            ok = _construct_and_validate(
                q, tmpl, world, stored_names, updated_names,
                profile["applies_updates"],
                n_total=len(world.entities),
                always_abstain=profile.get("always_abstain", False))
        if ok:
            correct += 1
        by_purpose[q.purpose].append(ok)
        by_comp[q.competency].append(ok)
        details.append({
            "question": q.question,
            "answer": q.answer,
            "competency": q.competency,
            "purpose": q.purpose,
            "correct": ok,
        })

    total = questions_seen
    accuracy = correct / total if total else 0.0

    return {
        "strategy": profile["name"],
        "template": tmpl.name,
        "seed": seed,
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "stored": len(stored_names),
        "missed": len(missed_names),
        "doc_chars": total_doc_chars,
        "by_purpose": {p: (sum(v), len(v)) for p, v in by_purpose.items()},
        "by_competency": {c: (sum(v), len(v)) for c, v in by_comp.items()},
        "details": details,
    }


def run_validation(agg: dict, templates_used: list[str]) -> dict[str, bool]:
    """Run invariant checks on aggregated results."""
    checks: dict[str, bool] = {}

    for tmpl_name in templates_used:
        prefix = f"[{tmpl_name}] "
        s = {name: vals for name, vals in agg.items()
             if any(v["template"] == tmpl_name for v in vals)}

        def avg_acc(strategy: str) -> float:
            vals = [v["accuracy"] for v in agg.get(strategy, [])
                    if v["template"] == tmpl_name]
            return sum(vals) / len(vals) if vals else 0.0

        def comp_acc(strategy: str, comp: str) -> float:
            totals = [0, 0]
            for v in agg.get(strategy, []):
                if v["template"] != tmpl_name:
                    continue
                c, t = v["by_competency"].get(comp, (0, 0))
                totals[0] += c
                totals[1] += t
            return totals[0] / totals[1] if totals[1] else 0.0

        p = avg_acc("perfect")
        st = avg_acc("strategic")
        n = avg_acc("naive")
        g = avg_acc("guesser")

        checks[prefix + "perfect = 100%"] = p >= 0.999
        checks[prefix + "guesser = 0%"] = g < 0.01
        checks[prefix + "strategic > naive"] = st > n
        checks[prefix + "strategic > naive + 10%"] = st > n + 0.10
        checks[prefix + "naive > guesser"] = n > g
        checks[prefix + "guesser < 5%"] = g < 0.05
        checks[prefix + "strategic update > naive update"] = (
            comp_acc("strategic", "update") > comp_acc("naive", "update"))

    # Priority vs random storage: soft check (advisory only).
    # Retrieval questions target random entities, so priority can only
    # influence comprehension (~25% of questions). With small sample sizes
    # the advantage is often within noise. Check across ALL templates
    # combined instead of per-template.
    all_ps = [v["accuracy"] for v in agg.get("priority_strategic", [])]
    all_rs = [v["accuracy"] for v in agg.get("random_strategic", [])]
    if all_ps and all_rs:
        avg_ps = sum(all_ps) / len(all_ps)
        avg_rs = sum(all_rs) / len(all_rs)
        checks["priority >= random (global avg)"] = avg_ps >= avg_rs - 0.02

    # Abstainer ceiling: always-abstain must stay below 20%
    for tmpl_name in templates_used:
        prefix = f"[{tmpl_name}] "
        abstainer_acc = avg_acc("abstainer")
        if abstainer_acc > 0:  # only check if abstainer was run
            checks[prefix + "abstainer < 20%"] = abstainer_acc < 0.20

    # Smart guesser ceiling: midpoint/common-value guessing must stay < 5%
    for tmpl_name in templates_used:
        prefix = f"[{tmpl_name}] "
        sg_vals = [v["accuracy"] for v in agg.get("smart_guesser", [])
                   if v["template"] == tmpl_name]
        if sg_vals:
            sg_acc = sum(sg_vals) / len(sg_vals)
            checks[prefix + "smart_guesser < 5%"] = sg_acc < 0.05

    # Trick retrieval: guesser must fail trick questions
    for tmpl_name in templates_used:
        prefix = f"[{tmpl_name}] "
        trick_correct = 0
        trick_total = 0
        for v in agg.get("guesser", []):
            if v["template"] != tmpl_name:
                continue
            c, t = v["by_purpose"].get("trick_retrieval", (0, 0))
            trick_correct += c
            trick_total += t
        if trick_total > 0:
            checks[prefix + "guesser trick_retrieval = 0%"] = trick_correct == 0

    # Determinism check
    for tmpl_name in templates_used:
        tmpl = TEMPLATES[tmpl_name]()
        w1 = tmpl.generate_world(seed=99, n_entities=60)
        w2 = tmpl.generate_world(seed=99, n_entities=60)
        rng1, rng2 = Random(99), Random(99)
        d1 = [tmpl.render_document(e, w1.active_attrs, rng1)
              for e in w1.entities]
        d2 = [tmpl.render_document(e, w2.active_attrs, rng2)
              for e in w2.entities]
        checks[f"[{tmpl_name}] determinism"] = d1 == d2

    return checks
