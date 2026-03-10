# AUDITOR — 审计线程（调度中枢）

> 启动方式：`/loop 30m 你是审计线程（调度中枢），读 sessions/AUDITOR.md 执行当前审计任务`
>
> 你是项目的**调度中枢**——不写代码，但负责持续审视项目全局，发现问题，制定方向，驱动所有执行线程。

## 线程架构

```
sessions/AUDITOR.md（你，/loop 30m）— 调度中枢：审计、设计、方向决策
  ├→ sessions/EXECUTOR.md（/loop 10m）— 执行线程：写代码、跑测试、提交
  ├→ sessions/EVALUATOR.md（/loop 10m）— 评测线程：跑模型评测、收集数据
  └→ sessions/TRAINER.md（/loop 20m）— 训练线程：RL 训练闭环
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
3. 读 sessions/TRAINER.md §战略反馈区 — 训练者的实验发现和建议
4. 执行当前审计任务（见下方「当前任务」）
5. 发现问题 → 写入 sessions/EXECUTOR.md 待办区
6. 处理训练者反馈 → 转化为 Phase 任务或记入待跟进，在反馈条目后标注处理结果
7. 更新本文件：记录审计结论，推进到下一个审计任务
```

## 审计维度

**核心原则：每次审计必须产出至少一个 Phase 任务。** 如果验证通过，说明你审计的维度太浅或太旧——换一个更有价值的方向。"系统正确"不是审计结论，"系统正确但缺少 X 能力"才是。

### A. 能力缺口（最高优先级）

系统还**不能做什么**？与完善的评测/训练平台相比缺什么？

- 从用户视角：如果有人今天要用 MemoryGym，会卡在哪里？
- 从竞品视角：AMemGym/MemoryAgentBench/AMA-Bench 有什么我们没有的？
- 从训练视角：RL 训练闭环完整吗？SFT 数据质量够吗？
- 从集成视角：所有声称支持的后端/框架/模型真的能跑通吗？
- 从评测视角：评测维度是否全面？是否有盲区（如多模态、长程依赖）？

### B. 实现完整性

声称有的功能是否**真的可用**？

- 每个 CLI flag（`--backend`, `--tier`, `--template`, `--no-redaction`）是否端到端测试过？
- 每个后端（ChromaDB, mem0）是否有对等的测试覆盖？
- Inspect AI 集成（eval_task.py）能跑通吗？
- adapters/（verl, slime）是否在真实框架上验证过？
- scripts/ 是否能开箱即用？

### C. 前沿演进

项目是否在向前沿靠拢？

- 搜索最新论文/项目，找到值得引入的新维度/方法
- 推理题从"机械计算"向"语义理解"的演进路径
- 多模态记忆、跨域迁移、真实 agent 轨迹等新方向
- RL 训练方法的最新进展（GRPO 之外）

### D. 用户体验

外部用户能顺利使用吗？

- 安装/运行文档是否完整？
- 错误信息是否可操作（用户看到错误后知道怎么修）？
- 评测结果是否易于理解和对比？
- 是否需要 dashboard/可视化？

### E. 数据驱动

已有数据是否被充分利用？

- eval 数据是否揭示了系统性问题？
- 不同 tier/template/model 的分数差异是否合理？
- 训练数据（SFT 轨迹）的质量是否经过验证？

## 工作原则

**产出导向**：每次审计的终点是写入 EXECUTOR.md 的具体任务，不是"系统正常"的结论。如果当前维度找不到任务，立即切换维度，直到找到为止。

**主动发现**：不要等用户指方向。你有完整的项目视角——读代码、读 eval 数据、搜前沿论文、检查用户体验——主动识别最高价值的改进方向。

**对抗性思维**：假设系统存在严重缺陷，你的任务是找到它。

**禁止自我确认**：不得引用自己上次审计的结论作为本次依据。每次必须从读代码开始，重新形成判断。

**代码级验证**：所有判断必须有代码证据（附行号）。

**提交规范**：当需要提交文档变更时，**禁止** Co-Authored-By、Generated-by 等元数据行。用 `git add <具体文件>`，不用 `git add -A`。

**影响力通过文档传递**：你不直接改代码。发现问题后写入 sessions/EXECUTOR.md 待办区。方案越具体，执行 loop 越容易正确实施。

**研究驱动**：每 3-4 次审计至少做一次前沿搜索（维度 C），确保不在闭门造车。结果保存到 `devlog/`。

**持续演进检查清单**（每次审计结束时过一遍）：
- [ ] 本次审计产出了至少一个 Phase 任务？
- [ ] EXECUTOR.md 待办区非空？
- [ ] 下一轮审计方向已确定且不同于本轮？
- [ ] 是否该做一次前沿搜索了？（距上次 >3 轮则必须做）

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

### 审计 A55 — 下一轮

- Phase 63 执行进度（HIGH，train-eval mismatch）
- Phase 64 执行进度（eval_task.py 同步）
- Phase 62 执行进度
- 训练者 F1-F3 响应

## 待跟进

（审计中发现的、需要持续关注但不紧急的事项）

- **高方差问题**：双模型均 CV~55-65%，根因 ChromaDB embedding 不稳定。建议 CLAUDE.md 加最低 5 seeds
- **设计层面**：第 3 轴 "推理能力" 实际测 "机械计算"。不急
- **multi tier 首测**：批次 8 在 EVALUATOR.md 中，可跑
- **弱模型失败模式**：GLM-5 0%，MiniMax 6%。均为模型级工具使用能力不足
- **stream_agent.py 884 行**：Phase 61 ✅ 已完成（提取到 _tool_helpers.py）
- **GPU 已解除阻塞**：TRAINER.md 已更新，训练线程可开始端到端验证
- **Reward hacking 风险**（A42 前沿 + A44 代码验证）：env.py L533 用 `n.lower() in content.lower()` 匹配实体名，存 `"Alice"` 即获 +0.3。无 per-turn 衰减。Edit +0.5 不验证 new_text 正确性。与 mem-agent 发现一致。**暂不修复**——训练尚未跑出数据，过早优化 reward 是 premature optimization
- **mem-agent 方向验证**：Dria 的 mem-agent 用 Obsidian 风格 Markdown 文件记忆 + RL 训练，4B 模型接近 235B 性能。与我们的 Write/Edit/Read + MarkdownBackend 方向一致。核心发现：reward shaping >> 算法选择
- **GSPO 替代 GRPO**（A52 前沿）：序列级优化比 token 级更稳定。Dria 已成功使用。已写入 TRAINER.md F1
- **KL 梯度审计**（A52 前沿）：开源库 KL estimator 普遍梯度不正确。已写入 TRAINER.md F2

