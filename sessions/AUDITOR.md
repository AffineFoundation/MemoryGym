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

### 已归档审计（A381-A425）

- **A381-A398**：bench.py 重试验证、Mistral 10 evals #1(24.3%)、LEADERBOARD 更新至 199 evals、前沿搜索 V36-V38(F182-F191)、base.py 微观审计零问题、NeurIPS 2026 E&D Track 确定(May 4/6)
- **A399-A403**：PA-16 NeurIPS 投稿准备派发、Writer PA-16 ~60%、前沿搜索 V39(F192-F194)、LongMemEval 引用通知
- **A404-A406**：低频巡航状态检查、Writer 完成 LongMemEval 引用(commit `5bfe833`)
- **A407-A414**：PA-17 创新性深化（4 data insights）派发→验收(commits `c232571`+`bf4a307`)、前沿搜索 V40(F195)
- **A415-A420**：PA-18 链条断裂分析派发→验收(commit `148efb2`)、PA-19 红队防御派发→验收(commit `bec5eeb`)、H4 correlation(commit `57dc544`)
- **A421-A425**：Trainer T1/T2 任务设计(4×H200)、TRAINER.md 防御性重写(20+ fault scenarios)、vLLM 必需性代码审计

---

### 已归档审计（A426-A443）

- **A426-A427**：H4 验收(commit `57dc544`) ✅、前沿搜索 V41(F196-F197: MemoryBench 竞品 + MemOS 生态机遇)
- **A428-A433**：Trainer 反馈机制建立(TRAINER.md 进度日志区)、Trainer 5 轮无活动→阻塞报告
- **A434-A443**：论文就绪度盘点(PA-16)、validators.py 零问题(A436)、README/CLI 文档审计(A437)、归档压缩(A438)、protocol.py 复查 2M+4L(A439)、前沿 V42 零新发现(A441)、NeurIPS E&D 不要求完全匿名化(A441)

---

### 已归档审计（A444-A505）

- **A444-A453**：Trainer T1 启动→Step 0-4 跟踪（4×H200, SFT 训练 37min, base 评测 30 runs）。A453 发第一次停滞报告
- **A454**：训练模块微观审计 — 1 CRITICAL(env.py:744 越界) + 2 HIGH(adapter info 未初始化, verl_reward 静默 fallback) + 2 MEDIUM
- **A455-A459**：Trainer 跟踪 + 归档。A456 前沿 V43（饱和，≈0 新发现，累计 197）
- **A460**：bench.py 审计 — 2 HIGH(无 except, client 泄漏) + 3 MEDIUM(无 timeout, 静默吞异常)
- **A461-A462**：第二次停滞报告 + 状态检查
- **A463**：⚡ Step 4 完成！Base 7B: C=13.8±8.4% (B=23.0,M=8.4,R=11.9,E=9.2) — 30 runs × 3 templates
- **A464-A474**：Step 5 SFT 评测跟踪（11 轮）
- **A470**：⚠ SFT 中期 C=4.1% — 退化 9.7pp。3 假设分析（merge/格式/过拟合）
- **A475**：Step 5 完成。SFT C=4.9% 确认退化 8.9pp
- **A476-A477**：格式审计排除格式不匹配。RL adapter 格式兼容问题记录
- **A478-A482**：方案 B（adapter 模式不 merge）初步 20% 但最终也退化
- **A483**：T1 完成 — SFT 全面失败（merged C=4.9%, LoRA C≈5%），merge 非根因
- **A485**：过拟合确认（3ep loss=0.07）。1ep lr=1e-5 重训启动
- **A486-A492**：1ep 跟踪 + 停滞报告
- **A493**：1ep SFT C≈15% — 与 base 持平。T1 最终结论：SFT 对 7B 无效
- **A494**：Phase 134 派发（5 Steps, 1 CRITICAL + 4 HIGH — env.py/adapters/bench.py/stream_agent.py）
- **A495-A499**：3B 实验跟踪。3B SFT 也退化 7pp。停滞报告
- **A500**：simulation.py 微观审计 — 零问题（652 行，24 competency 全覆盖）
- **A501**：⚡ 3B 结果 — Base 3B C=28.9% >> Base 7B 13.8%（意外！需多模板验证）。SFT 数据质量确认为根因
- **A502-A505**：Trainer 跟踪 + protocol.py 微观审计零问题（257 行）。Base 3B 完整评测启动中。SFT 训练信号方向有误

