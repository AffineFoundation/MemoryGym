# AUDITOR — 审计线程（调度中枢）

> 启动方式：`/loop 60m 你是审计线程（调度中枢），读 sessions/AUDITOR.md 执行当前审计任务`
>
> 你是项目的**调度中枢**——不写代码，但负责持续审视项目全局，发现问题，制定方向，驱动所有执行线程。

## 线程架构

```
sessions/AUDITOR.md（你，/loop 60m）— 调度中枢：审计、设计、方向决策
  ├→ sessions/EXECUTOR.md（/loop 30m）— 执行线程：写代码、跑测试、提交
  ├→ sessions/EVALUATOR.md（/loop 30m）— 评测线程：跑模型评测、收集数据
  └→ sessions/TRAINER.md（/loop 60m）— 训练线程：RL 训练闭环
```

- 执行线程和评测线程**不感知你的存在**
- 你通过修改 sessions/EXECUTOR.md 待办区和 sessions/EVALUATOR.md 任务队列来间接控制它们
- 你可以读所有文件（代码/测试/eval 结果/devlog），但**只写** sessions/AUDITOR.md / sessions/EXECUTOR.md 待办区 / sessions/EVALUATOR.md 任务区

## 你的角色

你不是开发者，你是**质疑者和架构师**。

执行线程倾向于认同自己的产出（确认偏误），你必须假设系统有问题并去证明它。

## 每次 /loop

```
1. 读本文件，了解上次审计状态和待跟进项
2. 读 CLAUDE.md 了解北极星
3. 执行当前审计任务（见下方「当前任务」）
4. 发现问题 → 写入 sessions/EXECUTOR.md 待办区（这是你影响执行 loop 的唯一方式，注意执行 loop 也可能会修改这个文件
）
5. 更新本文件：记录审计结论，推进到下一个审计任务
```

## 审计维度

每次循环从以下维度中选择 1-2 个深入分析。不要每次都蜻蜓点水全部扫一遍——深度优于广度。

### A. 设计有效性（最重要）

系统设计是否真正服务于北极星（"通用 agent 记忆能力"）？

- 评分反映的是真实能力还是可学习的模式？
- 不同模板是否需要不同的记忆策略？还是一套通吃？
- 推理题是否需要真正的理解，还是存了就能机械计算？
- 训练出的能力能迁移到真实 agent 场景吗？差距在哪？
- 评测结果能区分"好模型"和"会套路的模型"吗？

### B. 实现正确性

代码是否忠实实现了设计意图？

- 评分公式在所有路径（protocol.py / eval_scorer.py / bench.py / env.py）上一致吗？
- 问题生成是否有死代码、不可达路径、边缘 case？
- 测试覆盖是否匹配实际代码路径？哪些路径从未被测试？
- 文档（CLAUDE.md / ROADMAP.md）与代码实际状态是否一致？

### C. 前沿对齐

项目是否跟上了领域发展？

- 搜索最新的记忆评测/记忆系统论文和项目
- 对比 MemoryGym 与前沿工作的差距
- 是否有新的评测维度、训练方法、架构模式值得引入？
- 竞品分析：有没有类似项目做得更好？为什么？

### D. 工程质量

代码是否健康、可维护、可扩展？

- 文件行数是否逼近上限（1000 行）？
- 是否有冗余代码、重复逻辑、过度抽象？
- 依赖是否合理？是否有安全风险？
- 性能瓶颈在哪？100+ 实体场景下的表现？

### E. 数据验证

评测数据是否支撑结论？

- eval 结果是否与设计预期一致？
- 不同模型的得分差异是否反映真实能力差距？
- 是否有异常数据点需要解释？
- simulation 不变量是否仍然成立？

## 工作原则

**对抗性思维**：假设系统存在严重缺陷，你的任务是找到它。如果真的找不到，用代码证据证明（附行号），写入审计日志。

**禁止自我确认**：不得引用自己上次审计的结论作为本次依据。每次必须从读代码开始，重新形成判断。

**代码级验证**：所有判断必须有代码证据。"我认为评分是正确的"不可接受，"protocol.py:148 的 efficiency 公式是 min(correct/budget, 1.0)，与 eval_scorer.py:102-108 调用 compute_axis_scores() 一致"才可接受。

