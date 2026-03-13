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

---

~~### Phase 117 — project 世界模板（项目管理）~~ + ~~117-fix~~ **已合并完成**

**依据**：A228 审计通过红队攻击。OpenClaw 核心使用场景是 agent 管理项目上下文（任务进度、人员分工、截止日期、依赖关系）。现有 8 模板无管理视角覆盖。

**参考**：`memorygym/worlds/company.py`（~490 行，完整模板结构参考）

#### Step 1 — 创建 `memorygym/worlds/project.py`

模板结构（与 company.py 保持一致）：

**命名**：30 prefixes × 20 suffixes（语义无关）
```python
_PREFIXES = ["Phoenix", "Aurora", "Titan", "Nebula", "Horizon", "Catalyst", "Meridian", "Spectra", "Vanguard", "Axiom", "Zenith", "Summit", "Frontier", "Beacon", "Pinnacle", "Apex", "Nexus", "Vertex", "Quantum", "Helix", "Prism", "Nova", "Cobalt", "Onyx", "Argon", "Cipher", "Vector", "Flux", "Ember", "Pulse"]
_SUFFIXES = ["Platform", "Engine", "Portal", "Hub", "Suite", "Gateway", "Framework", "Pipeline", "Toolkit", "Module", "Workspace", "Dashboard", "Orchestrator", "Connector", "Bridge", "Nexus", "Core", "Studio", "Forge", "Matrix"]
```

**分类维度**（类似 company 的 _SECTORS）**：
```python
_METHODOLOGIES = ["Agile", "Waterfall", "Kanban", "Scrum", "SAFe", "Lean", "XP", "Spiral", "DevOps", "Hybrid", "RAD", "FDD"]
```

**23 属性**（6 dtype 全覆盖，参考 codebase/university 的分布）：
```python
# int (8): team_size(2-200), milestone_count(1-50), task_backlog(0-500), closed_tasks(0-2000), sprint_count(1-100), stakeholder_count(1-30), integration_count(0-40), commit_count(0-50000)
# float (7): completion_pct(0-100,%), budget_k(10-5000,$K), burn_rate_k(1-500,$K/mo), velocity_points(1-100), risk_score(0-10), scope_change_pct(0-80,%), customer_nps(-100-100)
# text (2): project_description (text_pool 20 条), key_risk (text_pool 20 条)
# enum (2): status(planning/active/on-hold/completed/cancelled), priority(critical/high/medium/low)
# date (2): start_date(2020-2026), deadline(2024-2027)
# list_float (2): weekly_velocity (list_len=5, sprint 速度趋势: ramp-up 曲线，前期低后期高), monthly_burn (list_len=5, 月度消耗: S 型支出曲线)
```

**注意**：避免与 codebase 重叠 — 不用 open_issues/test_coverage_pct/dependencies

**Inter-Attribute Constraints（至少 4 个）**：
```python
# 1. team_size ↔ burn_rate_k: burn_rate ∈ [team_size × 5, team_size × 30]（人均月成本 $5K-$30K）
# 2. completion_pct ↔ closed_tasks/task_backlog: completion ≈ closed/(closed+backlog) × 100，±15%
# 3. status cascade: status="completed" → completion_pct ∈ [95,100], task_backlog < 5
# 4. budget_k ↔ team_size × sprint_count: 总预算 ≥ team × sprint × 最低人工成本
# 5. scope_change_pct ↔ risk_score: 高 scope_change(>50%) → risk_score > 5
```

**Ratio Pairs（6 个）**：budget_k/team_size, closed_tasks/sprint_count, task_backlog/team_size, burn_rate_k/team_size, commit_count/team_size, velocity_points/team_size

**List_Float 生成模式**：
- weekly_velocity: ramp-up 曲线（团队磨合期低 → 稳定期高），val = base × (0.4 + 0.6 × sigmoid(t))
- monthly_burn: S 型支出（前期采购低 → 中期人力高 → 后期收尾低），val = peak × 4 × t × (1-t)

