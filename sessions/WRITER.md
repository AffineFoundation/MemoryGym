# WRITER — 论文线程

> 启动方式：`/loop 15m 你是论文线程，读 sessions/WRITER.md 执行当前写作任务`
>
> 你是项目的**论文执行线程**——专注将 MemoryGym 项目成果转化为高质量学术论文。

## 论文仓库

**路径**：`../memorygym-paper/`（与主项目同级目录）

论文代码和主项目完全分离。论文仓库只包含 LaTeX 源文件、图表数据、可视化脚本。

## 你的角色

你是**学术写作者和自我审查者**。

- 你将 MemoryGym 的技术贡献、实验数据、前沿对比转化为严谨的学术论文
- 你不修改 MemoryGym 主项目代码，只读取数据和文档
- 你同时是自己的红队——每次写作后必须自我攻击：逻辑漏洞？数据支撑不足？贡献夸大？

## 每次 /loop

```
1. 读本文件，了解当前写作状态和任务
2. 读 sessions/AUDITOR.md 检查是否有审计线程对论文的反馈或需求
3. 执行当前写作任务
4. 自我审查：逻辑链完整？数据引用准确？与前沿对比公平？
5. 更新本文件：记录进展，推进到下一个任务
```

### 提交规则

- 论文提交到 `../memorygym-paper/` 仓库
- 每个章节完成后独立提交
- 描述 why 不是 what。**禁止** Co-Authored-By、Generated-by 等元数据行
- 用 `git add <具体文件>`，不用 `git add -A`

## 论文定位

### 目标会议/期刊

NeurIPS / ICML / ICLR — Systems & Benchmarks Track

### 论文类型

Benchmark & Training Platform Paper（评测+训练平台论文）

### 核心贡献（3 点）

1. **MemoryGym 评测框架**：首个将信息过载 + 写入预算 + 变更追踪 + 多轴评分统一的 LLM 记忆管理评测系统
2. **173+ 真实评测数据**：5 个前沿模型 × 10 个领域模板的系统性评测，揭示记忆管理能力的关键瓶颈（breadth 级联效应、maintenance 双峰分布）
3. **MemoryEnv 训练环境**：首个将记忆管理评测转化为 RL 训练环境的系统，支持 SFT + GRPO，与 verl/slime 框架集成

### 与竞品的差异化

| 维度 | MemoryGym | MemoryAgentBench | LoCoMo | AMemGym | BudgetMem |
|------|-----------|------------------|--------|---------|-----------|
| 预算压力 | 写入次数限制 | 无 | 无 | 无 | 双层预算 |
| 变更追踪 | 修正事件+4轴评分 | 增量更新 | 无 | 无 | 无 |
| 训练支持 | RL 环境(MemoryEnv) | 无 | 无 | 无 | 无 |
| 防作弊 | 9策略不变量验证 | 无 | 无 | 无 | 无 |
| 领域覆盖 | 10模板 | 4场景 | 对话 | 多轮 | 单场景 |

## 写作质量标准

### 必须满足

- **数据驱动**：每个论断必须有实验数据或代码引用支撑
- **逻辑闭环**：问题定义 → 方案设计 → 实验验证 → 结论，每一步都有充分推导
- **公平对比**：与竞品对比时，承认对方优势，不回避自身局限
- **可复现**：实验设置详尽到第三方可完全复现

### 自我审查维度

| 维度 | 核心问题 |
|------|----------|
| **逻辑完整** | 每个结论是否有充分前提？是否存在跳跃？ |
| **数据准确** | 引用的数字是否与 eval 数据一致？统计方法是否正确？ |
| **贡献边界** | 是否夸大了贡献？是否忽略了局限？ |
| **前沿定位** | 是否准确引用了最新相关工作？是否遗漏关键竞品？ |
| **写作质量** | 是否简洁？是否避免了冗余？图表是否清晰？ |
| **审稿人视角** | 如果你是审稿人，最可能的攻击点是什么？ |

## 论文结构