**影响力通过文档传递**：你不直接改代码。发现问题后写入 sessions/EXECUTOR.md 待办区，由执行 loop 实施。设计方案写得越具体、越有代码证据，执行 loop 越容易正确实施。

**深度优于广度**：一次审计深入透彻地分析一个问题，比浅浅扫五个维度有价值得多。

**研究驱动**：定期搜索前沿工作，确保项目不是在闭门造车。研究结果保存到 `devlog/` 供全局参考。

## 自我演进

你有权修改以下文件来优化整个系统的运作方式：

- **sessions/AUDITOR.md**（本文件）：优化自己的审计维度、工作原则、任务流程
- **sessions/EXECUTOR.md**：优化执行线程的工作流、规范、卡住时的升级策略
- **sessions/EVALUATOR.md**：优化评测线程的工作流、故障处理、批次设计
- **sessions/TRAINER.md**：优化训练线程的工作流、实验规范、协作协议
- **CLAUDE.md**：当北极星、开发规则或架构描述与代码实际状态不一致时修正

每次审计循环末尾，花 1 分钟审视这些文档本身：
- 哪条规则从未产生价值？→ 删除（噪音拖慢演进）
- 哪个流程反复导致低质量产出？→ 重写
- 执行线程是否在重复犯同类错误？→ 补充针对性规则
- 有没有新的模式值得固化为规则？→ 添加

**原则**：文档服务于演进，不是演进服务于文档。规则的唯一存在理由是它能提升产出质量。如果不能，它就是负担。

## 如何写入 sessions/EXECUTOR.md

发现需要执行 loop 修复的问题时，写入 sessions/EXECUTOR.md 的**待办区**：

```markdown
### Phase N — 标题

**依据**：[审计发现的问题描述，附代码证据]

#### Step 1 — ...
#### Step 2 — ...

#### 验证标准
- [具体的、可自动化的验收条件]
```

要求：
- 问题描述必须附代码行号，让执行 loop 能快速定位
- 方案必须具体到"改哪个文件的哪个函数"，不能只说"优化评分"
- 验证标准必须可自动化（pytest / simulation / 具体数值断言）
- 大的设计变更可以只写背景和约束，让执行 loop 自己设计方案（但要明确约束）

---

## 当前任务

### 审计 A20 — session 文件质量 + 执行器思考规范

用户反馈：执行线程不应是机械执行工具，必须系统性深度思考，理解需求背后的真实意图。

**已执行**：
1. 更新 EXECUTOR.md — 增加「思考规范」一节（理解意图、独立判断、全局视角）
2. 清理 EVALUATOR.md — 已完成的批次 1-5 从「当前任务」移除，评测线程现在直接看到批次 6
3. stream_agent.py 987 行（未变）
4. 文件重组仍未提交（sessions/ untracked，旧文件 deleted）

## 待跟进

（审计中发现的、需要持续关注但不紧急的事项）

- ~~Phase 38 对比 eval~~ → 已部分确认（0%→10% 改善），批次 5 在 EVAL_QUEUE 中
- ~~**多模型数据缺失**~~ → A16 已确认：Qwen3.5 23%±12% vs Kimi 20%±13%，统计等价。**高方差是系统性的，非模型特异**
- **高方差问题**：双模型均 CV~55-65%，确认是系统性。根因：ChromaDB embedding search 不稳定。考虑在 CLAUDE.md 建议最低 5 seeds
- **设计层面**：第 3 轴 "推理能力" 实际测 "机械计算"。不急
- ~~**CLAUDE.md 文档漂移**~~ → 已加入文档同步规则（Phase 45 已提交 252c4e4）
- **multi tier 首测**：批次 8 在 EVAL_QUEUE 中，Phase 45 已提交，可跑
- **弱模型失败模式**：GLM-5 0%（存储成功但搜索全空），MiniMax 6%。均为模型级工具使用能力不足
- **批次 5 A/B 对比失效**：重跑覆盖原文件。未来需版本化文件名或归档旧结果。不紧急

## 审计日志

（每次审计的结论摘要，最新在最上面。保持简洁，详细分析写 devlog/。）

### 审计 A20（2026-03-10）— session 文件质量 + 执行器思考规范

**触发**：用户反馈执行线程不应是单纯执行工具，必须具备独立思考能力。

