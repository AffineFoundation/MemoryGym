# SFT v3: Write/Edit/Read Tool Interface

## Config

- Base: Qwen3-4B
- LoRA: rank=32, trainable 66M / 4B (1.6%)
- Data: `sft_mixed_v2.jsonl` (480 trajectories, Write/Edit/Read tools)
- Epochs: 8
- LR: 3e-5 (cosine schedule)
- Batch: 8 GPUs × 1 batch × 8 grad_accum = effective 64
- Max length: 12288
- Total steps: 64

## Loss Curve

| Epoch | Loss   | Grad Norm | LR       |
|-------|--------|-----------|----------|
| 1.3   | 0.1975 | 0.0219    | 2.89e-05 |
| 2.5   | 0.1312 | 0.0122    | 2.37e-05 |
| 3.8   | 0.1026 | 0.0079    | 1.84e-05 |
| 5.0   | 0.0894 | 0.0072    | 1.32e-05 |
| 6.3   | 0.0806 | 0.0063    | 7.89e-06 |
| 7.5   | 0.0760 | 0.0062    | 2.63e-06 |
| Final | 0.1106 (train avg) |  |          |

## Smoke Test

- Writes: 15/15 (all budget used)
- Correct: 0/10
- Reward: 0.00
- Turns: 20

## Analysis

**What worked:**
- Model learned correct `<tool_call>` format with new Write/Edit/Read tool names
- All writes use proper JSON schema `{"name": "Write", "arguments": {"content": ...}}`
- Information extraction from documents is accurate

**What failed:**
- Model only Writes, never does memory_search or submit_answer
- 0/10 questions answered — model doesn't know how to transition from storage to retrieval+answer
- Loss started very low (0.1975 vs v2b's 1.785) suggesting data is "too easy" for masked loss

**Root cause:**
- Training data is dominated by Write tokens (~90% of assistant content)
- memory_search + submit_answer appear only briefly at end of each trajectory
- Model over-indexes on the majority pattern (Write everything)
- Very low loss (0.076) means the model memorized Write patterns but lost base reasoning

**Comparison with v2b:**
| Metric | v2b | v3 |
|--------|-----|-----|
| Tool names | memory_store/forget | Write/Edit/Read |
| Loss start | 1.785 | 0.1975 |
| Loss end | 0.674 | 0.076 |
| Writes | 9 | 15 |
| Correct | 3/10 | 0/10 |
| Reward | 0.46 | 0.00 |

v2b's higher loss paradoxically preserved more base model reasoning, allowing it to answer 3/10 questions.

## Next Steps

- GRPO v3 should use this checkpoint as base — it has correct tool format
- GRPO reward will incentivize search + answer behavior that SFT alone can't teach
- Consider early stopping (fewer epochs) to preserve base reasoning ability