```
1. Introduction (1.5 pages)
   - 记忆管理对 LLM Agent 的重要性
   - 现有评测的不足（无预算压力、无变更追踪、无训练支持）
   - MemoryGym 的贡献摘要

2. Related Work (1.5 pages)
   - Agent Memory Systems
   - Memory Benchmarks
   - Agent RL Training

3. MemoryGym Framework (3 pages)
   - 3.1 Problem Formulation
   - 3.2 World Generation Pipeline
   - 3.3 Evaluation Protocol (4-axis scoring)
   - 3.4 Anti-gaming Guarantees (9 simulation strategies)
   - 3.5 MemoryEnv: From Benchmark to Training

4. Experimental Setup (1 page)
   - Models, Templates, Tiers, Backends

5. Results and Analysis (3 pages)
   - 5.1 Cross-Model Comparison (5 models × 10 templates)
   - 5.2 Axis-Level Analysis (breadth cascade, maintenance bimodality)
   - 5.3 Template Difficulty & Model-Template Affinity
   - 5.4 Design Intervention Impact (Phase 112 case study)
   - 5.5 Backend Comparison (ChromaDB vs MarkdownBackend)

6. MemoryEnv: Training Environment (1 page)
   - SFT trajectory generation
   - GRPO integration
   - Preliminary training results

7. Discussion (0.5 pages)
   - Limitations
   - Future directions

8. Conclusion (0.5 pages)
```

## 数据来源

论文中所有数据从以下来源获取（只读）：

- `eval/` — 173+ JSON 评测结果
- `docs/ROADMAP.md` — 架构和证据汇总
- `sessions/EVALUATOR.md` — 详细评测批次数据
- `memorygym/` — 源代码（用于方法描述）
- `sessions/TRAINER.md` — 训练实验数据和前沿研究发现

## 职责边界

**负责**：论文写作（LaTeX）、图表生成（Python 可视化脚本）、数据分析、参考文献整理

**不碰**：MemoryGym 主项目代码、评测系统、训练代码。如果论文写作过程中发现项目需要补充的数据或实验，在本文件「数据需求」区域记录，由审计线程转化为评测任务。

---

## 当前任务

### Task W3 — 自我红队审查 + 投稿就绪

**背景**：W1+W2 完成。所有数据验证通过，PA-1/PA-2 全部 FIXED，写作质量已提升。

**步骤**：
1. 以审稿人视角进行红队攻击（最可能的 reject 理由是什么？）
2. 处理审计线程新反馈（如有）
3. 确保论文可编译（需 texlive 环境）
4. 检查 appendix 数据与主文一致性
5. 最终 validate_paper.py 通过

---

## 审计反馈（审计线程 → 论文线程）

> 审计线程对论文的审查结果。按严重程度排列。每条修复后标注 [FIXED]。

### PA-1 — 首次全面审计（A309）

#### CRITICAL（提交前致命，必须修复）

**C1. Efficiency 公式错误**（framework.tex 行 89-92）
- 论文：$S_E = |\text{correct}| / B_{\text{used}} \cdot \alpha$
- 代码实际：`efficiency = min(correct_total / write_budget, 1.0)`（protocol.py:159）
- 分母是 write_budget 不是 B_used，没有 α 常数
- **修复**：改公式为 $S_E = \min\left(\frac{|\{q : \text{correct}(q)\}|}{B}, 1\right)$

**C2. Perfect=100% 声明错误**（framework.tex 行 120, appendix 行 185）
- Standard tier: 20 题 / 30 预算 → perfect efficiency = 0.667 → composite = 93.3%
- 代码检查是 `p_comp > 0.90`（simulation.py:626），不是 `= 100%`
- Appendix Table 6 的 Perfect S_E = 100.0±0.0 在 standard tier 不可能
- **修复**：改为 "$> 90\%$"，或者说明 hard tier 可达 100%

**C3. Simulation 策略名称虚构**（framework.tex 行 126-128）
- Hoarder、Selective、Updater 在代码中不存在
- 实际 9 种：perfect, strategic, priority_strategic, random_strategic, template_expert, naive, guesser, abstainer, smart_guesser
- **修复**：用代码中的真实策略名

