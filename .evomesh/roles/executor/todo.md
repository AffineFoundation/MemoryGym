# executor — 待办任务

## T3: Deduplicate Edit reward logic in env.py (优先级: LOW)

**背景**: `env.py` Edit tool handler (lines ~669-712) has identical reward logic in two branches (hasattr path and fallback path). 27 lines duplicated.

**目标**: Extract shared reward logic into a helper method.

**约束**: Must not change behavior. Run existing tests after.