**correction_rate**: 0.12（项目状态变更频繁）
**question_weights**: retrieval 25%, comprehension 40%, update 20%, abstention 15%（偏重跨项目推理）

- 每个属性需要 `_Q_TEXTS` 问题模板（3-4 变体）
- 每个属性需要 `_SENTENCE_TMPLS` 句型模板（至少 3 种 distractor style: none/temporal/comparative/qualified）
- 4 种 `doc_style`（status_report/executive_summary/standup_notes/risk_assessment）
- `_PROJECT_DESCRIPTIONS`（20 条）+ `_KEY_RISKS`（20 条）
- 所有 `agg_ops=("average",)` 加在百分比/比率类属性上

#### Step 2 — 注册模板

- `memorygym/worlds/__init__.py`：添加 `ProjectWorld` 到 `TEMPLATES` 和 `OFFICIAL_TEMPLATES`
- `memorygym/bench.py`：`--template` choices 增加 `project`

#### Step 3 — 测试

- `tests/test_worlds.py` 自动覆盖所有注册模板，无需额外测试代码
- 运行 `python tests/test_worlds.py` 确认通过
- 运行 `python -m memorygym.bench --seeds 3 --validate` 确认 simulation 不变量

#### 验证标准
- `python tests/test_worlds.py` 全通过
- `python -m memorygym.bench --seeds 3 --validate` 全通过
- project 模板 23 属性：int≥8, float≥7, text=2, enum=2, date=2, list_float=2
- `_Q_TEXTS` 覆盖所有 23 属性（每个 3-4 变体）
- `_SENTENCE_TMPLS` 覆盖所有 23 属性（每个至少 3 种 distractor style）
- inter-attribute constraints ≥ 4 个
- ratio_pairs = 6 个
- list_float 有领域特定生成模式（非纯随机）
- 与 codebase 无属性名重叠

---

### Phase 118 — agentteam 世界模板（多 Agent 协作）

**依据**：A229 审计通过红队攻击。多 agent 编排是 2025-2026 最热 AI 方向，直击 OpenClaw 用户核心场景。与 project（管理视角）和 codebase（代码视角）均不重叠——本模板测运维视角。

**参考**：Phase 117 的 project.py + company.py 结构

#### Step 1 — 创建 `memorygym/worlds/agentteam.py`

**命名**：30 prefixes × 20 suffixes（NATO phonetic + 功能词，语义无关）
```python
_PREFIXES = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Juliet", "Kilo", "Lima", "Mike", "November", "Oscar", "Papa", "Quebec", "Romeo", "Sierra", "Tango", "Uniform", "Victor", "Whiskey", "Xray", "Yankee", "Zulu", "Omega", "Sigma", "Theta", "Epsilon"]
_SUFFIXES = ["Agent", "Worker", "Node", "Unit", "Bot", "Daemon", "Service", "Handler", "Processor", "Executor", "Monitor", "Router", "Dispatcher", "Scheduler", "Planner", "Evaluator", "Analyzer", "Synthesizer", "Coordinator", "Controller"]
```

**分类维度**：
```python
_ROLES = ["coordinator", "worker", "monitor", "router", "planner", "executor", "analyzer", "retriever", "generator", "validator", "debugger", "optimizer"]
```

**23 属性**（6 dtype 全覆盖，参考 codebase 的复杂度水平）：
```python
# int (8): task_count(0-5000), message_count(0-100000), retry_count(0-500), queue_depth(0-1000), uptime_hours(0-8760), active_connections(0-500), tool_call_count(0-10000), context_switches(0-2000)
# float (7): success_rate(0-100,%), response_latency_ms(1-5000,ms), cpu_utilization(0-100,%), task_throughput(0.1-100,/hr), error_rate(0-50,%), coordination_score(0-100), memory_efficiency_pct(10-100,%)
# text (2): specialization (text_pool 20 条), last_error_description (text_pool 20 条)
# enum (2): status(active/idle/error/maintenance), communication_protocol(sync/async/pubsub/streaming)
# date (2): deployed_date(2023-2026), last_heartbeat(2026-01 to 2026-03)
# list_float (2): hourly_throughput (list_len=5, 最近 5 小时: 带负载波动 + 偶发 spike), error_burst (list_len=5, 错误频率趋势: 事故-恢复模式)
```

