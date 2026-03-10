# AUTOPILOT — 执行线程

> 启动方式：`/loop 30m 你是执行线程，读 AUTOPILOT.md 执行当前任务`
>
> 代码执行线程。负责写代码、跑测试、提交。不做战略推导（由 AUDIT.md 线程负责）。

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

## 待办空时

战略推导和系统审计由审计线程（`AUDIT.md`，`/loop 60m`）负责。执行线程不再做战略推导。

待办空时：检查是否有新任务被审计线程写入本文件。如果没有，等待。**不要**自行推导"系统已成熟"的结论——你无法客观审视自己写的代码。

## 卡住时逐级升级

- **任务级**：当前方案不通 → 分析根因，换方案或拆解为更小的子任务
- **方向级**：同一方向连续多个任务无进展 → 在 devlog 记录分析，质疑方向本身是否正确，考虑替代方向，更新 ROADMAP.md §4 优先级

## 新 session 引导

1. 读 `AUTOPILOT.md`（本文件）了解当前任务
2. 读 `CLAUDE.md` 了解北极星和开发规则
3. 上下文不足时读 `docs/ROADMAP.md` §0（当前状态）和最近的 `devlog/` 文件

---

## 当前任务

### Phase 44 — RL shaped reward 修正 + 修正搜索 tightening

**依据**：审计 A14 发现 MemoryEnv 两个训练质量问题。

#### Step 1 — 修正搜索博弈漏洞

training.py `step()` 中（约 507-524 行），当 tool=="memory_search" 且 event_type=="correction" 时：
- 当前：`self._correction_searched = True`（无论搜索结果是否为空）
- 修正：只在搜索返回非空结果时设置 `self._correction_searched = True`
- 即加 `if results:` 条件

#### Step 2 — Shaped reward 比例调整

training.py shaped reward 模式中：
- 当前：store=0.1, correction_flow=0.2, answer=1.0（10:1 比例太大）
- 调整：store=0.3, correction_flow=0.5, answer=1.0（更合理的 gradient signal）
- 确保测试仍然通过（shaped reward 测试可能有具体数值断言）

#### Step 3 — Multi-session MemoryEnv 测试

tests/test_training.py 中新增：
- `test_multi_session_episode`：MemoryEnv(tier="multi") 或 n_sessions=3，验证 reset()/step() 正常跑完
- 验证 session_break 事件在 observation 中出现
- 验证 memory backend 跨 session 持久化

#### 验证标准
- `python -m pytest tests/test_training.py -q` 全量通过
- `python -m pytest tests/ -q` 全量通过
- shaped reward 0% 搜索不再触发 correction_searched

## 已完成

### Phase 43 — 跨 session 修正测试补全 ✅
- test_cross_session_correction: 验证 n_sessions=3 时至少 1 个 correction 跨 session
- 与 Phase 42 一起提交 (commit 9ad38c2)
- 268 tests pass

### Phase 42 — 多会话评测实现 ✅
- events.py: `_insert_session_breaks()` + `generate_stream(n_sessions=)` 参数
- protocol.py: "multi" tier (60e/20q/5c/budget=30/3 sessions)
- simulation.py: `simulate_one_stream(n_sessions=)` 参数透传
- stream_agent.py: session_break 清空对话历史，保留 memory backend
- eval_task.py: session_break 清空消息，插入 session 通知
- training.py: MemoryEnv tier 自动读取 n_sessions，`_format_event` 支持 session_break
- bench.py: `_resolve_config` 返回 n_sessions，multi tier 自动用 stream 模式
- 267 tests pass, stream validation ALL PASS, multi tier validation ALL PASS

### Phase 41 — 多会话评测设计（设计 Phase）✅
- 产出 `devlog/multi-session-design.md`
- 推荐方案 A：stream 中插入 session_break 事件（最小侵入，~180 行变更）
- 现有 4 轴评分足够（多会话让同轴更难），多会话作为新 tier "multi"
- 9 种 simulation 策略无需扩展（session_break 对存储策略透明）
- 兼容 MemoryEnv + 确定性约束

### Phase 40 — base.py 拆分 + movie.py 补全 ✅
- base.py: 1096→728 行，提取 EventGeneratorMixin 到 events.py (388 行)
- movie.py: 补全 question_weights

### Phase 39 — 文档同步 + gen_question() API 完整性 ✅
- CLAUDE.md: 18→20 types, gen_question() dispatch 补全, 问题丢失警告

### Phase 38 — 系统提示词修正 + ChromaDB 搜索改进 ✅
- stream_agent.py: "substring matching" → "semantic search"
- chromadb_backend.py: keyword fallback — embedding top_k + case-insensitive substring scan
- 手动验证通过：精确实体名搜索返回正确结果
- 265 tests pass, simulation ALL PASS

### Phase 37 — 新题型采样率提升 ✅
- Priority slot 机制：counterfactual + multi_constraint 在 shuffle 后移到前面
- 采样率：6 模板 × 10 seeds = 100% 出现率（之前 ~50%）
- 265 tests pass, simulation ALL PASS

### Phase 36 — 模板策略差异化分析 ✅
- 审计发现正确：ratio 调整 (0.65→0.75) 对 simulation 无贡献
- 根因：simulation 无 budget 约束，ratio 越高越好，template-specific tuning 无意义
- 简化 _template_expert_ratio 公式，document 局限性
- 真正差异化在问题生成端（Phase 32 question_weights），不在存储策略端

