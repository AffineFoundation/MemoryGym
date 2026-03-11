# EXECUTOR — 执行线程

> 启动方式：`/loop 10m 你是执行线程，读 sessions/EXECUTOR.md 执行当前任务`
>
> 理解意图、设计方案、写代码、跑测试、提交。

## 每次 /loop

```
1. git pull --rebase origin main（同步训练者和其他开发者的变更）
2. 读本文件，理解「当前任务」的真实意图
3. 系统性思考：任务要解决什么问题？为什么这样做？有没有更好的方案？
4. 设计方案 → 写代码 → 跑测试
5. 代码变更 → python -m pytest tests/ -q
6. 评分/问题变更 → python -m memorygym.bench --seeds 3 --validate
7. 任务完成 → 移入「已完成」，提升下一待办
8. Phase 完成 → git add + git commit + git push origin main（**禁止** Co-Authored-By、Generated-by 等元数据行）
9. 待办空 → 等待新任务写入，不做其他事
```

**协作规则**：训练者是另一个独立开发者，会推送代码到同一个远程仓库。每次开发前必须 `git pull --rebase`，提交后必须 `git push`。如果 pull 有冲突，**在理解双方变更意图的基础上解决**，不要盲目接受任何一方。

## 思考规范

**理解意图**：每个任务都有表面需求和深层意图。审计线程写入的任务描述是起点而非终点——你必须理解问题的根因和解决方向，在此基础上设计最优方案。

**独立判断**：如果你在实施中发现任务描述的方案不是最优解，应该采用更好的方案并在 devlog 中说明理由。你是工程师，不是翻译机。

**全局视角**：改动任何代码前，先理解它在整个系统中的角色。读相关模块、理解调用链、考虑副作用。

## 执行规范

**代码任务**：理解意图 → 设计方案 → 改代码 → 跑测试 → 通过才算完成。

**eval 任务**：结果自动保存 `eval/`。API 故障（503/429/timeout）→ 重命名为 `*.503_error.json`，不计入数据表。只有 `success: true` 才是有效数据。一次 loop 只跑一个 eval 任务。

**完成判定**：有明确产出（eval JSON / 测试通过 / 文档更新）才算完成。

**闭环验证**：评分/问题/agent 逻辑变更后，必须跑 eval 验证效果。不能只改代码就宣布完成。

**提交粒度**：一个 Phase 一个 commit。提交时更新 `memorygym/__init__.py` 的 `__version__`（patch 递增）。

**文档同步**：Phase 完成时检查 CLAUDE.md 是否与代码一致。如有漂移，立即修正。

## 卡住时

- **任务级**：当前方案不通 → 换方案或拆解子任务
- **方向级**：连续多个任务无进展 → devlog 记录分析，更新 ROADMAP.md §4

## 新 session 引导

1. 读本文件了解当前任务
2. 读 CLAUDE.md 了解北极星
3. 上下文不足时读 `docs/ROADMAP.md` §0 和最近的 `devlog/`

---

## 当前任务

### Phase 78 — 推理题型全覆盖测试

**依据**：审计 A92 发现无综合测试验证所有 20 种 REASONING_COMPETENCIES 都能生成。如果新增类型但忘记加生成器，无测试捕获。

**目标**：在 `tests/test_worlds.py` 或新文件中添加测试：

1. 验证 `protocol.REASONING_COMPETENCIES` 中每种类型都在 `gen_question()` 分发表中注册
2. 验证每种类型至少在 10 个 seed（标准 tier: 60 entities）中成功生成 ≥1 次
3. 验证 `gen_adaptive_questions()` 产出的 competency 集合覆盖全部 20 种中的 ≥15 种（某些类型需要 corrections/relationships，不一定每次都触发）

**实现提示**：
- 用 `gen_question(world, rng, competency, available, corrections)` 逐类型测试
- counterfactual 和 delta 需传 corrections
- relationship_* 需世界有 relationships（所有 6 个模板都有）
- 如果某类型在 10 seeds 中从未生成成功，说明生成器有 bug 或前置条件过严

#### 验证标准
- `python -m pytest tests/ -q` 全部通过
- 新测试覆盖全部 20 种推理类型

### Phase 82 — adapters env.close() + info 初始化

**依据**：审计 A97 发现 adapters 内存泄漏和变量未绑定。

**问题 1 — env.close() 未调用**：
- `verl_adapter.py` L117: `env = MemoryEnv(...)`, L239 返回前未 close
- `slime_adapter.py` L54: `env = MemoryEnv(...)`, L122 返回前未 close
- `_common.py` `run_episode` 也未 close env
- 每个 episode 泄漏一个 ChromaDB collection，训练时 OOM
- **修复**：在所有 env 使用完毕后调用 `env.close()`。推荐 try/finally 确保异常时也清理。

**问题 2 — `_common.py` `run_episode` L220 info 未初始化**：
- 如果 while 循环不执行，`info` 变量未绑定
- **修复**：在循环前 `info: dict = {}` 初始化

**验证标准**：
- `python -m pytest tests/ -q` 全部通过
- grep 确认 adapters 中 env.close() 存在
- grep 确认 `info` 在循环前初始化

### Phase 81 — SFT 轨迹 JSON 转义修复

**依据**：审计 A96 发现 `training/env.py` generate_sft_trajectory 用 f-string 直接嵌入值，未做 JSON 转义。

**问题点**（3 处）：
1. L137-140: Write content — `f'"arguments": {{"content": "{content}"}}'`
2. L178-181: Edit old_val/new_val — `f'"old_text": "{old_val}"'`
3. L263-264: submit_answer — `f'"answer": "{answer}"'`

**修复方案**：用 `json.dumps(value)` 替代 `f'"{value}"'`，确保 tool_call 内部是合法 JSON。

```python
# Before:
f'"arguments": {{"content": "{content}"}}'
# After:
f'"arguments": {{"content": {json.dumps(content)}}}'
```

**验证标准**：
- `python -m pytest tests/ -q` 全部通过
- 生成一个轨迹，验证 tool_call 块内的 JSON 可被 `json.loads` 解析