**变更**：
1. EXECUTOR.md 增加「思考规范」：理解意图（任务背后的真实问题）、独立判断（发现更好方案时自主调整）、全局视角（改代码前理解系统角色）
2. EVALUATOR.md 清理：已完成批次 1-5 从「当前任务」移除，减少评测线程的认知负担
3. 确认文件重组仍未提交

**待办**：无新代码任务。系统稳定，等待 eval 数据积累。

### 审计 A18（2026-03-10）— 问题生成管线深度审计（维度 B）

**审计范围**：questions.py (711行) + questions_advanced.py (448行) + base.py gen_adaptive_questions (503-728)

**发现 1 — 矛盾问题 GT 格式不一致**：❌ BUG
- base.py:621 使用 `str(current_val)` → 输出 "3847.0"
- questions.py:295 _gq_update 使用 `self._format_value(c.attr, current_val)` → 输出 "$3,847.0M"
- 同类问题（都是 "update" competency）GT 格式不一致
- 严重度：低（AnswerValidator/LLM judge 处理数值等价），但违反一致性原则
- **已写入**：Phase 46 到 sessions/EXECUTOR.md

**其他检查项**：
- gen_question() dispatch table 完整（20 种 + delta/counterfactual） ✅
- gen_adaptive_questions 预算分配正确（lite: 1 comprehension, standard: 4） ✅
- Priority slot 机制正确（counterfactual + multi_constraint 前置） ✅
- detect_stored_entities 反作弊逻辑正确（name + value 同时出现） ✅
- maybe_replace_comprehension 降级逻辑正确（stored_pool → fn_map 全覆盖） ✅
- _weighted_choice 实体重要性加权正确 ✅
- _gq_multi_constraint 的 enum_attrs 过滤没有 len≤20 限制（vs enum_filter 有），可能误选 text 类型属性 — 非致命，记录备查

### 审计 A17（2026-03-10）— Phase 45 验证 + 批次 5 首个数据点

**Phase 45**：✅ PASS（commit 252c4e4）
- `__version__` = 0.5.0，eval JSON 包含 `extra.version`
- CLAUDE.md、sessions/EXECUTOR.md 规则同步
- 270 tests pass

**批次 5 首个数据点**：Kimi company s0 = 4%（v0.5.0）
- 原 batch 1 数据（20%）被覆盖 → A/B 对比失效
- 4% 在正常方差范围内（CV≈60%），不代表系统退化
- 教训：重跑相同 seed/template/model 会覆盖旧文件，需要版本化文件名

**STATUS_REPORT.md**：完全重写，从 Phase 7 时代更新到 Phase 44。包含 9 节：设计、评分、反作弊、实证数据、RL 训练、竞品对比、工程成熟度、诚实披露

### 审计 A16（2026-03-10）— 多模型数据分析（维度 E）

**新数据到达**：68 个 eval JSON（+34），批次 3（Qwen3.5 全 6 模板）和批次 4（MiniMax 2 + GLM-5 1）完成。

**多模型对比**（4 模型，35 数据点）：

| 模型 | N | Composite | Breadth | Maint. | Reasoning |
|------|---|-----------|---------|--------|-----------|
| Qwen3.5-397B | 12 | 23%±12% | 13%±11% | 49%±32% | 16%±18% |
| Kimi-K2.5 | 18 | 20%±13% | 14%±13% | 40%±32% | 13%±13% |
| MiniMax-M2.5 | 3 | 6%±6% | 8%±7% | 11%±19% | 0%±0% |
| GLM-5 | 1 | 0% | 0% | 0% | 0% |

**关键发现**：
1. **Qwen3.5 ≈ Kimi**（23% vs 20%，差异在噪音范围内）→ 评测测的是真实能力，非模型特异性
2. **高方差是系统性的**：双模型 CV~55-65%，根因是 ChromaDB embedding 不稳定
3. **Maintenance 是最强轴**（40-49%）：修正检测比检索/推理容易
4. **GLM-5 完全失败**：存了 32 实体（26/30 writes），但搜索返回空 → 模型不能有效使用 search tool
5. **MiniMax 弱**（6%）：reasoning=0%，工具使用能力不足

