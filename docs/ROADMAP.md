# MemoryGym Roadmap

> 项目状态、证据、优先级、架构、技术决策的权威文档。
> 由自治演进协议持续维护。

**最后更新**: 2026-03-11

---

## 0. 当前状态

> 新 session 先看这里 + `sessions/EXECUTOR.md`。上下文不足时可读最近的 devlog 文件。

**当前焦点**: RL 训练端到端验证（SFT v3 + GRPO v3）

**最大差距**: RL 训练尚未产出超越 SFT 基线的模型（SFT v2b: 3/10 correct, reward=0.46）

**已完成**:
- Phase 0-28: 基础系统、模板增强、评分统一、红队审计 ✅
- Phase 29-33: V2 系统重设计 — 反事实/多约束题型、模板事件流差异化、实体重要性、噪声注入 ✅
- Phase 34-46: 长上下文模式、多会话评测、RL shaped reward、版本追踪 ✅
- Phase 47-50: ChromaDB 搜索精度、mem0 集成、Inspect AI、adapter 完善 ✅
- Phase 51: MemoryEnv process-based reward 增强 ✅
- Phase 57-58: 系统提示词中立化 + mem0 后端移除 ✅
- Phase 59-61: 工具接口 OpenClaw 化（Write/Edit/Read）+ bug 修复 ✅
- Phase 62: MarkdownBackend 接入 bench.py + training env ✅
- Phase 63-64: training/env.py 与 eval 对齐 + eval_task.py 同步 ✅
- Phase 65: training/env.py Edit hasattr 修复 ✅
- Phase 67-70: 资源泄漏修复、RNG 对齐、MarkdownBackend temporal decay、ChromaDB Edit fallback ✅
- Phase 71-76: 事件格式策略提示移除、Simulation 轴分数验证、版本 bug、系统提示词修复、Inspect AI 路径修复、3 路径一致性测试 ✅
- Phase 77-80: contradiction 丢失 bug、推理题型全覆盖测试、数据质量修复 ✅
- Phase 81-86: 训练基础設施修复、MarkdownBackend recall 基准、Inspect AI 工具名、eval_task.py 默认值、test_path_consistency 扩展 ✅
- Phase 87-93: SFT 连续消息合并、budget 超支修复、问题措辞泄漏修复、RL reward 对齐 4 轴评分、CLI UX 修复 ✅
- 6 模板 × 22-23 attrs × 6 dtypes × 20 reasoning competencies
- 397 tests, 9 simulation strategies ALL PASS（v0.9.1）
- 66 real evaluations, 5 models — Qwen3.5=33%, Kimi=28%, GLM-5=25%, Qwen3-235B=18%, MiniMax=18%
- 2 backends: ChromaDB（embedding）+ MarkdownBackend（BM25+向量混合搜索）
- Backend 对比完成：MarkdownBackend 30% vs ChromaDB 31.7%（无显著差异，瓶颈在模型端）
- MemoryEnv shaped reward + verl/slime 适配器 + SFT 轨迹生成
- SFT v2b: loss 1.785→0.674, 9/15 writes, 3/10 correct, reward=0.46

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
│   ├── company/research/city/hospital/sport/movie.py  # 6 个领域模板
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

9 种策略验证评分有效性：perfect=100%, guesser=0%, strategic>naive+10%, abstainer<15%, smart_guesser<5%。

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

### 2.6 推理题型（20 types）

基础: synthesis, aggregation, cross_category, conditional, ratio, comparison, multi_hop, outlier, delta
推理: counterfactual, multi_constraint
关系: relationship_lookup, relationship_hop, relationship_chain, relationship_count, relationship_filter
新 dtype: temporal_trend, temporal_extreme, text_match, enum_filter

### 2.7 测试覆盖

397 tests: test_validators(81) + test_training(44) + test_adapters(33) + test_stream_agent(27) + test_bench(24) + test_worlds_features(22) + test_reasoning_coverage(22) + test_worlds(21) + test_markdown_backend(21) + test_path_consistency(19) + test_eval_task(17) + test_narrative(15) + test_env(13) + test_llm_judge(11) + test_new_dtypes(9) + test_config(9) + test_backend_bench(9)

---

## 3. 证据

### 3.1 评测数据 (v2 — Phase 16+ Enhanced Templates)

> v1 数据（10 属性模板）已归档到 `eval/archive_v1/`。以下为 v2 数据（22-23 属性，6 dtype，20 reasoning types）。

**66 次真实评测，5 个模型，5 个厂商。** 多模型汇总：

| 模型 | N | Composite | Breadth | Maint. | Reasoning | Efficiency |
|------|---|-----------|---------|--------|-----------|------------|
| Qwen3.5-397B | 27 | **24%** | 27% | 37% | 17% | 14% |
| Qwen3-235B | 7 | **19%** | 16% | 48% | 2% | 10% |
| Kimi-K2.5 | 18 | **18%** | 12% | 38% | 12% | 11% |
| GLM-5 | 5 | **17%** | 16% | 22% | 18% | 10% |
| MiniMax-M2.5 | 9 | **13%** | 7% | 28% | 8% | 7% |

