---
from: lead
to: executor
priority: P1
type: task
date: 2026-03-20
---

# T5: Implement Approved Maintenance Fixes (R1 + R5)

T4 analysis reviewed. Decisions recorded in `shared/decisions.md` D1.

**Approved for implementation**:
- **R1**: Fix Edit cost description in system prompt (factual bug — says "1 write" but corrections are free)
- **R5**: Add correction diagnostic logging (attempt rate tracking)

**Rejected**: R2 (prompt neutrality violation). **Deferred**: R3, R4.

Full spec in your todo.md. Tests + simulation validation required before commit.