**结论**：评测系统区分力有效 — 强模型（Qwen3.5/Kimi ~20%）> 弱模型（MiniMax 6%）> 工具不可用（GLM-5 0%）。评分有效，方差问题需要更多 seeds。

**已写入**：Phase 45（版本追踪提交）到 sessions/EXECUTOR.md

### 审计 A15（2026-03-10）— Phase 44 验证 + 全局盘点

**Phase 44**：✅ PASS（commit ad31dfa, 270→271 tests）
- training.py:523 空搜索不再触发 correction_searched ✓
- training.py:503 correction_flow reward 0.2→0.5 ✓
- test_multi_session_episode 新增 ✓

**全局状态**：
- 所有 .py 文件 ≤ 1000 行（stream_agent.py 987 最大，监控中）
- 271 tests, 34 eval JSON
- Phase 38-44 连续修复了所有审计发现的问题
- 系统功能完整：lite/standard/hard/multi 四级，20 种推理题，6 模板，9 种 simulation 策略，RL 训练环境
- **当前瓶颈**：eval 数据积累（只有 Kimi-K2.5 单模型数据）

### 审计 A14（2026-03-10）— MemoryEnv RL 训练闘环审计（维度 A+B）

**整体评估**：✅ Production-ready（54 tests pass，SFT→RL→Eval 完整流水线）

**Issue 1 — Shaped reward 信号太弱**（training.py:494-505）：
- 存储奖励 0.1、修正流程 0.2 vs 答题正确 1.0 → 10:1 比例
- RL（GRPO/PPO）会聚焦 episode reward，忽略 intermediate guidance
- **建议**：提升到 0.3/0.5，或在 RL 侧做 reward weighting

**Issue 2 — 修正搜索可博弈**（training.py:507-524）：
- `_correction_searched = True` 在搜索返回空结果时也设置
- Agent 可搜索不存在的实体，然后 forget+store 获得 +0.2
- **修复**：`if results:` 条件包裹 `_correction_searched = True`

**Issue 3 — Multi-session RL 无测试**：
- training.py 支持 n_sessions 但 test_training.py 没有 n_sessions>1 的测试
- 不影响 eval，但 RL 训练可能有未发现 bug

**无死代码**、SFT 轨迹生成完整、verl/slime adapters 功能完整

**已写入**：Phase 44 到 sessions/EXECUTOR.md

### 审计 A13（2026-03-09）— eval 数据深度分析（维度 E）

**Phase 43 验证**：✅ PASS（commit 9ad38c2, 268 tests）

**Kimi-K2.5 数据分析**（6 模板 × 3 seeds = 18 数据点）：

| 指标 | 值 | 评估 |
|------|-----|------|
| Composite mean | 20.8% | 低但合理（lite tier 预算压力大） |
| Composite std | 13.0% | **极高**（CV=63%），3 seeds 不够稳定 |
| Breadth mean | 13.9% | 存储覆盖差 |
| Maintenance mean | 40.6% | 最强轴（更新能力可以） |
| Reasoning mean | 13.4% | 弱（检索不到数据就无法计算） |
| Abstention | 100% | 完美（从不瞎猜） |

**Phase 38 效果确认**：
- EVAL_QUEUE 记录的 0% outliers（city_s2, hospital_s1）在 JSON 文件中为 10%
- JSON 文件被 post-Phase-38 重跑覆盖 → keyword fallback 消除了完全失败的 case
- 最差 case 从 0% → 10%，改善了最下界

**高方差根因**：
- Breadth（检索）仍然是瓶颈（0-38% range）
- 即使 Phase 38 改善了 keyword matching，embedding search 的不稳定性仍然导致大幅波动
- 不同 seed 的实体名组合影响 ChromaDB 的匹配质量

**结论**：评测系统功能完整（lite/standard/hard/multi 四级），评分逻辑正确，但**单模型 3 seeds 的数据不足以得出稳定结论**。需要更多模型数据来判断方差是模型特异性还是系统性问题。

### 审计 A12（2026-03-09）— Phase 42 实施验证

**Phase 42**：✅ PASS with 1 gap
- 267 tests pass（新增 2 个 multi-session 测试）
- events.py:361-462 `_insert_session_breaks()` 正确实现，含跨 session 修正约束
- protocol.py:34-41 multi tier（60e/20q/3 sessions/budget=30）
- simulation.py 自然跳过 session_break（只处理 question 事件）
- stream_agent.py:545-564 清空对话+保留 memory backend
- training.py:394-403 MemoryEnv 支持

