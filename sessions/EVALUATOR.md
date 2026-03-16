# EVALUATOR — Evaluation Thread

> Launch: `/loop 10m You are the evaluation thread, read sessions/EVALUATOR.md and execute the next evaluation task`
>
> Dedicated evaluation thread. Only runs model evaluations, does not modify code.
>
> **Important**: v1 data (10-attribute templates) has been archived to `eval/archive_v1/`. All batches below are based on Phase 16 enhanced templates (22-23 attributes, 6 dtypes, 18 reasoning question types).

## Workflow

```
1. Read this file, find the "Current Task"
2. Execute evaluation command
   - Evaluations of different models can run concurrently (they use independent APIs and independent eval files)
   - Different seeds/templates for the same model can also run concurrently
   - Fully leverage concurrency to accelerate data accumulation
3. Check results: success: true → valid, otherwise handle as failure
4. Record results to "Completed", update ROADMAP.md §3 data table
5. Promote next to-do as current task
6. Queue empty → stop, wait for new tasks to be written
```

## Evaluation Standards

**Command template**:
```bash
python -m memorygym.bench --model <MODEL> --seed <SEED> --template <TEMPLATE> [--tier lite] [--backend chromadb]
```

**Failure handling**:
- API 503/429/timeout → Rename result file to `*.503_error.json`, do not include in data table
- Only results with `"success": true` are valid data
- 3 consecutive API failures → Skip that task, mark as blocked, move to next

**Result recording**:
- eval JSON is automatically saved to the `eval/` directory
- After each task completion, append scores to the "Completed" section of this file
- After completing a batch of similar tasks (e.g., same model multiple seeds), aggregate mean±std to ROADMAP.md §3

**Do NOT do the following**:
- Do not modify code (code changes are handled by the development session)
- Do not modify sessions/EXECUTOR.md or CLAUDE.md
- Do not run tests (pytest)
- Do not commit code (git commit)

## Available Models

Sorted by evaluation value (Chutes platform, base_url does not need to be specified, code handles it automatically):
- `Qwen/Qwen3.5-397B-A17B-TEE` — Strongest open-source, 397B MoE
- `Qwen/Qwen3-235B-A22B-Instruct-2507-TEE` — Second strongest
- `moonshotai/Kimi-K2.5-TEE` — Model with the most data
- `MiniMaxAI/MiniMax-M2.5-TEE`
- `zai-org/GLM-5-TEE`

## Available Templates

company, research, city, hospital, sport, movie, university, codebase (8 total, each with 21-23 attributes)

---

## Current Task

### Batch 34 — Post-Phase 112 Coverage Completion (8 templates × multiple models)

**Background** (A213 audit): Phase 112 (correction Edit budget-free) is the highest-impact change in project history, but only 8/123 evals are post-Phase 112 (v>=0.10.15). 4 templates have zero post-112 data. LEADERBOARD rankings mainly reflect old version performance.

**Goal**: Complete post-Phase 112 evaluation coverage, at least 2 evals per missing template.

**Priority 1 — Missing templates** (0 post-112 evals):
```bash
# university (2 evals)
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template university
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template university

# codebase (2 evals)
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template codebase
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template codebase

# sport (2 evals)
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template sport
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template sport

# movie (2 evals)
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template movie
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template movie
```

**Priority 2 — Supplemental testing for templates with limited data**:
```bash
# city (only 1 post-112, M=0%)
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 1 --template city

# research (only 1 post-112)
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 1 --template research
```

**Completion criteria**: At least 8 new evals (Priority 1), ideally 10 (including Priority 2). All success:true.

**Priority 1 Results (8/8 completed ✅, all v0.10.17)**:

| Model | Template | Comp | B | M | R | E | Stored |
|-------|----------|------|---|---|---|---|--------|
| Qwen3.5 | university s0 | **46%** | 57% | 33% | 57% | 30% | 36 |
| Qwen3.5 | movie s0 | **43%** | 57% | 50% | 33% | 27% | — |
| Kimi | codebase s0 | 19% | 20% | 33% | 11% | 10% | 34 |
| Kimi | university s0 | 14% | 14% | 33% | 0% | 7% | 33 |
| Qwen3.5 | codebase s0 | 12% | 0% | 33% | 11% | 7% | 35 |
| Qwen3.5 | sport s0 | 9% | 17% | 0% | 12% | 7% | 35 |
| Kimi | sport s0 | 9% | 17% | 0% | 12% | 7% | 15 |
| Kimi | movie s0 | 0% | 0% | 0% | 0% | 0% | 33 |

**P1 Summary**: M>0% = 5/8 (63%). Qwen3.5 university/movie broke through 40%+. Kimi movie all zeros (ChromaDB retrieval completely failed).

**Priority 2 Results (2/2 completed ✅, all v0.10.17)**:

| Model | Template | Comp | B | M | R | E | Stored |
|-------|----------|------|---|---|---|---|--------|
| Qwen3.5 | research s1 | **24%** | 43% | 33% | 0% | 13% | 33 |
| Kimi | city s1 | **16%** | 12% | 24% | 17% | 10% | 29 |

