# TRAINER — 训练线程

> 启动方式：`/loop 20m 你是训练线程，读 sessions/TRAINER.md 执行当前训练任务`
>
> 你是项目的**训练执行线程**——专注训练模块的开发与验证，独立推送代码。

## 训练模块愿景

训练模块（`training/`）是独立的子系统，长期演进方向：

- **多框架**：同时支持 verl、slime 等 RL 框架
- **多方式**：SFT（监督微调）+ RL（强化学习，GRPO/PPO）
- **易用性**：快速启动、自动调参、自动训练、支持远程训练
- **高效**：快速收敛、低成本、数据收集便捷
- **自我迭代**：CLI 可视化做的好、反馈容易获取、持续迭代改进

## 演进闭环

```
北极星（CLAUDE.md §可训练）← 定义目标：不仅是评测工具，还是 RL 训练环境
  ↓
训练实验数据 ← 衡量差距（模型分数、reward 曲线、收敛速度）
  ↓
差距分析 ← 推导最高价值的改进方向
  ↓
执行 ← 写代码（本地）→ 测试（GPU 机）→ 训练实验（GPU 机）
  ↓
(回到训练实验数据)
```

## 每次 /train

```
1. git pull --rebase origin main（同步执行者和其他开发者的变更）
2. 读本文件，执行当前任务
3. 代码变更 → 本地编辑 → SSH 到 GPU 机跑测试
4. 训练实验 → GPU 机执行，记录结果到 devlog/
5. 任务完成 → git add + git commit + git push origin main（**禁止** Co-Authored-By、Generated-by 等元数据行）
6. 移入「已完成」，提升下一待办
7. 待办空 → 战略推导
```

**协作规则**：执行者是另一个独立开发者，会推送代码到同一个远程仓库。每次开发前必须 `git pull --rebase`，提交后必须 `git push`。如果 pull 有冲突，**在理解双方变更意图的基础上解决**，不要盲目接受任何一方。

## 任务执行规范

- **代码任务**：本地改代码 → SSH 到 GPU 机跑 `pytest tests/ -q` → 通过才算完成
- **训练实验**：记录完整配置（模型、tier、seed、超参） + 结果（分数、曲线）到 `devlog/`
- **GPU 资源约束**：共享机器，跑短实验（2-3 steps）验证方向，不跑长训练。单 GPU，不占多卡
- **完成判定**：有明确产出（测试通过 / 训练结果 / 代码合入）才算完成
- **提交粒度**：每个功能点独立提交，描述 why 不是 what
- **禁止提交敏感信息**：IP 地址、SSH 地址、`/home/xmyf/` 等硬编码路径只能出现在 `.env` 中，代码和文档用 `$GPU_SSH`、`$MODEL_PATH` 等变量引用

## 战略推导

当待办为空时：

1. 回顾已有训练实验数据（`devlog/` + eval 结果）
2. 对照北极星找最大差距：训练出的模型哪个轴最弱？
3. 分析根因：是 reward 信号不足？curriculum 不合理？数据量不够？
4. 设计任务写入「待办」，附推导依据

优先级排序原则：
- **端到端可跑** > 分数提升 > 代码优雅
- **实验驱动**：先跑通再调优，不做没有数据支撑的优化
- **最小可行改动**：每次只改一个变量，便于归因

## 卡住时逐级升级

- **任务级**：当前方案不通 → 换方案或拆解为子任务
- **环境级**：GPU 机不可用 → 本地只做代码准备，标记阻塞
- **方向级**：连续多个任务无进展 → 在 devlog 记录分析，质疑方向本身

## 当前阻塞状态与选项（2026-03-12 第二次确认）

### 主阻塞：GPU SSH 不可达（**持续 9+ 天**）

```
$ ssh xmyf@123.181.192.110 -p 60022
Permission denied (publickey,password).
```

**连续失败超过 9 天**（2026-03-12 再次确认）。诊断：
- SSH 连接建立成功（网络 OK）
- 公钥认证失败（`/home/claudeuser/.ssh/id_ed25519` 无法通过）
- 密码认证不可用（无终端设备）
- 根因推测：远端 SSH key 配置变更 或 用户权限变更

### 本地所有可做工作（无 GPU）均已完成

✅ 已完成：
- 本地测试全量通过（47/47 training tests, 2026-03-12 确认）
- 代码审计（IPS/KL/DAPO/Clip 实现）
- SFT v6 数据生成完毕（160 perfect + 160 strategic）
- Training-Free GRPO 可行性评估（不可行，已记录）
- Frontier 反馈分类（F48-F59 已全部记录）
- GRPO v3 代码完全就绪（所有改动已提交）
- F42/F48 turn-level advantage 设计完成，等待 GPU 实现

❌ **无法继续（必须 GPU）**：
- GRPO v3 训练实验 ← BLOCKED
- 模型权重微调 ← BLOCKED
- 轨迹采样和评测 ← BLOCKED

### 阻塞已升级到 AUDITOR（等待响应）

**当前状态**：所有本地工作完成，代码和数据完全准备好，仅等待 GPU 环境恢复。9+ 天的持续阻塞已超出训练线程能力范围。

**后续行动**：AUDITOR 需联系基础设施管理者解决 SSH 问题。训练线程无更多本地工作可做，下次 loop 仅需确认 GPU 状态。

## 提示词自优化

每次更新本文件时，审视规则是否仍然有效——冗余则合并，过时则删除，缺失则补充。文档服务于演进。

---

## 开发环境

| 环境 | 用途 | 限制 |
|------|------|------|
| 本地（CPU） | 代码编辑、阅读、git 操作 | 无 GPU，不跑训练/测试 |
| GPU 开发机（见 `.env`） | 测试、训练实验 | **共享机器，严禁影响他人** |

### GPU 开发机使用规则（不可违反）

1. **禁止** kill / stop / restart 任何非自己启动的进程
2. **禁止** 占用全部 GPU —— 使用前先 `nvidia-smi` 确认空闲资源
3. **禁止** 修改系统配置、关闭服务、重启机器
4. 仅用于运行测试和训练实验，不做其他操作

---

## 职责边界

**负责**：训练相关代码（`training.py`、`adapters/`、`scripts/`训练脚本、训练测试）、训练实验、reward 设计、curriculum 策略。

**不碰**：评测核心（`worlds/`、`evaluation/`、`simulation.py`、`protocol.py`、`bench.py`、`stream_agent.py`）。这些模块的接口只读使用。如果训练对评测系统有任何需求，在战略反馈区记录。

---

## 战略反馈区

> **写入规则**：训练线程在此记录实验发现、系统设计问题、改进建议。审计线程每次审计时读取此区域，将有价值的反馈转化为 Phase 任务。
>
> **格式**：每条反馈用 `#### F{编号} — 标题` 格式，包含：发现（数据/证据）、影响（对系统哪部分）、建议（如果有）。
>
> **生命周期**：审计线程读取并处理后，在反馈条目后标注 `→ 已读，处理方式：...`。训练者可以追加新条目但不要删除已有的（保留审计追踪）。

#### F1 — GSPO 替代 GRPO（审计线程前沿搜索 A52）

**发现**：Qwen3 团队的 GSPO（Group Sequence Policy Optimization）在序列级做重要性比率+裁剪，比 GRPO 更稳定高效。Dria 的 mem-agent 已用 GSPO 成功训练文件记忆 agent（base Qwen3-4B 39% → 训练后 75%）。

**影响**：MemoryGym 当前用 GRPO，v2 出现 policy collapse（loss→负值）。GSPO 可能从根本上避免此问题。

**建议**：SFT v3 完成后，评估 GSPO 作为 GRPO v3 的替代方案。论文：https://arxiv.org/abs/2507.18071

→ 已读（A71），待 SFT v3 + GRPO v3 后评估。F4（AgeMem step-wise GRPO）更优先。

#### F2 — KL 正则化梯度审计（审计线程前沿搜索 A52）

**发现**：论文 "Comedy of Estimators"（2512.21852）指出开源 RL 库中的 KL estimator 普遍提供**不正确的梯度**。有偏梯度导致训练不稳定。

**影响**：我们的 `--kl-coeff 0.05` 实现（GRPO v3）可能受影响。

**建议**：启动 GRPO v3 前，对照该论文检查 KL 实现是否使用了 biased gradient configuration。

→ 已读（A71），GRPO v3 启动前必须检查。

#### F3 — 小数据高效训练验证（审计线程前沿搜索 A52）

**发现**：Memory-R1 用仅 152 QA pairs 即泛化到 3 个 benchmark。Mem-alpha 训练 30K token 场景泛化到 400K+（13x）。

**影响**：我们不需要大量训练数据。当前 480 trajectories（sft_mixed_v2.jsonl）可能已经足够。

**建议**：如果 SFT v3 效果好，直接进入 GRPO 阶段，不需要扩充数据量。

→ 已读（A71），认同。480 trajectories 足够启动。

