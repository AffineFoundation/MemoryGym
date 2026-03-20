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

## Backlog

### T3: Deduplicate Edit reward logic in env.py (Priority: LOW)
**背景**: `env.py` Edit tool handler (lines ~669-712) has identical reward logic in two branches. 27 lines duplicated.
**目标**: Extract shared reward logic into a helper method. Must not change behavior.

## Completed
- [x] T1: build_assistant_mask tests (5 tests, commit `ee817d0`)
- [x] T2: Training code commit (verified already committed by trainer)
