# MemoryGym Roadmap

> 项目状态、证据、优先级、架构、技术决策的权威文档。
> 由自治演进协议持续维护。

**最后更新**: 2026-03-08

---

## 0. 当前状态

> 新 session 先看这里 + `AUTOPILOT.md`。上下文不足时可读最近的 devlog 文件。

**当前焦点**: 收集多模板 eval 基准数据

**最大差距**: 仅 company 模板有真实 eval 数据，无法判断系统跨领域稳定性

**已验证的能力**:
- 动态预算上下文让 maintenance 从 0% → 33-100%
- MemoryEnv 完整可用（tier/text obs/stats/get_verifiable_reward）
- 215 tests passing

**未提交的代码变更**:
```
M memorygym/agents/stream_agent.py   — 动态预算上下文 + tool loop nudge
M memorygym/worlds/eval_task.py      — 动态预算上下文
M memorygym/training.py              — MemoryEnv 补全 (tier/text obs/stats)
M memorygym/bench.py                 — tier/protocol 集成
M tests/test_bench.py                  — protocol 测试
M tests/test_training.py               — MemoryEnv 测试
```

---

## 1. 项目定位

MemoryGym 是 LLM agent **记忆管理能力**的评测与训练平台——测量 agent 在写入预算压力下的存储决策质量。

| 维度 | MemoryGym | 现有方案 |
|------|-------------|----------|
| **测什么** | 存储决策（存什么、更新什么、丢弃什么） | 检索质量（LoCoMo）、多轮记忆（MemoryAgentBench） |
| **预算压力** | 写入次数受限，必须选择性存储 | 无预算限制 |
| **记忆维护** | 测试修正后是否更新记忆 | 不测 |
| **训练支持** | MemoryEnv（RL 环境）+ SFT 轨迹 | 纯评测 |
| **接口兼容** | mem0 API（store/search/get/forget/list） | 自定义接口 |

---

## 2. 架构

### 2.1 系统结构

```
memorygym/
├── worlds/                     # 世界生成系统
│   ├── base.py (1179L)         # WorldTemplate ABC, World, EntitySpec, 问题生成
│   ├── company/research/city/hospital/sport.py  # 5 个领域模板
│   ├── eval_task.py            # Inspect AI task: stream solver
│   └── eval_scorer.py          # 4 轴评分器
├── evaluation/
│   ├── validators.py           # 答案匹配 (精确 → 数值 → 综合 → 弃权)
│   ├── llm_judge.py            # 多模型 LLM judge
│   └── backend_bench.py        # 后端天花板测试
├── memory/
│   ├── budget.py               # MemoryBudget（写入限制）
│   └── backends/               # chromadb（默认）+ mem0（可选）
├── agents/
│   └── stream_agent.py         # 真实 LLM agent runner
├── simulation.py               # 系统自测（8 种策略验证评分有效性）
├── bench.py                    # CLI: 真实评测 + simulation
├── protocol.py                 # 标准评估协议（tier 定义、JSON schema）
└── training.py                 # SFT 轨迹生成 + MemoryEnv（RL 环境）
```

### 2.2 评分体系 (4 轴)

| 轴 | 权重 | 测什么 |
|----|------|--------|
| breadth | 0.30 | 存储广度（retrieval 正确率）|
| maintenance | 0.25 | 记忆维护（update 正确率 × coverage gate）|
| reasoning | 0.25 | 推理能力（8 种 comprehension 题型）|
| efficiency | 0.20 | 效率（correct/writes_used）|

abstention_diagnostic 单独报告，不计入 composite。

### 2.3 评估层级

| Tier | 实体数 | 问题数 | 修正数 | 预算 | 压力比 |
|------|--------|--------|--------|------|--------|
| lite | 30 | 10 | 3 | 15 | 2:1 |
| standard | 60 | 20 | 5 | 30 | 2:1 |
| hard | 120 | 40 | 10 | 30 | 4:1 |

### 2.4 Simulation 策略与不变量

8 种策略验证评分有效性：perfect=100%, guesser=0%, strategic>naive+10%, abstainer<15%, smart_guesser<5%。

### 2.5 MemoryEnv (RL 环境)

| 属性 | 状态 |
|------|------|
| 接口 | reset() → str, step(action_text) → (str, float, bool, dict) |
| Tier 支持 | lite/standard/hard |
| Observation | 格式化文本（与 stream_agent 一致），含预算上下文 |
| Reward | binary (正确=+1, 错误=0)，仅 submit_answer 触发 |
| get_verifiable_reward() | accuracy，供 GRPO 使用 |
| 已知局限 | search 是 substring match，与真实 eval 的 embedding search 不一致 |

### 2.6 测试覆盖

215 tests: test_worlds(28) + test_validators(61) + test_bench(22) + test_stream_agent(17) + test_training(21) + test_backend_bench(7) + test_llm_judge(11) + test_narrative(15)

---

## 3. 证据

### 3.1 评测数据

