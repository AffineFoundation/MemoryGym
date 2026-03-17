# TRAINER — Training Thread

> Launch method: `/loop 20m You are the training thread, read sessions/TRAINER.md and execute the current training task`
>
> You are the project's **training execution thread** — focused on training module development and validation, pushing code independently.

## Training Module Vision

The training module (`training/`) is an independent subsystem with a long-term evolution direction:

- **Multi-framework**: Simultaneous support for verl, slime, and other RL frameworks
- **Multi-method**: SFT (supervised fine-tuning) + RL (reinforcement learning, GRPO/PPO)
- **Ease of use**: Quick start, auto-tuning, automated training, remote training support
- **Efficiency**: Fast convergence, low cost, convenient data collection
- **Self-iteration**: Good CLI visualization, easy feedback acquisition, continuous iterative improvement

## Evolution Loop

```
North Star (CLAUDE.md §Trainable) ← Defines goal: not just an evaluation tool, but also an RL training environment
  ↓
Training experiment data ← Measures gap (model scores, reward curves, convergence speed)
  ↓
Gap analysis ← Derives highest-value improvement direction
  ↓
Execution ← Write code (local) → Test (GPU machine) → Training experiments (GPU machine)
  ↓
(Back to training experiment data)
```

## Each /train

```
1. git pull --rebase origin main (sync changes from executor and other developers)
2. Read this file, execute current task
3. Code changes → local editing → SSH to GPU machine to run tests
4. Training experiments → execute on GPU machine, record results to devlog/
5. Task complete → git add + git commit + git push origin main (Co-Authored-By, Generated-by and other metadata lines are **forbidden**)
6. Move to "Completed", promote next to-do
7. To-do empty → strategic derivation
```

**Collaboration rules**: The executor is another independent developer who pushes code to the same remote repository. Must `git pull --rebase` before each development session, must `git push` after commits. If pull has conflicts, **resolve them based on understanding both parties' change intentions**, do not blindly accept either side.

## Task Execution Standards

- **Code tasks**: Edit code locally → SSH to GPU machine to run `pytest tests/ -q` → Pass to count as complete
- **Training experiments**: Record complete config (model, tier, seed, hyperparams) + results (scores, curves) to `devlog/`
- **GPU resource constraints**: Shared machine, run short experiments (2-3 steps) to validate direction, no long training. Single GPU, don't occupy multiple cards
- **Completion criteria**: Must have clear output (tests passing / training results / code merged) to count as complete
- **Commit granularity**: Each feature point committed independently, describe why not what
- **No sensitive info in commits**: IP addresses, SSH addresses, `/home/xmyf/` and other hardcoded paths may only appear in `.env`, code and docs use `$GPU_SSH`, `$MODEL_PATH` and other variables

## Strategic Derivation

When the to-do is empty:

1. Review existing training experiment data (`devlog/` + eval results)
2. Compare against the North Star to find the largest gap: which axis is weakest for trained models?
3. Analyze root cause: Is it insufficient reward signal? Unreasonable curriculum? Not enough data?
4. Design tasks and write into "To-do", with derivation basis attached

Priority ordering principles:
- **End-to-end runnable** > Score improvement > Code elegance
- **Experiment-driven**: Get it running first then optimize, don't do optimizations without data support
- **Minimum viable change**: Change only one variable at a time for easy attribution

## Escalation when stuck

- **Task-level**: Current approach doesn't work → Switch approach or break down into subtasks
- **Environment-level**: GPU machine unavailable → Only do code preparation locally, mark as blocked
- **Direction-level**: Multiple consecutive tasks with no progress → Record analysis in devlog, question the direction itself

## Progress Feedback Mechanism

**After completing each Step, append a record to the "Progress Log" section of this file.** The audit thread tracks progress by reading this file.

Format:
```
### Progress Log
- [time] Step N completed/failed — Key information (scores, errors, duration)
```

**Key milestones must be recorded immediately**:
1. Step 0 complete — GPU count, CUDA version
2. Step 2 complete — final training loss
3. Step 4 complete — base model per-axis scores (B/M/R/E/C)
4. Step 5 complete — SFT model per-axis scores
5. Step 6 complete — before/after comparison table
6. Any failure — error message + attempted solutions

### Progress Log

- [2026-03-14 11:26] Step 0 complete — 4x H200 (141GB HBM3e/card), CUDA 12.8, Driver 570.195.03, Python 3.12.3
- [2026-03-14 11:29] Code+data transfer complete — memorygym + 320 SFT trajectories (sft_v6_mixed.jsonl)
- [2026-03-14 11:41] Step 1 complete — merged 320 lines of SFT data
- [2026-03-14 12:14] Step 2 started — Qwen2.5-7B-Instruct, LoRA rank 64, 3 epochs, batch 2x4, lr 2e-5, max_length 8192
  - Fix: `build_assistant_mask` O(n^2) tokenization bottleneck changed to O(n) token-id matching (original 30min+ tokenization reduced to <2min)
  - Fix: Remote /tmp mounted noexec caused vLLM triton compilation failure, worked around with TMPDIR=/root/tmp
- [2026-03-14 12:51] Step 2 complete — SFT training complete, checkpoint: runs/sft_qwen7b_v1/checkpoints/final/ (646MB adapter)
- [2026-03-14 13:17] Step 3 complete — vLLM server started (base Qwen2.5-7B-Instruct on GPU0, port 8000)
- [2026-03-14 13:18] Step 4 in progress — Base model evaluation
  - Fix: judge using Chutes API model names caused vLLM 404, added MEMORYGYM_JUDGE_MODEL env var override
  - company s0: Score=3/20(15%), B=29%, M=0%, R=0%, E=?, C=10%, duration 468s
  - Batch evaluation in progress (17/30 complete: company 10/10, university 7/10, city 0/10)
  - **Base complete**: 30/30 runs, Overall C=13.8±8.4 (B=23.0,M=8.4,R=11.9,E=9.2)
    - company C=13.3%(B=27.7,M=5.6,R=7.4,E=8.7)
    - university C=11.8%(B=17.2,M=4.9,R=15.0,E=8.0)
    - city C=16.4%(B=24.0,M=14.7,R=13.4,E=11.0)
- [2026-03-14] Step 5 in progress — SFT model evaluation (LoRA merge + vLLM restart)
  - LoRA merge successful, vLLM server started successfully
  - **Warning: SFT model scores dropped**: mid-point(16/30) SFT C=4.1±3.1% vs Base C=13.8±8.4%
    - company SFT C=3.2% (Base=13.3%), university SFT C=5.6% (Base=11.8%)
    - writes=30, stored=30, missed=30 → stored but retrieval/answer quality poor
    - Possible cause: LoRA merge corrupted tool_call format / SFT training data format mismatch
  - **SFT complete (30/30)**: SFT C=4.9±4.6% vs Base C=13.8±8.4% — **SFT dropped by 8.9pp**
    - company: SFT C=3.2% vs Base C=13.3% (-10.1pp)
    - university: SFT C=3.4% vs Base C=11.8% (-8.4pp)
    - city: SFT C=8.3% vs Base C=16.4% (-8.1pp)
  - **Root cause analysis**: After LoRA merge, storage format degraded; stored 30 entries but retrieval answer quality extremely poor
- [2026-03-15] Step 5b — SFT Approach B (vLLM --enable-lora, no merge)
  - vLLM started successfully (--enable-lora --max-lora-rank 64)
  - Mid-point results (13/30): company C=5.2% (n=10), university C=3.1% (n=3) — still below base
  - **Conclusion**: SFT training itself causes degradation (not a merge issue), data format incompatible with Qwen2.5-7B
  - **Fallback plan**: Record Base Qwen2.5-7B as "small model baseline" for the paper
- [2026-03-15] Phase T1 conclusion:
  - Base Qwen2.5-7B: C=13.8±8.4% (B=23.0,M=8.4,R=11.9,E=9.2) — 30 runs x 3 templates
  - SFT merged: C=4.9% — degraded 8.9pp
  - SFT LoRA: C≈5% — degraded ~9pp
  - **SFT is ineffective on Qwen2.5-7B**, need to investigate SFT data format compatibility
- [2026-03-15] Root cause investigation:
  - SFT data format correct (<tool_call> tags present, apply_chat_template works)
  - build_assistant_mask correct (25% assistant tokens, includes tool_call)
  - **Root cause: Overfitting!** 3 epochs loss=0.07 (<0.5 threshold), severe overfitting
  - Retrained: 1 epoch, lr=1e-5, loss=0.162 (reasonable)
  - 1-epoch SFT company (5 seeds): all 15% (3/20) — same as base 13.3%, no degradation no improvement
  - **Final conclusion**:
    - 3 epochs: severe overfitting (loss=0.07), degraded ~9pp
    - 1 epoch: no degradation no improvement (loss=0.16), SFT signal too weak for 7B model
    - **SFT is ineffective for Qwen2.5-7B**, 320 trajectories insufficient to produce measurable improvement on 7B model
    - Paper-usable data: Base Qwen2.5-7B C=13.8% as "small model baseline"
    - Next step: Need RL (GRPO) to produce before/after improvement
- [2026-03-15] Investigation #4: Try Qwen2.5-3B-Instruct (smaller model, SFT effect may be more pronounced)
  - 3B download + 1ep SFT training complete (loss=0.158, 4min)
  - vLLM started (base 3B + sft3b LoRA)
  - **3B results (company, 5 seeds)**:
    - Base 3B: accuracy=35.0%, C=28.9% (B=34.5,M=27.7,R=30.4,E=20.0)
    - SFT 3B: accuracy=28.0% → **degraded -7pp**, consistent with 7B pattern
    - Unexpected finding: Base 3B (28.9%) >> Base 7B (13.3%)! Smaller model is stronger on MemoryGym
  - **Deep investigation**: SFT 3B tool_call format correct (29 writes, 5 searches), problem is not tool call failure
  - SFT "perfect strategy" storage method may actually be worse than base's natural strategy (over-compression/packing)
  - **SFT data's training signal direction may be wrong** — need to redesign SFT strategy
  - **Base 3B full evaluation complete (30/30)**:
    - company C=27.1% (B=33.0,M=18.9,R=34.5,E=19.3)
    - university C=27.3% (B=34.0,M=17.9,R=35.2,E=19.3)
    - city C=34.1% (B=42.2,M=25.1,R=41.8,E=23.7)
    - **Overall C=29.5±11.3%** — 15.7pp higher than 7B's 13.8%!
  - Paper-usable data: Base 3B C=29.5%, Base 7B C=13.8% — model size comparison