**Inter-Attribute Constraints（至少 5 个，复杂度对标 codebase）**：
```python
# 1. success_rate ↔ error_rate: success_rate + error_rate ∈ [85, 110]（不完全互补，有 timeout/unknown）
# 2. cpu_utilization ↔ response_latency_ms: high CPU(>80%) → latency > 500ms; low CPU(<20%) → latency < 200ms
# 3. status cascade: status="error" → error_rate > 20%, queue_depth > 100, success_rate < 50%
# 4. task_throughput ↔ active_connections: throughput ∈ [connections × 0.05, connections × 2]
# 5. uptime_hours ↔ retry_count: high uptime(>8000h) + high retry(>200) → memory_efficiency < 50%
# 6. coordination_score ↔ message_count/task_count: 高协调分(>80) → 消息/任务比 > 5
```

**Ratio Pairs（6 个）**：task_count/uptime_hours, message_count/task_count, retry_count/task_count, tool_call_count/task_count, error_rate/cpu_utilization, context_switches/active_connections

**List_Float 生成模式**：
- hourly_throughput: 正弦波负载（日间高/夜间低）+ 20% 概率 burst spike（3-5x），val = base × (0.6 + 0.4 × sin(π × t/4)) + spike
- error_burst: 事故-恢复模式（同 codebase error_rate_trend），spike 位置随机 + exponential decay

**correction_rate**: 0.15（agent 状态变化最频繁）
**question_weights**: retrieval 25%, comprehension 40%, update 20%, abstention 15%（偏重跨 agent 推理 — 负载均衡、故障传播链）

- 每个属性需要 `_Q_TEXTS` 问题模板（3-4 变体）
- 每个属性需要 `_SENTENCE_TMPLS` 句型模板（至少 3 种 distractor style: none/temporal/comparative/qualified）
- 4 种 `doc_style`（health_report/incident_log/capacity_review/orchestration_brief）
- `_SPECIALIZATIONS`（20 条）+ `_ERROR_DESCRIPTIONS`（20 条）
- 所有 `agg_ops=("average",)` 加在百分比/比率类属性上

#### Step 2 — 注册模板（同 Phase 117）

#### Step 3 — 测试（同 Phase 117）

#### 验证标准
- `python tests/test_worlds.py` 全通过
- `python -m memorygym.bench --seeds 3 --validate` 全通过
- agentteam 模板 23 属性：int≥8, float≥7, text=2, enum=2, date=2, list_float=2
- `_Q_TEXTS` 覆盖所有 23 属性（每个 3-4 变体）
- `_SENTENCE_TMPLS` 覆盖所有 23 属性（每个至少 3 种 distractor style）
- inter-attribute constraints ≥ 5 个（复杂度对标 codebase）
- ratio_pairs = 6 个
- list_float 有领域特定生成模式（spike/恢复/负载波动）
- 与 project/codebase 无属性名重叠
- correction_rate = 0.15（最高，agent 状态最动态）

---

## P3 — 评测质量 + 文档（不阻塞训练，可延后）

### 低优先级 Backlog

- ~~README + LEADERBOARD 文档同步（A155）~~ → **Phase 107 已派发**
- **用户体验修正**：API key 错误信息改善（docs/Design.md 已删除 A65，LEADERBOARD.md 已填充 A58）
- **Promise/Progress Reward**：等简单 shaped reward 在真实训练中验证后，再决定是否需要更复杂的 reward 模型
- **legacy 工具名清理**：移除 _KNOWN_TOOLS 中的 memory_store/memory_forget/memory_get/memory_list（等 v3 评测基线稳定后）

## 已完成

### Phase 131 — 训练 CLI help + API 错误友好化（v0.10.34） ✅
### Phase 130 — Agent Runner 鲁棒性修复（empty choices guard + edit refund guard, v0.10.33） ✅
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