### Phase 80 — bench.py 时间计量 + writes_used 传递修复

**依据**：审计 A95 发现 bench.py 两个数据质量 bug。

**Bug 1 — `seed_elapsed` 累积计时**（L251）：
`t0` 在 L173 设置（所有 seed 前），`seed_elapsed = time.time() - t0` 对后续 seed 包含前序时间。
**修复**：在每个 seed 的 model eval 块开头添加 `seed_t0 = time.time()`，`seed_elapsed = time.time() - seed_t0`。

**Bug 2 — `writes_used` 缺失于 result dict**（L287-302）：
model eval result dict 无 `writes_used`，导致 `_build_per_seed_axis_scores`（L559）用 `stored_count` 近似，效率分错误。
**修复**：在 result dict 中添加 `"writes_used": writes_used`，在 `_build_per_seed_axis_scores` 中优先使用 `v.get("writes_used", stored_count)`。

**验证标准**：
- `python -m pytest tests/ -q` 全部通过
- `seed_elapsed` 使用 per-seed 计时
- `_build_per_seed_axis_scores` 使用真实 writes_used

### Phase 79 — stream_agent.py 死代码清理 + write 计数修复

**依据**：审计 A94 发现两个问题。

**问题 1 — 死代码 `_parse_and_execute`**（`stream_agent.py` L160-183）：
定义但从未被调用。其功能已内联到 `_run_tool_loop`（L266-281）。直接删除。

**问题 2 — `stats.writes` 过度计数**（`stream_agent.py` L270-282）：
Write/Edit 在 `execute_tool` 前就计数（`n_w += 1`），被拒绝的写入也被统计。应该在 execute_tool 之后，根据返回结果判断是否实际消费了写入预算。

**修复方案**：
1. 删除 `_parse_and_execute` 函数
2. 在 `_run_tool_loop` 中，将 write 计数移到 `execute_tool` 之后，检查是否实际消费了预算（通过比较 `budget.writes_used` 前后差值）

**验证标准**：
- `python -m pytest tests/ -q` 全部通过
- `_parse_and_execute` 不存在
- stats.writes 只计实际消费的写入

### Phase 77 — events.py contradiction 丢失 bug + 中流问题权重不一致 ✅

**依据**：审计 A90 发现 events.py 事件流生成 2 个问题。

**Bug 1 — Contradiction batch 越界**（`memorygym/worlds/events.py` L233-234）：
```python
# 当前（有 bug）：
contradiction_batch = max(correction_batch + 1, int(n_batches * contra_frac))
# 当 correction_batch 靠近末尾时，contradiction_batch >= n_batches
# 循环 for batch_idx in range(n_batches) 永远不匹配 → contradictions 静默丢弃

# 修复：
contradiction_batch = min(n_batches - 1, max(correction_batch + 1, int(n_batches * contra_frac)))
```
触发条件：lite tier（30 entities, 10/batch → n_batches=3）+ 晚 correction timing（city）。

**Bug 2 — 中流问题忽略 template question_weights**（`memorygym/worlds/events.py` L464-496）：
`_generate_one_question()` 用硬编码概率（retrieval 50%, update 25%, synthesis 15%, abstention 10%），而 `gen_adaptive_questions()` 用 `self.question_weights`（Phase 32 模板定制）。

修复方案：`_generate_one_question()` 读 `self.question_weights`，用 `w["retrieval"]`、`w["update"]`、`w["comprehension"]` 替代硬编码阈值。保留现有的 fallback-to-abstention 逻辑。

#### 验证标准
- `python -m pytest tests/ -q` 全部通过
- `python -m memorygym.bench --seeds 3 --validate` ALL PASS
- 新测试：验证 lite tier（n_entities=30）生成的 stream 包含 contradiction 事件（type=="ingest" with is_contradiction=True）
- 新测试：验证 `_generate_one_question` 对不同 template 产生不同的问题类型分布（hospital 应有更多 update 类型）

### Phase 76 — 3 路径一致性自动化测试

**依据**：审计 A87-A88 发现"修了 2 处漏了第 3 处"模式已发生 4 次（Phase 70 Edit fallback、Phase 71/74 策略泄漏、Phase 75 eval_salt）。根因：bench.py / training/env.py / eval_task.py 三条评测路径有重复参数传递但无自动化一致性检查。

**⚠️ 先完成 Phase 75 Bug 3**：training/env.py L57 的 `eval_salt=1` 变更仍未 commit（`git diff HEAD -- memorygym/training/env.py` 可确认）。先 commit 此变更再开始 Phase 76。

**目标**：在 `tests/` 中添加一致性测试，从源码级验证 3 条路径的关键参数同步。

#### Step 1 — 新建 `tests/test_path_consistency.py`

验证以下一致性：

1. **eval_salt 传递**：bench.py 的 `--official` 模式、eval_task.py 的 `build_worldbench_stream()`、training/env.py 的 `generate_sft_trajectory()` 都应传 `eval_salt=1`。方法：用 AST 解析或 grep 确认 `generate_world` 调用包含 `eval_salt`。

2. **Edit fallback guard**：`_tool_helpers.py` 和 `inspect_task/tools.py` 的 Edit 路径都应包含 `old_text in results[0]["content"]` 检查。方法：读源码文本匹配。

3. **SYSTEM_PROMPT 无策略泄漏**：`stream_agent.py` 和 `eval_task.py` 的 SYSTEM_PROMPT 不应包含 `memory_search the entity`、`Corrections will arrive`、`Handling Corrections` 等策略指导文本。

4. **工具计数一致**：所有路径使用 `MemoryBudget` 且 Edit 失败时 refund（`writes_used -= 1`）。

#### Step 2 — 确保测试通过

```bash
python -m pytest tests/test_path_consistency.py -v
python -m pytest tests/ -q
```

#### 验证标准
- 新测试至少 6 个 test case（上述 4 类 × 覆盖关键路径）
- `python -m pytest tests/ -q` 全部通过
- 测试通过源码分析（AST/文本匹配），不依赖运行时