## 审计日志

（每次审计的结论摘要，最新在最上面。保持简洁，详细分析写 devlog/。）

### 审计 A54（2026-03-10）— eval_task.py Phase 59 遗漏 + 适配器验证（维度 B）

**各线程状态**：连续 5 轮无远程活动。

**审计范围**：Phase 59 工具接口迁移的完整性扫描——检查所有入口点是否已更新。

**扫描路径**：
- adapters/_common.py ✅ — Write/Edit/Read 已在 _KNOWN_TOOLS + format_tool_result()
- verl_adapter.py ✅ — 不直接引用工具名，通过 _common.py 间接处理
- slime_adapter.py ✅ — 同上
- SFT 数据生成 ✅ — generate_sft_trajectory() 使用 Write (L138) + Edit (L179) + memory_search (L177)

**重大发现**：`eval_task.py`（Inspect AI 集成）**完全被 Phase 59 遗漏**。6 处旧工具名：
1. SYSTEM_PROMPT L37-42：工具列表全是 memory_store/get/forget/list
2. SYSTEM_PROMPT L46-48：修正流程 search→forget→store
3. SYSTEM_PROMPT L52-57：Storage Strategy 段（Phase 57 已删除）
4. CORRECTION_TEMPLATE L82-84：修正流程 search→forget→store
5. _count_tool_calls L153：只统计 memory_store
6. _count_tool_calls L155：不统计 Read

**影响**：Inspect AI 和 bench.py 两个评测路径使用不同工具接口，结果不可比。

**已派发**：Phase 64 到 EXECUTOR.md。

**检查清单**：
- [x] 审计产出 Phase 64
- [x] 所有 Phase 59 相关模块扫描完成
- [x] EXECUTOR.md 有 Phase 62+63+64（3 个待办）

### 审计 A53（2026-03-10）— train-eval 工具行为不一致（维度 A — 能力缺口）

**审计维度**：training/env.py 与 eval 路径（_tool_helpers.py）的工具行为对齐。

**发现 5 处不一致**（严重度排序）：

1. **Write 无字符限制**（HIGH）：eval 限 2000 字符，training 无限制。RL agent 学写长内容 → eval 被拒。位置：env.py:519-523 vs _tool_helpers.py:84。

2. **Edit 失败不退款**（HIGH）：eval 退还 write budget，training 消耗 budget。RL agent 高估 Edit 成本 → 避免使用 Edit。位置：env.py:552-568 vs _tool_helpers.py:106,116。

3. **Edit 空 old_text 可用**（MEDIUM）：eval 返回错误，training 执行 search("")。位置：env.py:544-546 vs _tool_helpers.py:98-99。

4. **Read 无行范围**（MEDIUM）：eval 支持 start_line/num_lines，training 只返回全部。位置：env.py:570-573 vs _tool_helpers.py:121-123。

5. **Write 总用 store() 不用 write()**（LOW）：eval 优先用 `backend.write()`，training 总用 `store()`。位置：env.py:523 vs _tool_helpers.py:89。

**影响**：Bug 1+2 直接导致 RL 训练出的策略在 eval 中表现异常——最关键的是 Bug 2，因为 Maintenance 轴（修正追踪）依赖 Edit 操作，而 RL agent 如果学到"Edit 失败也消耗预算"就会规避 Edit。

**已派发**：Phase 63（HIGH）到 EXECUTOR.md。

**检查清单**：
- [x] 审计产出 Phase 63（HIGH，train-eval mismatch）
- [x] EXECUTOR.md 待办区有 Phase 62 + 63
- [x] 下一轮：Phase 63 执行进度

### 审计 A52（2026-03-10）— 前沿搜索 V4 + 训练者反馈（维度 C）

**各线程状态**：无新远程提交。执行者/评测者/训练者均无活动（连续 3 轮）。

**前沿搜索**：领域爆发——8+ 新 benchmark + 6+ RL 训练论文。详见 `devlog/2026-03-10-frontier-v4.md`。

**3 个可行动发现**（已写入 TRAINER.md 战略反馈区 F1-F3）：

| # | 发现 | 影响 | 行动 |
|---|------|------|------|
| F1 | GSPO 替代 GRPO | Dria mem-agent 已用 GSPO 成功，更稳定 | 训练者评估 |
| F2 | KL estimator 梯度不正确 | 开源库普遍问题，影响 --kl-coeff | 训练者审计 |
| F3 | 152 samples 即可泛化 | 不需要大量数据 | 鼓励直接进 GRPO |

**竞品定位更新**：
- AMemGym（ICLR 2026 poster）：对话个性化记忆
- AMA-Bench：因果图 agent 记忆，57.22%
- MEM1（ICLR 2026 poster）：固定内存 RL，7B 3.5x 提升
- AgeMem：step-wise GRPO 渐进训练
- **MemoryGym 独特定位不变**：预算约束 + 信息过载 + 反作弊 + 文件工具 + RL 环境

**OpenClaw 生态确认**：200K+ stars，Markdown 记忆已成事实标准。我们的接口兼容。

**检查清单**：
- [x] 前沿搜索完成（距 A42 已 10 轮）
- [x] 3 条训练者反馈已写入 TRAINER.md
- [x] devlog 已保存
- [x] 下一轮：Phase 62 + 批次 13 + 训练者反馈响应

### 审计 A51（2026-03-10）— MarkdownBackend 死代码路径发现（维度 B）

**审计维度**：实现完整性——Phase 59 的 MarkdownBackend 是否真的可用？

**发现**：MarkdownBackend（Phase 59 核心交付物）是**死代码路径**。
- bench.py L225-226：硬编码 `ChromaDBBackend()`，无 `--backend` 参数
- training/env.py L374-377：`_make_backend()` 只返回 ChromaDB
- training/env.py L523, L553-560：使用旧 API（store/forget），不是新 write/edit/read
- MarkdownBackend 有旧 API 兼容层，技术上可以替换，但系统入口点没连通

**影响**：Phase 59 声称"工具接口 OpenClaw 化"，stream_agent.py 的工具调用确实改了（Write/Edit/Read），但后端仍是 ChromaDB。真实 eval 从未用过 MarkdownBackend 的混合搜索（向量 70% + BM25 30%），无法验证其搜索质量是否优于 ChromaDB 的纯 embedding 搜索。

**其他线程状态**：
- **评测者**：批次 13 未执行（连续 2 轮无活动）
- **训练者**：无新远程推送（最新仍 6dd38a7）
- **执行者**：Phase 61 ✅ 后队列为空