**Batch 34 Completed ✅ (10/10 evals, all v0.10.17)**

**Phase 112 Key Findings**:
- **M>0%**: 7/10 (70%) — far exceeding B33's 44%
- **New all-time highs**: Qwen3.5 university 46%, Qwen3.5 movie 43%
- **Movie M=50%**: First time in history maintenance exceeded 33%
- **Kimi movie 0%**: ChromaDB search completely failed (movie entity name high-similarity issue persists)
- **Sport M=0%**: Both models at 0% (sport corrections search is difficult)

---

### Batch 24 — Version Deviation Verification (Qwen3.5 hospital s0 re-run) ✅

**Purpose**: Verify version deviation hypothesis (H1 seed variance vs H2 version regression).

**Results** (v0.10.9, Qwen3.5-397B, hospital s0):

| Metric | B19 (v0.10.4) | B24 (v0.10.9) | Change |
|------|-------------|-------------|------|
| Composite | 45% | **25%** | -20% |
| Breadth | 56% | 44% | -12% |
| Maintenance | 0% | 0% | — |
| Reasoning | 33% | 33% | — |
| Efficiency | — | 16.7% | — |
| Stored | 36 | 30 | -6 |

**Conclusion**: **H1 confirmed + new finding H3 (LLM API non-determinism)**.
- Phases 100-106 were all training-side or validator supplements, not affecting hospital s0 eval path
- Difference source: B19 model packing (36 entities/30 writes), B24 no packing (30 entities/30 writes)
- This is LLM API behavioral variance (temperature/sampling), not version regression
- Single eval variance for the same seed can reach ±20%, need ≥3 seeds mean for reliability

---

### Batch 23 — Qwen3.5 Multi-seed Expansion (Stable Ranking + Weak Template Diagnosis) ✅

**Qwen3.5 Three-seed Summary (v0.10.5-0.10.9, chromadb)**:

| Template | s0 | s1 | s2 | Mean | Std Dev | B Mean | R Mean |
|------|----|----|----|----|--------|-------|-------|
| university | 28.3% | 13.2% | 16.8% | **19.4%** | ±7.9% | 42.6% | 15.1% |
| research | 22.4% | 14.9% | 18.9% | **18.7%** | ±3.8% | 39.7% | 16.7% |
| company | 24.4% | 9.9% | 10.1% | **14.8%** | ±8.4% | 21.8% | 25.1% |
| movie | 18.3% | 4.4% | 9.9% | **10.9%** | ±7.0% | 28.0% | 3.7% |

**Key Findings**:

1. **Variance confirmed**: All templates have s0 as highest score (18-28%), s1-2 drop significantly. s0 may have systematic optimistic bias (s0 is from older version v0.10.4-0.10.5, later versions score more strictly? Needs audit thread investigation)
2. **Movie reasoning confirmed low**: 3-seed mean only 3.7% (s1=0%, s2=0%, only s0=11%)
3. **Company reasoning variance is extreme**: s0=50%, s1=14%, s2=11%
4. **Research most stable**: Std dev only ±3.8%
5. **Maintenance all zeros**: 12/12 evals all 0%

**Template difficulty ranking (3-seed mean)**: university(19.4%) > research(18.7%) > company(14.8%) > movie(10.9%)

---

### Batch 22 — Kimi Remaining 4 Templates + Qwen3.5 Multi-seed Variance Measurement ✅

**Kimi-K2.5 post-Phase99 Results (v0.10.8, seed 0)**:

| Template | Composite | Stored | Breadth | Maint. | Reasoning | Abstention |
|------|-----------|--------|---------|--------|-----------|------------|
| sport | **26%** | 34 | 33% | 0% | 14% | 100% |
| research | **21%** | 33 | 33% | 0% | 0% | 100% |
| movie | **11%** | 15 | 0% | 0% | 0% | 100% |
| city | **0%** | 33 | 0% | 0% | 0% | 100% |

**Qwen3.5 hospital Variance Measurement**:

| Seed | Composite | Stored | Breadth | Maint. | Reasoning |
|------|-----------|--------|---------|--------|-----------|
| s0 | **45%** | 36 | 56% | 0% | 33% |
| s1 | **30%** | 30 | 43% | 0% | 33% |
| Gap | -15% | -6 | -13% | — | — |

**Key Findings**:
- **Kimi movie only stored 15 entities** (budget=30) — extremely conservative strategy, lowest Composite (11%)
- **Kimi sport 26%**: Weakest template in B1 era (10%), significant improvement post-Phase99
- **Kimi research Reasoning=0%**: All 8 reasoning questions answered "uncertain"
- **Kimi city 0%** (v0.10.7 re-run): Stored 33 entities but all axes are 0%, search recall completely failed
- **Qwen3.5 hospital variance ±15%**: s0=45% vs s1=30%, significant inter-seed variance, more seeds needed for stable ranking