### Phase 75 — Inspect AI 路径 bug 修复（Edit fallback + eval_salt + dead code）✅ commit `d481f1d`

**依据**：审计 A86 发现 Inspect AI 路径 (`inspect_task/tools.py` + `eval_task.py`) 有 2 个 bug。

**Bug 1 — ChromaDB Edit fallback 缺检查**（`memorygym/inspect_task/tools.py` L95-99）：
Phase 70 修复了 `_tool_helpers.py` 和 `training/env.py`，但遗漏了此文件。
```python
# 当前（有 bug）：
results = backend.search(old_text, top_k=1)
if results:
    backend.forget(results[0]["id"])
    content = results[0]["content"].replace(old_text, new_text, 1)  # no-op 风险
    backend.store(content)
    return f"Edited. ..."

# 修复（与 _tool_helpers.py 一致）：
results = backend.search(old_text, top_k=1)
if results and old_text in results[0]["content"]:
    backend.forget(results[0]["id"])
    content = results[0]["content"].replace(old_text, new_text, 1)
    backend.store(content)
    return f"Edited. ..."
mem_budget.writes_used -= 1
raise ToolError("Text not found in memory.")
```

**Bug 2 — 缺 eval_salt**（`memorygym/worlds/eval_task.py` L172）：
```python
# 当前：
world = tmpl.generate_world(seed, n_entities)
# 修复：
world = tmpl.generate_world(seed, n_entities, eval_salt=1)
```
bench.py 和 env.py 都传 eval_salt，Inspect AI 路径遗漏。

**Bug 3 — SFT trajectory 缺 eval_salt**（`memorygym/training/env.py` L57）：
```python
# 当前：
world = tmpl.generate_world(seed=seed, n_entities=n_entities)
# 修复：
world = tmpl.generate_world(seed=seed, n_entities=n_entities, eval_salt=1)
```
SFT 训练数据使用 eval_salt=0（默认），而所有官方 eval 使用 eval_salt=1。训练数据和评测数据的数值不一致。

**Dead code 清理**（`eval_task.py` L240-242）：
`n_corrections_total` 变量计算后未使用（Phase 71 移除了引用的格式字符串）。删除。

**验证标准**：
- `python -m pytest tests/ -q` 全部通过
- grep 确认 `inspect_task/tools.py` 的 edit 路径包含 `old_text in results[0]["content"]`
- grep 确认 `eval_task.py` 和 `training/env.py generate_sft_trajectory` 包含 `eval_salt`

### Phase 74 — 系统提示词 Correction 策略泄漏修复 ✅ commit `4f120ed`

**依据**：审计 A84 发现 Phase 57（系统提示词中立化）和 Phase 71（事件格式策略提示移除）均遗漏了 SYSTEM_PROMPT 中的 "Handling Corrections" 章节。

**问题**：`stream_agent.py` L65-70 和 `eval_task.py` L55-60 的 SYSTEM_PROMPT 包含：
```
## Critical: Handling Corrections
When you receive a CORRECTION:
1. memory_search the entity name to find existing data
2. Edit the old value to the corrected value
This costs 1 write but ensures your answers reflect current data.
Failing to update = wrong answers on update questions.
```
以及 L72-75 / L65：
```
- Corrections will arrive later and each update costs 1 write
```

`training/env.py` L101 从 stream_agent.py 导入同一 SYSTEM_PROMPT，训练也受影响。

**修复方案**：

1. 移除 "Critical: Handling Corrections" 整个章节（L55-60 / L65-70）——correction 处理策略应由 agent 自主决定
2. 修改 "Memory Budget" 章节中 "Corrections will arrive later" → 移除此行。保留 "Each Write or Edit counts against your budget"
3. 只需改 `stream_agent.py` 和 `eval_task.py`——training 自动通过 import 继承

**注意**：eval_task.py 的 SYSTEM_PROMPT 是独立副本，需要**同步修改**（不是 import）。

**验证标准**：
- `python -m pytest tests/ -q` 全部通过
- `python -m memorygym.bench --seeds 3 --validate` ALL PASS
- grep 确认无 "memory_search the entity" 和 "Corrections will arrive"
- system prompt 仍描述工具用法和 budget 约束（只移除策略指导）

### Phase 72 — Simulation 轴分数不变量验证 ✅ commit `9b0055e`

### Phase 73 — Version bug + Leaderboard composite 排名修复 ✅ commit `bdf919c`

### Phase 73（原文） — Version bug + Leaderboard composite 排名修复

**依据**：审计 A81 发现两个数据质量 bug。

**Bug 1 — hardcoded version**（`memorygym/protocol.py` L196）：
```python
# 当前（错误）：
"memorygym_version": "0.4.0",
# 修复：
from memorygym import __version__
"memorygym_version": __version__,
```
`format_leaderboard_entry()` 输出的 JSON 版本永远是 "0.4.0"，应跟随 `__version__`（当前 0.7.3）。

**Bug 2 — leaderboard 忽略 4-axis composite**（`scripts/leaderboard.py`）：
- `load_results()`（L47）不提取 `extra.per_axis`。添加 `"per_axis": extra.get("per_axis", {})`
- `aggregate_by_model()`（L77）用 `score`（raw accuracy）排名。改为用 `per_axis.composite`（有时 fallback 到 `score`）
- `format_markdown()`（L118）表头增加 Composite 列
- 确保旧 eval JSON（无 per_axis 字段）兼容

**验证标准**：
- `python -m pytest tests/ -q` 全部通过
- `python scripts/leaderboard.py` 输出表格包含 Composite 列且排名按 composite
- 旧格式 eval JSON（无 per_axis）不 crash

---

### Phase 70 — ChromaDB Edit fallback 静默失败修复 ✅ commit `6a87b72`

### Phase 71 — 事件格式策略提示移除 ✅ commit `2849257`

**依据**：审计 A75 发现 Phase 57 只中立化了 system prompt，但 INGEST 事件格式中仍嵌入策略提示。这违反 CLAUDE.md "存储策略本身是被测能力的一部分"。