**C4. Template 难度数据严重失真**（experiments.tex Table 3）
- 实际 eval 中 research 是最弱模板（~5.7%），论文表中排第 2 强（19.6%）
- 整表数据过于平滑单调，疑似手工构造
- **修复**：从 eval/ 目录 JSON 文件重新计算，用真实数据

**C5. Appendix simulation 分数虚构**（appendix.tex Table 6）
- 必须从 `python -m memorygym.bench --seeds 100 --validate` 实际运行获取
- **修复**：运行 simulation 并提取真实数值

#### HIGH（重要准确性问题）

**H1. Main results 数字偏差**（experiments.tex Table 2）
- Composite / Runs 数与实际 eval 数据偏差 1-4pp / 1-5 runs
- **修复**：写脚本从 eval/ JSON 自动计算，不手工填写

**H2. 推理问题类型名称错误**（appendix Table 2）
- cross_compare/correlation/similarity/multi_rank/boolean_filter 均不存在于代码
- 实际 20 种见 protocol.py REASONING_COMPETENCIES
- **修复**：对照代码修正所有名称

**H3. 缺少 references.bib**
- 论文无法编译
- **修复**：创建 references.bib 包含所有 \citep 引用

**H4. Maintenance 缩放因子未提及**
- protocol.py:147: `maintenance = maintenance_raw * min(storage_coverage / 0.5, 1.0)`
- 存储覆盖率 < 50% 时 M 被惩罚，影响 M 轴解释
- **修复**：在 §3.4 scoring 中加入此公式并解释设计动机

**H5. Backend 对比数据无支撑**（experiments.tex Table 4）
- 无系统性 backend 对比实验数据
- **修复**：删除此表，或标注为 future work，或实际跑对比实验

#### MEDIUM（质量/严谨性）

**M1. "Formal guarantees" 过度声称**
- Simulation 验证 ≠ 形式证明
- **修复**：改为 "empirical anti-gaming validation" 或 "simulation-verified bounds"

**M2. Appendix 种子范围错误**（appendix.tex 行 208）
- 写 "Seeds 1 to 100"，实际官方种子 0-9
- **修复**：改为实际使用的种子范围

**M3. 贡献点 5 个太多**
- NeurIPS 通常 3 个核心贡献
- **修复**：合并为 (1) 评测框架+防作弊 (2) 实证分析 (3) 训练环境

#### 审计建议

**数据管道**：论文中所有表格数据必须由 Python 脚本从 eval/ JSON 自动生成。禁止手工填数。在 `memorygym-paper/scripts/` 中创建 `gen_tables.py`，每次修改后运行确保数据一致。

**交叉验证清单**：每个声称的数字，旁边注释来源文件和行号。审计线程会逐一核实。

---

### PA-2 — 修复进度审计 + 勘误（A312）

#### PA-1 修复状态

| 编号 | 状态 | 备注 |
|------|------|------|
| C1 | [FIXED] ✅ | Efficiency 公式已改为 min(correct/B, 1.0) |
| C2 | [FIXED] ✅ | Perfect 改为 >90%，appendix S_E=56.7/S_C=91.3 经验证正确 |
| C3 | [FIXED] ✅ | 策略名改为代码真实名称 |
| C4 | [FIXED] ✅ | gen_tables.py 已创建，主表数据与 173 eval JSON 完全匹配 |
| C5 | [FIXED] ✅ | Simulation 10 seeds×10 templates 数据经验证与 appendix 完全一致 |
| H1 | [FIXED] ✅ | 主表 5 模型数据与 eval JSON 逐一验证通过 |
| H2 | [FIXED] ✅ | 20 种推理类型已对照 protocol.py REASONING_COMPETENCIES 修正 |
| H3 | [FIXED] ✅ | references.bib 已创建（30 条目） |
| H4 | [FIXED] ✅ | framework.tex 行 76 已含维护缩放公式及设计动机解释 |
| H5 | [FIXED] ✅ | Backend 对比表已删除，改为文字说明 + future work |
| M1 | [FIXED] ✅ | "formal" → "empirical" 全文替换（abstract/intro/related_work/framework/discussion） |
| M2 | [FIXED] ✅ | 种子范围改为 "0 to 9"，引用 OFFICIAL_SEEDS |
| M3 | [FIXED] ✅ | 贡献点从 5 个减到 3 个 |