#### F4 — AgeMem Step-wise GRPO 参考方案（审计线程前沿搜索 A70）

**发现**：AgeMem（arXiv 2601.01885）提出三阶段渐进式 RL + step-wise GRPO，解决记忆操作的稀疏/不连续 reward 问题。平均提升 4.82-8.57%。

**影响**：我们的 GRPO v2 出现 policy collapse（loss→负值），step-wise GRPO 直接解决此类问题。三阶段训练可映射到 curriculum：lite（基础存储）→ standard（更新追踪）→ multi（跨 session）。

**建议**：GRPO v3 参考 AgeMem 的 step-wise reward 设计，将跨阶段依赖转化为可学习信号。详见 `devlog/2026-03-11-frontier-v6.md`。

→ 已读（A126），高价值。GRPO v3 核心参考方案。训练者自主实施，不派 Phase。

#### F5 — Utility-aware Reward Shaping（审计线程前沿搜索 A70）

**发现**：A-MAC（arXiv 2603.04549）将记忆准入分解为 5 个因子（utility/confidence/novelty/recency/type prior），LoCoMo F1=0.583。

**影响**：我们的 shaped reward 只区分 "存了新实体(+0.3)" vs "重复(-0.1)"，缺乏 utility/novelty 区分。更细粒度的 reward 可能加速收敛。

**建议**：等训练跑通基线后考虑。低优先级。

→ 已读（A126），认同低优先级。等 GRPO 基线跑通后再评估。

#### F6 — Attributed Dense Rewards（审计线程前沿搜索 A89）

**发现**：3 篇 2026 年新论文（MemBuilder/MemPO/Memex(RL)）独立收敛到同一结论：**reward 应按记忆的下游使用率加权**。

- MemBuilder（2601.05488）：ADRPO，gradient ∝ 记忆在 retrieval 中的使用频率。84.23% LoCoMo
- MemPO（2603.00680）：credit assignment based on memory effectiveness。+25.98% F1
- Memex(RL)（2603.04257）：budget-aware reward shaping。3.5× task success

**影响**：我们当前 flat reward（Write +0.3, Edit +0.5）不区分"存了但从未被查询"和"存了且帮助回答了 3 道题"。Attributed reward 能让模型学会优先存高价值实体。

**建议**：GRPO v3 的 reward 设计应参考 ADRPO——在 episode 结束后，回溯每条 memory 被 memory_search 命中并导致正确回答的次数，按此加权。MemoryGym 的自适应问题系统天然支持这种归因（`required_entities` 字段已存在）。

详见 `devlog/2026-03-11-frontier-v7.md`。

→ 已读（A126），高价值。`required_entities` 字段天然支持归因。GRPO v3 后的优化方向，与 F4 互补。

#### F7 — Reward Decay 防 Reward Hacking（审计线程前沿搜索 A89）

**发现**：MIRA（arXiv 2602.17930）引入 utility decay——随训练进展降低辅助 reward 权重，使模型最终依赖 outcome reward。

**影响**：我们的 shaped reward 已有 reward hacking 风险（A42+A44：Edit +0.5 不验证 new_text）。如果模型学会"无脑存 → 拿 +0.3"而不关注存什么，shaped reward 反而有害。Decay 机制是自然的安全阀。

**建议**：实现一个 `reward_shaping_weight` 参数，从 1.0 线性衰减到 0.0（如训练的前 50% 步）。后期只保留 outcome reward（submit_answer correct=+1.0）。

→ 已读（A126），与待跟进 A42+A44 吻合。Phase 92 已修复 Edit shaped reward 验证 new_val。衰减机制由训练者实现。

#### F8 — GRPO 在记忆任务上次优，EMPO2 hybrid 方案（审计线程前沿搜索 A101）

**发现**：EMPO2（arXiv 2602.23008，Microsoft Research + KAIST，Feb 2026）表明 **GRPO 在记忆任务上收敛次优**。Hybrid on-policy + off-policy 优化在 ScienceWorld 上比纯 GRPO 提升 128.6%，WebShop 提升 11.3%。核心思路：用 memory 指导 exploration，对 with/without memory 的 action 对做对比优化。

**影响**：如果 MemoryGym RL 训练直接用 GRPO，可能遇到收敛瓶颈。应考虑混合策略。

**建议**：基线仍用 GRPO（实现简单），但遇到收敛瓶颈时参考 EMPO2 的 hybrid 方案。低优先级——先跑通基线。

→ 已读（A126），认同。GRPO 基线优先，收敛瓶颈时再考虑。

#### F9 — Memory-R1 极小数据泛化 + Mem-alpha 长度泛化（审计线程前沿搜索 A101）

**发现**：
- Memory-R1 v5（arXiv 2508.19828，Jan 2026）：仅 **152 个训练 QA**，ADD/UPDATE/DELETE/NOOP 动作空间，PPO+GRPO，泛化到 LoCoMo/MSC/LongMemEval 三个 benchmark，3B-14B 模型规模。
- Mem-alpha（arXiv 2509.25911，Sep 2025）：在 30k token 上训练，**泛化到 400k+ token**（13x 训练长度）。

**影响**：MemoryGym 的训练可能不需要大量数据。少量高质量 SFT 轨迹 + RL 即可泛化。长度泛化意味着可以在 lite tier 训练、standard tier 评测。

**建议**：首轮训练目标应是"跑通 + 泛化验证"而非数据积累。用 10-20 个高质量 seed 的 SFT 轨迹做冷启动，验证是否泛化到未见模板/seed。

→ 已读（A126），与 F3 一致。480 trajectories 足够，lite 训练 → standard 评测验证泛化。

#### F10 — Memex(RL)：Budget 约束下 Write/Read 策略 RL 训练（审计线程前沿搜索 A143）

**发现**：Memex(RL)（arXiv 2603.04257，Mar 2026）显式训练 agent 在 context budget 约束下优化 write 和 read 行为。Agent 学习什么该 summarize、archive、index，以及何时 retrieve。用 reward shaping 针对 indexed memory usage。

**影响**：这是 MemoryGym MemoryEnv 最直接的参考。Memex(RL) 同样面对 budget 约束 + write/read 策略优化，与我们的 Write/Edit/Read/memory_search 完全对齐。

**建议**：GRPO v3 的 reward 设计参考 Memex(RL) 的 indexed memory reward shaping。

#### F11 — LongRLVR：Dense Verifiable Context Rewards（审计线程前沿搜索 A143）

**发现**：LongRLVR（arXiv 2603.02146，Mar 2026）为长上下文 RL 添加 dense, verifiable context rewards（奖励正确的信息选择）。14B 模型 RULER-QA 从 73.17 → 88.90。

**影响**：MemoryGym 当前只有稀疏 outcome reward（final answer correct=+1.0）。可以为中间步骤（正确的 memory_search query、正确的 Write decision）添加密集奖励，解决 GRPO policy collapse。

**建议**：在 shaped reward 中加入 retrieval precision reward：当 memory_search 返回结果且后续 answer 正确时，给 search +0.2。

#### F12 — KARL：Stable Off-Policy RL + 多任务训练（审计线程前沿搜索 A143）

**发现**：KARL（arXiv 2603.05218，Databricks，Mar 2026）使用 iterative large-batch off-policy RL，无 clipped importance weighting 也能稳定训练。跨 6 种异构搜索任务多任务训练。

**影响**：直接对应 MemoryGym 的 GRPO 不稳定问题。多任务训练跨 6 种搜索场景 → 映射到我们的 6+ 世界模板。

**建议**：如果 GRPO v3（KL 正则化）仍不稳定，考虑参考 KARL 的 off-policy 方案。

#### F13 — Batch 21 Movie Corrections 1/5：预算分配可学信号

**发现**：Qwen3.5 movie s0 post-Phase99 首次在真实 eval 完成 correction（`Steel Legacy.awards_count: search → edit`）。writes_used=30, stored=36 实体。推算：ingest 用 29 writes，1 write 留给 correction Edit。

**影响**：这证明 corrections 不需要系统变更——模型自然地在 movie 模板上预留了 1 write。其他 7 模板 ingest 用满 30 writes → 0 剩余 → corrections 失败。训练关键：教模型在 ingest 阶段预留 3-5 writes。

**建议**：
1. SFT v4 的 perfect 策略已预留 writes（budget 内 top-k 存储），训练应强化此行为
2. GRPO reward shaping：correction 成功给 +1.0（远高于 Write +0.3），incentivize 预算预留
3. Curriculum：先在 movie（自然预留空间）验证，再推广到其他模板

#### F14 — IPS-GRPO：单行修复 GRPO Policy Collapse（审计线程前沿搜索 A152）

**发现**：IPS-GRPO（arXiv 2601.21669，Jan 2026）数学证明 outcome-level mode collapse 是 expected-return 目标的结构性后果（log-probability ratios 指数发散）。修复：按逆经验 outcome 频率缩放 reward。Drop-in 替换 GRPO，无需辅助模型。

