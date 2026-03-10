# EXECUTOR — 执行线程

> 启动方式：`/loop 10m 你是执行线程，读 sessions/EXECUTOR.md 执行当前任务`
>
> 理解意图、设计方案、写代码、跑测试、提交。

## 每次 /loop

```
1. 读本文件，理解「当前任务」的真实意图
2. 系统性思考：任务要解决什么问题？为什么这样做？有没有更好的方案？
3. 设计方案 → 写代码 → 跑测试
4. 代码变更 → python -m pytest tests/ -q
5. 评分/问题变更 → python -m memorygym.bench --seeds 3 --validate
6. 任务完成 → 移入「已完成」，提升下一待办
7. Phase 完成 → 写 devlog/{date}-{n}.md，更新 ROADMAP.md §3/§4
8. 待办空 → 等待新任务写入，不做其他事
```

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

### ⚠️ Phase 52 — mem0 后端评测跑通（最高优先级，阻塞评测线程）

**停下 Phase 56，先完成这个。** 评测者已连续 3 次失败并标记阻塞。

**评测者报告的真实错误**（2 个独立问题，都要解决）：

**错误 1 — `attempt to write a readonly database`**
qdrant 本地 SQLite 在第一批 ingest 后变为只读。后续所有写入失败。这是单进程内的问题，不是并发。可能原因：
- `/tmp/mem0_qdrant_memorygym/` 有上次运行的残留文件/锁
- qdrant SQLite WAL 模式在 `/tmp` 下的行为异常

**修复方向**：在 `Mem0Backend.__init__` 中清理旧数据目录（`shutil.rmtree` if exists），确保每次 eval 从干净状态开始。

**错误 2 — `RuntimeError: mem0 extracted no facts from content`**
retry with "Remember:" prefix 仍然不够，某些结构化文档 mem0 LLM 就是无法提取 facts。

**修复方向**：在 `stream_agent.py` 的 `_execute_tool` memory_store 分支中捕获 RuntimeError，返回错误消息给 agent 而非崩溃：
```python
try:
    entry_id = backend.store(content, memory_id=memory_id)
except RuntimeError as e:
    budget.writes_used -= 1  # Refund the write
    return f"Store failed: {e}", None
```
这样 agent 会收到 "Store failed" 消息继续运行，而不是整个 eval 崩溃。

**执行流程**：
1. 修复两个错误
2. `rm -rf /tmp/mem0_qdrant_*` 清理残留
3. `python -m pytest tests/ -q` 通过
4. **自己跑**：`python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template company --backend mem0`
5. 确认 eval JSON `success: true` 才算完成

### Phase 53 — RL 训练冒烟验证 ✅

**已完成**（详见 devlog/2026-03-10-phase52-53.md）：
- Step 1: SFT 数据生成 ✅（5 prompts, system+user messages, eval_salt varied）
- Step 2: MemoryEnv 交互式 ✅（store +0.3, search found 1, episode done in 20 steps, reward=0.3）
- Step 3: verl/slime adapter ✅（imports OK, compute_score OK, _VERL_AVAILABLE=False expected）
- Step 4: devlog 记录 ✅
- **剩余 gap**：无 GPU 端到端训练。组件代码完整但未在真实梯度更新中验证。

---

以下为代码质量清理任务。

### Phase 54 — 导入风格修正 ✅（已完成，19 处同包导入改为相对导入）

### Phase 55 — 静默异常处理修正 ✅（7 处 except Exception → 具体异常类型）

### Phase 56 — 测试套件精简提效 ✅

10 个 >10s 测试标记 `@pytest.mark.slow`。
- `pytest -m "not slow"`: 320 tests, 88s（3x 加速）
- `pytest`: 330 tests, 250s（完整验证）

### 低优先级 Backlog（训练跑通后再考虑）

- **用户体验修正**：删除 docs/Design.md、填充 LEADERBOARD.md、README 补充、API key 错误信息
- **stream_agent.py 拆分**：972 行，提取事件处理函数降到 ~890 行
- **Promise/Progress Reward**：等简单 shaped reward 在真实训练中验证后，再决定是否需要更复杂的 reward 模型

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