**问题**：3 处 INGEST 事件格式中包含：
```
Corrections coming: {n_corrections_total}.
   Suggestion: store ≤{suggested} from this batch to reserve budget for corrections.
```
- `memorygym/agents/stream_agent.py` L474-477
- `memorygym/training/env.py` L419-421
- `memorygym/worlds/eval_task.py` L288-290

**影响**：
1. 泄漏 correction 总数 → agent 无需在不确定性下规划预算
2. 显式建议存储数量 → 直接规定存储策略
3. 训练出的模型依赖此提示 → 真实场景无此信息，迁移失效

**修复方案**：

保留 budget 信息（合理），移除 correction 泄漏和策略建议：

```python
# Before:
f"⚠️ Budget: {remaining}/{write_budget} writes remaining. "
f"Entities seen so far: {entities_seen} (more may follow). "
f"Corrections coming: {n_corrections_total}.\n"
f"   Suggestion: store ≤{suggested} from this batch to reserve budget for corrections."

# After:
f"⚠️ Budget: {remaining}/{write_budget} writes remaining. "
f"Entities seen so far: {entities_seen} (more may follow). "
f"Be selective — store what matters most."
```

3 个文件的 budget_ctx 都做相同修改。同时删除 `suggested` 计算逻辑（不再需要）。

**Part B — CORRECTION 事件步骤提示移除**（审计 A78 追加）

`stream_agent.py` L535-541 和 `training/env.py` L425-430 的 CORRECTION 事件中：
```python
# Before:
f"ACTION REQUIRED: You must update your stored memory.\n"
f"1. memory_search \"{entity_name}\"\n"
f"2. Edit the old value to the corrected value\n"

# After:
f"A correction has been issued. Decide how to handle it.\n"
f"Budget: {budget.remaining()} writes remaining."
```
移除原因：
- `memory_search "{entity_name}"` 给出了精确搜索查询 → 应由 agent 自己从 notice 文本提取
- 步骤列表规定了 search→edit 工作流 → 应由 agent 自己决定如何处理
- 保留 "A correction has been issued" 提示（agent 需知道这是修正事件）和 budget 信息

`eval_task.py` 的 CORRECTION 格式也需同步检查。

**验证标准**：
- `python -m pytest tests/ -q` 全部通过（更新 test_training.py L223 的 "Corrections coming:" 断言）
- `python -m memorygym.bench --seeds 3 --validate` ALL PASS
- grep 确认 3 个文件中无 "Corrections coming"、"Suggestion: store"、"ACTION REQUIRED"
- **注意**：此变更会影响 v3 eval 分数（模型失去策略提示可能表现更差），这是预期行为——v4 基线需重新建立

### Phase 72 — Simulation 轴分数不变量验证

**依据**：审计 A79+A80 发现 `run_validation()`（simulation.py L510-610）只检查 raw accuracy 不变量，不验证 4-axis composite scores。`compute_axis_scores` 在 simulation 路径中从未被调用。轴权重或门控逻辑 bug 不会被 `--validate` 捕获。

**修复方案**：在 `run_validation()` 末尾添加轴分数不变量检查。需要在 `simulate_one` 返回值中包含 `stored_count` 和 `writes_used`（已有 `stored`），然后调用 `compute_axis_scores`。

新增检查（每 template）：
```python
# 在 run_validation() 中，用 _build_per_seed_axis_scores 或直接调用 compute_axis_scores
# perfect: composite > 0.90 (允许 maintenance gate 小幅降低)
# guesser: composite == 0.0
# strategic: composite > naive composite
# abstainer: composite < 0.15
```

具体实现：
1. `bench.py` 的 `_build_per_seed_axis_scores` 已能从 simulation 数据计算轴分数——复用此逻辑
2. 在 `run_validation()` 中 import `compute_axis_scores`，对每个策略计算平均 composite
3. 添加 4 条新 invariant check

**验证标准**：
- `python -m pytest tests/ -q` 全部通过
- `python -m memorygym.bench --seeds 3 --validate` ALL PASS（新检查也通过）
- 故意修改 WEIGHTS 为错误值 → 新检查 FAIL

### Phase 70 — ChromaDB Edit fallback 静默失败修复

（内容不变，见下方）

### Phase 71 — 事件格式策略提示移除 ✅

commit `2849257`。INGEST + CORRECTION 策略提示全部移除。346 passed, simulation ALL PASS。

### Phase 69 — MarkdownBackend temporal decay 搜索 ✅

commit `1283a80`。temporal decay 实现完整。

### Phase 69（原文） — MarkdownBackend temporal decay 搜索

**依据**：审计 A73 前沿搜索发现 OpenClaw 官方记忆系统使用 temporal decay（指数衰减）对搜索结果排序——最近写入的记忆分数更高，旧记忆逐渐衰减。这直接影响 maintenance 轴评分：模型更新了记忆后，新版本应优先于旧版本被检索到。

**参考**：https://docs.openclaw.ai/concepts/memory — "Temporal decay applies an exponential multiplier to scores based on the age of each result"

**现状**：`memorygym/memory/backends/markdown_backend.py` 的 `search()` 使用 BM25 + vector 混合搜索，但没有时间因素。每次 `write()` 或 `edit()` 时没有记录时间戳。

**修复方案**：
1. 在 MarkdownBackend 中，为每个写入条目添加单调递增的序号（不需要真实时间戳，用写入计数器即可）
2. search() 结果排序时，对 RRF 分数乘以 decay factor：`score * decay^(max_seq - entry_seq)`，decay ≈ 0.95
3. 这样最新写入的记忆在搜索中排名更高，correction 后的新值优先于旧值

**验证标准**：
- `python -m pytest tests/ -q` 全部通过
- `python -m memorygym.bench --seeds 3 --validate` ALL PASS
- 新测试：写入 entity A（值=100），再 edit A（值=200），search "A" 返回的第一条结果包含 200
- MarkdownBackend eval 分数不降低（maintenance 可能提升）

### Phase 70 — ChromaDB Edit fallback 静默失败修复

**依据**：审计 A74 发现 `_tool_helpers.py` L109-115 的 ChromaDB Edit fallback 路径存在静默失败 bug。