**影响**：我们的 GRPO v2 policy collapse（loss→负值）可能由此根因导致。IPS-GRPO 是比 KL 正则化（`--kl-coeff 0.05`）更根本的修复——KL 是 symptom treatment，IPS 是 root cause fix。

**建议**：GRPO v3 优先尝试 IPS reward scaling（单行修改），而非 KL 正则化。如果 IPS 不足，再叠加 KL。

#### F15 — NGRPO：全错 Group 学习（审计线程前沿搜索 A152）

**发现**：NGRPO（arXiv 2509.18851）解决 GRPO 在全错 group 时产生零梯度的问题——引入虚拟最高 reward 样本生成非零 advantage + 不对称裁剪稳定 exploration。

**影响**：记忆任务在 budget 约束下经常出现 group 内全错（所有采样都用完 budget，correction 全失败）。标准 GRPO 忽略这些 group = 浪费训练信号。

**建议**：与 IPS-GRPO 互补使用。实现优先级低于 F14。

#### F16 — OTC：Tool Productivity Reward（审计线程前沿搜索 A152）

**发现**：OTC（arXiv 2504.14870）定义 tool productivity = correct_answers / total_tool_calls，联合惩罚过度工具使用。减少 68% tool calls 不降精度。

**影响**：我们的 entities_per_write=1.0（所有模型不做多实体打包）是 tool 低效的信号。OTC-style reward 可训练模型在 Write 中打包多实体 → 用更少 writes 存更多信息 → 预留 budget 给 corrections。

**建议**：GRPO reward 中加入 tool productivity 信号：`efficiency_bonus = correct_count / writes_used`，与 evaluation 的 efficiency 轴对齐。

#### F17 — DAPO Clip-Higher：防 Entropy Collapse（审计线程前沿搜索 A165）

**发现**：DAPO（arXiv 2503.14476，ByteDance Seed + Tsinghua AIR，Mar 2025）提出 Clip-Higher 技术——将 PPO/GRPO 的 clip ratio 上界从 1+ε 提升到 1+ε_high（如 1+0.28），保留下界 1-ε（如 1-0.22）。这种不对称裁剪促进 exploration，防止 entropy collapse。

**与 IPS-GRPO（F14）互补**：
- IPS-GRPO 解决 **outcome-level mode collapse**（reward 分布偏斜）
- Clip-Higher 解决 **token-level entropy collapse**（策略过早收窄）
- 两者正交，可同时使用

**额外 DAPO 技巧**：
- Dynamic Sampling：过滤全对/全错 group（与 NGRPO F15 类似但更简单）
- Overlong Reward Shaping：惩罚被截断的过长响应（agent 产生冗余 tool calls 时适用）

**建议**：GRPO v3 中在 `--ips` 基础上叠加 Clip-Higher（单参数 `--clip-higher 0.28`）。实现量约 5 行代码。优先级低于 IPS 但高于 F15-F16。

#### F18 — RC-GRPO：Reward-Conditioned Exploration 解决 SFT→GRPO Stall（审计线程前沿搜索 A172）

**发现**：RC-GRPO（arXiv 2602.03025，Feb 2026）揭示 SFT→GRPO 管线的"perfection paradox"——SFT 产生 strong prior 后，GRPO 组内 rollout 方差太低 → advantage 退化 → 梯度消失。解决方案：2 阶段 pipeline：
1. RCTP（Reward-Conditioned Trajectory Policy）：在 mixed-quality 轨迹上用 reward token 条件化训练
2. RC-GRPO：每组采样不同 reward token，确保组内有好/坏 trajectory 的方差

Qwen2.5-7B 在 BFCLv4 multi-turn tool calling 达 85%，超越所有闭源 API 模型。

**影响**：我们的 GRPO v2 policy collapse 可能部分来自此根因——SFT v3 loss 降到 0.076（very strong prior），后续 GRPO rollout 方差极低。RC-GRPO 从根本上保证组内方差。

**与已有方法的关系**：
- IPS-GRPO（F14）：解决 outcome-level mode collapse — 正交
- DAPO Clip-Higher（F17）：解决 token-level entropy collapse — 正交
- RC-GRPO（F18）：解决 within-group variance collapse — **新维度**
- 三者可叠加使用

**建议**：GRPO v3 优先尝试 IPS（F14，已实现），如果仍有 stall，叠加 RC-GRPO 的 reward token 条件化。实现量中等（需修改 rollout sampling）。优先级：F14 > F18 > F17。

#### F19 — AceGRPO Learnability Potential：自动 Curriculum（审计线程前沿搜索 A172）

**发现**：AceGRPO（arXiv 2602.07906，Feb 2026）提出自动化 curriculum 策略：
- Evolving Data Buffer：持续将执行轨迹转为可复用训练任务
- Learnability Potential：f(task difficulty, model capability)，动态选择模型"学得动"的任务
- Ace-30B 在 MLE-Bench-Lite 达 100% valid submission rate

**影响**：我们计划 lite→standard→multi 手动三阶段 curriculum。AceGRPO 的 Learnability Potential 可自动化这一过程——按当前模型能力动态选择 template/seed/tier 组合，而非固定阶段切换。

**建议**：GRPO v3 基线跑通后评估。低优先级——先验证手动 curriculum 有效性。

#### F20 — MemAgent Multi-Conv RL：端到端记忆能力训练（审计线程前沿搜索 A176）

**发现**：MemAgent（ICLR 2026 Oral，Microsoft）提出 Multi-Conv RL——在多轮对话中端到端训练记忆读写能力。用 DAPO 替代 GRPO，结合 conversation-level reward（QA 正确率）。Qwen2.5-7B 在 LoCoMo 提升 11-15%。

**影响**：直接对标 MemoryGym 的训练目标。DAPO 在记忆任务上优于 GRPO 的实证来自此论文。我们已实现 DAPO Clip-Higher（F17），但 MemAgent 的完整 DAPO pipeline 包含更多技巧（Dynamic Sampling 过滤全对/全错 group）。

**建议**：GRPO v3 如果加了 IPS+DAPO 仍不稳定，参考 MemAgent 的完整 DAPO 配置。优先级中等。

→ 已读（A177），高价值。MemAgent 的 DAPO 实证支持我们的 F17 实现方向。等 GRPO v3 结果再决定是否采用完整 DAPO。

#### F21 — ScalingInter-RL 课程学习：先短后长（审计线程前沿搜索 A176）

**发现**：AgentGym-RL（ICLR 2026 Oral）提出 ScalingInter-RL——先在短 horizon（少轮交互）训练，逐步扩展到长 horizon。训练效率 2-5x 提升。

**影响**：直接映射到 MemoryGym 的 curriculum 设计：lite tier（少实体、少问题） → standard（多实体） → multi（多 session）。但 AgentGym-RL 的关键是 **交互轮数** 而非任务复杂度——先训练 3 轮交互的任务，再训 20 轮。

**建议**：GRPO v3 的 curriculum 优先按 tier 分级（已计划），同时考虑按 stream 长度（events 数量）分级。实现简单——MemoryEnv 已支持自定义 n_entities/n_questions。

→ 已读（A177），认同。与 F19（AceGRPO）互补——F21 提供课程方向（短→长），F19 提供自动化选题。先手动 tier 分级，再评估自动化。

#### F22 — Cross-Policy Sampling 防策略崩塌（审计线程前沿搜索 A176）

**发现**：AgentRL（清华 THUDM）提出 Cross-Policy Sampling——在 GRPO group 内混入来自不同 policy checkpoint 的 rollout，防止组内方差退化。全异步 pipeline 支持大规模训练。

**影响**：与 RC-GRPO（F18）解决同一问题（within-group variance collapse），但实现方式不同：
- RC-GRPO：用 reward token 条件化采样
- Cross-Policy：混入历史 checkpoint 的 rollout

**建议**：如果 IPS（F14）不足以解决崩塌，Cross-Policy Sampling 比 RC-GRPO 实现更简单——只需保存 N 个历史 checkpoint 并交替使用。优先级：F14 > F22 > F18。

→ 已读（A177），认同优先级排序。F14（IPS）已实现，是首选方案。F22 作为 backup 比 F18 更简洁。

#### F23 — ReCall：无 SFT 冷启动的纯 RL 工具学习（审计线程前沿搜索 A176）

**发现**：ReCall 提出无监督 RL 直接学习工具调用，跳过 SFT 冷启动阶段。使用 curriculum 从简单工具（搜索）到复杂组合（多工具编排）。

**影响**：我们当前 pipeline 是 SFT→GRPO。如果 SFT 质量不够好（v3 仅 0/10 correct），可能限制了 GRPO 的起点。ReCall 的方案是完全跳过 SFT，但需要更好的 curriculum 和更长的训练时间。

