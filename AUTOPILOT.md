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

战略推导 — Phase 25-27 完成

### 阻塞任务（等待外部资源）
- GPU 端到端训练验证（需 4+ GPU）
- v2 评测数据收集（eval session 负责，见 EVAL_QUEUE.md）

## 待办

（无非阻塞待办。等待 GPU 和 eval 数据。）

---

### Phase 26 — 抗博弈性系统审计（训练者视角红队攻击）

**依据**：MemoryGym 的北极星是"不可作弊"。但如果一个训练者（而非模型自身）阅读了评测代码，理解了问题生成逻辑、评分公式、预算机制，然后通过 RL/SFT **教模型走捷径**，能否在不真正理解内容的情况下获得高分？这是最严重的威胁——因为训练者有代码级知识，等价于白盒攻击。

**本 Phase 不改代码，只做分析。产出红队报告，发现的漏洞作为后续 Phase 修复。**

#### 攻击面 1 — 问题分布可预测性

训练者知道预算分配（base.py:785-800）：
```
corrections=True: retrieval=40%, comprehension=25%, update=20%, abstention=15%
corrections=False: retrieval=50%, comprehension=40%, abstention=10%
```
- **攻击**：训练模型优先存储"容易被 retrieval 问到"的实体
  - retrieval 问题从 `introduced` 列表中采样，是否均匀？是否偏向早期/晚期实体？
  - 如果存在偏向，训练者可教模型只存高概率被问到的实体
- **分析要求**：统计 100 次生成中 retrieval 问题的实体分布，验证均匀性

#### 攻击面 2 — 推理题答案范围可推断

训练者知道每种推理题的答案结构：
- synthesis: 答案 = entity_name + value（最大/最小值实体）
- aggregation: 答案 = 数字（sum/avg）
- ratio: 答案 = 数字（A/B）
- temporal_trend: 答案 = "rising" 或 "falling"（二选一，50% baseline）
- temporal_extreme: 答案 = "1"-"5"（五选一，20% baseline）
- text_match: 答案 = entity_name
- enum_filter: 答案 = entity_name

- **攻击**：对 temporal_trend 随机猜 "rising"/"falling" 可得 50% 正确率
- **攻击**：对 temporal_extreme 猜 "1"（首期）可能偏高（movie 衰减首期最大）
- **分析要求**：计算每种问题类型的 random baseline 和 informed baseline

#### 攻击面 3 — 属性值范围博弈

训练者知道每个模板的 `AttrDef`（min_val, max_val, dtype）：
- **攻击**：不存任何实体，对 retrieval 直接猜中点值
  - 但 smart_guesser < 5% 已验证
- **攻击**：存少量实体但记住属性范围，对 aggregation 猜 `midpoint × entity_count`
- **分析要求**：已有 smart_guesser 策略覆盖，确认是否还有更聪明的猜测策略未被测试

#### 攻击面 4 — 效率轴博弈（Phase 25 修复前）

- **攻击**：只存 3 个高确定性实体（出现在 correction 列表中的），答对 update 题 + retrieval 题 → 高 efficiency
- **分析要求**：计算"最小存储最大效率"策略的理论得分上限

#### 攻击面 5 — 存储内容攻击

训练者知道 `detect_stored_entities()` 需要 name + value：
- **攻击**：存 "EntityA: revenue=500, employees=200 | EntityB: revenue=300" 把多个实体塞进一个 write
  - 这样 15 writes 可存 30+ 实体的信息
- **分析要求**：检查 detect_stored_entities 是否对 multi-entity packing 有防护
- **分析要求**：检查 memory backend 的 search 是否能正确检索 packed 内容

#### 攻击面 6 — correction 时序可预测性

训练者知道 correction 在 stream 的 60% 位置插入：
- **攻击**：训练模型在前 60% 不存储（省预算），等 correction 后再存
- **分析要求**：当前 question 是在 correction 之后生成的，但 retrieval 题是否也覆盖了未被 correct 的实体？

#### 攻击面 7 — 关系结构可推断

训练者知道关系用 seed+9191 生成，`n_rels = max(6, n_entities//3)`：
- **攻击**：给定 seed，训练者可精确预测哪些实体有关系
- **分析要求**：关系问题是否只问有关系的实体？如果是，训练模型优先存有关系的实体

#### 攻击面 8 — abstention 题型可识别

训练者知道 abstention 用虚构实体名（questions.py 中 `_gq_abstention` 生成）：
- **攻击**：训练模型识别"从未见过的实体名"→ 总是 abstain
- **分析要求**：trick_retrieval 是否足够防御？当前仅 2 题/10 题

#### 攻击面 9 — eval_salt 可逆

训练者知道 `_apply_eval_salt()` 的扰动范围（5-15%）：
- **攻击**：如果 salt 是固定的且已知，扰动是可逆的
- **分析要求**：eval_salt 是否对每次 eval 随机？是否包含在 seed 确定性中？

#### 输出要求

- 产出 `devlog/{date}-red-team-audit.md` 红队报告
- 对每个攻击面评估：威胁等级（高/中/低）、理论最大得分、当前防御、建议修复
- 新增 2-3 个 simulation 策略来验证新发现的攻击（如 multi-entity packing strategy, correction-timing strategy）
- 如果发现高威胁漏洞，作为后续独立 Phase 修复

## 已完成