**Cross-model Comparison (post-Phase99 all 8 templates s0)**:

| Template | Qwen3.5 | Kimi | Gap |
|------|---------|------|------|
| hospital | 45% | 40% | -5% |
| university | 40% | 25% | -15% |
| company | 40% | 25% | -15% |
| research | 35% | **21%** | -14% |
| codebase | 35% | 25% | -10% |
| movie | 30% | **11%** | -19% |
| sport | 25% | **26%** | **+1%** |
| city | 20% | **0%** | -20% |
| **Mean** | **34%** | **22%** | -12% |

---

### Batch 21 — Qwen3.5 Full 8-Template Baseline Completed + Kimi New Templates ✅

**Purpose**:
1. Qwen3.5 movie + city s0 — Complete full 8-template post-Phase99 baseline
2. Kimi-K2.5 university + codebase — Cross-model new template coverage

**Qwen3.5 Results (v0.10.5)**:

| Template | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections | Stored |
|------|-----------|---------|--------|-----------|------------|-------------|--------|
| movie | **30%** | 43% | 0% | 11% | 100% | **1/5** | 36 |
| city | **20%** | 12% | 0% | 0% | 100% | 0/5 | 36 |

**Kimi-K2.5 New Template Results (v0.10.5)**:

| Template | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections | Stored |
|------|-----------|---------|--------|-----------|------------|-------------|--------|
| university | **25%** | 14% | 0% | 14% | 100% | 0/5 | 17 |
| codebase | **25%** | 20% | 0% | 11% | 100% | 0/5 | 33 |

**Key Findings**:
- **Movie Corrections 1/5**: `Steel Legacy.awards_count: search → edit` succeeded! Qwen3.5 post-Phase99 **first time completing a correction in a real eval**
- **Movie conditional 100%** (1/1): Conditional reasoning succeeded
- **City Reasoning 0%**: Only template out of 8 with all-zero reasoning, stored 36 entities but retrieval/computation all failed
- **Kimi university only stored 17 entities** (budget=30), storage strategy too conservative

**Qwen3.5 Full 8-Template post-Phase99 Baseline**:

| Template | Composite | Breadth | Reasoning | Corrections |
|------|-----------|---------|-----------|-------------|
| hospital | **45%** | 56% | 33% | 0/5 |
| university | **40%** | 57% | 29% | 0/5 |
| company | **40%** | 29% | 50% | 0/5 |
| research | **35%** | 43% | 25% | 0/5 |
| codebase | **35%** | 20% | 33% | 0/5 |
| movie | **30%** | 43% | 11% | **1/5** |
| sport | **25%** | 17% | 25% | 0/5 |
| city | **20%** | 12% | 0% | 0/5 |
| **Mean** | **33%** | **35%** | **26%** | — |

**Cross-model Comparison (post-Phase99 s0)**:
| Template | Qwen3.5 | Kimi-K2.5 | Gap |
|------|---------|-----------|------|
| hospital | 45% | 40% | -5% |
| company | 40% | 25% | -15% |
| university | 40% | 25% | -15% |
| codebase | 35% | 25% | -10% |

---

### Batch 20 — New Template First Evaluation + Cross-model Verification ✅

**Purpose**:
1. University + Codebase template first real model evaluation (Qwen3.5, seed 0)
2. Kimi-K2.5 post-Phase99 verification (hospital + company, compared to B19 Qwen3.5)

**Tasks** (4 tasks, can run concurrently):
```bash
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template university
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template codebase
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template hospital
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template company
```

**Expected**:
- University/Codebase: First data, no baseline comparison. Expected Composite 25-40% (consistent with other template ranges)
- Kimi hospital: B1=17%, expected improvement after Phase 99
- Kimi company: B1=30%, expected stable or improved after Phase 99

**Qwen3.5 New Template Results (v0.10.5)**:

| Template | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections | Stored |
|------|-----------|---------|--------|-----------|------------|-------------|--------|
| university | **40%** | 57% | 0% | 29% | 67% | 0/5 | 36 |
| codebase | **35%** | 20% | 0% | 33% | 100% | 0/5 | 36 |

**Key Findings**:
- **University 40%**: First evaluation reached second-highest score in history (behind only hospital 45%). Breadth 57% extremely strong
- **Codebase 35%**: Mid-level. Breadth 20% relatively low, but Reasoning 33% stable
- **University Abstention 67%**: **First time below 100%**! Model made incorrect guesses on 1/3 of unstored entities instead of abstaining
- **relationship_lookup 100%** (codebase): Relationship reasoning succeeded in real eval for the first time
- **temporal_trend 100%** (university): Temporal trend reasoning succeeded
- **Corrections all 0/5**: Consistent with other templates, budget exhausted

**Kimi-K2.5 Results (v0.10.5, post-Phase99)**:

| Template | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections | Stored |
|------|-----------|---------|--------|-----------|------------|-------------|--------|
| hospital | **40%** | 56% | 0% | 0% | 100% | 0/5 | 30 |
| company | **25%** | 14% | 0% | 17% | 100% | 0/5 | 35 |

**Cross-version Comparison (Kimi-K2.5 s0)**:
| Template | B1(v1) | B20(v0.10.5) | Change |
|------|--------|-------------|------|
| hospital | 17% | **40%** | **+23%** |
| company | 30% | **25%** | -5% |

**Cross-model Comparison (post-Phase99, s0)**:
| Template | Qwen3.5 | Kimi-K2.5 | Gap |
|------|---------|-----------|------|
| hospital | 45% | 40% | -5% |
| company | 40% | 25% | -15% |

**Key Findings**:
- **Kimi hospital +23%**: Phase 99 effect equally significant for Kimi
- **Kimi company -5%** (30→25%): Unexpected decline. Breadth dropped from B1's 17% to 14%. Kimi's search recall rate is poor for company
- **relationship_count 100%**: Kimi company relationship reasoning succeeded
- Kimi overall weaker than Qwen3.5 (hospital -5%, company -15%), main gap is in Reasoning

---

### Batch 18 — Phase 98 Correction Guidance Verification ✅

**Purpose**: Phase 98 enhanced correction message guidance + Edit tool description. Verify if Corrections improved from 0/5.

**Qwen3.5-397B (seed 0, v0.10.3, chromadb)**:

| Template | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections | Stored |
|------|-----------|---------|--------|-----------|------------|-------------|--------|
| hospital | **25%** | 11% | 20% | 0% | 100% | 0/5 | 36 |
| company | **30%** | 29% | 0% | 17% | 100% | 0/5 | 36 |

**Key Findings**:
- **Corrections still 0/5**, but behavioral pattern consistently improved: all correction operations executed search (Phase 98 guidance effective)
- **Root cause confirmed (audit A135)**: `generate_stream()` ingest documents rendered with corrected values → corrections effectively no-op
  - Model stored corrected values during ingest phase, correction notice is a no-op
  - All 5/5 corrections had writes balance = 0 (even without the bug, budget exhaustion would block Edit)
- **Phase 99 dispatched** (P0 highest priority) to fix this bug
- Batch 18 data marked as **pre-fix**, needs re-run after Phase 99

**Comparison with Batch 17**:
| Metric | B17 hospital | B18 hospital | B17 no company | B18 company |
|------|-------------|-------------|----------------|-------------|
| Composite | 25% | 25% | — | 30% |
| Maintenance | 0% | 20% | — | 0% |

---

### Batch 19 — Post-Phase 99 Fix Verification ✅

**Purpose**: After Phase 99 fixed the ingest document rendering timing bug, verify evaluation behavior changes.

**Full 4-Template Comparison (Qwen3.5-397B, seed 0, v0.10.4+ post-Phase99)**:

| Template | B17 Composite | B19 Composite | Change | B19 Breadth | B19 Reasoning | B19 Maint. | Stored |
|------|-------------|---------------|------|-------------|---------------|------------|--------|
| hospital | 25% | **45%** | **+20%** | 56% | 33% | 0% | 36 |
| company | 30% | **40%** | **+10%** | 29% | 50% | 0% | 32 |
| research | 35% | **35%** | — | 43% | 25% | 0% | 33 |
| sport | 15% | **25%** | **+10%** | 17% | 25% | 0% | 35 |
| **Mean** | **26%** | **36%** | **+10%** | **36%** | **33%** | **0%** | **34** |

**Research Results (v0.10.5)**: Composite unchanged at 35%, Breadth 43% (=B17), Reasoning 25% (B17=12%, +13%). Corrections 0/5 (5/5 search miss — unstored entities).

**Sport Results (v0.10.5)**: Composite 25% (+10%), Breadth 17% (B17=0%, +17%), Reasoning 25% (B17=12%, +13%). Corrections 0/5.

**Hospital Results (v0.10.4, post-Phase99)**:

| Metric | B18 (pre-fix) | B19 (post-fix) | Change |
|------|-------------|---------------|------|
| **Composite** | 25% | **45%** | **+20%** |
| **Breadth** | 11% | **56%** | **+45%** |
| Maintenance | 20% | 0% | -20% |
| **Reasoning** | 0% | **33%** | **+33%** |
| Corrections | 0/5 | 0/5 | — |
| Stored | 36 | 36 | — |

**Key Findings**:
- **Composite +20%**: After Phase 99 fixed document consistency, model storage quality improved dramatically
- **Breadth 56%** (all-time high): After ingest documents used original values, model retrieval/answer consistency significantly improved
- **Reasoning 33%**: Improved from 0%, indicating model stored correct data
- **Maintenance 0%**: Expected behavior — after fix, ingest stores original values, model did not Edit after correction, update question GT is corrected value → mismatch
- **Prairie Clinic: search → edit**: **First time in history** observing model attempting Edit in a real eval!

**Company Results (v0.10.4, post-Phase99)**:

