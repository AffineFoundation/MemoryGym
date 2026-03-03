"""MemoryBench v3 — Evaluation CLI.

Evaluates simulated agent strategies on streaming memory management tasks.

Usage:
    python eval.py                              # 30 seeds, all 5 strategies
    python eval.py --seed 42                    # Single seed
    python eval.py --seeds 10                   # Seeds 0..9
    python eval.py --strategy strategic naive   # Subset of strategies
    python eval.py --verbose --seed 0           # Per-task trace
    python eval.py -o results.json              # Save JSON output
    python eval.py --validate                   # Run pass/fail checks
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from memorybench.cli_display import (
    categorize_reason,
    print_answer_entropy,
    print_failure_analysis,
    print_verbose,
)
from memorybench.config import EvalConfig
from memorybench.evaluation.scorer import (
    compute_accuracy,
    compute_adaptability,
    compute_efficiency,
    compute_process_score,
    compute_trajectory,
    score_by_competency,
    score_by_domain,
)
from memorybench.generation.task_stream import generate_stream
from memorybench.simulation.agents import simulate_agent

ALL_STRATEGIES = ["perfect", "strategic", "fixed", "naive", "guesser"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="MemoryBench v3 — Streaming Memory Evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python eval.py --seed 42\n"
            "  python eval.py --seeds 10 --strategy strategic naive\n"
            "  python eval.py --verbose --seed 0 --strategy strategic\n"
            "  python eval.py --validate -o results.json\n"
        ),
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument("--seed", type=int, metavar="N",
                   help="evaluate a single seed")
    g.add_argument("--seeds", type=int, default=30, metavar="N",
                   help="number of seeds to evaluate, 0..N-1 (default: 30)")
    p.add_argument("--strategy", nargs="+", choices=ALL_STRATEGIES,
                   default=ALL_STRATEGIES, metavar="S",
                   help="strategies to evaluate (default: all)")
    p.add_argument("--write-budget", type=int, default=50, metavar="N",
                   help="max memory writes per agent (default: 50)")
    p.add_argument("--entities", type=int, default=25, metavar="N",
                   help="entities per domain (default: 25)")
    p.add_argument("--max-writes-per-task", type=int, default=3, metavar="N",
                   help="max writes per task per agent (default: 3)")
    p.add_argument("--output", "-o", type=str, metavar="PATH",
                   help="save results to JSON file")
    p.add_argument("--validate", action="store_true",
                   help="run pass/fail validation checks")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="print per-task traces (use with --seed)")
    p.add_argument("--show-registry", action="store_true",
                   help="print domain/config info and exit")
    p.add_argument("--eval-salt", type=int, default=0, metavar="N",
                   help="perturbation salt to defeat seed fingerprinting "
                        "(default: 0 = no perturbation)")
    p.add_argument("--quiet", "-q", action="store_true",
                   help="suppress per-seed progress output")
    return p.parse_args(argv)


# ── Registry ──

def show_registry():
    from memorybench.domains import ALL_DOMAINS
    config = EvalConfig()

    print("=" * 60)
    print("MemoryBench v3 — Registry")
    print("=" * 60)
    print(f"\nConfig:")
    print(f"  tasks/seed:      {config.n_tasks}")
    print(f"  entities/domain: {config.n_entities_per_domain}")
    print(f"  write budget:    {config.write_budget}")
    print(f"  domains/seed:    {config.n_domains} of {len(ALL_DOMAINS)}")
    print(f"  cross-domain %:  {config.cross_domain_prob:.0%}")

    print(f"\nDomains ({len(ALL_DOMAINS)}):")
    for dom in ALL_DOMAINS:
        print(f"  {dom.name}:")
        print(f"    attrs:  {', '.join(dom.ALL_ATTRS)}")
        print(f"    groups: {', '.join(dom.GROUP_NAMES[:5])}")

    print(f"\nStrategies:")
    for s in ALL_STRATEGIES:
        print(f"  {s}")


# ── Single seed evaluation ──

def run_seed(seed: int, config: EvalConfig, strategies: list[str],
             eval_salt: int = 0):
    tasks, updates, kbs, dom_map, switch_pt = generate_stream(
        seed, config, eval_salt=eval_salt,
    )
    out = {}
    for strategy in strategies:
        results, writes, traces = simulate_agent(
            strategy, tasks, kbs, dom_map, updates, seed,
            config.write_budget, config.max_writes_per_task,
        )
        out[strategy] = {
            "results": results,
            "traces": traces,
            "accuracy": compute_accuracy(results),
            "trajectory": compute_trajectory(results),
            "efficiency": compute_efficiency(results, max(writes, 1)),
            "adaptability": compute_adaptability(results, switch_pt),
            "process": compute_process_score(traces, writes),
            "by_competency": score_by_competency(results),
            "by_domain": score_by_domain(results),
            "writes_used": writes,
        }
    return out, dom_map, tasks, updates


# ── Validation ──

def run_validation(scores: dict, comp_scores: dict) -> dict[str, bool]:
    checks = {}
    s, c = scores, comp_scores

    if "perfect" in s:
        checks["perfect accuracy = 100%"] = s["perfect"]["accuracy"] >= 0.999

    if "strategic" in s and "naive" in s:
        checks["strategic > naive + 10%"] = (
            s["strategic"]["accuracy"] > s["naive"]["accuracy"] + 0.10)
        checks["strategic synthesis > naive + 15%"] = (
            c.get("synthesis", {}).get("strategic", 0) >
            c.get("synthesis", {}).get("naive", 0) + 0.15)
        checks["strategic trajectory > naive"] = (
            s["strategic"]["trajectory"] > s["naive"]["trajectory"])
        checks["strategic efficiency > naive"] = (
            s["strategic"]["efficiency"] > s["naive"]["efficiency"])
        checks["strategic adaptability > naive"] = (
            s["strategic"]["adaptability"] > s["naive"]["adaptability"])
        checks["strategic update > naive + 10%"] = (
            c.get("update", {}).get("strategic", 0) >
            c.get("update", {}).get("naive", 0) + 0.10)

    if "strategic" in s and "fixed" in s:
        checks["strategic > fixed"] = (
            s["strategic"]["accuracy"] > s["fixed"]["accuracy"])

    if "perfect" in s and "cross_domain" in c:
        checks["cross_domain + perfect=100%"] = (
            c["cross_domain"].get("perfect", 0) >= 0.99)

    # ── Anti-cheat checks ──
    if "guesser" in s:
        checks["guesser accuracy < 5%"] = s["guesser"]["accuracy"] < 0.05
        checks["guesser synthesis = 0%"] = (
            c.get("synthesis", {}).get("guesser", 0) < 0.01)
        checks["guesser cross_domain = 0%"] = (
            c.get("cross_domain", {}).get("guesser", 0) < 0.01)
        checks["guesser process = 0%"] = s["guesser"]["process"] < 0.01

    if "guesser" in s and "strategic" in s:
        checks["strategic >> guesser +80%"] = (
            s["strategic"]["accuracy"] > s["guesser"]["accuracy"] + 0.80)

    # ── Process checks ──
    if "strategic" in s:
        checks["strategic process > 50%"] = s["strategic"]["process"] > 0.50

    return checks


def check_determinism(config: EvalConfig, n: int = 5,
                      eval_salt: int = 0) -> bool:
    ok = True
    all_global_ids: set[int] = set()
    for seed in range(n):
        t1, _, _, _, _ = generate_stream(seed, config, eval_salt=eval_salt)
        t2, _, _, _, _ = generate_stream(seed, config, eval_salt=eval_salt)
        for a, b in zip(t1, t2):
            if a.documents != b.documents:
                print(f"  FAIL: seed={seed} task={a.task_id} docs differ")
                ok = False
                break
            qa = (a.question.question, a.question.answer) if a.question else None
            qb = (b.question.question, b.question.answer) if b.question else None
            if qa != qb:
                print(f"  FAIL: seed={seed} task={a.task_id} questions differ")
                ok = False
                break
            if a.global_id != b.global_id:
                print(f"  FAIL: seed={seed} task={a.task_id} "
                      f"global_id differs: {a.global_id} vs {b.global_id}")
                ok = False
                break
            if a.global_id is not None:
                if a.global_id in all_global_ids:
                    print(f"  FAIL: global_id {a.global_id} collides "
                          f"(seed={seed}, task={a.task_id})")
                    ok = False
                all_global_ids.add(a.global_id)
    print(f"  determinism ({n} seeds, 2 runs each): {'PASS' if ok else 'FAIL'}")
    if all_global_ids:
        print(f"  global_id uniqueness ({len(all_global_ids)} IDs): "
              f"{'PASS' if ok else 'FAIL'}")
    return ok


# ── Main ──

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.show_registry:
        show_registry()
        return 0

    config = EvalConfig(
        write_budget=args.write_budget,
        n_entities_per_domain=args.entities,
        max_writes_per_task=args.max_writes_per_task,
    )
    strategies = args.strategy
    seeds = [args.seed] if args.seed is not None else list(range(args.seeds))
    n_seeds = len(seeds)

    eval_salt = args.eval_salt

    # ── Header ──
    print("=" * 70)
    print("MemoryBench v3 — Evaluation")
    print("=" * 70)
    salt_info = f"  Salt: {eval_salt}" if eval_salt else ""
    print(f"Seeds: {n_seeds}  Strategies: {', '.join(strategies)}  "
          f"Budget: {config.write_budget}  Entities: {config.n_entities_per_domain}"
          f"{salt_info}")

    # ── Run seeds ──
    t0 = time.time()
    agg = {s: {"accuracy": [], "trajectory": [], "efficiency": [],
               "adaptability": [], "process": [],
               "by_comp": defaultdict(list),
               "by_domain": defaultdict(list)}
           for s in strategies}
    domain_counts: Counter = Counter()
    comp_totals: Counter = Counter()
    per_seed = []
    all_results: dict[str, list] = {s: [] for s in strategies}

    for i, seed in enumerate(seeds):
        if not args.quiet and not args.verbose:
            print(f"\r  seed {seed} ({i+1}/{n_seeds})", end="", flush=True)

        out, dom_map, tasks, updates = run_seed(
            seed, config, strategies, eval_salt=eval_salt,
        )
        domain_counts.update(dom_map.keys())
        for t in tasks:
            if t.question:
                comp_totals[t.question.competency] += 1

        if args.verbose:
            print_verbose(seed, out, tasks, updates)

        row = {"seed": seed, "domains": list(dom_map.keys())}
        for s in strategies:
            agg[s]["accuracy"].append(out[s]["accuracy"])
            agg[s]["trajectory"].append(out[s]["trajectory"])
            agg[s]["efficiency"].append(out[s]["efficiency"])
            agg[s]["adaptability"].append(out[s]["adaptability"])
            agg[s]["process"].append(out[s]["process"])
            for comp, val in out[s]["by_competency"].items():
                agg[s]["by_comp"][comp].append(val)
            for dom, val in out[s]["by_domain"].items():
                agg[s]["by_domain"][dom].append(val)
            all_results[s].extend(out[s]["results"])

            row[s] = {
                "accuracy": out[s]["accuracy"],
                "writes": out[s]["writes_used"],
            }
            if args.output:
                row[s]["tasks"] = [
                    {
                        "task_id": r.task_id,
                        "competency": r.competency,
                        "domain": r.domain,
                        "correct": r.is_correct,
                        "agent_answer": str(r.agent_answer),
                        "expected": str(r.expected_answer),
                        "question": r.question_text,
                        "failure_reason": r.failure_reason,
                        "search_hits": r.search_hits,
                    }
                    for r in out[s]["results"]
                ]
        per_seed.append(row)

    if not args.quiet and not args.verbose:
        print("\r" + " " * 40 + "\r", end="")
    elapsed = time.time() - t0

    # ── Aggregate ──
    def avg(xs):
        return sum(xs) / len(xs) if xs else 0.0

    scores = {}
    for s in strategies:
        scores[s] = {k: avg(agg[s][k])
                     for k in ("accuracy", "trajectory", "efficiency",
                               "adaptability", "process")}

    all_comps = sorted({c for s in strategies for c in agg[s]["by_comp"]})
    comp_scores = {}
    for comp in all_comps:
        comp_scores[comp] = {
            s: avg(agg[s]["by_comp"].get(comp, []))
            for s in strategies
        }

    all_doms = sorted({d for s in strategies for d in agg[s]["by_domain"]})
    dom_scores = {}
    for dom in all_doms:
        dom_scores[dom] = {
            s: avg(agg[s]["by_domain"].get(dom, []))
            for s in strategies
        }

    # ── Print results ──
    print(f"\nCompleted {n_seeds} seed{'s' if n_seeds != 1 else ''} "
          f"in {elapsed:.1f}s")
    print(f"Domains: {dict(domain_counts)}\n")

    print(f"{'Strategy':<12s} {'Accuracy':>9s} {'Trajectory':>11s} "
          f"{'Efficiency':>11s} {'Adapt':>7s} {'Process':>8s}")
    print("-" * 61)
    for s in strategies:
        sc = scores[s]
        print(f"{s:<12s} {sc['accuracy']:>8.1%} {sc['trajectory']:>10.3f} "
              f"{sc['efficiency']:>10.3f} {sc['adaptability']:>6.3f} "
              f"{sc['process']:>7.2f}")

    if all_comps:
        print(f"\nPer-competency accuracy:")
        hdr = f"  {'':15s}" + "".join(f"{s:>12s}" for s in strategies)
        print(hdr)
        print("  " + "-" * (15 + 12 * len(strategies)))
        for comp in all_comps:
            row = f"  {comp:<15s}"
            for s in strategies:
                row += f"{comp_scores[comp].get(s, 0):>11.1%}"
            print(row)

    if all_doms:
        print(f"\nPer-domain accuracy:")
        hdr = f"  {'':15s}" + "".join(f"{s:>12s}" for s in strategies)
        print(hdr)
        print("  " + "-" * (15 + 12 * len(strategies)))
        for dom in all_doms:
            row = f"  {dom:<15s}"
            for s in strategies:
                row += f"{dom_scores[dom].get(s, 0):>11.1%}"
            print(row)

    total_qs = sum(comp_totals.values())
    if total_qs:
        print(f"\nQuestions: {total_qs} total across {n_seeds} seeds")
        for comp in sorted(comp_totals):
            cnt = comp_totals[comp]
            print(f"  {comp:<15s} {cnt:>5d} ({cnt/total_qs:>5.1%})")

    if n_seeds >= 3 and not args.quiet:
        print_failure_analysis(all_results)

    # ── Validation ──
    all_pass = True
    if args.validate:
        print(f"\n{'='*70}")
        print("Validation")
        print("=" * 70)
        checks = run_validation(scores, comp_scores)
        for check, passed in checks.items():
            print(f"  {check:<45s}: {'PASS' if passed else 'FAIL'}")
            if not passed:
                all_pass = False
        if not check_determinism(config, eval_salt=eval_salt):
            all_pass = False
        if n_seeds >= 3 and "perfect" in strategies:
            print_answer_entropy(all_results["perfect"])
        print(f"\n  Result: {'ALL PASS' if all_pass else 'SOME FAILURES'}")

    # ── Save JSON ──
    if args.output:
        failure_analysis = {}
        for s in strategies:
            failures = [r for r in all_results[s] if not r.is_correct]
            cat_counts = Counter(categorize_reason(r.failure_reason)
                                 for r in failures)
            comp_fails = Counter(r.competency for r in failures)
            failure_analysis[s] = {
                "total_failures": len(failures),
                "by_reason": dict(cat_counts.most_common()),
                "by_competency": dict(comp_fails),
            }

        result = {
            "config": {
                "seeds": seeds, "n_tasks": config.n_tasks,
                "write_budget": config.write_budget,
                "n_entities_per_domain": config.n_entities_per_domain,
                "strategies": strategies,
                "eval_salt": eval_salt,
            },
            "summary": scores,
            "per_competency": comp_scores,
            "per_domain": dom_scores,
            "question_distribution": dict(comp_totals),
            "domain_usage": dict(domain_counts),
            "failure_analysis": failure_analysis,
            "per_seed": per_seed,
            "elapsed_seconds": round(elapsed, 2),
        }
        if args.validate:
            result["validation"] = {k: v for k, v in checks.items()}
            result["validation"]["determinism"] = all_pass

        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, default=str))
        print(f"\nSaved: {out_path}")

    if args.validate and not all_pass:
        return 1
    return 0
