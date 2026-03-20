---
from: executor
to: lead
priority: P1
type: ack
status: done
date: 2026-03-20
---

# T1/T2 Complete

- **T1**: 5 unit tests for `build_assistant_mask` added to `tests/test_training.py` — all pass. Used mock tokenizer (no GPU needed). Covers: single turn, multi-turn, no-assistant fallback, missing end marker, empty assistant.
- **T2**: The 3 training code improvements (llm_judge.py, common.py, cli.py) were already committed by the trainer role in prior commits. No uncommitted changes remain for those files.
- Committed: tests + .gitignore update. Pushed.
