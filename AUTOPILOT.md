# AUTOPILOT

> 自治演进协议 + 任务队列。每次 `/loop` 读此文件。

## 演进闭环

```
北极星（CLAUDE.md）← 定义目标
  ↓
eval 数据（ROADMAP.md §3）← 衡量差距
  ↓
差距分析 ← 推导最高价值的改进方向
  ↓
执行 ← 写代码、跑测试、跑 eval
  ↓
(回到 eval 数据)
```

## 每次 /loop

```
1. 读本文件，执行当前任务
2. 代码变更 → python -m pytest tests/ -q
3. 评分/问题变更 → python -m memorygym.bench --seeds 3 --validate
4. 任务完成 → 移除完成项，提升下一待办为当前任务
5. Phase 完成 → 写 devlog/{date}-{n}.md，更新 ROADMAP.md §3/§4
6. 待办空 → 战略推导
```

## 任务执行规范

**eval 任务**：默认模型见 CLAUDE.md。结果自动保存到 `eval/` 目录。跑完后将分数记录到 ROADMAP.md §3。

**代码任务**：改代码 → 跑测试 → 测试通过才算完成。

**完成判定**：任务有明确产出（eval JSON / 代码通过测试 / 文档已更新）即为完成。无产出不算完成。

**提交时机**：Phase 级别完成时提交（如 Phase 0 全部 eval 跑完并汇总后）。单个 eval 不需要单独提交。

**长时间任务**：eval 可能耗时较长，一次 loop 只执行一个 eval 任务即可，不必赶进度。

## 战略推导

读 ROADMAP.md → 对照北极星找最大差距 → 设计任务写入本文件 → 在 ROADMAP.md §4 记录推导依据。方向可偏离既有路线，只要有证据支持。战略推导时应研究前沿工作（ROADMAP.md §7 + 主动搜索），从中获取设计启发，研究结果也保存到 devlog/。

## 提示词自优化

每次更新文档时，从长期自我演进的全局角度审视文档本身足够友好合理，是否在拖慢演进——规则冗余则合并，约束过时则删除，流程低效则简化，也可以补充新的合理规则和记忆。文档服务于演进，不是演进服务于文档。如果一条规则从未触发过价值，它就是噪音。

## 卡住时逐级升级

- **任务级**：当前方案不通 → 分析根因，换方案或拆解为更小的子任务
- **方向级**：同一方向连续多个任务无进展 → 在 devlog 记录分析，质疑方向本身是否正确，考虑替代方向，更新 ROADMAP.md §4 优先级

## 新 session 引导

1. 读 `AUTOPILOT.md`（本文件）了解当前任务
2. 读 `CLAUDE.md` 了解北极星和开发规则
3. 上下文不足时读 `docs/ROADMAP.md` §0（当前状态）和最近的 `devlog/` 文件

---

## 当前任务

### Phase 9 — 评测过程可视化增强

目标：让评测过程输出信息完整、可读、有诊断价值，但不冗余。当前输出过于压缩，缺少关键上下文。

改进点：
1. **INGEST 事件**：显示实体名列表（前几个+总数）、agent 实际存了哪些（tool_calls 中 memory_store 的 key）、跳过了哪些、写入效率（stored/seen）
2. **CORRECTION 事件**：显示修正内容摘要（entity.attr: old→new）、agent 操作链（search→forget→store）、是否成功更新了值
3. **QUESTION 事件**：显示完整问题文本、GT 答案、agent 答案、判定结果（不仅在 verbose 模式）、搜索了什么关键词
4. **阶段分隔**：用清晰的分隔线区分 ingest/correction/question 阶段，显示阶段汇总统计
5. **实时预算仪表**：每个事件后显示预算进度条（如 `[████░░░░░░] 6/15 writes`）
6. **最终报告增强**：per-competency 分数、存储覆盖率、correction 成功率、耗时分布

