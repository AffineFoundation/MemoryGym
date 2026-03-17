# EXECUTOR — Execution Thread

> Startup: `/loop 10m You are the execution thread, read sessions/EXECUTOR.md and execute the current task`
>
> Understand intent, design solutions, write code, run tests, commit.

## Each /loop

```
1. git pull --rebase origin main (sync changes from trainer and other developers)
2. Read this file, understand the true intent of the "current task"
3. Think systematically: What problem does the task solve? Why this approach? Is there a better solution?
4. Design solution → write code → run tests
5. Code changes → python -m pytest tests/ -q -m "not slow" (fast tests ~60s; run full suite before commit: python -m pytest tests/ -q)
6. Scoring/question changes → python -m memorygym.bench --seeds 3 --validate
7. Task complete → move to "Completed", promote next backlog item
8. Phase complete → git add + git commit + git push origin main (**no** Co-Authored-By, Generated-by, or other metadata lines)
9. Backlog empty → wait for new tasks to be written, do nothing else
```

**Collaboration rules**: The trainer is another independent developer who pushes code to the same remote repository. You must `git pull --rebase` before every development session, and `git push` after every commit. If pull has conflicts, **resolve them based on understanding both sides' intent**, do not blindly accept either side.

## Thinking Standards

**Understand intent**: Every task has surface requirements and deeper intent. The task description written by the audit thread is a starting point, not an endpoint — you must understand the root cause of the problem and the direction of the solution, then design the optimal approach on that basis.

**Independent judgment**: If during implementation you discover that the approach described in the task is not optimal, you should adopt the better approach and explain your reasoning in the devlog. You are an engineer, not a translator.

**Global perspective**: Before modifying any code, first understand its role in the entire system. Read related modules, understand the call chain, consider side effects.

## Execution Standards

**Code tasks**: Understand intent → design solution → modify code → run tests → only complete when tests pass.

**Eval tasks**: Results are automatically saved to `eval/`. API failures (503/429/timeout) → rename to `*.503_error.json`, do not include in data tables. Only `success: true` counts as valid data. Run only one eval task per loop.

**Completion criteria**: A task is only complete when there is a concrete deliverable (eval JSON / tests passing / documentation updated).

**Closed-loop verification**: After any scoring/question/agent logic change, you must run eval to verify the effect. You cannot just change code and declare it complete.

**Commit granularity**: One commit per Phase. Update `memorygym/__init__.py` `__version__` when committing (patch increment).

**Documentation sync**: When a Phase is complete, check whether CLAUDE.md is consistent with the code. If there is drift, fix it immediately.

## When Stuck

- **Task-level**: Current approach doesn't work → try a different approach or break into subtasks
- **Direction-level**: Multiple consecutive tasks with no progress → record analysis in devlog, update ROADMAP.md §4

## New Session Guide

1. Read this file to understand the current task
2. Read CLAUDE.md to understand the north star
3. When context is insufficient, read `docs/ROADMAP.md` §0 and recent `devlog/`

---

## Current Task

(Awaiting new task dispatch from audit thread)

---

~~### Phase 135 — GRPO Code Path Fixes (training/cli.py 1 BLOCKER + 5 HIGH)~~

**Basis**: Audit A520 found 1 BLOCKER and 5 HIGH severity bugs in the `training/cli.py` GRPO implementation, explaining why the Trainer's GRPO smoke test could not produce results. These bugs block the production of NeurIPS paper training experiment data.

**Intent**: Fix gradient flow, loss computation, and resource management issues in the GRPO training pipeline to enable normal RL training.

#### Step 1 — Fix zero-loss fallback (BLOCKER)

**File**: `memorygym/training/cli.py:648-650`

**Problem**: When all trajectories have advantage ≈ 0 and are skipped, `total_loss = torch.tensor(0.0, requires_grad=True)` creates a tensor with no computation graph. `loss.backward()` produces zero gradients, and the model does not train.

**Fix**: Return an explicit marker (e.g., `None`) so the caller skips `backward()` + `optimizer.step()` for that step. Alternatively, use `0 * model_param.sum()` to create a zero loss connected to the model (but this is also suboptimal, wasting computation). Recommended: return `None` and handle it at the call site. Also add a warning log: `"GRPO step skipped: all trajectories filtered (advantage ≈ 0)"`.

#### Step 2 — Add warning for silent skipping (HIGH)

**File**: `memorygym/training/cli.py:582-583`