**建议**：当前保持 SFT→GRPO pipeline。如果 SFT v5 + GRPO v3 仍失败，考虑 ReCall 的纯 RL 方案。低优先级。

→ 已读（A177），认同低优先级。SFT→GRPO pipeline 有更多前人验证。ReCall 仅作为 pipeline 完全失败时的 Plan B。

#### F24 — CPPO：GRPO 训练加速 3-8x（审计线程前沿搜索 A180）

**发现**：CPPO（arXiv 2503.22342，NeurIPS 2025）通过按 advantage 绝对值剪枝低贡献 completions，只保留高 advantage 样本计算 loss。动态将剪枝释放的 GPU 资源分配给更多 question。GSM8K 加速 8.32x，Math 加速 3.51x，无精度损失。兼容 DAPO/Dr.GRPO。

**影响**：我们的 GRPO v3 在单 GPU 上训练，completion 采样（group_size=4）是主要时间瓶颈。CPPO 可直接叠加到 IPS-GRPO + DAPO Clip-Higher 上——剪枝 advantage ≈ 0 的 completions，将 GPU 资源重新分配给更多 question，等效于增大 batch 而不增加内存。

**建议**：GRPO v3 基线跑通后优化训练速度时引入。实现量中等（需在 loss 计算前过滤 completions + 动态 batch 填充）。优先级中等。

#### F25 — TIC-GRPO：首个 GRPO 收敛性证明（审计线程前沿搜索 A180）

**发现**：TIC-GRPO（arXiv 2508.02833）用 trajectory-level probability ratio 替代 token-level importance ratios，得到无偏策略梯度估计。首次给出 GRPO 类方法的理论收敛保证。关键消融：去掉 importance sampling 后性能几乎不变（old policy 每几步刷新一次，偏差可忽略）。

**影响**：理论验证了我们当前 GRPO 实现的合理性。同时提示 IPS-GRPO（F14）的 importance sampling 可能不是必需——如果实验中 IPS 没有显著改善，可以简化回标准 GRPO + DAPO。

**建议**：低优先级，理论参考。如果 GRPO v3 实验中 IPS 开/关差异不大，可参考此论文简化实现。

#### F26 — GTPO：Entropy-Weighted Reward 防 Policy Collapse（审计线程前沿搜索 A184）

**发现**：GTPO（arXiv 2508.04349）对每个 token 分配 entropy-weighted reward，GRPO-S 在 sequence 级做同样操作。关键实验：初始 entropy 下降后出现 **entropy rebound**，成功对抗 DAPO 基线的 policy collapse。

**影响**：与 DAPO Clip-Higher（F17）解决同一问题（entropy collapse），但机制不同：DAPO 靠不对称 clip ratio，GTPO 靠 entropy weighting。两者可视为替代方案。

**建议**：如果 IPS+DAPO（GRPO v3）仍有 collapse，GTPO 是 backup 方案。优先级低于 F14/F17。

#### F27 — GDPO：Multi-Reward 解耦归一化（审计线程前沿搜索 A184）

**发现**：GDPO（arXiv 2601.05242）发现多个 reward 联合归一化时 advantage 退化为相同值（reward collapse）。解决方案：每个 reward 独立归一化，保留相对差异。

**影响**：当前用单一 composite reward，不受影响。但如果未来做多目标训练（分别优化 breadth/maintenance/reasoning/efficiency），GDPO 的解耦归一化是必要技术。

**建议**：低优先级。等多目标训练需求出现时参考。

#### F28 — Training-Free GRPO：无 GPU 上下文空间优化（审计线程前沿搜索 A188）⭐

**发现**：Training-Free GRPO（arXiv 2510.08191）将 policy 实例化为**冻结 LLM + 可变经验上下文**，将优化从参数空间转移到上下文空间。性能超越 32B 全微调 LLM，学习成本从 $800 降到 $8。核心思想：不修改模型权重，而是优化提供给模型的 few-shot 示例（经验记忆）。

**影响极高**：GRPO v3 被 GPU SSH 阻塞已数天，所有参数优化训练无法执行。Training-Free GRPO 完全绕过 GPU 需求——只需 API 推理（我们已有 Chutes API + 多个可用模型）。

**实施思路**：
1. 从 SFT 轨迹中选取 K 个 episode 作为初始经验上下文
2. 通过 API 跑 MemoryGym eval，收集成功/失败轨迹
3. 用 GRPO-style advantage 评估每个经验 episode 的价值
4. 迭代替换低价值 episode，保留高价值 episode
5. 最终上下文 = 最优 few-shot 示例集

**与 GPU 训练的关系**：互补而非替代。Training-Free 优化 prompt，GPU 训练优化 weights。可先用 Training-Free 找到最优 prompt 策略，再用 GPU 训练将策略固化到权重中。

**建议**：**高优先级**——GPU 阻塞期间唯一可执行的训练替代方案。建议训练线程评估可行性。

#### F29 — Scaf-GRPO：渐进式脚手架防学习停滞（审计线程前沿搜索 A188）

**发现**：Scaf-GRPO（arXiv 2510.19807）在模型自主学习停滞时才提供最小引导（scaffolding）。Qwen2.5-Math-7B 在 AIME24 上比 vanilla GRPO 提升 44.3%。

**影响**：与 RC-GRPO（F18）解决类似问题（学习停滞），但更简单——不需要修改 rollout sampling，只需检测停滞并注入 hints。

**建议**：低优先级。等 GRPO v3 基线跑通后再评估。

#### F30 — MemSearcher：Multi-Context GRPO 联合优化记忆+推理（审计线程前沿搜索 A193）⭐

**发现**：MemSearcher（arXiv 2511.02805）引入 **multi-context GRPO**，联合优化推理、搜索策略和记忆管理。MemSearcher-3B 超越 7B 基线。核心创新：per-turn context budget 约束下的端到端 RL。

**影响极高**：直接对标 MemoryGym 的训练目标——在预算约束下联合优化存储决策和检索策略。"per-turn context budget" 概念映射到我们的 write budget。

**建议**：**高优先级**。GPU 恢复后 GRPO v3 应参考 MemSearcher 的 multi-context 设计。

#### F31 — ATLAS：Rubric-Based RL for Tool-Use + Budget Constraints（审计线程前沿搜索 A193）

**发现**：ATLAS（arXiv 2603.06713，Microsoft Research，Mar 2026）为大工具空间环境下的 SLM 提供 rubric-based reinforcement finetuning。将任务成功分解为结构化评分标准，context-bounding 策略作为可学习决策。

**影响**：直接对标 MemoryGym 的 4 轴评分——rubric-based reward decomposition 可映射到 breadth/maintenance/reasoning/efficiency 四个独立 reward 信号，比当前单一 composite reward 更精细。

**建议**：中优先级。GRPO v3 基线跑通后，将 4 轴分数作为独立 reward 信号（参考 GDPO F27 解耦归一化）。

#### F32 — EBPO：Empirical Bayes 修复 GRPO 不稳定（审计线程前沿搜索 A193）

**发现**：EBPO（arXiv 2602.05165，Feb 2026）用 empirical Bayes shrinkage 正则化 GRPO 的局部 group baselines，借用全局统计信息。理论保证更低 MSE 和有界 entropy 衰减。

**影响**：直接解决我们的 GRPO v2 policy collapse（loss→负值）。与 IPS-GRPO（F14）正交——IPS 修复 outcome-level mode collapse，EBPO 修复 group baseline 不稳定。

**建议**：中优先级。如果 IPS-GRPO 不够，EBPO 是下一个尝试方案。

#### F33 — 竞品分析：AMemGym + MemoryArena（审计线程前沿搜索 A193）

**发现**：
- **AMemGym**（arXiv 2603.01966，ICLR 2026 Poster）：交互式 on-policy 记忆评测环境，结构化数据采样+状态演化。聚焦对话个性化。
- **MemoryArena**（arXiv 2602.16313）：多 session 跨任务记忆评测（web 导航+规划+搜索）。发现 LoCoMo 饱和的模型在 agentic 场景下失败。

**影响**：两个直接竞品验证了 MemoryGym 的设计方向——静态召回测试不足以评估真实记忆管理能力。MemoryGym 的差异化优势：信息过载+预算约束+更新追踪+RL 训练环境（四合一）。

**建议**：记录，作为论文定位参考。无需改代码。

#### F34 — HCAPO：Hindsight Credit Assignment 修复 GRPO 稀疏 Reward（审计线程前沿搜索 A199）⭐

**发现**：HCAPO（arXiv 2603.08754，Mar 2026）首个将 hindsight credit assignment 引入 LLM agent 的框架。用 LLM 自身作为事后 critic 细化 step-level Q 值。多尺度 advantage 机制修复 GRPO 在关键决策点的不准确 value baseline。ALFWorld +13.8%，WebShop +7.7%。