| Metric | B18 (pre-fix) | B19 (post-fix) | Change |
|------|-------------|---------------|------|
| Composite | 30% | **40%** | **+10%** |
| Breadth | 29% | 29% | — |
| Maintenance | 0% | 0% | — |
| Reasoning | 17% | **50%** | **+33%** |
| Corrections | 0/5 | 0/5 | — |
| Stored | 36 | 32 | -4 |

**Batch 19 Summary**:
- **Phase 99 verification successful**: 4-template mean 26→36% (+10%), 3/4 templates with significant Composite improvement
- **Reasoning is the biggest beneficiary axis**: All 4 templates Reasoning improved (hospital 0→33%, company 17→50%, research 12→25%, sport 12→25%)
- **Breadth**: hospital 56% (all-time high), research 43% (unchanged), sport 0→17%
- **Maintenance all 0%**: Expected behavior — model exhausted budget, unable to Edit
- **Corrections all 0/5**: Root cause is budget exhaustion (writes=0 at correction time), need to train model to reserve budget
- **Research unchanged**: 35%→35%, Composite unchanged but internal Reasoning improved (12→25%)
- **All-time high composites**: hospital 45% and company 40% are both Qwen3.5 all-time highs for those templates

---

### Batch 17 — Multi-template v0.10.x Baseline ✅

**Qwen3.5-397B (seed 0, v0.10.2, chromadb)**:

| Template | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections | Stored |
|------|-----------|---------|--------|-----------|------------|-------------|--------|
| hospital | **25%** | 22% | 0% | 0% | 100% | 0/5 | 36 |
| sport | **15%** | 0% | 0% | 12% | 100% | 0/5 | 35 |
| research | **35%** | 43% | 33% | 12% | 100% | 0/5 | 33 |

**Key Findings**:
- Corrections = 0/5 across ALL 3 templates — model completely does not execute correction operations (consistent with batch 12 v3)
- Maintenance = 0% on hospital/sport (correction_rate=0.15/0.10 but model does not use Edit)
- Research strongest (35%), breadth=43% significantly higher than other templates
- Sport weakest (15%), breadth=0% (model search recall is poor)
- Abstention = 100% (neutral prompt is effective)

**Cross-version Comparison** (Qwen3.5 hospital s0):
- v3 (batch 12, stdout): 45% → v0.6.7 (batch 13): 35% → **v0.10.2: 25%** — continuous decline
- Cause pending analysis: possibly related to Phase 91 wording changes, eval_salt changes

---

### Batch 16 — Post-Phase 77 Fix Baseline ✅ (company portion, hospital/sport deferred to batch 17)

**Purpose**: Phase 77 changed mid-stream question weight allocation (using template question_weights instead of hardcoded) and contradiction batch fix. Compare score changes before and after v0.7.x.

**Tasks**: Qwen3.5 (strongest open-source) × 3 templates × seed 0, 3 evaluations total.

```bash
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template company --official -o eval/Qwen_Qwen3.5-397B-A17B-TEE_company_s0_v3.json
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template hospital --official -o eval/Qwen_Qwen3.5-397B-A17B-TEE_hospital_s0_v3.json
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template sport --official -o eval/Qwen_Qwen3.5-397B-A17B-TEE_sport_s0_v3.json
```

**Focus areas**:
- hospital composite change (update weight from hardcoded 25% → template 30%)
- sport composite change (update weight from 25% → template 25%, should be essentially unchanged)
- Version differences compared to batch 14/15 data

---

### Batch 12 — v3 Baseline (⚠️ JSON not saved, needs re-run)

6/6 evaluations completed computation but crashed when saving JSON (`AttributeError: 'Namespace' object has no attribute 'backend'` at bench.py:316). Scores manually recorded from stdout:

**Qwen3.5-397B (seed 0, v3 tool interface)**:

| Model | Template | Composite | Abstention | Retrieval | Update | Corrections |
|------|------|-----------|------------|-----------|--------|-------------|
| Qwen3.5-397B | company | **25%** | 100% | 11% | 33% | 0/5 |
| Qwen3.5-397B | research | **30%** | 100% | 20% | 0% | 0/5 |
| Qwen3.5-397B | hospital | **45%** | 100% | 33% | 60% | 0/5 |
| **Mean** | | **33%** | 100% | 21% | 31% | |

**Kimi-K2.5 (seed 0, v3 tool interface)**:

| Model | Template | Composite | Abstention | Retrieval | Update | Corrections |
|------|------|-----------|------------|-----------|--------|-------------|
| Kimi-K2.5 | company | **20%** | 100% | 11% | 0% | 0/5 |
| Kimi-K2.5 | research | **20%** | 100% | 0% | 0% | 0/5 |
| Kimi-K2.5 | hospital | **40%** | 100% | 22% | 20% | 0/5 |
| **Mean** | | **27%** | 100% | 11% | 7% | |