**关键发现**（A62 数据分析 + A69 批次分析）：
- Retrieval 11% 正确率是最大瓶颈（60% 弃权 = 存了但搜不到）
- 7 个推理类型 0%（outlier/comparison/cross_category/text_match/enum_filter/aggregation/multi_hop）——系统性模型能力差距，非 bug
- Maintenance 最强轴（27-49%），Efficiency 最弱（5-13%）
- 五模型分为三档：Qwen3.5 领先（24%），Qwen3-235B/Kimi/GLM-5 中档（17-19%），MiniMax 末位（13%）
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

eval/              # v2 数据（Phase 16 后，22-23 属性模板）
├── 50+ JSON results + trajectory files
└── 5 models × 6 templates × multiple seeds/tiers
```

---

## 4. 优先级

> 基于 §3 证据推导。方向可变，变更时必须记录依据。

### 当前优先级

**1. RL 训练闭环** — 最高优先
- SFT v2b 突破：3/10 correct, reward=0.46（首个能正确回答的模型）
- SFT v3 进行中：新工具接口（Write/Edit/Read）数据已生成（480 trajectories）
- GRPO v2 确认 policy collapse → v3 计划：KL 正则化 + step-wise GRPO（AgeMem 参考）
- 成功标准：7B 模型 composite ≥ 45%, maintenance ≥ 30%

**2. 代码质量强化** — 进行中
- MemoryEnv ChromaDB 资源泄漏（训练循环累积 orphan collections）
- MarkdownBackend 临时目录清理
- 训练-评测 RNG 一致性审计
- stale 元数据清理（mem0 __pycache__, egg-info）

**3. 弱模型覆盖扩展** — 进行中
- GLM-5 仅 5 evals, MiniMax 仅 9 evals
- 需要更多数据点确认弱模型得分是否稳定
- Batch 15 已派发

### 已完成优先级

- ✅ 多模板 eval 数据（跨模板有效性已确认）
- ✅ 跨模型工具兼容性（3 厂商均非零分）
- ✅ 任务复杂度升级 + 新世界模板（20 reasoning types, 6 templates）
- ✅ V2 系统升级（Phase 29-44）
- ✅ 工具接口 OpenClaw 化（Phase 59-61）
- ✅ MarkdownBackend 开发与对比验证（Phase 62-65）

### 优先级变更记录

| 日期 | 变更 | 依据 |
|------|------|------|
| 2026-03-08 | 初始优先级设定 | 基于已有 eval 数据分析 |
| 2026-03-08 | 任务复杂度升级从 #4 提升到 #3 | 用户指示 |
| 2026-03-08 | Phase 1-3 完成，RL 训练闭环提升为最高优先 | 评测系统稳定 |
| 2026-03-09 | V2 系统级重设计 | 战略审计确认推理机械化 + 模板策略同质化 |
| 2026-03-11 | RL 训练 + 代码质量并行 | 50 evals 稳定，backend 对比完成，代码审计发现资源泄漏 |

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

### 待决定

| 决策 | 选项 | 决定时机 |
|------|------|----------|
| GRPO v3 算法 | KL 正则化 vs GSPO vs step-wise GRPO | SFT v3 完成后 |

### 已否决

| 方案 | 理由 |
|------|------|
| 每批次预算上限 | 违反 agent 自主决策原则 |
| Correction 免费写入 | 降低预算管理策略性 |
| 自研 GRPO | 不是核心贡献 |
| mem0 后端 | Phase 58 移除——API 不稳定，无法可靠集成 |

---

## 6. 已知问题

| 问题 | 严重度 | 备注 |
|------|--------|------|
| MemoryEnv ChromaDB 资源泄漏 | 中 | reset() 创建新 collection 不清理旧的 |
| ~~MarkdownBackend 临时目录泄漏~~ | ~~低~~ | ✅ Phase 79 已修 close() |
| GRPO v2 policy collapse | 高 | loss→负值，v3 计划 KL 正则化 |
| 7 个推理类型所有模型 0% | 中 | 需更多数据确认是合理难度还是需调整 |
| entities_per_write = 1.0 | 低 | 模型能力问题，非系统 bug |
| ~~sport priority>random 偶尔 flaky~~ | ~~低~~ | ✅ 改为 global avg 软检查 |
| ~~MemoryEnv search 是 substring~~ | ~~中~~ | ✅ 已改为 ChromaDB embedding search |
| ~~stream_agent 工具解析脆弱~~ | ~~中~~ | ✅ 支持 4 种格式 |

---

## 7. 参考文献

### Agent Memory
- A-Mem (2502.12110), AgeMem (2601.01885), A-MAC (2603.04549)
- Learn to Memorize (2508.16629), MemGPT/Letta (2310.08560)
- mem-agent (Dria/HF — Markdown file + GSPO), Memory-R1 (ADD/UPDATE/DELETE + GRPO)
- PlugMem (Microsoft — hierarchical memory), Memex(RL) (2507.08115)

### Agent RL Training
- DeepSeek-R1 (2501.12948), Agent-R1 (2511.14460), WebAgent-R1 (2505.16421)
- REDSearcher (2602.14234), Simia (2511.01824)
- Search-R1 (2503.09516), VerlTool (2509.01055), AgentGym-RL (ICLR 2026)
- GSPO (2507.18071 — Qwen3 team, sequence-level importance ratio)

### Benchmarks
- LoCoMo (2402.17753), MemoryAgentBench (ICLR 2026), LongMemEval (2024)
- AMemGym (ICLR 2026), openclaw-memory-bench (OpenClaw team)
- PinchBench, GAIA (2311.12983), AgentBench (ICLR 2024)