**问题**：当 agent 调用 `Edit(old_text, new_text)` 且后端是 ChromaDB 时，代码用 `backend.search(old_text, top_k=1)` 找最相似条目，然后做 `content.replace(old_text, new_text, 1)`。但 `search()` 返回的是**语义相似**结果，不保证包含 `old_text` 原文。当 `old_text not in results[0]["content"]` 时，`replace()` 是 no-op，条目被 forget + re-store 但内容不变，预算已消耗，返回 "Edited" 报告成功。

**修复方案**：2 处相同模式需同步修复：

1. `memorygym/agents/_tool_helpers.py` L111-115
2. `memorygym/training/env.py` L590-594（完全相同的 search→replace 模式）

在 `replace()` 前加检查：
```python
results = backend.search(old_text, top_k=1)
if results:
    if old_text not in results[0]["content"]:
        budget.writes_used -= 1  # Refund (或 env.py 中 self._writes_used -= 1)
        return "Text not found in memory.", None  # (env.py 中设 info["error"])
    backend.forget(results[0]["id"])
    content = results[0]["content"].replace(old_text, new_text, 1)
    backend.store(content)
    ...
```

**验证标准**：
- `python -m pytest tests/ -q` 全部通过
- 新测试：ChromaDB backend，store "Company A | Revenue: 500"，Edit(old_text="Revenue: 999", new_text="Revenue: 600")，验证：budget 退款、返回 "Text not found"、原条目不变
- env.py 测试：MemoryEnv(backend_type="chromadb")，write entity → edit with wrong old_text → verify writes_used unchanged

---

### Phase 68 — RNG 对齐 + env.py 漂移修复 ✅

bench.py/training/env.py/eval_task.py/env.py 全部用 seed+3333/seed+5555 分离 RNG。env.py 同步修复 eval_salt、backend 选择、version 字段。343 passed。

### Phase 67 — MemoryEnv 资源泄漏修复 ✅

ChromaDB collection + MarkdownBackend tmpdir 清理。`close()` 添加到两个后端 + MemoryEnv.close() + __del__。343 passed, 1 skipped。

### Phase 57 — 系统提示词中立化 ✅

Storage Strategy → Memory Budget（只描述约束，不规定策略）。
测试 314 passed, simulation ALL PASS。eval 待 API 恢复后记录。

### Phase 58 — 移除 mem0 后端 ✅

删除 mem0_backend.py + 18 处引用 + 6 个 mock 测试。
`grep -r "mem0\|Mem0" --include="*.py" memorygym/` = 0 结果。
测试 314 passed, simulation ALL PASS。

---

### Phase 59 — 工具接口 OpenClaw 化（训练迁移核心）

**依据**：红队论证确认，MemoryGym 当前工具接口（memory_store/memory_forget）与 OpenClaw 的记忆接口（Write/Edit 文件 + memory_search）不兼容。训练出的模型在 OpenClaw 上存储执行层完全不迁移。将工具接口改为 OpenClaw 兼容，使 RL 训练出的 action pattern 直接可用于 OpenClaw。

**核心变更**：工具接口从"记忆 API 模式"改为"文件操作模式"

```
当前工具                          改为（= OpenClaw 原生语义）
───────                          ──────────────────────
memory_store(content)      →     Write(content)         追加到 MEMORY.md
memory_forget(id)+store    →     Edit(old_text, new_text) 原地编辑 MEMORY.md
memory_get(id)             →     Read(start_line?, n?)   读取 MEMORY.md
memory_search(query)       →     memory_search(query)    不变
submit_answer(answer)      →     submit_answer(answer)   不变（评测专用）
```

#### Step 1 — 新增 MarkdownBackend（`memorygym/memory/backends/markdown_backend.py`）

```python
class MarkdownBackend:
    """OpenClaw-compatible: Markdown file + hybrid search."""

    def __init__(self, memory_dir):
        self.memory_file = Path(memory_dir) / "MEMORY.md"
        # 向量索引（复用 all-MiniLM-L6-v2）+ BM25 索引
        # Markdown 按 ~400 token chunk，80 token overlap（与 OpenClaw QMD 一致）

    def write(self, content: str) -> str:
        """追加到 MEMORY.md，触发重索引，返回行范围"""

    def edit(self, old_text: str, new_text: str) -> bool:
        """原地编辑 MEMORY.md，触发重索引"""

    def read(self, start_line=None, num_lines=None) -> str:
        """读取 MEMORY.md 内容"""

    def search(self, query: str, top_k=5) -> list[dict]:
        """混合搜索：向量(70%) + BM25(30%) + RRF rerank"""
```

搜索实现：用 `sentence_transformers`（已有依赖）+ `rank_bm25`（新依赖，轻量）做混合搜索，与 OpenClaw QMD 逻辑一致。

#### Step 2 — stream_agent.py 工具接口改造

1. SYSTEM_PROMPT 中的工具描述改为 Write/Edit/Read/memory_search 语义
2. `_KNOWN_TOOLS` 更新为新工具名
3. `_execute_tool` 中各分支适配新工具语义：
   - `Write`：调 `backend.write(content)`，消耗 1 write budget
   - `Edit`：调 `backend.edit(old, new)`，消耗 1 write budget
   - `Read`：调 `backend.read()`，不消耗预算
   - `memory_search`：不变
   - `submit_answer`：不变

#### Step 3 — simulation.py 适配

策略核心逻辑（决定存什么）不变，只改接口调用：
- `backend.store(content)` → `backend.write(content)`
- `backend.forget(id) + backend.store(new)` → `backend.edit(old, new)`
- 9 种策略的选择逻辑保持不变

#### Step 4 — training/env.py 适配

MemoryEnv 的工具接口和 reward 信号适配：
- 工具名映射
- shaped reward：检测 Write 调用（而非 memory_store）
- episode 结束后读 MEMORY.md 评估存储质量

#### Step 5 — bench.py 适配

`--tool-mode` 参数暂不需要。直接用新接口作为默认。ChromaDB 后端仍可用（ChromaDBBackend 实现同样的 write/edit/read/search 接口），但 MarkdownBackend 为默认。