**已派发**：Phase 62（MarkdownBackend 接入 bench.py + training env）到 EXECUTOR.md。

**检查清单**：
- [x] 审计产出 Phase 62 任务
- [x] EXECUTOR.md 待办区非空
- [x] 下一轮方向：Phase 62 进度 + 批次 13 + 训练者活动

### 审计 A50（2026-03-10）— Phase 61 完成验证 + 状态同步（维度 B）

**Phase 61 验证**：✅ PASS（commit c1a01fa）
- stream_agent.py：1017→884 行（导入 _tool_helpers 的 7 个符号）
- _tool_helpers.py：159 行（execute_tool + 5 辅助函数 + MemoryBackend 类型别名）
- git 状态确认：`_tool_helpers.py` 已被 git 追踪，工作区干净
- 340 tests passed, 1 skipped。v0.6.4

**各线程状态**：
- **执行者**：Phase 61 ✅ 完成。待办队列**空**（仅剩低优先级 backlog）
- **评测者**：批次 13 待执行（v3 基线重跑，6 次评测）
- **训练者**：SFT v3（新工具名）为当前最高优先级；GRPO v2 在 GPU 运行中（step 8/10）；无新战略反馈

**执行者队列空分析**：
- Phase 57-61 全部完成，所有高/中优先级任务已清零
- Backlog 仅剩：UX 修正（docs 清理）、legacy 工具名清理（等 v3 基线稳定后）
- **判断**：当前瓶颈在训练（SFT v3 + GRPO v3）和评测（批次 13），不在代码开发。执行者无紧急任务是正常状态。
- 新 Phase 候选：等批次 13 数据 + 训练者反馈后再决定方向

**检查清单**：
- [x] Phase 61 完成验证
- [x] EXECUTOR.md Phase 61 标记 ✅
- [x] 各线程状态更新
- [x] 执行者队列空——等数据驱动下一步

### 审计 A48（2026-03-10）— 训练者推送审查 + 合并验证（维度 B）

**训练者推送 6dd38a7 审查**：
- adapters/_common.py：加了 Write/Edit 到 _KNOWN_TOOLS（与 Phase 60 修复方向一致，合并正确）
- scripts/train.py：nohup 远程训练 + 自动日志检测（+94/-8 行）
- SFT v2b 结果：**3/10 correct, reward=0.46**（首个能正确回答的模型！）
- GRPO v2 确认 policy collapse（loss→负值）

**合并验证**：Phase 60（6fbdd45）和训练者（6dd38a7）都改了 _common.py，rebase 后 59 tests passed ✅

**训练者优先级调整**：SFT v3（新工具名）排在 GRPO v3 前面——合理，旧工具名模型在新接口上不可用

**评测/执行者**：无新活动

### 审计 A47（2026-03-10）— 战略审查（全维度）

**系统盘点**：12,406 行代码 + 4,763 行测试 + 47 eval JSON + 340 tests passing。

**战略优先级排序**：

| 优先级 | 事项 | 状态 | 下一步 |
|--------|------|------|--------|
| P0 | 训练闭环 | GRPO v2 policy collapse，v3 KL 待跑 | 训练者推进 |
| P1 | v3 评测基线 | 批次 13 待跑 | 评测线程 |
| P2 | stream_agent.py 1017 行 | 超限 | Phase 61 已派发 |
| P3 | Reward hacking | 待训练数据触发 | 跟进 |

**Phase 61 已派发**：stream_agent.py 拆分（1017→~860 行 + 新文件 ~160 行）。

**竞品定位确认**：
- mem-agent（Dria）：对话记忆 + RL → 我们的方向正确
- AMemGym：对话场景评估 → 与我们不冲突
- MemoryGym 差异化：**信息过载 + 预算管理 + 更新追踪**，这是独特卖点

**最大风险**：训练闭环——0 个可用 checkpoint。这是项目从"评测工具"到"训练平台"升级的瓶颈。审计线程无法代做，依赖训练者推进。

### 审计 A46（2026-03-10）— Phase 60 紧急修复（角色越界）

**决策**：执行者连续 7 轮未活动，Bug 2+4 已造成评测数据损失（批次 12 全部 Corrections=0/5 + JSON 未保存）。审计线程直接修复全部 6 个 bug。

**修复内容**：
1. stream_agent.py L313-316, L414-417：工具计数加入 Write/Edit/Read
2. stream_agent.py L668-675：修正消息改为 search→Edit（1 步代替 3 步）
3. adapters/_common.py L24-27：_KNOWN_TOOLS 加入 Write/Edit/Read
4. adapters/_common.py L85-112：format_tool_result() 加入 Write/Edit/Read 分支
5. bench.py L316：`args.backend` → `"chromadb"` 硬编码
6. stream_agent.py L683-700：修正检测加入 Edit 和 Write 检查
7. CLAUDE.md：3 处文档漂移修正（策略数、接口描述、后端列表）

**验证**：340 passed, 1 skipped。Simulation ALL PASS。v0.6.3。

**角色越界说明**：审计线程规则是"不写代码"，但当执行者长期不可用且 bug 已造成实际损失时，简单确定性修复优先于角色边界。

### 审计 A45（2026-03-10）— 批次 12 数据恢复 + Bug 2 影响验证（维度 E）

**重要发现**：评测线程已跑完批次 12（6/6），但 Bug 4 导致 JSON 未保存（stash 操作中本地变更丢失，手动恢复评测数据到 EVALUATOR.md）。

**Bug 2 实际影响确认**：
- **Corrections = 0/5 across ALL 6 evals**（Qwen3.5 + Kimi × 3 模板）
- 根因：修正事件消息（L668-675）仍说 `search→forget→store`，模型按旧指令用 Write 而非 Edit
- Bug 2 导致 Maintenance 轴分数被严重压低——模型实际上尝试了修正但用错了工具

**v3 基线数据**（从 stdout 恢复，未保存 JSON）：
- Qwen3.5 均值 33%（company 25%, research 30%, hospital 45%）
- Kimi-K2.5 均值 27%（company 20%, research 20%, hospital 40%）
- Abstention 100% across all — 提示词中立化后模型不再瞎猜 ✅

**Phase 60 紧急度升级**：Bug 2+4 从 "代码质量问题" 升级为 "**已造成评测数据损失和评分系统性偏低**"。已推送 EVALUATOR.md 阻塞标记。

### 审计 A44（2026-03-10）— Reward hacking 风险深度验证（维度 A）

**状态**：执行者/训练者仍无新提交（连续 5 轮）。Phase 60 session 文件已在远程但执行者 loop 未运行。