约束：默认开启增强输出，`--quiet` 恢复当前简洁模式。不引入 rich/tqdm 等额外依赖。

### Phase 10 — 评测覆盖扩展

1. 用可用模型跑多模板评测（hospital/research/city/sport），打破 company-only 偏斜
2. 核心模型多 seed（至少 3 个），报告均值±标准差
3. 重跑旧评测带轨迹（用当前代码获取完整轨迹）
4. 更新 STATUS_REPORT.md 和 ROADMAP.md

## 已完成

### Phase 8 — 评测可靠性 + 工具链 ✅
1. ~~Judge 超时机制~~ ✅ → 300s 总超时 + 7 备用模型
2. ~~轨迹分析脚本~~ ✅ → `scripts/analyze_trajectory.py`
3. ~~Leaderboard 生成器~~ ✅ → `scripts/leaderboard.py`（markdown/csv）
4. ~~批量评测运行器~~ ✅ → `scripts/batch_eval.py`（自动跳过已有结果）

### Phase 7 — 一致性修复 + 训练安全 ✅
1. ~~eval_scorer 补全 3 种关系题型~~ ✅ → _REASONING_COMPETENCIES 14 types
2. ~~ROADMAP.md 权重表同步~~ ✅
3. ~~训练 eval_salt 随机化~~ ✅ → MemoryEnv + generate_train_data.py
4. ~~待办区清理~~ ✅

### Phase 6 — 代码质量 + 轨迹分析 ✅
1. ~~test_worlds.py 拆分~~ ✅ → test_worlds.py(699) + test_worlds_features.py(679)
2. ~~轨迹分析~~ ✅ → 发现仅保存统计计数，缺失 tool_calls/results
3. ~~增强轨迹保存~~ ✅ → turns 列表含 tool_calls(name+args) + tool_results

### Phase 5 — 评测质量持续迭代 ✅
1. ~~实体属性异构化~~ ✅ → per-entity 随机激活 5-9 个属性
2. ~~跨类别聚合问题（cross_category）~~ ✅ → top-K 排名后聚合另一属性，需跨多类别实体
3. ~~隐式矛盾（implicit contradictions）~~ ✅ → Contradiction 类 + generate_contradictions()
4. ~~评分权重调整~~ ✅ → breadth 0.25, reasoning 0.30
5. ~~轨迹保存~~ ✅ → *_trajectory.json
6. ~~base.py 拆分~~ ✅ → types.py(125) + questions.py(769) + base.py(802)

### Phase 3 — RL 训练闭环（代码完成，待 GPU 验证）
1. ~~MemoryEnv search 从 substring → embedding~~ ✅
2. ~~GRPO 框架调研与选型~~ ✅ → verl + slime 双适配
3. ~~小模型基线 eval（Qwen3-14B/32B）~~ ✅ → 14B=20%, 32B=30%
4. ~~verl 环境搭建 + MemoryEnv AgentLoopBase 集成~~ ✅ → @register memorygym_agent + config + data gen + reward
5. GPU 端到端训练验证（需 4+ GPU 环境）— 阻塞于硬件

### 验证新功能
1. ~~movie 模板验证~~ ✅
2. ~~standard tier 关系题验证~~ ✅
3. 用可用模型跑 movie 模板 real eval — 阻塞于 API key

### 质量审查与复杂度提升 ✅
1. ~~审查世界模板设计质量~~ ✅ → 修复 movie.py opening_weekend > box_office 约束违反
2. ~~图拓扑方案增加问题复杂度~~ ✅ → 增加关系密度、新增 3 种关系题型、comprehension 重试逻辑

### 战略调研 ✅
1. ~~REDSearcher + agent RL 训练范式调研~~ ✅ → 产出 devlog/2026-03-08-agent-rl-research.md

## 待办

### 阻塞任务（等待外部资源）
- GPU 端到端训练验证（需 4+ GPU）
- Movie 模板 real eval（需 API key）