---

### 审计 A506 — 归档压缩 + validators.py 微观审计（维度 D/B）✅

**归档**：A444-A505（62 条审计）压缩为 22 行摘要。AUDITOR.md 从 ~909 行 → 187 行。

**validators.py（273 行）：零问题 ✅**。24 competency 路由完整（numeric_match 12 + synthesis_match 5 + entity_match 4 + temporal_trend 1 + abstention 1 + exact match 前置），与 simulation.py 和 protocol.py REASONING_COMPETENCIES 完全对齐。

**Trainer**：无新更新（Base 3B 完整评测第 3 轮等待）。

**代码质量审计汇总（A500-A506 停滞期）**：
- simulation.py（652 行）：零问题 ✅
- protocol.py（257 行）：零问题 ✅
- validators.py（273 行）：零问题 ✅
- **3 大评分核心模块全部通过**，代码健康度高

**下一轮**：A507。维度 E — Base 3B 完整评测结果跟踪。如 A508 仍无更新则发停滞报告。

---

### 审计 A507 — Base 3B 评测跟踪（维度 E）✅

Trainer 日志无新条目（第 4 轮等待）。无新 commit。Base 3B 30 runs × 3 templates 按历史节奏 ~4h 应已完成但 Trainer loop 可能断开。

**下一轮**：A508。维度 E — 停滞报告触发轮。

---

### 审计 A508 — ⚠ Base 3B 完整评测停滞报告（维度 E）✅

**Base 3B 评测日志停留 5 轮（A504-A508）**。最后记录：「Base 3B 完整评测启动中 (30 runs, 3 templates)」。无新 commit。

**评估**：30 runs × 3 templates = 90 runs，按 ~8min/run ≈ 12h。即使考虑较长耗时，5 轮审计间隔已远超预期完成时间。

**最可能原因**：Trainer loop 断开。历史模式一致 — Trainer 在长时间批量评测中 loop 超时或 SSH 断开，评测可能已完成但结果未写入日志。

**全线程停滞汇总**：
- **Trainer**：Base 3B 完整评测，5 轮无更新。loop 可能断开
- **Executor**：Phase 134 待执行，无新 commit。loop 未启动
- **Evaluator**：空闲
- **Writer**：PA-16 继续（独立仓库）

**建议用户**：
1. 确认 Trainer 远程 3B 评测是否已完成
2. 如已完成，重启 Trainer loop — 日志会自动追加结果
3. 如需要 Phase 134 执行，启动 Executor loop

**审计资源利用**：停滞期已完成 3 大评分核心模块审计（simulation.py + protocol.py + validators.py），全部零问题。代码库健康度高。

**下一轮**：A509。维度 E — 等待用户响应或 Trainer 更新。进入低频巡航，不再重复停滞报告。

---

### 审计 A509-A511 — 低频巡航（维度 E）✅

A509-A511：全线程停滞继续。无新 commit，Trainer 日志无变化。A508 停滞报告待用户响应。

**下一轮**：A512。巡航。如有更新则立即跟进。

---

### 审计 A512 — ⚡ Base 3B 完整评测结果分析（维度 E）✅

**Base Qwen2.5-3B 完整结果（30/30 runs × 3 templates）**：

| 模板 | C | B | M | R | E |
|------|---|---|---|---|---|
| company (n=10) | 27.1% | 33.0 | 18.9 | 34.5 | 19.3 |
| university (n=10) | 27.3% | 34.0 | 17.9 | 35.2 | 19.3 |
| city (n=10) | 34.1% | 42.2 | 25.1 | 41.8 | 23.7 |
| **Overall (n=30)** | **29.5±11.3%** | **36.4** | **20.6** | **37.2** | **20.8** |

**vs Base Qwen2.5-7B**：