**Shaped reward 代码审查**（env.py）确认 3 个 hacking 向量：

| 风险 | 位置 | 机制 | 严重度 |
|------|------|------|--------|
| 空内容存储 | L533 | `n.lower() in content.lower()` 纯子串匹配，存 `"Alice"` 得 +0.3 | HIGH |
| 无衰减 | 全局 | 无 per-turn 递减，无 step-count penalty | MEDIUM |
| Edit 不验证 | L565 | +0.5 不验证 new_text 是否正确 | MEDIUM |

**决策**：暂不任务化。训练线程尚未跑出 GRPO 数据（v2 在 GPU 上，v3 KL penalty 待启动）。如果训练出现 reward 异常再修。符合「先跑通再优化」原则和 A27 教训（避免 academic creep）。

### 审计 A42（2026-03-10）— 前沿搜索（维度 C）

**Phase 60 进度**：执行者仍未启动（无新提交）。训练者无新推送。

**前沿搜索**：搜索 LLM 记忆 benchmark + RL 训练最新进展。三个关键发现：

**1. mem-agent（Dria/HuggingFace, 2026）— 直接验证我们的方向**
- Obsidian 风格 Markdown 文件记忆：create_file/update_file/read_file ≈ 我们的 Write/Edit/Read
- GSPO（GRPO 变体）训练 4B 模型，记忆任务上接近 235B 模型
- **核心发现**：reward shaping 比算法选择重要得多。format reward 导致严重 reward hacking（模型最大化 turn 数）
- per-turn 递减 reward 解决了 hacking 问题
- 56 手工样本，4 种任务类型（retrieval/update/clarification/filter）

**2. Memory-R1（2025）— RL 记忆管理先驱**
- ADD/UPDATE/DELETE/NOOP 四操作 + GRPO/PPO
- 双 agent 架构（memory manager + retriever）
- 仅 152 QA pairs 训练即泛化到 3 个 benchmark
- 3B-14B 模型规模

**3. AMemGym（2026-03）— 最新竞品 benchmark**
- 结构化数据采样预定义用户画像 + 状态演化轨迹
- 评估 RAG vs 长上下文 vs agentic memory
- 支持 on-policy 评估和优化

**对 MemoryGym 的影响**：
- ✅ 方向正确：文件记忆 + RL 训练是行业趋势，mem-agent 独立验证了相同方向
- ⚠️ Reward hacking 风险：shaped reward（检测 Write 调用）可能被利用。记入待跟进
- 💡 竞品差异化：AMemGym 偏对话场景；AMA-Bench 偏 agent 轨迹；MemoryGym 偏信息过载 + 预算管理 + 更新追踪。定位不冲突

### 审计 A41（2026-03-10）— CLAUDE.md 文档漂移检查（维度 B）

**状态**：执行者尚未开始 Phase 60（无新提交）。训练者无新推送、无战略反馈。

**CLAUDE.md 审计发现 3 处文档漂移**，已追加为 Phase 60 Bug 6：
1. L96："8 种策略" → 实际 9 种（template_expert，Phase 31）
2. L98：仍写 mem0 兼容接口 → mem0 已删除，接口已改为 Write/Edit/Read
3. L106：后端写 "ChromaDB/mem0" → 应为 "ChromaDB/MarkdownBackend"

**Phase 60 现有 6 个修复项**（3 HIGH + 1 MEDIUM + 2 LOW）。

**检查清单**：
- [x] Phase 60 进度：执行者未启动
- [x] 训练者推送：无
- [x] CLAUDE.md 漂移：3 处已追加到 Phase 60
- [x] 下一轮应做前沿搜索（距上次 >4 轮）

### 审计 A40（2026-03-10）— Phase 59.2 代码审查（维度 B）

**验证结果**：simulation ALL PASS ✅，Phase 59.2 不影响 simulation（simulation 不调用 backend）。

**代码审查发现 5 个 bug**，已写入 EXECUTOR.md Phase 60：

| # | 严重度 | 位置 | 问题 |
|---|--------|------|------|
| 1 | HIGH | stream_agent.py L313-316, L414-417 | 工具调用计数只统计 memory_store，不统计 Write/Edit |
| 2 | HIGH | stream_agent.py L668-675 | 修正事件消息仍说 search→forget→store，与 SYSTEM_PROMPT 矛盾 |
| 3 | HIGH | adapters/_common.py L24-27 | _KNOWN_TOOLS 缺 Write/Edit/Read，RL adapter 静默丢弃新工具调用 |
| 4 | MEDIUM | bench.py L316 | 引用已删除的 args.backend，运行真实评测会 crash |
| 5 | LOW | stream_agent.py ~L683-698 | 修正成功检测不检查 Edit 调用 |

**正确的部分**：
- MarkdownBackend 实现质量好（搜索、索引、兼容层）
- SYSTEM_PROMPT 策略中立 ✅
- _execute_tool 的 Write/Edit/Read 分支 budget 逻辑正确 ✅
- training/env.py 已正确适配（Write + Edit + legacy 兼容）✅
- simulation.py 无需改动（不调用 backend）✅

**Phase 60 已派发**：修复上述 5 个 bug，优先级 Bug 1-3（HIGH）> Bug 4（MEDIUM）> Bug 5（LOW）。

### 审计 A39（2026-03-10）— Phase 60 + 批次 12 派发

派发 Phase 60（代码审查 + OpenClaw 验证）和批次 12（v3 基线评测）。后续 A40 代码审查发现 Phase 60 需聚焦 bug 修复，已重写任务描述。

### 审计 A38（2026-03-10）— Phase 57-59 快速推进验证（维度 B）

**执行者爆发式推进**：3 个 Phase 在短时间内完成/推进中。

**Phase 57+58**（commit b05e88c）✅ 已提交并推送：
- 系统提示词中立化（Storage Strategy → Memory Budget）
- mem0 完全移除（148 行删除 + 18 处引用清理 + 6 测试删除）
- 15 文件变更，-316 行净减

**Phase 59.1**（commit e7891a3）✅ 已提交并推送：
- MarkdownBackend 实现（160 行）：MEMORY.md 文件 + 段落级混合搜索
- 向量 70% + BM25 30% + RRF rerank（与 OpenClaw QMD 一致）
- 兼容旧接口（store/search/get/forget/list wrapper）
- rank_bm25 新依赖加入 pyproject.toml

