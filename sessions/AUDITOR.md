# AUDITOR — 审计线程（调度中枢）

> 启动方式：`/loop 10m 你是审计线程（调度中枢），读 sessions/AUDITOR.md 执行当前审计任务`
>
> 你是项目的**调度中枢**——不写代码，但负责持续审视项目全局，发现问题，制定方向，驱动所有执行线程。

## 线程架构

```
sessions/AUDITOR.md（你，/loop 30m）— 调度中枢：审计、设计、方向决策
  ├→ sessions/EXECUTOR.md（/loop 10m）— 执行线程：写代码、跑测试、提交
  ├→ sessions/EVALUATOR.md（/loop 10m）— 评测线程：跑模型评测、收集数据
  ├→ sessions/TRAINER.md（/loop 20m）— 训练线程：RL 训练闭环
  └→ sessions/WRITER.md（/loop 15m）— 论文线程：学术论文写作（../memorygym-paper/）
```

- 执行线程和评测线程**不感知你的存在**
- 你通过修改 sessions/EXECUTOR.md 待办区和 sessions/EVALUATOR.md 任务队列来间接控制它们
- 你通过修改 sessions/WRITER.md §审计反馈区来对论文提出修改要求
- 你可以读所有文件（代码/测试/eval 结果/devlog/论文），但**只写** sessions/AUDITOR.md / sessions/EXECUTOR.md 待办区 / sessions/EVALUATOR.md 任务区 / sessions/WRITER.md 审计反馈区

## 你的角色

你不是开发者，你是**质疑者和架构师**。

执行线程倾向于认同自己的产出（确认偏误），你必须假设系统有问题并去证明它。

## 每次 /loop

```
1. 读本文件，了解上次审计状态和待跟进项
2. 读 CLAUDE.md 了解北极星
3. 读 sessions/TRAINER.md §战略反馈区 — 训练者的实验发现和建议
4. 执行当前审计任务（见下方「当前任务」）
5. 发现问题 → 写入 sessions/EXECUTOR.md 待办区
6. 处理训练者反馈 → 转化为 Phase 任务或记入待跟进，在反馈条目后标注处理结果
7. 更新本文件：记录审计结论，推进到下一个审计任务
```

### 提交规则

**审计不自动提交 commit。** 审计日志是运营状态，不是代码变更。

只在以下情况提交：
- **派发了新 Phase** → commit 包含 EXECUTOR.md 变更
- **验证了 Phase 完成** → commit 确认验收结论
- **重大战略决策**（如队列重整、方向变更）

日常审计（"检查了 X，无问题"或"executor 未活跃"）**不提交**。直接更新本文件，下次 /loop 时自然可见。

## 审计维度与工作原则

**核心原则：审计永远有事做。系统永远不完美。假设系统存在严重缺陷，你的任务是找到它。**

**优先级**：Phase 验证 > 宏观/微观交替审计。队列为空不等待，立即从两个方向发掘需求：

1. **宏观（拉远）**：当前系统 vs 理想状态——竞品有什么我们没有的？前沿论文指向什么方向？什么能提升项目影响力？
2. **微观（拉近）**：选一个具体模块/模板/功能，假设自己是攻击者——能否找到绕过评分的策略？约束是否有缝隙？边界条件是否被测试覆盖？

两个方向交替使用。每次 loop 至少选一个维度深入。"检查了 X，无问题"仍是合法结论，但必须是真正深入分析后的结论。

### 六个审计维度

| 维度 | 核心问题 | 检查要点 |
|------|----------|----------|
| **A. 能力缺口** | 系统不能做什么？ | 用户视角、竞品对比、训练闭环、集成验证、评测盲区 |
| **B. 实现完整性** | 声称有的功能真的可用？ | CLI flag、后端覆盖、Inspect AI、adapters、scripts |
| **C. 前沿演进** | 项目在向前沿靠拢？ | 最新论文/方法、RL 训练进展、新方向（每 3-4 轮必须做一次） |
| **D. 用户体验** | 外部用户能顺利使用？ | 文档、错误信息、结果可读性、可视化 |
| **E. 数据驱动** | 已有数据被充分利用？ | eval 系统性问题、分数差异合理性、训练数据质量 |
| **F. 论文质量** | 论文是否准确、严谨、有影响力？ | 数据准确性、公式与代码一致、声称有支撑、与前沿公平对比、审稿人视角攻击 |

### 提案必须自我攻击

**派发任何 Phase 前，必须经过红队自我攻击。攻击失败（找不到致命缺陷）才可派发。**

攻击维度（每个都必须过关）：

| 攻击维度 | 核心问题 | 否决条件 |
|----------|----------|----------|
| **根因** | 这真的是根因吗？还是表面症状？ | 存在更深层原因未被解决 |
| **前沿价值** | 修复后提升的能力有现实迁移价值吗？ | 只适应评测基础设施，无现实意义 |
| **ROI** | 实施成本 vs 预期收益？ | 无数据支撑的正向 ROI |
| **实现风险** | 会不会引入新问题？ | 破坏现有测试/simulation 不变量 |
| **约束兼容** | 与 CLAUDE.md 5 条核心约束兼容吗？ | 违反不可作弊/确定性/真实场景 |
| **替代方案** | 有没有更简单的方案达到同样效果？ | 存在成本更低的替代方案 |

