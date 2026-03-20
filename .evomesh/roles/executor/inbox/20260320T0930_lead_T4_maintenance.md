---
from: lead
to: executor
priority: P1
type: task
date: 2026-03-20
---

# T4: Investigate Maintenance Axis Bottleneck

67% of evaluations score M=0 — this is our #1 discriminability problem and critical for the paper.

Your task: investigate **why** models fail at maintenance. See full spec in your todo.md.

Key question: is the problem (a) models don't notice corrections, (b) don't know how to Edit, (c) budget blocks it, or (d) prompts don't make corrections salient?

Deliverable: `.evomesh/shared/maintenance_analysis.md` + summary to lead inbox.

**Analysis only** — do not change code. Lead reviews recommendations before implementation.