### Phase 27 — 红队发现修复 ✅
1. ~~temporal_trend 5 级答案~~ ✅ → random baseline 50%→20%（strongly rising/slightly rising/flat/slightly falling/strongly falling）
2. ~~eval_salt 官方配置~~ ✅ → TIERS 全部加入 eval_salt: 1
3. ~~Correction 时序随机化~~ ✅ → [40%, 70%] 随机替代固定 60%
4. ~~Multi-entity packing~~ ✅ → 设计决策：合法策略（智能压缩是记忆管理核心技能）
5. ~~simulation 不变量~~ ✅ → 261 tests + 10 seeds × 6 templates ALL PASS

### Phase 26 — 抗博弈性红队审计 ✅
1. ~~9 个攻击面分析~~ ✅ → 2 Medium-High, 2 Medium, 5 Low
2. ~~红队报告~~ ✅ → devlog/2026-03-09-red-team-audit.md
3. **关键发现**：multi-entity packing 可绕过预算（设计决策）、temporal_trend 50% random baseline
4. **结论**：无高威胁漏洞，2 个 medium-high 待后续 Phase 修复

### Phase 25 — 评分有效性系统性修复 ✅
1. ~~评分公式统一~~ ✅ → eval_scorer.py/bench.py/_build_per_seed_axis_scores/test_worlds.py 全部改用 compute_axis_scores()
2. ~~效率轴重设计~~ ✅ → `min(correct_total / write_budget, 1.0)` 替代旧公式
3. ~~Maintenance gate 修复~~ ✅ → eval_scorer.py 改用 stored_count/n_entities（eval_task.py 注入 stored_count）
4. ~~干扰语言标记消除~~ ✅ → 6 模板 ~100 个 distractor 模板去除方向性/标签性语言，distractor 方向随机化
5. ~~simulation 不变量回归~~ ✅ → 261 tests + 10 seeds × 6 templates ALL PASS

### Phase 24 — affinetes SDK 端到端验证 ✅
1. ~~依赖导入~~ ✅ → pip install, Actor import, OpenEnvResponse import
2. ~~Docker build~~ ✅ → Dockerfile 创建, `memorygym:test` 镜像构建成功 (4.7GB)
3. ~~load_env~~ ✅ → 容器启动, reset/state/stop RPC 调用成功
4. ~~task_id 映射~~ ✅ → task_id % 6 = template, task_id // 6 = seed
5. ~~错误场景~~ ✅ → invalid template→ValueError, missing API→error result, unknown episode→done=True

### Phase 23 — 模板差异化自审 ✅
1. ~~检查 1: 问题类型覆盖差异~~ ✅ → comprehension 子类型因属性组合和关系拓扑而异
2. ~~检查 2: list_float 统计指纹~~ ✅ → 6 种不同斜率/自相关模式（slopes [-0.33, +0.32]）
3. ~~检查 3: 领域约束覆盖~~ ✅ → 6/6 模板均有属性间约束
4. ~~检查 4: 独占评测维度~~ ✅ → 每个模板有唯一差异化维度
5. ~~检查 5: 死代码清零~~ ✅ → text_match 修复（bigram 匹配），18/18 competency 均触发
6. ~~审查报告~~ ✅ → devlog/2026-03-09-template-differentiation-audit.md

### Phase 22 — 模板真正差异化 ✅
1. ~~层级死代码移除~~ ✅ → EntitySpec.parent/children + hierarchy_aggregate/lookup 问题类型 + ~90 行代码
2. ~~新问题类型激活~~ ✅ → temporal_trend/extreme, text_match, enum_filter 纳入 comprehension 采样池
3. ~~领域特定 list_float~~ ✅ → 6 种不同时序模式（季节性/影响力曲线/平滑趋势/周期峰值/streak/指数衰减）
4. ~~领域约束补齐~~ ✅ → Company 人均产出、City 人口密度+基础设施、Hospital beds≥icu_beds+staff
5. ~~smart_guesser 修复~~ ✅ → 新 dtype 问题返回 None（无可靠猜测策略）
6. ~~验证~~ ✅ → 261 tests + simulation ALL PASS (5 seeds × 6 templates × 8 strategies)

### Phase 21 — MemoryEnv shaped reward ✅
1. ~~reward_mode 参数~~ ✅ → "binary" (默认) | "shaped"
2. ~~store_quality~~ ✅ → 含实体名 +0.1
3. ~~budget_penalty~~ ✅ → 预算耗尽 -0.05
4. ~~correction_flow~~ ✅ → search→forget→store +0.2
5. ~~测试~~ ✅ → 27 passed (22 existing + 5 new)

### Phase 20 — eval JSON 加入完整对话历史 ✅
1. ~~stream_agent.py trajectory 增强~~ ✅ → turns 加 role+content，system prompt 存为首条记录
2. ~~protocol.py trajectory_to_conversation()~~ ✅ → 共享函数，从 trajectory 重建对话
3. ~~bench.py eval JSON 加 conversation~~ ✅ → extra.conversation 字段
4. ~~env.py 修复 conversation 构建~~ ✅ → 替换为调用共享函数
5. ~~根目录 env.py~~ ✅ → 薄 re-export，affinetes 自动发现
6. ~~测试验证~~ ✅ → 256 passed + simulation ALL PASS (3 seeds)

### Phase 19 — 评测数据重建 ✅
1. ~~归档旧数据~~ ✅ → 49 JSON 移至 eval/archive_v1/ + README.md
2. ~~EVAL_QUEUE.md 重写~~ ✅ → v2 批次 1-6（冒烟→基线→横评→tier 测试）
3. ~~LEADERBOARD.md 重置~~ ✅ → v2 标注，待新数据填充
4. ~~ROADMAP.md §3 更新~~ ✅ → v1 数据标记 archived，v2 数据待填

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
