# GRPO v3: KL Regularization + Schulman k3 Estimator

## Config

- Base: Qwen3-4B + SFT v3 LoRA (sft-v3-write-edit-read)
- New LoRA: rank=32 on top of merged SFT
- KL: Schulman k3 `(r-1) - log(r)`, coeff=0.05
- Steps: 10, G=4, 2 groups/step = 8 episodes/step
- Max turns: 40, max new tokens: 256, max length: 4096
- LR: 5e-6, tier: lite, all 6 templates

## Step-by-Step Results

| Step | Loss    | Mean R | Notes |
|------|---------|--------|-------|
| 1    | 0.1498  | 0.070  | One outlier: 5/10 correct (movie) |
| 2    | -0.1063 | 0.058  | Some episodes answer without writing |
| 3    | 0.0000  | 0.000  | Collapse on movie template |
| 4    | -0.1157 | 0.105  | Sport template, some correct |
| 5    | 0.4030  | 0.074  | Company: best episode 3/10 with 11 writes |
| 6    | 0.0134  | 0.123  | Research 4/10 without writes |
| 7    | 0.0545  | 0.067  | Mixed |
| 8    | 0.0359  | 0.189  | Hospital 4/10, best step |
| 9    | 0.0003  | 0.094  | Hospital collapse, city recovers |
| 10   | —       | —      | (summary only) |

**Summary**: reward 0→0.558, correct 0→5/10, loss 0.1498→0.0003

## Key Observations

1. **KL penalty works**: No policy collapse (v2 collapsed at step 5). Loss stays bounded.
2. **Model learns to answer without writing**: Most high-reward episodes have writes=0.
   The model is "cheating" by extracting answers from the document context directly,
   bypassing the memory system entirely.
3. **Variance is very high**: Same template can score 0/10 or 5/10 across group members.
4. **Template sensitivity**: Hospital/city tend to score higher; movie is hardest.

## Diagnosis: Answering Without Memory

The model discovered it can sometimes answer questions from the document text still
in context, without needing to Write→Search→Answer. This is a valid strategy for
short contexts but won't generalize to real use cases.

Root cause: `max_length=4096` means early documents may still be in context window
when questions are asked. The model reads the question, reasons from context, and
submits answers — no memory needed.

## Next Steps

- Increase context pressure: more entities or shorter max_length to force memory usage
- Track writes vs correct correlation — are writes=0 episodes genuinely answering from memory?
- Consider adding a write_count component to reward to encourage storage behavior
- Step-wise reward (F4) could help: reward Write actions that later enable correct answers