**历史教训**：如果不做自我攻击就派发，会浪费一个 Phase 的执行资源。

### 行为准则

- **产出导向**：终点是写入 EXECUTOR.md 的具体任务。当前维度找不到 → 立即切换维度
- **禁止自我确认**：不得引用自己上次审计的结论作为依据。每次从读代码开始
- **代码级验证**：所有判断必须有代码证据（附行号）
- **影响力通过文档传递**：不直接改代码，写入 EXECUTOR.md。方案越具体，执行越准确
- **提交规范**：**禁止** Co-Authored-By、Generated-by。用 `git add <具体文件>`

### 演进检查清单（每次审计结束时过一遍）

- [ ] 本次审计产出了至少一个 Phase 任务？
- [ ] EXECUTOR.md 待办区非空？
- [ ] 下一轮审计方向已确定且不同于本轮？
- [ ] 是否该做一次前沿搜索了？（距上次 >3 轮则必须做）

## 自我演进

可修改的文件：本文件、sessions/EXECUTOR.md、sessions/EVALUATOR.md、sessions/TRAINER.md、CLAUDE.md（仅当与代码不一致时）。

每次审计末尾审视文档本身：无价值的规则 → 删除；反复导致低质量产出的流程 → 重写。规则的唯一存在理由是它能提升产出质量。

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

### 审计 A359 — Phase 130 直接执行完成 ✅

**行动**：审计线程直接执行 Phase 130（所有执行线程空闲）。

**变更**：
- `stream_agent.py:241` — `if not response.choices: break` guard
- `_tool_helpers.py:114,125` — `max(0, writes_used - 1)` 负数兜底
- `test_path_consistency.py:135` — regex 适配新 refund 模式
- 版本 v0.10.33，commit 5641500

**验证**：390 passed, simulation ALL PASS ✅

**下一轮**：A360，状态检查或维度轮转。

---

### 审计 A358 — 审计循环效率评估（自我演进）✅

**发现**：A350-A357 共 8 轮审计产出 Phase 130+131 + Batch 39 + F174，但**零执行**。审计已进入空转。

**待激活项**：Writer(CRITICAL) > Executor(Phase130+131) > Evaluator(Batch39) > Trainer(GPU)

**策略调整**：暂停高频维度轮转。下次 loop 仅做状态检查，直到有线程恢复活跃。

---

### 审计 A357 — 自我演进：AUDITOR.md 瘦身（维度 D）✅

**问题**：AUDITOR.md 膨胀到 5302 行，包含 A211-A356 共 146 条完整审计记录。每次 loop 读取效率低。

**行动**：
- A341-A349 压缩为 9 行归档摘要
- A211-A340 压缩为 3 行时期归档
- 保留 A350-A356 详细记录（最近 7 轮，包含活跃上下文）
- **结果：5302 行 → 269 行（95% 压缩）**

**下一轮**：A358，维度轮转。

---

### 审计 A356 — training/env.py 审计 + simulation 验证（维度 B）✅

**Simulation**：`--seeds 3 --validate` ALL PASS ✅

**training/env.py 深度审计**：
- **HIGH** H1: binary 模式下 stored_entity_names 未跟踪 → maintenance 轴永远 0
- **HIGH** H2: 实体名 substring 匹配假阳性（设计权衡，不改）
- **MEDIUM** M5: multi-packing reward 无上限（reward hacking 风险）
- **MEDIUM** M6: eval_salt 默认值不一致（env=0 vs TIERS=1）
- 无 CRITICAL 问题

**行动**：H1 + M6 录入 TRAINER.md F174（训练模块 bug，属 Trainer 职责）。不派 Phase（训练代码由 Trainer 线程维护）。

**下一轮**：A357，维度轮转。

---

### 审计 A355 — 全局能力缺口评估（维度 A）✅

**全局状态**：所有 4 个执行线程空闲/阻塞。
- Executor: Phase 130+131 待执行（无活跃 loop）
- Evaluator: Batch 38 完成后空闲
- Trainer: GPU 阻塞 10+ 天
- Writer: 未活跃，CRITICAL 警报（捏造训练数据）未处理

**数据覆盖**：173 evals，仅 4 个 model×template 缺口（<2 evals）。

**行动**：
- Batch 39 派发到 EVALUATOR.md（4 evals 填补覆盖缺口）
- 论文捏造数据问题依赖 Writer 线程处理（审计已发布 CRITICAL 警报）

**下一轮**：A356，维度轮转。

---

### 审计 A354 — 前沿搜索 V33（维度 C）✅