| 轴 | 3B | 7B | 差异 |
|----|----|----|------|
| Composite | **29.5%** | 13.8% | **+15.7pp** |
| Breadth | 36.4% | 23.0% | +13.4pp |
| Maintenance | 20.6% | 8.4% | +12.2pp |
| Reasoning | 37.2% | 11.9% | +25.3pp |
| Efficiency | 20.8% | 9.2% | +11.6pp |

**vs Chutes 大模型排行榜**：

| 排名 | 模型 | Composite |
|------|------|-----------|
| **#1** | **Base Qwen2.5-3B (local vLLM)** | **29.5%** |
| #2 | Mistral-Small-24B (Chutes) | 24.3% |
| #3 | Qwen3-235B (Chutes) | 18.6% |
| #4 | Qwen3.5-397B (Chutes) | 18.3% |

**审计分析 — 3 个关键问题**：

**1. 结果可信吗？3B 超过 397B？**

⚠ **可比性存疑**。需排查以下差异：
- **Judge model 不同**：Trainer 用 `MEMORYGYM_JUDGE_MODEL` 覆盖了 judge（本地 vLLM 模型），Chutes 评测用 Chutes API 模型。不同 judge 可能对同一答案给出不同判定
- **API 延迟差异**：本地 vLLM 无网络延迟，Chutes API 有延迟 → 可能影响 timeout 行为
- **模板覆盖**：3B 只测了 3 个模板（company/university/city），Chutes 模型测了 10 个模板。3B 在其他 7 个模板上可能不同
- **SD=11.3%** 很高（变异系数 38%），部分 runs 可能极端偏高

**2. 如果结果可复现 → 论文级发现**

"3B 模型在 MemoryGym 上超过 397B 模型" 是反直觉的发现。可能原因：
- (a) 3B-Instruct 的 tool-use 训练更高效
- (b) 大模型生成更冗长，在固定预算下浪费更多 writes
- (c) 3B 更严格遵循系统提示的存储指令
- (d) Judge model 差异（最需排查）

**3. 下一步建议**

- **P0（验证可比性）**：用 Chutes 模型跑一轮 Base 3B（如果有 Qwen2.5-3B-Instruct 在 Chutes 上），或用本地 vLLM 跑一个 Chutes 模型（如 Qwen3-235B）作为对照
- **P1（扩展模板）**：3B 在剩余 7 个模板上跑，看是否一致
- **P2（SFT 重试）**：既然 Base 3B 这么强，用它自己的高分轨迹做 SFT 数据（on-policy SFT）

**Trainer 下一步**：日志显示"论文可用数据: Base 3B C=29.5%, Base 7B C=13.8% — 模型尺寸对比"。Trainer 可能认为可以直接用这组数据。但**审计认为可比性问题必须先解决**。

**下一轮**：A513。维度 E — Trainer 后续行动跟踪（是否做可比性验证）。

---

### 审计 A513 — ⚡ Phase 134 验收 + T2 GRPO 启动（维度 B/E）✅

**Phase 134 验收**（commit `9e0d7b7`，8 files, +29/-9）：

| Step | 修复 | 验证 |
|------|------|------|
| 1 | env.py:744 submit_answer 越界 → `current_event is None` 保护 | ✅ 正确使用已有变量 |
| 2 | verl/slime adapter info 初始化 | ✅ 各加 1 行 `info: dict = {}` |
| 3 | verl_reward.py `pass` → `return 0.0` | ✅ 显式返回，无歧义 |
| 4 | bench.py 加 `except Exception as e` + `continue` | ✅ 单 seed 失败不中断后续 |
| 5 | stream_agent.py client try/finally | ✅ 22 行变更含 cleanup |

**Phase 134 验收通过 ✅**。版本号已更新，pyproject.toml 同步。A454+A460 发现的 1 CRITICAL + 4 HIGH 全部修复。

**Trainer T2 启动 — GRPO on Base 3B**：
- 跳过 SFT 前提（SFT 已证明无效），直接 RL
- 配置：Qwen2.5-3B, lite tier, steps=5 smoke test, group_size=4, lr=1e-5, LoRA rank 16
- 进行中

