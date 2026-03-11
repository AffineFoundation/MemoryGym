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

1. **GRPO v3：IPS-GRPO + KL + SFT v3 base**（当前优先，阻塞于 GPU）
   - ✅ IPS-GRPO 已实现（Phase 103）：`--ips` flag，0.05 分桶 → 逆频率缩放 advantage
   - ✅ KL 正则化已实现：`--kl-coeff 0.05`
   - v2 确认 policy collapse（loss→负值），IPS 是根因修复（F14）
   - **实验计划**：先 `--ips --kl-coeff 0`（IPS only），再 `--ips --kl-coeff 0.05`（IPS+KL），对比 v2
   - Base checkpoint: `checkpoints/sft-v3-write-edit-read`（GPU 机）
   - **阻塞**：GPU 机 SSH 不可达（Permission denied），等待恢复
2. 更多 shaped reward 信号（如 search 精准度奖励、correction 完成奖励、F6 attributed reward）
3. 多模板 curriculum 效果验证（lite → standard → multi）

## 已完成

- IPS-GRPO 实现（Phase 103）：`--ips` flag，逆频率缩放防 mode collapse
- SFT v3 完成：loss 0.1975→0.076，Write/Edit/Read 格式正确，但 0/10 correct（详见 `devlog/sft-v3.md`）
- SFT v3 数据生成：`data/sft_v4.jsonl`（160 perfect）+ `data/sft_v4_strategic.jsonl`（160 strategic）
- SFT v5 数据生成（Phase 104 correction fix 后）：`data/sft_v5.jsonl`（160 perfect, 3.0 edits/traj）+ `data/sft_v5_strategic.jsonl`（160 strategic, 3.0 edits/traj）— 51% correction edit rate, up from ~1.7 pre-fix
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