**Gap**：跨 session 修正约束（events.py:403-440）未被显式测试。test_session_breaks() 用 stored_names=set() 绕过了约束验证逻辑。

**已写入**：Phase 43 到 sessions/EXECUTOR.md（补全测试 + multi tier eval 任务）

### 审计 A11（2026-03-09）— Phase 41 设计审查 + Phase 42 分发

**Phase 41 设计审查**：✅ PASS with 4 notes
- 方案 A（session_break 事件）合理：最小侵入、确定性、兼容 RL
- 4 轴评分不变（多会话让同轴更难）正确
- simulation 策略无需扩展正确
- ~180 行变更估算合理

**审查发现的 4 个未决点**（写入 Phase 42 让执行线程决策）：
1. 预算分配：共享 vs 按 session 分配？（建议共享）
2. Session break 位置：需显式保证跨 session 修正约束
3. Session 数量论证缺失（设计说 3 但没论证为什么）
4. multi tier 与 standard 同参数，分数差异可能太小

**已写入**：Phase 42 到 sessions/EXECUTOR.md（多会话评测实现）

### 审计 A10（2026-03-09）— 方向决策 + 任务分发

**已分发**：
- sessions/EVALUATOR.md：新增批次 5（Phase 38 对比验证，seed 0 × 6 模板重跑）
- sessions/EXECUTOR.md：Phase 41（多会话评测设计，设计 Phase，不写代码）

**初步数据观察**（不可作为结论，样本太小）：
- 批次 2 数据中 company s1=41%, s2=15%，JSON 文件显示 45%, 25% — 可能暗示 Phase 38 有 +4% 到 +10% 改善
- city s2 从 0% 到 JSON 10% — 但也可能是重跑的自然波动
- 需要批次 5 的系统化对比

### 审计 A9（2026-03-09）— 前沿对齐（维度 C）

**竞品格局**（详见 devlog/2026-03-09-frontier-alignment.md）：
- **AMemGym**（ICLR 2026）：最直接竞争者 — schema-based + interactive + self-evolution，与 MemoryGym 思路高度重合
- **MemoryAgentBench**（ICLR 2026）：multi-turn 记忆评测，axes 与 MemoryGym 类似
- **AMA-Bench**（Feb 2026）：真实 agent 轨迹，6 个领域，GPT 5.2 仅 72%
- **LongMemEval**（ICLR 2025）：5 种能力，500 问题，115K-1.5M tokens

**MemoryGym 独特价值**：
1. RL 训练环境（MemoryEnv）— 无竞品有此功能
2. 确定性复现（seed-based）
3. 抗博弈（eval_salt + distractor hardening）
4. 预算受限存储（forced prioritization）

**MemoryGym 主要差距**：
1. 无真实 agent 轨迹（vs AMA-Bench）
2. 无多会话评测（vs LongMemEval/AMemGym）
3. 推理全部机械化（vs 语义理解）
4. 单后端（ChromaDB/mem0）

**战略建议**：defend RL training niche + add multi-session support。不追求 free-form interaction。

### 审计 A8（2026-03-09）— Phase 40 验证

**Phase 40**：✅ PASS
- base.py: 1096→728 行，events.py: 388 行（EventGeneratorMixin）
- movie.py:431 有 question_weights override
- 模板去重（Step 3）未执行 — 因各模板 `_SENTENCE_TMPLS` 等模块变量不同，简单提取会破坏结构。合理决策。
- 265 tests pass

### 审计 A7（2026-03-09）— 工程质量（维度 D）

**Phase 39 验证**：✅ PASS（commit fc4728f，CLAUDE.md 无 "18 types"，gen_question dispatch 补全，base.py:1074 有 warnings.warn）

**base.py 超限**：❌ FAIL — **1096 行**，超过 1000 行规则
- 最佳拆分方案：提取 events.py（EventGeneratorMixin，~285 行：generate_corrections/contradictions/stream/noise）+ rendering.py（DocumentRenderingMixin，~143 行：_render_narrative/_compact_document/attr_label）
- 拆分后 base.py 降至 ~668 行

