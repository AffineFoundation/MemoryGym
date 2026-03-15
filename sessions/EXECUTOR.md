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
5. 代码变更 → python -m pytest tests/ -q -m "not slow"（快速测试 ~60s；提交前跑全量 python -m pytest tests/ -q）
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

### Phase 135 — GRPO 代码路径修复（training/cli.py 1 BLOCKER + 5 HIGH）

**依据**：审计 A520 发现 `training/cli.py` GRPO 实现存在 1 个 BLOCKER 和 5 个 HIGH 级别 bug，解释了 Trainer GRPO smoke test 无法产出结果的原因。这些 bug 阻塞了 NeurIPS 论文训练实验数据的产出。

**意图**：修复 GRPO 训练管线中的梯度流、损失计算、资源管理问题，使 RL 训练能正常进行。

#### Step 1 — 修复零损失 fallback（BLOCKER）

**文件**：`memorygym/training/cli.py:648-650`

**问题**：当所有 trajectory 的 advantage ≈ 0 被跳过后，`total_loss = torch.tensor(0.0, requires_grad=True)` 创建无计算图的张量。`loss.backward()` 产生零梯度，模型不训练。

**修复**：返回一个明确标记（如 `None`），让调用方跳过该 step 的 `backward()` + `optimizer.step()`。或者用 `0 * model_param.sum()` 创建连接到模型的零损失（但这也不好，浪费计算）。推荐返回 `None` 并在调用方处理。同时添加 warning 日志：`"GRPO step skipped: all trajectories filtered (advantage ≈ 0)"`。

#### Step 2 — 为静默跳过添加 warning（HIGH）

**文件**：`memorygym/training/cli.py:582-583`

**问题**：`if abs(advantage) < 1e-6: continue` 无任何日志。大量 trajectory 可能被静默跳过，Trainer 看不到原因。

**修复**：添加 `logger.warning("Skipping trajectory with near-zero advantage: %.6f", advantage)`。在函数末尾统计跳过数量并 warning：`"GRPO loss: %d/%d trajectories used (skipped %d with |advantage| < 1e-6)"` 。

#### Step 3 — 修复 KL 散度计算（HIGH）

**文件**：`memorygym/training/cli.py:624-627`

**问题**：`ratio = torch.exp(mean_log_ratio)` 在 sequence-level 做 exp，等价于几何均值。然后用这个 ratio 做 clipping，相当于对整个序列的"平均 ratio"做 PPO clipping，而非 per-token 操作。

**修复方案（二选一，推荐 A）**：
- **A（per-token ratio, 更接近 GRPO）**：`ratio = torch.exp(log_ratio)` per-token，clipping 在 per-token 上做，然后 `pg_loss = -(torch.min(surr1, surr2) * mask).sum() / n_tokens`
- **B（保持 sequence-level 但修正 KL）**：KL penalty 直接用 `mean_log_ratio`（已是 E[log(π/π_ref)]），不需要再 exp

注意：如果选 A，需要同时修改 cli.py:629-633 的 clipping 逻辑为 per-token。

#### Step 4 — 修复 loss 归一化一致性（HIGH）

**文件**：`memorygym/training/cli.py:651-652`

**问题**：`n_valid > 1` 时 `total_loss / n_valid`，但 `n_valid == 1` 时不除。

**修复**：统一为 `total_loss / n_valid`（当 n_valid >= 1 时）。

#### Step 5 — 移除内循环 empty_cache + MemoryEnv 资源泄漏（HIGH + MEDIUM）

**文件**：`memorygym/training/cli.py:585, 470`

**修复 1**：移除 `torch.cuda.empty_cache()`（:585），或移到外层 step 循环。内循环调用导致 3-5x 性能下降。

**修复 2**：`_run_episode`（:470）中 `env = MemoryEnv(...)` 后加 `try/finally: env.close()`，防止异常时 ChromaDB 资源泄漏。

#### 验证标准

1. `python -m pytest tests/ -q -m "not slow"` — 全部通过
2. `python -m pytest tests/test_training*.py -q` — 训练相关测试通过
3. 手动验证：`_compute_grpo_loss` 在 advantage 全为 0 时返回 `None`（非 requires_grad=True 的零张量）
4. 手动验证：`_compute_grpo_loss` 日志输出跳过 trajectory 的 warning
5. 版本号 patch 递增