#### Step 6 — 测试

- 新增 MarkdownBackend 单元测试（write/edit/read/search 基本功能）
- 修改现有 simulation 测试适配新接口
- 确认 `python -m memorygym.bench --seeds 3 --validate` 通过

**验证标准**：
- MarkdownBackend 通过 write → search 闭环测试
- 混合搜索（向量 + BM25）recall >= 90%
- simulation 9 种策略不变量全部通过
- `python -m pytest tests/ -q` 全通过

**注意**：这是一个大改动，建议分 2-3 个子 commit：
1. MarkdownBackend 实现 + 测试
2. stream_agent.py + simulation.py 工具接口改造
3. training/env.py + bench.py 适配

---

### Phase 60 — Phase 59 遗留 bug 修复（审计 A40 发现）✅

6/6 bug 全部修复。审计线程直接修复（执行者 7 轮未活动，Bug 2+4 已造成评测数据损失）。
340 passed, simulation ALL PASS。

#### Bug 1（HIGH）— stream_agent.py 工具调用计数遗漏

`_parse_and_execute()`（L313-316）和 `_run_tool_loop()`（L414-417）只统计 `memory_store`，不统计 `Write` 和 `Edit`。导致 trajectory stats 中 write 计数为 0。

修复：
```python
# L313-316
if name in ("Write", "Edit", "memory_store"):
    n_writes += 1
elif name in ("memory_search", "memory_list", "memory_get", "Read"):
    n_searches += 1

# L414-417 同上
```

#### Bug 2（HIGH）— stream_agent.py 修正事件消息仍用旧工具名

L668-675 修正事件的 ACTION REQUIRED 仍说 `memory_search → memory_forget → memory_store`，与 SYSTEM_PROMPT 中的 `search → Edit` 矛盾。模型收到冲突指令。

修复：
```python
f"ACTION REQUIRED: You must update your stored memory.\n"
f"1. memory_search \"{entity_name}\"\n"
f"2. Edit the old value to the corrected value\n"
```

#### Bug 3（HIGH）— adapters/_common.py 缺少新工具名

`_KNOWN_TOOLS`（L24-27）只有旧名（memory_store/forget/get/list），缺 Write/Edit/Read。`format_tool_result()`（L81-112）也没有新工具名分支。RL 训练时 verl/slime adapter 会**静默丢弃**模型的 Write/Edit/Read 调用。

修复：
- L24-27：`_KNOWN_TOOLS` 加入 `"Write", "Edit", "Read"`
- L81-112：`format_tool_result()` 加入 Write/Edit/Read 分支

#### Bug 4（MEDIUM）— bench.py args.backend 未定义

L316 引用 `args.backend`，但 `--backend` 参数已在 Phase 58 删除。运行 `bench.py --model` 会 crash。

修复：L316 改为 `"backend": "chromadb"`（硬编码，或改为检测实际后端类型）

#### Bug 5（LOW）— stream_agent.py 修正检测逻辑

修正成功检测（~L683-698）只检查 `memory_store` 调用，不检查 `Edit` 调用。Edit-based 修正不会被标记为成功。

修复：修正检测增加对 Edit 调用的检查。

#### Bug 6（LOW）— CLAUDE.md 文档漂移（3 处）

Phase 57-59 完成后 CLAUDE.md 有 3 处描述与代码不一致：

1. **L96**："8 种确定性策略" → 实际 9 种（Phase 31 加了 template_expert）
2. **L98**："记忆接口：mem0 兼容（store/search/get/forget/list）。ChromaDB 和 mem0 后端的分数不可直接比较" → mem0 已删除（Phase 58），工具接口改为 Write/Edit/Read（Phase 59）。改为描述当前接口：Write/Edit/Read/memory_search，后端 ChromaDB + MarkdownBackend
3. **L106**："后端（ChromaDB/mem0）" → 改为 "后端（ChromaDB/MarkdownBackend）"

#### 验证标准
- `python -m pytest tests/ -q` 全通过
- `python -m memorygym.bench --seeds 3 --validate` ALL PASS
- `python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template company` 不 crash（验证 Bug 4 修复）
- CLAUDE.md 中无 mem0 引用、策略数量正确

---

### Phase 53 — RL 训练冒烟验证 ✅
### Phase 54 — 导入风格修正 ✅
### Phase 55 — 静默异常处理修正 ✅
### Phase 56 — 测试套件精简提效 ✅

### Phase 61 — stream_agent.py 拆分 ✅

提取 execute_tool + 5 个辅助函数到 `_tool_helpers.py`（159 行）。
stream_agent.py 1017→884 行。340 passed, simulation ALL PASS。v0.6.4。

### Phase 62 — MarkdownBackend 接入 bench.py + training env ✅

bench.py 新增 `--backend` 参数（chromadb/markdown），training/env.py `_make_backend()` 支持 markdown 分支。
340 passed。v0.6.5。

~~**依据**~~：Phase 59 构建了 MarkdownBackend，但系统入口点硬编码 ChromaDB：

1. **bench.py L225-226**：`ChromaDBBackend()` 硬编码，无 `--backend` 参数（Phase 58 删除了）
2. **training/env.py L374-377**：`_make_backend()` 只返回 ChromaDBBackend
3. **training/env.py L523, L553-560**：使用旧 API（store/forget/list），不用新 write/edit/read

MarkdownBackend 有旧 API 兼容层（store/get/forget/list wrapper），所以即使 training env 用旧 API 也能工作，但不是最优路径。

#### Step 1 — bench.py 添加 `--backend` 参数

```python
parser.add_argument("--backend", choices=["chromadb", "markdown"], default="chromadb")
```

L225-226 根据 `args.backend` 选择：
```python
if args.backend == "markdown":
    from memorygym.memory.backends.markdown_backend import MarkdownBackend
    backend_obj = MarkdownBackend()
else:
    from memorygym.memory.backends.chromadb_backend import ChromaDBBackend
    backend_obj = ChromaDBBackend()
```

L316 和 L462 使用 `args.backend` 替代硬编码 `"chromadb"`。

