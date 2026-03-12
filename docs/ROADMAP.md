# MemoryGym Roadmap

> 项目状态、证据、优先级、架构、技术决策的权威文档。
> 由自治演进协议持续维护。

**最后更新**: 2026-03-12

---

## 0. 当前状态

> 新 session 先看这里 + `sessions/EXECUTOR.md`。上下文不足时可读最近的 devlog 文件。

**当前焦点**: RL 训练闭环（SFT v6 就绪，GRPO v3 代码就绪，GPU SSH 阻塞 9+ 天）

**最大差距**: GPU SSH 不可达，RL 训练无法执行。评测侧 breadth 10.8% 是级联瓶颈。

**已完成**:
- Phase 0-28: 基础系统、模板增强、评分统一、红队审计 ✅
- Phase 29-33: V2 系统重设计 — 反事实/多约束题型、模板事件流差异化、实体重要性、噪声注入 ✅
- Phase 34-46: 长上下文模式、多会话评测、RL shaped reward、版本追踪 ✅
- Phase 47-50: ChromaDB 搜索精度、mem0 集成、Inspect AI、adapter 完善 ✅
- Phase 51: MemoryEnv process-based reward 增强 ✅
- Phase 57-58: 系统提示词中立化 + mem0 后端移除 ✅
- Phase 59-61: 工具接口 OpenClaw 化（Write/Edit/Read）+ bug 修复 ✅
- Phase 62: MarkdownBackend 接入 bench.py + training env ✅
- Phase 63-65: training/env.py 与 eval 对齐 + eval_task.py 同步 + Edit 修复 ✅
- Phase 67-76: 资源泄漏、RNG 对齐、temporal decay、Edit fallback、事件格式、Simulation 验证、版本 bug、系统提示词、Inspect AI 路径、3 路径一致性测试 ✅
- Phase 77-86: contradiction 修复、推理题型全覆盖、数据质量、训练基础设施、MarkdownBackend recall、Inspect AI 工具名、eval_task.py 默认值、test_path_consistency ✅
- Phase 87-93: SFT 连续消息合并、budget 超支修复、问题措辞泄漏修复、RL reward 对齐 4 轴评分、CLI UX 修复 ✅
- Phase 94: 死代码清理 ✅
- Phase 96-101: University/Codebase 模板（6→8 模板）、constraint 修复 ✅
- Phase 102-104: Correction 追踪误报修复、SFT 轨迹修复、Edit 覆盖提升 ✅
- Phase 106-109: validator dispatch 补全、文档同步、CLI UX 打磨、LEADERBOARD 4 轴 ✅
- Phase 110-114: validators 推理题型路由、context overflow abstain、**Correction Edit 免预算（Phase 112，最大影响变更）**、stdout 评分一致、README 同步 ✅
- 8 模板 × 21-23 attrs × 6 dtypes × 20 reasoning competencies
- 437 tests, 9 simulation strategies ALL PASS（v0.10.18）
- 123 real evaluations, 5 models — Qwen3.5=18.0%, Qwen3-235B=17.7%, MiniMax=15.2%, Kimi=15.2%, GLM-5=10.2%（Composite）
- 2 backends: ChromaDB（embedding）+ MarkdownBackend（BM25+向量混合搜索）
- Phase 112 impact: composite +3.6pp, maintenance +5.6pp（16 post-112 evals，M>0% 从 ~20% 提升到 70%）
- SFT v6 数据就绪：160 perfect + 160 strategic 轨迹
- GRPO v3 代码就绪（IPS + DAPO Clip-Higher + KL + clipped ratio）

---

## 1. 项目定位

MemoryGym 是 LLM agent **记忆管理能力**的评测与训练平台——测量 agent 在写入预算压力下的存储决策质量。

| 维度 | MemoryGym | 现有方案 |
|------|-------------|----------|
| **测什么** | 存储决策（存什么、更新什么、丢弃什么） | 检索质量（LoCoMo）、多轮记忆（MemoryAgentBench） |
| **预算压力** | 写入次数受限，必须选择性存储 | 无预算限制 |
| **记忆维护** | 测试修正后是否更新记忆 | 不测 |
| **训练支持** | MemoryEnv（RL 环境）+ SFT 轨迹 | 纯评测 |
| **接口兼容** | Write/Edit/Read + memory_search（OpenClaw 兼容） | 自定义接口 |

---

## 2. 架构

### 2.1 系统结构