---

## Backlog

- **legacy 工具名清理**：移除 _KNOWN_TOOLS 中的 memory_store/memory_forget/memory_get/memory_list（等 v3 评测基线稳定后）

## 已完成

### Phase 132 — validators.py regex 修复：leading-dot decimals（v0.10.35） ✅
### Phase 131 — 训练 CLI help + API 错误友好化（v0.10.34） ✅
### Phase 130 — Agent Runner 鲁棒性修复（empty choices guard + edit refund guard, v0.10.33） ✅
### Phase 134 — 训练模块 + bench.py 鲁棒性修复（env.py 越界 + adapters info 初始化 + bench.py except + client try/finally） ✅
### Phase 129 — 资源泄漏修复（OpenAI clients close + bench.py try/finally + MarkdownBackend __del__） ✅
### Phase 128 — LEADERBOARD/README 刷新（173 evals）+ pyproject.toml 版本同步 ✅
### Phase 127 — test_worlds.py 补齐 4 缺失模板测试覆盖（6→10 模板） ✅
### Phase 126 — Inspect AI correction Edit 免费 + 提示词同步（两路径行为一致） ✅
### Phase 125 — task_id 稳定映射（TEMPLATE_REGISTRY + _parse_task_id 重写） ✅
### Phase 124 — 并发 & Long-Run 资源泄漏修复（MarkdownBackend/ChromaDB/bench.py close） ✅
### Phase 123 — LEADERBOARD.md 刷新（150 evals, 10 模板，Qwen3-235B #1） ✅
### Phase 122 — counterfactual validator 路由修复 + cross_domain dead code 清理 ✅
### Phase 121 — eval_salt 约束一致性修复（enforce_constraints 钩子，10 模板全覆盖） ✅
### Phase 120 — agentteam C1 约束修复（success+error ∈ [85,110] 违反率 40%→0%） ✅
### Phase 119 — README 文档同步（10 模板 + Training quickstart + CLAUDE.md 同步） ✅
### Phase 118 — agentteam 世界模板（第 10 个模板，23 attrs，6 constraints，correction_rate=0.15） ✅
### Phase 117 — project 世界模板 + 117-fix 质量修复（第 9 个模板，23 attrs，4 constraints） ✅
### Phase 116 — 战略文档同步（ROADMAP.md + STATUS_REPORT.md，Phase 94-114 补全） ✅
### Phase 114 — README 排行榜数据同步（123 evals, Composite 列） ✅
### Phase 113 — stdout 评分表 axis scores 一致 + smart_guesser<=5% + trajectory post-judge ✅
### Phase 112 — Correction Edit 免预算 + 消息增强（maintenance 轴修复） ✅
### Phase 111 — LEADERBOARD 刷新 (121 evals) + stream_agent context overflow 优雅 abstain ✅
### Phase 110 — validators.py 推理题型路由补全（8 个未路由题型） ✅
### Phase 109 — LEADERBOARD.md 4 轴补全 + leaderboard.py Reasoning/Efficiency 列 ✅
### Phase 108 — CLI UX 打磨（表格对齐/API 前置检查/choices 显示/HF 噪音） ✅
### Phase 107 — 文档同步：README/LEADERBOARD/pyproject.toml/EVALUATOR ✅
### Phase 106 — relationship_hop/chain validator dispatch + GT 格式化解析 ✅
### Phase 104 — SFT 轨迹 correction 时序修复 + Edit 覆盖提升 ✅
### Phase 102 — Correction 追踪误报修复 ✅
### Phase 101 — university + codebase 加入 OFFICIAL_TEMPLATES ✅
### Phase 100 — SFT 轨迹 _compact_document 使用原始值修复 ✅
### Phase 99 — generate_stream ingest 文档渲染时序修复 ✅
### Phase 98 — Correction 引导消息增强 ✅
### Phase 97 — Codebase 世界模板（第 8 个领域） ✅
### Phase 96 — University 模板 Constraint 4 逻辑修复 ✅
### Phase 94 — 死代码清理 ✅
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
