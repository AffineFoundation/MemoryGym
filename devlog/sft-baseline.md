# SFT Baseline Results

## Config
- Model: Qwen3-4B + LoRA rank=16
- Data: 180 short trajectories (10 entities, 3 questions, 6 templates x 30 seeds)
- Training: 5 epochs, lr=2e-5, batch=4, max_length=8192
- Label masking: assistant-only (37.5% of tokens)
- Loss: 0.22 → 0.06

## Episode Results (lite tier, seed=42, company template)
- Tool calls: 12 (all memory_store)
- Writes: 12/15
- Correct: 0/10
- Reward: 0.07
- Avg gen time: 36.93s/turn (1024 max_new_tokens for Qwen3 think mode)

## Analysis
- SFT successfully teaches **tool-calling format** — model produces `<tool_call>` tags
- Model stores documents on ingest events (12 stores)
- Model does NOT effectively search/answer on question events → 0% accuracy
- Root cause: SFT teaches format (what calls look like) but not strategy (when to search, how to use results)
- The 36.9s/turn is dominated by Qwen3's `<think>` mode consuming tokens before tool calls

## Next Steps
- GRPO training to optimize episode reward (teaches when/how to use tools)
- Consider suppressing `<think>` in SFT data or using a model without thinking mode
- May need to increase training data diversity (more templates, more seeds)
