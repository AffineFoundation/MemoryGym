"""Display and reporting functions for the MemoryBench CLI."""

from __future__ import annotations

from collections import Counter, defaultdict


def print_verbose(seed: int, out: dict, tasks: list, updates: dict):
    """Print per-task diagnostic traces for each strategy."""
    for strategy, data in out.items():
        results = data["results"]
        traces = data["traces"]

        print(f"\n{'─'*70}")
        print(f"  SEED {seed} │ STRATEGY: {strategy} │ "
              f"ACCURACY: {data['accuracy']:.0%} │ WRITES: {data['writes_used']}")
        print(f"{'─'*70}")

        # Build result lookup
        result_by_tid = {r.task_id: r for r in results}

        for trace in traces:
            r = result_by_tid.get(trace.task_id)
            tid = trace.task_id

            # Task header
            marker = ""
            if r:
                marker = " ✓" if r.is_correct else " ✗"
            budget_str = (f"budget: {trace.budget_after}"
                          if strategy != "perfect" else "")

            print(f"\n  T{tid:02d} [{trace.domain}]{marker}  "
                  f"docs={trace.n_docs_received} new={trace.n_new_entities} "
                  f"{budget_str}")

            # Writes
            if trace.writes:
                accepted = [w for w in trace.writes if w.accepted]
                rejected = [w for w in trace.writes if not w.accepted]
                cats = Counter(w.category for w in accepted)
                cat_str = " ".join(f"{c}={n}" for c, n in sorted(cats.items()))
                print(f"       writes: {len(accepted)} accepted ({cat_str})"
                      + (f", {len(rejected)} rejected (budget full)"
                         if rejected else ""))

            # Question & answer
            if r:
                q_short = r.question_text
                if len(q_short) > 80:
                    q_short = q_short[:77] + "..."
                print(f"       Q [{r.competency}]: {q_short}")
                if r.is_correct:
                    print(f"       A: {r.expected_answer} (correct, "
                          f"{r.search_hits} hits)")
                else:
                    print(f"       A: {r.agent_answer} ≠ {r.expected_answer}")
                    print(f"       FAIL: {r.failure_reason} "
                          f"({r.search_hits} hits)")

        # Failure summary
        failures = [r for r in results if not r.is_correct]
        if failures:
            print(f"\n  ── Failure Summary ({len(failures)} failed) ──")
            reason_counts = Counter(r.failure_reason for r in failures)
            for reason, cnt in reason_counts.most_common():
                print(f"       {reason}: {cnt}")

        # Write budget timeline
        if strategy != "perfect" and traces:
            budget_timeline = [(t.task_id, t.budget_after) for t in traces]
            exhausted_at = next(
                (tid for tid, b in budget_timeline if b <= 0), None)
            if exhausted_at is not None:
                qs_after = sum(1 for r in results if r.task_id >= exhausted_at)
                correct_after = sum(
                    1 for r in results
                    if r.task_id >= exhausted_at and r.is_correct)
                print(f"\n  ── Budget Exhausted at T{exhausted_at:02d} ──")
                print(f"       questions after: {qs_after}, "
                      f"correct: {correct_after}")


def categorize_reason(reason: str) -> str:
    """Collapse per-entity failure reasons into categories."""
    if reason.startswith("no_entity_in_memory"):
        return "no_entity_in_memory"
    if reason.startswith("attr_missing"):
        parts = reason.split(":")
        return f"attr_missing:{parts[1]}" if len(parts) >= 2 else "attr_missing"
    return reason


def print_failure_analysis(all_results: dict):
    """Print aggregated failure root-cause analysis across all seeds."""
    print(f"\n{'='*70}")
    print("Failure Analysis")
    print("=" * 70)

    for strategy, results_list in all_results.items():
        failures = [r for r in results_list if not r.is_correct]
        if not failures:
            print(f"\n  {strategy}: 0 failures")
            continue

        total = len(results_list)
        print(f"\n  {strategy}: {len(failures)}/{total} failed "
              f"({len(failures)/total:.0%})")

        # By categorized failure reason
        cat_counts = Counter(categorize_reason(r.failure_reason)
                             for r in failures)
        print(f"    Root causes:")
        for reason, cnt in cat_counts.most_common():
            pct = cnt / len(failures)
            bar = "█" * int(pct * 15) + "░" * (15 - int(pct * 15))
            print(f"      {reason:<30s} {cnt:>3d} ({pct:>5.1%}) {bar}")

        # By competency
        comp_fails = Counter(r.competency for r in failures)
        comp_totals = Counter(r.competency for r in results_list)
        print(f"    By competency:")
        for comp in sorted(comp_totals):
            n_fail = comp_fails.get(comp, 0)
            n_total = comp_totals[comp]
            rate = n_fail / n_total if n_total else 0
            bar = "█" * int(rate * 20) + "░" * (20 - int(rate * 20))
            print(f"      {comp:<15s} {n_fail:>3d}/{n_total:<3d} "
                  f"{bar} {rate:.0%}")


def print_answer_entropy(results: list):
    """Analyze GT answer diversity per competency across seeds."""
    by_comp: dict[str, set[str]] = defaultdict(set)
    by_comp_total: Counter = Counter()
    for r in results:
        by_comp[r.competency].add(str(r.expected_answer))
        by_comp_total[r.competency] += 1

    print(f"\n  Answer diversity (unique GT answers across seeds):")
    for comp in sorted(by_comp):
        n_unique = len(by_comp[comp])
        n_total = by_comp_total[comp]
        risk = " ⚠ memorization risk" if n_unique < 20 else ""
        print(f"    {comp:<15s} {n_unique:>4d} unique / {n_total:>4d} total{risk}")
