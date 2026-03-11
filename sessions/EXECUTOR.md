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

> **P1+P2 完成，P3 进行中。** 按优先级排序（A118 审计重整）。

---

## P2 — RL 训练质量 ✅

### Phase 92 — RL reward 对齐 4 轴评分 + Edit shaped reward 验证 ✅

get_verifiable_reward() 改用 compute_axis_scores() composite。Edit shaped reward 验证 new_val 正确性（+0.5 正确 / +0.1 错误）。+2 tests。

---

## P3 — 评测质量 + 文档（不阻塞训练，可延后）

### 低优先级 Backlog

- **用户体验修正**：API key 错误信息改善（docs/Design.md 已删除 A65，LEADERBOARD.md 已填充 A58）
- **Promise/Progress Reward**：等简单 shaped reward 在真实训练中验证后，再决定是否需要更复杂的 reward 模型
- **legacy 工具名清理**：移除 _KNOWN_TOOLS 中的 memory_store/memory_forget/memory_get/memory_list（等 v3 评测基线稳定后）

## 已完成

### Phase 88 — docs/ROADMAP.md 同步更新 ✅
### Phase 93 — CLI UX 修复：README tier 默认值 + help 补全 ✅
### Phase 91 — 问题措辞泄漏修复（temporal_trend + comparison） ✅
### Phase 92 — RL reward 对齐 4 轴评分 + Edit shaped reward ✅
### Phase 89+90 — SFT 轨迹 budget 超支 + json.dumps ✅
### Phase 87 — SFT 轨迹连续 user 消息合并 ✅
### Phase 86 — test_path_consistency 扩展 + flaky test 修复 ✅
### Phase 85 — eval_task.py 默认值 + pyproject.toml 版本同步 ✅
### Phase 84 — Inspect AI 工具名不匹配修复 ✅
### Phase 83 — MarkdownBackend recall 基准测试 ✅
### Phase 81+82 — 训练基础設施修复 ✅
### Phase 79+80 — 数据质量修复 ✅
### Phase 78 — 推理题型全覆盖测试 ✅
### Phase 77 — events.py contradiction 丢失 bug + 中流问题权重不一致 ✅
### Phase 76 — 3 路径一致性自动化测试 ✅
### Phase 75 — Inspect AI 路径 bug 修复 ✅
### Phase 74 — 系统提示词 Correction 策略泄漏修复 ✅
### Phase 73 — Version bug + Leaderboard composite 排名修复 ✅
### Phase 72 — Simulation 轴分数不变量验证 ✅
### Phase 71 — 事件格式策略提示移除 ✅
### Phase 70 — ChromaDB Edit fallback 静默失败修复 ✅
### Phase 69 — MarkdownBackend temporal decay 搜索 ✅
### Phase 68 — RNG 对齐 + env.py 漂移修复 ✅
### Phase 67 — MemoryEnv 资源泄漏修复 ✅
### Phase 65 — training/env.py Edit 路径与 eval 对齐 ✅
### Phase 64 — eval_task.py 工具接口同步 ✅
### Phase 63 — training/env.py 工具行为与 eval 对齐 ✅
### Phase 62 — MarkdownBackend 接入 bench.py + training env ✅
### Phase 61 — stream_agent.py 拆分 ✅
### Phase 60 — Phase 59 遗留 bug 修复 ✅
### Phase 59 — 工具接口 OpenClaw 化 ✅
### Phase 58 — 移除 mem0 后端 ✅
### Phase 57 — 系统提示词中立化 ✅
### Phase 53-56 — RL 训练冒烟 + 导入风格 + 静默异常 + 测试精简 ✅
### Phase 51 — MemoryEnv process-based reward 增强 ✅
### Phase 50 — verl_adapter 私有 API 修复 + 适配器健壮性 ✅
### Phase 49 — Inspect AI 完善 + 关键模块测试补全 ✅
### Phase 3-48 — 基础系统 → 评测迭代 → 模板增强 → RL 训练 ✅
