# MemoryGym Roadmap

> 项目状态、证据、优先级、架构、技术决策的权威文档。
> 由自治演进协议持续维护。

**最后更新**: 2026-03-08

---

## 0. 当前状态

> 新 session 先看这里 + `AUTOPILOT.md`。上下文不足时可读最近的 devlog 文件。

**当前焦点**: RL 训练闭环（verl 端到端验证）

**最大差距**: 端到端训练验证（verl 集成已完成，需 GPU 环境验证）

**已完成**:
- Phase 0: 多模板 eval（3 模板 × Qwen3.5-397B）✅
- Phase 1: 跨模型兼容性（3 厂商非零分）✅
- Phase 2: 任务复杂度升级（实体关系 + MovieWorld）✅
- 6 个领域模板（company/research/city/hospital/sport/movie）
- 实体关系层（5 种关系题型：lookup/hop/chain/count/filter）
- 247 tests passing
- 动态预算上下文 + tool loop nudge
- MemoryEnv 完整可用（tier/text obs/stats/get_verifiable_reward/ChromaDB embedding search）
- verl + slime 双适配器 + 训练基础设施（config/data gen/reward func）
- 小模型基线（Qwen3-14B=20%, Qwen3-32B=30%）

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
│   └── backends/               # chromadb（默认）+ mem0（可选）
├── agents/
│   └── stream_agent.py         # 真实 LLM agent runner
├── simulation.py               # 系统自测（8 种策略验证评分有效性）
├── bench.py                    # CLI: 真实评测 + simulation
├── protocol.py                 # 标准评估协议（tier 定义、JSON schema）
├── training.py                 # SFT 轨迹生成 + MemoryEnv（RL 环境）
├── adapters/                   # RL 框架适配层
│   ├── _common.py              # 共享工具解析 + episode runner
│   ├── verl_adapter.py         # verl AgentLoopBase 集成（@register memorygym_agent）
│   ├── verl_reward.py          # verl compute_score 奖励函数
│   └── slime_adapter.py        # slime custom generate/reward
└── scripts/                    # 训练脚本
    ├── generate_train_data.py  # 生成训练 prompts JSONL
    ├── verl_memorygym.yaml     # verl GRPO 训练配置
    └── memorygym_agent.yaml    # agent loop 配置
```

### 2.2 评分体系 (4 轴)

| 轴 | 权重 | 测什么 |
|----|------|--------|
| breadth | 0.25 | 存储广度（retrieval 正确率）|
| maintenance | 0.25 | 记忆维护（update 正确率 × coverage gate）|
| reasoning | 0.30 | 推理能力（14 种 comprehension 题型，含 5 种关系推理）|
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
| Search | ChromaDB embedding search（all-MiniLM-L6-v2），与真实 eval 一致 |

### 2.6 测试覆盖

247 tests: test_worlds(37) + test_validators(61) + test_bench(22) + test_stream_agent(21) + test_training(21) + test_backend_bench(7) + test_llm_judge(11) + test_narrative(15) + test_adapters(27) + other(25)

---

## 3. 证据

### 3.1 评测数据

| 模型 | 模板 | Tier | Seeds | Composite | Breadth | Maintenance | Reasoning | Abstention |
|------|------|------|-------|-----------|---------|-------------|-----------|------------|
| Qwen3.5-397B | research | lite | 1 | **70%** | 100% | **33%** | 50% | 100% |
| Qwen3.5-397B | city | lite | 1 | **60%** | 100% | **33%** | 0% | 100% |
| Qwen3.5-397B | hospital | lite | 1 | **90%** | 100% | **100%** | 50% | 100% |
| MiniMax-M2.5 | company | lite | 1 | **50%** | 50% | **67%** | 0% | 100% |
| Kimi-K2.5 | company | lite | 1 | **80%** | 75% | **100%** | 50% | 100% |
| Qwen2.5-72B | company | 极简(30e/5q) | 0 | **83%** | 100% | **100%** | n/a | 100% |
| Qwen3-235B | company | lite | 1,2 | **27%** | 55% | **33-100%** | 33% | 0% |
| Qwen3-235B | company | standard | 0 | 10% | 20% | 0% | 0% | 0% |
| Qwen3-32B | company | mixed | 0,1,2 | **30%** | 33% | 11% | 33% | 50% |
| DeepSeek-V3 | company | 旧格式(200e) | 0,1,2 | **37%** | 22% | 0% | 67% | 71% |
| Qwen3-14B | company | lite | 1 | **20%** | 0% | **33%** | 0% | 100% |
| Qwen3-32B | company | lite | 1 | **30%** | 25% | **33%** | 0% | 100% |
| GPT-OSS-120B | company | standard | 0 | 0% | 0% | 0% | 0% | 0% |

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

**3. 跨模板评测有效性已确认（Qwen3.5-397B × 3 模板）**
- 事实：research=70%, city=60%, hospital=90%（同一模型, seed=1, lite）
- 事实：breadth=100% 在所有模板一致 → 存储决策稳定
- 事实：abstention=100% 在所有模板一致 → 弃权能力稳定
- 事实：maintenance 波动大（33%-100%）→ 取决于 correction 时是否还有预算 + 是否成功执行更新
- 事实：reasoning 波动最大（0%-50%）→ 模板间推理难度差异显著
- 解读：评测系统跨模板有效，无明显领域偏好。差异来自任务难度而非系统偏差
- 影响：可以进入跨模型兼容性阶段

### 3.3 数据索引

```
eval/
├── Qwen_Qwen3.5-397B-A17B-TEE_{research,city,hospital}_s1.json
├── MiniMaxAI_MiniMax-M2.5-TEE_company_s1.json
├── moonshotai_Kimi-K2.5-TEE_company_s1.json
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