**审计评估**：
1. **Phase 134 为 T2 扫清障碍**：env.py 越界 + adapter 未初始化修复确保 GRPO 不会因代码 bug 崩溃
2. **Trainer 是否 pull 了 Phase 134？** commit `9e0d7b7` 在 Trainer 启动 T2 之前。如果 Trainer pull 了最新代码，则 GRPO 使用修复后的 env.py。需确认
3. **GRPO smoke test（5 steps）是正确策略**：先验证 RL 管线能跑通，再扩大训练
4. **A512 可比性问题仍需关注**：Trainer 直接进入 GRPO 而非验证 3B vs 大模型的可比性。这可接受 — GRPO 的 before/after 对比不依赖跨模型对比

**下一轮**：A514。维度 E — T2 GRPO smoke test 结果跟踪。

---

### 审计 A514 — T2 GRPO smoke test 跟踪（维度 E）✅

Trainer 日志无新条目（T2 GRPO "进行中..."，第 1 轮等待）。无新 Trainer commit。

**预期时间线**：GRPO smoke test（5 steps × lite tier × group_size=4）— 每 step 需 rollout（env.py 交互）+ reward 计算 + 梯度更新。首次运行可能需 debug 管线问题。预计 1-4h。

**Phase 134 已验收通过**（A513）。Executor 任务清空。

**下一轮**：A515。维度 E — T2 GRPO 结果跟踪。

---

### 审计 A515 — T2 GRPO 跟踪（维度 E）✅

无新更新（第 2 轮）。GRPO smoke test 仍在进行中。首次 RL 管线运行常需 debug，正常等待。

**下一轮**：A516。维度 E — T2 GRPO 跟踪。如 A518 仍无更新则发停滞报告。

---

### 审计 A516 — T2 GRPO 跟踪（维度 E）✅

无变化（第 3 轮）。GRPO smoke test 首次运行，可能在 debug RL 管线（verl adapter + env.py 交互）。

---

### 审计 A514-A518 — T2 GRPO 跟踪 + 停滞报告（维度 E）✅

A514-A517：T2 GRPO smoke test 跟踪，4 轮无更新。

**A518 停滞报告**：T2 GRPO 日志停留 5 轮（A514-A518）。最后记录：「配置: Qwen2.5-3B, lite tier, steps=5 smoke test, group_size=4, lr=1e-5, LoRA rank 16 — 进行中...」

**可能原因**：
1. **RL 管线 bug**（最可能）：首次 GRPO 运行，verl adapter + MemoryEnv 交互链长（rollout → reward → gradient），任何环节报错都会阻塞。虽然 Phase 134 修复了已知 bug，但 RL 管线有更多潜在问题（GPU 内存、tokenizer 兼容性、reward 函数等）
2. **Trainer loop 断开**：GRPO 正在训练但 loop 未更新日志
3. **GRPO 运行正常但极慢**：5 steps × lite tier 但 rollout 需要 env.py 全流程交互（60 events × group_size=4），每 step 可能耗时较长

**建议用户**：请确认 Trainer T2 GRPO smoke test 状态。如遇到 RL 管线 bug，Trainer 日志应记录错误信息以便审计分析。

**下一轮**：A519。维度 E — 等待用户响应或 Trainer 更新。进入低频巡航。

---

### 审计 A519 — 低频巡航（维度 E）✅

无变化。A518 停滞报告待用户响应。

---

### 审计 A520 — ⚡ GRPO 代码路径审计 + Phase 135 派发（维度 B/E）

**触发**：用户反馈"训练者一直在调试，太慢了效率太低了"。主动审计 `memorygym/training/cli.py` GRPO 代码路径，找到 Trainer 受阻根因。

**Trainer T2 状态**：v1 配置（group_size=4, max_turns=100）→ 67min 未完成 1 step。v2 配置（group_size=2, max_turns=40）重启，仍"进行中"。

**GRPO 代码路径审计结果（`training/cli.py`）**：

**🔴 BLOCKER（1 个）**：
1. **cli.py:648-650 — 零损失 fallback 阻断梯度流**：当所有 trajectory 被跳过时，`total_loss = torch.tensor(0.0, requires_grad=True)` 创建无计算图的张量。`loss.backward()` 不会通过模型 → 该 step 模型完全不训练。这解释了为什么 Trainer 可能看到 loss 但模型不改善。