#### Step 2 — training/env.py 支持 MarkdownBackend

`_make_backend()` L374-377 根据 `self._backend_type` 选择：
```python
def _make_backend(self):
    if self._backend_type == "markdown":
        from memorygym.memory.backends.markdown_backend import MarkdownBackend
        return MarkdownBackend()
    from memorygym.memory.backends.chromadb_backend import ChromaDBBackend
    return ChromaDBBackend(...)
```

#### Step 3 — 测试

- 新增测试：MarkdownBackend 通过 bench.py `--backend markdown --seeds 3 --validate` ALL PASS
- 新增测试：MemoryEnv 使用 MarkdownBackend 的 episode 完整执行
- `python -m pytest tests/ -q` 全通过

**验证标准**：
- `python -m memorygym.bench --seeds 3 --validate --backend markdown` ALL PASS
- `python -m memorygym.bench --seeds 3 --validate --backend chromadb` ALL PASS（回归）
- 两种后端的 simulation 分数差异 < 2%

### Phase 63 — training/env.py 工具行为与 eval 对齐 ✅

5 处 train-eval 不一致修复：Write 2000 字符限制、Edit 失败退款、Edit 空 old_text 检查、Read 行范围、Write native write()。
340 passed, simulation ALL PASS。v0.6.5。

~~**依据**~~：审计 A53 对比 `_tool_helpers.py`（eval 路径）和 `training/env.py`（RL 路径）发现 5 处工具行为不一致。

| # | 不一致 | eval 行为 | training 行为 | 影响 |
|---|--------|-----------|---------------|------|
| 1 | Write 字符限制 | >2000 字符被拒（_tool_helpers.py:84） | 无限制（env.py:519-523） | RL agent 学写长内容 → eval 失败 |
| 2 | Edit 失败退款 | 退还 write budget（_tool_helpers.py:106,116） | 不退款（env.py:552-568） | RL agent 高估 Edit 成本 → 避免 Edit |
| 3 | Edit 空 old_text | 返回错误（_tool_helpers.py:98-99） | search("") 返回随机结果 | RL agent 学到空 Edit 可探测 |
| 4 | Read 行范围 | 支持 start_line/num_lines（_tool_helpers.py:121-123） | 只返回全部（env.py:570-573） | RL agent 不学 Read 参数 |
| 5 | Write 方法 | `backend.write()` 优先（_tool_helpers.py:89） | 总用 `store()`（env.py:523） | MarkdownBackend 行为差异 |

#### Step 1 — 修复 Bug 1+2+3（HIGH）

**env.py L519-523**（Write 字符限制）：
```python
content = args.get("content", "")
if not isinstance(content, str):
    content = str(content)
if len(content) > 2000:
    info["error"] = "Content exceeds 2000 character limit"
    # No reward, no budget consumed
else:
    ...  # existing store logic
```

**env.py L552-568**（Edit 退款 + 空 old_text 检查）：
```python
elif tool == "Edit":
    old_text = args.get("old_text", "")
    new_text = args.get("new_text", "")
    if not old_text:
        info["error"] = "old_text is required"
    elif self._writes_used >= self.write_budget:
        info["error"] = "Budget exhausted"
        if shaped:
            reward = -0.05
    else:
        results = self._backend.search(old_text, top_k=1)
        if results:
            self._backend.forget(results[0]["id"])
            updated = results[0]["content"].replace(old_text, new_text, 1)
            self._mem_counter += 1
            mid = f"mem_{self._mem_counter:03d}"
            self._backend.store(updated, memory_id=mid)
            self._writes_used += 1
            info["edited"] = True
            info["remaining"] = self.write_budget - self._writes_used
            if shaped and event_type == "correction":
                reward = 0.5
        else:
            info["edited"] = False
            info["error"] = "Text not found in memory"
            # NO budget consumed — match eval behavior (refund)
```

#### Step 2 — 修复 Bug 4+5（MEDIUM）

**env.py L570-573**（Read 行范围支持）：
```python
elif tool == "Read":
    start = args.get("start_line")
    n = args.get("num_lines")
    if hasattr(self._backend, "read"):
        content = self._backend.read(start_line=start, num_lines=n)
        info["content"] = content if content else ""
    else:
        entries = self._backend.list()
        info["content"] = "\n".join(e["content"] for e in entries) if entries else ""
```

**env.py L523**（Write 使用 native write()）：
```python
if hasattr(self._backend, "write"):
    self._backend.write(content)
else:
    self._backend.store(content, memory_id=mid)
```

#### 验证标准
- `python -m pytest tests/ -q` 全通过
- `python -m memorygym.training smoke` 通过
- 新增测试：Write >2000 chars → error, budget not consumed
- 新增测试：Edit miss → budget not consumed (refund)
- 新增测试：Edit empty old_text → error

### Phase 64 — eval_task.py 工具接口同步 ✅

SYSTEM_PROMPT 替换为 Write/Edit/Read 工具描述（与 stream_agent.py 一致），CORRECTION_TEMPLATE 改为 search→Edit，_count_tool_calls 加入新工具名。340 passed。v0.6.5。

~~**依据**~~：审计 A54 发现 eval_task.py 在 Phase 59 工具接口 OpenClaw 化时被完全遗漏。

| # | 位置 | 问题 |
|---|------|------|
| 1 | SYSTEM_PROMPT L37-42 | 工具列表全是旧名（memory_store/get/forget/list），缺 Write/Edit/Read |
| 2 | SYSTEM_PROMPT L46-48 | 修正流程说 search→forget→store，应改为 search→Edit |
| 3 | SYSTEM_PROMPT L52-57 | Storage Strategy 段仍在（Phase 57 已在 stream_agent.py 删除） |
| 4 | CORRECTION_TEMPLATE L82-84 | 修正流程说 search→forget→store |
| 5 | _count_tool_calls L153 | 只统计 `memory_store`，不统计 Write/Edit |
| 6 | _count_tool_calls L155 | 不统计 Read |