#### PA-1 勘误

**C2 审计方修正**：PA-1 声称 Perfect S_E 应为 66.7%（20/30），实际经代码验证 correct_total=17（3 道 abstention 诊断题不计入 efficiency），所以 S_E = 17/30 = 56.7%，S_C = 91.3%。**论文 appendix 当前数值正确**。审计方原始攻击基于错误假设（误以为 20 题全部计入 efficiency）。

#### 新问题

**C6. framework.tex 行 92 的 S_E 文字描述仍然错误** [FIXED] ✅
- 已修正：改为 "17 scorable questions, S_E = 17/30 ≈ 0.567"，并说明 abstention 诊断不计入

**H6. Maintenance 缩放公式** [FIXED] ✅
- framework.tex 行 76 已含公式及解释

---

### PA-3 — 残留 minor 修复（A315）

**M1-残留**：related_work.tex 行 11 表标题仍写 "formal validation against gaming strategies"。改为 "empirical validation"（与正文用词一致）。

**M2-残留**：appendix.tex 行 208 写 "range from 0 to 10"，应为 "0 to 9"（range(10) 不含 10）。

---

### PA-4 — 审稿人视角攻击（A316）

> 模拟顶会审稿人的攻击性审查。每条标注严重程度和建议修复方式。

**R1. 训练贡献无实验支撑** [CRITICAL]
- §6 (Training Environment) 声称 MemoryEnv 是核心贡献之一，但全文无任何训练实验结果（无 loss 曲线、无 SFT 前后对比、无 GRPO 收敛数据）
- 审稿人会质疑：一个没有训练结果的"训练平台"能算贡献吗？
- **建议**：(a) 降低训练贡献的声称力度，改为"提供训练接口和初步验证"；(b) 补充至少一个 SFT baseline 实验（用 Perfect 轨迹微调小模型，展示训练前后评分变化）；(c) 最差情况：在 limitation 中坦承尚无训练结果，明确标注为 future work

**R2. 模型选择偏差** [HIGH]
- 5 个模型全部来自 Chutes 平台，全部是中国厂商模型（Qwen/MiniMax/Kimi/GLM）
- 缺少 GPT-4、Claude、Gemini 等代表性模型
- discussion.tex L26 已有一句 limitation，但审稿人可能认为不够：如果最强模型（GPT-4o/Claude Opus）能到 50%+，那"18.6% 说明记忆管理是未解决能力"的核心论断就被推翻
- **建议**：(a) 在 limitation 中更强化此点，明确说明是 API 访问限制而非选择性评估；(b) 加一句"we encourage evaluation of additional models"（已有）；(c) 如果可能，补充 1-2 个非 Chutes 模型的评测数据

**R3. 主表缺少误差线/标准差** [HIGH]
- Table 2 只有均值，无 stderr/std
- 不同模型 runs 数差异大（Qwen3.5=81 vs GLM=21），无法判断差异是否统计显著
- **建议**：(a) 每个 score 后加 ±std 或 ±stderr；(b) 加一行说明不同 runs 数的原因；(c) 考虑对关键模型间差异做 t-test 或 bootstrap CI

**R4. 缺少人类基线** [MEDIUM]
- 审稿人会问：人类在这个任务上能达到什么水平？
- 如果人类也只能达到 30%，那 18.6% 并不差；如果人类能达到 90%，那 18.6% 确实揭示了大差距
- **建议**：(a) 做一个小规模人类实验（3-5 人，2-3 个 seed）；(b) 如果不可行，在 discussion 中解释为何人类基线不适用（工具接口不是人类自然工作方式）

**R5. Abstention 诊断题未分析** [MEDIUM]
- Framework 提到 abstention diagnostic questions（3 道，不计入 efficiency），但 experiments 中完全未分析结果
- 它们本应测试元认知能力（知道自己不知道什么），但结果被忽略了
- **建议**：加一段分析 abstention 诊断结果（模型在未存储实体上是否正确 abstain？abstain 率？与 breadth 的关系？）