**1. 多模板 eval 数据** — ✅ 完成
- 依据：§3.2 发现 3 — 仅 company 有数据，无法确认跨模板有效性
- 结果：research=70%, city=60%, hospital=90%，跨模板有效性已确认

**2. 跨模型工具兼容性** — ✅ 完成
- 依据：§3.2 发现 2 — 工具格式是跨模型障碍
- 结果：Qwen3.5-397B(60-90%), MiniMax-M2.5(50%), Kimi-K2.5(80%)，3 厂商均非零分

**3. 任务复杂度升级 + 新世界模板** — ✅ 完成
- 结果：实体关系层（5 模板 × 2 关系类型 + relationship_lookup/hop 题型）
- 结果：MovieWorld 新模板（全部 simulation 不变量通过）
- 结果：13 种 comprehension 题型（原 8 种 + 5 种关系推理）

**4. RL 训练闭环** — 高（当前最大差距）
- 依据：MemoryEnv embedding search 已完成，verl 集成已完成
- 关键组件：~~embedding search~~ ✅ → ~~GRPO 对接~~ ✅ → ~~小模型基线~~ ✅ → ~~curriculum 配置~~ ✅ → GPU 端到端验证 → shaped reward
- 小模型基线：Qwen3-14B=20%, Qwen3-32B=30%（breadth/maintenance 是主要瓶颈，reasoning=0%）
- 成功标准：7B 模型 composite ≥ 45%, maintenance ≥ 30%

### 优先级变更记录

| 日期 | 变更 | 依据 |
|------|------|------|
| 2026-03-08 | 初始优先级设定 | 基于已有 eval 数据分析 |
| 2026-03-08 | 任务复杂度升级从 #4 提升到 #3 | 用户指示：增加新世界模板和题型复杂度优先于 RL |
| 2026-03-08 | Phase 1-3 完成，RL 训练闭环提升为最高优先 | 评测系统稳定，训练是最大差距 |

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
| RL 框架 | verl + slime 双适配（memorygym/adapters/） | 共享 MemoryEnv，薄适配层对接各框架 |

### 待决定

| 决策 | 选项 | 决定时机 |
|------|------|----------|
| ~~RL 具体框架~~ | ~~verl vs OpenRLHF~~ | ✅ 已决定: verl（见 devlog/2026-03-08-grpo-framework-selection.md）|
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
| ~~sport priority>random 偶尔 flaky~~ | ~~低~~ | ✅ 改为 global avg 软检查（2% 容差）|
| ~~MemoryEnv search 是 substring~~ | ~~中~~ | ✅ 已改为 ChromaDB embedding search |
| ~~stream_agent 工具解析对非标准格式脆弱~~ | ~~中~~ | ✅ 支持 tool_call/function_call/code block/bare JSON 四种格式 |

---

## 7. 参考文献

### Agent Memory
- A-Mem (2502.12110), AgeMem (2601.01885), A-MAC (2603.04549)
- Learn to Memorize (2508.16629), MemGPT/Letta (2310.08560), mem0 (2504.19413)

### Agent RL Training
- DeepSeek-R1 (2501.12948), Agent-R1 (2511.14460), WebAgent-R1 (2505.16421)
- REDSearcher (2602.14234), Simia (2511.01824)
- Search-R1 (2503.09516), VerlTool (2509.01055), AgentGym-RL (ICLR 2026)

### Benchmarks
- LoCoMo (2402.17753), MemoryAgentBench (ICLR 2026), LongMemEval (2024)
- PinchBench, GAIA (2311.12983), AgentBench (ICLR 2024)
