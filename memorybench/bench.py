"""MemoryBench — Unified CLI for WorldTemplate evaluation.

Usage:
    python -m memorybench.bench --seed 0 -v              # Single seed, verbose
    python -m memorybench.bench --seeds 10                # 10 seeds aggregate
    python -m memorybench.bench --seeds 10 --validate     # With invariant checks
    python -m memorybench.bench --template company        # Specific template
    python -m memorybench.bench --seeds 5 -o results.json # Save JSON
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from random import Random

from memorybench.evaluation.validators import AnswerValidator
from memorybench.worlds import ALL_TEMPLATES
from memorybench.worlds.base import Correction, GeneratedQA, World, WorldTemplate

TEMPLATES = ALL_TEMPLATES

STRATEGIES = [
    {"name": "perfect", "store_ratio": 1.0, "applies_updates": True},
    {"name": "strategic", "store_ratio": 0.7, "applies_updates": True},
    {"name": "naive", "store_ratio": 0.4, "applies_updates": False},
    {"name": "guesser", "store_ratio": 0.0, "applies_updates": False},
    {"name": "abstainer", "store_ratio": 1.0, "applies_updates": True,
     "always_abstain": True},
    {"name": "smart_guesser", "store_ratio": 0.0, "applies_updates": False,
     "smart_guess": True},
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="MemoryBench — Memory Management Evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument("--seed", type=int, metavar="N",
                   help="evaluate a single seed")
    g.add_argument("--seeds", type=int, default=10, metavar="N",
                   help="number of seeds to evaluate (default: 10)")
    p.add_argument("--template", "-t", choices=list(TEMPLATES),
                   default=None, metavar="T",
                   help="template to evaluate (default: all)")
    p.add_argument("--strategy", nargs="+",
                   choices=[s["name"] for s in STRATEGIES],
                   default=None, metavar="S",
                   help="strategies to evaluate (default: all)")
    p.add_argument("--entities", type=int, default=60, metavar="N",
                   help="entities per world (default: 60)")
    p.add_argument("--questions", type=int, default=20, metavar="N",
                   help="questions per evaluation (default: 20)")
    p.add_argument("--corrections", type=int, default=5, metavar="N",
                   help="corrections per evaluation (default: 5)")
    p.add_argument("--output", "-o", type=str, metavar="PATH",
                   help="save results to JSON file")
    p.add_argument("--validate", action="store_true",
                   help="run invariant checks")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="print per-question details")
    p.add_argument("--stream", action="store_true",
                   help="use interleaved stream (vs 3-phase)")
    p.add_argument("--model", "-m", type=str, metavar="MODEL",
                   help="run real LLM agent (requires API key)")
    p.add_argument("--api-base", type=str, metavar="URL",
                   help="OpenAI-compatible API base URL")
    p.add_argument("--eval-salt", type=int, default=0, metavar="N",
                   help="perturb numeric values (anti-fingerprint)")
    return p.parse_args(argv)


_VALIDATOR = AnswerValidator()


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

    # Aggregation: guess a round number
    if q.competency == "aggregation":
        return str(rng.choice([100, 500, 1000, 5000, 10000]))

    # Default: guess a round number
    return str(rng.choice([100, 1000, 10000, 50000]))


def _can_answer(
    q: GeneratedQA,
    stored_names: set[str],
    updated_names: set[str],
    applies_updates: bool,
    n_total: int,
    always_abstain: bool = False,
) -> bool:
    """Simulate: can agent answer based on stored entities and update behavior?"""
    # Always-abstain strategy: only correct on real abstention questions
    if always_abstain:
        return q.competency == "abstention"

    if q.competency == "abstention":
        coverage = len(stored_names) / max(n_total, 1)
        return coverage >= 0.5

    if q.competency == "update":
        entity = q.required_entities[0]
        if entity not in stored_names:
            return False
        if not applies_updates:
            return False
        return entity in updated_names

    return all(name in stored_names for name in q.required_entities)


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
            ok = _can_answer(q, stored_names, updated_names,
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
    all_docs = [(e, tmpl.render_document(e, world.active_attrs, rng_doc))
                for e in world.entities]
    total_doc_chars = sum(len(doc) for _, doc in all_docs)

    # Storage decision (same as non-stream)
    rng_store = Random(seed + 111)
    ratio = profile["store_ratio"]
    if ratio >= 1.0:
        stored_docs = [doc for _, doc in all_docs]
    elif ratio <= 0.0:
        stored_docs = []
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

        # Reconstruct GeneratedQA for _can_answer
        q = GeneratedQA(
            question=event["question"],
            answer=event["answer"],
            competency=event["competency"],
            required_entities=event.get("required_entities", []),
            purpose=event.get("purpose", ""),
        )

        if is_smart_guesser:
            guess = _smart_guess(q, world, guess_rng)
            ok = _VALIDATOR.validate(guess, q.answer, q.competency) if guess else False
        else:
            ok = _can_answer(q, stored_names, updated_names,
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    templates = ([TEMPLATES[args.template]] if args.template
                 else list(TEMPLATES.values()))
    template_names = [t().name for t in templates]

    is_model_eval = args.model is not None
    if is_model_eval:
        strategy_names = [args.model]
    else:
        strategies = ([s for s in STRATEGIES if s["name"] in args.strategy]
                      if args.strategy else STRATEGIES)
        strategy_names = [s["name"] for s in strategies]

    seeds = ([args.seed] if args.seed is not None
             else list(range(args.seeds)))
    n_seeds = len(seeds)

    # Header
    print("=" * 70)
    print("MemoryBench — Memory Management Evaluation")
    print("=" * 70)
    label = (f"Model: {args.model}" if is_model_eval
             else f"Strategies: {', '.join(strategy_names)}")
    print(f"Seeds: {n_seeds}  Templates: {', '.join(template_names)}  "
          f"{label}")
    print(f"Entities: {args.entities}  Questions: {args.questions}  "
          f"Corrections: {args.corrections}"
          + ("  [STREAM]" if args.stream or is_model_eval else ""))

    t0 = time.time()
    agg: dict[str, list[dict]] = defaultdict(list)

    for tmpl_cls in templates:
        tmpl = tmpl_cls()
        for i, seed in enumerate(seeds):
            if not args.verbose:
                print(f"\r  [{tmpl.name}] seed {seed} ({i+1}/{n_seeds})",
                      end="", flush=True)

            if is_model_eval:
                # Real LLM agent evaluation
                from memorybench.agents.stream_agent import run_stream_agent
                world = tmpl.generate_world(seed=seed, n_entities=args.entities,
                                            eval_salt=args.eval_salt)
                rng = Random(seed)
                corrections = tmpl.generate_corrections(
                    world, rng, args.corrections)
                stream = tmpl.generate_stream(
                    world, rng, corrections,
                    stored_names=set(),
                    n_questions=args.questions,
                    entities_per_batch=10,
                )

                agent_results, writes_used, stored = run_stream_agent(
                    model=args.model,
                    stream=stream,
                    write_budget=30,
                    api_base=args.api_base,
                    verbose=args.verbose,
                )

                # Convert to standard format
                correct = sum(r.correct for r in agent_results)
                total = len(agent_results)
                by_comp: dict[str, list[bool]] = defaultdict(list)
                by_purp: dict[str, list[bool]] = defaultdict(list)
                details = []
                for r in agent_results:
                    by_comp[r.competency].append(r.correct)
                    by_purp[r.purpose].append(r.correct)
                    details.append({
                        "question": r.question,
                        "answer": r.ground_truth,
                        "competency": r.competency,
                        "purpose": r.purpose,
                        "correct": r.correct,
                    })

                # Detect stored entities
                stored_names, missed = tmpl.detect_stored_entities(
                    world, stored)

                result = {
                    "strategy": args.model,
                    "template": tmpl.name,
                    "seed": seed,
                    "accuracy": correct / total if total else 0.0,
                    "correct": correct,
                    "total": total,
                    "stored": len(stored_names),
                    "missed": len(missed),
                    "doc_chars": 0,
                    "by_purpose": {
                        p: (sum(v), len(v)) for p, v in by_purp.items()},
                    "by_competency": {
                        c: (sum(v), len(v)) for c, v in by_comp.items()},
                    "details": details,
                }
                agg[args.model].append(result)

                if args.verbose:
                    print(f"  [{tmpl.name}] seed={seed} "
                          f"{args.model} {result['accuracy']:.0%} "
                          f"stored={result['stored']} writes={writes_used}")

            else:
                # Simulation mode
                for profile in strategies:
                    sim_fn = (simulate_one_stream if args.stream
                              else simulate_one)
                    result = sim_fn(
                        tmpl, seed, profile,
                        n_entities=args.entities,
                        n_questions=args.questions,
                        n_corrections=args.corrections,
                        eval_salt=args.eval_salt,
                    )
                    agg[profile["name"]].append(result)

                    if args.verbose:
                        acc = result["accuracy"]
                        print(f"  [{tmpl.name}] seed={seed} "
                              f"{profile['name']:12s} {acc:.0%} "
                              f"stored={result['stored']}")
                        if profile["name"] != "guesser":
                            for d in result["details"]:
                                mark = "+" if d["correct"] else "-"
                                print(f"    {mark} [{d['competency']:12s}] "
                                      f"[{d['purpose']:13s}] "
                                      f"{d['question'][:60]}")

    if not args.verbose:
        print("\r" + " " * 50 + "\r", end="")
    elapsed = time.time() - t0

    # Aggregate
    def avg(vals: list[dict], key: str = "accuracy") -> float:
        return sum(v[key] for v in vals) / len(vals) if vals else 0.0

    print(f"\nCompleted in {elapsed:.1f}s\n")

    # Per-template results
    for tmpl_name in template_names:
        print(f"--- {tmpl_name} ---")
        print(f"  {'Strategy':<12s} {'Accuracy':>9s} {'Stored':>7s} "
              f"{'Retrieval':>10s} {'Update':>8s} "
              f"{'Comprehension':>14s} {'Abstention':>11s}")
        print("  " + "-" * 75)
        for s_name in strategy_names:
            vals = [v for v in agg[s_name] if v["template"] == tmpl_name]
            acc = avg(vals)
            stored = sum(v["stored"] for v in vals) / len(vals) if vals else 0

            def comp_pct(*comps: str) -> str:
                c_tot = t_tot = 0
                for comp in comps:
                    for v in vals:
                        c, t = v["by_competency"].get(comp, (0, 0))
                        c_tot += c
                        t_tot += t
                return f"{c_tot/t_tot:.0%}" if t_tot else "n/a"

            print(f"  {s_name:<12s} {acc:>8.0%} {stored:>6.0f} "
                  f"{comp_pct('retrieval'):>10s} "
                  f"{comp_pct('update'):>8s} "
                  f"{comp_pct('synthesis', 'aggregation', 'conditional'):>14s} "
                  f"{comp_pct('abstention'):>11s}")
        print()

    # Validation
    all_pass = True
    if args.validate:
        print("=" * 70)
        print("Validation")
        print("=" * 70)
        checks = run_validation(agg, template_names)
        for check, passed in checks.items():
            status = "PASS" if passed else "FAIL"
            print(f"  {check:<50s}: {status}")
            if not passed:
                all_pass = False
        print(f"\n  Result: {'ALL PASS' if all_pass else 'SOME FAILURES'}")

    # Save JSON
    if args.output:
        # Flatten for JSON (remove details unless verbose)
        json_data = {
            "config": {
                "seeds": seeds,
                "templates": template_names,
                "strategies": strategy_names,
                "n_entities": args.entities,
                "n_questions": args.questions,
                "n_corrections": args.corrections,
            },
            "summary": {},
            "per_seed": [],
        }
        for s_name in strategy_names:
            vals = agg[s_name]
            # Aggregate per-competency across all seeds/templates
            comp_agg: dict[str, list[int]] = {}
            for v in vals:
                for comp, (c, t) in v["by_competency"].items():
                    if comp not in comp_agg:
                        comp_agg[comp] = [0, 0]
                    comp_agg[comp][0] += c
                    comp_agg[comp][1] += t
            json_data["summary"][s_name] = {
                "accuracy": avg(vals),
                "by_template": {
                    t: avg([v for v in vals if v["template"] == t])
                    for t in template_names
                },
                "by_competency": {
                    c: round(cr / ct, 4) if ct else 0.0
                    for c, (cr, ct) in comp_agg.items()
                },
            }
        for v_list in agg.values():
            for v in v_list:
                entry = {k: v[k] for k in
                         ("strategy", "template", "seed", "accuracy",
                          "correct", "total", "stored", "missed")}
                entry["by_purpose"] = {
                    p: {"correct": c, "total": t}
                    for p, (c, t) in v["by_purpose"].items()
                }
                entry["by_competency"] = {
                    c: {"correct": cr, "total": ct}
                    for c, (cr, ct) in v["by_competency"].items()
                }
                json_data["per_seed"].append(entry)

        if args.validate:
            json_data["validation"] = {k: v for k, v in checks.items()}

        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(json_data, indent=2, default=str))
        print(f"\nSaved: {out_path}")

    if args.validate and not all_pass:
        return 1
    return 0


def _cli_entry() -> None:
    """Entry point for `memorybench` console script."""
    import sys
    sys.exit(main())


if __name__ == "__main__":
    _cli_entry()
