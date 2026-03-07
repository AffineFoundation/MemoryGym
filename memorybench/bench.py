"""MemoryBench — CLI for real agent evaluation + simulation self-tests.

Real evaluation (--model):
    python -m memorybench.bench --model openai/gpt-4o --seed 42
    python -m memorybench.bench --model openai/gpt-4o --seeds 3 --template company

Simulation (system self-testing, no LLM):
    python -m memorybench.bench --seed 0 -v
    python -m memorybench.bench --seeds 10 --validate
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from random import Random

# Re-export simulation symbols for backward compatibility with tests.
# All simulation logic lives in memorybench.simulation.
from memorybench.simulation import (  # noqa: F401
    STRATEGIES,
    TEMPLATES,
    _VALIDATOR,
    _construct_and_validate,
    _data_available,
    _entity_priority_score,
    _smart_guess,
    run_validation,
    simulate_one,
    simulate_one_stream,
)


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

                print(f"\n  [{tmpl.name}] seed={seed} — Generating world ...",
                      end="", flush=True)
                world = tmpl.generate_world(seed=seed, n_entities=args.entities,
                                            eval_salt=args.eval_salt)
                print(f" {len(world.entities)} entities")

                rng = Random(seed)
                print(f"  [{tmpl.name}] seed={seed} — Generating corrections ...",
                      end="", flush=True)
                corrections = tmpl.generate_corrections(
                    world, rng, args.corrections)
                print(f" {len(corrections)} corrections")

                print(f"  [{tmpl.name}] seed={seed} — Building stream ...",
                      end="", flush=True)
                stream = tmpl.generate_stream(
                    world, rng, corrections,
                    stored_names=set(),
                    n_questions=args.questions,
                    entities_per_batch=10,
                )
                n_ingest = sum(1 for e in stream if e["type"] == "ingest")
                n_correct = sum(1 for e in stream if e["type"] == "correction")
                n_question = sum(1 for e in stream if e["type"] == "question")
                print(f" {len(stream)} events "
                      f"({n_ingest} ingest, {n_correct} correction, "
                      f"{n_question} question)")

                print(f"  [{tmpl.name}] seed={seed} — Running agent "
                      f"({args.model}) ...")
                agent_results, writes_used, stored = run_stream_agent(
                    model=args.model,
                    stream=stream,
                    write_budget=30,
                    api_base=args.api_base,
                    verbose=args.verbose,
                    world=world,
                    template=tmpl,
                    seed=seed,
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

            else:
                # Simulation mode (system self-testing)
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

    # Auto-generate output path for model eval if not specified
    if is_model_eval and not args.output:
        safe_model = args.model.replace("/", "_")
        tmpl_str = args.template or "all"
        seed_str = (str(args.seed) if args.seed is not None
                    else f"{n_seeds}seeds")
        args.output = (f"eval/{safe_model}_{tmpl_str}_e{args.entities}"
                       f"_q{args.questions}_{seed_str}.json")

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
