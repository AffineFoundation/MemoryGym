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

**eval 任务**：默认模型见 CLAUDE.md。结果自动保存到 `eval/` 目录。跑完后将分数记录到 ROADMAP.md §3。**注意**：如果 eval 因 API 故障（503/429/timeout）失败，将结果文件重命名为 `*.503_error.json`，不要计入 ROADMAP.md 数据表。只有 `success: true` 的结果才是有效数据。

**代码任务**：改代码 → 跑测试 → 测试通过才算完成。

**完成判定**：任务有明确产出（eval JSON / 代码通过测试 / 文档已更新）即为完成。无产出不算完成。

**闭环验证**：代码改进（评分/问题/agent 逻辑）后，必须跑一次 eval 验证改进效果。不能只改代码就宣布 Phase 完成——需要有 eval 数据证明改进有效或至少无退化。

**提交粒度**：每个 Phase 独立提交，一个 commit 对应一个 Phase。不合并多个 Phase 到一个 commit。

**文档同步**：每次 Phase 完成时检查 CLAUDE.md 是否与代码实际状态一致（模板数、评分权重、架构模块等）。如有漂移，立即修正。关键决策（框架选型、设计变更）必须同步到 ROADMAP.md §5。

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

待办空，执行战略推导。

### 阻塞任务（等待外部资源）
- GPU 端到端训练验证（需 4+ GPU）
- Phase 16 增强后真实 eval 冒烟测试（已加入 EVAL_QUEUE.md 批次 P17）

## 待办

### Phase 19 — 评测数据重建（归档旧数据 + 全面重测）

**依据**：Phase 16 大幅改变了所有 6 个模板的结构（属性 10→22-24，新增 text/enum/list_float/date，新问题类型），旧版评测数据基于 10 属性模板产出，与当前代码不兼容，分数不可比较。

1. **归档旧评测数据**：
    - `eval/` 目录中所有现有 JSON 移动到 `eval/archive_v1/`
    - 创建 `eval/archive_v1/README.md` 说明：数据基于 Phase 16 前的 10 属性模板，仅供历史参考
    - ROADMAP.md §3 旧数据标注为 `[v1, archived]`
2. **EVAL_QUEUE.md 全面重写**：
    - 清空现有批次（全部基于旧模板）
    - 批次 1：冒烟测试 — 每模板 × 1 seed × Kimi-K2.5（6 任务，验证 agent 能处理新 dtype）
    - 批次 2：新基线 — Kimi-K2.5 全模板 × 3 seeds（18 任务，计算均值±标准差）
    - 批次 3：横评 — Qwen3.5-397B 全模板 × 1 seed（6 任务）
    - 批次 4：补充 — MiniMax + GLM-5 各 company+movie × 1 seed（4 任务）
    - 批次 5：standard tier — Kimi × company × 1 seed
    - 批次 6：hard tier — Kimi × company × 1 seed
3. **LEADERBOARD.md 重置**：
    - 清空旧排行，标注 "v2 — Phase 16 enhanced templates"
    - 新数据到位后重新生成
4. **ROADMAP.md §3 更新**：
    - 新增 v2 数据表
    - 新旧基线定性对比（预期分数下降，属性更多+问题更复杂）

## 已完成

### Phase 18 — 项目全面自审 ✅
1. ~~死代码清理~~ ✅ → 6 处未用导入移除，无死函数/类
2. ~~架构一致性~~ ✅ → cross_category 补入 protocol.py, OFFICIAL_TEMPLATES 加 movie, eval_scorer 改为引用 protocol
3. ~~版本同步~~ ✅ → __init__.py 0.3.0→0.4.0
4. ~~文档同步~~ ✅ → ROADMAP.md §0/§2 更新，CLAUDE.md 架构描述修正
5. ~~审查报告~~ ✅ → devlog/2026-03-09-project-audit.md
6. ~~验证~~ ✅ → 256 tests + simulation ALL PASS

### Phase 17 — 增强模板系统性验证 ✅
1. ~~simulation 全 PASS~~ ✅ → 10 seeds × 6 templates × 8 strategies
2. ~~test_new_dtypes.py~~ ✅ → 7 focused tests
3. ~~EVAL_QUEUE.md 批次 P17~~ ✅