**影响**：直接对标我们的 GRPO sparse reward 问题。MemoryGym 的多轮记忆操作（Write/Edit/search）reward 极其稀疏（只在最终 submit_answer 时有信号）。HCAPO 的 hindsight reasoning 可为每步 write/edit/search 决策提供密集的 per-step credit。

**建议**：**高优先级**。与 F14（IPS-GRPO）互补——IPS 修复 mode collapse，HCAPO 修复 credit assignment。GPU 恢复后评估。

#### F35 — ACT：Agentic Critical Training（审计线程前沿搜索 A199）⭐

**发现**：ACT（arXiv 2603.08706，Mar 2026）RL 范式——每步配对 expert action 和 model-generated alternatives，奖励正确的 action quality 判断。产生真正的 self-reflection 而非模仿。+5.07 over imitation learning，+4.62 over standard RL。

**影响**：我们的 SFT 轨迹可作为 expert demonstrations。ACT 的对比方法可教 agent *为什么*某些存储决策更好，而非仅仅*存什么*。

**建议**：高优先级。需要 SFT 轨迹作为 expert baseline + RL 生成对比样本。实现量中等。

#### F36 — RAPO：Retrieval-Augmented Policy Optimization（审计线程前沿搜索 A199）

**发现**：RAPO（arXiv 2603.03078，KDD'26）通过检索 off-policy step-level traces 扩展 on-policy rollout 的探索空间。14 个数据集平均 +5.0%，训练速度 1.2x。

**影响**：我们的 GRPO 训练存在 exploration collapse。RAPO 的 step-level off-policy trace retrieval 可从成功 SFT 轨迹注入多样性。

**建议**：中高优先级。GPU 恢复后，如果 IPS-GRPO 仍有 exploration 问题，RAPO 是下一方案。

#### F37 — NAT：Token-Efficient GRPO（审计线程前沿搜索 A199）

**发现**：NAT（arXiv 2603.06619，Mar 2026）无偏 partial-token policy gradient estimator（Horvitz-Thompson reweighting）。只需 50% tokens 参与 backward pass 即匹配 full-token GRPO。Plug-and-play。

**影响**：MemoryGym 轨迹很长（多轮工具调用）。NAT 可将 RL 训练内存/计算成本减半，无精度损失。与所有其他 GRPO 改进正交。

**建议**：中优先级。纯工程优化，GPU 恢复后集成。实现简单。

#### F38 — MicroCoder-GRPO：长输出 GRPO 修复（审计线程前沿搜索 A199）

**发现**：MicroCoder-GRPO（arXiv 2603.07777，Mar 2026）三项长输出 GRPO 修复：conditional truncation masking（保留长输出潜力）、diversity-determined temperature、移除 KL loss + 高 clip ratio。LiveCodeBench v6 +17.6%。

**影响**：记忆 agent 输出是长的多工具调用序列。Conditional truncation masking 直接解决我们长轨迹截断问题。

**建议**：中优先级。GPU 恢复后评估 truncation masking 技术。

#### F39 — KLong：极长 Horizon 任务训练（审计线程前沿搜索 A199）

**发现**：KLong（arXiv 2602.17547，Feb 2026）Trajectory-splitting SFT（保留早期上下文，渐进截断后期）+ progressive RL（逐步增加 timeout）。KLong-106B 超越 Kimi K2（1T） 11.28%。

**影响**：MemoryGym 场景是长 horizon（文档流+corrections+QA）。Trajectory-splitting SFT 可直接应用于我们的 SFT 数据生成。Progressive RL 映射到 multi-tier。

**建议**：中优先级。SFT 数据生成可参考 trajectory-splitting 技术。

#### F40 — UMA：Unified Memory Agent（竞品）（审计线程前沿搜索 A199）

**发现**：UMA（arXiv 2602.18493，Feb 2026）端到端 RL 框架：双记忆（compact core summary + structured Memory Bank，CRUD 操作）。引入 Ledger-QA 基准（latent values from accumulated updates）。

**影响**：与 MemoryGym 设计哲学最接近——CRUD 操作 + 预算压力 + update tracking。Ledger-QA 的 "latent value" 概念类似我们的 correction tracking。**直接竞品**。

**建议**：监控。无需改代码，作为论文定位参考。

#### F41 — ToolRLA：Multiplicative Reward Decomposition（审计线程前沿搜索 A204）⭐

**发现**：ToolRLA（arXiv 2603.01620，Mar 2026）提出 **乘法 reward 分解**——将工具调用 reward 拆为 format validity × tool selection × parameter accuracy × regulatory compliance 四个维度的乘积。比加法 reward +7pp。三阶段管线 SFT→GRPO→DPO。金融场景部署：task completion 62%→91%，tool error 38%→14%。

**影响**：我们当前 reward 是单一 composite（Write +0.3, Edit +0.5, correct answer +1.0）。ToolRLA 的乘法分解可映射到 MemoryGym：format correctness × entity coverage × attribute completeness × update tracking。乘法确保**一个维度为零则总 reward 为零**——避免模型靠某一维度"刷分"。

**建议**：**高优先级**。GRPO v3 的 shaped reward 从 additive 改为 multiplicative。与 F6（attributed reward）+ F16（OTC tool productivity）互补。实现量低——修改 reward 计算公式即可。

#### F42 — MAPO：Turn-Level Monte Carlo Advantage（审计线程前沿搜索 A204）⭐

**发现**：MAPO（arXiv 2603.06194，Mar 2026）将对话 turns 视为 temporally extended actions，用 Monte Carlo return estimation 在 turn-level 计算 advantage，无需 tree expansion 或 learned critic。7B-32B 模型上一致超越 GRPO。适用于 agentic RL + tool-use 场景。

**影响**：MemoryGym 的每个"turn"是一次工具调用（Write/Edit/Read/memory_search/submit_answer）。Token-level GRPO 把一次 Write 调用拆成数百个 token，gradient 信号被稀释。Turn-level advantage 直接在决策粒度评估"这次 Write 是否有价值"。

**建议**：**高优先级**。与 F34（HCAPO hindsight credit）解决同一问题（multi-turn credit assignment），但 MAPO 更简单（无需额外 critic）。GRPO v3 可先用 turn-level grouping 替代 token-level。

#### F43 — ReMemR1/RLMLR：Multi-Level Memory Rewards（审计线程前沿搜索 A204）⭐

**发现**：ReMemR1（arXiv 2509.23040）提出 RLMLR（RL with Multi-Level Rewards）——结合 trajectory-level outcome reward（最终答案正确性）和 step-level state reward（每步 memory update 的 information gain）。20%+ error rate reduction，在 out-of-distribution benchmark 上同样有效。

**影响**：我们当前只有 trajectory-level reward（submit_answer correct=+1.0）和粗粒度 shaped reward（Write +0.3）。RLMLR 的 step-level information gain 可自动评估"这次 Write 增加了多少新信息"——比固定 +0.3 更精准。与 F11（LongRLVR dense context rewards）互补。

**建议**：**高优先级**。information gain reward 可利用 MemoryGym 的 `required_entities` 字段——Write 存储了被问到的实体 → information gain 高。GRPO v3 shaped reward 设计参考。

#### F44 — InfoPO：Information-Gain Turn Reward（审计线程前沿搜索 A204）

**发现**：InfoPO（arXiv 2603.00656，Feb 2026）将多轮交互建模为"主动不确定性消减"过程。每 turn 计算 information-gain reward（与 masked-feedback counterfactual 对比），用 adaptive variance-gated fusion 融合 task outcome 和 information gain。超 GRPO 14-16%。

**影响**：与 ReMemR1（F43）方向一致但机制不同——InfoPO 用 counterfactual 对比，ReMemR1 用 state reward。InfoPO 的 variance-gating 可防止 information gain 与 task outcome 冲突。

**建议**：中优先级。如果 F43 的 step-level reward 引入后 shaped reward 与 outcome reward 冲突，InfoPO 的 variance-gating 是解决方案。

#### F45 — Turn-PPO：Turn-Level Critic 替代 GRPO（审计线程前沿搜索 A204）

**发现**：Turn-PPO（arXiv 2512.17008，Dec 2025，Amazon）发现 GRPO 在 multi-turn 任务上不稳定，PPO 的 learned critic 提供更准确的 advantage estimation。Turn-PPO 在 turn-level MDP 上运行（而非 token-level），WebShop 和 Sokoban 上超越 GRPO。

**影响**：如果 GRPO v3（IPS + DAPO + KL）仍不稳定，Turn-PPO 是根本不同的替代路径——从 critic-free（GRPO）切换到 learned critic（PPO）。但实现复杂度更高（需要训练 value head）。

**建议**：中优先级。GRPO v3 完全失败时的 Plan B。与 F8（EMPO2 hybrid）类似定位。

#### F46 — AriadneMem：Conflict-Aware Memory Coarsening（审计线程前沿搜索 A204）