```
memorygym/
├── worlds/                     # 世界生成系统
│   ├── base.py                 # WorldTemplate ABC, World, EntitySpec, Relationship, 问题生成
│   ├── company/research/city/hospital/sport/movie/university/codebase.py  # 8 个领域模板
│   ├── eval_task.py            # Inspect AI task: stream solver
│   └── eval_scorer.py          # 4 轴评分器
├── evaluation/
│   ├── validators.py           # 答案匹配 (精确 → 数值 → 综合 → 弃权)
│   ├── llm_judge.py            # 多模型 LLM judge
│   └── backend_bench.py        # 后端天花板测试
├── memory/
│   ├── budget.py               # MemoryBudget（写入限制）
│   └── backends/               # chromadb + markdown（BM25+向量混合搜索）
├── agents/
│   ├── stream_agent.py         # 真实 LLM agent runner
│   └── _tool_helpers.py        # 工具执行逻辑（Write/Edit/Read/memory_search）
├── simulation.py               # 系统自测（9 种策略验证评分有效性）
├── bench.py                    # CLI: 真实评测 + simulation
├── protocol.py                 # 标准评估协议（tier 定义、JSON schema）
├── training/                   # SFT 轨迹生成 + MemoryEnv（RL 环境）
│   ├── env.py                  # MemoryEnv + SFT 轨迹生成
│   ├── common.py               # 共享工具（模型加载、assistant mask、chat template）
│   ├── cli.py                  # 统一 CLI（data/sft/grpo/smoke）
│   └── __main__.py             # python -m memorygym.training 入口
├── adapters/                   # RL 框架适配层
│   ├── _common.py              # 共享工具解析 + episode runner
│   ├── verl_adapter.py         # verl AgentLoopBase 集成（@register memorygym_agent）
│   ├── verl_reward.py          # verl compute_score 奖励函数
│   └── slime_adapter.py        # slime custom generate/reward
└── scripts/                    # 训练脚本
    ├── train.py                # 统一远程训练入口（SSH 远程 + GPU 检测 + 日志解析）
    ├── generate_train_data.py  # 生成训练 prompts JSONL
    ├── verl_memorygym.yaml     # verl GRPO 训练配置
    └── memorygym_agent.yaml    # agent loop 配置
```

### 2.2 评分体系 (4 轴)

| 轴 | 权重 | 测什么 |
|----|------|--------|
| breadth | 0.30 | 存储广度（retrieval 正确率）|
| maintenance | 0.25 | 记忆维护（update 正确率 × coverage gate）|
| reasoning | 0.25 | 推理能力（20 种 competency：9 基础 + 2 修正 + 5 关系推理 + 4 新 dtype）|
| efficiency | 0.20 | 效率（correct_count / write_budget）|

abstention_diagnostic 单独报告，不计入 composite。

### 2.3 评估层级

| Tier | 实体数 | 问题数 | 修正数 | 预算 | 压力比 |
|------|--------|--------|--------|------|--------|
| lite | 30 | 10 | 3 | 15 | 2:1 |
| standard | 60 | 20 | 5 | 30 | 2:1 |
| hard | 120 | 40 | 10 | 30 | 4:1 |
| multi | 60 | 20 | 5 | 30 | 2:1 (3 sessions) |

### 2.4 Simulation 策略与不变量

9 种策略验证评分有效性：perfect=100%, guesser=0%, strategic>naive+10%, abstainer<15%, smart_guesser<=5%。

### 2.5 MemoryEnv (RL 环境)

| 属性 | 状态 |
|------|------|
| 接口 | reset() → str, step(action_text) → (str, float, bool, dict) |
| Tier 支持 | lite/standard/hard |
| Observation | 格式化文本（与 stream_agent 一致），含预算上下文 |
| Reward | binary (正确=+1, 错误=0) + shaped (store=+0.3, correction=+0.5, answer=+1.0) |
| get_verifiable_reward() | accuracy，供 GRPO 使用 |
| Search | ChromaDB/MarkdownBackend（与真实 eval 一致）|
| 工具接口 | Write/Edit/Read/memory_search（OpenClaw 兼容）|
| Correction Edit | 免预算（Phase 112），与 eval 一致 |

### 2.6 推理题型（20 types）

基础: synthesis, aggregation, cross_category, conditional, ratio, comparison, multi_hop, outlier, delta
推理: counterfactual, multi_constraint
关系: relationship_lookup, relationship_hop, relationship_chain, relationship_count, relationship_filter
新 dtype: temporal_trend, temporal_extreme, text_match, enum_filter

### 2.7 测试覆盖

437 tests, 9 simulation strategies ALL PASS（v0.10.18）

---

## 3. 证据

### 3.1 评测数据 (v2 — Phase 16+ Enhanced Templates)

> v1 数据（10 属性模板）已归档到 `eval/archive_v1/`。以下为 v2 数据（21-23 属性，6 dtype，20 reasoning types）。
> 8 模板：company, research, city, hospital, sport, movie, university, codebase