**Problem**: `if abs(advantage) < 1e-6: continue` has no logging. A large number of trajectories may be silently skipped, and the Trainer cannot see the reason.

**Fix**: Add `logger.warning("Skipping trajectory with near-zero advantage: %.6f", advantage)`. At the end of the function, report skip counts with a warning: `"GRPO loss: %d/%d trajectories used (skipped %d with |advantage| < 1e-6)"`.

#### Step 3 — Fix KL divergence computation (HIGH)

**File**: `memorygym/training/cli.py:624-627`

**Problem**: `ratio = torch.exp(mean_log_ratio)` computes exp at sequence-level, equivalent to the geometric mean. Then using this ratio for clipping amounts to PPO clipping on the "average ratio" of the entire sequence, rather than a per-token operation.

**Fix (choose one, A recommended)**:
- **A (per-token ratio, closer to GRPO)**: `ratio = torch.exp(log_ratio)` per-token, clipping done per-token, then `pg_loss = -(torch.min(surr1, surr2) * mask).sum() / n_tokens`
- **B (keep sequence-level but fix KL)**: KL penalty uses `mean_log_ratio` directly (which is already E[log(π/π_ref)]), no need for additional exp

Note: If choosing A, you also need to modify the clipping logic at cli.py:629-633 to be per-token.

#### Step 4 — Fix loss normalization consistency (HIGH)

**File**: `memorygym/training/cli.py:651-652`

**Problem**: When `n_valid > 1`, `total_loss / n_valid`, but when `n_valid == 1`, no division is performed.

**Fix**: Unify to `total_loss / n_valid` (when n_valid >= 1).

#### Step 5 — Remove inner-loop empty_cache + MemoryEnv resource leak (HIGH + MEDIUM)

**File**: `memorygym/training/cli.py:585, 470`

**Fix 1**: Remove `torch.cuda.empty_cache()` (:585), or move it to the outer step loop. Calling it in the inner loop causes 3-5x performance degradation.

**Fix 2**: In `_run_episode` (:470), after `env = MemoryEnv(...)`, add `try/finally: env.close()` to prevent ChromaDB resource leaks on exceptions.

#### Verification Criteria

1. `python -m pytest tests/ -q -m "not slow"` — all pass
2. `python -m pytest tests/test_training*.py -q` — training-related tests pass
3. Manual verification: `_compute_grpo_loss` returns `None` when all advantages are 0 (not a requires_grad=True zero tensor)
4. Manual verification: `_compute_grpo_loss` log output shows warning for skipped trajectories
5. Version number patch increment

---

## Backlog

- **Legacy tool name cleanup**: Remove memory_store/memory_forget/memory_get/memory_list from _KNOWN_TOOLS (wait until v3 eval baseline is stable)

## Completed