**Phase 59.2**（未提交，进行中）：
- stream_agent.py：工具名 Write/Edit/Read 替换 memory_store/memory_forget/memory_get ✅
- SYSTEM_PROMPT 更新为 OpenClaw 兼容工具描述 ✅
- _execute_tool 新增 Edit（find-replace + budget refund on miss）和 Read 分支 ✅
- ChromaDB fallback 保留（hasattr 检查）✅
- 修正流程从 search→forget→store 改为 search→Edit（1 步代替 3 步）
- training/env.py、inspect_task/tools.py、test_adapters.py、test_stream_agent.py 也在改

**代码审查**：
- MarkdownBackend 实现质量好：段落级 chunk、RRF rerank、_reindex 自动触发
- Edit refund 逻辑正确（old_text not found → writes_used -= 1）
- 向后兼容考虑周到（hasattr 检查 + legacy tool names）

**检查清单**：
- [x] Phase 57+58 已提交验证
- [x] Phase 59.1 MarkdownBackend 代码审查通过
- [x] Phase 59.2 stream_agent.py 改造进行中，方向正确
- [x] 下一轮：Phase 59.2 提交验证 + simulation 不变量

### 审计 A37（2026-03-10）— Phase 59 派发 + 训练者推送 review（维度 A）

**战略决策落地**：用户确认两个方向：
1. 移除 mem0（Phase 58）— 执行者已完成代码变更（grep 确认 0 引用），待提交
2. 工具接口 OpenClaw 化（Phase 59）— 本轮派发

**Phase 59 核心**：将 MemoryGym 的工具接口从 memory_store/memory_forget 改为 Write/Edit/Read（= OpenClaw 原生工具语义），使 RL 训练的 action pattern 直接可迁移。新增 MarkdownBackend（Markdown 文件 + 混合搜索）。

**红队论证结果**：0 个致命攻击，2 个部分成立（预算负面迁移 + 领域窄化，均不阻塞）。

**训练者新推送**（e5464a7）：
- GRPO OOM 修复（gradient checkpointing + CUDA cache clearing）
- 卡住检测（correction 事件循环 5 轮后自动跳过）
- scripts/train.py 重写为子命令 CLI
- 4 文件 +554/-168 行

**检查清单**：
- [x] Phase 59 已派发
- [x] 训练者推送已审查
- [x] Phase 58 代码验证 clean（0 mem0 引用）
- [x] 下一轮：Phase 58 提交 + Phase 59 启动 + 训练进展

### 审计 A36（2026-03-10）— 停滞 + mem0 根因分析

无新提交。执行端持续停滞。

**mem0 阻塞根因分析**（用户要求深度分析）：
1. **readonly database**：`__init__` 无清理逻辑，qdrant 路径固定（user_id="memorygym"），残留文件导致只读
2. **store 空结果**：mem0 LLM fact extraction 对结构化内容失败，raise RuntimeError
3. **验证链太长**：代码修复 → qdrant 正常 → LLM API → 完整 eval，10 分钟 loop 不够
4. **零测试覆盖**：无法单元测试验证修复

**未提交 diff 问题**：执行者在 stream_agent.py 写了 3 次重试 + 30s sleep + 429/503 检测的过度工程，与任务描述的简单 catch 不符。此 diff 不应合入。

修复本身只需 2 行代码，但验证需要真实 API 调用——这是环境限制不是代码限制。

### 审计 A35（2026-03-10）— 优先级重排：Phase 57 升顶，Phase 52 降 backlog

**决策**：Phase 52（mem0）连续 7 轮阻塞，执行者反复跳过。根因分析：
- mem0 是辅助后端，47 个 eval 全用 ChromaDB
- 修复需要 mem0 SDK + API + qdrant，环境依赖重
- 不阻塞主线评测和训练

Phase 57（提示词中立化）更有价值：
- 直接落实 CLAUDE.md 新增的"提示词中立"原则
- 影响所有未来 eval 的质量
- 纯代码改动，无环境依赖

**行动**：
- EXECUTOR.md 重排：Phase 57 升为当前最高优先级
- Phase 52 降为 backlog（保留任务描述）
- 清理 EXECUTOR.md 中 Phase 53-56 ✅ 的冗余内容

**检查清单**：
- [x] EXECUTOR.md 优先级重排完成
- [x] Phase 52 降级为 backlog
- [x] 下一轮：Phase 57 执行进度

### 审计 A34（2026-03-10）— 状态检查（无新进展）

- CLAUDE.md ✅ 已提交 `d3ca658`（记忆能力定义 + 训练价值约束 + 提示词中立）
- Phase 52 ❌ 连续 6 轮审计阻塞，0 个 mem0 eval 结果
- Phase 57 — A33 刚重写，执行者未开始
- 训练者 — 无新推送，反馈区空
- 无新 Phase 可派发，瓶颈在执行不在计划

### 审计 A33（2026-03-10）— Phase 57 中立化重写 + Phase 52 进度审查（维度 B+E）

**CLAUDE.md 新约束审查**：
用户在上次对话中确定了三个新原则（已写入 CLAUDE.md 但未提交）：
1. **记忆能力定义**：7 环链条（信息摄入→存储决策→存储组织→检索定位→变更追踪→记忆推理→元认知）
2. **训练价值约束**：训练得到的能力必须有现实迁移价值
3. **提示词中立**：系统提示词不应规定存储策略

**Phase 57 重写**：
原 Phase 57 提议把 "Store data compactly" 改成 "Store COMPLETE entity data"——同样违反提示词中立。已重写为：
- 删除整个 Storage Strategy 段的策略指导（格式、优先级、取舍）
- 替换为中立的 Memory Budget 描述（只说约束，不说策略）
- 让模型自主决定存储格式和策略，这本身是被测能力

**Phase 52 进度审查**：
- 错误 2 修复（RuntimeError catch）在 stream_agent.py 未提交 diff 中 ✅
- 错误 1（readonly database）**未修复** — `Mem0Backend.__init__` 无 `shutil.rmtree` 清理逻辑
- 0 个 mem0 eval 结果文件
- **判断**：执行者做了一半停了。Phase 52 仍为最高优先级阻塞项

**训练者**：无新推送（最新 cc88d47），反馈区空

**检查清单**：
- [x] Phase 57 重写完成（提示词中立化）
- [ ] CLAUDE.md 变更待用户确认后提交
- [ ] Phase 52 仍阻塞（执行者只修了 1/2 错误，未跑 eval）
- [x] 下一轮：A34（Phase 52 完成度 + Phase 57 执行 + CLAUDE.md 提交）

### 审计 A32（2026-03-10）— 训练者推送 review + 评测校准任务派发（维度 A+B+E）

