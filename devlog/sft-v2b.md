# SFT v2b Results

## Config
- Model: Qwen3-4B + LoRA rank=32
- Data: 480 trajectories (300 strategic + 180 perfect), old tool names (memory_store)
- Training: 8 epochs, lr=3e-5, batch=1, grad_accum=4, max_length=4096
- Total steps: 960

## Loss Curve
| Epoch | Loss |
|-------|------|
| 0.1 | 1.785 |
| 1.0 | 1.006 |
| 2.0 | 0.756 |
| 3.0 | 0.723 |
| 4.0 | 0.708 |
| 5.0 | 0.710 |
| 6.0 | 0.693 |
| 7.0 | 0.682 |
| 8.0 | 0.674 |

Loss plateaued at ~0.68-0.72 from epoch 3 onwards. The biggest gains are in epochs 0-2.

## Smoke Test (lite tier, seed=42, company template)
- Turns: 21
- Tool calls: 14
- Writes: 9/15
- Correct: **3/10**
- Reward: **0.46**
- Avg gen time: 27.35s/turn

## Comparison
| Metric | SFT v1 (5ep, old data) | SFT v2 (3ep) | SFT v2b (8ep) |
|--------|----------------------|-------------|--------------|
| Loss | 0.06 | 1.007 | 0.674 |
| Writes | 12/15 | 0/15 | 9/15 |
| Correct | 0/10 | 0/10 | 3/10 |
| Reward | 0.07 | 0.00 | 0.46 |

## Analysis
- **First model to answer correctly.** v2b achieves 3/10 correct, proving the SFT data
  can teach both tool format AND strategy.
- **Selective storage**: 9/15 writes shows the model learned from strategic trajectories
  to be selective rather than storing everything (v1) or nothing (v2).
- **Why v2 failed**: 3 epochs only reached loss=1.0, insufficient for the model to learn
  complex multi-turn tool-calling patterns. 8 epochs + higher LR reached 0.67.
- **LoRA rank 32 vs 16**: Higher rank (v2b=32 vs v1=16) may help with complex tasks.

## Next Steps
- Use v2b as base for GRPO v3 (with KL penalty)
- Retrain SFT v3 with new tool names (Write/Edit/Read) using sft_mixed_v2.jsonl