**123 次真实评测，5 个模型，5 个厂商。5 模型 × 8 模板全覆盖。**

#### 全模型排名（Composite，123 evals）

| 模型 | N | Composite | Avg Score | 模板覆盖 |
|------|---|-----------|-----------|----------|
| Qwen3.5-397B | 71 | **18.0%** | 31.0% | 8/8 |
| Qwen3-235B | 11 | **17.7%** | 20.9% | 8/8 |
| MiniMax-M2.5 | 11 | **15.2%** | 21.8% | 8/8 |
| Kimi-K2.5 | 21 | **15.2%** | 26.0% | 8/8 |
| GLM-5 | 9 | **10.2%** | 20.6% | 8/8 |

#### Phase 112 影响（Correction Edit 免预算）

Phase 112 是历史最大影响变更：
- Composite +3.6pp（16 post-112 evals vs pre-112 baseline）
- Maintenance +5.6pp（M>0% 从 ~20% 提升到 70%）
- 根因：修正事件发生时 agent 已用完 30 writes，无法 Edit → 免预算后可正常更新

#### 关键发现

- **Breadth 10.8% 是级联瓶颈**：模型存储覆盖率低 → reasoning/maintenance 也因缺数据而失败
- entities_per_write = 1.0（所有模型）——多实体打包是未开发的优化方向
- Backend 对比：MarkdownBackend 30% vs ChromaDB 31.7%——无显著差异，瓶颈在模型端

### 3.2 v1 历史数据摘要 [archived]

v1 关键发现（仅供参考，分数不可与 v2 比较）：
- Qwen3.5-397B 最强（73% avg），breadth/abstention 100%
- Kimi-K2.5 中等（40% avg），maintenance 弱（多数 0%）
- v2 分数显著低于 v1（22-23 属性 vs 10，信息密度更高）

### 3.3 数据索引

```
eval/archive_v1/  # v1 数据（Phase 16 前，10 属性模板）
├── 49 JSON files (results + trajectories)
└── README.md

eval/              # v2 数据（Phase 16 后，21-23 属性模板）
├── 130+ JSON files (results + trajectories，123 有效)
└── 5 models × 8 templates × multiple seeds/tiers
```

---

## 4. 优先级

> 基于 §3 证据推导。方向可变，变更时必须记录依据。

### 当前优先级

**1. RL 训练闭环** — 最高优先（阻塞于 GPU SSH 不可达，9+ 天）
- SFT v6 数据就绪：320 mixed trajectories（160 perfect + 160 strategic），8 templates
- GRPO v3 代码就绪：IPS + DAPO Clip-Higher + KL 正则化 + clipped ratio
- 前沿参考：MEM-alpha（RL 记忆构建，13x 泛化）、INTENT（budget-aware planning）、WebAgent-R1（binary reward 5-6x 提升）
- 成功标准：7B 模型 composite ≥ 45%, maintenance ≥ 30%

**2. 评测数据积累** — 已达 123 evals，5 模型 × 8 模板全覆盖
- 数据积累基本完成，焦点转向 RL 训练
- 新 eval 仅在代码变更后做回归验证

**3. 代码质量** — 低优先级
- MemoryEnv ChromaDB 资源泄漏（训练循环累积 orphan collections）
- 执行线程待办为空

### 已完成优先级

- ✅ 多模板 eval 数据（跨模板有效性已确认，8 模板全覆盖）
- ✅ 跨模型工具兼容性（5 厂商均非零分）
- ✅ 任务复杂度升级 + 新世界模板（20 reasoning types, 8 templates）
- ✅ V2 系统升级（Phase 29-44）
- ✅ 工具接口 OpenClaw 化（Phase 59-61）
- ✅ MarkdownBackend 开发与对比验证（Phase 62-65）
- ✅ Correction Edit 免预算（Phase 112，+3.6pp composite）

### 优先级变更记录

| 日期 | 变更 | 依据 |
|------|------|------|
| 2026-03-08 | 初始优先级设定 | 基于已有 eval 数据分析 |
| 2026-03-08 | 任务复杂度升级从 #4 提升到 #3 | 用户指示 |
| 2026-03-08 | Phase 1-3 完成，RL 训练闭环提升为最高优先 | 评测系统稳定 |
| 2026-03-09 | V2 系统级重设计 | 战略审计确认推理机械化 + 模板策略同质化 |
| 2026-03-11 | RL 训练 + 代码质量并行 | 50 evals 稳定，backend 对比完成，代码审计发现资源泄漏 |
| 2026-03-12 | 评测数据从"进行中"改为"基本完成" | 123 evals，5×8 全覆盖 |

---

## 5. 技术决策

### 已确定