### Phase 135 — GRPO Code Path Fixes (per-token ratio + None loss + env.close + warning logs) ✅
### Phase 132 — validators.py regex fix: leading-dot decimals (v0.10.35) ✅
### Phase 131 — Training CLI help + API error friendliness (v0.10.34) ✅
### Phase 130 — Agent Runner robustness fixes (empty choices guard + edit refund guard, v0.10.33) ✅
### Phase 134 — Training module + bench.py robustness fixes (env.py out-of-bounds + adapters info init + bench.py except + client try/finally) ✅
### Phase 129 — Resource leak fixes (OpenAI clients close + bench.py try/finally + MarkdownBackend __del__) ✅
### Phase 128 — LEADERBOARD/README refresh (173 evals) + pyproject.toml version sync ✅
### Phase 127 — test_worlds.py fill in 4 missing template test coverage (6→10 templates) ✅
### Phase 126 — Inspect AI correction Edit free + prompt sync (consistent behavior across both paths) ✅
### Phase 125 — task_id stable mapping (TEMPLATE_REGISTRY + _parse_task_id rewrite) ✅
### Phase 124 — Concurrency & long-run resource leak fixes (MarkdownBackend/ChromaDB/bench.py close) ✅
### Phase 123 — LEADERBOARD.md refresh (150 evals, 10 templates, Qwen3-235B #1) ✅
### Phase 122 — Counterfactual validator routing fix + cross_domain dead code cleanup ✅
### Phase 121 — eval_salt constraint consistency fix (enforce_constraints hook, full 10-template coverage) ✅
### Phase 120 — agentteam C1 constraint fix (success+error ∈ [85,110] violation rate 40%→0%) ✅
### Phase 119 — README documentation sync (10 templates + Training quickstart + CLAUDE.md sync) ✅
### Phase 118 — agentteam world template (10th template, 23 attrs, 6 constraints, correction_rate=0.15) ✅
### Phase 117 — project world template + 117-fix quality fixes (9th template, 23 attrs, 4 constraints) ✅
### Phase 116 — Strategic documentation sync (ROADMAP.md + STATUS_REPORT.md, Phase 94-114 backfill) ✅
### Phase 114 — README leaderboard data sync (123 evals, Composite column) ✅
### Phase 113 — stdout score table axis scores consistency + smart_guesser<=5% + trajectory post-judge ✅
### Phase 112 — Correction Edit budget-free + message enhancement (maintenance axis fix) ✅
### Phase 111 — LEADERBOARD refresh (121 evals) + stream_agent context overflow graceful abstain ✅
### Phase 110 — validators.py comprehension question type routing completion (8 unrouted question types) ✅
### Phase 109 — LEADERBOARD.md 4-axis completion + leaderboard.py Reasoning/Efficiency columns ✅
### Phase 108 — CLI UX polish (table alignment/API pre-check/choices display/HF noise) ✅
### Phase 107 — Documentation sync: README/LEADERBOARD/pyproject.toml/EVALUATOR ✅
### Phase 106 — relationship_hop/chain validator dispatch + GT formatting parse ✅
### Phase 104 — SFT trajectory correction timing fix + Edit coverage improvement ✅
### Phase 102 — Correction tracking false positive fix ✅
### Phase 101 — university + codebase added to OFFICIAL_TEMPLATES ✅
### Phase 100 — SFT trajectory _compact_document use original values fix ✅
### Phase 99 — generate_stream ingest document rendering timing fix ✅
### Phase 98 — Correction guidance message enhancement ✅
### Phase 97 — Codebase world template (8th domain) ✅
### Phase 96 — University template Constraint 4 logic fix ✅
### Phase 94 — Dead code cleanup ✅
### Phase 88 — docs/ROADMAP.md sync update ✅
### Phase 93 — CLI UX fix: README tier defaults + help completion ✅
### Phase 91 — Question wording leakage fix (temporal_trend + comparison) ✅
### Phase 92 — RL reward aligned with 4-axis scoring + Edit shaped reward ✅
### Phase 89+90 — SFT trajectory budget overrun + json.dumps ✅
### Phase 87 — SFT trajectory consecutive user message merging ✅
### Phase 86 — test_path_consistency expansion + flaky test fix ✅
### Phase 85 — eval_task.py defaults + pyproject.toml version sync ✅
### Phase 84 — Inspect AI tool name mismatch fix ✅
### Phase 83 — MarkdownBackend recall benchmark ✅
### Phase 81+82 — Training infrastructure fixes ✅
### Phase 79+80 — Data quality fixes ✅
### Phase 78 — Comprehension question type full coverage testing ✅
### Phase 77 — events.py contradiction loss bug + mid-stream question weight inconsistency ✅
### Phase 76 — 3-path consistency automated testing ✅
### Phase 75 — Inspect AI path bug fix ✅
### Phase 74 — System prompt correction strategy leakage fix ✅
### Phase 73 — Version bug + Leaderboard composite ranking fix ✅
### Phase 72 — Simulation axis score invariant verification ✅
### Phase 71 — Event format strategy hint removal ✅
### Phase 70 — ChromaDB Edit fallback silent failure fix ✅
### Phase 69 — MarkdownBackend temporal decay search ✅
### Phase 68 — RNG alignment + env.py drift fix ✅
### Phase 67 — MemoryEnv resource leak fix ✅
### Phase 65 — training/env.py Edit path aligned with eval ✅
### Phase 64 — eval_task.py tool interface sync ✅
### Phase 63 — training/env.py tool behavior aligned with eval ✅
### Phase 62 — MarkdownBackend integrated into bench.py + training env ✅
### Phase 61 — stream_agent.py split ✅
### Phase 60 — Phase 59 remaining bug fixes ✅
### Phase 59 — Tool interface OpenClaw migration ✅
### Phase 58 — Remove mem0 backend ✅
### Phase 57 — System prompt neutralization ✅
### Phase 53-56 — RL training smoke test + import style + silent exceptions + test streamlining ✅
### Phase 51 — MemoryEnv process-based reward enhancement ✅
### Phase 50 — verl_adapter private API fix + adapter robustness ✅
### Phase 49 — Inspect AI improvements + critical module test completion ✅
### Phase 3-48 — Base system → eval iteration → template enhancement → RL training ✅