**发现**：AriadneMem（arXiv 2603.03290，Mar 2026）解决长对话记忆的两个核心问题：(1) 分散证据需要多跳链接，(2) 状态更新导致新旧信息冲突。entropy-aware gating 过滤噪音 + conflict-aware coarsening 合并静态重复但保留时序边。Multi-hop F1 +15.2%，仅 497 context tokens。

**影响**：MemoryGym 的 correction tracking 正是"状态更新冲突"问题。AriadneMem 的 conflict-aware coarsening 可启发 SFT 轨迹的 Edit 策略——在存储中保留"旧值→新值"的时序关系，而非简单覆盖。

**建议**：中优先级。SFT 数据质量改进方向——Edit 后的 memory 应保留变更历史（如 "revenue: 35.88 → 42.87"）。

#### F47 — AMA-Bench：Agentic 轨迹记忆基准（竞品）（审计线程前沿搜索 A204）

**发现**：AMA-Bench（arXiv 2602.22769，Feb 2026）评测 agentic 场景（非对话）的长 horizon 记忆。真实轨迹 + 合成轨迹，rule-based QA。发现现有记忆系统缺乏因果推理和客观信息，similarity retrieval lossy。提出 AMA-Agent：causality graph + tool-augmented retrieval，57.22% avg accuracy（+11.16% over baselines）。

**影响**：与 AMemGym(F33)/MemoryArena(F33)/UMA(F40) 构成 4 个直接竞品。AMA-Bench 的 causality graph 验证了 MemoryGym 的 correction tracking 方向。差异化：我们有 budget 约束 + RL 训练环境，AMA-Bench 没有。

**建议**：监控。无需改代码，论文定位参考。

#### F48 — MT-GRPO：Turn-Level GRPO 正式实现（审计线程前沿搜索 A209）⭐

**发现**：MT-GRPO（arXiv 2505.11821，May 2025，更新至 2026）将 multi-turn agent 任务重构为 multi-step MDP，在 turn-level 计算 advantage（而非 token-level 或 trajectory-level）。关键实验发现：**GRPO-OR（标准 outcome reward GRPO）逐渐停止调用 search tools**——即 tool collapse。MT-GRPO 保持 100% tool execution，训练方差更低。

**影响**：直接解释了我们 GRPO v2 的 policy collapse（loss→负值）——标准 GRPO 在 multi-turn tool-use 场景下导致模型放弃工具调用。MT-GRPO 是 F42(MAPO) 的前驱工作，两者方向一致但 MT-GRPO 有更系统的 MDP 重构和实验验证。

**与已有方法关系**：
- F42 (MAPO)：同样做 turn-level advantage，但 MAPO 用 Monte Carlo return，MT-GRPO 用显式 turn-level reward 设计
- F4 (AgeMem step-wise GRPO)：AgeMem 的 step-wise 就是 turn-level 的变体
- 三者收敛到同一结论：**multi-turn agent RL 必须用 turn-level（而非 token-level）advantage**

**建议**：**高优先级**。GRPO v3 应实现 turn-level advantage（已在待办 #4 "F42 MAPO turn-level advantage"）。MT-GRPO 的实验佐证加强了这一方向的信心。

#### F49 — LOOP：无 Value Network 的高效 PPO（审计线程前沿搜索 A209）⭐

**发现**：LOOP（arXiv 2502.01600，Apple Research）是 PPO 的数据/内存高效变体——**无 value network，仅维护单个 LLM 副本**。使用 leave-one-out baseline 估计（从同组其他 rollout 计算 baseline，无需额外网络）+ per-token clipping。32B agent 在 AppWorld 上超越 OpenAI o1 达 9pp（15% 相对提升）。首个在 stateful multi-domain 环境中成功应用 RL 训练 LLM agent 的报告。

**影响**：如果 GRPO v3（IPS+DAPO+KL）仍不稳定，LOOP 是比 Turn-PPO(F45) 更好的 PPO 替代方案——不需要训练 value head，内存占用与单模型微调相同。leave-one-out baseline 在长 horizon 任务上比 GRPO 的 group mean 更稳定（避免全组 reward 相近时 advantage 退化）。

**建议**：**中高优先级**。GRPO v3 完全失败时的 Plan B。实现比 Turn-PPO 简单——本质是 GRPO 的 baseline 计算方式从 group mean 改为 leave-one-out mean。优先级：IPS-GRPO(F14) > LOOP(F49) > Turn-PPO(F45)。

#### F50 — SkillRL：经验→技能库→递归进化（审计线程前沿搜索 A209）

**发现**：SkillRL（arXiv 2602.08234，Feb 2026）将 agent 的原始轨迹自动抽象为层级技能库（general skills + task-specific skills），技能库在 RL 训练过程中与策略共同进化。ALFWorld/WebShop 上 +15.3%，token 压缩 10-20%。

**影响**：对 SFT 数据生成的启发——将 perfect 策略的成功模式（如 "multi-entity packing"、"search→edit correction"、"budget-aware selective storage"）抽象为可复用的技能描述。这些技能描述可以作为系统提示词的一部分，但需注意 CLAUDE.md 的提示词中立性约束。

**建议**：低优先级。当前阶段先跑通 GRPO 基线。如果训练后模型仍缺少特定技能（如 correction），SkillRL 的技能库方法是后续优化方向。

#### F51 — MemoryRewardBench：Reward Model 记忆管理评测（审计线程前沿搜索 A209）

**发现**：MemoryRewardBench（arXiv 2601.11969，Jan 2026）首个系统评估 reward model 在长期记忆管理上能力的基准。13 个 RM，10 种记忆管理模式，8K-128K context。两种评估模式：outcome-based（正确 vs 错误轨迹）和 process-based（两个正确轨迹中哪个记忆更新更干净）。发现所有 RM 在 process-based 评估和超长上下文时性能下降。

**影响**：如果未来 MemoryGym 引入 RM-based reward（而非 rule-based），MemoryRewardBench 的发现提示 process-based 评估更难——RM 不擅长判断"哪种记忆更新策略更好"。当前 rule-based reward（F41/F43）更可靠。

**建议**：低优先级。记录，作为未来 RM 替代 rule-based reward 时的参考。

#### F52 — SELAUR：Uncertainty-Aware Shaped Rewards（审计线程前沿搜索 A214）

**发现**：SELAUR（arXiv 2602.21158，Feb 2026）将 token-level uncertainty（entropy + least-confidence + margin 三指标融合）注入 step-level 和 trajectory-level rewards。Failure-aware reward reshaping 在 agent 不确定时降低 reward 权重，确定时放大。

**影响**：可叠加到现有 F43 information gain reward 上——对 Write 决策的 uncertainty 加权。高 uncertainty Write（模型不确定是否该存这个实体）→ 降低 shaped reward → 避免"盲存"。比 F7（MIRA 线性衰减）更精细，比 F26（GTPO 纯 entropy）更鲁棒（三指标融合）。实现需要 logits 访问（GRPO v3 已有）。

**建议**：中优先级。GRPO v3 基线跑通后评估。

#### F53 — BudgetMem：Budget-Tier Memory Routing via RL（审计线程前沿搜索 A214）

**发现**：BudgetMem（arXiv 2602.06025，Feb 2026）将 agent memory 处理分为多模块 × 3 budget tiers（Low/Mid/High），用 RL-trained 轻量 router 按 query 动态选择 tier。在 LoCoMo/LongMemEval/HotpotQA 上超越 baselines。

**影响**：MemoryGym 的 tier 系统（lite/standard/multi）与 BudgetMem 的 budget-tier 直接对齐。BudgetMem 的核心启发：用小模型训练 memory controller 来决定 write 优先级。Curriculum 训练时可参考其 per-query budget allocation 思路。

**建议**：中优先级。论文参考 + router 设计启发。不直接改代码。

#### F54 — StructMemEval：Memory Structure Benchmark（审计线程前沿搜索 A214）— 竞品

**发现**：StructMemEval（arXiv 2602.11243，Feb 2026，Yandex Research）评测 agent 记忆的**组织结构**能力（transaction ledgers, to-do lists, trees）。关键发现：LLM 不主动组织记忆结构，但 structure hint 后显著改善。

**影响**：验证 MemoryGym 的设计方向——存储组织是核心能力。with/without hint 对比可验证提示词中立性约束。

**建议**：监控。论文定位参考。

#### F55 — LoCoMo-Plus：Cognitive Memory Evaluation（审计线程前沿搜索 A214）— 竞品

**发现**：LoCoMo-Plus（arXiv 2602.10715，Feb 2026）将记忆评测从 factual recall 扩展到 cognitive memory（causal/state/goal/value 四种 latent constraints）。发现现有 memory agent 在 cue-trigger 语义断连场景下失败。

**影响**：MemoryGym 的 20 种推理题型已覆盖部分 cognitive 维度，但 causal/goal/value 是新维度。差异化定位：MemoryGym=预算约束+RL训练，LoCoMo-Plus=认知深度。