### Phase 35 — V2 评测数据收集 ✅
- Qwen3.5-397B 6模板 avg=24%: city=34%, research=31%, sport=29%, movie=21%, hospital=18%, company=13%
- 跨模型: Kimi-K2.5=41%(standard), Qwen3.5=13%, Qwen3-235B=14%, MiniMax=0%
- breadth普遍低(0-25%), maintenance最强轴, V2评分分化显著

### Phase 34 — 长上下文评测模式 ✅
- --no-redaction flag：stream_agent.py + eval_task.py + bench.py CLI
- 保留完整对话历史，不做 selective redaction
- 对比"长上下文 vs 工具辅助记忆"的能力差异
- 265 tests, ALL simulation invariants PASS (5 seeds)

### Phase 33 — 信息隐藏 + 噪声注入 ✅
- C1: 隐藏 total_entities（"Entities seen so far: N (more may follow)"），stream_agent + eval_task 同步
- C3: 噪声文档注入 — _generate_noise_doc() 生成含实体名但无属性的干扰文本
- 噪声穿插在 ingest 批次间（~30% 批次），"noise" event type
- stream_agent + eval_task 处理噪声事件（展示给 agent，不需要存储）
- simulation 自动跳过噪声事件（只处理 question 类型）
- 265 tests, ALL simulation invariants PASS

### Phase 32 — 实体重要性分化 + 问题分布定制 ✅
- entity_importance() 方法：关系度数 + 属性极值 + 完整度 → 重要性评分
- question_weights 属性：5 模板自定义问题比例（company/research 偏推理，hospital/sport 偏更新，city 偏检索）
- _weighted_choice() 在 retrieval 问题中按重要性加权选择实体
- simulation _entity_priority_score() 对齐 entity_importance（priority_store 更有效）
- 265 tests, 9 策略 × 6 模板 × 5 seeds ALL PASS

### Phase 31 — 模板事件流差异化 ✅
- correction_rate 属性：hospital=0.15, sport=0.12, company=0.10, research=0.08, movie=0.07, city=0.05
- correction_timing 属性：高频模板早修正(0.3-0.5), 低频模板晚修正(0.5-0.8)
- entities_per_batch 属性（可覆盖，默认 10）
- generate_stream() 使用 self 属性替代硬编码
- 新增 template_expert 策略（priority_store + template-aware ratio）
- 验证：template_expert > strategic (global avg) PASS，9 策略 × 6 模板 × 5 seeds ALL PASS

### Phase 30 — 反事实推理 + 多约束过滤题型 ✅
- counterfactual: GT=correction.old_val, 需要 agent 记住修正前值
- multi_constraint: 2-3 条件组合过滤计数, required_entities≥3 防空集
- simulation: counterfactual 需 applies_updates + stored; smart_guesser 返回 None
- 265 tests, simulation 10 seeds ALL PASS

### Phase 29 — 系统级重设计（设计 Phase）✅
- 3 缺陷验证：策略同质化（部分确认）、推理机械化（确认）、真实场景脱节（部分确认）
- 前沿研究：MemGPT/LoCoMo/MemoryAgentBench/LongMemEval/Mem-alpha/AMemGym 等 10+ 系统
- 设计方案：反事实题(B1) + 多约束(B2) + 模板事件流(A1) + 实体重要性(A3) + 信息隐藏(C1)
- 产出：devlog/2026-03-09-v2-design.md + devlog/2026-03-09-memory-benchmark-research.md

### Phase 28 — 关键缺陷修复 + 测试补全 ✅
- eval_scorer runtime crash 修复（n_total/n_correct 未定义）
- relationship 问题替换补全（fn_map 加入 5 种关系类型）
- questions.py 拆分（685 + 315 行，AdvancedQuestionMixin 独立文件）
- 新增 eval_scorer 运行时测试 + relationship GT 验证测试（263 tests total）

### Phase 27 — 红队发现修复 ✅
- temporal_trend 5 级答案（baseline 50%→20%）、eval_salt 官方配置、correction 时序随机化、multi-entity packing 设计决策

### Phase 26 — 抗博弈性红队审计 ✅
- 9 个攻击面分析（2 Medium-High, 2 Medium, 5 Low），无高威胁漏洞

### Phase 25 — 评分有效性系统性修复 ✅
- 评分公式统一到 compute_axis_scores()、效率轴 correct/budget、maintenance gate stored_count/n_entities、distractor 去标记

### Phase 24 — affinetes SDK 端到端验证 ✅
### Phase 23 — 模板差异化自审 ✅ (5/5 PASS)
### Phase 22 — 模板真正差异化 ✅ (6 模板 × 领域特定 list_float + 约束 + 18 competency)
### Phase 21 — MemoryEnv shaped reward ✅
### Phase 20 — eval JSON 完整对话历史 ✅
### Phase 19 — 评测数据重建 ✅ (v1 归档, v2 队列)
### Phase 18 — 项目全面自审 ✅
### Phase 16-17 — 模板结构分化 + 验证 ✅ (6 dtype, 18 competency)
### Phase 14-15 — 发布准备 + eval 完整性 ✅
### Phase 5-13 — 评测质量迭代 + 工具链 ✅
### Phase 3 — RL 训练闭环 (代码完成，待 GPU 验证)