**🟠 HIGH（5 个）**：
2. **cli.py:582-583 — 静默跳过 advantage≈0 的 trajectory**：`if abs(advantage) < 1e-6: continue` 无任何 warning。GRPO 中 group 内 advantage 归一化后如果 reward 方差小，大量 trajectory 可能被跳过，导致有效训练样本极少。这是 T2 "跑很久无结果"的可能原因。
3. **cli.py:624-627 — KL 用几何均值而非算术均值**：`ratio = torch.exp(mean_log_ratio)` 等价于 `exp(E[log(π/π_ref)])`（几何均值），正确的 KL 散度应是 `E[π/π_ref * log(π/π_ref)]` 或至少 `E[log(π/π_ref)]`。当前实现错误地对 ratio 取指数后再乘 advantage。
4. **cli.py:651-652 — loss 归一化不一致**：`n_valid > 1` 时除以 `n_valid`，但 `n_valid == 1` 时不除。这意味着单 trajectory batch 的梯度量级与多 trajectory batch 不同。
5. **cli.py:633 — PPO 风格 min(surr1, surr2) 而非 GRPO**：GRPO 论文使用 per-token ratio clipping，而当前代码在 sequence-level ratio 上做 PPO-style clipping。与函数名和注释声称的"GRPO"不符。
6. **cli.py:470 — MemoryEnv 异常时未 close**：`_run_episode` 中 env 创建后无 try/finally，异常时 ChromaDB 资源泄漏。

**🟡 MEDIUM（2 个）**：
7. **cli.py:585 — `torch.cuda.empty_cache()` 每个 trajectory 调用一次**：在内循环中清缓存导致 3-5x 性能下降。应移到 step 级别或完全移除。
8. **cli.py:593-595 — 潜在 device 不匹配**：`build_assistant_mask` 返回 CPU tensor 再 `.to(model.device)`，但中间计算可能在错误 device 上。

**红队自我攻击**：

| 攻击维度 | 分析 | 通过？ |
|----------|------|--------|
| 根因 | BLOCKER（零损失 fallback）和 HIGH#2（静默跳过）直接解释 Trainer 受阻 | ✅ |
| 前沿价值 | 修复 GRPO 管线是产出训练结果的前提，有直接论文价值 | ✅ |
| ROI | 修改约 30 行代码，解锁整个 RL 训练管线 | ✅ |
| 实现风险 | 仅修改 training/cli.py，不影响 eval/simulation/bench | ✅ |
| 约束兼容 | 训练代码修复，与 5 条核心约束无关 | ✅ |
| 替代方案 | 无。这些是代码 bug，必须修复 | ✅ |

**决策**：派发 Phase 135 到 EXECUTOR.md。

**下一轮**：A521。维度 E — Phase 135 执行跟踪 + Trainer T2 结果。

---

### 已归档审计（A341-A380）

*(A341-A380 详细摘要见前次归档。关键：Phase 129-133 验收、前沿搜索 V31-V36(F164-F186)、论文事实核查+红队攻击、validators.py/simulation.py/stream_agent.py 全模块深度审计。)*

*(A211-A340 历史记录已归档，覆盖 2026-03-12 至 03-13 的中后期审计。关键里程碑：Phase 112-129 验收、前沿搜索 V14-V31(F52-F167)、Batch 34-38 数据分析、10 模板扩展完成、173 evals 积累、论文写作+审稿人攻击防御 PA-1 至 PA-12。)*

*(A78-A210 历史记录已归档，覆盖 2026-03-11 至 03-12 的中期审计。关键里程碑：Phase 71-113 验收、前沿搜索 V8-V12(F1-F51)、Batch 16-33 数据分析、Phase 112 correction Edit 免预算、8→10 模板扩展。)*

*(A1-A77 历史记录已归档，覆盖 2026-03-09 至 03-11 的早期审计。关键里程碑：Phase 30-68 验收、前沿搜索 V1-V8、Batch 1-15 数据分析、系统架构从 4 模板扩展到 8 模板。)*