| 决策 | 选择 | 理由 |
|------|------|------|
| 评估路径 | WorldTemplate | 可控、可扩展、确定性 |
| 评分体系 | 4-axis + abstention diagnostic | 可解释、可分析 |
| 数值验证 | 整数精确 + 浮点 2% 容差 | 阻止猜测、容忍显示差异 |
| 预算上下文 | 动态注入（非强制限制） | 存储决策应由 agent 做 |
| MemoryEnv obs | 文本格式 | 与 LLM 输入格式一致 |
| RL 框架 | verl + slime 双适配（memorygym/adapters/） | 共享 MemoryEnv，薄适配层 |
| Multi-entity packing | 允许（合法策略） | 智能压缩是核心技能 |
| 效率公式 | correct_count / write_budget | 不惩罚少写，奖励正确答案 |
| 工具接口 | Write/Edit/Read/memory_search（OpenClaw 兼容） | 标准化 |
| Backend | ChromaDB + MarkdownBackend 并行 | 对比验证无显著差异 |
| Correction Edit 免预算 | Phase 112 实现 | 修正事件时 agent 已用完预算，无法 Edit 是 M=0% 的根因 |

### 待决定

| 决策 | 选项 | 决定时机 |
|------|------|----------|
| GRPO v3 算法 | KL 正则化 vs GSPO vs step-wise GRPO | GPU 可用后 |

### 已否决

| 方案 | 理由 |
|------|------|
| 每批次预算上限 | 违反 agent 自主决策原则 |
| 自研 GRPO | 不是核心贡献 |
| mem0 后端 | Phase 58 移除——API 不稳定，无法可靠集成 |

---

## 6. 已知问题

| 问题 | 严重度 | 备注 |
|------|--------|------|
| GPU SSH 不可达 | **高** | 阻塞 RL 训练 9+ 天，需基础设施管理员介入 |
| MemoryEnv ChromaDB 资源泄漏 | 中 | reset() 创建新 collection 不清理旧的 |
| GRPO v2 policy collapse | 高 | loss→负值，v3 计划 KL 正则化 |
| entities_per_write = 1.0 | 低 | 模型能力问题，非系统 bug |
| ~~MarkdownBackend 临时目录泄漏~~ | ~~低~~ | ✅ Phase 79 已修 close() |
| ~~sport priority>random 偶尔 flaky~~ | ~~低~~ | ✅ 改为 global avg 软检查 |
| ~~MemoryEnv search 是 substring~~ | ~~中~~ | ✅ 已改为 ChromaDB embedding search |
| ~~stream_agent 工具解析脆弱~~ | ~~中~~ | ✅ 支持 4 种格式 |
| ~~Maintenance 全线 0%~~ | ~~高~~ | ✅ Phase 112 Correction Edit 免预算，M>0% 从 ~20%→70% |

---

## 7. 参考文献

### Agent Memory
- A-Mem (2502.12110), AgeMem (2601.01885), A-MAC (2603.04549)
- Learn to Memorize (2508.16629), MemGPT/Letta (2310.08560)
- mem-agent (Dria/HF — Markdown file + GSPO), Memory-R1 (ADD/UPDATE/DELETE + GRPO)
- PlugMem (Microsoft — hierarchical memory), Memex(RL) (2507.08115)
- MEM-alpha (2509.25911 — RL memory construction, 13x length generalization)
- FluxMem (2602.14038 — adaptive memory structure selection)

### Agent RL Training
- DeepSeek-R1 (2501.12948), Agent-R1 (2511.14460), WebAgent-R1 (2505.16421)
- REDSearcher (2602.14234), Simia (2511.01824)
- Search-R1 (2503.09516), VerlTool (2509.01055), AgentGym-RL (ICLR 2026)
- GSPO (2507.18071 — Qwen3 team, sequence-level importance ratio)
- SELAUR (2602.21158 — uncertainty-aware shaped rewards)
- Training-Free GRPO (2510.08191 — zero-cost semantic advantage distillation)
- Dr.MAS (2602.08847 — per-agent advantage normalization)
- INTENT (2602.11541 — budget-constrained intention-aware tool planning)

### Benchmarks
- LoCoMo (2402.17753), MemoryAgentBench (2507.05257, ICLR 2026), LongMemEval (2024)
- AMemGym (ICLR 2026), openclaw-memory-bench (OpenClaw team)
- PinchBench, GAIA (2311.12983), AgentBench (ICLR 2024)
- BudgetMem (2511.04919 — dual-tier memory + budget constraints)
- StructMemEval (2602.11243 — memory organization structure)
- LoCoMo-Plus (2602.10715 — cognitive memory evaluation)
- Evo-Memory (2511.20857 — self-evolving memory, DeepMind)
- MemoryArena (interdependent multi-session agentic memory)