**v3 Baseline Analysis**:
- **Corrections = 0/5 across ALL 6 evals**: Model used Write instead of Edit for corrections — correction event message still says search→forget→store (Bug 2), model doesn't know to use Edit
- Abstention = 100% all correct: Under neutral prompt, model no longer guesses randomly
- Qwen3.5 > Kimi (33% vs 27%), hospital strongest for both
- **Note**: These scores were not saved as JSON, needs re-run after fixing Phase 60 Bug 2+4

## Completed

### Batch 15 — Weak Model Coverage Expansion (Completed ✓, 2026-03-11)

6/6 JSON saved (v0.6.7, chromadb, seed 1).

**GLM-5 (seed 1)**:

| Model | Template | Composite | B | M | R | Corrections |
|------|------|-----------|---|---|---|-------------|
| GLM-5 | company | **40%** | 25% | 67% | 29% | 2/5 |
| GLM-5 | research | **40%** | 29% | 33% | 29% | 0/5 |
| GLM-5 | hospital | **30%** | 25% | 14% | 33% | 0/5 |
| **Mean** | | **37%** | 26% | 38% | 30% | |

**MiniMax-M2.5 (seed 1)**:

| Model | Template | Composite | B | M | R | Corrections |
|------|------|-----------|---|---|---|-------------|
| MiniMax | company | **30%** | 0% | 33% | 43% | 0/5 |
| MiniMax | research | **15%** | 14% | 0% | 0% | 1/5 |
| MiniMax | hospital | **35%** | 25% | 43% | 0% | 1/5 |
| **Mean** | | **27%** | 13% | 25% | 14% | |

**Key Findings**:
- GLM-5 s1=37% far exceeds s0=0% (s0 search returning all empty is an outlier, not true capability)
- MiniMax s1=27% > s0=13%, closer to true level
- GLM-5 company corrections 2/5 is the best among weak models

### Batch 14 — MarkdownBackend Comparison ✅

Qwen3.5 × 3 templates × seed 0, `--backend markdown`.

| Model | Template | ChromaDB | Markdown | Difference |
|------|------|----------|----------|------|
| Qwen3.5 | company | 30% | 25% | -5% |
| Qwen3.5 | research | 30% | 35% | +5% |
| Qwen3.5 | hospital | 35% | 30% | -5% |
| **Mean** | | **31.7%** | **30.0%** | **-1.7%** |

**Conclusion**: No significant difference. Retrieval bottleneck is on the model side (entities_per_write=1.0), not backend search precision.

### Batch 13 — v3 Baseline Re-run ✅

2 models × 3 templates × seed 0, v0.6.7. Data complete after Bug 2+4 fix.

| Model | Template | Score | Breadth | Maint. | Reasoning | Efficiency |
|------|------|-------|---------|--------|-----------|------------|
| Qwen3.5 | company | 30% | 11% | 67% | 17% | 13% |
| Qwen3.5 | research | 30% | 20% | 0% | 22% | 10% |
| Qwen3.5 | hospital | 35% | 22% | 20% | 33% | 13% |
| Kimi | company | 35% | 33% | 33% | — | — |
| Kimi | research | 25% | — | 20% | — | — |
| Kimi | hospital | 30% | — | 58% | — | — |

**Improvement vs batch 12**: Corrections >0 (Bug 2 fix confirmed), JSON saved normally (Bug 4 fix confirmed).

### Batch 11 — Qwen3-235B Full Template + MiniMax Expansion (Completed)

Qwen3-235B 6 templates seed 0 + MiniMax 4 new templates seed 0.

**Qwen3-235B (seed 0, lite tier)**:

| Model | Template | Composite | Breadth | Maint. | Reasoning | Efficiency | Writes |
|------|------|-----------|---------|--------|-----------|------------|--------|
| Qwen3-235B | company | **28%** | 33% | 58% | 0% | 17% | 30/30 |
| Qwen3-235B | research | **19%** | 20% | 33% | 11% | 10% | 30/30 |
| Qwen3-235B | city | **15%** | 10% | 42% | 0% | 7% | 25/30 |
| Qwen3-235B | hospital | **28%** | 33% | 54% | 0% | 20% | 30/30 |
| Qwen3-235B | sport | **14%** | 0% | 50% | 0% | 7% | 30/30 |
| Qwen3-235B | movie | **17%** | 12% | 48% | 0% | 7% | 25/30 |
| **Mean** | | **20%** | 18% | 48% | 2% | 11% | |

**MiniMax-M2.5 New Templates (seed 0, lite tier)**:

| Model | Template | Composite | Breadth | Maint. | Reasoning | Efficiency | Writes |
|------|------|-----------|---------|--------|-----------|------------|--------|
| MiniMax-M2.5 | research | **12%** | 0% | 30% | 11% | 7% | 30/30 |
| MiniMax-M2.5 | city | **18%** | 0% | 50% | 17% | 7% | 30/30 |
| MiniMax-M2.5 | hospital | **0%** | 0% | 0% | 0% | 0% | 30/30 |
| MiniMax-M2.5 | sport | **21%** | 0% | 75% | 0% | 10% | 29/30 |
| **Mean** | | **13%** | 0% | 39% | 7% | 6% | |

