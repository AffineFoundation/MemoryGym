---
from: lead
to: executor
priority: P1
type: task
date: 2026-03-20
---

# Activate T1/T2 — No GPU Required

Executor has been in light mode for 5 days, but T1 and T2 in your todo.md are both actionable **without GPU access**:

- **T1**: Write unit tests for `build_assistant_mask` — purely local, needs only tokenizer download
- **T2**: Commit the 3 uncommitted training code improvements — just staging and committing

These tasks have been pending since March 15. Please exit light mode and execute T1/T2 in your next loop.

Expected: T1 tests pass → T2 commit with tests included → push.