| 模型 | Tier | Seeds | Composite | Breadth | Maintenance | Reasoning | Abstention |
|------|------|-------|-----------|---------|-------------|-----------|------------|
| Qwen2.5-72B | 极简(30e/5q) | 0 | **83%** | 100% | **100%** | n/a | 100% |
| Qwen3-235B | lite | 1,2 | **27%** | 55% | **33-100%** | 33% | 0% |
| Qwen3-235B | standard | 0 | 10% | 20% | 0% | 0% | 0% |
| Qwen3-32B | mixed | 0,1,2 | **30%** | 33% | 11% | 33% | 50% |
| DeepSeek-V3 | 旧格式(200e) | 0,1,2 | **37%** | 22% | 0% | 67% | 71% |
| GPT-OSS-120B | standard | 0 | 0% | 0% | 0% | 0% | 0% |

### 3.2 关键发现与解读

**1. 预算分配是 maintenance 的瓶颈，不是模型能力**
- 事实：所有模型在前 2 个 batch 耗尽预算 → correction 时 budget=0 → maintenance=0%
- 事实：动态预算上下文注入后，Qwen3-235B seed=2 maintenance=100%
- 事实：Qwen2.5-72B 在宽松预算下 update=100%
- 解读：评测系统需要给模型足够的决策信息（预算状态），否则测的是"信息是否充分"而非"决策是否正确"
- 影响：系统改进（非 RL）就能显著提升表现。说明当前基础设施还有优化空间

**2. 工具调用格式是跨模型的主要障碍**
- 事实：Qwen3 `<think>` 块消耗整个响应，无 tool_call → 空答案
- 事实：GPT-OSS-120B 全零分，可能是工具格式兼容问题
- 解读：当前 stream_agent 的 text-based tool parsing 对非标准输出格式脆弱
- 影响：提升跨模型兼容性可能比 RL 训练更紧急

**3. 仅有 company 模板数据，无法判断系统稳定性**
- 事实：5 个模板仅 company 有真实 eval
- 解读：评测设计可能对 company 领域有隐性偏好
- 影响：需要多模板数据才能确认评测有效性

### 3.3 数据索引

```
eval/
├── Qwen_Qwen2.5-72B-Instruct_company_s0.json
├── Qwen_Qwen3-235B-*_company_s{0,1,2,3}.json
├── Qwen_Qwen3-32B_company_s{0,1,2}.json
├── openai_gpt-oss-120b-TEE_company_s0.json
└── deepseek_DeepSeek-V3-0324_aggregate.json
```

---

## 4. 优先级

> 基于 §3 证据推导。方向可变，变更时必须记录依据。

### 当前优先级

**1. 多模板 eval 数据** — 紧急
- 依据：§3.2 发现 3 — 仅 company 有数据，无法确认跨模板有效性
- 完成条件：≥3 个模板有 Qwen3-235B eval 数据
- 具体：跑 research + city × seed=1 (lite tier)

**2. 跨模型工具兼容性** — 高
- 依据：§3.2 发现 2 — 工具格式是跨模型障碍
- 完成条件：≥3 个不同模型能完成完整 eval（非零分）
- 具体：分析 GPT-OSS-120B 零分原因，改进 stream_agent 工具解析

**3. RL 训练闭环** — 中
- 依据：MemoryEnv 已就绪，但 search 是 substring match，与真实 eval 不一致
- 前置：优先级 1 确认评测跨模板有效
- 关键组件：embedding search → GRPO 对接 → shaped reward → curriculum
- 成功标准：7B 模型 composite ≥ 45%, maintenance ≥ 30%

**4. 任务复杂度升级** — 低
- 依据：当前 key-value 存取已能区分策略差异（strategic 63% vs naive 19%），区分度够用
- 前置：RL 训练验证基础评测有效
- 方向：实体关系图、多跳推理、信息分散度控制

### 优先级变更记录

| 日期 | 变更 | 依据 |
|------|------|------|
| 2026-03-08 | 初始优先级设定 | 基于已有 eval 数据分析 |

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
| RL 框架 | 对接 verl/OpenRLHF（非自研） | RL 算法不是核心贡献 |

### 待决定

| 决策 | 选项 | 决定时机 |
|------|------|----------|
| RL 具体框架 | verl vs OpenRLHF | RL 闭环启动时 |
| 真实数据源 | Wikipedia vs 纯合成 | 任务复杂度升级时 |

### 已否决

| 方案 | 理由 |
|------|------|
| 每批次预算上限 | 违反 agent 自主决策原则 |
| Correction 免费写入 | 降低预算管理策略性 |
| 自研 GRPO | 不是核心贡献 |

---

## 6. 已知问题

| 问题 | 严重度 | 备注 |
|------|--------|------|
| sport priority>random 偶尔 flaky | 低 | 某些 seed 下差异不显著 |
| MemoryEnv search 是 substring | 中 | 与真实 eval 的 embedding search 不一致 |
| stream_agent 工具解析对非标准格式脆弱 | 中 | GPT-OSS-120B 零分可能与此相关 |

---

## 7. 参考文献

### Agent Memory
- A-Mem (2502.12110), AgeMem (2601.01885), A-MAC (2603.04549)
- Learn to Memorize (2508.16629), MemGPT/Letta (2310.08560), mem0 (2504.19413)

### Agent RL Training
- DeepSeek-R1 (2501.12948), Agent-R1 (2511.14460), WebAgent-R1 (2505.16421)
- REDSearcher (2602.14234), Simia (2511.01824)

### Benchmarks
- LoCoMo (2402.17753), MemoryAgentBench (ICLR 2026), LongMemEval (2024)
- PinchBench, GAIA (2311.12983), AgentBench (ICLR 2024)