### Phase 16 — 模板结构分化 ✅
1. ~~types.py AttrDef 扩展~~ ✅ → 6 种 dtype (int/float/text/enum/list_float/date), EntitySpec 加 parent/children
2. ~~base.py 框架适配~~ ✅ → _generate_attr_value(), _perturb_value(), _apply_eval_salt() 支持全 dtype
3. ~~questions.py 新问题类型~~ ✅ → 6 种新 competency (temporal_trend/extreme, hierarchy_aggregate/lookup, text_match, enum_filter)
4. ~~eval_scorer + protocol.py 注册~~ ✅ → 20 种 reasoning competency
5. ~~simulation.py 适配~~ ✅ → smart_guesser 处理新 dtype, priority tolerance 放宽
6. ~~company 模板增强~~ ✅ → 10→23 attrs (含 text/enum/date/list_float)
7. ~~research 模板增强~~ ✅ → 10→22 attrs + cites 关系
8. ~~city 模板增强~~ ✅ → 10→23 attrs (含层级结构相关 enum)
9. ~~hospital 模板增强~~ ✅ → 10→23 attrs (含 3 个 text + 2 个 enum)
10. ~~sport 模板增强~~ ✅ → 10→22 attrs (含 3 个 list_float 时间序列)
11. ~~movie 模板增强~~ ✅ → 10→23 attrs (含 director/actor/summary text + studio/rating enum)
12. ~~测试通过~~ ✅ → 249 passed, simulation ALL PASS (3 seeds × 6 templates × 8 strategies)

### Phase 15 — Eval 结果完整性 + 评分复用 ✅
1. ~~per_axis/composite 加入 eval JSON~~ ✅
2. ~~compute_axis_scores() 共享函数~~ ✅ → protocol.py
3. ~~trajectory 加 content 字段~~ ✅ → ingest/correction/question 均含事件内容
4. ~~测试~~ ✅ → 249 passed

### Phase 14 — 公开发布准备 ✅
1. ~~README.md~~ ✅
2. ~~pip install -e . 验证~~ ✅
3. ~~LEADERBOARD.md~~ ✅ → scripts/leaderboard.py 生成，9 个模型排行
4. ~~CLAUDE.md 一致性~~ ✅ → 评分权重统一为 breadth=0.30, reasoning=0.25
5. ~~env.py~~ ✅ → Actor(evaluate/reset/step/state/stop)，含 per-axis 评分 + conversation
6. ~~affinetes_build.py~~ ✅
7. ~~affinetes_example.py~~ ✅

### Phase 13 — 评测数据整理 ✅
1. ~~movie 模板 eval~~ ✅ → Kimi-K2.5 movie seed=0: 55%（首个 movie 结果）
2. ~~sport 补充 eval~~ ✅ → Kimi-K2.5 sport seed=1: 40%
3. ~~ROADMAP.md §3 更新~~ ✅ → 覆盖矩阵增加 movie 列，详细数据表补充 3 行
4. 评测跑分已委托 eval session（EVAL_QUEUE.md 批次 2-6）

### Phase 12 — 评测系统完备性修复 ✅
1. ~~`--backend {chromadb,mem0}` CLI 参数~~ ✅ → bench.py 创建对应 backend 对象并传递
2. ~~eval JSON 加 `backend` 字段~~ ✅
3. ~~`--official` 模式强制 eval_salt~~ ✅ → eval_salt=0 时自动设为 1
4. ~~judge 崩溃处理~~ ✅ → 已有 try/except 捕获 RuntimeError，无需额外修复

### Phase 11 — Maintenance 弱点诊断与系统改进 ✅
1. ~~轨迹分析~~ ✅ → MISS 模式（搜索但不存储）确认为主要失败模式
2. ~~改进 correction 提示~~ ✅ → stream_agent.py + eval_task.py 添加明确 search→forget→store 步骤
3. ~~验证 eval~~ ✅ → Kimi-K2.5 company seed=0: maintenance 0%→33%, corrections 1/5 成功
4. ~~更新 ROADMAP.md~~ ✅ → §3.2 发现 2 已更新

### Phase 10 — 评测覆盖扩展 ✅
1. ~~多模板评测~~ ✅ → Kimi×5模板, MiniMax×5模板, Qwen3.5×3模板
2. ~~多 seed~~ ✅ → Kimi company 4 seeds (38%均值)
3. ~~轨迹~~ ✅ → 新 eval 均含 trajectory
4. ~~ROADMAP.md §3~~ ✅ → 覆盖矩阵 + 5 条发现
5. ~~补充验证~~ ✅ → 503 重命名、§6 验证、Phase 5 确认

### Phase 9 — 评测过程可视化增强 ✅
1. ~~INGEST~~ ✅ → 实体名列表 + 存储/跳过统计
2. ~~CORRECTION~~ ✅ → old→new 值 + 操作链 + 成功检测
3. ~~QUESTION~~ ✅ → 默认显示问题/GT/答案/搜索关键词
4. ~~阶段分隔~~ ✅ → 分隔线 + 阶段汇总
5. ~~预算仪表~~ ✅ → `[████░░░░░░] 6/15 writes` 进度条
6. ~~最终报告~~ ✅ → per-competency + correction 成功率 + 耗时
7. `--quiet` 恢复简洁模式

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