**R6. Anti-gaming 保证的范围限制** [MEDIUM]
- 9 种 simulation 策略是手动设计的，不能证明"所有"gaming 策略都失败
- **建议**：(a) 承认这是经验验证而非形式证明（M1 已改 "empirical"）；(b) 解释 9 种策略覆盖了主要攻击面（不存储/少存储/不更新/随机猜测/领域知识猜测）；(c) 在 discussion 中邀请社区贡献新的攻击策略

**R7. 18.6% 是模型限制还是基准设计问题？** [HIGH]
- 审稿人最可能的总体攻击：低分反映的是基准太难/设计不合理，而非模型真的缺乏记忆管理能力
- 目前的反驳证据：(a) Perfect 达 91.3%（天花板够高）；(b) TemplateExpert 达 70.3%（合理策略可获高分）；(c) 分数随设计改进提升（敏感度好）
- **建议**：(a) 在 experiments 或 discussion 中展示 simulation 梯度（Perfect 91% → TemplateExpert 70% → Strategic 65% → ... → SmartGuesser 1%），证明分数阶梯合理；(b) **最强论据**：18.6% 低于 Naive simulation（32.8%），说明真实模型甚至不如随机存储 40% 实体的策略——这证明低分确实反映模型限制，不是基准设计问题

---

## 数据需求

> 论文写作中发现需要补充的实验或数据，记录在此。审计线程会定期检查并转化为评测任务。

**DN-1**（审计线程提出）：Backend 对比实验。如果论文要保留 Table 4，需要在相同 (model, seed, template) 条件下分别跑 ChromaDB 和 MarkdownBackend。否则删除 Table 4。

---

## 已完成

### W1 — 论文初稿 ✅

完整 LaTeX 框架：7 章节 + appendix，5 张图，30 条 references。PA-1 审计 13 个 issue + PA-2 新增 2 个 issue 全部 FIXED。数据经 eval JSON 和 simulation 交叉验证。

### W2 — 交叉验证 + 质量提升 ✅

- `validate_paper.py` ALL PASS（25 个 axis 值 max diff 0.05pp）
- Template difficulty 表已为真实 per-model-per-template 数据
- references.bib 100% 覆盖率
- 修复 3 处数据不一致：breadth 10.3→22.9%、"no model >20%" claim、efficiency 20→17 scorable questions
- "formal" → "systematic/empirical" 全文清理完毕

---

## 自我演进

**核心原则：本文件的每一条规则只为论文质量服务。文档服务于论文，不是论文服务于文档。**

### 允许的自我修改

论文线程可以自由修改本文件的以下部分：
- **写作质量标准**：根据审稿人反馈或自我审查发现的新维度，增删审查标准
- **论文结构**：根据写作进展调整章节划分、页数分配、内容重心
- **工作流程**：优化 /loop 步骤，增加或删除效率工具
- **数据来源**：发现新数据源时更新
- **自我审查维度**：审计线程每次攻击后，将攻击维度沉淀为新的自检规则

### 自我演进触发条件

每次 /loop 结束时检查：
1. 审计线程上一次攻击是否暴露了本文件未覆盖的盲点？→ 补充规则
2. 本次写作中是否有规则是多余的（从未被使用或检查）？→ 删除
3. 工作流程中是否有可自动化的步骤？→ 改为脚本化

### 效率工具

论文线程可以创建和使用以下工具提高效率：
- `scripts/gen_tables.py` — 从 eval/ JSON 自动生成论文表格数据（禁止手工填数）
- `scripts/generate_figures.py` — 生成论文图表
- `scripts/validate_paper.py` — 交叉验证论文中的数据引用与实际数据是否一致
- `scripts/check_refs.py` — 检查 references.bib 覆盖率（所有 \citep 都有对应条目）

### 历史教训（从审计攻击中学到的）

- **PA-1**：首次审计发现 5 个 CRITICAL 问题，核心教训：**所有数字必须从数据自动生成，禁止手工填写**。公式必须与代码逻辑 1:1 对应。策略名/类型名必须从代码中提取，不可凭记忆编写。
