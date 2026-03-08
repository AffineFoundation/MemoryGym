# MemoryBench 战略蓝图：从评测工具到记忆智能训练平台

> 版本 0.2 | 2026-03-08 | 内部调研文档
> 更新：新增 Phase 0（系统级改进），基于真实评测数据修正差距分析

---

## 目录

1. [前沿研究全景](#1-前沿研究全景)
2. [MemoryBench 当前状态](#2-memorybench-当前状态)
3. [真实评测数据与核心问题](#3-真实评测数据与核心问题)
4. [战略定位](#4-战略定位)
5. [架构演进路线](#5-架构演进路线)
6. [Phase 0：系统级改进（当前阶段）](#6-phase-0系统级改进当前阶段)
7. [Phase 1：RL 训练闭环](#7-phase-1rl-训练闭环)
8. [Phase 2：任务复杂度升级](#8-phase-2任务复杂度升级)
9. [Phase 3：生产级平台](#9-phase-3生产级平台)
10. [技术路线与风险](#10-技术路线与风险)
11. [进度追踪](#11-进度追踪)

---

## 1. 前沿研究全景

### 1.1 Agent Memory 研究现状

| 方向 | 代表工作 | 核心思想 | 局限 |
|------|----------|----------|------|
| **分层记忆架构** | MemGPT/Letta (2023-2024) | context window = RAM，外部存储 = disk | 纯 prompting，策略不可学习 |
| **生产记忆系统** | mem0 (2025), Zep, LangMem | 自动提取事实、图谱存储 | 黑盒存储，agent 不做决策 |
| **自适应准入控制** | A-MAC (2025.03) | 5 维信号决定是否写入 | 规则驱动，未与 RL 结合 |
| **可学习记忆** | Learn-to-Memorize (2025.08), AgeMem (2026.01) | MoE 门控 + RL 优化策略 | 绑定特定任务 |
| **Zettelkasten 链接** | A-Mem (2025.02) | 记忆条目间动态链接 | 无法验证策略优劣 |

**核心空白**：所有系统都缺乏可量化、可训练的评估框架来回答"存储决策做得好不好"。

### 1.2 Agent RL 训练前沿

| 工作 | 方法 | 关键贡献 |
|------|------|----------|
| **DeepSeek-R1** | GRPO + rule-based RL | 证明 RL 可从零训练推理能力 |
| **Agent-R1** | Multi-turn MDP + end-to-end RL | 单轮→多轮 agent RL |
| **WebAgent-R1** | Multi-turn RL for web agents | 3B: 6.1%→33.9% |
| **REDSearcher** | Mid-training + GRPO + 模拟环境 | 成本降 8x，30B 超 GPT-5-Thinking |

核心趋势：GRPO 为事实标准，mid-training 分离技能习得与策略学习，模拟环境实现 cost-free rollout。

### 1.3 Memory Benchmark 现状

| Benchmark | 测什么 | 与 MemoryBench 的区别 |
|-----------|--------|----------------------|
| **LoCoMo** (2024) | 长对话记忆检索 | 不测存储决策 |
| **MemoryAgentBench** (2025) | 4 项记忆能力 | 无预算压力 |
| **LongMemEval** (2024) | 多会话时序推理 | agent 不做存储选择 |

**没有 benchmark 同时测试：预算约束下的存储决策 + 记忆更新维护 + 可训练的 RL 环境。**

---

## 2. MemoryBench 当前状态

### 2.1 已建立的核心能力

| 能力 | 状态 | 说明 |
|------|------|------|
| 问题定义 | ✅ 完成 | write-time decision quality vs read-time retrieval quality |
| Anti-hack 验证 | ✅ 完成 | 6 策略 × 5 模板 × 10 seeds，55 不变量全通过 |
| 确定性可复现 | ✅ 完成 | 同 seed → 相同场景，eval_salt 防预计算 |
| 4 轴评分 | ✅ 完成 | breadth(0.30) + maintenance(0.25) + reasoning(0.25) + efficiency(0.20) |
| 标准协议 | ✅ 完成 | 3 tier (lite/standard/hard) + official mode + JSON schema |
| 并行 judge | ✅ 完成 | 延迟 judge，event loop 结束后 ThreadPoolExecutor 并行执行 |
| 选择性红删 | ✅ 完成 | 事件后保留记忆状态摘要，解决 85% 空答案问题 |

### 2.2 已验证的设计决策

| 决策 | 验证结果 |
|------|----------|
| 交错流式传输 | 强制增量推理，不能 read-all-then-answer |
| 相同问题措辞（retrieval vs update） | Agent 无法通过措辞区分 |
| 虚构实体测弃权 + trick retrieval | always-abstain 天花板 15% |
| name+value 联合检测 | name-only packing = 0 coverage |

### 2.3 尚未完成的基础设施

| 组件 | 声称状态 | 实际状态 |
|------|---------|---------|
| MemoryEnv | "已完成" | **骨架**：返回 dict 非 string，binary reward，substring search，无 axis scores |
| SFT 轨迹 | 已完成 | 功能可用，格式正确 |
| 多模板评测数据 | 需要 | **仅 company 模板有真实数据** |

---

## 3. 真实评测数据与核心问题

### 3.1 已有评测结果汇总

所有评测均在 **company 模板** 上进行。

| 模型 | Tier | Seeds | 平均准确率 | Retrieval | Update | Reasoning | Abstention |
|------|------|-------|-----------|-----------|--------|-----------|------------|
| **Qwen2.5-72B** | 极简(30e/5q) | 0 | **83%** | 100% | **100%** | n/a | 100% |
| **Qwen3-235B** | lite | 1,2,3 | **27%** | 55% | **0%** | 33% | 0% |
| **Qwen3-235B** | standard | 0 | 10% | 20% | **0%** | 0% | 0% |
| **Qwen3-32B** | mixed | 0,1,2 | **30%** | 33% | **11%** | 33% | 50% |
| **DeepSeek-V3** | 旧格式(200e) | 0,1,2 | **37%** | 22% | **0%** | 67% | 71% |
| **GPT-OSS-120B** | standard | 0 | 0% | 0% | 0% | 0% | 0% |

### 3.2 核心发现：预算耗尽是第一问题

| 模型 | writes_used / budget | 耗尽时机 |
|------|---------------------|---------|
| Qwen3-235B (所有 seeds) | 15/15 或 30/30 (**100%**) | 前 2 个 ingest batch |
| Qwen3-32B (所有 seeds) | 15/15 或 30/30 (**100%**) | 前 2-3 个 ingest batch |
| Qwen2.5-72B | 30/30 (100%) | 全部 ingest |
| GPT-OSS-120B | 15/30 (50%) | 工具调用失败 |

**因果链**：模型在前 2 个 ingest batch 耗尽全部预算 → correction 到达时 budget=0 → 无法执行 search→forget→store → **maintenance=0%**。

**尝试过的修复**：在 system prompt 中加入 "Reserve ~20% budget for corrections" → **无效**（seed=3 仍然 budget=0 after batch 2）。

### 3.3 关键数据点：Qwen2.5-72B 的异常

Qwen2.5-72B 在极简场景（30 entities / 5 questions / 30 budget）得到 83%，包括 update=100%。这表明：
- 当 **budget >> entities**（30/30 = 1:1）时，预算耗尽问题自然消失
- 模型 **有能力** 执行 correction 流程（search→forget→store），只是在预算紧张时不会预留
- **这不是模型能力问题，是预算分配问题**

### 3.4 与蓝图 v0.1 差距分析的修正

| 维度 | v0.1 评级 | 修正评级 | 理由 |
|------|----------|---------|------|
| **预算分配** | 未提及 | 🔴 **最紧迫** | 所有模型 maintenance=0% 的根因 |
| RL 训练闭环 | 🔴 | 🔴 但降优先级 | 系统级改进应先于 RL |
| 任务推理深度 | 🔴 | 🟡 **降级** | 当前简单任务都未解决好，复杂度升级过早 |
| 信息分散度 | 🔴 | 🟡 **降级** | 同上 |
| MemoryEnv 完整度 | 未提及 | 🔴 | 骨架状态，与蓝图描述严重不符 |
| 跨模板评测数据 | 未提及 | 🟡 | 仅 company 模板有数据，泛化性未验证 |

---

## 4. 战略定位

不变。MemoryBench 是 **Memory Management 领域的 Gymnasium**：

1. 不测检索质量（向量数据库的事）
2. 测存储决策质量（agent 的事）
3. 提供 RL 训练环境（没人做的事）
4. 与生产记忆系统接口兼容（mem0 API）

---

## 5. 架构演进路线

### 5.1 修正后的四阶段演进

```
Phase 0 (2-3 周)        Phase 1 (8-12 周)       Phase 2 (6-8 周)       Phase 3 (8-12 周)
─────────────────       ─────────────────       ─────────────────      ─────────────────
系统级改进               RL 训练闭环              任务复杂度升级           生产级平台
• 预算分配机制            • MemoryEnv 补全         • 知识图谱 World        • 多后端训练
• 动态预算显示            • Shaped rewards         • 多跳推理              • 分布式 rollout
• Correction 预算策略     • GRPO 对接              • 信息分散              • 论文 + Leaderboard
• 多模板基准数据          • Mid-training SFT
• MemoryEnv 骨架补全      • Curriculum learning

Gate: maintenance>20%   Gate: 7B composite>55%  Gate: anti-hack pass   Gate: 3+ 外部用户
```

**核心原则**：每个 Phase 有明确的 Gate 条件。Phase 0 的 Gate 是"通过系统级改进让至少 1 个模型 maintenance>20%"。如果 Phase 0 达不到，说明问题根因不在系统设计，需要重新评估 RL 的必要性和方向。

---

## 6. Phase 0：系统级改进（当前阶段）

### 6.1 核心目标

> 通过系统级改进（不依赖 RL 训练），让现有模型在 standard tier 上 maintenance>20%。
> 同时建立跨模板基准数据，验证评测体系的泛化性。

### 6.2 预算分配问题分析

当前模型为什么在前 2 个 batch 耗尽预算？

1. **System prompt 的预留提示太弱**：一句 "Reserve ~20% budget" 被大量实体文档淹没
2. **每个 ingest 事件没有预算上下文**：模型不知道还有多少 batch 要来、还剩多少预算
3. **No enforcement**：系统允许模型在 ingest 阶段用光所有 budget

### 6.3 解决方案

#### 方案 A：动态预算上下文（最优先）

在每个 ingest 事件的用户消息中注入预算状态：

```
=== Event 2/16 [DOCUMENTS] ===

⚠️ Budget: 10/15 writes remaining (5 used). Reserve ≥3 for upcoming corrections.
   You have seen 10/30 entities so far. ~20 more entities + 3 corrections to come.

**Documents:**
[Document 1] ...
```

关键信息：
- 剩余 budget / 总 budget
- 已见实体数 / 总实体数（让模型知道还有多少来）
- 预计 correction 数量（帮助模型规划）
- 建议预留量

**文件变更**：
- `memorybench/agents/stream_agent.py`: INGEST_TEMPLATE 和事件处理逻辑中注入预算上下文
- `memorybench/worlds/eval_task.py`: 同步修改 INGEST_TEMPLATE

**验证**：用 Qwen3-235B seed=1 (已知 baseline=50%) 重跑，对比是否预留了 budget。

#### 方案 B：Correction 免费写入

将 correction 事件的写入不计入 write_budget：
- search + forget 已经免费
- 让 store（仅限 correction 事件触发的）也免费
- 逻辑：correction 是系统要求的更新，不应该惩罚 agent

**权衡**：
- 优点：彻底消除预算耗尽导致 maintenance=0% 的问题
- 缺点：降低了预算管理的策略性——agent 不再需要权衡"存新实体 vs 预留更新"
- **决策**：先用方案 A 测试。如果方案 A 不够，再考虑方案 B 作为 fallback。

#### 方案 C：每批次预算上限

限制单个 ingest batch 的最大写入数：

```python
max_writes_per_batch = write_budget // expected_total_batches
```

**权衡**：
- 优点：系统级强制分配，不依赖模型理解
- 缺点：过于限制——模型可能在高价值 batch 中需要更多写入
- **决策**：不采用。这违反了 MemoryBench 的核心设计——存储决策应该由 agent 做。

### 6.4 多模板基准数据收集

当前所有评测仅在 company 模板上。需要至少验证 2 个模板的评测可行性。

**计划**：
- 用当前最佳模型 (Qwen3-235B) 在 research 和 city 模板上各跑 1 seed
- 验证评测流程在其他模板上正常工作
- 收集跨模板的 baseline 数据

### 6.5 MemoryEnv 骨架补全

当前 MemoryEnv 是骨架，以下项需在 Phase 0 补全（为 Phase 1 做准备）：

| 项目 | 当前 | 目标 |
|------|------|------|
| observation 格式 | dict | 格式化文本（与 stream_agent 一致） |
| reward | binary (0/1) | 保持 binary，但累积 episode 统计 |
| info 返回 | 基本 | 加入 writes_used, budget_remaining, axis_scores |
| get_verifiable_reward() | 不存在 | 返回 episode composite score |
| tier 参数 | 不存在 | 支持 lite/standard/hard |

**不在 Phase 0 做的**：shaped reward (Phase 1)、embedding search (Phase 1)、GRPO 对接 (Phase 1)。

### 6.6 实施步骤

```
Step 1: 动态预算上下文                           [估时: 1-2 小时]
  - 修改 stream_agent.py 和 eval_task.py 的 ingest 模板
  - 注入 budget 状态、已见实体数、预计 correction 数
  - 单元测试验证模板渲染

Step 2: 验证预算上下文效果                        [估时: 2-4 小时]
  - Qwen3-235B seed=1 重跑（与 baseline 50% 对比）
  - 观察 budget 消耗曲线是否改变
  - 如果 maintenance 仍=0%，考虑方案 B

Step 3: MemoryEnv 补全                           [估时: 2-3 小时]
  - 文本观测格式化
  - episode 统计累积 + get_verifiable_reward()
  - tier 参数支持
  - 测试更新

Step 4: 多模板基准数据                            [估时: 4-6 小时]
  - Qwen3-235B × research × seed=1
  - Qwen3-235B × city × seed=1
  - 汇总跨模板 baseline
```

### 6.7 Phase 0 完成标准（Gate）

- [ ] 动态预算上下文实现并测试
- [ ] 至少 1 个模型在 lite tier 上 maintenance>20%（或 correction 后 budget>0）
- [ ] MemoryEnv 支持文本观测 + episode 统计 + tier 参数
- [ ] 至少 3 个模板有真实评测数据
- [ ] 所有 206 测试通过 + 55 不变量保持

**如果 Phase 0 Gate 未达标**：
- 方案 A 无效 → 尝试方案 B（correction 免费写入）
- 方案 B 也无效 → 说明模型根本不执行 correction 流程（不是预算问题），直接进 Phase 1 用 RL 训练

---

## 7. Phase 1：RL 训练闭环

### 7.1 核心目标

> 用 GRPO 在 MemoryEnv 上训练 3B/7B 模型，使其记忆管理能力显著优于 prompting baseline。

### 7.2 前置条件（Phase 0 必须完成）

- MemoryEnv 文本观测 + episode 统计可用
- 至少有 3 个模板的 baseline 数据
- 清楚 maintenance=0% 的根因是预算分配还是模型能力

### 7.3 关键组件

#### MemoryEnv 升级（从 Phase 0 骨架到 RL-ready）

| 升级项 | 说明 |
|--------|------|
| Shaped reward (3 层) | Layer 1: outcome composite; Layer 2: per-question; Layer 3: storage oracle bonus |
| Embedding search | sentence-transformers 替代 substring match，与评估一致 |
| Batch rollout 支持 | 无状态实例化，支持并行 episode |

#### GRPO 对接

选择 verl 或 OpenRLHF，提供 MemoryBenchRolloutWorker 适配器。

#### Mid-Training 分离（借鉴 REDSearcher）

```
Stage I:  SFT — 学会工具调用格式（perfect 策略轨迹）
Stage II: SFT — 学会信息提取（document → compact summary）
Stage III: GRPO — 学会策略性存储决策
```

#### 课程学习

lite → standard → hard，根据 composite score 自动升级。

### 7.4 修正后的成功标准

| 指标 | 当前 baseline | Phase 1 目标 | 说明 |
|------|-------------|-------------|------|
| Composite | ~27% (235B avg) | ≥45% (7B) | 比原蓝图降低（55%→45%），更现实 |
| Maintenance | 0% (all models) | ≥30% | 比原蓝图降低（60%→30%），但仍是质变 |
| Efficiency | ~10% | ≥25% | 学会节约 budget |

### 7.5 预估时间：8-12 周

---

## 8. Phase 2：任务复杂度升级

### 8.1 前置条件

- Phase 1 Gate: 7B 模型 composite≥45%，maintenance≥30%
- 基本任务已解决，需要更强区分度

### 8.2 关键组件

| 组件 | 说明 |
|------|------|
| GraphWorldTemplate | 实体间关系（供应商→客户、母子公司等） |
| 多跳推理问题 | treewidth=1,2,3 的图推理 |
| 信息分散 | 每个实体的信息分散在 ≥3 个 documents |

### 8.3 Anti-hack 兼容

- guesser 在图谱问题上 = 0%
- smart_guesser < 5%
- perfect = 100%（全存储时所有信息可用）

### 8.4 预估时间：6-8 周

---

## 9. Phase 3：生产级平台

### 9.1 核心组件

| 组件 | 说明 |
|------|------|
| 多后端训练 | ChromaDB + mem0 + Zep 统一接口 |
| 分布式 Rollout | vLLM + 异步 MemoryEnv workers |
| PyPI 发布 | `pip install memorybench` |
| HuggingFace Leaderboard | 公开排行榜 |
| 预训练 memory agent | 7B 模型开源 |

### 9.2 论文定位

> **MemoryBench: Learning Strategic Memory Management for LLM Agents**
> 投稿目标：NeurIPS 2026 Datasets & Benchmarks Track

### 9.3 预估时间：8-12 周

---

## 10. 技术路线与风险

### 10.1 关键技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 预算分配 | 动态上下文 > correction 免费 > 批次限制 | 从最轻干预到最重干预逐步尝试 |
| RL 框架 | 对接 verl/OpenRLHF | RL 算法不是核心贡献 |
| 后端对齐 | Phase 1 加 embedding | 训练-评估一致性 |

### 10.2 风险矩阵

| 风险 | 可能性 | 影响 | 缓解 |
|------|--------|------|------|
| Phase 0 动态上下文无效 | 中 | 低 | 方案 B/C 备选 |
| RL 训练不收敛 | 中 | 高 | mid-training 提高 base rate |
| 模型不执行 correction 流程 | 高 | 高 | Phase 0 数据验证 + RL 训练 |
| 任务复杂度升级破坏 anti-hack | 中 | 高 | 每次改动跑 55 不变量 |

### 10.3 不做的事情

| 不做 | 为什么 |
|------|--------|
| 自研 GRPO | 不是核心贡献 |
| 每批次预算上限 | 违反 agent 自主决策原则 |
| Phase 0 就做 embedding search | 优先级低于预算问题 |
| 多模态记忆 | 文本优先 |

---

## 11. 进度追踪

### 已完成

- [x] 4 轴评分体系（breadth/maintenance/reasoning/efficiency）
- [x] 标准协议（3 tier + official mode + JSON schema）
- [x] 并行 judge（ThreadPoolExecutor，延迟批量执行）
- [x] 选择性红删（记忆状态摘要替代核清洗）
- [x] System prompt 改进（correction 步骤显式化 + 预算预留提示）
- [x] 搜索结果去截断
- [x] Backend_bench comprehension 验证修复
- [x] MemoryEnv 骨架 + SFT 轨迹生成
- [x] 5 个模型 × company 模板的 baseline 数据

### Phase 0 进行中

- [ ] Step 1: 动态预算上下文
- [ ] Step 2: 验证效果（至少 1 model maintenance>0%）
- [ ] Step 3: MemoryEnv 补全
- [ ] Step 4: 多模板基准数据

### 待启动

- [ ] Phase 1: RL 训练闭环
- [ ] Phase 2: 任务复杂度升级
- [ ] Phase 3: 生产级平台

---

## 附录 A：评测数据索引

所有评测结果存储在 `eval/` 目录：

```
eval/
├── Qwen_Qwen2.5-72B-Instruct_company_s0.json
├── Qwen_Qwen3-235B-A22B-Instruct-2507-TEE_company_s0.json
├── Qwen_Qwen3-235B-A22B-Instruct-2507-TEE_company_s1.json
├── Qwen_Qwen3-235B-A22B-Instruct-2507-TEE_company_s2.json
├── Qwen_Qwen3-235B-A22B-Instruct-2507-TEE_company_s3.json
├── Qwen_Qwen3-32B_company_s0.json
├── Qwen_Qwen3-32B_company_s1.json
├── Qwen_Qwen3-32B_company_s2.json
├── openai_gpt-oss-120b-TEE_company_s0.json
├── deepseek_DeepSeek-V3-0324_aggregate.json
└── report_gpt-oss-120b_vs_qwen3-32b.md
```

## 附录 B：前沿文献索引

### Agent Memory
- A-Mem: Agentic Memory (2502.12110)
- AgeMem: Agentic Memory Unified Framework (2601.01885)
- A-MAC: Adaptive Memory Admission Control (2603.04549)
- Learn to Memorize (2508.16629)
- MemGPT / Letta (2310.08560)
- mem0 (2504.19413)

### Agent RL Training
- DeepSeek-R1: GRPO for Reasoning (2501.12948)
- Agent-R1: End-to-End RL (2511.14460)
- WebAgent-R1: Multi-Turn RL (2505.16421)
- REDSearcher: Search Agent Training (2602.14234)
- Simia: LLM-Simulated Environments (2511.01824)

### Memory Benchmarks
- LoCoMo: Long-term Conversational Memory (2402.17753)
- MemoryAgentBench (2025)
- LongMemEval (2024)
