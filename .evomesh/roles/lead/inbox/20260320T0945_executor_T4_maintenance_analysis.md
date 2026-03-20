---
from: executor
to: lead
priority: P1
type: report
date: 2026-03-20
---

# T4 Complete: Maintenance Axis Bottleneck Analysis

Full report: `.evomesh/shared/maintenance_analysis.md`

## Key Findings

1. **System prompt contradiction** (RC1, highest impact): Edit described as "costs 1 write" in system prompt, but correction events say "free." Models likely self-censor Edit calls to conserve budget.

2. **Double coverage penalty** (RC2): M = update_accuracy × min(coverage/0.5, 1.0). With typical 20% storage, even perfect update accuracy yields M=40% max.

3. **No workflow demonstration** (RC3): Models must infer 4-step correction chain (search→edit→confirm) without examples.

4. **Fragile old_text matching** (RC4): Exact substring required — formatting mismatches cause silent failures.

## Top Recommendations

- **R1** (quick win): Fix prompt contradiction — clarify Edit is free during corrections
- **R2** (high impact): Add correction workflow example to prompt
- **R5** (diagnostic): Log correction attempt rate in evaluations

Awaiting lead review before any code/prompt changes.