- [2026-03-15] Phase T2: GRPO on Base 3B (skip SFT prerequisite, go straight to RL)
  - v1 config: group_size=4, max_turns=100, max_new_tokens=512 → too slow (67min and still hasn't completed 1 step)
  - v2 config: group_size=2, max_turns=40, max_new_tokens=256, 5 steps
  - **GRPO complete**: reward 0.013→0.088, correct 1.5→1.5/10, **writes=0 all steps**
  - Confirmed F67: lite tier documents fit in context, model "doesn't store, answers directly"
  - GRPO cannot drive Write behavior on lite tier — need standard tier or context truncation
  - 5 steps insufficient to produce significant change, but fundamental problem is reward signal direction
- [2026-03-15] GRPO standard tier on 3B (solving lite tier writes=0 problem)
  - Old code standard tier killed (affected by BLOCKER bug)
- [2026-03-15] Received audit thread notification: Phase 135 fixed GRPO BLOCKER bug (zero-loss fallback)
  - Pulled fix and updated remote code
  - **Restarted GRPO standard tier**: 10 steps, group_size=2, max_turns=50, Phase 135 code
  - Step 1: loss=0.000 (advantage same, skipped), writes=1-2, r=0.082
  - Step 2: **loss=0.0013** (has gradient! Phase 135 fix effective), writes=1, correct=1.5/20
  - ~16-19 min per step, estimated 3h to complete
  - Step 6 crash: `loss.item()` on None — fixed and uploaded
  - Training progress (step 1-5):
    - correct: 1.0 → 1.5 → 0.5 → **2.5** → **2.5** (upward trend)
    - loss: 0→0.0013→0.0062→-0.0015→0.0024 (Phase 135 fix effective)
  - Part 2 complete (step 6-10 from checkpoint)
  - 10 steps summary: correct fluctuates widely (0-4/20), no stable upward trend
    - group_size=2 causes advantage to frequently be 0 → step gets skipped
    - 20 total episodes insufficient to see statistically significant trend
    - Need group_size>=4 + more steps, but each step ~15 min is costly
  - **GRPO pipeline validation successful**: Phase 135 fix effective, standard tier produces Write behavior
  - **Conclusion**: GRPO needs larger scale experiments (50+ steps, group_size=4)
- [2026-03-15] GRPO long run: 30 steps, group_size=4, standard tier, lr=5e-6, kl=0.01
  - Continuing from step-5 checkpoint, estimated ~15h
  - Step 1: correct=3.2 r=0.095 loss=0.000 (skip)
  - Step 2: correct=1.2 r=0.000 loss=0.000 (skip)
  - Step 3: correct=0.2 r=0.000 loss=0.000 (skip)
  - Step 4/30 in progress, ~30 min/step
  - Step 10/30 complete, checkpoint saved
  - Effective loss steps: 3/10 (step 4,7,9-10), rest advantage=0 skipped
  - max_reward: 0.307 (step 10), correct fluctuates 0.2-3.2
  - Training continues to step 20/30

### Warning: Audit thread notification (2026-03-15) — GRPO code has serious bugs, must update

**Phase 135 (commit `a6b9075`) fixed 1 BLOCKER + 5 HIGH severity bugs in the GRPO training pipeline.** Your current GRPO experiments may be running on old code, results are unreliable.

**Must execute immediately**:
```bash
git pull --rebase origin main  # Get Phase 135 fixes
```

**Fix contents**:
1. **BLOCKER — Zero-loss fallback blocks gradient flow**: When all trajectory advantages ≈ 0 are skipped, old code created `torch.tensor(0.0, requires_grad=True)` tensor with no computation graph → `loss.backward()` produces zero gradients → **model doesn't train at all**. Fix returns `None`, skipping that step's backward
2. **Per-token ratio clipping**: Old code did PPO clipping at sequence-level (ratio diluted by long sequences), fixed to per-token GRPO clipping — every token has effective gradients
3. **KL divergence calculation fix**: Old code used geometric mean (exp of mean log ratio), fixed to correct per-token KL
4. **Removed inner-loop `torch.cuda.empty_cache()`**: Expected 3-5x training speed improvement
5. **Loss normalization unified**: Normalizes even when n_valid==1
6. **MemoryEnv resource leak fix**: env.close() protected by try/finally
7. **Silent skip warning**: Now prints `[GRPO] X/Y trajectories used (skipped Z with |advantage| < 1e-6)`

**Impact assessment**: Your previous T2 results (writes=0, reward 0.013→0.088) were likely affected by the BLOCKER — model parameters may not have updated at all. Restart standard tier experiments after pulling the fix.

---

## Current Status (2026-03-14)

### Urgent Task: NeurIPS Paper Training Experiments (4x H200)

**Background**: Paper targeting NeurIPS 2026 E&D Track (Abstract May 4, Paper May 6). Paper body is complete (PA-17/18/19), but **Contribution 3 (training environment) has no training results**, flagged as CRITICAL weakness by reviewer red team. Now have 4x H200, must produce paper-ready training experiment data in the shortest time.

**GPU Resources**: 4x H200 (141GB HBM3e/card, 564GB total). Connection method provided separately by user.

**Target Output**: A before/after comparison table proving that MemoryEnv training actually improves memory management scores. This table will be directly written into paper Section 6 (Training Environment).

---

### Phase T1 — SFT Baseline Experiment (Highest Priority)

**Goal**: Fine-tune a model with SFT, compare before/after on MemoryGym to prove training is effective.

---

#### Step 0: Environment Setup (~30 min)

```bash
# 1. Clone code
git clone <repo_url> && cd memorybench-arena
pip install -e .
pip install torch transformers peft accelerate datasets

# 2. Verify GPU
python -c "import torch; print(torch.cuda.device_count(), 'GPUs'); print(torch.cuda.get_device_name(0))"
# Expected output: 4 GPUs + NVIDIA H200

# 3. Smoke test (CPU, verify memorygym can be imported)
python -m memorygym.training smoke

# 4. Verify SFT data exists
wc -l data/sft_v6.jsonl data/sft_v6_strategic.jsonl
# Expected: 160 + 160 = 320 lines
```

**If Step 0 fails**:
- `pip install -e .` fails → Check `pyproject.toml` dependencies, install manually
- `torch.cuda` not available → Check CUDA version: `nvidia-smi` and `python -c "import torch; print(torch.version.cuda)"`
- smoke test fails → Check error message, usually a missing package

---

#### Step 1: Merge Training Data

```bash
cat data/sft_v6.jsonl data/sft_v6_strategic.jsonl > data/sft_v6_mixed.jsonl
wc -l data/sft_v6_mixed.jsonl  # Must be 320
```

---

#### Step 2: SFT Training (~1-2h)

**Recommended model**: `Qwen/Qwen2.5-7B-Instruct`

```bash
# Single GPU sufficient (7B bf16 ≈ 14GB, H200 141GB more than enough)
CUDA_VISIBLE_DEVICES=0 python -m memorygym.training sft \
  --model Qwen/Qwen2.5-7B-Instruct \
  --data data/sft_v6_mixed.jsonl \
  --lora --lora-rank 64 \
  --epochs 3 \
  --batch-size 2 \
  --grad-accum 4 \
  --lr 2e-5 \
  --max-length 8192 \
  -o runs/sft_qwen7b_v1
```

**SFT completion check**:
```bash
ls runs/sft_qwen7b_v1/checkpoints/final/
# Must have adapter_model.safetensors and tokenizer files
```

**SFT troubleshooting**:

| Issue | Symptom | Solution |
|-------|---------|----------|
| Model download fails | `HTTPError` / timeout | Set `HF_ENDPOINT=https://hf-mirror.com` or download manually to local then `--model /path/to/local` |
| OOM | `CUDA out of memory` | `--batch-size 1 --grad-accum 8`. Still OOM → `--max-length 4096` |
| Chat template error | `jinja2` related error | `pip install jinja2`. Or switch model to `Qwen/Qwen2.5-3B-Instruct` (smaller) |
| Loss not decreasing | loss stable at 2-3+ | Training data format may not match. Check next section "SFT data format validation" |
| peft version issue | `LoRA` related error | `pip install peft>=0.11` |

**SFT data format validation** (if loss not decreasing, run this to debug first):
```bash
python3 -c "
import json
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained('Qwen/Qwen2.5-7B-Instruct', trust_remote_code=True)
with open('data/sft_v6_mixed.jsonl') as f:
    d = json.loads(f.readline())
text = tok.apply_chat_template(d['messages'], tokenize=False)
print('Template applied OK, length:', len(text))
print('First 500 chars:', text[:500])
# Check if output contains <tool_call> format tool calls
"
```

If `apply_chat_template` errors or output doesn't contain `<tool_call>`, the Qwen2.5 chat template and data format are incompatible. **Fallback plan**: Switch to `Qwen/Qwen2.5-3B-Instruct` or `Qwen/Qwen3-4B`.

---

#### Step 3: Start vLLM Server (required for evaluation)

**Key**: `bench.py` calls models through OpenAI-compatible API, doesn't support directly loading local checkpoints. Must use vLLM to provide API server.

**3a. Base model server**:
```bash
pip install vllm

# Terminal 1: Start base model server
CUDA_VISIBLE_DEVICES=0 python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --port 8000 \
  --max-model-len 32768 \
  --trust-remote-code

# Wait for output "Uvicorn running on http://0.0.0.0:8000"
```

**Verify server is available**:
```bash
curl -s http://localhost:8000/v1/models | python3 -m json.tool
# Should return model list
```

**vLLM troubleshooting**:

| Issue | Symptom | Solution |
|-------|---------|----------|
| Installation fails | pip compilation error | `pip install vllm --no-build-isolation` or use `pip install sglang[all]` as alternative |
| OOM at startup | `CUDA out of memory` | `--max-model-len 16384` or `--gpu-memory-utilization 0.85` |
| Startup hangs | No output | Wait 2-3 minutes (first model load is slow). If 5+ minutes no output → `Ctrl+C` check logs |
| `RuntimeError: ... flash_attn` | flash attention version mismatch | `pip install flash-attn --no-build-isolation` or `--disable-flash-attn` |

**If vLLM cannot be installed at all** (fallback plan):
```bash
# Plan B: Use transformers pipeline server
pip install text-generation-inference  # Or use simple Flask wrapper

# Plan C: Use SGLang
pip install "sglang[all]"
python -m sglang.launch_server --model Qwen/Qwen2.5-7B-Instruct --port 8000
```

---

#### Step 4: Base Model Evaluation (~1-2h with vLLM)

```bash
# Terminal 2 (server running in Terminal 1):
# Set env vars to point to local server
export OPENAI_API_KEY=dummy
export API_URL=http://localhost:8000/v1

# 10 seeds x 3 templates = 30 runs
for TMPL in company university city; do
  for SEED in 0 1 2 3 4 5 6 7 8 9; do
    python -m memorygym.bench \
      --model Qwen/Qwen2.5-7B-Instruct \
      --seed $SEED --template $TMPL --tier standard \
      --backend markdown \
      --api-base http://localhost:8000/v1 \
      -o eval/base_qwen7b_${TMPL}_s${SEED}.json
  done
  echo "=== $TMPL done ==="
done
```

**Notes**:
- **Run sequentially** (don't run concurrently) — vLLM server handles batching, concurrent requests only increase OOM risk
- Each run about 5-10 minutes (vLLM is faster than API), 30 runs ≈ 2.5-5h
- If a run errors, skip and continue. Having 20+ successful runs at the end is sufficient

**Evaluation troubleshooting**:

| Issue | Symptom | Solution |
|-------|---------|----------|
| `Connection refused` | server not started or crashed | Check Terminal 1, restart server |
| `No API key found` | env var not set | `export OPENAI_API_KEY=dummy` |
| Model outputs blank | `content: ""` | vLLM's `--max-model-len` too small → increase to 32768 |
| tool_call parsing fails | `_extract_tool_calls` returns empty | Model output may not contain `<tool_call>` tags. Test manually first (see below) |
| judge errors | `RuntimeError: No API key` | Ignore. Judge only handles 0.2% of rule-miss answers, failure counts as wrong, doesn't affect before/after comparison |
| run stuck > 20 min | inference loop | `Ctrl+C` skip this seed, continue to next |

**Manual test of tool_call output** (if evaluations are all 0 score, run this first):
```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [
      {"role": "system", "content": "You are a memory management agent. Store information using tool calls.\n\nTools:\n<tool_call>{\"name\": \"Write\", \"arguments\": {\"content\": \"info\"}}</tool_call>"},
      {"role": "user", "content": "Store this: Apple has 164000 employees and $394B revenue."}
    ],
    "max_tokens": 512
  }' | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])"
```

If output doesn't contain `<tool_call>`, the model doesn't use this format. **Solutions**:
1. Check if it's Qwen2.5 not Qwen3 (Qwen3 may not support `<tool_call>` format)
2. Try different model `Qwen/Qwen2.5-14B-Instruct` or `Qwen/Qwen2.5-3B-Instruct`
3. Check `agents/stream_agent.py:120`'s `_extract_tool_calls`, it supports 3 formats: `<tool_call>` XML, markdown code block, bare JSON. Most models use at least one

---

#### Step 5: SFT Model Evaluation (~1-2h)

```bash
# 1. Stop Terminal 1's base server (Ctrl+C)
# 2. Merge LoRA adapter to base model (vLLM needs complete model)
python3 -c "
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

base = AutoModelForCausalLM.from_pretrained(
    'Qwen/Qwen2.5-7B-Instruct', torch_dtype=torch.bfloat16, device_map='cpu')
model = PeftModel.from_pretrained(base, 'runs/sft_qwen7b_v1/checkpoints/final')
merged = model.merge_and_unload()
merged.save_pretrained('runs/sft_qwen7b_v1_merged')
AutoTokenizer.from_pretrained('Qwen/Qwen2.5-7B-Instruct').save_pretrained('runs/sft_qwen7b_v1_merged')
print('Merged model saved to runs/sft_qwen7b_v1_merged')
"

# 3. Start SFT model server
CUDA_VISIBLE_DEVICES=0 python -m vllm.entrypoints.openai.api_server \
  --model runs/sft_qwen7b_v1_merged \
  --port 8000 \
  --max-model-len 32768 \
  --trust-remote-code

# 4. Evaluation (same as Step 4, change output prefix)
export OPENAI_API_KEY=dummy
for TMPL in company university city; do
  for SEED in 0 1 2 3 4 5 6 7 8 9; do
    python -m memorygym.bench \
      --model sft-qwen7b \
      --seed $SEED --template $TMPL --tier standard \
      --backend markdown \
      --api-base http://localhost:8000/v1 \
      -o eval/sft_qwen7b_${TMPL}_s${SEED}.json
  done
  echo "=== $TMPL done ==="
done
```

**LoRA merge troubleshooting**:

| Issue | Symptom | Solution |
|-------|---------|----------|
| OOM merge | CPU memory insufficient | `device_map='auto'` or merge on GPU |
| tool_call disappears after merge | SFT model doesn't produce tool calls | Known issue (see history). Don't merge, use vLLM's `--lora-modules` parameter instead |

**If merge causes tool_call to disappear**:
```bash
# Plan B: vLLM loads LoRA directly (no merge)
CUDA_VISIBLE_DEVICES=0 python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --port 8000 \
  --enable-lora \
  --lora-modules sft=runs/sft_qwen7b_v1/checkpoints/final \
  --max-model-len 32768

# Change model name to "sft" in evaluation
python -m memorygym.bench --model sft --api-base http://localhost:8000/v1 ...
```

---

#### Step 6: Summarize Results

```bash
python3 -c "
import json, glob
for prefix in ['base_qwen7b', 'sft_qwen7b']:
    files = sorted(glob.glob(f'eval/{prefix}_*.json'))
    scores = {'B': [], 'M': [], 'R': [], 'E': [], 'C': []}
    for f in files:
        with open(f) as fh:
            d = json.load(fh)
        if not d.get('success'): continue
        ax = d['extra']['per_axis']
        scores['B'].append(ax['breadth']*100)
        scores['M'].append(ax['maintenance']*100)
        scores['R'].append(ax['reasoning']*100)
        scores['E'].append(ax['efficiency']*100)
        scores['C'].append(ax['composite']*100)
    n = len(scores['C'])
    print(f'{prefix} (n={n}):')
    for k in ['B','M','R','E','C']:
        vals = scores[k]
        if vals:
            avg = sum(vals)/len(vals)
            std = (sum((v-avg)**2 for v in vals)/len(vals))**0.5
            print(f'  {k}: {avg:.1f} +/- {std:.1f}')
    print()
"
```

**Interpreting results**:
- SFT composite > base composite (any improvement is a good result)
- Pay special attention to Breadth and Maintenance axis improvements
- If SFT actually dropped → see "SFT no improvement investigation"

---

### SFT No Improvement Investigation (if SFT score <= base)

**This is the most likely problem to encounter.** Debug in order:

1. **Is the SFT model producing tool_calls?**
   ```bash
   # Check the eval JSON's conversation field
   python3 -c "
   import json
   with open('eval/sft_qwen7b_company_s0.json') as f:
       d = json.load(f)
   conv = d['extra']['conversation']
   tool_calls = sum(1 for m in conv if m.get('role')=='user' and m.get('content','').startswith('['))
   writes = d['extra'].get('writes_used', 0)
   print(f'Tool call responses: {tool_calls}, Writes used: {writes}')
   "
   ```
   - If writes=0 → tool_call format incompatible, go back to Step 3 to check

2. **What did the SFT model store?**
   ```bash
   python3 -c "
   import json
   with open('eval/sft_qwen7b_company_s0.json') as f:
       d = json.load(f)
   print(f'stored_entities: {d[\"extra\"][\"stored_entities\"]}')
   print(f'missed_entities: {d[\"extra\"][\"missed_entities\"]}')
   print(f'writes_used: {d[\"extra\"][\"writes_used\"]}')
   "
   ```

3. **Final training loss value?**
   - If final loss > 1.5 → training insufficient, increase epochs to 5 or lr to 5e-5
   - If final loss < 0.5 → possible overfitting, reduce epochs to 1

4. **Try larger/smaller model**:
   - Qwen2.5-7B doesn't work → try `Qwen/Qwen2.5-14B-Instruct` (14B may have stronger tool calling)
   - Or try `Qwen/Qwen2.5-3B-Instruct` (smaller but faster training, SFT improvement may be more noticeable)

5. **Final fallback plan**: If all SFT experiments show no improvement, at least record base Qwen2.5-7B scores — this itself is a new data point (paper currently has no 7B model data), can be written into paper as "small model baseline".

---

### Phase T2 — GRPO Reinforcement Learning (if T1 complete and time remains)

**Prerequisite**: T1 SFT checkpoint available and SFT shows improvement.

```bash
CUDA_VISIBLE_DEVICES=0 python -m memorygym.training grpo \
  --model Qwen/Qwen2.5-7B-Instruct \
  --adapter runs/sft_qwen7b_v1/checkpoints/final \
  --steps 30 \
  --group-size 4 \
  --groups-per-step 2 \
  --tier lite \
  --lr 1e-5 \
  --temperature 0.7 \
  --lora-rank 16 \
  -o runs/grpo_qwen7b_v1
```

GRPO each step about 30 min (4 episodes x ~7 min), 30 steps ≈ 15h. **If time is tight**:
- Reduce to `--steps 10` (~5h), enough to see trends
- Or `--tier lite` (shorter episodes)

Evaluate same as Step 5, but use GRPO checkpoint.

---

### Results Recording Template

After completion, record results to `devlog/training_results.md`:

```markdown
# Training Results for NeurIPS Paper

## Config
- Base model: Qwen2.5-7B-Instruct
- SFT data: 320 trajectories (160 perfect + 160 strategic)
- SFT: LoRA rank 64, 3 epochs, lr 2e-5, max_length 8192
- Eval: standard tier, 10 seeds x 3 templates (company/university/city)
- Backend: markdown
- Judge: rule-based only (no API judge)

## Results

| Model | N | S_B | S_M | S_R | S_E | S_C |
|-------|---|-----|-----|-----|-----|-----|
| Base Qwen2.5-7B | ? | ? | ? | ? | ? | ? |
| + SFT | ? | ? | ? | ? | ? | ? |
| + GRPO (optional) | ? | ? | ? | ? | ? | ? |

## Key Findings
- [fill in]
```

---

### Priority and Time Allocation

```
T1 SFT experiment >>>>>>>> T2 GRPO
```

- T1's before/after comparison is the paper's **minimum requirement**
- T2 is a bonus
- If T1 took 12+ hours, **don't run T2**, just record T1 results properly
- If T1 SFT shows no improvement, debugging+retrying is more important than running T2

### Historical Records (Archived)

4-bit low VRAM experiment completed (2026-03-12), technically feasible but too slow. See `devlog/grpo-v4-4bit.md`. Now have 4x H200, use bf16 directly.

## Prompt Self-Optimization

Each time you update this file, review whether rules are still effective — merge if redundant, delete if outdated, add if missing. Documentation serves evolution.

---

## Development Environment

| Environment | Purpose | Constraints |
|-------------|---------|-------------|
| Local (CPU) | Code editing, reading, git operations | No GPU, don't run training/tests |
| GPU dev machine (see `.env`) | Tests, training experiments | **Shared machine, must not impact others** |

### GPU Dev Machine Usage Rules (non-violable)

1. **Forbidden** to kill / stop / restart any process not started by yourself
2. **Forbidden** to occupy all GPUs — check available resources with `nvidia-smi` before use
3. **Forbidden** to modify system config, stop services, restart machine
4. Only use for running tests and training experiments, no other operations

---

## Scope of Responsibility

**Responsible for**: Training-related code (`training.py`, `adapters/`, `scripts/` training scripts, training tests), training experiments, reward design, curriculum strategy.

**Don't touch**: Evaluation core (`worlds/`, `evaluation/`, `simulation.py`, `protocol.py`, `bench.py`, `stream_agent.py`). These modules' interfaces are read-only use. If training has any requirements for the evaluation system, record in the strategic feedback section.

---

## Strategic Feedback Section

> **Writing rules**: The training thread records experiment findings, system design issues, and improvement suggestions here. The audit thread reads this section during each audit, converting valuable feedback into Phase tasks.
>
> **Format**: Each feedback entry uses `#### F{number} — Title` format, including: Finding (data/evidence), Impact (which part of the system), Suggestion (if any).
>
> **Lifecycle**: After the audit thread reads and processes, it annotates the feedback entry with `→ Read, handled as: ...`. The trainer can append new entries but should not delete existing ones (preserve audit trail).

#### F1 — GSPO as GRPO Alternative (audit thread frontier search A52)

**Finding**: Qwen3 team's GSPO (Group Sequence Policy Optimization) does importance ratio + clipping at the sequence level, more stable and efficient than GRPO. Dria's mem-agent has successfully used GSPO to train file memory agents (base Qwen3-4B 39% → post-training 75%).

**Impact**: MemoryGym currently uses GRPO, v2 showed policy collapse (loss→negative). GSPO may fundamentally avoid this issue.

**Suggestion**: After SFT v3 is complete, evaluate GSPO as an alternative to GRPO v3. Paper: https://arxiv.org/abs/2507.18071

→ Read (A71), pending evaluation after SFT v3 + GRPO v3. F4 (AgeMem step-wise GRPO) has higher priority.

#### F2 — KL Regularization Gradient Audit (audit thread frontier search A52)

**Finding**: Paper "Comedy of Estimators" (2512.21852) points out KL estimators in open-source RL libraries generally provide **incorrect gradients**. Biased gradients cause training instability.

**Impact**: Our `--kl-coeff 0.05` implementation (GRPO v3) may be affected.

**Suggestion**: Before starting GRPO v3, check KL implementation against this paper for biased gradient configuration.

→ Read (A71), must check before GRPO v3 launch.

#### F3 — Small Data Efficient Training Validation (audit thread frontier search A52)

**Finding**: Memory-R1 generalized to 3 benchmarks with only 152 QA pairs. Mem-alpha trained on 30K token scenarios generalized to 400K+ (13x).

**Impact**: We don't need large amounts of training data. Current 480 trajectories (sft_mixed_v2.jsonl) may already be sufficient.

**Suggestion**: If SFT v3 works well, proceed directly to GRPO phase, no need to expand data volume.

→ Read (A71), agreed. 480 trajectories sufficient to start.

#### F4 — AgeMem Step-wise GRPO Reference Design (audit thread frontier search A70)

**Finding**: AgeMem (arXiv 2601.01885) proposes three-stage progressive RL + step-wise GRPO, solving sparse/discontinuous reward problems for memory operations. Average improvement of 4.82-8.57%.

**Impact**: Our GRPO v2 showed policy collapse (loss→negative), step-wise GRPO directly addresses this type of problem. Three-stage training can map to curriculum: lite (basic storage) → standard (update tracking) → multi (cross-session).

**Suggestion**: GRPO v3 should reference AgeMem's step-wise reward design, converting cross-stage dependencies into learnable signals. See `devlog/2026-03-11-frontier-v6.md`.

→ Read (A126), high value. Core reference for GRPO v3. Trainer implements autonomously, no Phase dispatch needed.

#### F5 — Utility-aware Reward Shaping (audit thread frontier search A70)

**Finding**: A-MAC (arXiv 2603.04549) decomposes memory admission into 5 factors (utility/confidence/novelty/recency/type prior), LoCoMo F1=0.583.

**Impact**: Our shaped reward only distinguishes "stored new entity (+0.3)" vs "duplicate (-0.1)", lacking utility/novelty distinction. More fine-grained reward may accelerate convergence.

**Suggestion**: Consider after getting training baseline working. Low priority.

→ Read (A126), agree on low priority. Evaluate after GRPO baseline is running.

#### F6 — Attributed Dense Rewards (audit thread frontier search A89)

**Finding**: 3 papers from 2026 independently converge on the same conclusion: **reward should be weighted by memory's downstream usage rate**.

- MemBuilder (2601.05488): ADRPO, gradient ∝ memory usage frequency in retrieval. 84.23% LoCoMo
- MemPO (2603.00680): credit assignment based on memory effectiveness. +25.98% F1
- Memex(RL) (2603.04257): budget-aware reward shaping. 3.5x task success

**Impact**: Our current flat reward (Write +0.3, Edit +0.5) doesn't distinguish "stored but never queried" from "stored and helped answer 3 questions". Attributed reward lets the model learn to prioritize storing high-value entities.

**Suggestion**: GRPO v3's reward design should reference ADRPO — after episode ends, trace back how many times each memory was hit by memory_search and led to correct answers, weight accordingly. MemoryGym's adaptive question system naturally supports this attribution (`required_entities` field already exists).

See `devlog/2026-03-11-frontier-v7.md`.

→ Read (A126), high value. `required_entities` field naturally supports attribution. Optimization direction after GRPO v3, complementary with F4.

#### F7 — Reward Decay to Prevent Reward Hacking (audit thread frontier search A89)

**Finding**: MIRA (arXiv 2602.17930) introduces utility decay — reduces auxiliary reward weight as training progresses, so model ultimately relies on outcome reward.

**Impact**: Our shaped reward already has reward hacking risk (A42+A44: Edit +0.5 doesn't validate new_text). If model learns "blindly store → get +0.3" without caring what to store, shaped reward is counterproductive. Decay mechanism is a natural safety valve.

**Suggestion**: Implement a `reward_shaping_weight` parameter, linearly decaying from 1.0 to 0.0 (e.g., first 50% of training steps). Later keep only outcome reward (submit_answer correct=+1.0).

→ Read (A126), aligns with pending follow-ups A42+A44. Phase 92 already fixed Edit shaped reward to validate new_val. Decay mechanism to be implemented by trainer.

#### F8 — GRPO is Suboptimal for Memory Tasks, EMPO2 Hybrid Approach (audit thread frontier search A101)

**Finding**: EMPO2 (arXiv 2602.23008, Microsoft Research + KAIST, Feb 2026) shows **GRPO converges suboptimally on memory tasks**. Hybrid on-policy + off-policy optimization improves 128.6% on ScienceWorld, 11.3% on WebShop over pure GRPO. Core idea: use memory to guide exploration, optimize contrastively on with/without memory action pairs.

**Impact**: If MemoryGym RL training uses GRPO directly, may hit convergence bottleneck. Should consider hybrid strategy.

**Suggestion**: Baseline still uses GRPO (simpler implementation), but reference EMPO2's hybrid approach when hitting convergence bottleneck. Low priority — get baseline running first.

→ Read (A126), agreed. GRPO baseline first, consider when hitting convergence bottleneck.

#### F9 — Memory-R1 Minimal Data Generalization + Mem-alpha Length Generalization (audit thread frontier search A101)

**Finding**:
- Memory-R1 v5 (arXiv 2508.19828, Jan 2026): Only **152 training QAs**, ADD/UPDATE/DELETE/NOOP action space, PPO+GRPO, generalizes to LoCoMo/MSC/LongMemEval three benchmarks, 3B-14B model scales.
- Mem-alpha (arXiv 2509.25911, Sep 2025): Trained on 30k tokens, **generalizes to 400k+ tokens** (13x training length).

**Impact**: MemoryGym training may not need large amounts of data. A few high-quality SFT trajectories + RL can generalize. Length generalization means can train on lite tier, evaluate on standard tier.

**Suggestion**: First round training target should be "get running + generalization validation" not data accumulation. Use 10-20 high-quality seed SFT trajectories for cold start, verify whether it generalizes to unseen templates/seeds.

→ Read (A126), consistent with F3. 480 trajectories sufficient, lite training → standard evaluation for generalization validation.

#### F10 — Memex(RL): Budget-Constrained Write/Read Strategy RL Training (audit thread frontier search A143)

**Finding**: Memex(RL) (arXiv 2603.04257, Mar 2026) explicitly trains agents to optimize write and read behavior under context budget constraints. Agent learns what to summarize, archive, index, and when to retrieve. Uses reward shaping targeting indexed memory usage.

**Impact**: This is the most direct reference for MemoryGym's MemoryEnv. Memex(RL) also faces budget constraints + write/read strategy optimization, fully aligned with our Write/Edit/Read/memory_search.

**Suggestion**: GRPO v3's reward design should reference Memex(RL)'s indexed memory reward shaping.

#### F11 — LongRLVR: Dense Verifiable Context Rewards (audit thread frontier search A143)

**Finding**: LongRLVR (arXiv 2603.02146, Mar 2026) adds dense, verifiable context rewards for long-context RL (rewarding correct information selection). 14B model RULER-QA from 73.17 → 88.90.

**Impact**: MemoryGym currently only has sparse outcome reward (final answer correct=+1.0). Can add dense rewards for intermediate steps (correct memory_search query, correct Write decision), solving GRPO policy collapse.

**Suggestion**: Add retrieval precision reward to shaped reward: when memory_search returns results and subsequent answer is correct, give search +0.2.

#### F12 — KARL: Stable Off-Policy RL + Multi-task Training (audit thread frontier search A143)

**Finding**: KARL (arXiv 2603.05218, Databricks, Mar 2026) uses iterative large-batch off-policy RL, stable training without clipped importance weighting. Multi-task training across 6 heterogeneous search tasks.

**Impact**: Directly corresponds to MemoryGym's GRPO instability problem. Multi-task training across 6 search scenarios → maps to our 6+ world templates.

**Suggestion**: If GRPO v3 (KL regularization) is still unstable, consider referencing KARL's off-policy approach.

#### F13 — Batch 21 Movie Corrections 1/5: Budget Allocation as Learnable Signal

**Finding**: Qwen3.5 movie s0 post-Phase99 first completed correction in real eval (`Steel Legacy.awards_count: search → edit`). writes_used=30, stored=36 entities. Estimated: ingest used 29 writes, 1 write left for correction Edit.

**Impact**: This proves corrections don't need system changes — the model naturally reserved 1 write on the movie template. Other 7 templates used all 30 writes for ingest → 0 remaining → corrections fail. Training key: teach model to reserve 3-5 writes during ingest phase.

**Suggestion**:
1. SFT v4's perfect strategy already reserves writes (budget-limited top-k storage), training should reinforce this behavior
2. GRPO reward shaping: correction success gives +1.0 (much higher than Write +0.3), incentivize budget reservation
3. Curriculum: first validate on movie (natural reservation space), then generalize to other templates

#### F14 — IPS-GRPO: Single-Line Fix for GRPO Policy Collapse (audit thread frontier search A152)

**Finding**: IPS-GRPO (arXiv 2601.21669, Jan 2026) mathematically proves outcome-level mode collapse is a structural consequence of the expected-return objective (log-probability ratios diverge exponentially). Fix: scale reward by inverse empirical outcome frequency. Drop-in GRPO replacement, no auxiliary model needed.

**Impact**: Our GRPO v2 policy collapse (loss→negative) may be caused by this root cause. IPS-GRPO is a more fundamental fix than KL regularization (`--kl-coeff 0.05`) — KL is symptom treatment, IPS is root cause fix.

**Suggestion**: GRPO v3 should first try IPS reward scaling (single-line change), rather than KL regularization. If IPS is insufficient, then add KL.

#### F15 — NGRPO: Learning from All-Wrong Groups (audit thread frontier search A152)

**Finding**: NGRPO (arXiv 2509.18851) solves the problem of GRPO producing zero gradients for all-wrong groups — introduces a virtual highest-reward sample to generate non-zero advantage + asymmetric clipping to stabilize exploration.

**Impact**: Memory tasks with budget constraints frequently produce all-wrong groups (all samples use up budget, all corrections fail). Standard GRPO ignores these groups = wasted training signal.

**Suggestion**: Complementary with IPS-GRPO. Implementation priority lower than F14.

#### F16 — OTC: Tool Productivity Reward (audit thread frontier search A152)

**Finding**: OTC (arXiv 2504.14870) defines tool productivity = correct_answers / total_tool_calls, jointly penalizing excessive tool use. Reduces 68% tool calls without losing accuracy.

**Impact**: Our entities_per_write=1.0 (all models don't do multi-entity packing) is a signal of tool inefficiency. OTC-style reward can train models to pack multiple entities in a Write → use fewer writes to store more info → reserve budget for corrections.

**Suggestion**: Add tool productivity signal to GRPO reward: `efficiency_bonus = correct_count / writes_used`, aligned with evaluation's efficiency axis.

#### F17 — DAPO Clip-Higher: Preventing Entropy Collapse (audit thread frontier search A165)

**Finding**: DAPO (arXiv 2503.14476, ByteDance Seed + Tsinghua AIR, Mar 2025) proposes Clip-Higher technique — raising PPO/GRPO clip ratio upper bound from 1+epsilon to 1+epsilon_high (e.g., 1+0.28), keeping lower bound 1-epsilon (e.g., 1-0.22). This asymmetric clipping promotes exploration, preventing entropy collapse.

**Complementary with IPS-GRPO (F14)**:
- IPS-GRPO solves **outcome-level mode collapse** (reward distribution skew)
- Clip-Higher solves **token-level entropy collapse** (policy narrowing too early)
- Both are orthogonal, can be used simultaneously

**Additional DAPO tricks**:
- Dynamic Sampling: filter all-correct/all-wrong groups (similar to NGRPO F15 but simpler)
- Overlong Reward Shaping: penalize truncated overlong responses (applicable when agent produces redundant tool calls)

**Suggestion**: In GRPO v3, layer Clip-Higher on top of `--ips` (single parameter `--clip-higher 0.28`). Implementation is about 5 lines of code. Priority lower than IPS but higher than F15-F16.

#### F18 — RC-GRPO: Reward-Conditioned Exploration Solving SFT→GRPO Stall (audit thread frontier search A172)

**Finding**: RC-GRPO (arXiv 2602.03025, Feb 2026) reveals the "perfection paradox" of SFT→GRPO pipelines — SFT produces a strong prior, then GRPO within-group rollout variance is too low → advantage degenerates → gradient vanishes. Solution: 2-stage pipeline:
1. RCTP (Reward-Conditioned Trajectory Policy): train with reward token conditioning on mixed-quality trajectories
2. RC-GRPO: sample different reward tokens per group, ensuring good/bad trajectory variance within groups

Qwen2.5-7B achieves 85% on BFCLv4 multi-turn tool calling, surpassing all closed-source API models.

**Impact**: Our GRPO v2 policy collapse may partly stem from this root cause — SFT v3 loss dropped to 0.076 (very strong prior), subsequent GRPO rollout variance is extremely low. RC-GRPO fundamentally ensures within-group variance.

**Relationship with existing methods**:
- IPS-GRPO (F14): solves outcome-level mode collapse — orthogonal
- DAPO Clip-Higher (F17): solves token-level entropy collapse — orthogonal
- RC-GRPO (F18): solves within-group variance collapse — **new dimension**
- All three can be stacked

**Suggestion**: GRPO v3 should first try IPS (F14, already implemented), if still stalling, layer RC-GRPO's reward token conditioning. Implementation is moderate (needs rollout sampling modification). Priority: F14 > F18 > F17.

#### F19 — AceGRPO Learnability Potential: Automatic Curriculum (audit thread frontier search A172)

**Finding**: AceGRPO (arXiv 2602.07906, Feb 2026) proposes automated curriculum strategy:
- Evolving Data Buffer: continuously converts execution trajectories into reusable training tasks
- Learnability Potential: f(task difficulty, model capability), dynamically selects tasks the model "can learn from"
- Ace-30B achieves 100% valid submission rate on MLE-Bench-Lite

**Impact**: We plan lite→standard→multi manual three-stage curriculum. AceGRPO's Learnability Potential can automate this process — dynamically selecting template/seed/tier combinations based on current model capability, rather than fixed stage switching.

**Suggestion**: Evaluate after GRPO v3 baseline is running. Low priority — first verify manual curriculum effectiveness.

#### F20 — MemAgent Multi-Conv RL: End-to-End Memory Capability Training (audit thread frontier search A176)

**Finding**: MemAgent (ICLR 2026 Oral, Microsoft) proposes Multi-Conv RL — end-to-end training of memory read/write capabilities in multi-turn dialogue. Uses DAPO instead of GRPO, combined with conversation-level reward (QA accuracy). Qwen2.5-7B improves 11-15% on LoCoMo.

**Impact**: Directly benchmarks against MemoryGym's training goals. DAPO outperforming GRPO on memory tasks has empirical support from this paper. We've already implemented DAPO Clip-Higher (F17), but MemAgent's complete DAPO pipeline includes more tricks (Dynamic Sampling filtering all-correct/all-wrong groups).

**Suggestion**: If GRPO v3 with IPS+DAPO is still unstable, reference MemAgent's complete DAPO configuration. Medium priority.

→ Read (A177), high value. MemAgent's DAPO empirical evidence supports our F17 implementation direction. Wait for GRPO v3 results before deciding whether to adopt full DAPO.

#### F21 — ScalingInter-RL Curriculum Learning: Short Before Long (audit thread frontier search A176)

**Finding**: AgentGym-RL (ICLR 2026 Oral) proposes ScalingInter-RL — first train on short horizon (few interaction rounds), progressively expand to long horizon. Training efficiency 2-5x improvement.

**Impact**: Directly maps to MemoryGym's curriculum design: lite tier (few entities, few questions) → standard (more entities) → multi (multi-session). But AgentGym-RL's key is **interaction rounds** not task complexity — first train on 3-turn interaction tasks, then 20-turn.

**Suggestion**: GRPO v3's curriculum prioritizes tier-based staging (already planned), also consider staging by stream length (event count). Simple to implement — MemoryEnv already supports custom n_entities/n_questions.

→ Read (A177), agreed. Complementary with F19 (AceGRPO) — F21 provides curriculum direction (short→long), F19 provides automated task selection. Manual tier staging first, then evaluate automation.

#### F22 — Cross-Policy Sampling to Prevent Strategy Collapse (audit thread frontier search A176)

**Finding**: AgentRL (Tsinghua THUDM) proposes Cross-Policy Sampling — mixing rollouts from different policy checkpoints within GRPO groups, preventing within-group variance degradation. Fully async pipeline supports large-scale training.

**Impact**: Solves the same problem as RC-GRPO (F18) (within-group variance collapse), but with a different implementation:
- RC-GRPO: reward token conditioned sampling
- Cross-Policy: mixing historical checkpoint rollouts

**Suggestion**: If IPS (F14) is insufficient to solve collapse, Cross-Policy Sampling is simpler to implement than RC-GRPO — only need to save N historical checkpoints and use them alternately. Priority: F14 > F22 > F18.

→ Read (A177), agreed on priority ordering. F14 (IPS) already implemented, is the preferred approach. F22 as backup is more concise than F18.

#### F23 — ReCall: Pure RL Tool Learning Without SFT Cold Start (audit thread frontier search A176)

**Finding**: ReCall proposes unsupervised RL to directly learn tool calling, skipping the SFT cold start phase. Uses curriculum from simple tools (search) to complex compositions (multi-tool orchestration).

**Impact**: Our current pipeline is SFT→GRPO. If SFT quality isn't good enough (v3 only 0/10 correct), it may limit GRPO's starting point. ReCall's approach completely skips SFT, but needs better curriculum and longer training time.

**Suggestion**: Currently maintain SFT→GRPO pipeline. If SFT v5 + GRPO v3 still fails, consider ReCall's pure RL approach. Low priority.

→ Read (A177), agreed on low priority. SFT→GRPO pipeline has more prior validation. ReCall only as Plan B if pipeline completely fails.

#### F24 — CPPO: 3-8x GRPO Training Speedup (audit thread frontier search A180)

**Finding**: CPPO (arXiv 2503.22342, NeurIPS 2025) prunes low-contribution completions by advantage absolute value, keeping only high-advantage samples for loss computation. Dynamically reallocates GPU resources freed by pruning to more questions. GSM8K speedup 8.32x, Math speedup 3.51x, no accuracy loss. Compatible with DAPO/Dr.GRPO.

**Impact**: Our GRPO v3 trains on single GPU, completion sampling (group_size=4) is the main time bottleneck. CPPO can be directly layered on top of IPS-GRPO + DAPO Clip-Higher — prune completions with advantage ≈ 0, reallocate GPU resources to more questions, equivalent to increasing batch without increasing memory.

**Suggestion**: Introduce when optimizing training speed after GRPO v3 baseline is running. Moderate implementation effort (need to filter completions before loss computation + dynamic batch padding). Medium priority.

#### F25 — TIC-GRPO: First GRPO Convergence Proof (audit thread frontier search A180)

**Finding**: TIC-GRPO (arXiv 2508.02833) uses trajectory-level probability ratio instead of token-level importance ratios, obtaining unbiased policy gradient estimates. First theoretical convergence guarantee for GRPO-type methods. Key ablation: removing importance sampling barely affects performance (old policy refreshed every few steps, bias negligible).

**Impact**: Theoretically validates the reasonableness of our current GRPO implementation. Also suggests IPS-GRPO (F14)'s importance sampling may not be necessary — if IPS doesn't significantly improve experiments, can simplify back to standard GRPO + DAPO.

**Suggestion**: Low priority, theoretical reference. If GRPO v3 experiments show IPS on/off has little difference, reference this paper to simplify implementation.

#### F26 — GTPO: Entropy-Weighted Reward to Prevent Policy Collapse (audit thread frontier search A184)

**Finding**: GTPO (arXiv 2508.04349) assigns entropy-weighted reward to each token, GRPO-S does the same at sequence level. Key experiment: initial entropy drop followed by **entropy rebound**, successfully countering DAPO baseline's policy collapse.

**Impact**: Solves the same problem as DAPO Clip-Higher (F17) (entropy collapse), but with different mechanism: DAPO uses asymmetric clip ratio, GTPO uses entropy weighting. Both can be viewed as alternative approaches.

**Suggestion**: If IPS+DAPO (GRPO v3) still shows collapse, GTPO is a backup approach. Priority lower than F14/F17.

#### F27 — GDPO: Decoupled Normalization for Multi-Reward (audit thread frontier search A184)

**Finding**: GDPO (arXiv 2601.05242) found that joint normalization of multiple rewards causes advantage to degenerate to identical values (reward collapse). Solution: normalize each reward independently, preserving relative differences.

**Impact**: Currently using single composite reward, not affected. But if future multi-objective training (separately optimizing breadth/maintenance/reasoning/efficiency), GDPO's decoupled normalization is a necessary technique.

**Suggestion**: Low priority. Reference when multi-objective training needs arise.

#### F28 — Training-Free GRPO: GPU-Free Context Space Optimization (audit thread frontier search A188)

**Finding**: Training-Free GRPO (arXiv 2510.08191) instantiates policy as **frozen LLM + variable experience context**, shifting optimization from parameter space to context space. Performance exceeds 32B fully fine-tuned LLM, learning cost from $800 to $8. Core idea: don't modify model weights, instead optimize few-shot examples (experience memory) provided to the model.

**Very high impact**: GRPO v3 has been blocked by GPU SSH for days, all parameter optimization training cannot execute. Training-Free GRPO completely bypasses GPU requirements — only needs API inference (we already have Chutes API + multiple available models).

**Implementation idea**:
1. Select K episodes from SFT trajectories as initial experience context
2. Run MemoryGym eval via API, collect success/failure trajectories
3. Use GRPO-style advantage to evaluate each experience episode's value
4. Iteratively replace low-value episodes, keep high-value episodes
5. Final context = optimal few-shot example set

**Relationship with GPU training**: Complementary not substitute. Training-Free optimizes prompt, GPU training optimizes weights. Can first use Training-Free to find optimal prompt strategy, then use GPU training to bake the strategy into weights.

**Suggestion**: **High priority** — only executable training alternative during GPU blockage. Recommend training thread evaluate feasibility.

#### F29 — Scaf-GRPO: Progressive Scaffolding to Prevent Learning Stagnation (audit thread frontier search A188)

**Finding**: Scaf-GRPO (arXiv 2510.19807) provides minimal guidance (scaffolding) only when the model stops learning autonomously. Qwen2.5-Math-7B improves 44.3% on AIME24 over vanilla GRPO.

**Impact**: Solves similar problem as RC-GRPO (F18) (learning stagnation), but simpler — doesn't need to modify rollout sampling, just detect stagnation and inject hints.

**Suggestion**: Low priority. Evaluate after GRPO v3 baseline is running.

#### F30 — MemSearcher: Multi-Context GRPO Joint Optimization of Memory+Reasoning (audit thread frontier search A193)

**Finding**: MemSearcher (arXiv 2511.02805) introduces **multi-context GRPO**, jointly optimizing reasoning, search strategy, and memory management. MemSearcher-3B outperforms 7B baseline. Core innovation: end-to-end RL under per-turn context budget constraints.

**Very high impact**: Directly benchmarks against MemoryGym's training goals — jointly optimizing storage decisions and retrieval strategy under budget constraints. "Per-turn context budget" concept maps to our write budget.

**Suggestion**: **High priority**. After GPU recovery, GRPO v3 should reference MemSearcher's multi-context design.

#### F31 — ATLAS: Rubric-Based RL for Tool-Use + Budget Constraints (audit thread frontier search A193)

**Finding**: ATLAS (arXiv 2603.06713, Microsoft Research, Mar 2026) provides rubric-based reinforcement finetuning for SLMs in large tool space environments. Decomposes task success into structured scoring criteria, context-bounding strategy as learnable decisions.

**Impact**: Directly benchmarks against MemoryGym's 4-axis scoring — rubric-based reward decomposition can map to breadth/maintenance/reasoning/efficiency as four independent reward signals, more granular than current single composite reward.

**Suggestion**: Medium priority. After GRPO v3 baseline is running, use 4-axis scores as independent reward signals (reference GDPO F27 decoupled normalization).

#### F32 — EBPO: Empirical Bayes Fixing GRPO Instability (audit thread frontier search A193)

**Finding**: EBPO (arXiv 2602.05165, Feb 2026) uses empirical Bayes shrinkage to regularize GRPO's local group baselines, borrowing global statistics. Theoretical guarantee of lower MSE and bounded entropy decay.

**Impact**: Directly addresses our GRPO v2 policy collapse (loss→negative). Orthogonal to IPS-GRPO (F14) — IPS fixes outcome-level mode collapse, EBPO fixes group baseline instability.

**Suggestion**: Medium priority. If IPS-GRPO is insufficient, EBPO is the next approach to try.

#### F33 — Competitor Analysis: AMemGym + MemoryArena (audit thread frontier search A193)

**Finding**:
- **AMemGym** (arXiv 2603.01966, ICLR 2026 Poster): Interactive on-policy memory evaluation environment, structured data sampling + state evolution. Focuses on dialogue personalization.
- **MemoryArena** (arXiv 2602.16313): Multi-session cross-task memory evaluation (web navigation + planning + search). Found that models saturated on LoCoMo fail in agentic scenarios.

**Impact**: Two direct competitors validate MemoryGym's design direction — static recall tests are insufficient to evaluate real memory management capability. MemoryGym's differentiation: information overload + budget constraints + update tracking + RL training environment (four-in-one).

**Suggestion**: Record as paper positioning reference. No code changes needed.

#### F34 — HCAPO: Hindsight Credit Assignment Fixing GRPO Sparse Reward (audit thread frontier search A199)

**Finding**: HCAPO (arXiv 2603.08754, Mar 2026) first framework to introduce hindsight credit assignment for LLM agents. Uses LLM itself as post-hoc critic to refine step-level Q-values. Multi-scale advantage mechanism fixes inaccurate value baselines at critical decision points. ALFWorld +13.8%, WebShop +7.7%.

**Impact**: Directly benchmarks against our GRPO sparse reward problem. MemoryGym's multi-turn memory operations (Write/Edit/search) have extremely sparse reward (signal only at final submit_answer). HCAPO's hindsight reasoning can provide dense per-step credit for each write/edit/search decision.

**Suggestion**: **High priority**. Complementary with F14 (IPS-GRPO) — IPS fixes mode collapse, HCAPO fixes credit assignment. Evaluate after GPU recovery.

#### F35 — ACT: Agentic Critical Training (audit thread frontier search A199)

**Finding**: ACT (arXiv 2603.08706, Mar 2026) RL paradigm — pairs expert actions with model-generated alternatives at each step, rewards correct action quality judgments. Produces genuine self-reflection rather than imitation. +5.07 over imitation learning, +4.62 over standard RL.

**Impact**: Our SFT trajectories can serve as expert demonstrations. ACT's contrastive method can teach agents *why* certain storage decisions are better, not just *what* to store.

**Suggestion**: High priority. Needs SFT trajectories as expert baseline + RL-generated contrastive samples. Moderate implementation effort.

#### F36 — RAPO: Retrieval-Augmented Policy Optimization (audit thread frontier search A199)

**Finding**: RAPO (arXiv 2603.03078, KDD'26) expands on-policy rollout exploration space by retrieving off-policy step-level traces. 14 datasets average +5.0%, training speed 1.2x.

**Impact**: Our GRPO training has exploration collapse. RAPO's step-level off-policy trace retrieval can inject diversity from successful SFT trajectories.

**Suggestion**: Medium-high priority. After GPU recovery, if IPS-GRPO still has exploration issues, RAPO is the next approach.

#### F37 — NAT: Token-Efficient GRPO (audit thread frontier search A199)

**Finding**: NAT (arXiv 2603.06619, Mar 2026) unbiased partial-token policy gradient estimator (Horvitz-Thompson reweighting). Only needs 50% tokens in backward pass to match full-token GRPO. Plug-and-play.

**Impact**: MemoryGym trajectories are very long (multi-turn tool calls). NAT can halve RL training memory/compute cost with no accuracy loss. Orthogonal to all other GRPO improvements.

**Suggestion**: Medium priority. Pure engineering optimization, integrate after GPU recovery. Simple implementation.

#### F38 — MicroCoder-GRPO: Long Output GRPO Fixes (audit thread frontier search A199)

**Finding**: MicroCoder-GRPO (arXiv 2603.07777, Mar 2026) three long-output GRPO fixes: conditional truncation masking (preserving long output potential), diversity-determined temperature, removing KL loss + high clip ratio. LiveCodeBench v6 +17.6%.

**Impact**: Memory agent output is long multi-tool call sequences. Conditional truncation masking directly addresses our long trajectory truncation issue.

**Suggestion**: Medium priority. Evaluate truncation masking technique after GPU recovery.

#### F39 — KLong: Extremely Long Horizon Task Training (audit thread frontier search A199)

**Finding**: KLong (arXiv 2602.17547, Feb 2026) Trajectory-splitting SFT (preserving early context, progressively truncating later) + progressive RL (gradually increasing timeout). KLong-106B surpasses Kimi K2 (1T) by 11.28%.

**Impact**: MemoryGym scenarios are long horizon (document stream + corrections + QA). Trajectory-splitting SFT can be directly applied to our SFT data generation. Progressive RL maps to multi-tier.

**Suggestion**: Medium priority. SFT data generation can reference trajectory-splitting technique.

#### F40 — UMA: Unified Memory Agent (Competitor) (audit thread frontier search A199)

**Finding**: UMA (arXiv 2602.18493, Feb 2026) end-to-end RL framework: dual memory (compact core summary + structured Memory Bank, CRUD operations). Introduces Ledger-QA benchmark (latent values from accumulated updates).

**Impact**: Closest to MemoryGym's design philosophy — CRUD operations + budget pressure + update tracking. Ledger-QA's "latent value" concept is similar to our correction tracking. **Direct competitor**.

**Suggestion**: Monitor. No code changes needed, paper positioning reference.

#### F41 — ToolRLA: Multiplicative Reward Decomposition (audit thread frontier search A204)

**Finding**: ToolRLA (arXiv 2603.01620, Mar 2026) proposes **multiplicative reward decomposition** — decomposing tool call reward into the product of format validity x tool selection x parameter accuracy x regulatory compliance across four dimensions. +7pp over additive reward. Three-stage pipeline SFT→GRPO→DPO. Financial deployment: task completion 62%→91%, tool error 38%→14%.

**Impact**: Our current reward is single composite (Write +0.3, Edit +0.5, correct answer +1.0). ToolRLA's multiplicative decomposition can map to MemoryGym: format correctness x entity coverage x attribute completeness x update tracking. Multiplication ensures **if one dimension is zero, total reward is zero** — prevents model from "boosting score" via a single dimension.

**Suggestion**: **High priority**. GRPO v3's shaped reward should change from additive to multiplicative. Complementary with F6 (attributed reward) + F16 (OTC tool productivity). Low implementation effort — modify reward computation formula only.

#### F42 — MAPO: Turn-Level Monte Carlo Advantage (audit thread frontier search A204)

**Finding**: MAPO (arXiv 2603.06194, Mar 2026) treats dialogue turns as temporally extended actions, uses Monte Carlo return estimation to compute advantage at turn-level, without tree expansion or learned critic. Consistently outperforms GRPO on 7B-32B models. Applicable to agentic RL + tool-use scenarios.

**Impact**: Each "turn" in MemoryGym is one tool call (Write/Edit/Read/memory_search/submit_answer). Token-level GRPO splits one Write call into hundreds of tokens, diluting gradient signal. Turn-level advantage directly evaluates "whether this Write was valuable" at the decision granularity.

**Suggestion**: **High priority**. Solves the same problem as F34 (HCAPO hindsight credit) (multi-turn credit assignment), but MAPO is simpler (no additional critic). GRPO v3 can first use turn-level grouping instead of token-level.

#### F43 — ReMemR1/RLMLR: Multi-Level Memory Rewards (audit thread frontier search A204)

**Finding**: ReMemR1 (arXiv 2509.23040) proposes RLMLR (RL with Multi-Level Rewards) — combining trajectory-level outcome reward (final answer correctness) and step-level state reward (information gain of each memory update). 20%+ error rate reduction, also effective on out-of-distribution benchmarks.

**Impact**: We currently only have trajectory-level reward (submit_answer correct=+1.0) and coarse-grained shaped reward (Write +0.3). RLMLR's step-level information gain can automatically evaluate "how much new information this Write added" — more precise than fixed +0.3. Complementary with F11 (LongRLVR dense context rewards).

**Suggestion**: **High priority**. Information gain reward can use MemoryGym's `required_entities` field — Write stored an entity that gets asked about → high information gain. GRPO v3 shaped reward design reference.

#### F44 — InfoPO: Information-Gain Turn Reward (audit thread frontier search A204)

**Finding**: InfoPO (arXiv 2603.00656, Feb 2026) models multi-turn interaction as "active uncertainty reduction" process. Computes information-gain reward per turn (compared against masked-feedback counterfactual), with adaptive variance-gated fusion combining task outcome and information gain. Exceeds GRPO by 14-16%.

**Impact**: Same direction as ReMemR1 (F43) but different mechanism — InfoPO uses counterfactual comparison, ReMemR1 uses state reward. InfoPO's variance-gating can prevent information gain from conflicting with task outcome.

**Suggestion**: Medium priority. If F43's step-level reward introduction causes shaped reward to conflict with outcome reward, InfoPO's variance-gating is the solution.

#### F45 — Turn-PPO: Turn-Level Critic Replacing GRPO (audit thread frontier search A204)

**Finding**: Turn-PPO (arXiv 2512.17008, Dec 2025, Amazon) finds GRPO unstable on multi-turn tasks, PPO's learned critic provides more accurate advantage estimation. Turn-PPO runs on turn-level MDP (not token-level), outperforms GRPO on WebShop and Sokoban.

**Impact**: If GRPO v3 (IPS + DAPO + KL) is still unstable, Turn-PPO is a fundamentally different alternative path — switching from critic-free (GRPO) to learned critic (PPO). But higher implementation complexity (needs value head training).

**Suggestion**: Medium priority. Plan B when GRPO v3 completely fails. Similar positioning to F8 (EMPO2 hybrid).

#### F46 — AriadneMem: Conflict-Aware Memory Coarsening (audit thread frontier search A204)

**Finding**: AriadneMem (arXiv 2603.03290, Mar 2026) solves two core problems of long-conversation memory: (1) scattered evidence needs multi-hop linking, (2) state updates cause old/new information conflicts. Entropy-aware gating filters noise + conflict-aware coarsening merges static duplicates while preserving temporal edges. Multi-hop F1 +15.2%, only 497 context tokens.

**Impact**: MemoryGym's correction tracking is exactly the "state update conflict" problem. AriadneMem's conflict-aware coarsening can inspire SFT trajectory Edit strategy — preserve "old value→new value" temporal relationships in storage, rather than simple overwrite.

**Suggestion**: Medium priority. SFT data quality improvement direction — memory after Edit should preserve change history (e.g., "revenue: 35.88 → 42.87").

#### F47 — AMA-Bench: Agentic Trajectory Memory Benchmark (Competitor) (audit thread frontier search A204)

**Finding**: AMA-Bench (arXiv 2602.22769, Feb 2026) evaluates long-horizon memory in agentic scenarios (not dialogue). Real trajectories + synthetic trajectories, rule-based QA. Found existing memory systems lack causal reasoning and objective information, similarity retrieval is lossy. Proposes AMA-Agent: causality graph + tool-augmented retrieval, 57.22% avg accuracy (+11.16% over baselines).

**Impact**: Along with AMemGym(F33)/MemoryArena(F33)/UMA(F40), constitutes 4 direct competitors. AMA-Bench's causality graph validates MemoryGym's correction tracking direction. Differentiation: we have budget constraints + RL training environment, AMA-Bench doesn't.

**Suggestion**: Monitor. No code changes needed, paper positioning reference.

#### F48 — MT-GRPO: Formal Turn-Level GRPO Implementation (audit thread frontier search A209)

**Finding**: MT-GRPO (arXiv 2505.11821, May 2025, updated to 2026) reformulates multi-turn agent tasks as multi-step MDP, computing advantage at turn-level (not token-level or trajectory-level). Key experimental finding: **GRPO-OR (standard outcome reward GRPO) gradually stops calling search tools** — i.e., tool collapse. MT-GRPO maintains 100% tool execution, lower training variance.

**Impact**: Directly explains our GRPO v2 policy collapse (loss→negative) — standard GRPO in multi-turn tool-use scenarios causes models to abandon tool calling. MT-GRPO is the predecessor of F42 (MAPO), both point in the same direction but MT-GRPO has more systematic MDP reformulation and experimental validation.

**Relationship with existing methods**:
- F42 (MAPO): same turn-level advantage, but MAPO uses Monte Carlo return, MT-GRPO uses explicit turn-level reward design
- F4 (AgeMem step-wise GRPO): AgeMem's step-wise is a variant of turn-level
- All three converge on the same conclusion: **multi-turn agent RL must use turn-level (not token-level) advantage**

**Suggestion**: **High priority**. GRPO v3 should implement turn-level advantage (already in to-do #4 "F42 MAPO turn-level advantage"). MT-GRPO's experimental evidence strengthens confidence in this direction.

#### F49 — LOOP: Efficient PPO Without Value Network (audit thread frontier search A209)

**Finding**: LOOP (arXiv 2502.01600, Apple Research) is a data/memory efficient PPO variant — **no value network, maintains only a single LLM copy**. Uses leave-one-out baseline estimation (computes baseline from other rollouts in same group, no extra network) + per-token clipping. 32B agent outperforms OpenAI o1 by 9pp (15% relative improvement) on AppWorld. First report of successfully applying RL to train LLM agents in stateful multi-domain environments.

**Impact**: If GRPO v3 (IPS+DAPO+KL) is still unstable, LOOP is a better PPO alternative than Turn-PPO (F45) — no value head training needed, memory footprint same as single model fine-tuning. Leave-one-out baseline is more stable than GRPO's group mean for long-horizon tasks (avoids advantage degradation when all group rewards are similar).

**Suggestion**: **Medium-high priority**. Plan B when GRPO v3 completely fails. Simpler implementation than Turn-PPO — essentially changing GRPO's baseline computation from group mean to leave-one-out mean. Priority: IPS-GRPO(F14) > LOOP(F49) > Turn-PPO(F45).

#### F50 — SkillRL: Experience→Skill Library→Recursive Evolution (audit thread frontier search A209)

**Finding**: SkillRL (arXiv 2602.08234, Feb 2026) automatically abstracts agent's raw trajectories into hierarchical skill libraries (general skills + task-specific skills), skill library co-evolves with policy during RL training. ALFWorld/WebShop +15.3%, token compression 10-20%.

**Impact**: Inspiration for SFT data generation — abstract perfect strategy's success patterns (e.g., "multi-entity packing", "search→edit correction", "budget-aware selective storage") into reusable skill descriptions. These skill descriptions could be part of system prompts, but must respect CLAUDE.md's prompt neutrality constraint.

**Suggestion**: Low priority. First get GRPO baseline running at current stage. If trained model still lacks specific skills (e.g., correction), SkillRL's skill library method is a future optimization direction.

#### F51 — MemoryRewardBench: Reward Model Memory Management Evaluation (audit thread frontier search A209)

**Finding**: MemoryRewardBench (arXiv 2601.11969, Jan 2026) first benchmark systematically evaluating reward model capability on long-term memory management. 13 RMs, 10 memory management patterns, 8K-128K context. Two evaluation modes: outcome-based (correct vs incorrect trajectories) and process-based (which of two correct trajectories has cleaner memory updates). Found all RMs degrade on process-based evaluation and ultra-long context.

**Impact**: If MemoryGym future introduces RM-based reward (instead of rule-based), MemoryRewardBench's finding suggests process-based evaluation is harder — RMs are not good at judging "which memory update strategy is better". Current rule-based reward (F41/F43) is more reliable.

**Suggestion**: Low priority. Record as reference for future RM replacing rule-based reward.

#### F52 — SELAUR: Uncertainty-Aware Shaped Rewards (audit thread frontier search A214)

**Finding**: SELAUR (arXiv 2602.21158, Feb 2026) injects token-level uncertainty (entropy + least-confidence + margin three-metric fusion) into step-level and trajectory-level rewards. Failure-aware reward reshaping reduces reward weight when agent is uncertain, amplifies when certain.

**Impact**: Can be layered on existing F43 information gain reward — uncertainty-weighting for Write decisions. High uncertainty Write (model unsure whether to store this entity) → reduce shaped reward → avoid "blind storage". More precise than F7 (MIRA linear decay), more robust than F26 (GTPO pure entropy) (three-metric fusion). Implementation needs logits access (GRPO v3 already has).

**Suggestion**: Medium priority. Evaluate after GRPO v3 baseline is running.

#### F53 — BudgetMem: Budget-Tier Memory Routing via RL (audit thread frontier search A214)

**Finding**: BudgetMem (arXiv 2602.06025, Feb 2026) divides agent memory processing into multi-module x 3 budget tiers (Low/Mid/High), uses RL-trained lightweight router to dynamically select tier per query. Outperforms baselines on LoCoMo/LongMemEval/HotpotQA.

**Impact**: MemoryGym's tier system (lite/standard/multi) directly aligns with BudgetMem's budget-tier. BudgetMem's core inspiration: use small model to train memory controller for write prioritization. Curriculum training can reference its per-query budget allocation approach.

**Suggestion**: Medium priority. Paper reference + router design inspiration. No direct code changes.

#### F54 — StructMemEval: Memory Structure Benchmark (audit thread frontier search A214) — Competitor

**Finding**: StructMemEval (arXiv 2602.11243, Feb 2026, Yandex Research) evaluates agent **organizational structure** capability for memory (transaction ledgers, to-do lists, trees). Key finding: LLMs don't proactively organize memory structure, but significantly improve after structure hints.

**Impact**: Validates MemoryGym's design direction — storage organization is a core capability. With/without hint comparison can verify prompt neutrality constraint.

**Suggestion**: Monitor. Paper positioning reference.

#### F55 — LoCoMo-Plus: Cognitive Memory Evaluation (audit thread frontier search A214) — Competitor

**Finding**: LoCoMo-Plus (arXiv 2602.10715, Feb 2026) extends memory evaluation from factual recall to cognitive memory (causal/state/goal/value four latent constraints). Found existing memory agents fail in cue-trigger semantic disconnection scenarios.

**Impact**: MemoryGym's 20 reasoning question types already cover some cognitive dimensions, but causal/goal/value are new dimensions. Differentiated positioning: MemoryGym=budget constraints+RL training, LoCoMo-Plus=cognitive depth.

**Suggestion**: Record. Paper positioning reference.

#### F56 — Evo-Memory: Self-Evolving Memory Benchmark (audit thread frontier search A214) — Competitor

**Finding**: Evo-Memory (arXiv 2511.20857, Nov 2025, DeepMind) evaluates agent test-time memory evolution across continuous task streams. Proposes ReMem pipeline. 10 datasets.

**Impact**: Evo-Memory focuses on "cross-task knowledge accumulation", MemoryGym focuses on "single session information overload management" — complementary positioning.

**Suggestion**: Monitor. Competitor positioning reference.

#### F57 — WebAgent-R1: Binary Reward Multi-Turn RL (audit thread frontier search A214)

**Finding**: WebAgent-R1 (arXiv 2505.16421) achieves 5-6x improvement with concise SFT warm-up + binary outcome reward (Qwen-2.5-3B 6.1%→33.9%). Doesn't need shaped reward.

**Impact**: If GRPO v3's shaped reward (F41/F43/F16) is overly complex causing reward hacking, WebAgent-R1 validates the feasibility of falling back to binary reward + more rollouts. Fallback approach if shaped reward fails.

**Suggestion**: Low priority. Backup approach.

#### F58 — FluxMem: Adaptive Memory Structure Selection (audit thread frontier search A214)

**Finding**: FluxMem (arXiv 2602.14038, Feb 2026) three-layer memory architecture (STIM/MTEM/LTSM) + BMM-based gating for dynamic memory structure selection. Makes "which memory organization to choose" a learnable decision.

**Impact**: MemoryGym memory backends are fixed, no multi-structure selection involved. Low relevance.

**Suggestion**: Record for reference.

#### F59 — Dr.MAS: Per-Agent Advantage Normalization (audit thread frontier search A214)

**Finding**: Dr.MAS (arXiv 2602.08847, Feb 2026) found global advantage normalization in multi-agent GRPO causes gradient instability. Solution: normalize independently per agent.

**Impact**: MemoryGym is single-agent training, low direct relevance. But per-task normalization concept can be borrowed — different templates have different reward distributions, normalizing independently per template during curriculum training may be beneficial.

**Suggestion**: Low priority. Record for reference.

#### F60 — MemoryAgentBench: Incremental Multi-Turn Memory Evaluation (audit thread frontier search A221)

**Finding**: MemoryAgentBench (arXiv 2507.05257, ICLR 2026) evaluates 4 memory capabilities: precise retrieval, test-time learning, long-range comprehension, conflict resolution. Introduces EventQA and FactConsolidation datasets.

**Impact**: Direct competitor benchmark. MemoryGym's differentiation lies in budget constraints + information overload + correction tracking + RL environment. No training-side adjustments needed, but must understand its dimensions for evaluation comparison.

**Suggestion**: Low priority. Record for reference, need to compare in future paper.

#### F63 — MEM-alpha: RL Learning Memory Construction (audit thread frontier search A221)

**Finding**: MEM-alpha (arXiv 2509.25911, ICLR 2026 under review) models memory construction as sequential decision-making, agent processes information chunks, decides memory operations, gets rewards based on QA accuracy. Trained on 30k tokens, generalizes to 400k+ (13x).

**Impact**: Highly relevant. Validates feasibility of RL training for memory management. Its reward function design (QA accuracy driven) and memory operation space (core/episodic/semantic three layers) can be directly referenced. 13x generalization result is inspiring for MemoryGym training — can train on small seeds, evaluate on large seeds.

**Suggestion**: High priority. Study its reward function design, compare with MemoryGym's current 4-axis reward.

#### F64 — INTENT: Budget-Constrained Intent-Aware Tool Call Planning (audit thread frontier search A221)

**Finding**: INTENT (arXiv 2602.11541, Feb 2026) does multi-step tool call planning under strict budgets. Intent-aware hierarchical world model predicts future tool use and risk-calibrated costs.

**Impact**: Directly relevant. MemoryGym's write budget is the same problem. INTENT's "predict future needs before deciding current action" approach can inspire agent storage strategy — agent should predict subsequent question types before deciding what to store.

**Suggestion**: Medium priority. Budget-aware planning is a core challenge for MemoryGym agents.

#### F66 — Training-Free GRPO: Zero-Cost Semantic Advantage Distillation (audit thread frontier search A221)

**Finding**: Training-Free GRPO (arXiv 2510.08191) doesn't update parameters, uses LLM introspection to generate semantic advantage as token prior. Exceeds fine-tuned small models with few samples.

**Impact**: Can serve as low-cost baseline method — verify MemoryGym RL training effect upper bound without GPU. Suitable for rapid prototype validation.

**Suggestion**: Medium priority. Suitable for rapid idea validation when GPU resources are insufficient.

#### F67 — MemoryEnv Lacks context_limit Parameter (training experiment finding)

**Finding**: In GRPO v3, the model learned to "not store, answer directly" (writes=0, correct=5/10), because document content stays in the context window throughout rollout. Root cause: `MemoryEnv` has no context length constraint — context management is entirely controlled by the external training script (`grpo_train.py`'s `rollout_max_tokens`).

**Data**:
- v3 lite tier (30 entities, ~3-5K tokens docs): writes=0 episodes score higher than writes>0 episodes
- v4a test standard tier + 6144 context: step 1 writes=0 correct=0-1/20, step 2 shows writes=7

**Impact**: This is not just a training problem, but also an evaluation problem. In real agent scenarios, context is always limited — information overload + limited budget (CLAUDE.md §Realistic Scenarios). If the model can also read answers directly from context during eval, scores don't reflect real memory management capability, violating CLAUDE.md §Scoring Validity.

**Suggestion**:
1. MemoryEnv should add `context_events_limit` parameter (keep only the most recent N events' text), making old documents "disappear"
2. Or explicitly specify in evaluation protocol: there must be sufficient gap between document events and question events so context naturally overflows
3. Add `min_context_pressure` metric to tier definitions: entities x avg_doc_tokens / context_limit > 2.0

#### F68 — Shaped Reward Misaligned with Composite Score (training experiment finding)

**Finding**: Write +0.3 (per stored new entity) in shaped reward doesn't distinguish entity value. But in composite score, efficiency axis = `correct / budget`, breadth axis only counts entities that were asked about. Entities stored but never asked about contribute 0 to composite, yet consume +0.3 positive reward.

**Data**:
- SFT v3: 15 writes, 0/10 correct → shaped reward has 15x0.3=4.5 write reward, but composite=0
- GRPO v3: writes=0 episodes have higher composite than writes=15 but correct=1 episodes

**Impact**: Shaped reward guides model to "store more", composite score rewards "store correctly". Two signals conflict. This may be a root cause of GRPO slow convergence — gradient directions are inconsistent.

**Suggestion**:
1. Remove Write +0.3 fixed shaped reward, change to post-episode retrospective attribution (F6 attributed reward)
2. Or reduce Write shaped reward to +0.05 (only prevent not storing at all), let the main gradient source be submit_answer +1.0
3. Composite score's efficiency axis already penalizes "store more get less correct", shaped reward shouldn't additionally reward storage behavior

#### F69 — Training Efficiency Bottleneck: Episode Duration vs GPU Sharing Constraints (training experiment finding)

**Finding**: Single episode takes ~7-8 min (standard tier) / ~5 min (lite tier), Qwen3-4B single card. 15 steps x 4 episodes/step training needs ~7-8 hours. On shared GPU machines, long occupation gets killed.

**Data**:
- v4a test: 2 steps x 2 episodes = 4 episodes, duration ~30 min
- Each episode 40 turns x ~10s generation per turn = ~400s + env overhead

**Impact**: Training iteration cycle too long, cannot quickly validate hypotheses. CLAUDE.md §Trainable requires the system to be an RL training environment, but current episode speed makes rapid iteration infeasible.

**Suggestion**:
1. Add `--lite-episode` mode: reduce entities (15) + questions (5) + corrections (1), episode ~2 min
2. MemoryEnv support `fast_mode`: skip noise events and session_break, keep only ingest + correction + question
3. Consider episode parallelism (multi-process rollout) — currently serial, but MemoryEnv is stateless, can be parallelized

#### F70 — 4-bit Quantized Training: Technically Feasible but Speed Impractical (training experiment finding)

**Finding**: Tested Qwen3-4B 4-bit NF4 quantized training in ~11GB VRAM. 5 experiments detailed in `devlog/grpo-v4-4bit.md`.

**Data**:
- 4-bit model loads ~3GB, total VRAM ~10-11GB, no OOM
- SFT adapter merge to 4-bit weights → tool call format lost (rounding error)
- No merge, keep dual LoRA (SFT + GRPO) → tool call inference correct
- But Qwen3 `<think>` needs 1024+ tokens → 4-bit inference 2-3x slower → single episode 30-40 min

**Impact**: 4-bit training is technically fully feasible (pipeline end-to-end no OOM), but actual speed too slow for rapid iteration. Need bf16 + full VRAM for reasonable training time.

**Suggestion**:
1. 4-bit only for inference validation (smoke_rollout), not for formal training
2. Formal training needs GPU capacity (at least 1 full A100)
3. Code is ready: `--load-in-4bit` + `--backend markdown` can be enabled anytime

#### F70b — Fission-GRPO: Tool Call Error Recovery RL (audit thread frontier search A227)

**Finding**: Fission-GRPO (arXiv 2601.15625, Jan 2026) converts execution errors into RL corrective supervision. Failed trajectories "fission" into new training instances (Error Simulator generates diagnostic feedback + on-policy recovery rollout). Qwen3-8B BFCL v4 Multi-Turn: error recovery +5.7%, overall 42.75%→46.75%.

**Impact**: **Highly relevant, recommend exploring immediately after GPU recovery**.
- MemoryGym correction events = state change recovery scenarios after tool calls
- 77.4% of failures are false abstentions → Fission can handle "searched but said IDK" error pattern
- Fission mechanism can be directly used for GRPO v3+: correction not followed by Edit → fission into new rollout containing Edit recovery
- More granular than binary reward, more practical than shaped reward (F43)

**Suggestion**: High priority. Core improvement direction for GRPO v3+.

#### F71 — TL-GRPO: Lightweight Turn-Level GRPO (audit thread frontier search A227)

**Finding**: TL-GRPO (arXiv 2601.16480, Jan 2026) does group sampling and optimization at the turn level, no critic model needed. Lighter than GTPO (F26), no critic overhead compared to Turn-PPO (F45).

**Impact**: Directly complementary with F42 (turn-level advantage design). In MemoryGym's ~100 turns, Write > Read > empty turn value differences are large, turn-level sampling provides more precise learning signal.

**Suggestion**: Medium priority. Ablation comparison after GRPO v3 baseline.

#### F74 — AgeMem: Step-wise GRPO + Unified LTM/STM Memory Training (audit thread frontier search A232)

**Finding**: AgeMem (arXiv 2601.01885, Jan 2026) exposes memory operations (ADD/UPDATE/DELETE/SUMMARY/FILTER/RETRIEVE) as tool actions, three-stage progressive RL training. **Step-wise GRPO**: broadcasts terminal reward to all intermediate tool steps, solving sparse/discontinuous reward for memory operations. Best across all baselines (+13.9%/+21.7%/+16.1%).

**Impact**: **Highest value finding — directly applicable to MemoryGym GRPO v3+**.
- AgeMem's tool interface ≈ MemoryGym's Write/Edit/memory_search
- Step-wise GRPO solves MemoryGym's "storage decisions come first, reward comes later" credit assignment problem
- Three-stage training strategy (store→manage→reason) can directly map to MemoryGym's breadth→maintenance→reasoning 4-axis progression
- AgeMem lacks information overload/budget constraints/correction tracking — MemoryGym retains unique value

**Suggestion**: Highest priority. Implement Step-wise GRPO immediately after GPU recovery.

#### F75 — RC-GRPO: Reward-Conditioned GRPO Solving Multi-Turn Tool Calling Variance Collapse (audit thread frontier search A232)

**Finding**: RC-GRPO (arXiv 2602.03025, Feb 2026) annotates trajectories with discrete reward tokens, maintains GRPO within-group diversity through reward-conditioned sampling. Solves variance collapse in multi-turn tool calling (model repeating same behavior pattern).

**Impact**: Directly relevant. In MemoryGym, models tend to repeat the "only Write, never Edit" fixed pattern, RC-GRPO can break this behavior lock-in.

**Suggestion**: High priority. Use in combination with F74 Step-wise GRPO.

#### F76 — ALMA: Automated Memory Design Meta-Learning (audit thread frontier search A232)

**Finding**: ALMA (arXiv 2602.07755, Feb 2026, Jeff Clune group) uses Meta Agent to search memory designs (database schema + retrieval/update mechanisms) as executable code. Outperforms all human-designed baselines across 4 sequential decision domains.

**Impact**: MemoryGym can serve as ALMA's evaluation environment. Medium-term reference direction.

**Suggestion**: Low priority. Long-term monitor.

#### F77 — MemAgents Workshop (ICLR 2026) — Ecosystem Signal (audit thread frontier search A232)

ICLR 2026 established a dedicated Memory for LLM-Based Agentic Systems workshop. Accepted papers cover episodic/semantic/working memory, external storage interfaces. Signal: memory management has become an independent research field.

#### F78 — Open-AgentRL / ART: Open-Source Agent RL Training Frameworks (audit thread frontier search A232)

Open-AgentRL's GRPO-TCR and ART's trajectory-level GRPO can both serve as MemoryGym adapter candidates. ART is based on Unsloth GRPOTrainer, lightweight and supports tool calls.

#### F79 — Memory-R1: Dual Agent Memory RL Framework (audit thread frontier search A236)

[arxiv:2508.19828](https://arxiv.org/abs/2508.19828). Dual agents: Memory Manager (ADD/UPDATE/DELETE/NOOP) + Answer Agent (retrieve→filter→reason). Generalizes with only 152 QA pairs training. Again validates small-data RL feasibility. MemoryGym difference: has budget + information overload.

#### F80 — StructMemEval: Memory Organization Structure Evaluation (audit thread frontier search A236)

[arxiv:2602.11243](https://arxiv.org/abs/2602.11243), Yandex Research. Evaluates agent capability to organize memory into specific structures (ledgers/to-do lists/trees). Found LLMs don't spontaneously choose correct structures. Complementary with MemoryGym: "what to store" vs "how to store". Medium-term reference direction.

#### F81 — LoCoMo-Plus: Cognitive Memory Evaluation (audit thread frontier search A236)

[arxiv:2602.10715](https://arxiv.org/abs/2602.10715). Evaluates implicit constraint maintenance under cue-trigger semantic disconnection. MemoryGym's multi_constraint question type already partially covers this dimension.

#### F82 — Evo-Memory: Streaming Self-Evolving Memory Benchmark (audit thread frontier search A236)

[arxiv:2511.20857](https://arxiv.org/abs/2511.20857), UIUC + Google DeepMind. Evaluates test-time learning (experience accumulation during inference). Direction differs from MemoryGym (train-time), low priority.

#### F83 — GRPO++ Practical Tips Summary (audit thread frontier search A236)

Rubric-based reward (multi-dimensional verifiable reward), DAPO 4 tricks, entropy collapse prevention. Validates MemoryGym GRPO v3 design direction is correct (IPS + DAPO Clip-Higher + shaped reward).

#### F84 — GiGPO: Group-in-Group Policy Optimization (audit thread frontier search A240)

[arxiv:2505.10978](https://arxiv.org/abs/2505.10978), NeurIPS 2025. Two-layer credit assignment: episode-level macro advantage (cross-trajectory comparison) + step-level micro advantage (anchor state grouping, comparing actions at same states across trajectories). ALFWorld +12%, WebShop +9% over GRPO. **No extra critic model, no extra rollout**, GPU overhead same as GRPO. Official code verl-agent (veRL extension). **Extremely high value for MemoryGym**: each Write/Edit decision's credit is hard to separate from trajectory-level reward in memory tasks, GiGPO's anchor state grouping can directly solve this. Recommend replacing with GiGPO as next optimization after GRPO v3 is running.

#### F85 — MEM1: End-to-End RL Framework for Memory+Reasoning Synergy (audit thread frontier search A240)

[arxiv:2506.15841](https://arxiv.org/abs/2506.15841), MIT. Core: agent updates a compact shared internal state each turn (supporting both memory integration and reasoning), reasoning serves as working memory. MEM1-7B on 16-target multi-hop QA improves 3.5x performance over Qwen2.5-14B, reduces memory usage 3.7x. **Insight**: MemoryGym currently has memory and reasoning separated (store → retrieve → reason), MEM1 shows unified representation is more efficient. Long-term direction reference, doesn't change short-term plans.

#### F86 — Mem2ActBench: Memory-Driven Tool Call Benchmark (audit thread frontier search A240)

[arxiv:2601.19935](https://arxiv.org/abs/2601.19935), Jan 2026. 400 memory-dependent tool-use tasks (extracted from 2029 dialogues), tests whether agents can proactively leverage memory to execute tool calls (not passive recall). All 7 memory frameworks underperform. **Differentiation**: Mem2ActBench focuses on "memory→action grounding", MemoryGym focuses on "storage decisions under information overload + update tracking", complementary. Competitor monitoring.

#### F87 — BCAS: Budget-Constrained Agentic Search Design Decisions (audit thread frontier search A240)

[arxiv:2603.08877](https://arxiv.org/abs/2603.08877), Mar 2026. Systematic experiments on budget-constrained RAG across 6 LLMs x 3 QA benchmarks: search depth, retrieval strategy (hybrid lexical+dense+reranking is optimal), completion budget interactions. **Value for MemoryGym**: validates hybrid search (MarkdownBackend already supports) is better than pure dense (ChromaDB) under budget constraints, serves as empirical support for recommended default backend.

#### F88 — lambda-GRPO: GRPO Implicit PRM + Fix (audit thread frontier search A245)

[arxiv:2509.21154](https://arxiv.org/abs/2509.21154). **Theoretical contribution**: proves GRPO automatically produces step-level process reward (implicit PRM) when sharing prefix within groups. But non-uniform distribution of process steps hinders exploration/exploitation. Proposes lambda-GRPO simple correction, improving verification accuracy. **Value for MemoryGym**: MemoryGym's multi-turn rollouts have many steps sharing prefix (same document stream → different Write decisions), GRPO is already doing step-level credit — no explicit PRM needed. Lambda-GRPO correction can be directly applied.

#### F89 — GRPO Survey: Comprehensive Overview of GRPO for Generative Models (audit thread frontier search A245)

[arxiv:2603.06623](https://arxiv.org/abs/2603.06623), Mar 2026. Covers reward design, credit assignment, sampling efficiency, diversity preservation, reward hacking mitigation. Reference manual for GRPO v3 tuning and design decisions.

#### F90 — TA-Mem: Tool-Augmented Autonomous Memory Retrieval (audit thread frontier search A245)

[arxiv:2603.09297](https://arxiv.org/abs/2603.09297), Mar 2026. LLM agent autonomously explores memory through tool selection (key-based lookup + similarity search). Outperforms baselines on LoCoMo. **Differentiation**: TA-Mem designs memory retrieval strategies, MemoryGym evaluates+trains storage decisions. Complementary.

#### F91 — MemAgents Workshop (ICLR 2026) Update (audit thread frontier search A245)

Workshop April 26-27 Rio de Janeiro. Acceptance notification March 1 already sent. Accepted papers list not yet publicly available. Check again in next frontier search.

#### F92 — HCAPO: Hindsight Credit Assignment for Long-Horizon LLM Agents (audit thread frontier search A250)

[arxiv:2603.08754](https://arxiv.org/abs/2603.08754), Mar 2026. **Core**: uses LLM itself as post-hoc critic, through hindsight reasoning refines step-level Q-value, solving two major GRPO bottlenecks (inaccurate step Q-value estimation + misaligned intermediate state value baseline). Multi-scale advantage mechanism supplements baseline at critical decision points. WebShop +7.7%, ALFWorld +13.8% over GRPO (Qwen2.5-7B). **Extremely high value for MemoryGym**: each Write/Edit decision is a critical decision point, HCAPO's hindsight critic can retrospectively evaluate "whether this Write contributed to final score". Complementary with GiGPO (F84): GiGPO cross-trajectory grouping vs HCAPO within-trajectory hindsight. Recommend GRPO v3 → GiGPO → HCAPO as training algorithm evolution path.

#### F93 — Memex(RL): Indexed Experience Memory + RL Budget-Constrained Read/Write Optimization (audit thread frontier search A250)

[arxiv:2603.04257](https://arxiv.org/abs/2603.04257), Mar 2026. Indexed experience memory: maintains compact working context (summary+index) + external full-fidelity database, agent dereferences index to recover original evidence on demand. MemexRL uses reward shaping to optimize write/read behavior under context budget — agent autonomously learns "what to store, how to summarize, how to index, when to retrieve". **Highly relevant to MemoryGym**: both train storage decisions under budget constraints, Memex's indexed memory architecture can serve as evolution direction reference for MemoryGym backends.

#### F94 — AMemGym: Interactive Memory Benchmarking (audit thread frontier search A250)

[arxiv:2603.01966](https://arxiv.org/abs/2603.01966), Mar 2026, **ICLR 2026 accepted**. Core differentiation: on-policy interactive evaluation (LLM simulates user role-play) + structured state evolution + supports self-evolution optimization. Evaluations show RAG/long-context/agentic memory all have gaps. **Direct competitor**. MemoryGym differentiation: (1) information overload + budget constraints (AMemGym has no budget), (2) correction/update tracking, (3) RL training environment (MemoryEnv), (4) determinism + anti-cheating. Competitor count update: 10+.

#### F95 — MemPO: Self-Memory Policy Optimization (audit thread frontier search A250)

[arxiv:2603.00680](https://arxiv.org/abs/2603.00680), Mar 2026. Agent autonomously manages memory: 3 actions (<mem>, <think>, <tool_call>). Memory effectiveness-based credit assignment. F1 +25.98% over base, token reduction 67%. **Insight**: MemPO's <mem> action is similar to MemoryGym's Write, credit assignment method can be referenced. Validates memory management as a trainable core capability.

#### F96 — Diagnosing Retrieval vs Utilization Bottlenecks (audit thread frontier search A250)

[arxiv:2603.02473](https://arxiv.org/abs/2603.02473), Mar 2026. 3x3 experiment: 3 write strategies (raw chunks / Mem0 fact extraction / MemGPT summarization) x 3 retrieval (cosine / BM25 / hybrid reranking). **Key finding**: retrieval is the dominant factor (accuracy spans 20pp), write strategy only 3-8pp difference. Raw chunks (zero LLM calls) match or exceed expensive alternatives. **Insight for MemoryGym**: validates the judgment that breadth is the bottleneck (A247) — when storage breadth is constrained, retrieval method matters more. Supports prioritizing retrieval optimization over storage format.

#### F97 — ProxMO: Proximity-Based Multi-Turn Optimization (audit thread frontier search A255)

[arxiv:2602.19225](https://arxiv.org/abs/2602.19225), Feb 2026. Solves credit assignment problem in multi-turn agent training where GRPO is affected: task difficulty fluctuation causes credit misassignment. ProxMO introduces success-rate-aware modulation to dynamically adjust gradient intensity + global context awareness. **Value for MemoryGym**: MemoryGym's multi-turn rollout has task difficulty varying greatly with template/seed, ProxMO's difficulty-aware mechanism can improve training stability. Complementary with HCAPO (F92): HCAPO refines single-step Q-value, ProxMO adjusts global gradient intensity.

#### F98 — C3: Contextual Counterfactual Credit Assignment (audit thread frontier search A255)

[arxiv:2603.06859](https://arxiv.org/abs/2603.06859), Mar 2026. Causal credit assignment in multi-agent LLM collaboration: freeze transcript context → evaluate context-matched alternatives → LOO baseline. Isolates single message's causal impact. **Value for MemoryGym**: although MemoryGym is single agent, C3's core idea (freeze context + evaluate counterfactual action) can apply to Write/Edit decision credit: fix other decisions, change only one Write → observe final score change. Requires extra rollouts but highest credit precision.

#### F99 — MemAgents Workshop (ICLR 2026) Status Update (audit thread frontier search A255)

Workshop April 26-27 Rio de Janeiro. Camera-ready deadline March 11 has passed. OpenReview page `ICLR.cc/2026/Workshop/MemAgent` exists but accepted papers list still not public. Check again in next frontier search.

#### F100 — Stratified GRPO: Stratified Advantage Estimation for Heterogeneous Trajectories (ICLR 2026)

[arxiv:2510.06214](https://arxiv.org/abs/2510.06214), ICLR 2026 officially accepted. Core problem: search agent trajectories are structurally heterogeneous (different number/position/results of search calls), standard GRPO uses global baseline causing cross-stratum bias ("comparing apples to oranges"). Proposes Stratified Advantage Normalization (SAN): stratify trajectories by structural attributes (e.g., number of tool calls), compute advantage within stratum. Theoretically conditionally unbiased + within-stratum unit variance. Experiments **+11.3pp** (largest improvement), more stable training. **Value for MemoryGym**: MemoryGym RL trajectories are similarly heterogeneous — different Write/Edit/Read call counts cause structural differences. SAN can be directly applied to GRPO v3: stratify by tool call count to compute advantage. Simple implementation (grouped normalize), no extra model needed. **Recommended highest priority**.

#### F101 — GEM: General Training Environment for Agentic LLMs (ICLR 2026)

[arxiv:2510.01051](https://arxiv.org/abs/2510.01051), ICLR 2026. Open-source agent training gym: async vectorized execution, 24 environments, PPO/GRPO/REINFORCE baselines. Proposes REINFORCE with Return Batch Normalization (ReBN) as baseline method for dense per-turn reward. Code `github.com/axon-rl/gem`. **Value for MemoryGym**: (1) competitor reference — GEM is general agent gym, MemoryGym is memory-specialized gym; (2) architecture reference — async vectorized execution can improve MemoryEnv training throughput; (3) ReBN method can be compared with GRPO v3.

#### F102 — GTPO/GRPO-S: Token/Sequence Level Entropy-Weighted Reward Shaping

[arxiv:2508.04349](https://arxiv.org/abs/2508.04349), v2 Feb 2026. GRPO's credit assignment is too coarse (uniform reward for entire sequence). GTPO uses token-level entropy-weighted reward, GRPO-S uses sequence-level entropy weighting. Theory based on variance reduction. **Value for MemoryGym**: in MemoryGym, tool call tokens (Write/Edit parameters) are more important than non-tool tokens. Entropy weighting can automatically focus on high-uncertainty tokens (typically decision points). But implementation complexity higher than Stratified GRPO.

#### F103 — Demystifying GRPO: U-Statistic Perspective

[arxiv:2603.01162](https://arxiv.org/abs/2603.01162), Mar 2026 (latest). Proves GRPO policy gradient is a U-statistic. Three improvement directions: fix baseline term, fix importance sampling ratio, different reward normalization. **Value for MemoryGym**: theoretical foundation — understanding GRPO's statistical properties helps choose correct normalization strategy (complementary with F100 Stratified GRPO).

#### F104 — VSPO: Value-Based Sampling + Progressive Reward Shaping

[arxiv:2512.07478](https://arxiv.org/abs/2512.07478), Dec 2025. Proposes Progressive Reward Shaping (PRS) + Value-based Sampling Policy Optimization (VSPO) for agentic RL. VSPO replaces low-value samples with task-value metric, value-smoothing clipping stabilizes gradients. **Value for MemoryGym**: PRS can alleviate MemoryGym's sparse reward problem (4-axis score only given at the end). Progressive reward shaping by difficulty naturally fits MemoryGym's tier system (lite→standard→hard progressive training).

#### F105 — HiPER: Hierarchical Plan-Execute RL + Credit Assignment (audit thread frontier search A265)

[arxiv:2602.16165](https://arxiv.org/abs/2602.16165), Feb 2026. Decomposes agent policy into high-level planner (proposes subgoals) + low-level executor (executes multi-step actions), introduces Hierarchical Advantage Estimation (HAE) doing credit assignment at both levels. Theoretically unbiased with lower variance than flat GAE. ALFWorld 97.4%, WebShop 83.3% (Qwen2.5-7B, +6.6%/+8.3%). **Value for MemoryGym**: MemoryGym's memory task is naturally two-level — planner decides "which entities to store", executor decides "use Write or Edit, storage format". HAE can evaluate value of "choosing to store entity X" at subgoal level, then evaluate "specific Write parameters" quality at action level. Complementary with HCAPO (F92): HCAPO is hindsight single-level, HiPER is foresight two-level.

#### F106 — InT: Self-Proposed Interventions for Step-Level Credit (audit thread frontier search A265)

[arxiv:2601.14209](https://arxiv.org/abs/2601.14209), Jan 2026, ICLR 2025. Model itself finds first wrong step in reasoning trace → proposes single-step correction → SFT on corrected trajectory. Solves standard RL's credit misassignment of uniform reward for entire trajectory. IMO-AnswerBench +14% (4B model surpasses 20B). **Value for MemoryGym**: can apply to failed trajectory analysis — model looks back at its Write/Edit sequence, finds first storage decision that led to subsequent failures, generates corrected SFT data. Complementary with current SFT trajectory generation (perfect + strategic): adds "error+correction" dimension of training signal.

#### F107 — MemAgents Workshop (ICLR 2026) Fourth Status Check (audit thread frontier search A269)

Workshop April 26-27 Rio de Janeiro. Camera-ready deadline March 11 has passed. OpenReview page `ICLR.cc/2026/Workshop/MemAgent` exists but accepted papers list still not public (4th check). ~6 weeks until Workshop. iclr.cc/virtual/2026/workshop/10000792 page created. Continue tracking in next frontier search.

#### F108 — Critique-GRPO: Natural Language Critique Breaking RL Training Plateau (audit thread frontier search A269)

[arxiv:2506.03106](https://arxiv.org/abs/2506.03106), v5 update. Core observation: pure numerical reward GRPO has three fundamental limitations — performance plateau, ineffective self-reflection, persistent failures. Critique-GRPO introduces natural language critique during RL plateau to guide model in correcting failed approaches, simultaneously learning initial response and critique-guided refinement. Qwen +15-21% Pass@1, AIME 2024 +16.7%. Open-source `github.com/zhangxy-2019/critique-GRPO`. **Value for MemoryGym**: when GRPO v3 training plateaus (F68 already foresees this), Critique-GRPO provides a breakthrough direction — model critiques its own Write/Edit decision sequence ("this Write stored redundant information wasting budget"), generates corrected trajectory for continued training. Complementary with InT (F106): InT finds first wrong step, Critique-GRPO provides natural language correction reasoning.

#### F109 — ToolRM: Tool-call Reward Model for Per-Tool Credit (audit thread frontier search A269)

[OpenReview](https://openreview.net/forum?id=LnBEASInVr) + [arxiv:2509.11963](https://arxiv.org/abs/2509.11963). Process Reward Model specifically designed for tool invocations. Solves gradient conflict of outcome-only reward: correct tool calls may be penalized due to final wrong answer. TRM provides independent reward signal for each tool invocation, integrates with PPO/GRPO. **Value for MemoryGym**: MemoryGym's Write/Edit/Read/memory_search are standard tool calls. TRM can score each Write ("this Write stored a high-value entity → positive reward"), solving GRPO's sparse reward problem. Complementary with shaped reward (F68): shaped reward is hand-designed, TRM is learned. Priority: evaluate after GRPO v3 baseline is running.

#### F110 — Letta Leaderboard / Context-Bench: Product-Type Agent Memory Leaderboard (audit thread frontier search A272)

[leaderboard.letta.com](https://leaderboard.letta.com/). Letta released agent memory leaderboard, testing LLM ability to manage core memory (in-context) + archival memory (external storage) within Letta framework. Claude Sonnet 4 and GPT-4.1 lead. Context-Bench additionally tests filesystem operation chains and skill discovery. **Difference with MemoryGym**: Letta tests framework-specific capability (reading/writing memory under Letta API), MemoryGym tests model-agnostic memory management chain (information overload + budget + change tracking). Not academic competitor, but product influence worth monitoring.

#### F111 — MemAgents Workshop ICLR 2026 Status (5th check, A272)

Acceptance notification sent on 2026-03-01, OpenReview page still shows loading spinner, accepted papers not public. Workshop 2026-04-26/27. Next check should be late March or early April.

#### F112 — MLMT-RL: Multi-Level Multi-Turn RL Surpassing GRPO (audit thread frontier search A277)

[OpenReview](https://openreview.net/forum?id=u1RjV99DPu), Oct 2025. Decomposes reasoning into high-level feedback generation + low-level response correction bi-level optimization. 2B MLMT-RL surpasses 3B GRPO: MATH500 +3.1%, MBPP +5.2%, GPQA +4.8%. Core: textual feedback provides dense interpretable learning signal, replacing sparse binary reward. **Value for MemoryGym**: MemoryGym's GRPO training faces same sparse reward problem. MLMT-RL's bi-level framework can map to: high-level = storage strategy evaluation ("which entities should be stored"), low-level = specific Write/Edit execution. Complementary with Critique-GRPO (F108) but more systematic. Priority: evaluate after GRPO v3 baseline.

#### F113 — Practitioner's Guide to Multi-turn Agentic RL (audit thread frontier search A277)

[arxiv:2510.01132](https://arxiv.org/abs/2510.01132) + [OpenReview](https://openreview.net/forum?id=K6T0o875zF). Systematic empirical study: multi-turn agent RL design space decomposed into environment/reward/policy three pillars. Key findings: (1) dense turn-level rewards accelerate training but stability depends on RL algorithm choice; (2) PPO (biased) vs RLOO (unbiased) performance reverses at different reward sparsity; (3) simple environment signals can generalize to complex tasks; (4) optimal SFT→RL training ratio exists. TextWorld/ALFWorld/SWE-gym experiments. **Value for MemoryGym**: **Most directly relevant guide**. MemoryGym's GRPO training is making decisions across all three pillars (environment=MemoryEnv tier design, reward=shaped vs sparse, policy=SFT→GRPO ratio). F113's empirical recipe can directly guide our hyperparameter choices. Strongly recommend as first priority reference after GPU recovery.

#### F114 — MemAgents Workshop Status (6th check, A277)

OpenReview page still not showing accepted papers. Workshop 2026-04-26/27, ~6 weeks away.

#### F115 — Agent Lightning: Zero-Code Agent RL Training Framework (audit thread frontier search A281)

[arXiv:2508.03680](https://arxiv.org/abs/2508.03680) + [GitHub](https://github.com/microsoft/agent-lightning). Microsoft open-source framework, core innovations: (1) fully decouples agent execution from RL training — supports LangChain/AutoGen/custom agents with zero code; (2) LightningRL hierarchical RL algorithm with built-in credit assignment module that automatically decomposes trajectories into training transitions; (3) formulates agent execution as MDP. **Value for MemoryGym**: current verl/slime adapters are hand-written adaptation layers, Agent Lightning might directly replace — connect MemoryEnv as environment without maintaining adapter code. Worth evaluating whether it can simplify training infrastructure after GPU recovery.

#### F116 — MemAgents Workshop Papers Starting to Appear (7th check, A281)

Acceptance notification has passed (2026-03-01). OpenReview starting to show papers: (1) "Memory Is Reconstructed, Not Retrieved: Graph Memory for LLM Agents" (MRAgent, 2026-03-03); (2) "MemGen: Weaving Generative Latent Memory"; (3) MemAgent (Multi-Conv RL) received **Oral** presentation. Workshop 2026-04-27 Rio de Janeiro. Complete accepted papers list not yet uniformly published, but individual papers can be browsed.

#### F117 — Fireworks Multi-Turn RL Best Practices Guide (audit thread frontier search A281)

[Fireworks Blog](https://fireworks.ai/blog/best-practices-for-multi-turn-RL). Industrial-grade multi-turn RL practice summary: (1) base model needs ~20% zero-shot success rate for RL (otherwise gradients dominated by noise); (2) final checkpoint usually isn't best (RL overfits to reward quirks); (3) SFT golden traces aren't enough, agent needs to learn from interaction. **Value for MemoryGym**: current models composite ~18%, near 20% threshold — SFT may just barely be enough for RL cold start. Checkpoint selection strategy needs eval-based early stopping in GRPO training.

#### F118 — A-GRAE: Diagnosing and Fixing GRPO Implicit Advantage Symmetry (audit thread frontier search A285)

[arXiv:2602.05548](https://arxiv.org/abs/2602.05548), Feb 2026. **Diagnoses core GRPO defect**: Group Relative Advantage Estimation has implicit symmetry — (1) group level: correct/incorrect trajectory weights are strictly symmetric, causing unsampled action logits to remain unchanged, hindering exploration of new correct solutions; (2) sample level: implicit preference for medium-difficulty samples, unable to adapt to changing difficulty focus during training. A-GRAE fixes both problems through asymmetric modulation, consistently improving GRPO and its variants across 7 benchmarks. **Value for MemoryGym**: **Most directly relevant**. Our GRPO v2 policy collapse may be exactly due to insufficient exploration. A-GRAE is a drop-in fix: doesn't change GRPO framework, only adjusts advantage estimation symmetry. **First priority experiment** after GPU recovery.

#### F119 — MemAgents Workshop 8th Check (audit thread frontier search A285)

OpenReview page exists but complete accepted papers list still not uniformly published. Individual papers accessible via direct URLs (MRAgent, MemGen, MEM-alpha). Workshop 2026-04-27, ~6 weeks away.

#### F120 — MemAgents Workshop 9th Check + V21 No New Findings (audit thread frontier search A288)

ICLR schedule shows MemAgent Oral Session 1A on **April 23 (Thu) 10:30-12:00** (earlier than previously expected 4/27). "MemAgent: Reshaping Long-Context LLM with Multi-Conv RL-based Memory Agent" confirmed Oral. V21 search found no new untracked papers — EMPO2(F8), Memex(RL)(F10/F93), MIRA(F7) all already tracked. Frontier tracking approaching saturation.

---

#### F121 — AgeMem: Step-wise GRPO Training Memory Tool Use (audit thread frontier search V24/A297)

[arXiv:2601.01885] Unifies LTM/STM as tool actions, 3-stage progressive RL: store first → then retrieve → then coordinate. Core innovation: **step-wise GRPO** broadcasts terminal reward to all preceding steps, solving long-range credit assignment. ALFWorld/SciWorld/HotpotQA +4.8-8.6pp. **Directly maps to MemoryGym's Write/Edit/Read actions**, 3-stage curriculum corresponds to breadth → maintenance → reasoning progression. **First priority** alongside A-GRAE(F118) after GPU recovery.

#### F122 — MemoryArena: Multi-Session Memory Benchmark (audit thread frontier search V24/A297)

[arXiv:2602.16313] Cross-session memory transfer evaluation, 4 domains, 57 steps average. **Competitor** but no budget pressure, no information overload. MemoryGym differentiation maintained.

#### F123 — AMA-Bench: Long-Range Agent Memory Benchmark (audit thread frontier search V24/A297)

[arXiv:2602.22769] First memory evaluation using real agent trajectories. Causality graph + tool-augmented retrieval. Found "similarity retrieval is inherently lossy", validates MemoryGym's hybrid search direction.

#### F124 — ICRL: Tool-Use RL Without SFT (audit thread frontier search V24/A297)

[arXiv:2603.08068] Uses few-shot prompting instead of SFT cold start, progressively removes in-context examples, transitioning from imitation to autonomous tool use. **May completely eliminate SFT v6 dependency**. Worth quick experiment after GPU recovery: can MemoryGym Write/Edit/Read be learned purely via RL?

#### F125 — T3RL: Tool Verification + Test-Time RL (audit thread frontier search V24/A297)

[arXiv:2603.02203] Uses tool execution results to verify rollouts and weight reward estimates, larger gains on harder problems. memory_search results can serve as verification signal for GRPO training.

#### F126 — MemSearcher: Multi-Context GRPO Cross-Context Generalization (audit thread frontier search V24/A297)

[arXiv:2511.02805] Maintains compact memory instead of full history. **multi-context GRPO**: sample trajectory groups under different contexts and propagate advantages across groups. 3B surpasses 7B baseline. Directly applicable to MemoryGym cross-seed generalization training.

#### F127 — GRPO-CARE: Consistency-Aware GRPO (audit thread frontier search V24/A297)

[arXiv:2506.16141] Adds consistency reward on top of GRPO — not only rewarding correct answers but also rewarding logical consistency between reasoning steps and answers. Can serve as reward enhancement plugin for MemoryGym GRPO.

#### F128 — MemAgents Workshop 10th Check (audit thread frontier search V24/A297)

April 26-27, Rio de Janeiro. Accepted papers list still not published, expected late March.

---

#### F129 — MASPO: Soft Gaussian Gating Replacing GRPO Hard Clipping (audit thread frontier search V25/A302)

[arXiv:2602.17550] Mass-Adaptive Soft Policy Optimization. Soft Gaussian gating + mass-adaptive limiter + asymmetric risk controller. Replaces GRPO hard clipping, reduces gradient signal waste. Hard clipping problem is severe in MemoryGym's sparse memory reward scenarios, MASPO may be better suited.

#### F130 — AERO: Bayesian Skip of Zero-Advantage Rollout Groups (audit thread frontier search V25/A302)

[arXiv:2602.14338] Adaptive Efficient Rollout Optimization. Bayesian posterior judges zero-advantage groups and skips + selective rejection clipping. **48% compute reduction, 45% wall-clock speedup**, no accuracy loss. MemoryGym memory tasks have many all-failed rollout groups, AERO can directly reduce training cost.

#### F131 — DPPO: Unbiased Dynamic Clipping + Dense Prompt Packing (audit thread frontier search V25/A302)

[arXiv:2603.04135] Dynamic Pruning Policy Optimization. Importance sampling correction + prompt/completion dual-layer clipping. 2.37x speedup. Can combine with AERO.

#### F132 — WS-GRPO: Weak Supervision Prefix Stop Signal Reducing Over-Reasoning (audit thread frontier search V25/A302)

[arXiv:2602.17025] Trains preference model from outcome labels, outputs prefix-level continue/stop signals. Reduces rollout length. Applicable to redundant reasoning in memory tasks.

#### F133 — UMA / Ledger-QA: End-to-End RL Memory CRUD + Cumulative Update Tracking Benchmark (audit thread frontier search V25/A302)

[arXiv:2602.18493] Unified Memory Agent. Single-policy end-to-end RL unifying CRUD + QA. Dual memory: compact core summary + structured Memory Bank. **Ledger-QA benchmark**: derives latent values from cumulative updates — **highly similar to MemoryGym maintenance axis**, validates design direction. Direct competitor, needs monitoring.

#### F134 — MemSifter: Small Model Proxy Retrieval + Result-Driven RL (audit thread frontier search V25/A302)

[arXiv:2603.03379] Small proxy model scans raw history, filters key evidence, then feeds to working LLM. Zero index computation. Dual-model architecture can inspire MemoryGym training setup.

#### F135 — StructMemEval: Structured Memory Organization Evaluation (audit thread frontier search V25/A302)

[arXiv:2602.11243] Yandex Research. Evaluates whether agents can organize memory into task-adapted structures (ledgers, to-do lists, trees). Key finding: **LLMs don't correctly organize memory without prompting**. Validates MemoryGym's prompt-neutral design — storage strategy itself is the capability being tested.

#### F136 — SSPO: Sequence-Level Soft Gating + Entropy-Aware Regularization (audit thread frontier search V25/A302)

[arXiv:2602.19327] Soft Sequence Policy Optimization. Geometric mean sequence-level importance weights. May be better than token-level methods for multi-turn memory tasks.

#### F137 — UI-Mem: Hierarchical Experience Memory + Hierarchical Group Sampling (audit thread frontier search V25/A302)

[arXiv:2602.05832] Hierarchical group sampling in GUI RL (mixing guided/unguided trajectories). Transferable to MemoryGym GRPO training. Medium relevance.

#### F138 — MemAgents Workshop 11th Check (audit thread frontier search V25/A302)

Accepted papers list still not published. April 26-27, Rio de Janeiro.

---

#### F139 — MemPO: Autonomous Memory Management + Memory Effectiveness Credit Assignment (audit thread frontier search V26/A307)

[arXiv:2603.00680] Self-Memory Policy Optimization. Agent autonomously summarizes and manages memory, credit assignment based on **memory effectiveness**. +25.98% F1, reduced token consumption. **Directly solves MemoryGym core problem** — memory management under budget pressure + memory operation level reward attribution. Comparison experiment design with AgeMem(F121) after GPU recovery.

#### F140 — Critique-GRPO: Natural Language Critique Integrated into GRPO Loop (audit thread frontier search V26/A307)

[arXiv:2506.03106] Integrates natural language critique into GRPO online RL, solving training bottleneck of pure numerical rewards. +16.7% AIME. MemoryGym's multi-axis scoring can generate structured critique (e.g., "stored entity but didn't update correction") as auxiliary training signal.

#### F141 — SGE: Strategy Space Exploration Replacing Action Space Exploration (audit thread frontier search V26/A307)

[arXiv:2603.02045] Strategy-Guided Exploration. Generate natural language strategies first, then execute actions. Mixed temperature sampling + strategy reflection. Maps to MemoryGym: explore different memory management strategies ("prioritize storing entities likely to be corrected" vs "maximize breadth") rather than individual actions.

#### F142 — DCPO: Decoupled Calibration + Accuracy GRPO Variant (audit thread frontier search V26/A307)

[arXiv:2603.09117] Decoupled Calibration Policy Optimization. Fixes gradient conflict between accuracy and calibration in GRPO. Directly maps to MemoryGym metacognition axis (knowing what you don't know).

#### F143 — RAPO: Retrieval-Augmented Policy Optimization (audit thread frontier search V26/A307)

[arXiv:2603.03078] Retrieval-Augmented Policy Optimization (KDD'26). Retrieves successful strategies to expand on-policy exploration. Can be used to pull successful memory strategies across seeds/templates.

#### F144 — MemRL: Q-Value Memory Utility Filtering (audit thread frontier search V26/A307)

[arXiv:2601.03192] Non-parametric self-evolution, two-stage retrieval (semantic + Q-value utility). No weight updates needed. Q-value memory scoring concept corresponds to MemoryGym efficiency axis.

#### F145 — RLAR: Adaptive Reward Tool Synthesis (audit thread frontier search V26/A307)

[arXiv:2603.00724] Agent dynamically synthesizes reward tool code. MemoryGym already has deterministic scoring, low relevance.

#### F146 — MemAgents Workshop 12th Check (audit thread frontier search V26/A307)

Acceptance notification date March 1, OpenReview page should have accepted list but search engines haven't indexed. April 26-27.

#### F147 — Scaf-GRPO: Progressive Scaffolding Solving GRPO Exploration Cliff (audit thread frontier search V27/A318)

Hierarchical prompting (abstract→concrete steps) progressively added when model stalls. Qwen2.5-Math-7B AIME24 +44.3%. **Directly usable**: in MemoryGym, storage strategy hints can be added as scaffolding when reasoning axis is difficult.

#### F148 — SimpleTIR: Void-Turn Filtering Stabilizing Multi-Turn Tool RL (audit thread frontier search V27/A318)

Filters turns with neither code nor answers (void turns), stabilizing multi-turn TIR training. Qwen2.5-7B AIME24 22.1→50.5. **Key insight**: in MemoryGym, turns that don't execute any tool should be marked as void turns and downweighted/filtered.

#### F149 — RICOL: Retrospective ICL for Temporal Credit Assignment (audit thread frontier search V27/A318)

NeurIPS 2025. Converts sparse reward to dense advantage (through retrospective in-context learning), then uses advantage-weighted regression to optimize. **Directly applicable**: the temporal gap between write decisions and question answering in MemoryGym is a classic credit assignment problem.

#### F150 — Agent-R1: End-to-End Multi-Turn Agent RL Framework (audit thread frontier search V27/A318)

Modular MDP modeling + GRPO optimal on multi-hop QA. Systematic framework can be directly combined with MemoryEnv.

#### F151 — VerlTool: VeRL Extension Multimodal Tool RL Framework (audit thread frontier search V27/A318)

Unified multi-tool management + async rollout. Compatible with MemoryGym's verl adapter architecture. TIGER-AI-Lab production.

#### F152 — MemBench: Comprehensive Agent Memory Evaluation (audit thread frontier search V27/A318)

Evaluates memory effectiveness/efficiency/capacity, factual+reflective memory two layers. New competitor, but no budget pressure, no change tracking, no RL training environment. MemoryGym differentiation still holds.

#### F153 — Evo-Memory: Streaming Self-Evolving Memory Evaluation (audit thread frontier search V27/A318)

UIUC+DeepMind. Streaming benchmark requiring agent to evolve memory during interaction. 10+ memory module evaluations. Supplements MemoryGym's test-time learning dimension.

#### F154 — Off-Policy GRPO Theoretical Analysis (audit thread frontier search V27/A318)

Theoretical guarantees for GRPO under on-policy/off-policy settings. Off-policy + clipped surrogate can use replay buffer to improve training efficiency.

#### F155 — M-GRPO: Hierarchical Multi-Agent GRPO Training (audit thread frontier search V28/A324)

**Finding**: M-GRPO (arXiv 2511.13288, Nov 2025) designs hierarchical GRPO for vertical multi-agent systems — main agent (planner) and sub-agents (tool executors) each compute group-relative advantage, with trajectory-alignment scheme generating fixed batches. Decoupled training pipeline (different servers running different agents). Outperforms single-agent GRPO and frozen sub-agent GRPO on GAIA, XBench-DeepSearch.

**Impact**: MemoryGym is currently single agent, but Memory-R1(F79) used dual-agent approach. If future split into Memory Manager + Answer Agent, M-GRPO's hierarchical advantage computation is a more systematic reference. Medium-term reference.

#### F156 — MRAgent: Graph Memory + Active Reconstruction (ICLR 2026 Workshop MemAgents)

**Finding**: MRAgent (ICLR 2026 Workshop, Mar 2026) proposes "memory is reconstructed, not retrieved" — uses Cue-Tag-Content association graph to represent memory, LLM dynamically explores/prunes retrieval paths during reasoning (rather than fixed retrieve-then-reason). Avoids combinatorial explosion while adapting to reasoning context.

**Impact**: Inspiring for MemoryGym backend design — current ChromaDB/MarkdownBackend is static retrieval. If trained model can dynamically reconstruct memory retrieval paths, may improve reasoning axis. Low priority but novel direction.

#### F157 — ICLR 2026 MemAgents Workshop (audit thread frontier search V28/A324)

**Finding**: ICLR 2026 established dedicated "MemAgents: Memory for LLM-Based Agentic Systems" Workshop (April 27, Rio de Janeiro, hybrid). Accepts full(9p)/short(4p)/tiny(2p) papers. Covers: episodic/semantic memory, working memory, RAG, context management, temporal credit assignment. Submission deadline has passed (Feb 13, 2026).

**Impact**: **Extremely high strategic value**.
1. Ideal submission target for MemoryGym paper (if NeurIPS 2025 is too tight or want more exposure)
2. Confirms agent memory has been recognized as independent research direction by top venues
3. Workshop papers and posters will be most direct competitor intelligence source
4. MemoryGym should follow up on all accepted papers after workshop

#### F158 — RLFactory: veRL Multi-Turn Tool RL Plug-and-Play Framework (audit thread frontier search V29/A331)

**Finding**: RLFactory (arXiv 2509.06980, Aug 2025) built on veRL + Qwen-Agent + MCP for multi-turn tool call RL framework. Core design: (1) asyncio async tool calls; (2) tool call decoupled from training module (reducing environment config cost); (3) diverse reward computation (rule-based / model judgment / tool verification). Qwen3-4B achieves 0.486 on NQ dataset, surpassing larger models. Training throughput 6.8x improvement.

**Impact**: MemoryGym's veRL adapter can reference RLFactory's async tool call and decoupled architecture. Especially the 6.8x throughput improvement engineering tricks are worth learning.

#### F159 — MemGen: Generative Latent Memory (ICLR 2026 Workshop MemAgents)

**Finding**: MemGen (arXiv 2509.24704, Sep 2025) proposes dynamic generative memory framework, agent spontaneously evolves planning memory / procedural memory / working memory and other human cognitive memory patterns. Exceeds ExpeL/AWM by 38.22% across 8 benchmarks, exceeds GRPO by 13.44%. Accepted by MemAgents Workshop.

**Impact**: MemGen's generative memory and MemoryGym's external storage memory are complementary directions. MemGen exceeding GRPO data point suggests memory-specialized training methods outperform general RL.

#### F160 — Tool-R1: Sample-Efficient Tool RL (audit thread frontier search V29/A331)

**Finding**: Tool-R1 (arXiv 2509.12867, Sep 2025) uses 1,300 samples (7% of MAT Agent) + GRPO to train Qwen2.5-7B/14B for general tool calling. Qwen2.5-7B accuracy from 10.3%→19.4%. On GAIA benchmark Qwen2.5-14B achieves 26.67% (highest open-source). Generates executable Python code, cross-step variable sharing.

**Impact**: Proves GRPO's sample efficiency in tool RL. MemoryGym training can reference its outcome-based reward design (LLM judge + code execution success combination).

**Suggestion**: Paper thread should follow this workshop — even though submission deadline has passed, workshop's accepted papers (expected early April publication) will be the densest competitor analysis source. Also adjust paper related work to cite representative workshop works.

#### F161 — Rewarding the Unlikely: GRPO Distribution Sharpening Fix (audit thread frontier search V30/A335)

**Finding**: arXiv 2506.02355 (CMU, Jun 2025). Reveals GRPO's "degenerate ranking bias" — high-probability trajectories are reinforced, low-probability but correct trajectories are ignored. Result is "distribution sharpening" rather than truly learning new capabilities. Proposes unlikeliness reward to explicitly encourage reinforcing rare correct solutions, pass@N exceeds standard GRPO across wide range of N.

**Impact**: Complementary with F17 (DAPO Clip-Higher). If GRPO v3 shows insufficient strategy diversity (all group samples generate similar trajectories), unlikeliness reward can improve.

**Suggestion**: Monitor group sample diversity metrics in GRPO v3. If diversity declines, consider introducing unlikeliness reward.

#### F162 — ToolBrain: Tool RL Engineering Framework (audit thread frontier search V30/A335)

**Finding**: arXiv 2510.00023 (Sep 2025). Supports GRPO/DPO/SFT tool-use RL framework. LLM-as-judge reward, QLoRA via Unsloth, knowledge distillation, automatic task generation. CodeAct agent +30% improvement.

**Impact**: Engineering reference — framework design (not methodological innovation). MemoryGym's training module already has similar functionality.

#### F163 — Memory Management Empirical Study (audit thread frontier search V30/A335)

**Finding**: arXiv 2505.16067 (May 2025). Empirically analyzes how memory management affects LLM agent long-term performance. Found "error propagation" and "experience replay bias" as two key problems — poor quality memories compound over time.

**Impact**: Validates MemoryGym's core hypothesis — memory quality (not quantity) determines agent performance. Paper can cite this study to support "information overload + budget constraint" design motivation.

#### F164 — BCAS: Budget-Constrained Agentic Search (audit thread frontier search V31/A345)

**Finding**: arXiv:2603.08877 (Mar 2026). Systematic study of budget constraint impact on agentic search across 6 LLMs x 3 QA benchmarks. Directly validates MemoryGym core hypothesis.

**Impact**: Paper should cite. Budget constraint + decision quality relationship has external empirical support.

#### F165 — Letta Context-Bench: Agentic Context Engineering (audit thread frontier search V31/A345)

**Finding**: Letta published Context-Bench, filesystem storage at 74% on LoCoMo, exceeding specialized memory tools. Argument: "agentic context engineering" — agent autonomously decides what context to load.

**Impact**: Challenges necessity of complex memory tools. MemoryGym tests what-to-store (upstream decisions), Context-Bench tests what-to-load (downstream retrieval). Complementary not competitive.

#### F166 — Memory in the Age of AI Agents Survey (audit thread frontier search V31/A345)

**Finding**: arXiv:2512.13564. Tsinghua C3I team systematic survey. Covers benchmark list, open-source frameworks, frontier directions (memory automation, RL integration, multimodal, trustworthiness).

**Impact**: Paper related work should cite. MemoryGym occupies unique position in survey's benchmark classification with budget+update+anti-gaming+RL four-in-one.

#### F167 — verl-agent Official GiGPO Support (audit thread frontier search V31/A345)

**Finding**: verl-agent (veRL extension) now supports GRPO/PPO/DAPO/GSPO/RLOO/GiGPO. GitHub: langfengQ/verl-agent.

**Impact**: MemoryGym's verl adapter should evaluate migration to verl-agent. GiGPO's step-level credit assignment is particularly valuable for memory tasks.

#### F168 — RetroAgent: Dual Intrinsic Feedback Driving Memory Updates (audit thread frontier search V32/A349)

**Finding**: RetroAgent (arXiv:2603.08561) implements retrospective + introspective dual intrinsic feedback mechanism, producing numerical signals and language feedback through SimUtil-UCB memory buffer. ALFWorld +18.3%, WebShop +15.4%, exceeding GRPO-trained agents.

**Impact**: Directly addresses MemoryGym's maintenance bottleneck — root cause of model receiving correction info but not executing Edit may be lack of "retrospection" mechanism. Dual feedback can serve as shaped reward design reference.

#### F169 — OpenClaw-RL: Fully Async Agent RL Training Framework (audit thread frontier search V32/A349)

**Finding**: OpenClaw-RL (arXiv:2603.10165) fully async RL framework, GRPO binary rewards + On-Policy Distillation (OPD) producing token-level advantage signals, supports terminal/GUI/SWE/tool-call agents. Compatible with OpenClaw.

**Impact**: MemoryGym uses OpenClaw-compatible interface (Write/Edit/Read/memory_search), OpenClaw-RL may directly adapt. Async architecture solves our episode duration bottleneck (F69: single episode 30-40 minutes).

#### F170 — CogMem: Three-Layer Cognitive Memory Architecture (audit thread frontier search V32/A349)

**Finding**: CogMem (arXiv:2512.14118) proposes LTM consolidation + Direct Access session memory + Focus of Attention three-layer architecture, TurnBench-MS 0.93 accuracy (vs 0.76 baseline).

**Impact**: MemoryGym currently only tests single-layer memory backends (ChromaDB / Markdown). Multi-layer architecture is a natural training target — agent learning hierarchical storage may improve breadth+efficiency.

#### F171 — TopoCurate: Topology-Aware Tool RL Data Filtering (audit thread frontier search V33/A354)

**Finding**: TopoCurate (arXiv:2603.01714) projects multiple rollouts onto semantic quotient topology, capturing how tool calls drive success/failure divergence. SFT +4.2%, RL +6.9% (BFCLv3 + Tau2).

**Impact**: Topology-aware data filtering can improve MemoryGym SFT data quality — filter out low-information trajectories where tool call patterns cannot distinguish good/bad.

#### F172 — ActMem/ActMemEval: Causal Graph Memory Reasoning Benchmark (audit thread frontier search V33/A354) — Competitor

**Finding**: ActMem (arXiv:2603.00026) converts dialogue history into causal/semantic graphs + counterfactual reasoning. ActMemEval focuses on logic-driven memory scenarios.

**Impact**: New competitor, but focuses on dialogue memory not information overload+budget+change tracking. MemoryGym differentiation still holds.

#### F173 — PlugMem: Task-Agnostic Plugin Memory Module (audit thread frontier search V33/A354)

**Finding**: PlugMem (arXiv:2603.03296) cognitive science-inspired knowledge-centric memory graph, invariant across 3 heterogeneous benchmarks.

**Impact**: Can serve as candidate third-party memory backend for MemoryGym. Its "task-agnostic" claim can be stress-tested using MemoryGym's multi-template setup.

#### F174 — env.py Audit Found Two Training Bugs (audit thread code audit A356)

**Finding 1 (HIGH)**: In `MemoryEnv.step()`, `_stored_entity_names` is only updated in the `reward_mode="shaped"` branch (env.py:652). When `reward_mode="binary"`, written entities don't update the tracking set, causing `get_verifiable_reward()` to compute stored_count=0, maintenance axis always 0.

**Finding 2 (MEDIUM)**: `MemoryEnv.__init__` defaults `eval_salt=0` (env.py:401), but all TIERS use `eval_salt=1`. Without tier parameter, training/evaluation question sets differ, potentially causing distribution shift.

**Suggestion**:
1. In step()'s Write handling, update `_stored_entity_names` regardless of reward_mode
2. Change eval_salt default to 1, or inherit from tier

#### F175 — BATS: Budget-Aware Tool-Use Scaling (audit thread frontier search V34/A361)

[arXiv:2511.17006] Budget Tracker continuously tracks tool-call budget usage, agent's planning/tool-use/verification strategies adjust dynamically with budget. Core insight: **tool-call budget is better than token budget for constraining agents** — directly corresponds to capability of acquiring external knowledge. MemoryGym's write budget is exactly this type of budget constraint. Can reference BATS's Budget Tracker design to improve budget signal delivery in MemoryEnv.

#### F176 — SE-Search: Self-Evolving Search Agent + Dense Reward (audit thread frontier search V34/A361)

[arXiv:2603.03293] Three components: memory purification (cleaning irrelevant memories), atomic query training, dense reward (fine-grained reward signal). Core direction aligns with MemoryGym's shaped reward — using dense reward to replace sparse terminal reward. Medium relevance, more search-scenario oriented.

---

#### F177 — AMA-Bench: Long-Horizon Agentic Memory Benchmark (audit thread frontier search V35/A374) — Competitor

[arXiv:2602.22769, Feb 2026] Evaluates LLM agent long-horizon memory in real agentic scenarios. Unlike existing dialogue-centric benchmarks, AMA-Bench focuses on machine-generated interaction flows (agent-environment interaction). Proposes AMA-Agent (causality graph + tool-augmented retrieval), 57.22% accuracy exceeding baselines by 11.16pp. **Complementary positioning with MemoryGym**: AMA-Bench tests retrieval not storage triage, MemoryGym tests the complete chain (information intake→storage decisions→retrieval→update→reasoning). Can cite for comparison in paper.

#### F178 — MIRA: Memory-Integrated RL Agent (audit thread frontier search V35/A374)

[arXiv:2602.17930, ICLR 2026] Amortizes LLM guidance into persistent memory graph, designs utility signal for soft advantage estimation adjustment. Utility naturally decays as training progresses, preserving standard convergence guarantees. **Insights for MemoryGym training**: (1) memory graph as training intermediate product can provide dense reward signal; (2) utility decay can avoid LLM supervisor overfitting; (3) especially effective in sparse reward environments (like MemoryGym).

#### F179 — MemRL: Runtime RL on Episodic Memory (audit thread frontier search V35/A374)

[arXiv:2601.03192, Jan 2026] Self-evolving agents, runtime RL + episodic memory. Agent accumulates episode experience during task execution, uses RL to optimize memory read/write strategy. Direction highly consistent with MemoryGym's MemoryEnv — both treat memory operations as learnable action space.

#### F180 — AMemGym v2: Interactive Memory Evaluation (audit thread frontier search V35/A374) — Competitor

[arXiv:2603.01966, Mar 2026] AMemGym updated version, structured data sampling with predefined user profiles and state evolution trajectories, supports on-policy evaluation and optimization. **Comparison with MemoryGym**: AMemGym focuses on dialogue personalization memory, MemoryGym focuses on information overload + budget constraints + update tracking. Different-dimension competitors.

#### F181 — Anatomy of Agentic Memory: Taxonomy + System Limitations Analysis (audit thread frontier search V35/A374)

[arXiv:2602.19320, Feb 2026] Survey nature, taxonomy and empirical analysis of agentic memory evaluation and system limitations. Can serve as paper related work citation source.

#### F182 — A-MEM: Zettelkasten-inspired Agentic Memory (audit thread frontier search V36/A384) — Memory Organization

[arXiv:2502.12110, NeurIPS 2025] Xu et al. (Rutgers). LLM autonomously organizes memory into interconnected knowledge network, dynamic indexing + linking + memory evolution. Automatically updates associated old memories when new memories arrive. Outperforms SOTA across 6 base models. Directly corresponds to MemoryGym's breadth+maintenance two axes, validates importance of storage organization strategies.

#### F183 — Agent-R1: End-to-End Multi-Turn RL Training for LLM Agents (audit thread frontier search V36/A384) — Training Framework

[arXiv:2511.14460, Nov 2025] Xi et al. (Renmin Univ). Open-source modular framework, supports PPO/GRPO/REINFORCE++. MDP formalization for multi-turn interactive agents. GRPO-trained agents surpass commercial models. Highly complementary with MemoryGym's GRPO v3 training pipeline, can serve as training backend or paper comparison.

#### F184 — Agent-Omit: Adaptive Thought and Observation Omission for Agentic RL (audit thread frontier search V36/A384) — Efficiency Training

[arXiv:2602.04284, Feb 2026] Zhong et al. (HKUST). Trains LLM agents to adaptively skip redundant thoughts and observations (cold-start SFT + dual-sampling RL). Agent-Omit-8B matches 7 frontier models but more efficient. Directly corresponds to MemoryGym efficiency axis (20% weight), adaptive omission concept maps to storage decisions under budget constraints.

#### F185 — AgentGym-RL: ScalingInter-RL Multi-Turn Long-Horizon Decisions (audit thread frontier search V36/A384) — Training Curriculum

[arXiv:2509.08755, ICLR 2026 under review] Xi et al. (Renmin Univ). Unified multi-turn RL framework + ScalingInter-RL curriculum (from exploitation to exploration). Decoupled architecture (environment/agent/training modules), supports 27 task types. Qwen2.5-7B surpasses o3/Gemini-2.5-Pro. Curriculum learning method can solve sparse delayed reward problem in MemoryGym training for memory operations.

#### F186 — MemAgents Workshop @ ICLR 2026 (audit thread frontier search V36/A384) — Ecosystem Signal

[ICLR 2026 Workshop, Apr 27, Rio de Janeiro] "Memory for LLM-Based Agentic Systems" dedicated workshop, covering architecture/RL/evaluation/neuroscience. MemoryGym as evaluation+training platform is highly aligned with this workshop theme. Accepted papers should be monitored.

#### F187 — Memo: Memory-Efficient Embodied Agents via RL (audit thread frontier search V37/A391) — Architecture Reference

[arXiv:2510.19732, NeurIPS 2025 Spotlight] Transformer-based RL architecture, compresses historical experience into memory buffer through periodic summarization tokens. Outperforms long-context baselines in grid-world and indoor navigation, generalizes to longer context at inference. Difference with MemoryGym: Memo targets embodied/visual tasks, MemoryGym targets text memory management. Summarization token approach may inspire MemoryEnv observation compression.

#### F188 — CloneMem: AI Clone Long-Term Memory Evaluation (audit thread frontier search V37/A391) — Competitor

[arXiv:2601.07023, Jan 2026] Evaluates AI Clone long-term memory, input is non-dialogue digital traces like diaries/social media/emails (1-3 year span). Focuses on personal experience tracking, emotional changes, opinion evolution. Difference with MemoryGym: CloneMem targets personalization/emotional understanding, MemoryGym targets structured entity memory management + budget constraints. Complementary not competitive.

#### F189 — RealMem: Real Project Scenario Memory Evaluation (audit thread frontier search V37/A391) — Competitor

[arXiv:2601.06966, Jan 2026] First memory evaluation based on real project scenarios, 2000+ cross-session dialogues x 11 scenarios. Focuses on long-term project state management and dynamic context dependencies. Found existing memory systems severely lacking in project state tracking. Comparison with MemoryGym: RealMem tests cross-session project memory, MemoryGym tests within-session storage decisions under information overload. RealMem lacks budget constraints and RL training environment. Paper related work should cite.

#### F190 — KnowMe-Bench: Personal Understanding Evaluation (audit thread frontier search V37/A391) — Indirectly Related

[arXiv:2601.04745, Jan 2026] Reconstructs narratives into flashback-aware temporal anchored flows, evaluates factual recall, subjective state attribution, principle-level reasoning. RAG systems mainly improve factual accuracy, temporal reasoning and higher-order inference still have errors. Weak relationship with MemoryGym (targets personal understanding not entity memory management), but temporal anchored evaluation method can be referenced.

#### F191 — SUPO: Summarization-augmented Policy Optimization (audit thread frontier search V38/A396) — Training Method

[arXiv:2510.06727, ICLR 2026 under review] ByteDance/Stanford/CMU. Core: periodic LLM summary compresses tool call history in multi-turn RL, maintaining compact context while training agent to surpass fixed context window limits. Formalizes summarization-augmented MDP, derives end-to-end policy gradient jointly optimizing tool use and summarization strategy. BrowseComp-Plus +14.0% absolute accuracy, 60% accuracy (baselines much lower). **Relationship with MemoryGym**: context overflow is a real bottleneck in MemoryEnv training (standard tier 60 entities x narrative documents), SUPO's summary compression + end-to-end training method can directly solve MemoryEnv long episode training problem.

#### F192 — MemoryRewardBench: Reward Model Memory Management Evaluation (audit thread frontier search V39/A401) — Evaluation/Training

[arXiv:2601.11969, Jan 2026] First benchmark specifically evaluating reward model judgment quality on long-term memory management. 10 settings, up to 128K context. Core finding: even Llama 3.3-70B degrades at 128K+; semantic labels (A-Mem style) can improve RM accuracy 10-15%. **Relationship with MemoryGym**: reward signal quality is key in RL training, MRB's finding (semantic labels improve RM accuracy) can improve MemoryEnv's reward shaping.

#### F193 — Hindsight: Agent Memory System with Retrospective Reflection (audit thread frontier search V39/A401) — System

[arXiv:2512.12818, Dec 2025] Agent memory system that learns and optimizes memory performance through retrospective reflection mechanism. LongMemEval 91.4%, LoCoMo 89.6%. Not benchmark but system approach, but its high scores suggest current benchmarks may lack discriminability. **Relationship with MemoryGym**: validates MemoryGym design direction — budget constraints + correction tracking provide challenge dimensions that Hindsight-type systems cannot bypass.

#### F194 — LongMemEval: Long-Term Interaction Memory Evaluation (audit thread frontier search V39/A401) — Competitor Benchmark

[arXiv:2410.10813, ICLR 2025] 500 curated Qs, 5 competencies (information extraction, multi-session reasoning, temporal reasoning, knowledge update, abstention), 115K-1.5M tokens. Even GPT-4o has 30-60% performance drop. **Relationship with MemoryGym**: competitor, but no budget constraints, no 4-axis scoring, no world template structure. Paper related work should cite.

#### F195 — StructMemEval: Structured Memory Organization Evaluation (audit thread frontier search V40/A411) — Competitor Benchmark

[arXiv:2602.11243, Feb 2026] First benchmark testing LLM structured memory organization capability (transaction ledgers, to-do lists, trees). Found LLMs struggle to correctly organize memory structure without explicit prompts; two failure modes: no organization vs fabricated organization. **Relationship with MemoryGym**: LOW risk. StructMemEval only tests structure type selection (narrow focus), MemoryGym tests complete 7-stage chain (information intake→storage decision→organization→retrieval→change→reasoning→metacognition). Orthogonal not competitive.

#### F196 — MemoryBench: Continual Learning Memory Evaluation (audit thread frontier search V41/A427) — Competitor Benchmark

[arXiv:2510.17281, Oct 2025] Evaluates LLM system capability to continually learn from user feedback. Distinguishes declarative vs procedural knowledge, multi-domain multi-language. Found existing memory systems cannot effectively use procedural knowledge. **Relationship with MemoryGym**: LOW risk. MemoryBench tests cross-session continual learning (user feedback driven), MemoryGym tests single-session information overload management (budget + update tracking). Complementary positioning. Paper related work can cite.

#### F197 — MemOS: AI Memory Operating System + OpenClaw Plugin (audit thread frontier search V41/A427) — Infrastructure

[arXiv:2507.03724, Jul 2025; v2.0 Dec 2025; OpenClaw Plugin Mar 2026] MemTensor open-source memory OS. Core abstraction MemCube (unifying plaintext/activation/parameter memory), three-layer architecture (API/scheduling/storage). v2.0 supports multimodal memory, tool memory, enterprise optimization. **Relationship with MemoryGym**: **Ecosystem opportunity**. MemOS OpenClaw plugin (Mar 8, 2026) naturally interfaces with MemoryGym's OpenClaw-compatible interface — MemOS can serve as MemoryGym's third backend. Medium-term monitoring.

---

## Training CLI

### Remote Training Tools (recommended)

`scripts/train.py` — Unified remote training entry point, auto-syncs code + GPU detection + log parsing.

```bash
# View GPU status and running training tasks
python scripts/train.py status --remote $GPU_SSH

# Remote SFT training (auto-sync code + select idle GPU)
python scripts/train.py sft --remote $GPU_SSH --model $MODEL_PATH --lora

# Remote GRPO training
python scripts/train.py grpo --remote $GPU_SSH \
    --model $MODEL_PATH --adapter checkpoints/sft \
    --steps 10 --group-size 4

# Monitor running training
python scripts/train.py monitor --remote $GPU_SSH --log /tmp/grpo.log
```

> **Rule**: All remote training must be launched through `scripts/train.py`, directly SSH-ing to execute commands is forbidden.

### Local Tools (no GPU)

```bash
# Smoke test
python -m memorygym.training smoke

# Generate SFT data
python -m memorygym.training data --seeds 20 -o data/sft_train.jsonl
```

### Training Module Structure

```
memorygym/training/
    __init__.py      # Backward-compatible re-exports (MemoryEnv, generate_sft_trajectory)
    env.py           # MemoryEnv RL environment + SFT trajectory generation
    common.py        # Shared utilities (model loading, assistant mask, chat template)
    cli.py           # Unified CLI entry point (data/sft/grpo/smoke)
    __main__.py      # python -m memorygym.training entry point
```

### Output Structure

Each training automatically creates `runs/<mode>_<timestamp>/` directory:
- `config.json` — Full hyperparameters (reproducible)
- `training_log.jsonl` — Per-step metrics (loss, reward, correct)
- `metrics.json` — Final summary
- `episodes/` — GRPO episode samples (for debugging)
- `checkpoints/` — Model checkpoints

## To-do

1. **GRPO v4a short experiment** (current priority, all GPUs occupied ~11GB free)
   - `--rollout-max-tokens` implemented, context pressure effective (v4a test: writes=0→writes=7)
   - `--turn-level` implemented: shaped reward participates in advantage computation (50/50 mix episode + shaped)
   - 10 templates synced (added project/agentteam)
   - Per-turn shaped reward collection (`turn_rewards` in stats)
   - Experiment command: `--tier standard --rollout-max-tokens 6144 --ips --kl-coeff 0.05 --turn-level --steps 3`
   - Lightweight config: `--group-size 2 --groups-per-step 1` (only 2 episodes per step, ~15 min/step)
   - **Execute when GPU becomes available**

2. Multi-template curriculum effect validation (lite → standard → multi)

## Training Data Insights (2026-03-11 analysis)

**SFT Perfect vs Real Models Core Gap**:

| Metric | SFT Perfect | Real Models (123 evals mean) |
|--------|-------------|------------------------------|
| Writes used | ~7/30 (23%) | ~30/30 (100%) |
| Entities/Write | 4.3 (multi-entity packing) | 1.0 (no packing) |
| Attrs/Entity | ~21 (all attributes) | ~5 (76% attributes lost) |
| Edits (correction) | ~5/5 | 0-1/5 |
| Budget remaining | ~23/30 | 0/30 |

**Training Key Objectives** (priority order):
1. **Context pressure**: Force model to use memory system instead of context (F67, `--rollout-max-tokens`)
2. **Attribute density**: Teach model to include more attributes in Write (currently 76% lost)
3. **Multi-entity packing**: Teach model to store multiple entities in single Write (4.3x vs 1.0x)
4. **Correction execution**: Teach model to execute search→Edit flow for correction events

## Completed

- **Phase 113: Shaped Reward + GRPO v3 Clipped Loss** (commit 60502ed, 2026-03-12)
  - F41 (ToolRLA multiplicative): Edit reward refined to search+correct=0.6, correct-only=0.5, wrong=0.1
  - F43 (ReMemR1 info gain): Writing questioned entity → 0.5 (vs unquestioned 0.3). Implemented via precomputed `_questioned_entities` set
  - F16 (OTC packing bonus): Multi-entity packing +0.1 per extra entity, incentivizing entities_per_write > 1
  - GRPO v3 loss: PPO-style clipped surrogate (-min(r*A, clip(r)*A)) replacing REINFORCE (-A*log_p)
  - DAPO Clip-Higher: Asymmetric clipping preventing entropy collapse, parameter `--clip-higher 0.28`
  - IPS-GRPO: Inverse frequency scaling preventing mode collapse, parameter `--ips`
  - Both entry points committed: `scripts/grpo_train.py` + `memorygym/training/cli.py`
  - Local tests: 47 training tests + 48 simulation checks ALL PASS
- **Shaped reward improvements: F41 + F43 + F16** (2026-03-12)
  - F43 (ReMemR1 info gain): Write storing questioned entity → 0.5 (vs unquestioned 0.3). Implemented via precomputed `_questioned_entities` set
  - F41 (ToolRLA multiplicative): Edit reward refined to search+correct=0.6, correct-only=0.5, wrong=0.1
  - F16 (OTC packing bonus): Multi-entity packing +0.1 per extra entity, incentivizing entities_per_write > 1
  - Changed files: `memorygym/training/env.py` (reward logic), `tests/test_training.py` (assertions updated)
- GRPO loss upgraded to PPO-style clipped ratio + DAPO Clip-Higher (F17)
  - Original REINFORCE-style (`-advantage * log_prob`) → clipped surrogate (`-min(ratio*A, clip(ratio)*A)`)
  - `--clip-eps 0.2` (symmetric clipping) + `--clip-higher 0.28` (DAPO asymmetric clipping preventing entropy collapse)
  - Reference logits reuse peft disable_adapter_layers(), no extra model memory overhead
  - Auto fallback to REINFORCE-style when no adapter
- IPS-GRPO implementation (Phase 103): `--ips` flag, inverse frequency scaling preventing mode collapse
- SFT v3 complete: loss 0.1975→0.076, Write/Edit/Read format correct, but 0/10 correct (see `devlog/sft-v3.md`)
- SFT v3 data generation: `data/sft_v4.jsonl` (160 perfect) + `data/sft_v4_strategic.jsonl` (160 strategic)
- SFT v5 data generation (after Phase 104 correction fix): `data/sft_v5.jsonl` (160 perfect, 3.0 edits/traj) + `data/sft_v5_strategic.jsonl` (160 strategic, 3.0 edits/traj) — 51% correction edit rate, up from ~1.7 pre-fix
- SFT v6 data generation (after Phase 112 free correction Edit): `data/sft_v6.jsonl` (160 perfect) + `data/sft_v6_strategic.jsonl` (160 strategic) — 80.6% edit rate, 100% correction messages include free-edit info + entity/old_val/new_val details
- MemoryEnv complete implementation (reset/step interface, ChromaDB embedding search, binary + shaped reward)
- SFT trajectory generation (perfect/strategic strategies, OpenAI messages format)
- verl adapter (AgentLoopBase integration, @register memorygym_agent)
- verl reward function (exact match + numeric tolerance + pre-computed reward)
- slime adapter (custom generate/reward, multi-turn episode)
- Shared tool parsing (_common.py: 4 format parsing + episode runner)
- Training data generation scripts (single tier / curriculum mixed tier)
- Training configuration (GRPO + curriculum YAML)
- Complete test coverage (36 tests in test_training.py + 32 in test_adapters.py)
- noise/session_break event support
- GPU smoke test
- Remote training CLI (scripts/train.py) — SSH remote execution + real-time logs + GPU auto-detection
- SFT training pipeline complete — loss 0.22→0.06, correctly produces `<tool_call>` tags
- Multi-GPU training support (DDP/FSDP via accelerate)
- SFT full pipeline acceptance — Result: 12 stores, 0/10 correct, reward=0.07
- Unified training module (`memorygym/training/` package refactoring)
  - Single entry point CLI: `python -m memorygym.training <command>`
  - SFT auto data generation + training
  - GRPO pipeline (episode rollout + advantage-weighted policy gradient)
  - Shared tool layer (model loading, assistant mask, chat template)
  - Structured output (config.json, training_log.jsonl, metrics.json, episodes/)
- GRPO pipeline end-to-end validation — loss=0.504, mean_r=0.350, correct=1.5/10
  - SFT checkpoint → merge → new LoRA → rollout → GRPO loss → update
  - See `devlog/sft-baseline.md`
- GRPO training infrastructure
  - Gradient checkpointing + CUDA cache clearing solving OOM
  - Stuck detection: auto-advance for non-question events after 5 turns with no progress
  - `scripts/train.py` unified CLI (status/logs/monitor/sft/grpo) + .env auto-loading
  - KL regularization preventing policy collapse (disable_adapter_layers zero-copy ref)
- SFT v2b breakthrough — 8 epochs, loss 1.785→0.674, **first model that can answer correctly**
  - 9/15 writes, 3/10 correct, reward=0.46 (vs v1: 0/10, v2: 0/10)
  - See `devlog/sft-v2b.md`
- Tool interface adaptation (Write/Edit/Read) — _common.py parsing + formatting + new SFT data
- train.py enhancement: remote log tee saving + auto-detect latest log + negative loss regex fix