**影响**：通过 `inspect eval eval_task.py` 运行的评测和通过 `bench.py` 的评测用**不同工具接口和提示词**，结果不可比。Inspect AI 用户会得到与 bench.py 用户完全不同的体验。

**修复方案**：

1. **SYSTEM_PROMPT**：复用 `stream_agent.py` 的 `SYSTEM_PROMPT`（`from memorygym.agents.stream_agent import SYSTEM_PROMPT`），与 SFT 和 bench.py 保持一致。如果 eval_task.py 需要 Inspect 特定的提示词格式，至少工具列表和修正流程必须一致。

2. **CORRECTION_TEMPLATE L82-84**：改为：
```
1. memory_search "{entity_name}"
2. Edit the old value to the corrected value
```

3. **_count_tool_calls L153-156**：
```python
if fn in ("Write", "Edit", "memory_store"):
    n_writes += 1
elif fn in ("memory_search", "memory_list", "memory_get", "Read"):
    n_searches += 1
```

**验证标准**：
- `python -m pytest tests/ -q` 全通过
- eval_task.py 中无 `memory_store`/`memory_forget`/`memory_get` 引用（grep 验证）
- SYSTEM_PROMPT 工具列表与 stream_agent.py 一致

### Phase 65 — training/env.py Edit 路径与 eval 对齐 ✅

审计线程直接修复（执行者 10+ 轮无活动，角色越界 #3）。
env.py Edit 加 hasattr(backend, "edit") 检查 + refund 逻辑。stream_agent.py 返回类型 4→5 元素。
340 passed, 1 skipped。v0.6.7。

（原始任务描述保留供参考）

### Phase 65 原始描述 — training/env.py Edit 路径与 eval 对齐

**依据**：审计 A59 发现 training/env.py L551-578 的 Edit 处理不检查 `hasattr(backend, "edit")`，直接走 search+forget+store 回退路径。MarkdownBackend.forget() 设计为返回 False，导致旧内容不删除 + 新内容重复追加。_tool_helpers.py（eval 路径）L103 正确使用 `hasattr(backend, "edit")`。

**具体修复**（env.py L551-578）：

```python
elif tool == "Edit":
    old_text = args.get("old_text", "")
    new_text = args.get("new_text", "")
    if not old_text:
        info["error"] = "old_text is required"
    elif self._writes_used >= self.write_budget:
        info["error"] = "Budget exhausted"
        if shaped:
            reward = -0.05
    else:
        self._writes_used += 1  # Consume budget upfront (match eval)
        if hasattr(self._backend, "edit"):
            ok = self._backend.edit(old_text, new_text)
            if not ok:
                self._writes_used -= 1  # Refund on miss
                info["edited"] = False
                info["error"] = "Text not found in memory"
            else:
                info["edited"] = True
                info["remaining"] = self.write_budget - self._writes_used
                if shaped and event_type == "correction":
                    reward = 0.5
        else:
            # Fallback for ChromaDB: search + forget + store
            results = self._backend.search(old_text, top_k=1)
            if results:
                self._backend.forget(results[0]["id"])
                updated = results[0]["content"].replace(old_text, new_text, 1)
                self._mem_counter += 1
                mid = f"mem_{self._mem_counter:03d}"
                self._backend.store(updated, memory_id=mid)
                info["edited"] = True
                info["remaining"] = self.write_budget - self._writes_used
                if shaped and event_type == "correction":
                    reward = 0.5
            else:
                self._writes_used -= 1  # Refund on miss
                info["edited"] = False
                info["error"] = "Text not found in memory"
```

**附加任务**：
1. 添加 `test_memenv_edit_markdown` 测试（MarkdownBackend 下 Edit 成功/失败行为）
2. 修复 stream_agent.py 返回类型标注（4 元素 → 5 元素）

**验证标准**：
- `python -m pytest tests/ -q` 全通过
- `python -m memorygym.training smoke` 通过

---

### 低优先级 Backlog

- **用户体验修正**：API key 错误信息改善（docs/Design.md 已删除 A65，LEADERBOARD.md 已填充 A58）
- **Promise/Progress Reward**：等简单 shaped reward 在真实训练中验证后，再决定是否需要更复杂的 reward 模型
- **legacy 工具名清理**：移除 _KNOWN_TOOLS 中的 memory_store/memory_forget/memory_get/memory_list（等 v3 评测基线稳定后）

## 已完成

### Phase 51 — MemoryEnv process-based reward 增强 ✅
### Phase 50 — verl_adapter 私有 API 修复 + 适配器健壮性 ✅
### Phase 49 — Inspect AI 完善 + 关键模块测试补全 ✅
### Phase 48 — mem0 后端完善集成 ✅
### Phase 47 — ChromaDB 搜索精度提升 ✅
### Phase 46 — 矛盾问题 GT 格式修复 ✅
### Phase 45 — 版本追踪 + 提交 ✅
### Phase 44 — RL shaped reward 修正 + 修正搜索 tightening ✅
### Phase 43 — 跨 session 修正测试补全 ✅
### Phase 42 — 多会话评测实现 ✅
### Phase 41 — 多会话评测设计 ✅
### Phase 40 — base.py 拆分 + movie.py 补全 ✅
### Phase 39 — 文档同步 + gen_question() API 完整性 ✅
### Phase 38 — 系统提示词修正 + ChromaDB 搜索改进 ✅
### Phase 37 — 新题型采样率提升 ✅
### Phase 36 — 模板策略差异化分析 ✅
### Phase 35 — V2 评测数据收集 ✅
### Phase 34 — 长上下文评测模式 ✅
### Phase 33 — 信息隐藏 + 噪声注入 ✅
### Phase 32 — 实体重要性分化 + 问题分布定制 ✅
### Phase 31 — 模板事件流差异化 ✅
### Phase 30 — 反事实推理 + 多约束过滤题型 ✅
### Phase 29 — 系统级重设计 ✅
### Phase 25-28 — 评分修复 + 红队审计 + 缺陷修复 ✅
### Phase 16-24 — 模板增强 + RL 训练 + SDK 验证 ✅
### Phase 3-15 — 基础系统 + 评测迭代 ✅