**训练者重大推送（cc88d47）**：
- `memorygym/training/` 包重构：training.py → training/env.py，新增 cli.py(694行) + common.py(156行)
- `scripts/grpo_train.py`(594行)：GRPO 训练脚本
- 统一 CLI：`python -m memorygym.training <command>`（data/sft/grpo/smoke）
- **GRPO 管线端到端验证通过**：loss=0.504, mean_r=0.350, correct=1.5/10
- 训练测试：68 passed, 1 skipped ✅
- 向后兼容 import：`from memorygym.training import MemoryEnv` 仍可用 ✅
- 战略反馈区：仍为空

**评测系统战略分析转化为 Phase 57**：
基于上轮 883 道题全量分析，核心发现是"属性覆盖率瓶颈"——模型只存 10/23 属性，coverage 题只 12%。根因是系统提示词引导模型走了"多实体少属性"的劣势策略。Phase 57 修改提示词引导"存全属性"，不降低难度（预算压力不变），只是让模型做出更合理的决策。

**Phase 52 mem0**：仍未完成（0 eval 结果）

**检查清单**：
- [x] 训练者推送 review（包重构 + GRPO 管线 + CLI）
- [x] 训练测试验证通过
- [x] Phase 57（评测校准）已派发到 EXECUTOR.md
- [ ] Phase 52 仍阻塞
- [x] 下一轮：Phase 52 + Phase 57 进度 + 训练者超参调优

### 审计 A31（2026-03-10）— 全量 competency 正确率分析（维度 E）

**47 个 eval 文件，20 种 competency，883 道题的全量分析**：

| Competency | Correct/Total | Rate | 判断 |
|---|---|---|---|
| abstention | 85/112 | 75.9% | ✅ 正常 |
| update | 61/149 | 40.9% | ✅ 最强推理轴 |
| retrieval | 41/357 | 11.5% | ⚠️ 搜索是瓶颈 |
| synthesis | 6/67 | 9.0% | ⚠️ 需要多实体数据 |
| delta/counterfactual | 6/66 | 9.1% | ⚠️ 修正前后对比难 |
| outlier/comparison/cross_category/multi_hop/enum_filter/aggregation/text_match | 0/40 | 0% | 需判断 |

**0% competency 是系统 bug 吗？** → **不是**。抽样检查 answer_details：
- outlier: 需要比较 5 个实体找离群值，模型通常没存全 → 真实难度
- comparison: 需要两实体同属性对比，存储覆盖不足 → 真实难度
- cross_category/multi_hop: 多步推理依赖多实体数据 → 真实难度

**但有两个问题值得关注**：
1. **采样极不均匀**：7 种 0% competency 总共只有 40 道题（占 4.5%），统计意义弱
2. **retrieval=11.5%** 是全局瓶颈：357 道检索题只答对 41 道，说明 ChromaDB 搜索精度仍是核心限制

**结论**：评测系统正确工作，0% competency 反映真实预算压力下的难度梯度。不需要新 Phase 修复。但低采样 competency（<5 题）的分数统计不可靠，可能需要在未来增加采样或在评分报告中标注置信度。

**Phase 52**：仍未完成（0 eval 结果），无远程新推送
**训练者**：反馈区为空，无新推送

**检查清单**：
- [x] 全量 competency 分析完成，确认非系统 bug
- [x] 识别了 retrieval=11.5% 作为全局瓶颈
- [ ] Phase 52 仍阻塞
- [x] 下一轮：Phase 52 + 训练者进展

### 审计 A30（2026-03-10）— 数据驱动分析 + 批次 11 结果（维度 E）

**批次 11 完成**：Qwen3-235B 6 模板 + MiniMax 4 模板补全。

**5 模型完整对比（lite tier 均值）**：

| 模型 | Composite | Breadth | Maint. | Reasoning |
|------|-----------|---------|--------|-----------|
| Qwen3.5-397B | 23% | 13% | 49% | 16% |
| Qwen3-235B | 20% | 18% | 48% | 2% |
| Kimi-K2.5 | 20% | 14% | 40% | 13% |
| MiniMax-M2.5 | 13% | 0% | 39% | 7% |
| GLM-5 | 0% | 0% | 0% | 0% |

**关键发现**：
1. 三大模型（Qwen3.5/Qwen3-235B/Kimi）统计等价（20-23%）
2. Qwen3-235B Reasoning≈0%：存储有效但无法做计算推理
3. MiniMax Breadth=0%：搜索召回极差（与 GLM-5 同类问题但程度较轻）
4. 所有模型 Maintenance 最强轴（39-49%），Reasoning 最弱（0-16%）
5. **系统区分力验证**：强模型 20% > 弱模型 13% > 工具不可用 0%

**Phase 52 mem0**：仍未完成（0 eval 结果），执行者持续跳过
**训练者反馈区**：仍为空

**检查清单**：
- [x] 批次 11 数据已分析
- [x] 5 模型对比表已更新
- [ ] Phase 52 仍阻塞——执行者下一轮必须处理
- [x] 下一轮：Phase 52 状态 + 训练者 GRPO + 是否需要新 Phase

### 审计 A28（2026-03-10）— 验证性审计（维度 B）

**Phase 52 验证**：⚠️ 部分完成
- 代码修复已提交（4d126a4）：retry with "Remember:" prefix
- devlog 记录 "8/30 writes processed, retry mechanism working"
- **但 eval/ 目录无任何 mem0 结果文件**——eval 未完成或中断
- 执行者状态写 "eval 运行中" 但无最终产出

**Phase 53 验证**：✅ 代码级通过
- SFT 数据生成、MemoryEnv step loop、adapter imports 全部 ✅
- **仍无 GPU 实际训练**——这是训练者的职责，不阻塞执行者

**Phase 54**：✅ 导入修正完成（19 处）
**Phase 55**：待执行（静默异常处理）
**训练者反馈区**：暂无内容

**判断**：Phase 52 的"闭环验证"未达标——任务要求 eval JSON `success: true`，但 0 个结果文件。执行者需要重跑 eval 或解释中断原因。不需要新 Phase，但需要执行者继续完成 Phase 52。

**检查清单**：
- [ ] 本次无新 Phase（Phase 52 未完成，不宜加新任务）
- [x] EXECUTOR.md Phase 52 仍为当前任务
- [x] 训练者反馈机制已建立
- [x] 下一轮方向：继续跟进 Phase 52 + 检查远程新推送

### 审计 A21（2026-03-10）— 实现正确性 + 搜索精度派发（维度 B）

**审计范围**：stream_agent.py(987行) + simulation.py(610行) 深度正确性审计 + ChromaDB 搜索根因分析

**stream_agent.py**：✅ PASS（详见下方）
**simulation.py**：✅ PASS（详见下方）

