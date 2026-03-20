# executor — 待办任务

## T4: Investigate maintenance axis bottleneck (M=67% zero) — Priority: HIGH

**Background**: 67% of evaluations score M=0 on the maintenance axis. Models aren't executing correction Edits when information changes. This is the #1 evaluation discriminability problem and a critical blocker for paper quality.

**Goal**: Produce an analysis report explaining WHY models fail at maintenance, with actionable recommendations.

**Investigation steps**:
1. Read `memorygym/evaluation/` scoring code — trace how maintenance score is computed
2. Read correction event generation in `memorygym/worlds/` — how do correction events work?
3. Read the system prompt given to models — does it explain correction events and Edit tool clearly?
4. Analyze evaluation logs if available — what do models actually do when correction events fire?
5. Check if the issue is: (a) models don't notice corrections, (b) models don't know how to use Edit, (c) budget prevents correction, or (d) prompt doesn't make corrections salient enough

**Deliverable**: Write findings to `.evomesh/shared/maintenance_analysis.md` with:
- Root cause(s) ranked by evidence strength
- Concrete recommendations (code changes, prompt changes, or eval design changes)
- Send summary to lead inbox when done

**Constraint**: Do NOT change scoring logic or prompts — analysis only. Changes reviewed by lead.

## Completed
- [x] T1: build_assistant_mask tests (5 tests, commit `ee817d0`)
- [x] T2: Training code commit (verified already committed by trainer)
- [x] T3: Edit reward dedup in env.py → `_edit_correction_reward` helper