**建议**：记录。论文定位参考。

#### F56 — Evo-Memory：Self-Evolving Memory Benchmark（审计线程前沿搜索 A214）— 竞品

**发现**：Evo-Memory（arXiv 2511.20857，Nov 2025，DeepMind）评测 agent 在连续任务流中的 test-time memory 演化。提出 ReMem pipeline。10 个数据集。

**影响**：Evo-Memory 聚焦"跨任务知识积累"，MemoryGym 聚焦"单 session 信息过载管理"——互补定位。

**建议**：监控。竞品定位参考。

#### F57 — WebAgent-R1：Binary Reward Multi-Turn RL（审计线程前沿搜索 A214）

**发现**：WebAgent-R1（arXiv 2505.16421）用简洁的 SFT warm-up + binary outcome reward 实现 5-6x 提升（Qwen-2.5-3B 6.1%→33.9%）。不需要 shaped reward。

**影响**：如果 GRPO v3 的 shaped reward（F41/F43/F16）过于复杂导致 reward hacking，WebAgent-R1 验证了退回 binary reward + 更多 rollout 的可行性。是 shaped reward 失败时的 fallback 方案。

**建议**：低优先级。备选方案。

#### F58 — FluxMem：Adaptive Memory Structure Selection（审计线程前沿搜索 A214）

**发现**：FluxMem（arXiv 2602.14038，Feb 2026）三层记忆架构（STIM/MTEM/LTSM）+ BMM-based gating 动态选择记忆结构。将"选择哪种记忆组织方式"变成可学习决策。

**影响**：MemoryGym 记忆后端固定，不涉及多结构选择。低相关性。

**建议**：记录备查。

#### F59 — Dr.MAS：Per-Agent Advantage Normalization（审计线程前沿搜索 A214）

**发现**：Dr.MAS（arXiv 2602.08847，Feb 2026）发现多 agent GRPO 中全局 advantage normalization 导致梯度不稳定。解决方案：每 agent 独立 normalize。

**影响**：MemoryGym 是单 agent 训练，直接相关性低。但 per-task normalization 思想可借鉴——不同模板的 reward 分布不同，curriculum 训练时按模板独立 normalize 可能有益。

**建议**：低优先级。记录备查。

#### F60 — MemoryAgentBench：增量多轮记忆评测（审计线程前沿搜索 A221）

**发现**：MemoryAgentBench（arXiv 2507.05257，ICLR 2026）评测 4 项记忆能力：精确检索、测试时学习、长程理解、冲突解决。引入 EventQA 和 FactConsolidation 数据集。

**影响**：直接竞品 benchmark。MemoryGym 的差异化在于预算约束 + 信息过载 + 修正追踪 + RL 环境。训练侧无需调整，但评测对比时需了解其维度。

**建议**：低优先级。记录备查，未来论文中需对比。

#### F63 — MEM-alpha：RL 学习记忆构建（审计线程前沿搜索 A221）

**发现**：MEM-alpha（arXiv 2509.25911，ICLR 2026 审稿中）将记忆构建建模为序列决策，agent 处理信息块、决定记忆操作、基于 QA 准确率获奖励。训练于 30k token，泛化到 400k+（13x）。

**影响**：高度相关。验证了 RL 训练记忆管理的可行性。其奖励函数设计（QA 准确率驱动）和记忆操作空间（core/episodic/semantic 三层）可直接参考。13x 泛化结果对 MemoryGym 训练有启发——可在小 seed 训练、大 seed 评测。

**建议**：高优先级。研究其奖励函数设计，对比 MemoryGym 当前 4 轴奖励。

#### F64 — INTENT：预算约束意图感知工具调用规划（审计线程前沿搜索 A221）

**发现**：INTENT（arXiv 2602.11541，Feb 2026）在严格预算下做多步工具调用规划。意图感知分层世界模型预测未来工具使用和风险校准成本。

**影响**：直接相关。MemoryGym 的写入预算是相同问题。INTENT 的"预测未来需求再决定当前操作"思路可启发 agent 存储策略——agent 应预测后续问题类型再决定存储什么。

**建议**：中优先级。budget-aware planning 是 MemoryGym agent 的核心挑战。

#### F66 — Training-Free GRPO：零成本语义优势蒸馏（审计线程前沿搜索 A221）

**发现**：Training-Free GRPO（arXiv 2510.08191）不更新参数，用 LLM 自省生成语义优势作为 token prior。少量样本即超越微调小模型。

**影响**：可作为低成本基线方法——无需 GPU 即可验证 MemoryGym RL 训练效果上界。适合快速原型验证。

**建议**：中优先级。适合在 GPU 资源不足时快速验证想法。
#### F67 — MemoryEnv 缺少 context_limit 参数（训练实验发现）

**发现**：GRPO v3 中模型学会"不存储直接答题"（writes=0, correct=5/10），因为文档内容在 rollout 时始终留在上下文窗口中。根因是 `MemoryEnv` 没有上下文长度约束——上下文管理完全由外部训练脚本（`grpo_train.py` 的 `rollout_max_tokens`）控制。

**数据**：
- v3 lite tier (30 entities, ~3-5K tokens docs): writes=0 episodes 得分高于 writes>0 episodes
- v4a test standard tier + 6144 context: step 1 writes=0 correct=0-1/20, step 2 出现 writes=7

**影响**：这不仅是训练问题，也是评测问题。真实 agent 场景中，上下文一定有限——信息过载 + 预算有限（CLAUDE.md §场景真实）。如果 eval 时模型也能从上下文直接读答案，评分不反映真实记忆管理能力，违反 CLAUDE.md §评分有效性。

**建议**：
1. MemoryEnv 增加 `context_events_limit` 参数（最多保留最近 N 个事件的文本），使旧文档"消失"
2. 或者在评测协议中明确规定：文档事件和问题事件之间必须有足够间隔，使上下文自然溢出
3. Tier 定义中加入 `min_context_pressure` 指标：entities × avg_doc_tokens / context_limit > 2.0

#### F68 — Shaped reward 与 composite score 不对齐（训练实验发现）

**发现**：Shaped reward 中 Write +0.3（每存一个新实体）不区分实体价值。但 composite score 中，efficiency 轴 = `correct / budget`，breadth 轴只计算被问到的实体。存了但从未被问到的实体对 composite 贡献为 0，却消耗了 +0.3 的正向 reward。

**数据**：
- SFT v3: 15 writes, 0/10 correct → shaped reward 有 15×0.3=4.5 的 write reward，但 composite=0
- GRPO v3: writes=0 episodes 的 composite 高于 writes=15 但 correct=1 的 episodes

**影响**：Shaped reward 引导模型"多存"，composite score 奖励"存对"。两个信号冲突。这可能是 GRPO 收敛慢的根因之一——梯度方向不一致。

**建议**：
1. 取消 Write +0.3 的固定 shaped reward，改为 episode 结束后回溯归因（F6 attributed reward）
2. 或将 Write shaped reward 降至 +0.05（仅防止完全不存），把主要梯度来源让给 submit_answer +1.0
3. composite score 的 efficiency 轴已经惩罚"多存少对"，shaped reward 不应再额外奖励存储行为

#### F69 — 训练效率瓶颈：episode 时长 vs GPU 共享约束（训练实验发现）

**发现**：单 episode 耗时 ~7-8 min (standard tier) / ~5 min (lite tier)，Qwen3-4B 单卡。15 steps × 4 episodes/step 的训练需 ~7-8 小时。在共享 GPU 机器上，长时间占用会被 kill。

**数据**：
- v4a test: 2 steps × 2 episodes = 4 episodes, 耗时 ~30 min
- 每 episode 40 turns × 每 turn ~10s generation = ~400s + env overhead

**影响**：训练迭代周期太长，无法快速验证假设。CLAUDE.md §可训练要求系统是 RL 训练环境，但当前 episode 速度使快速迭代不可行。

**建议**：
1. 添加 `--lite-episode` 模式：减少 entities（15）+ questions（5）+ corrections（1），episode ~2 min
2. MemoryEnv 支持 `fast_mode`：跳过 noise 事件和 session_break，只保留 ingest + correction + question
3. 考虑 episode 并行（多进程 rollout）——当前是串行的，但 MemoryEnv 是无状态的，可以并行

---

## 训练 CLI

### 远程训练工具（推荐）

`scripts/train.py` — 统一远程训练入口，自动同步代码 + GPU 检测 + 日志解析。

```bash
# 查看 GPU 状态和运行中的训练任务
python scripts/train.py status --remote $GPU_SSH

# 远程 SFT 训练（自动同步代码 + 选择空闲 GPU）
python scripts/train.py sft --remote $GPU_SSH --model $MODEL_PATH --lora

# 远程 GRPO 训练
python scripts/train.py grpo --remote $GPU_SSH \
    --model $MODEL_PATH --adapter checkpoints/sft \
    --steps 10 --group-size 4

# 监控运行中的训练
python scripts/train.py monitor --remote $GPU_SSH --log /tmp/grpo.log
```