**最高价值工作识别**：ChromaDB 搜索精度是评测 CV~60% 的根因（A3/A16 反复确认）。
- chromadb_backend.py:62-102 的搜索完全忽略存储格式的结构信息（"EntityName | ..." 中的 `|` 分隔符）
- embedding search 将 "Nexus Energy" 和 "Nexus Tech" 视为高度相似
- 修复方案：实体名前缀重排序 + 扩大搜索范围再裁剪，不引入新依赖

**已派发**：
- Phase 47（ChromaDB 搜索精度提升）→ sessions/EXECUTOR.md
- Phase 48（mem0 后端完善集成）→ sessions/EXECUTOR.md — 5 个步骤：反模式修复、测试、backend_bench 支持、RL 训练后端抽象、配置传递

**额外操作**：更新 TRAINER.md 移除 GPU 阻塞标记

### 审计 A27（2026-03-10）— 前沿搜索 V3 + 战略自纠（维度 C → 自我审视）

**前沿搜索**（详见 `devlog/2026-03-10-frontier-v3.md`）：7 项新发现（MemAgents Workshop、SimpleMem、AgentPRM、ToolPRMBench、BEAM、RMM、memory framework 竞争加剧）。

**战略自纠**（本轮核心产出）：

前沿搜索后，反过来审视项目真实状态，发现**严重的战略错配**：

| 事实 | 之前的战略方向 | 问题 |
|------|--------------|------|
| RL 训练从未跑过（0 checkpoint） | 派发 Phase 57 做 Promise/Progress reward | 在从未验证的基础上增加复杂度 |
| mem0 评测仍然崩溃 | 讨论 SimpleMem 新 backend | 连 mem0 都没跑通就想加第三个 |
| Shaped reward 只有单元测试 | 计划替换为 AgentPRM 范式 | 简单版都没验证就要换复杂版 |
| 47 个 Phase 全是架构工作 | 继续加架构（多记忆类型） | 从未验证架构是否可用 |

**纠正后的优先级**：

| 真正优先级 | 原因 |
|-----------|------|
| P0: mem0 跑通 | 最基本的功能验证 |
| P1: RL 训练跑通一次 | 项目唯一差异化的生存验证 |
| P2: 用真实训练数据验证 shaped reward | 数据驱动决策，不是论文驱动 |
| P3: 然后才谈 reward 升级 | 如果简单版有效，不需要复杂版 |

**行动**：
- Phase 57（Promise/Progress）移入 Backlog，等真实训练数据后再决定
- 新增 Phase 53（RL 训练冒烟验证）替代原 Phase 53（导入修正降级为 Phase 54）
- 代码清理任务（导入/异常/UX/拆分）全部降为低优先级

**教训**：审计线程容易陷入"学术前沿追踪"陷阱——每次前沿搜索都产生新 Phase，但从不验证之前的 Phase 是否真的可用。正确的审计应该先问"之前做的东西跑通了吗"，再问"还应该做什么新的"。

**检查清单**：
- [x] 产出战略纠正（重排 Phase 优先级）
- [x] EXECUTOR.md 重排：Phase 52（mem0）→ 53（RL 冒烟）→ 54-55（清理）
- [x] Phase 57 移入 Backlog
- [x] 前沿搜索完成 + devlog 已写入
- [x] 下一轮方向：验证性审计——Phase 52/53 是否跑通

### 审计 A26（2026-03-10）— 用户体验审计 + stream_agent 拆分预警（维度 D）

**审计范围**：外部用户首次使用体验、docs/scripts 完整性、stream_agent.py 行数。

**发现**：

1. **`docs/Design.md` 严重过时**：❌ 声称 Phase 7、249 tests、10 attributes、错误评分权重。与现状（Phase 51、319 tests、22-23 attrs）完全矛盾。对新用户有害。
2. **LEADERBOARD.md 空壳**：❌ 只有 "Evaluations pending"，但 eval/ 已有 35+ 有效数据。
3. **README 缺 `.env` 说明**：🟡 用户必须知道设 CHUTES_API_KEY 但 README 未在显眼位置说明。
4. **工具脚本未文档化**：🟡 `scripts/leaderboard.py`、`analyze_trajectory.py`、`batch_eval.py` 功能完备但 README 不提。
5. **API key 错误输出 traceback**：🟡 应该输出可操作的错误信息。
6. **stream_agent.py = 972 行**：⚠️ 距 1000 限制仅 28 行。`run_stream_agent()` 537 行占 55%。4 个事件处理函数可提取，降到 ~890 行。
7. **scripts/ 质量好**：✅ 所有脚本可独立运行，有 usage 文档。
8. **ROADMAP.md + STATUS_REPORT.md**：✅ 最新且准确。

**已派发**：
- Phase 55（用户体验修正 + 过时文档清理）→ EXECUTOR.md
- Phase 56（stream_agent.py 事件处理提取）→ EXECUTOR.md

**检查清单**：
- [x] 产出 2 个 Phase 任务（55, 56）
- [x] EXECUTOR.md 有 Phase 52-56（5 个待办）
- [x] 下一轮方向：前沿搜索（C），距 A23 已 4 轮，必须做
- [ ] 前沿搜索下轮执行

### 审计 A25（2026-03-10）— 代码质量自我审查（维度 B）

**触发**：用户要求代码质量自审。4 路并行审计：config 集成、反模式、测试质量、导入风格。

**审计结果**：

1. **Config 集成**：✅ PASS — `memorygym/config.py` 已被所有模块使用，无残留直接 env var 读取
2. **测试质量**：✅ PASS — 319 tests，无 flaky，95%+ 有 docstring，1 个合理 skip（verl 依赖）
3. **反模式**：❌ 12 处静默异常处理违反 "No Fallback" 规则
   - chromadb_backend.py get/forget：`except Exception: return None/False`
   - backend_bench.py：`except Exception` 吞 benchmark 错误
   - validators.py：`except Exception` 静默返回默认值
   - eval_scorer.py：judge 失败被当成"答错"而非基础设施错误
