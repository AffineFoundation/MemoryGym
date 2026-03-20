# 技术决策记录

## D1 | 2026-03-20 | Maintenance Axis Remediation Plan

**Context**: T4 analysis found 5 root causes for 67% M=0. Lead reviewed against project design principles.

### Approved

- **R1: Fix system prompt Edit cost contradiction** — System prompt says "Edit costs 1 write" but corrections make Edit free. This is a factual bug in tool documentation. Prompt neutrality compliant (describes tool behavior, not strategy).
- **R5: Add correction diagnostic logging** — Track correction attempt rates (search, edit, success/fail) in evaluations. Pure diagnostic.

### Rejected

- **R2: Add correction workflow demonstration to prompt** — Violates "Prompt neutrality" (CLAUDE.md): system prompts describe tasks and tools, not prescribe strategies. The correction workflow IS the memory management capability being tested. Teaching it in the prompt converts capability evaluation into instruction-following.

### Deferred

- **R3: Case-insensitive Edit matching** — Changes evaluation semantics. Needs simulation invariant re-validation. Could mask genuine retrieval accuracy issues.
- **R4: Separate coverage penalty from maintenance formula** — Valid concern about double-counting with Storage Breadth axis. Current formula: `M = update_accuracy × min(coverage/0.5, 1.0)`. Alternative: `M = correct_updates / corrections_on_stored_entities`. Needs paper thread alignment before changing reported numbers.