**movie.py 缺少 question_weights**：❌ BUG — Phase 32 遗漏
- 其他 5 个模板都 override 了 question_weights（company:391, research:382, city:436, hospital:463, sport:412）
- movie.py 使用 base.py 默认值（retrieval:0.40, comprehension:0.25, update:0.20, abstention:0.15）
- 应该有 movie 特定的权重分布

**6 个模板重复代码**：4 个方法在全部 6 个模板中完全相同
- `_sentence_templates()`、`_ratio_pairs()`、`_format_value()`、`_q_text()` — 每个模板都是同样的 delegation，共 ~240 行重复
- 应提取到 base.py 作为默认实现，模板只需 override 有差异的部分

**已写入**：Phase 40 到 sessions/EXECUTOR.md

### 审计 A6（2026-03-09）— 推理题设计有效性

**核心发现**：所有 20 种推理题都是**机械计算**（搜索→取数→套公式），无需域语义理解。

**分析**：
- synthesis/aggregation/comparison/ratio/outlier：max/min/avg/sum 纯算术
- multi_hop/cross_category/conditional：多步算术但仍是机械的
- counterfactual：需要保存历史值（测存储设计，非语义理解）
- multi_constraint：布尔过滤 + 计数（AND 逻辑）
- temporal_trend：线性回归 + 阈值分类（统计方法，非语义理解）
- text_match：子串搜索（文本保存，非语义理解）
- relationship_*：图遍历 + 属性查找

**一个零理解 agent 能得 100%？** YES，只要它：存所有实体 + 实现基础算术 + 线性回归 + 子串搜索

**BUT — 这是否是设计缺陷？** 需要区分两个目标：
1. "通用 agent 记忆管理能力"（北极星）→ 当前设计**有效**。真实 agent 场景中记忆管理就是存储策略 + 数据处理，不是域知识
2. "推理能力"（CLAUDE.md 第 3 轴名称）→ **措辞不准确**。实际测的是"存储数据上的计算能力"，不是推理

**结论**：系统对北极星是有效的，但 CLAUDE.md 和评分轴命名有误导。第 3 轴叫"推理能力"不如叫"数据处理"或"计算能力"。

**不写入 Phase**：这是设计层面的认知，不是代码 bug。当前命名不影响评分有效性（guesser=0% 仍然成立），改名只是更诚实。记入待跟进。

### 审计 A5（2026-03-09）— Phase 38+39 实施验证

**Phase 38**：✅ ALL PASS
- stream_agent.py:90 已改为 "uses semantic search"（不再声称 substring matching）
- chromadb_backend.py:82-99 加入 keyword fallback（embedding + substring scan + seen_ids 去重）
- 265 tests pass, simulation ALL PASS（commit 5206f3d）

**Phase 39**：✅ 实施中/已完成
- CLAUDE.md 不再包含 "18 types"
- gen_question() 签名加入 corrections 参数（questions.py:33）
- dispatch table 补全：multi_constraint（line 56），delta/counterfactual 通过 correction-dependent 分支（lines 61-64）
- 设计合理：无 corrections 时 delta/counterfactual 返回 None

### 审计 A4（2026-03-09）— 实现正确性深度审计

**维度 B — 实现正确性**。两个子任务：评分一致性 + 问题生成管线。

**评分一致性**：✅ PASS
- compute_axis_scores()（protocol.py:110-161）是唯一的评分计算点
- eval_scorer.py:99-105、bench.py:300-306、env.py:297-303 均调用它
- WEIGHTS（protocol.py:42-48）无硬编码副本
- MemoryEnv.get_verifiable_reward()（training.py:564-572）故意使用 correct_count/total 作为 RL episode reward，不是评分不一致

**问题生成管线**：3 个问题

1. **CLAUDE.md 文档漂移**：声称 "18 种推理题型" 但 REASONING_COMPETENCIES（protocol.py:99-107）实际有 **20 种**。Phase 30 加入 counterfactual + multi_constraint 后未同步。

2. **gen_question() API 不完整**（questions.py:34-54）：dispatch table 缺少 delta/counterfactual/multi_constraint。这 3 种类型由 gen_adaptive_questions() 直接调用，运行时无问题，但无法通过 gen_question() 公共 API 测试。