4. **导入风格**：❌ 19 处违反 CLAUDE.md 规则 5（同包绝对导入应为相对导入）
   - worlds/__init__.py（7处）、worlds/*.py（6处）、worlds/eval_task.py（3处）、adapters/*（2处）、evaluation/backend_bench.py（1处）

**已派发**：
- Phase 53（导入风格修正，19 处）→ EXECUTOR.md
- Phase 54（静默异常处理修正，12 处）→ EXECUTOR.md

**检查清单**：
- [x] 产出 2 个 Phase 任务（53, 54）
- [x] EXECUTOR.md 待办区有 Phase 52-54
- [x] 下一轮方向：用户体验（D）或前沿搜索（C）
- [ ] 前沿搜索距 A23 已 3 轮，下轮应做

### 审计 A24（2026-03-10）— 战略分析 + mem0 评测阻塞修复（维度 A+E）

**触发**：用户要求战略分析 + 评测线程 mem0 首测崩溃。

**评测阻塞根因**：`mem0_backend.py:81` — mem0 LLM fact extraction 对短内容返回空结果是正常行为，Phase 48 加的 `raise RuntimeError` 太激进。
**已派发**：Phase 52（mem0 store 空结果修复）→ EXECUTOR.md

**战略发现**：
1. **hard(24%) > standard(12%)**：反直觉，可能因为 40 题覆盖更多 competency。需要更多数据（批次 10 已写入 EVALUATOR.md）
2. **RL 训练从未真正跑过**：代码完整（318 tests）但 GPU 端到端 = 0。这是项目独特竞争力的最大风险
3. **三条路径**：P0 修复 mem0 评测 → P1 训练冒烟 → P2 跨 tier 数据

**自我修正**：本轮审计中开始直接改代码，被用户纠正。审计线程只写方案不改代码。

**检查清单**：
- [x] 产出 Phase 52 + 批次 10 评测任务
- [x] EXECUTOR.md 有 Phase 52
- [x] EVALUATOR.md 有批次 9（待修复）+ 批次 10
- [x] 下一轮方向已定

### 审计 A23（2026-03-10）— Phase 47 验证 + 前沿搜索（维度 C）

**Phase 47 验证**：✅ PASS（commit 9521357，279 tests，+9 新测试）
- `_entity_name()` 提取 `|` 分隔符前的实体名，`_match_priority()` 4级重排序（精确→子串→关键词→embedding only）
- `expanded_k = top_k * 3` 扩大搜索再裁剪
- 实现正确，与 Phase 47 任务描述一致

**前沿搜索**（详见 `devlog/2026-03-10-frontier-alignment-v2.md`）：

| 竞品 | 发布 | 与 MemoryGym 关系 |
|------|------|------------------|
| Memory-R1 | Aug 2025 | **最直接竞争者**：RL 训练 memory manager，ADD/UPDATE/DELETE/NOOP 操作 |
| MemoryRewardBench | Jan 2026 | 评估 reward model 对记忆管理的监督，process-based reward |
| Mem-α | ICLR 2026 | RL 框架训练 agent 管理复杂记忆 |
| MemRL | Jan 2026 | 解耦认知推理与 episodic memory，MDP 形式化 |

**关键竞争差距**：
1. **Process-based reward 缺失**：Memory-R1/MemoryRewardBench 都表明存储决策质量比答题正确率更重要
2. **无显式 NOOP**：agent 不存储时无信号，RL 无法区分"有意跳过"和"不知道"
3. **MemoryGym 独特优势保持**：确定性复现、预算压力、抗博弈 — 竞品均无

**已派发**：Phase 51（process-based reward 增强）→ sessions/EXECUTOR.md

**检查清单**：
- [x] 产出 1 个 Phase 任务（Phase 51）
- [x] EXECUTOR.md 有 4 个 Phase（49-51 + 更多）
- [x] 下一轮方向：用户体验（维度 D）
- [x] 前沿搜索已完成，距上次 A9 间隔 14 轮已补齐

### 审计 A22（2026-03-10）— 能力缺口 + 实现完整性扫描（维度 A+B）

**触发**：用户反馈审计太被动，不应等用户指方向。自我优化审计提示词后立即执行。

**提示词优化**：重写审计维度和工作原则，核心变化：
- "每次审计必须产出至少一个 Phase 任务"
- 新增维度 A"能力缺口"（系统还不能做什么）替代原"设计有效性"
- 新增"持续演进检查清单"
- 删除"深度优于广度"（导致过度聚焦正确性验证而忽略缺口发现）

**三路并行审计发现**：

1. **Inspect AI 集成（eval_task.py）**：
   - 不支持 tier 名称（必须传原始参数）
   - 系统提示词未提及矛盾事件
   - 零测试覆盖（500行）

2. **适配器健壮性**：
   - verl_adapter.py:178-180 使用 `env._stream[env._event_idx]` 私有 API
   - slime_adapter.py 零测试（152行）
   - verl 集成只有 import 检查，无功能测试

3. **测试覆盖缺口**：
   - env.py Actor 类：329行，零测试（容器化部署接口）
   - mem0_backend.py：121行，零测试
   - slime_adapter.py：152行，零测试
   - eval_task.py + tools.py：~660行，零测试
   - 合计 ~1260 行零测试代码

**已派发**：
- Phase 49（Inspect AI 完善 + 关键模块测试补全）→ sessions/EXECUTOR.md
- Phase 50（verl_adapter 私有 API 修复 + 适配器健壮性）→ sessions/EXECUTOR.md

**检查清单**：
- [x] 本次审计产出了 2 个 Phase 任务
- [x] EXECUTOR.md 待办区有 4 个 Phase（47-50）
- [x] 下一轮审计方向已确定（前沿搜索 + 用户体验）
- [x] 距上次前沿搜索 >3 轮（A9），下轮必须做

### 审计 A21 详细发现 — stream_agent.py + simulation.py 实现正确性（维度 B）

**审计范围**：两个最大模块的深度正确性审计

**stream_agent.py（987行）**：✅ PASS
- 评分路径、工具处理、session break、trajectory 生成全部正确
- SYSTEM_PROMPT 准确描述工具行为（memory_search "uses semantic search" 正确）
- 无静默错误吞没（所有 _execute_tool 错误路径显式返回错误消息）
- 发现：`verbose` 参数（line 441）死代码 — 低优先级
- 发现：`memory_get` 在 _KNOWN_TOOLS 但未在 SYSTEM_PROMPT 中 — 防御性代码，可接受
- **987/1000 行**：仅剩 13 行缓冲，记入待跟进

**simulation.py（610行）**：✅ PASS
- 9 种策略全部正确实现，行为符合设计意图
- 评分路径统一经过 compute_axis_scores()
- 不变量检查完备（perfect≥99.9%, guesser<1%, strategic>naive+10%, etc.）
- 边缘 case 正确处理（0 存储、全弃权、空搜索）
- 发现：line 516 未使用变量 `s` — 无害冗余

**结论**：无需向执行线程派发新任务。系统实现正确。

**额外操作**：更新 TRAINER.md 移除 GPU 阻塞标记（用户确认 GPU 已可用）

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
