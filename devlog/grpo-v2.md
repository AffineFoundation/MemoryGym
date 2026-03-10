# GRPO v2 Experiment Results

## Config
- Model: Qwen3-4B + LoRA rank=16
- Base: SFT v1 checkpoint (sft-qwen3-4b-masked)
- Steps: 10, group-size: 4, groups-per-step: 2 (8 episodes/step)
- Tier: lite, max-turns: 40, max-new-tokens: 256, max-length: 4096
- LR: 5e-6, no KL penalty (kl_coeff=0)
- Reward: shaped (ingest store +0.3, correction flow +0.5, efficiency bonus)
- Infra: gradient checkpointing, CUDA cache clearing, stuck detection

## Step-by-Step Results

| Step | Loss | Mean R | Max R | Correct | Time(s) | Templates |
|------|------|--------|-------|---------|---------|-----------|
| 1 | 0.2815 | 0.388 | 0.600 | 2.9/10 | — | company, research |
| 2 | 0.1783 | 0.309 | 0.600 | 1.8/10 | 2934 | city, research |
| 3 | 0.0456 | 0.202 | 0.400 | 1.1/10 | 3069 | movie (hard) |
| 4 | 0.0885 | 0.336 | 0.600 | 2.4/10 | 2383 | sport |
| 5 | **-0.0671** | 0.331 | 0.600 | 1.9/10 | 2483 | company |
| 6 | -0.0013 | 0.334 | 0.600 | 2.4/10 | 2254 | research, sport |
| 7 | **0.5767** | 0.211 | 0.400 | 1.5/10 | 2600 | sport, movie |
| 8+ | (in progress) | — | — | — | — | movie |

## Key Observations

1. **Policy collapse confirmed**: Loss goes negative at step 5 (-0.067), classic sign of
   policy drifting too far from SFT reference without KL constraint.

2. **Template difficulty varies**: Movie is hardest (mean_r=0.202), sport easiest
   (mean_r=0.336). This suggests curriculum ordering matters.

3. **Reward plateau**: Mean reward stays ~0.3 across steps. No upward trend despite
   loss decreasing → model optimizing loss without improving actual performance.

4. **High variance within groups**: Same seed/template yields 0.1-0.6 reward across
   group members, showing the model has learned some strategies but applies them
   inconsistently.

5. **Writes over-counting**: Some episodes show writes=15 (at budget limit),
   suggesting model stores aggressively but doesn't search/answer effectively.

## Root Cause Analysis

Without KL penalty, GRPO pushes the model toward high-advantage trajectories but
allows unbounded drift. The model learns to maximize the advantage signal within
each group rather than learning generalizable strategies. Loss→0→negative means
the policy gradient is pushing probabilities arbitrarily, losing the SFT-learned
tool-calling structure.

## Next: GRPO v3 (KL penalty)
- Add `--kl-coeff 0.05` to constrain policy drift
- Use SFT v2b checkpoint if it produces a better base
- Expected: loss stays positive, reward trend improves