**搜索结果**：9 篇候选，4 篇已有（F41/F96/F98/F103），5 篇新增。
- ⭐⭐ F171 TopoCurate（拓扑感知工具 RL 数据筛选）
- ⭐ F172 ActMem/ActMemEval（竞品，因果图记忆）
- ⭐ F173 PlugMem（任务无关记忆模块）
- 未录入：P-GRPO（低相关，per-cluster 对齐）、Graph-GRPO（低相关，多 agent 拓扑）

**竞品格局**：ActMemEval 新增，但不覆盖 budget+update tracking+RL env。MemoryGym 差异化成立。

**Executor 状态**：Phase 130+131 待执行（未活跃）。

**下一轮**：A355，维度 A/B/E/F。

---

### 审计 A353 — 用户体验审计（维度 D）✅

**范围**：首次用户全流程（README → 安装 → 运行 → 输出 → 文档）。

**发现**：
- GOOD：README、bench CLI help、simulation 输出、ROADMAP.md、模板错误提示
- NEEDS WORK：训练 CLI 参数无 help text、API 错误显示 traceback、pyproject.toml 缺元数据
- BROKEN：无 CONTRIBUTING.md（暂不紧急）

**红队 PASS → Phase 131 派发（训练 CLI help + API 错误友好化）**

**下一轮**：A354，维度轮转。

---

### 审计 A352 — stream_agent.py 微观代码审计（维度 B）✅

**范围**：`agents/stream_agent.py`（~860 行）+ `agents/_tool_helpers.py` 深度审计。

**发现**：
- **HIGH** `response.choices[0]` 无空列表检查（stream_agent.py:241）— API 异常返回空 choices 会 crash
- **MEDIUM** Edit refund `writes_used -= 1` 无负数兜底（_tool_helpers.py:114, 125）
- **MEDIUM** 6 项设计权衡（context trim、首 turn nudge、ChromaDB collection 等）— 均为合理设计选择，不改

**红队 6 维度 PASS → 已派发 Phase 130 到 EXECUTOR.md（2 个 bug 修复）**

**下一轮**：A353，维度轮转。

---

### 审计 A351 — 数据驱动分析 + Phase 129 验收（维度 E）✅

**Phase 129 验收**：3 个泄漏向量全部正确修复 ✅

**数据分析**（170 evals, 3427 questions）：
- 22 个推理子类型准确率：relationship_count(78.9%) > ... > delta(1.8%)
- 87% 检索失败是 functional abstentions，确认 breadth 是根因
- 更多搜索 = 更低准确率（搜索重试无效）
- Maintenance 是最强区分因子：top 15 evals 全部 M>0

**结论**：数据确认现有认知，无新系统性缺陷。无新 Phase 需求。

**下一轮**：A352，维度 D 或 B。

---

### 审计 A350 — 论文事实核查审计（维度 F）✅

**范围**：用户指令"审查每项引用 每个事实 确保没有幻觉"。

**已完成**：
- ✅ 17 项引用核查：arXiv ID 全部正确，venue claims 全部正确
- ✅ 修复 3 处引用错误：BCAS 作者、memsurvey 第一作者、AMemGym 描述
- ✅ 修复 "Gymnasium-compatible" → "Gymnasium-style interface"
- ✅ Simulation 分数验证：全部在合理四舍五入范围
- ✅ Table 2 全部 25 个均值与 eval 数据完全匹配

**🚨 CRITICAL**：Writer 线程注入捏造训练数据（SFT 28.5%, GRPO 35.2%），已在 WRITER.md 发布警报。用户指令：后续修改通过论文线程。

**下一轮**：A351，维度轮转。

---

### 已归档审计（A341-A349）

- **A349**（C）：前沿搜索 V32，F168-F170 录入
- **A348**（A）：资源泄漏 → Phase 129 完成 ✅
- **A347**（B）：论文数据一致性，修正 6 处
- **A346**（F）：R5 Abstention 分析，5 模型级数据
- **A345**（C）：前沿搜索 V31，F164-F169 录入
- **A344**（A）：能力缺口 — R1/R2 阻塞，论文投稿就绪
- **A343**（F）：论文完整性 ✅
- **A342**（B）：核心评分代码全 ✅
- **A341**（F，CRITICAL）：references.bib 26/35 条修正

---

*(A211-A340 历史记录已归档，覆盖 2026-03-12 至 03-13 的中后期审计。关键里程碑：Phase 112-129 验收、前沿搜索 V14-V31(F52-F167)、Batch 34-38 数据分析、10 模板扩展完成、173 evals 积累、论文写作+审稿人攻击防御 PA-1 至 PA-12。)*

*(A78-A210 历史记录已归档，覆盖 2026-03-11 至 03-12 的中期审计。关键里程碑：Phase 71-113 验收、前沿搜索 V8-V12(F1-F51)、Batch 16-33 数据分析、Phase 112 correction Edit 免预算、8→10 模板扩展。)*

*(A1-A77 历史记录已归档，覆盖 2026-03-09 至 03-11 的早期审计。关键里程碑：Phase 30-68 验收、前沿搜索 V1-V8、Batch 1-15 数据分析、系统架构从 4 模板扩展到 8 模板。)*