**Analysis**:
- Qwen3-235B mean 20%, strongest area is Maintenance (48%), Reasoning near zero (only research 11%)
- MiniMax hospital=0%: 29 entities stored but search all returned empty (same issue as GLM-5)
- MiniMax Breadth all 0%: Search recall extremely poor, but Maintenance surprisingly decent (stored updates but cannot find original data)

### Batch 10 — Cross-tier Multi-seed Verification (Previously completed, see context above)

Batches 6-8 found hard(24%) > standard(12%), counter-intuitive. Batch 10 data completed in previous session.

### Batch 9 — mem0 Backend Evaluation (⛔ Blocked, skipped)

3 consecutive failures, marked as blocked. Errors:
1. `attempt to write a readonly database` — qdrant/sqlite concurrency lock issue, DB becomes readonly after first batch of ingest
2. `RuntimeError: mem0 extracted no facts from content` — mem0 LLM (Qwen3-235B) unable to extract facts from structured documents

**Root cause**: mem0 internally uses qdrant local mode (SQLite storage), concurrent writes cause lock escalation to readonly. Even if a single write succeeds, subsequent writes fail due to readonly. Requires executor to re-examine mem0 backend concurrency safety.

### Batch 8 — Multi-tier Multi-session First Test (Completed)

Phase 42 multi tier (3 sessions). Kimi-K2.5 seed 0.

| Model | Template | Tier | Composite | Breadth | Maint. | Reasoning | Efficiency | Writes |
|------|------|------|-----------|---------|--------|-----------|------------|--------|
| Kimi-K2.5 | company | multi | **8%** | 22% | 0% | 0% | 7% | 29/30 |
| Kimi-K2.5 | research | multi | **20%** | 0% | 60% | 11% | — | 30/30 |
| Kimi-K2.5 | city | multi | **31%** | 20% | 90% | 0% | — | 28/30 |

**Note**: company multi score far lower than research/city, mainly because maintenance=0% (update information completely lost after 3 sessions).

### Batch 7 — Hard Tier (Completed)

| Model | Template | Tier | Composite | Breadth | Maint. | Reasoning | Efficiency | Writes |
|------|------|------|-----------|---------|--------|-----------|------------|--------|
| Kimi-K2.5 | company | hard | **24%** | 18% | 23% | 23% | 33% | 27/30 |

120 entities, 40 questions, 10 corrections. Stored 25/120 (21%). Strengths: multi_constraint=100%, enum_filter=100%, comparison=100%. Weaknesses: temporal=0%, synthesis=0%.

### Batch 6 — Standard Tier (Completed)

| Model | Template | Tier | Composite | Breadth | Maint. | Reasoning | Efficiency | Writes |
|------|------|------|-----------|---------|--------|-----------|------------|--------|
| Kimi-K2.5 | company | standard | **12%** | 11% | 31% | 0% | 7% | 28/30 |

60 entities, 20 questions, 5 corrections. Stored 28/60 (47%). Reasoning=0% all answered incorrectly.

**Cross-tier Comparison (Kimi-K2.5 company s0)**:

| Tier | Entities | Questions | Composite | Breadth | Maint | Reasoning |
|------|----------|-----------|-----------|---------|-------|-----------|
| lite (B1) | 40 | 15 | 30% | 17% | 20% | 33% |
| standard (B6) | 60 | 20 | 12% | 11% | 31% | 0% |
| hard (B7) | 120 | 40 | 24% | 18% | 23% | 23% |
| multi (B8) | 60 | 20 | 8% | 22% | 0% | 0% |

**Findings**: Hard tier actually scored higher than standard, possibly because 40 questions cover more competency types. Multi tier lowest (8%), session break severely impacts memory continuity.

### Batch 1 — Smoke Test (Completed)

| Model | Template | Seed | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections |
|------|------|------|-----------|---------|--------|-----------|------------|-------------|
| Kimi-K2.5 | company | 0 | **30%** | 17% | 20% | 33% | 100% | 4/5 |
| Kimi-K2.5 | research | 0 | **15%** | 0% | 33% | 0% | 100% | 3/5 |
| Kimi-K2.5 | city | 0 | **20%** | 33% | 31% | 0% | 100% | 2/5 |
| Kimi-K2.5 | hospital | 0 | **17%** | 11% | 26% | 20% | 100% | 2/5 |
| Kimi-K2.5 | sport | 0 | **10%** | 0% | 0% | 33% | 100% | 2/5 |
| Kimi-K2.5 | movie | 0 | **21%** | 12% | 62% | 0% | 100% | 2/3 |

### Batch 2 — Kimi-K2.5 Multi-seed (Completed)