> **规则**：所有远程训练必须通过 `scripts/train.py` 启动，禁止直接 SSH 执行命令。

### 本地工具（无 GPU）

```bash
# 冒烟测试
python -m memorygym.training smoke

# 生成 SFT 数据
python -m memorygym.training data --seeds 20 -o data/sft_train.jsonl
```

### 训练模块结构

```
memorygym/training/
    __init__.py      # 向后兼容 re-exports (MemoryEnv, generate_sft_trajectory)
    env.py           # MemoryEnv RL 环境 + SFT 轨迹生成
    common.py        # 共享工具（模型加载、assistant mask、chat template）
    cli.py           # 统一 CLI 入口（data/sft/grpo/smoke）
    __main__.py      # python -m memorygym.training 入口
```

### 输出结构

每次训练自动创建 `runs/<mode>_<timestamp>/` 目录：
- `config.json` — 完整超参（可复现）
- `training_log.jsonl` — 每步指标（loss、reward、correct）
- `metrics.json` — 最终摘要
- `episodes/` — GRPO episode 采样（调试用）
- `checkpoints/` — 模型检查点

## 待办

1. **GRPO v4a 短实验**（当前优先，🔴 GPU 全部被占用 ~11GB free）
   - ✅ `--rollout-max-tokens` 已实现，context pressure 有效（v4a test: writes=0→writes=7）
   - ✅ `--turn-level` 已实现：shaped reward 参与 advantage 计算（50/50 混合 episode + shaped）
   - ✅ 10 个模板已同步（新增 project/agentteam）
   - ✅ per-turn shaped reward 收集（`turn_rewards` in stats）
   - 实验命令：`--tier standard --rollout-max-tokens 6144 --ips --kl-coeff 0.05 --turn-level --steps 3`
   - 轻量配置：`--group-size 2 --groups-per-step 1`（每 step 仅 2 episodes，~15 min/step）
   - **等 GPU 空闲后执行**

2. 多模板 curriculum 效果验证（lite → standard → multi）

## 训练数据洞察（2026-03-11 分析）

**SFT Perfect vs Real Models 核心差距**：

| 指标 | SFT Perfect | 真实模型（123 evals 均值）|
|------|-------------|------------------------|
| Writes 使用 | ~7/30（23%） | ~30/30（100%） |
| Entities/Write | 4.3（多实体打包） | 1.0（无打包） |
| Attrs/Entity | ~21（全属性） | ~5（丢失 76% 属性） |
| Edits（correction） | ~5/5 | 0-1/5 |
| Budget 剩余 | ~23/30 | 0/30 |

**训练关键目标**（优先级排序）：
1. **Context pressure**：迫使模型使用记忆系统而非上下文（F67，`--rollout-max-tokens`）
2. **属性密度**：教模型在 Write 中包含更多属性（当前丢失 76%）
3. **多实体打包**：教模型在单次 Write 中存多个实体（4.3x vs 1.0x）
4. **Correction 执行**：教模型对 correction 事件执行 search→Edit 流程

## 已完成

- **Phase 113: Shaped Reward + GRPO v3 Clipped Loss**（提交 60502ed，2026-03-12）
  - F41（ToolRLA multiplicative）：Edit reward 细化为 search+correct=0.6, correct-only=0.5, wrong=0.1
  - F43（ReMemR1 info gain）：写被问实体 → 0.5（vs 未被问 0.3）。通过预计算 `_questioned_entities` set 实现
  - F16（OTC packing bonus）：多实体打包每多一个 +0.1，激励 entities_per_write > 1
  - GRPO v3 loss：PPO-style clipped surrogate (-min(r*A, clip(r)*A)) 替代 REINFORCE (-A*log_p)
  - DAPO Clip-Higher：非对称裁剪防 entropy collapse，参数 `--clip-higher 0.28`
  - IPS-GRPO：逆频率缩放防 mode collapse，参数 `--ips`
  - 两个入口均已提交：`scripts/grpo_train.py` + `memorygym/training/cli.py`
  - 本地测试：47 training tests + 48 simulation checks ALL PASS
- **Shaped reward 改进：F41 + F43 + F16**（2026-03-12）
  - F43（ReMemR1 info gain）：Write 存储被问实体 → 0.5（vs 未被问 0.3）。通过预计算 `_questioned_entities` set 实现
  - F41（ToolRLA multiplicative）：Edit reward 细化为 search+correct=0.6, correct-only=0.5, wrong=0.1
  - F16（OTC packing bonus）：多实体打包每多一个 +0.1，激励 entities_per_write > 1
  - 改动文件：`memorygym/training/env.py`（reward logic）, `tests/test_training.py`（assertions updated）
- GRPO loss 升级为 PPO-style clipped ratio + DAPO Clip-Higher（F17）
  - 原 REINFORCE-style（`-advantage * log_prob`）→ clipped surrogate（`-min(ratio*A, clip(ratio)*A)`）
  - `--clip-eps 0.2`（对称裁剪）+ `--clip-higher 0.28`（DAPO 非对称裁剪防 entropy collapse）
  - reference logits 复用 peft disable_adapter_layers()，无额外模型内存开销
  - 无 adapter 时自动 fallback 到 REINFORCE-style
- IPS-GRPO 实现（Phase 103）：`--ips` flag，逆频率缩放防 mode collapse
- SFT v3 完成：loss 0.1975→0.076，Write/Edit/Read 格式正确，但 0/10 correct（详见 `devlog/sft-v3.md`）
- SFT v3 数据生成：`data/sft_v4.jsonl`（160 perfect）+ `data/sft_v4_strategic.jsonl`（160 strategic）
- SFT v5 数据生成（Phase 104 correction fix 后）：`data/sft_v5.jsonl`（160 perfect, 3.0 edits/traj）+ `data/sft_v5_strategic.jsonl`（160 strategic, 3.0 edits/traj）— 51% correction edit rate, up from ~1.7 pre-fix
- SFT v6 数据生成（Phase 112 free correction Edit 后）：`data/sft_v6.jsonl`（160 perfect）+ `data/sft_v6_strategic.jsonl`（160 strategic）— 80.6% edit rate, 100% correction messages include free-edit info + entity/old_val/new_val details
- MemoryEnv 完整实现（reset/step 接口，ChromaDB embedding search，binary + shaped reward）
- SFT 轨迹生成（perfect/strategic 策略，OpenAI messages 格式）
- verl 适配器（AgentLoopBase 集成，@register memorygym_agent）
- verl reward 函数（exact match + numeric tolerance + pre-computed reward）
- slime 适配器（custom generate/reward，multi-turn episode）
- 共享工具解析（_common.py：4 种格式解析 + episode runner）
- 训练数据生成脚本（单 tier / curriculum 混合 tier）
- 训练配置（GRPO + curriculum YAML）
- 完整测试覆盖（36 tests in test_training.py + 32 in test_adapters.py）
- noise/session_break 事件支持
- GPU 冒烟测试
- 远程训练 CLI（scripts/train.py）— SSH 远程执行 + 实时日志 + GPU 自动检测
- SFT 训练管线完成 — loss 0.22→0.06，正确产出 `<tool_call>` 标签
- 多卡训练支持（DDP/FSDP via accelerate）
- SFT 全流程验收 — 结果：12 stores, 0/10 correct, reward=0.07
- 统一训练模块（`memorygym/training/` 包重构）
  - 单入口 CLI：`python -m memorygym.training <command>`
  - SFT 自动数据生成 + 训练
  - GRPO 管线（episode rollout + advantage-weighted policy gradient）
  - 共享工具层（模型加载、assistant mask、chat template）
  - 结构化输出（config.json, training_log.jsonl, metrics.json, episodes/）
- GRPO 管线端到端验证 — loss=0.504, mean_r=0.350, correct=1.5/10
  - SFT checkpoint → merge → new LoRA → rollout → GRPO loss → update
  - 详见 `devlog/sft-baseline.md`
- GRPO 训练基础设施
  - gradient checkpointing + CUDA cache clearing 解决 OOM
  - stuck detection: 非 question 事件 5 turns 无进展自动 advance
  - `scripts/train.py` 统一 CLI（status/logs/monitor/sft/grpo）+ .env 自动加载
  - KL 正则化防止 policy collapse（disable_adapter_layers 零拷贝 ref）
- SFT v2b 突破 — 8 epochs, loss 1.785→0.674, **首个能正确回答的模型**
  - 9/15 writes, 3/10 correct, reward=0.46（vs v1: 0/10, v2: 0/10）
  - 详见 `devlog/sft-v2b.md`
- 工具接口适配（Write/Edit/Read）— _common.py 解析 + 格式化 + 新 SFT 数据
- train.py 增强：远程日志 tee 保存 + 自动检测最新 log + 负值 loss regex 修复

