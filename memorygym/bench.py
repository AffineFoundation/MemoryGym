"""MemoryGym — CLI for real agent evaluation + simulation self-tests.

Real evaluation (--model):
    python -m memorygym.bench --model openai/gpt-4o --seed 42
    python -m memorygym.bench --model openai/gpt-4o --seeds 3 --template company

Standard protocol:
    python -m memorygym.bench --model openai/gpt-4o --tier standard
    python -m memorygym.bench --model openai/gpt-4o --official -o results.json

Simulation (system self-testing, no LLM):
    python -m memorygym.bench --seed 0 -v
    python -m memorygym.bench --seeds 10 --validate
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from random import Random

from memorygym.protocol import (
    OFFICIAL_SEEDS,
    OFFICIAL_TEMPLATES,
    TIERS,
    compute_composite,
    format_leaderboard_entry,
)

# Re-export simulation symbols for backward compatibility with tests.
# All simulation logic lives in memorygym.simulation.
from memorygym.simulation import (  # noqa: F401
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
        description="MemoryGym — Memory Management Evaluation",
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
    p.add_argument("--entities", type=int, default=None, metavar="N",
                   help="entities per world (default: from tier)")
    p.add_argument("--questions", type=int, default=None, metavar="N",
                   help="questions per evaluation (default: from tier)")
    p.add_argument("--corrections", type=int, default=None, metavar="N",
                   help="corrections per evaluation (default: from tier)")
    p.add_argument("--output", "-o", type=str, metavar="PATH",
                   help="save results to JSON file")
    p.add_argument("--validate", action="store_true",
                   help="run invariant checks")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="print per-question details")
    p.add_argument("--quiet", "-q", action="store_true",
                   help="minimal output (single-line per event)")
    p.add_argument("--stream", action="store_true",
                   help="use interleaved stream (vs 3-phase)")
    p.add_argument("--model", "-m", type=str, metavar="MODEL",
                   help="run real LLM agent (requires API key)")
    p.add_argument("--api-base", type=str, metavar="URL",
                   help="OpenAI-compatible API base URL")
    p.add_argument("--eval-salt", type=int, default=0, metavar="N",
                   help="perturb numeric values (anti-fingerprint)")
    p.add_argument("--tier", choices=list(TIERS),
                   default=None, metavar="TIER",
                   help="evaluation tier (lite/standard/hard)")
    p.add_argument("--backend", choices=["chromadb", "mem0"],
                   default="chromadb", metavar="BACKEND",
                   help="memory backend (default: chromadb)")
    p.add_argument("--official", action="store_true",
                   help="official mode: seeds 0-9, all templates, "
                        "standard JSON output")
    return p.parse_args(argv)


def _resolve_config(args: argparse.Namespace) -> tuple[int, int, int, int]:
    """Resolve entities/questions/corrections/budget from tier or args.

    Returns (entities, questions, corrections, write_budget).
    """
    tier_name = args.tier or ("standard" if args.official else None)
    if tier_name:
        tier = TIERS[tier_name]
        entities = args.entities or tier["entities"]
        questions = args.questions or tier["questions"]
        corrections = args.corrections or tier["corrections"]
        write_budget = tier["write_budget"]
    else:
        entities = args.entities or 60
        questions = args.questions or 20
        corrections = args.corrections or 5
        write_budget = 30
    return entities, questions, corrections, write_budget


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Resolve tier/manual config
    n_entities, n_questions, n_corrections, write_budget = _resolve_config(args)

    # Official mode overrides
    if args.official:
        args.template = None  # all templates
        if args.eval_salt == 0:
            args.eval_salt = 1  # official mode requires eval_salt
        if args.seed is None and args.seeds == 10:
            pass  # default 10 seeds is fine
        # Force seeds 0-9
        seeds = OFFICIAL_SEEDS
    else:
        seeds = ([args.seed] if args.seed is not None
                 else list(range(args.seeds)))

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

    n_seeds = len(seeds)

    # Header
    tier_label = args.tier or ("standard" if args.official else "custom")
    print("=" * 70)
    print("MemoryGym — Memory Management Evaluation")
    print("=" * 70)
    label = (f"Model: {args.model}" if is_model_eval
             else f"Strategies: {', '.join(strategy_names)}")
    print(f"Seeds: {n_seeds}  Templates: {', '.join(template_names)}  "
          f"{label}")
    print(f"Tier: {tier_label}  Entities: {n_entities}  "
          f"Questions: {n_questions}  Corrections: {n_corrections}  "
          f"Budget: {write_budget}"
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
                from memorygym.agents.stream_agent import run_stream_agent

                print(f"\n  [{tmpl.name}] seed={seed} — Generating world ...",
                      end="", flush=True)
                world = tmpl.generate_world(seed=seed, n_entities=n_entities,
                                            eval_salt=args.eval_salt)
                print(f" {len(world.entities)} entities")

                rng = Random(seed)
                print(f"  [{tmpl.name}] seed={seed} — Generating corrections ...",
                      end="", flush=True)
                corrections = tmpl.generate_corrections(
                    world, rng, n_corrections)
                # Implicit contradictions: ~30% of correction count
                n_contras = max(1, n_corrections // 3)
                exclude_corrected = {c.entity_name for c in corrections}
                rng_contra = Random(seed + 7373)
                contradictions = tmpl.generate_contradictions(
                    world, rng_contra, n_contras,
                    exclude_entities=exclude_corrected)
                print(f" {len(corrections)} corrections, "
                      f"{len(contradictions)} contradictions")

                print(f"  [{tmpl.name}] seed={seed} — Building stream ...",
                      end="", flush=True)
                stream = tmpl.generate_stream(
                    world, rng, corrections,
                    stored_names=set(),
                    n_questions=n_questions,
                    entities_per_batch=10,
                    contradictions=contradictions,
                )
                n_ingest = sum(1 for e in stream if e["type"] == "ingest")
                n_correct = sum(1 for e in stream if e["type"] == "correction")
                n_question = sum(1 for e in stream if e["type"] == "question")
                print(f" {len(stream)} events "
                      f"({n_ingest} ingest, {n_correct} correction, "
                      f"{n_question} question)")

                print(f"  [{tmpl.name}] seed={seed} — Running agent "
                      f"({args.model}) ...")
                # Create backend
                if args.backend == "mem0":
                    from memorygym.memory.backends.mem0_backend import Mem0Backend
                    backend_obj = Mem0Backend()
                else:
                    from memorygym.memory.backends.chromadb_backend import ChromaDBBackend
                    backend_obj = ChromaDBBackend()

                agent_results, writes_used, stored, eval_error, traj = run_stream_agent(
                    model=args.model,
                    stream=stream,
                    write_budget=write_budget,
                    api_base=args.api_base,
                    verbose=args.verbose,
                    quiet=args.quiet,
                    backend=backend_obj,
                    world=world,
                    template=tmpl,
                    seed=seed,
                )

                # Convert to standard format
                seed_elapsed = time.time() - t0
                correct = sum(r.correct for r in agent_results)
                total = len(agent_results)
                by_comp: dict[str, list[bool]] = defaultdict(list)
                by_purp: dict[str, list[bool]] = defaultdict(list)
                answer_details = []
                for r in agent_results:
                    by_comp[r.competency].append(r.correct)
                    by_purp[r.purpose].append(r.correct)
                    detail = {
                        "question": r.question,
                        "expected": r.ground_truth,
                        "actual": r.answer,
                        "score": 1.0 if r.correct else 0.0,
                        "is_correct": r.correct,
                        "competency": r.competency,
                        "purpose": r.purpose,
                        "validation_method": r.validation_method,
                        "validation_reason": r.validation_reason,
                        "api_calls": r.api_calls,
                        "elapsed": round(r.elapsed, 2),
                        "retries": r.retries,
                    }
                    if r.error:
                        detail["error"] = r.error
                    answer_details.append(detail)

                # Detect stored entities
                stored_names, missed = tmpl.detect_stored_entities(
                    world, stored)

                comp_scores = {
                    c: round(sum(v) / len(v), 4) if v else 0.0
                    for c, v in by_comp.items()
                }

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
                    "details": answer_details,
                }
                agg[args.model].append(result)

                # Save per-seed result in LiveWeb-compatible format
                eval_result = {
                    "task_name": (f"memorygym:{tmpl.name}"
                                  f":{n_entities}e:{n_questions}q"),
                    "score": correct / total if total else 0.0,
                    "success": total > 0 and eval_error is None,
                    "time_taken": seed_elapsed,
                    "extra": {
                        "model": args.model,
                        "backend": args.backend,
                        "seed": seed,
                        "template": tmpl.name,
                        "n_entities": n_entities,
                        "n_questions": n_questions,
                        "n_corrections": n_corrections,
                        "write_budget": write_budget,
                        "writes_used": writes_used,
                        "stored_entities": len(stored_names),
                        "missed_entities": len(missed),
                        "by_competency": comp_scores,
                        "answer_details": answer_details,
                    },
                }
                if eval_error:
                    eval_result["error"] = eval_error
                eval_dir = Path("eval")
                eval_dir.mkdir(exist_ok=True)
                safe_model = args.model.replace("/", "_")
                eval_path = (eval_dir / f"{safe_model}_{tmpl.name}"
                             f"_s{seed}.json")
                tmp_path = eval_path.with_suffix(".tmp")
                tmp_path.write_text(
                    json.dumps(eval_result, indent=2, default=str))
                tmp_path.rename(eval_path)
                print(f"  Saved: {eval_path}")

                # Save trajectory alongside result
                if traj:
                    traj_path = (eval_dir / f"{safe_model}_{tmpl.name}"
                                 f"_s{seed}_trajectory.json")
                    traj_tmp = traj_path.with_suffix(".tmp")
                    traj_tmp.write_text(
                        json.dumps(traj, indent=2, default=str))
                    traj_tmp.rename(traj_path)
                    print(f"  Trajectory: {traj_path}")

            else:
                # Simulation mode (system self-testing)
                for profile in strategies:
                    sim_fn = (simulate_one_stream if args.stream
                              else simulate_one)
                    result = sim_fn(
                        tmpl, seed, profile,
                        n_entities=n_entities,
                        n_questions=n_questions,
                        n_corrections=n_corrections,
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
              f"{'Breadth':>8s} {'Maint.':>7s} "
              f"{'Reasoning':>10s} {'Abstention':>11s}")
        print("  " + "-" * 68)
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
                  f"{comp_pct('retrieval'):>8s} "
                  f"{comp_pct('update'):>7s} "
                  f"{comp_pct('synthesis', 'aggregation', 'conditional', 'ratio', 'comparison', 'multi_hop', 'outlier', 'delta'):>10s} "
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

    # Save aggregate JSON (simulation mode or explicit --output)
    if args.output:
        if args.official:
            # Official mode: use standard schema
            model_name = args.model or strategy_names[0]
            per_seed_out = _build_per_seed_axis_scores(
                agg, strategy_names[0], template_names, n_questions,
                write_budget)
            per_template_out = {}
            for tname in template_names:
                per_template_out[tname] = [
                    s for s in per_seed_out if s.get("template") == tname]
            tier_name = args.tier or "standard"
            config = {
                "entities": n_entities,
                "questions": n_questions,
                "corrections": n_corrections,
                "write_budget": write_budget,
                "seeds": seeds,
                "templates": template_names,
            }
            json_data = format_leaderboard_entry(
                model=model_name,
                tier=tier_name,
                backend="chromadb",
                per_seed_results=per_seed_out,
                config=config,
                per_template=per_template_out,
            )
        else:
            # Legacy format
            json_data = {
                "config": {
                    "seeds": seeds,
                    "templates": template_names,
                    "strategies": strategy_names,
                    "n_entities": n_entities,
                    "n_questions": n_questions,
                    "n_corrections": n_corrections,
                },
                "summary": {},
                "per_seed": [],
            }
            for s_name in strategy_names:
                vals = agg[s_name]
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


def _build_per_seed_axis_scores(
    agg: dict[str, list[dict]],
    strategy_name: str,
    template_names: list[str],
    n_questions: int,
    write_budget: int,
) -> list[dict]:
    """Build per-seed axis scores from aggregated results."""
    from memorygym.protocol import compute_composite

    per_seed: list[dict] = []
    for v in agg.get(strategy_name, []):
        by_comp = v["by_competency"]

        def _comp_rate(*comps: str) -> float:
            c_tot = t_tot = 0
            for comp in comps:
                c, t = by_comp.get(comp, (0, 0))
                c_tot += c
                t_tot += t
            return c_tot / t_tot if t_tot else 0.0

        breadth = _comp_rate("retrieval")
        maintenance_raw = _comp_rate("update")
        # Gate on breadth
        maintenance = maintenance_raw * min(breadth / 0.5, 1.0)
        reasoning = _comp_rate(
            "synthesis", "aggregation", "conditional", "ratio",
            "comparison", "multi_hop", "outlier", "delta")
        abstention_diagnostic = _comp_rate("abstention")

        # Efficiency
        n_correct = v["correct"]
        n_total = v["total"]
        accuracy = v["accuracy"]
        # Approximate writes_used from stored count
        writes_used = v.get("stored", 0)
        ideal_rate = n_total / max(write_budget, 1)
        if writes_used == 0:
            efficiency = 0.0
        else:
            raw_eff = min(n_correct / writes_used / ideal_rate, 1.0)
            efficiency = raw_eff * accuracy

        composite = compute_composite(breadth, maintenance, reasoning,
                                      efficiency)

        per_seed.append({
            "template": v["template"],
            "seed": v["seed"],
            "composite": round(composite, 4),
            "breadth": round(breadth, 4),
            "maintenance": round(maintenance, 4),
            "reasoning": round(reasoning, 4),
            "efficiency": round(efficiency, 4),
            "abstention_diagnostic": round(abstention_diagnostic, 4),
            "accuracy": round(accuracy, 4),
            "correct": n_correct,
            "total": n_total,
        })
    return per_seed


def _cli_entry() -> None:
    """Entry point for `memorygym` console script."""
    import sys
    sys.exit(main())


if __name__ == "__main__":
    _cli_entry()