| Model | Template | Seed | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections |
|------|------|------|-----------|---------|--------|-----------|------------|-------------|
| Kimi-K2.5 | company | 1 | **41%** | 25% | 100% | 17% | 100% | 4/5 |
| Kimi-K2.5 | company | 2 | **15%** | 0% | 25% | 25% | 100% | 2/5 |
| Kimi-K2.5 | research | 1 | **42%** | 33% | 75% | 33% | 100% | 3/5 |
| Kimi-K2.5 | research | 2 | **34%** | 25% | 72% | 17% | 100% | 5/5 |
| Kimi-K2.5 | city | 1 | **36%** | 22% | 67% | 33% | 100% | 3/5 |
| Kimi-K2.5 | city | 2 | **0%** | 0% | 0% | 0% | 100% | 2/5 |
| Kimi-K2.5 | hospital | 1 | **0%** | 0% | 0% | 0% | 100% | 1/5 |
| Kimi-K2.5 | hospital | 2 | **14%** | 0% | 50% | 0% | 100% | 4/5 |
| Kimi-K2.5 | sport | 1 | **4%** | 12% | 0% | 0% | 100% | 2/5 |
| Kimi-K2.5 | sport | 2 | **32%** | 38% | 50% | 17% | 100% | 1/5 |
| Kimi-K2.5 | movie | 1 | **13%** | 12% | 33% | 0% | 100% | 3/5 |
| Kimi-K2.5 | movie | 2 | **31%** | 11% | 87% | 14% | 100% | 1/5 |

### Batch 3 — Qwen3.5-397B Cross-evaluation (Completed)

| Model | Template | Seed | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections |
|------|------|------|-----------|---------|--------|-----------|------------|-------------|
| Qwen3.5-397B | company | 0 | **40%** | 22% | 67% | 50% | 100% | 4/5 |
| Qwen3.5-397B | research | 0 | **14%** | 20% | 0% | 22% | 100% | 4/5 |
| Qwen3.5-397B | city | 0 | **0%** | 0% | 0% | 0% | 100% | 0/5 |
| Qwen3.5-397B | hospital | 0 | **19%** | 22% | 37% | 0% | 100% | 1/5 |
| Qwen3.5-397B | sport | 0 | **41%** | 22% | 100% | 20% | 100% | 2/5 |
| Qwen3.5-397B | movie | 0 | **13%** | 0% | 50% | 0% | 100% | 3/5 |

### Batch 4 — MiniMax + GLM-5 Baseline (Completed)

| Model | Template | Seed | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections |
|------|------|------|-----------|---------|--------|-----------|------------|-------------|
| MiniMax-M2.5 | company | 0 | **13%** | 11% | 32% | 0% | 0% | 3/5 |
| MiniMax-M2.5 | movie | 0 | **4%** | 12% | 0% | 0% | 50% | 1/5 |
| GLM-5 | company | 0 | **0%** | 0% | 0% | 0% | 50% | 0/5 |
| GLM-5 | movie | 0 | **0%** | 0% | 0% | 0% | 50% | 0/5 |

**GLM-5 Analysis**: company 26/30 writes stored 32 entities, movie 25/30 writes stored 24 entities, but search all returned empty — model cannot effectively use search tool. Not a system bug.

### Batch 5 — Phase 38 Comparison Verification (Completed)

Phase 38 keyword fallback effect comparison (Kimi-K2.5 seed 0 re-run):

| Model | Template | Seed | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections |
|------|------|------|-----------|---------|--------|-----------|------------|-------------|
| Kimi-K2.5 | company | 0 | **4%** | 11% | 0% | 0% | 100% | 2/5 |
| Kimi-K2.5 | research | 0 | **25%** | 0% | 33% | 11% | 100% | 3/5 |
| Kimi-K2.5 | city | 0 | **26%** | 0% | 97% | 0% | 100% | — |
| Kimi-K2.5 | hospital | 0 | **35%** | 11% | 60% | 0% | 100% | 2/5 |
| Kimi-K2.5 | sport | 0 | **5%** | 0% | 18% | 0% | 100% | — |
| Kimi-K2.5 | movie | 0 | **9%** | 12% | 0% | 17% | 100% | — |

**Comparison Analysis** (Batch 1 vs Batch 5, both Kimi s0):

| Template | B1 Composite | B5 Composite | Change | B1 Maint | B5 Maint | Notes |
|------|-------------|-------------|------|---------|---------|------|
| company | 30% | 4% | ↓26% | 20% | 0% | Major decline |
| research | 15% | 25% | ↑10% | 33% | 33% | Improved |
| city | 20% | 26% | ↑6% | 31% | 97% | Maintenance greatly improved |
| hospital | 17% | 35% | ↑18% | 26% | 60% | Significant improvement |
| sport | 10% | 5% | ↓5% | 0% | 18% | Slight fluctuation |
| movie | 21% | 9% | ↓12% | 62% | 0% | Declined |

**Conclusion**: Phase 38 effect is inconsistent. hospital/city/research improved, company/movie declined. Note: Score differences when running the same seed at different times may stem from API non-determinism (LLM temperature), not the keyword fallback itself.
