#!/usr/bin/env python3
"""Analyze MemoryGym evaluation trajectories.

Reads trajectory JSON files and produces a human-readable analysis of
agent behavior: budget allocation, correction handling, answer patterns.

Usage:
    python scripts/analyze_trajectory.py eval/*_trajectory.json
    python scripts/analyze_trajectory.py eval/moonshotai_Kimi-K2.5-TEE_company_s42_trajectory.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def analyze_one(traj_path: Path) -> dict:
    """Analyze a single trajectory file. Returns summary dict."""
    traj = json.loads(traj_path.read_text())

    # Try to load companion eval result
    result_path = Path(str(traj_path).replace("_trajectory", ""))
    result = json.loads(result_path.read_text()) if result_path.exists() else None

    summary = {
        "file": traj_path.name,
        "events": len(traj),
        "ingest_events": [],
        "corrections": [],
        "questions": [],
        "total_writes": 0,
        "total_searches": 0,
        "total_api_calls": 0,
    }

    for ev in traj:
        t = ev["type"]

        if t == "ingest":
            n_entities = len(ev.get("entity_names", []))
            writes = ev.get("writes", 0)
            summary["total_writes"] += writes
            summary["total_searches"] += ev.get("searches", 0)
            summary["total_api_calls"] += ev.get("api_calls", 0)
            summary["ingest_events"].append({
                "n_entities": n_entities,
                "writes": writes,
                "budget_remaining": ev.get("budget_remaining"),
                "store_rate": f"{writes}/{n_entities}" if n_entities else "0/0",
            })

        elif t == "correction":
            writes = ev.get("writes", 0)
            summary["total_writes"] += writes
            summary["total_api_calls"] += ev.get("api_calls", 0)

            # Analyze correction behavior from turns
            actions = []
            stored_content = None
            for turn in ev.get("turns", []):
                for c in turn.get("tool_calls", []):
                    name = c.get("name", "")
                    actions.append(name)
                    if name == "memory_store":
                        stored_content = c.get("arguments", {}).get("content", "")

            summary["corrections"].append({
                "entity": ev.get("entity_name", ""),
                "attr": ev.get("attr", ""),
                "writes": writes,
                "actions": actions,
                "did_search": "memory_search" in actions,
                "did_forget": "memory_forget" in actions,
                "did_store": "memory_store" in actions,
                "stored_content_preview": (stored_content[:80] + "..."
                                           if stored_content and len(stored_content) > 80
                                           else stored_content),
            })

        elif t == "question":
            summary["total_api_calls"] += ev.get("api_calls", 0)
            summary["total_searches"] += ev.get("searches", 0)

            actions = []
            for turn in ev.get("turns", []):
                for c in turn.get("tool_calls", []):
                    actions.append(c.get("name", ""))

            summary["questions"].append({
                "competency": ev.get("competency", ""),
                "purpose": ev.get("purpose", ""),
                "correct": ev.get("correct", False),
                "question": ev.get("question", "")[:70],
                "ground_truth": str(ev.get("ground_truth", "")),
                "agent_answer": str(ev.get("agent_answer", ""))[:70],
                "actions": actions,
                "elapsed": ev.get("elapsed", 0),
            })

    # Compute derived stats
    total_entities = sum(ie["n_entities"] for ie in summary["ingest_events"])
    n_correct = sum(1 for q in summary["questions"] if q["correct"])
    n_questions = len(summary["questions"])

    summary["total_entities_seen"] = total_entities
    summary["accuracy"] = f"{n_correct}/{n_questions}" if n_questions else "0/0"
    summary["correction_success_rate"] = (
        f"{sum(1 for c in summary['corrections'] if c['did_store'])}"
        f"/{len(summary['corrections'])}"
    )

    if result:
        extra = result.get("extra", {})
        summary["score"] = result.get("score", 0)
        summary["model"] = extra.get("model", "?")
        summary["template"] = extra.get("template", "?")
        summary["seed"] = extra.get("seed", "?")
        summary["write_budget"] = extra.get("write_budget", "?")
        summary["stored_entities"] = extra.get("stored_entities", "?")
        summary["by_competency"] = extra.get("by_competency", {})

    return summary


def print_analysis(s: dict) -> None:
    """Print formatted analysis of a trajectory."""
    header = f"{s.get('model', '?')} | {s.get('template', '?')} seed={s.get('seed', '?')}"
    print("=" * 70)
    print(header)
    print("=" * 70)

    score = s.get("score")
    if score is not None:
        print(f"\nScore: {score*100:.0f}%")
    print(f"Entities seen: {s['total_entities_seen']}, "
          f"Stored: {s.get('stored_entities', '?')}")
    print(f"Writes: {s['total_writes']}/{s.get('write_budget', '?')}, "
          f"API calls: {s['total_api_calls']}, "
          f"Accuracy: {s['accuracy']}")

    # Budget allocation
    print(f"\n--- Budget Allocation ---")
    for i, ie in enumerate(s["ingest_events"]):
        print(f"  Batch {i+1}: {ie['store_rate']} stored, "
              f"budget remaining: {ie['budget_remaining']}")

    # Corrections
    if s["corrections"]:
        print(f"\n--- Corrections ({s['correction_success_rate']} updated) ---")
        for c in s["corrections"]:
            actions_str = " -> ".join(c["actions"]) if c["actions"] else "(no action)"
            mark = "OK" if c["did_store"] else "MISSED"
            print(f"  [{mark}] {c['entity']}.{c['attr']}: {actions_str}")
            if c["stored_content_preview"]:
                print(f"       stored: {c['stored_content_preview']}")

    # Questions
    if s["questions"]:
        print(f"\n--- Questions ---")
        for q in s["questions"]:
            mark = "OK" if q["correct"] else "WRONG"
            elapsed = f" ({q['elapsed']:.1f}s)" if q["elapsed"] else ""
            print(f"  [{mark:5}] {q['competency']:15} {q['question']}")
            if not q["correct"]:
                print(f"          expected: {q['ground_truth']}")
                print(f"          got:      {q['agent_answer']}")

    # Per-competency breakdown
    bc = s.get("by_competency", {})
    if bc:
        print(f"\n--- Per-Competency ---")
        for k, v in sorted(bc.items()):
            print(f"  {k:20} {v*100:.0f}%")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Analyze MemoryGym evaluation trajectories",
    )
    parser.add_argument(
        "files", nargs="+", type=Path,
        help="Trajectory JSON files to analyze",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output raw JSON instead of formatted text",
    )
    args = parser.parse_args()

    summaries = []
    for f in args.files:
        if not f.exists():
            print(f"WARNING: {f} not found, skipping", file=sys.stderr)
            continue
        s = analyze_one(f)
        summaries.append(s)

    if args.json:
        print(json.dumps(summaries, indent=2, default=str))
    else:
        for s in summaries:
            print_analysis(s)


if __name__ == "__main__":
    main()
