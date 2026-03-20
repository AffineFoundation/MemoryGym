# Maintenance Axis Bottleneck Analysis (T4)

**Author**: executor | **Date**: 2026-03-20 | **Status**: Complete

## Problem

67% of evaluations score M=0 on the maintenance axis. This is the #1 evaluation discriminability problem.

## Root Causes (ranked by evidence strength)

### RC1: System prompt contradicts correction event message (HIGH confidence)

**The contradiction**:
- System prompt (`stream_agent.py:53`): *"Edit — Update existing content... (costs 1 write)"*
- Correction event message (`stream_agent.py:520`): *"Correction edits do not consume your write budget."*

Models read the system prompt first and internalize "Edit = 1 write cost." When corrections appear later, the special "free edit" note may not override the initial understanding, especially under budget pressure. **Models likely self-censor Edit calls during corrections to conserve budget.**

**Evidence**: The backend actually makes correction Edits free (`_tool_helpers.py:101-126`, `free_edit=True`), so the implementation is correct. The failure is in communication.

### RC2: Maintenance formula double-penalizes low coverage (HIGH confidence)

**Formula** (`protocol.py:145-147`):
```
M = update_accuracy × min(storage_coverage / 0.5, 1.0)
```

If a model stores 20% of entities (typical), the penalty factor = 0.4. Even with 100% update accuracy on stored entities, M maxes at 40%. With realistic 50% update accuracy, M = 0.5 × 0.4 = 20%.

**This is a design choice, not a bug** — it rewards models that store more. But it makes M=0 very easy when coverage is low AND update accuracy is low.

### RC3: Complex multi-step workflow with no demonstration (MEDIUM confidence)

A successful correction requires 4 sequential actions:
1. Read the correction notice
2. `memory_search` for the entity
3. `Edit` with exact `old_text` matching stored content
4. Confirm the edit succeeded

Most LLMs aren't trained on this exact tool-calling pattern. The system prompt describes each tool individually but doesn't demonstrate the correction workflow. Without few-shot examples, models must infer the entire chain.

### RC4: Edit old_text matching is fragile (MEDIUM confidence)

The Edit tool requires exact substring match of `old_text` in stored memory. If the model stored "Revenue: $500M" but tries to edit "revenue: 500M", the edit fails silently. The model gets back "Text not found in memory" but may not retry with corrected text.

**In ChromaDB backend** (`env.py:689-697`), Edit is emulated via search+forget+store — the old_text must appear in the top search result's content.

### RC5: Update questions are indistinguishable from retrieval (LOW — by design)

Update questions use identical wording to retrieval questions (`questions.py:281-297`, same `_q_text`). This is intentional (tests true memory state) but means models can't "prepare" for update questions. They must have actually updated their memory.

## Recommendations

### R1: Fix system prompt contradiction (LOW effort, HIGH impact)

Change Edit description from "costs 1 write" to:
```
**Edit** — Update existing content in your memory file (costs 1 write;
free during correction events):
```

Or restructure to separate the general case from the correction-specific behavior.

### R2: Add correction workflow demonstration (MEDIUM effort, HIGH impact)

Add a brief example to the system prompt or correction event message:
```
When you see a correction:
1. memory_search for the entity name
2. Edit: old_text = the outdated value, new_text = the corrected value
```

This costs ~2 prompt tokens but would dramatically improve correction compliance.

### R3: Consider case-insensitive Edit matching (LOW effort, MEDIUM impact)

Make the Edit old_text match case-insensitive or fuzzy-match in the backend. This would reduce false negatives where the model attempts the right action but fails on formatting.

**Caution**: This changes evaluation behavior — may need simulation invariant re-validation.

### R4: Separate storage coverage penalty from maintenance (DISCUSSION needed)

Current formula conflates "did you store enough?" (already captured by Storage Breadth axis) with "did you update correctly?" Consider:
```
M = update_accuracy  # Pure maintenance
```
Or gate only on whether the *corrected entity* was stored:
```
M = correct_updates / total_corrections_on_stored_entities
```

**Caution**: Changes scoring semantics. Needs lead + paper thread alignment.

### R5: Track correction attempt rate in evaluation logs (LOW effort, diagnostic)

Add logging to record:
- How many correction events the model received
- How many triggered a memory_search
- How many triggered an Edit
- How many Edits succeeded vs failed

This would convert M=0 from a mystery into an actionable diagnostic.

## Not Recommended

- **Making corrections more visually prominent**: Current `[CORRECTION]` formatting is already salient. The issue is action, not awareness.
- **Reducing correction count**: Fewer corrections makes M=0 even more likely (single miss = 0%).
- **Asking correction-specific questions**: Breaks the design principle that questions are wording-neutral.
