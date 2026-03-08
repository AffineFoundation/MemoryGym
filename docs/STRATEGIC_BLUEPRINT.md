# MemoryBench 战略蓝图：从评测工具到记忆智能训练平台

> 版本 0.1 | 2026-03-08 | 内部调研文档

---

## 目录

1. [前沿研究全景](#1-前沿研究全景)
2. [MemoryBench 当前已解决的问题](#2-memorybench-当前已解决的问题)
3. [核心差距分析](#3-核心差距分析)
4. [战略定位：为什么是"记忆管理"](#4-战略定位为什么是记忆管理)
5. [架构演进路线](#5-架构演进路线)
6. [Phase 1：RL 训练闭环](#6-phase-1rl-训练闭环)
7. [Phase 2：任务复杂度升级](#7-phase-2任务复杂度升级)
8. [Phase 3：生产级记忆代理训练](#8-phase-3生产级记忆代理训练)
9. [技术路线选择与权衡](#9-技术路线选择与权衡)
10. [成功标准与里程碑](#10-成功标准与里程碑)

---

## 1. 前沿研究全景

### 1.1 Agent Memory 研究现状

Agent 记忆正在从"工程 hack"走向"一等公民能力"。几条关键脉络：

| 方向 | 代表工作 | 核心思想 | 局限 |
|------|----------|----------|------|
| **分层记忆架构** | MemGPT/Letta (2023-2024) | context window = RAM，外部存储 = disk，LLM 自主管理数据迁移 | 没有训练——纯 prompting，策略不可学习 |
| **生产记忆系统** | mem0 (2025), Zep, LangMem | 自动提取事实、图谱存储、时序追踪 | 黑盒存储，agent 不做存储决策 |
| **自适应准入控制** | A-MAC (2025.03) | 5 维信号（有用性、可靠性、冗余度、时效性、持久性）决定是否写入 | 规则驱动，未与 RL 结合 |
| **可学习记忆** | Learn-to-Memorize (2025.08), AgeMem (2026.01) | MoE 门控 + off-policy/on-policy 优化记忆策略 | 绑定特定任务，缺乏通用 benchmark |
| **Zettelkasten 式动态链接** | A-Mem (2025.02) | 记忆条目间建立动态链接（共现、语义、标签） | 链接质量依赖 LLM，无法验证存储策略优劣 |

**核心观察**：**所有这些系统都缺乏一个可量化、可训练的评估框架来回答"存储决策做得好不好"。** 它们要么是纯工程系统（mem0/Zep），要么是纯理论框架（A-MAC），要么绑定在特定任务上（AgeMem）。

### 1.2 Agent RL 训练前沿

| 工作 | 时间 | 方法 | 关键贡献 |
|------|------|------|----------|
| **DeepSeek-R1** | 2025.01 | GRPO + rule-based RL | 证明 RL 可以从零训练推理能力 |
| **Agent-R1** | 2025.11 | Multi-turn MDP + end-to-end RL | 将单轮 RL 扩展到多轮 agent 交互 |
| **WebAgent-R1** | 2025.05 | Multi-turn RL for web agents | 3B 模型：6.1%→33.9%，证明小模型可训练 |
| **REDSearcher** | 2026.02 | Mid-training + GRPO + 模拟环境 | 训练成本降低 8x，30B 超越 GPT-5-Thinking |
| **Simia** | 2025.11 | LLM 模拟环境替代真实环境 | 无需实现真实环境即可 RL 训练 |
| **GRPO for Tool Use** | 2025 | GRPO + 100 samples | 工具调用提升 23%，数据效率极高 |

**核心趋势**：
1. **GRPO 是当前 agent RL 的事实标准**——无需 value model，内存效率高，适合长序列
2. **Mid-training 分离原子技能和交互执行**——REDSearcher 证明这能降低 8x 训练成本
3. **模拟环境是关键基础设施**——真实 API 调用太贵，模拟环境实现 cost-free rollout
4. **小模型 + RL 可以超越大模型 prompting**——WebAgent-R1 的 8B 超越 GPT-4o

### 1.3 Memory Benchmark 现状

| Benchmark | 测什么 | 与 MemoryBench 的区别 |
|-----------|--------|----------------------|
| **LoCoMo** (2024) | 长对话记忆检索 | 纯检索质量，不测存储决策 |
| **MemoryAgentBench** (2025) | 4 项能力：检索、学习、理解、遗忘 | 多轮交互但无预算压力 |
| **LongMemEval** (2024) | 多会话时序推理 | 被动评估，agent 不做存储选择 |
| **StoryBench/MemBench** (2025) | 叙事理解中的记忆 | 文学领域，非 agent 场景 |
| **GAIA** (2024) | 通用 AI 助手能力 | 包含记忆但非核心维度 |

**关键空白**：**没有一个 benchmark 同时满足：(1) 预算约束下的存储决策、(2) 记忆更新维护、(3) 可训练的 RL 环境。** 这就是 MemoryBench 的定位空间。

---

## 2. MemoryBench 当前已解决的问题

### 2.1 已建立的核心能力

#### ✅ 问题定义：记忆管理 ≠ 记忆检索

MemoryBench 定义并实现了一个重要区分：**write-time decision quality**（写入时的决策质量）vs read-time retrieval quality（读取时的检索质量）。这是一个真实的、被产业界忽视的问题：

- mem0 的 `store()` 会自动提取事实——但谁来决定**是否该调用 store()**？
- MemGPT 有 tier migration——但**迁移策略**怎么评估、怎么训练？
- A-MAC 提出了 5 维准入信号——但**信号权重**怎么学习？

MemoryBench 的回答：给 agent 一个 write budget，让它在信息流中自主决策存什么、更新什么、丢弃什么，然后通过下游问答测量决策质量。

#### ✅ Anti-hack 验证体系

8 种确定性策略 × 5 模板 × 10 种子 = 400 组验证，55 个不变量全部通过：

| 不变量 | 意义 |
|--------|------|
| guesser = 0% | 不存储不能蒙 |
| smart_guesser < 5% | 统计猜测无效 |
| perfect = 100% | 全存全更新 = 满分 |
| strategic > naive + 10% | 策略性存储优于盲存 |
| priority > random | **存什么**比**存多少**更重要 |
| abstainer < 15% | 全拒答天花板 15% |
| naive update = 0% | 不更新的 agent 在维护轴上零分 |

这个验证体系的价值在于：**任何对评分系统的修改都必须同时通过所有 55 个不变量**，这防止了 benchmark 退化。

#### ✅ 确定性可复现

同一 seed → 完全相同的实体、文档、修正、问题。eval_salt 扰动数值防止预计算答案。这是 benchmark 可信度的基础。

#### ✅ 4 轴评分体系

breadth(0.30) + maintenance(0.25) + reasoning(0.25) + efficiency(0.20) 将记忆管理分解为可解释的子能力，而非单一分数。

#### ✅ 训练数据基础设施（雏形）

- SFT 轨迹生成：5 模板 × 8 策略 × 任意 seeds，OpenAI messages 格式
- MemoryEnv：step/reset 接口，action={tool, args}，reward=答题正确性
- 已与 mem0 兼容的工具接口（store/search/get/forget/list）

### 2.2 已验证的设计决策

| 决策 | 为什么正确 |
|------|-----------|
| 交错流式传输（ingest→correction→question 混合） | 强制增量推理，不能 read-all-then-answer |
| 相同问题措辞（retrieval vs update） | Agent 无法通过措辞区分，必须真正更新记忆 |
| 虚构实体测弃权 | 高覆盖率 agent 对虚构实体自信地说"不知道" |
| trick retrieval | 总是弃权的策略会失败 |
| name+value 联合检测 | 防止 name-only packing 攻击 |

---

## 3. 核心差距分析

### 3.1 与前沿的差距矩阵

| 维度 | MemoryBench 现状 | 前沿标准 | 差距等级 |
|------|-----------------|----------|----------|
| **任务推理深度** | 1-2 步（max/sum/ratio） | 3-5 步多跳推理（REDSearcher treewidth=3） | 🔴 严重 |
| **信息分散度** | 每个 document 包含一个实体的完整信息 | 答案碎片分散在多个源中（REDSearcher dispersion≥3） | 🔴 严重 |
| **RL 训练闭环** | MemoryEnv API 完成，无 RL 算法 | GRPO + mid-training + 模拟环境（REDSearcher/Agent-R1） | 🔴 严重 |
| **奖励设计** | 二值（答对=1，答错=0） | shaped rewards + 过程奖励（存了有用实体即有奖励） | 🟡 中等 |
| **数据真实性** | 纯随机合成（600名×10属性） | Wikipedia + 知识图谱（REDSearcher finewiki） | 🟡 中等 |
| **实体关系** | 纯标量属性 + 类别标签 | 知识图谱（A-Mem 链接、Zep 时序图谱） | 🟡 中等 |
| **训练-评估一致性** | MemoryEnv 用 substring match，评估用 ChromaDB | 同一后端，同一验证逻辑 | 🟡 中等 |
| **课程学习** | lite/standard/hard 三档 | 连续难度谱 + 自适应调整 | 🟢 轻微 |
| **anti-hack** | V14 验证 + 8 策略 baseline | 5 阶段验证（REDSearcher） | 🟢 相当 |
| **评估协议** | protocol.py + per-seed JSON | 标准化 + leaderboard | 🟢 可用 |

### 3.2 最致命的问题：RL 训练不可用

当前 `MemoryEnv` 的问题不是接口设计，而是 **缺乏完整的训练 pipeline**：

1. **无 rollout 收集器**：没有从 MemoryEnv 批量生成轨迹的能力
2. **无 policy model 集成**：MemoryEnv 不与任何 LLM 连接
3. **无 GRPO/PPO 实现**：没有 RL 优化器
4. **无 reward shaping**：只有最终答题正确性，无中间信号
5. **无 curriculum**：不能根据 agent 能力动态调整难度

这意味着：虽然 MemoryBench 声称支持 RL 训练，但实际上只是提供了一个裸的 step/reset 接口。**一个无法闭环训练的 RL 环境等于没有。**

### 3.3 第二严重的问题：任务太简单

当前所有 comprehension 问题都是 1-2 步的简单计算：

```
synthesis:    max(entity_a.revenue, entity_b.revenue)     → 1 步比较
aggregation:  sum(entities_in_category.revenue)           → 1 步聚合
conditional:  filter(revenue > threshold) → max(profit)   → 2 步（筛选+排序）
multi_hop:    best_category(avg_attr1) → best_entity(attr2) → 2 步
ratio:        entity.attr1 / entity.attr2                 → 1 步除法
```

对比 REDSearcher 的 treewidth=3 任务：agent 需要维护多个竞争假设、跨文档合成信息、3-5 步推理链。MemoryBench 的 reasoning axis 名不副实——它测的是简单算术，不是推理。

---

## 4. 战略定位：为什么是"记忆管理"

### 4.1 产业痛点

每个 agent 框架都面临记忆管理问题，但没有人系统性地解决：

```
LangChain/LangGraph → 手动配置 memory policy，无法训练
AutoGPT/CrewAI     → 无限 context 假设，超长对话崩溃
mem0/Zep           → 自动提取，但 agent 不控制存储策略
MemGPT/Letta       → tier 迁移靠 prompting，策略不可学习
```

**核心洞察**：Agent memory 的存储策略应该是一个 **可学习的能力**，而不是一个工程配置。这等价于：

> 操作系统的页面置换策略（LRU/LFU/Clock）是可以通过 workload 特征学习的。LLM agent 的记忆管理策略也是。

### 4.2 独特定位

MemoryBench 的定位不是"又一个 agent benchmark"，而是：

> **Memory Management 领域的 Gymnasium：既是评测标准，也是训练环境。**

这个定位的唯一性在于：
1. **不测检索质量**（那是向量数据库的事）
2. **测存储决策质量**（这是 agent 的事）
3. **提供 RL 训练环境**（这是没人做的事）
4. **与生产记忆系统接口兼容**（mem0 API，零迁移成本）

### 4.3 为什么现在是正确的时机

- GRPO 已被证明是 agent RL 的有效方法（DeepSeek-R1, Agent-R1, WebAgent-R1）
- 模拟环境已被证明可以替代真实环境（REDSearcher, Simia）
- 记忆管理被提升为一等公民（A-MAC, AgeMem, Learn-to-Memorize）
- 但**没有人把这三者结合起来**——RL + 模拟环境 + 记忆管理评测

---

## 5. 架构演进路线

### 5.1 目标架构

```
memorybench/
├── worlds/                     # World 生成（现有，需升级）
│   ├── base.py                 # WorldTemplate ABC + 关系图谱
│   ├── company.py ... sport.py # 5 模板（现有）
│   ├── graph_world.py          # [NEW] 知识图谱式 world（多跳推理）
│   ├── eval_task.py            # Inspect AI 集成（现有）
│   └── eval_scorer.py          # 4 轴评分（现有，需扩展）
│
├── training/                   # [NEW] 训练子系统
│   ├── env.py                  # MemoryEnv（从 training.py 拆出，升级）
│   ├── rollout.py              # [NEW] 轨迹收集器（vLLM batch rollout）
│   ├── reward.py               # [NEW] 奖励函数（outcome + shaped）
│   ├── curriculum.py           # [NEW] 课程学习调度器
│   ├── sft.py                  # SFT 轨迹生成（从 training.py 拆出）
│   └── grpo.py                 # [NEW] GRPO 训练器（或对接 verl/OpenRLHF）
│
├── evaluation/                 # 验证系统（现有）
│   ├── validators.py
│   ├── llm_judge.py
│   └── backend_bench.py
│
├── memory/                     # 记忆后端（现有）
│   ├── budget.py
│   └── backends/
│
├── agents/                     # Agent runner（现有）
│   └── stream_agent.py
│
├── simulation.py               # 系统自测（现有）
├── bench.py                    # CLI（现有）
└── protocol.py                 # 评估协议（现有）
```

### 5.2 三阶段演进

```
Phase 1 (4-6 周)        Phase 2 (6-8 周)         Phase 3 (8-12 周)
─────────────────       ─────────────────        ─────────────────
RL 训练闭环              任务复杂度升级             生产级训练平台
• GRPO 集成              • 知识图谱 World          • 多后端训练
• Shaped rewards         • 多跳推理问题             • 分布式 rollout
• Curriculum learning    • 信息分散度控制           • 论文 + Leaderboard
• 模拟环境对齐            • 真实数据源               • 开源社区
```

---

## 6. Phase 1：RL 训练闭环

### 6.1 核心目标

> 用 GRPO 在 MemoryEnv 上训练一个 3B/7B 模型，使其记忆管理能力显著优于 prompting baseline。

这是项目从"评测工具"变为"训练平台"的关键转折。

### 6.2 设计方案

#### 6.2.1 MemoryEnv 升级

当前 MemoryEnv 的问题和解决方案：

| 问题 | 解决方案 |
|------|----------|
| 搜索是 substring match | 加入轻量 embedding 搜索（sentence-transformers），与评估一致 |
| 只有最终 reward | 引入 shaped rewards |
| 无 episode 统计 | 返回 info 中加入 axis scores、write efficiency |
| 不支持批量 rollout | 环境实例化无状态，支持并行 |
| observation 是原始 dict | 序列化为文本（与 LLM 输入格式一致） |

升级后的接口：

```python
class MemoryEnv:
    def __init__(self, template="company", tier="standard", seed=None,
                 reward_mode="shaped", backend="builtin"):
        ...

    def reset(self, seed=None) -> str:
        """返回文本格式的初始 observation（系统提示 + 第一个事件）"""

    def step(self, action_text: str) -> tuple[str, float, bool, dict]:
        """
        action_text: LLM 生成的文本（包含 <tool_call>）
        返回: (observation_text, reward, done, info)
        info 包含：
          - axis_scores: {breadth, maintenance, reasoning, efficiency}
          - writes_used / budget
          - questions_answered / total_questions
          - correct_count / total_answered
        """

    def get_verifiable_reward(self) -> float:
        """Episode 结束后返回 composite score（GRPO 用）"""
```

关键设计：**action 和 observation 都是文本**，直接兼容 LLM 的 generate 接口。不需要把 LLM 输出 parse 成结构化 action 再传给 env——env 自己 parse tool calls。

#### 6.2.2 奖励设计

```python
def compute_reward(env_state, action, outcome) -> float:
    """
    三层奖励信号，从稀疏到稠密：

    Layer 1 - Outcome reward（必须有，GRPO 的基础）
      episode 结束时：composite_score ∈ [0, 1]

    Layer 2 - Question-level reward（每个 submit_answer 触发）
      correct → +1.0 / total_questions
      incorrect → 0.0

    Layer 3 - Storage reward（每个 memory_store 触发）
      +bonus 如果存储的实体后续被问到
      -penalty 如果浪费了 budget 在不会被问到的实体上
      注意：这需要 oracle 信息，只在训练时可用
    """
```

**为什么 Layer 3 合理**：在 RL 训练中，env 可以访问 oracle 信息（未来的问题列表）来计算 shaped reward。这不等于给 agent 透题——agent 看不到未来的问题，但 reward function 可以。这等价于 Atari 游戏中用"得分增量"作为 shaped reward。

**为什么 Layer 3 需要谨慎**：
- 如果 storage reward 太强，agent 会学到"只存确定会被问到的"，这退化为一个预测问题而非记忆管理
- 解决方案：Layer 3 权重远小于 Layer 1（建议 0.1x），且只在早期训练使用，后期只用 outcome reward

#### 6.2.3 GRPO 集成策略

两个选择：

| 方案 | 优势 | 劣势 |
|------|------|------|
| **A: 对接 verl/OpenRLHF** | 成熟框架，分布式支持，社区维护 | 需要适配 multi-turn agent 格式 |
| **B: 自研轻量 GRPO** | 完全控制，针对 MemoryBench 优化 | 工程量大，需自己处理分布式 |

**建议选择方案 A**，理由：
1. verl（字节跳动开源）已经支持 multi-turn RL（Agent-R1 用的就是类似框架）
2. OpenRLHF 支持 GRPO + vLLM rollout
3. 自研 GRPO 的工程量远超 MemoryBench 的核心价值

集成方式：

```python
# MemoryBench 提供：
# 1. 环境接口（MemoryEnv）
# 2. 奖励函数（compute_reward）
# 3. 轨迹收集器（rollout.py）

# verl/OpenRLHF 提供：
# 1. GRPO 优化器
# 2. vLLM 推理后端
# 3. 分布式训练

class MemoryBenchRolloutWorker:
    """适配 verl 的 rollout worker"""
    def __init__(self, template, tier, seed_range):
        self.envs = [MemoryEnv(template, tier, seed=s) for s in seed_range]

    def rollout(self, policy_model) -> list[Trajectory]:
        """用 policy_model 在 envs 中收集轨迹"""
        trajectories = []
        for env in self.envs:
            obs = env.reset()
            while not done:
                action = policy_model.generate(obs)
                obs, reward, done, info = env.step(action)
            trajectories.append(Trajectory(
                messages=env.get_messages(),
                reward=env.get_verifiable_reward()
            ))
        return trajectories
```

#### 6.2.4 课程学习

```python
class MemoryCurriculum:
    """根据 agent 当前能力动态调整训练难度"""

    STAGES = [
        # Stage 1: 学习基本工具使用
        {"tier": "lite", "templates": ["company"], "reward_mode": "shaped"},

        # Stage 2: 学习存储策略
        {"tier": "standard", "templates": ["company", "research"],
         "reward_mode": "shaped"},

        # Stage 3: 学习跨模板泛化
        {"tier": "standard", "templates": ALL_TEMPLATES,
         "reward_mode": "outcome_only"},

        # Stage 4: 预算压力下的决策
        {"tier": "hard", "templates": ALL_TEMPLATES,
         "reward_mode": "outcome_only"},
    ]

    def get_stage(self, agent_composite_score: float) -> dict:
        if agent_composite_score < 0.30:
            return self.STAGES[0]
        elif agent_composite_score < 0.50:
            return self.STAGES[1]
        elif agent_composite_score < 0.65:
            return self.STAGES[2]
        else:
            return self.STAGES[3]
```

#### 6.2.5 预期成果

| 指标 | Prompting baseline (GPT-4o) | RL-trained 7B | 目标 |
|------|---------------------------|---------------|------|
| Composite | ~40-50% (估计) | ≥55% | 小模型 + RL 超越大模型 prompting |
| Maintenance | ~30% (估计) | ≥60% | RL 学会更新记忆 |
| Efficiency | ~20% (估计) | ≥40% | RL 学会节约 budget |

如果达到这个结果，就证明了：**记忆管理策略是可以通过 RL 训练的，而且 RL-trained 小模型优于 prompting 大模型。** 这是一个有说服力的论文贡献。

### 6.3 Mid-Training 分离（借鉴 REDSearcher）

REDSearcher 的核心洞察：将"原子技能习得"与"交互式执行"分离，可以将 RL 成功率从 5% 提升到 40%。

应用到 MemoryBench：

```
Mid-Training Stage I: 记忆工具使用能力
  - 数据：SFT 轨迹（perfect 策略）
  - 目标：学会 tool call 格式、memory_store/search/forget 的正确用法
  - 不需要策略性——只需要格式正确

Mid-Training Stage II: 信息提取能力
  - 数据：document → 结构化摘要 的配对
  - 目标：从叙事文本中提取 entity name + key attributes
  - 关键能力：决定 document 中哪些信息值得存储

RL Post-Training: 策略性存储决策
  - 环境：MemoryEnv
  - 目标：在 budget 约束下最大化 composite score
  - 此时 agent 已经会用工具、会提取信息，RL 只需学习"存什么"
```

**为什么这很重要**：如果跳过 mid-training 直接 RL，agent 的 rollout 95% 都会失败（不会用工具、不会提取信息），GRPO 几乎学不到有用信号。Mid-training 把 base success rate 提到 ~40%，RL 才有足够的正负样本对比。

---

## 7. Phase 2：任务复杂度升级

### 7.1 核心目标

> 将 reasoning axis 从"简单算术"升级为"多跳图推理"，使 MemoryBench 具备前沿 benchmark 的区分度。

### 7.2 知识图谱式 World

当前 WorldTemplate 的实体是孤立的标量属性包。升级方向：

```python
class GraphWorldTemplate(WorldTemplate):
    """基于知识图谱的 World 生成"""

    def generate_world(self, seed, n_entities, ...):
        # 1. 生成实体（现有逻辑）
        entities = self._generate_entities(...)

        # 2. [NEW] 生成实体间关系
        relations = self._generate_relations(entities, rng)
        # 关系类型：
        #   供应商 → 客户
        #   母公司 → 子公司
        #   竞争对手
        #   合作伙伴
        #   地理邻近

        # 3. [NEW] 信息分散到多个 documents
        documents = self._render_distributed_documents(
            entities, relations,
            dispersion=3  # 每个实体的完整信息分散在 ≥3 个 documents 中
        )

        # 4. [NEW] 生成多跳问题
        questions = self._generate_graph_questions(
            entities, relations,
            treewidth=2  # 推理复杂度控制
        )
```

#### 多跳问题示例

**treewidth=1（线性链）**：
```
Q: "Acme Corp 的最大供应商的年收入是多少？"
推理: Acme.supplier → SupplierX → SupplierX.revenue
需要存储: Acme 的供应商关系 + SupplierX 的收入
```

**treewidth=2（环形依赖）**：
```
Q: "在 Acme Corp 的供应链中，哪个公司既是 Acme 的供应商，
    又是 Acme 最大客户的竞争对手？"
推理: Acme.suppliers ∩ Acme.biggest_customer.competitors
需要存储: Acme 的供应商列表 + Acme 的客户列表 + 客户的竞争对手
```

**treewidth=3（全耦合）**：
```
Q: "在 Acme Corp 的供应链网络中，找到一个公司 X，使得：
    X 是 Acme 的供应商，X 的收入超过 Acme 最大客户的收入，
    且 X 与 Acme 的竞争对手没有合作关系。"
推理: 需要同时维护供应商、客户、竞争对手、合作关系四个维度
```

#### 信息分散

当前：一个 document 包含 entity 的全部 10 个属性。
升级后：

```python
def _render_distributed_documents(self, entities, relations, dispersion=3):
    """
    每个实体的信息分散在 ≥dispersion 个 documents 中。

    Document 1 (关于 Acme): "Acme Corp 报告年收入 $500M..."
    Document 2 (关于 SupplierX): "SupplierX 是 Acme 的主要供应商..."
    Document 3 (行业报告): "科技行业中，Acme 和 BetaInc 是主要竞争对手..."

    Agent 必须从 3 个 document 中拼凑 Acme 的完整画像。
    这让存储决策更有策略性：存哪些碎片？如何组织？
    """
```

**为什么这很重要**：信息分散迫使 agent 做更精细的存储决策。现在是"存不存这个实体"（二元决策），升级后是"存这个实体的哪些属性片段"（连续决策空间）。这更接近真实 agent 系统的挑战。

### 7.3 与 anti-hack 的兼容性

每个新增的问题类型都必须通过已有的 55 个不变量。具体要求：

- guesser 在图谱问题上仍然 = 0%（因为需要具体的实体名和关系）
- smart_guesser 在图谱问题上 < 5%（关系组合爆炸，无法猜测）
- perfect = 100%（全存储 + 全更新 → 所有信息可用）
- 信息分散不能导致 perfect 策略无法达到 100%（必须确保所有碎片都可存储）

### 7.4 真实数据源（可选，Phase 2 后期）

用 Wikipedia 实体替代随机合成，方法借鉴 REDSearcher：

1. 从 Wikipedia dump 中选择结构化实体（公司、城市、人物）
2. 提取真实属性值（收入、人口、出生年份）
3. 用 eval_salt 扰动数值（防止模型靠预训练知识作答）
4. 生成叙事文档（保持现有的 4 种叙事模板）

**为什么可选**：合成数据的优势是完全可控；真实数据的优势是更可信。两者可以共存——合成数据用于训练（快速迭代），真实数据用于最终评估（可信度）。

---

## 8. Phase 3：生产级记忆代理训练

### 8.1 核心目标

> 建立一个完整的 train→eval→deploy 管道，训练出的记忆策略可以直接迁移到 mem0/Zep/LangMem 等生产系统。

### 8.2 多后端训练

当前问题：MemoryEnv 用 substring match，评估用 ChromaDB，训练和评估不一致。

```python
class MemoryEnv:
    def __init__(self, backend="chromadb"):  # 或 "mem0", "zep"
        if backend == "chromadb":
            self.memory = ChromaDBBackend()
        elif backend == "mem0":
            self.memory = Mem0Backend()
        elif backend == "builtin":
            self.memory = BuiltinBackend()  # 当前的 substring match

    # 所有后端实现相同的 MemoryInterface：
    # store(content) -> id
    # search(query, top_k) -> results
    # get(id) -> content
    # forget(id) -> bool
    # list() -> all entries
```

**关键设计**：后端不影响 World 生成、问题生成、奖励计算。只影响 memory_search 的返回结果。这意味着同一个 RL 训练环境可以适配不同的生产系统。

### 8.3 分布式 Rollout

RL 训练的瓶颈是 rollout 收集。MemoryBench 的一个 episode 包含 ~50 个事件（ingest+correction+question），每个事件需要 LLM 推理。一个 episode 的 rollout 需要 ~100 次 LLM forward pass。

解决方案（借鉴 REDSearcher 的异步架构）：

```
┌─────────────────────────────────────┐
│         GRPO Trainer (GPU)          │
│  - Policy update                    │
│  - Advantage computation            │
└─────────────┬───────────────────────┘
              │ 新 policy weights
              ▼
┌─────────────────────────────────────┐
│     vLLM Inference Server (GPU)     │
│  - Batch generation                 │
│  - Prefix caching                   │
└─────────────┬───────────────────────┘
              │ 生成的 actions
              ▼
┌─────────────────────────────────────┐
│   MemoryEnv Workers (CPU, N 并行)    │
│  - 每个 worker 持有一个 env 实例     │
│  - 异步收集 rollout                  │
│  - 计算 reward                       │
└─────────────────────────────────────┘
```

### 8.4 论文定位

建议的论文标题和定位：

> **MemoryBench: Learning Strategic Memory Management for LLM Agents**

**核心贡献**：
1. 定义 Memory Management 为可量化、可训练的 agent 能力（区别于 retrieval quality）
2. 提出 4 轴评分体系 + anti-hack 验证协议
3. 提供 RL 训练环境 + GRPO 集成，证明记忆策略可学习
4. 实验证明 RL-trained 7B 模型在记忆管理上超越 prompting GPT-4o

**投稿目标**：NeurIPS 2026 Datasets & Benchmarks Track 或 ICML 2026

### 8.5 开源与社区

```
Release 1.0:
  - PyPI 包：pip install memorybench
  - 评估协议 + 评分标准
  - 5 个 World 模板
  - MemoryEnv RL 接口
  - 预训练的 memory agent（7B）

Release 2.0:
  - 知识图谱 World
  - 多跳推理题
  - 分布式训练支持
  - Leaderboard（HuggingFace Space）
  - 多后端支持（ChromaDB/mem0/Zep）
```

---

## 9. 技术路线选择与权衡

### 9.1 关键技术决策

| 决策点 | 选项 A | 选项 B | 建议 | 理由 |
|--------|--------|--------|------|------|
| RL 框架 | 对接 verl/OpenRLHF | 自研 GRPO | A | 核心价值在环境和评测，不在 RL 算法 |
| 任务合成 | 知识图谱 + treewidth | 保持现有简单题 | A（Phase 2） | 区分度不够会导致 benchmark 无意义 |
| 数据源 | 合成 + Wikipedia | 纯合成 | 混合 | 训练用合成（快），评估用真实（可信） |
| 后端 | 多后端统一接口 | 只支持 ChromaDB | A（Phase 3） | 生产迁移需要多后端 |
| 模型规模 | 3B/7B | 13B/30B | 3B 先，7B 后 | 证明小模型+RL 的价值 |
| reward 设计 | 纯 outcome | shaped + outcome | shaped 先，pure 后 | shaped 加速早期收敛 |

### 9.2 风险与缓解

| 风险 | 可能性 | 影响 | 缓解策略 |
|------|--------|------|----------|
| RL 训练不收敛 | 中 | 高 | mid-training 提高 base success rate；课程学习降低初始难度 |
| 任务复杂度升级破坏 anti-hack | 中 | 高 | 每次修改都跑 55 个不变量；新题型先过 guesser=0% |
| 社区不采用 | 高 | 高 | 先发论文建立学术可信度；提供预训练模型降低使用门槛 |
| 与现有 benchmark 重叠 | 低 | 中 | 明确差异化：存储决策 vs 检索质量 |
| 评估指标不可信 | 低 | 高 | LLM judge + rule-based 双验证；发布人类评估结果 |

### 9.3 不做的事情

| 不做 | 为什么 |
|------|--------|
| 自研 GRPO 算法 | RL 框架不是我们的核心贡献 |
| 支持所有 agent 框架 | 先做好 mem0 兼容接口，其他框架按需加 |
| 建 real web search 环境 | 那是 REDSearcher 的方向，不是我们的 |
| 做 multimodal memory | 文本优先，多模态是 future work |
| 做 multi-agent memory | 复杂度太高，Phase 3 后考虑 |

---

## 10. 成功标准与里程碑

### Phase 1 完成标准（RL 训练闭环）

- [ ] MemoryEnv 支持文本 action/observation + shaped reward
- [ ] GRPO 训练 pipeline 跑通（verl 或 OpenRLHF 对接）
- [ ] 课程学习从 lite → standard → hard
- [ ] 7B 模型训练后 composite ≥ 55%（超越 prompting baseline）
- [ ] maintenance axis ≥ 60%（证明 RL 学会了更新策略）
- [ ] 所有 55 个 anti-hack 不变量仍然通过
- [ ] 训练一个模型 ≤ 48 GPU-hours（单机 8×A100）

### Phase 2 完成标准（任务复杂度升级）

- [ ] GraphWorldTemplate 生成 treewidth=1,2,3 的多跳问题
- [ ] 信息分散度 ≥ 3（每个实体的信息分散在 3+ documents）
- [ ] 新增 anti-hack 不变量覆盖图谱问题（guesser=0%, smart_guesser<5%）
- [ ] RL-trained 模型在图谱问题上比 prompting 更优
- [ ] 至少 3 个主流模型（GPT-4o, Claude, Qwen）的公开评测结果

### Phase 3 完成标准（生产级平台）

- [ ] 论文被 NeurIPS/ICML 接受
- [ ] PyPI 包发布 + HuggingFace leaderboard
- [ ] 多后端支持（ChromaDB + mem0）
- [ ] 预训练 memory agent 开源（7B，composite ≥ 60%）
- [ ] ≥ 3 个外部团队使用 MemoryBench 评测

---

## 附录 A：MemoryBench vs REDSearcher 对照

| 维度 | MemoryBench | REDSearcher |
|------|-------------|-------------|
| **核心能力测试** | 记忆存储策略（what to store） | 搜索推理策略（what to search） |
| **环境类型** | 信息流接收（被动） | Web 搜索（主动） |
| **预算约束** | 写入次数（write_budget=30） | 搜索次数 / context 长度 |
| **任务合成** | 随机实体 + 属性 | 知识图谱 + dual-constrained |
| **训练方法** | SFT 轨迹（完成）+ RL（待建） | Mid-training + SFT + GRPO（完整） |
| **模拟环境** | MemoryEnv（简单） | 本地 Web 环境（复杂） |
| **竞争优势** | Anti-hack 验证 + 4轴评分 | 规模化 + SOTA 结果 |
| **互补关系** | 记忆管理是搜索的上游能力 | 搜索能力依赖记忆管理 |

**关键洞察**：搜索 agent 的效率瓶颈之一是重复搜索已知信息。如果 agent 能更好地管理记忆（存储有价值的搜索结果、丢弃无关信息、更新过时信息），搜索效率会显著提升。MemoryBench 训练的能力可以直接迁移到 REDSearcher 类系统。

---

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

### Production Systems
- Zep: Temporal Knowledge Graph
- LangMem: LangGraph Integration
- EverMemOS: Engram-Inspired Lifecycle