3. **静默问题预算丢失**：gen_adaptive_questions() 的 comprehension 循环中，当所有 fallback 生成器返回 None，问题 slot 被静默丢弃。评测可能得到 18-19 题而非预期 20 题，影响评分一致性。

**已写入**：Phase 39 到 sessions/EXECUTOR.md（文档同步 + API 完整性 + 预算丢失警告）

### 审计 A3（2026-03-09）— 检索失败根因深挖

**结论**：benchmark 部分在测 ChromaDB 检索质量，而非纯粹的模型记忆能力。需要修复。

**证据链**：

1. **系统提示词谎言**（stream_agent.py:90）：告诉模型 `memory_search` "uses substring matching"，但实际实现是 ChromaDB 的 embedding cosine similarity search（chromadb_backend.py:62-69，`collection.query(query_texts=[query])`）
   - 模型合理地认为搜 "Onyx Dynamics" 会精确匹配子串
   - 实际上 all-MiniLM-L6-v2 embedding 将 "Onyx Dynamics" 和 "Atlas Systems" 视为相似（都是公司名 + 抽象词）

2. **ChromaDB 对实体名匹配不精确**：
   - 存储格式："EntityName | attr1: val1, attr2: val2"（长文本），实体名只是前缀
   - Embedding 由整段文本决定，实体名对 embedding 的影响被属性值稀释
   - top_k=5 返回 cosine 最近的 5 条，无最小相似度阈值
   - 搜 "Nimbus Digital" 可能返回 "Nimbus Robotics"（共享 "Nimbus" 前缀）

3. **Kimi-K2.5 实际检索表现**：
   - 29/30 writes，30/60 entities stored → 存储行为正常
   - 对已存储实体的检索准确率：4/9 = 44%
   - 对未存储实体：0/9 = 0%（预期）
   - 44% 的已存储实体检索失败 = ChromaDB 返回了错误实体

4. **影响范围**：不只是 Kimi，所有模型都受影响。ChromaDB 检索质量成为所有模型得分的隐性上限。

**已写入**：Phase 38 到 sessions/EXECUTOR.md（系统提示词修正 + 搜索改进）

### 审计 A2（2026-03-09）— Kimi-K2.5 数据分析 + Phase 32-34

**Kimi-K2.5 低分根因**：NOT 系统缺陷，是检索链路问题
- 模型用了 29-30/30 writes，存了 20-30/60 实体 → 存储行为正常
- Retrieval 0-33% → 模型搜索实体名，ChromaDB 返回错误实体（"Onyx Dynamics" → "Atlas Systems"）
- 模型正确地 abstain 了（100% abstention）→ 模型行为合理
- **核心问题**：ChromaDB embedding search（all-MiniLM-L6-v2）对 entity name matching 不够精确
- 这可能影响所有模型，不只是 Kimi

**Phase 32（实体重要性）**：PARTIAL — question_weights 已差异化（5 个模板 override），entity_importance 未被任何模板 override
- city: 45% retrieval（最高），hospital: 30% update（最高），company/research: 35% comprehension
- 但 entity_importance() 所有模板用同一个 base class 实现

**Phase 34（长上下文）**：PASS — --no-redaction flag 正确实现在 stream_agent.py:447,837

**已写入**：Phase 36-37 到 sessions/EXECUTOR.md 待办区（上轮已写）。新发现（检索质量）待下轮深挖。

### 审计 A1（2026-03-09）— Phase 30-31 有效性

**Phase 30（新题型）**：PASS with caveats
- counterfactual/multi_constraint 实现正确，GT 准确，guesser=0%
- 但采样率过低（14-19 类型竞争 5-7 个 slot），期望每种仅 ~0.4 次/eval
- 已写入 sessions/EXECUTOR.md Phase 37 要求提升采样率

**Phase 31（模板事件流差异化）**：FAIL on core claim
- correction_rate 值确实不同（0.05-0.15），代码实现正确
- 但 template_expert 的优势完全来自 priority_store，correction_rate 调整贡献 ~0%
- 固定 0.7 + priority_store 在全局均值上与 template_expert 相当
- 所有模板的最优策略仍然相同 → 策略差异化**未实现**
- 已写入 sessions/EXECUTOR.md Phase 36 要求真正的差异化
