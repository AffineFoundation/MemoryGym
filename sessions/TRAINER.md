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

#### F2 — KL 正则化梯度审计（审计线程前沿搜索 A52）

**发现**：论文 "Comedy of Estimators"（2512.21852）指出开源 RL 库中的 KL estimator 普遍提供**不正确的梯度**。有偏梯度导致训练不稳定。

**影响**：我们的 `--kl-coeff 0.05` 实现（GRPO v3）可能受影响。

**建议**：启动 GRPO v3 前，对照该论文检查 KL 实现是否使用了 biased gradient configuration。

#### F3 — 小数据高效训练验证（审计线程前沿搜索 A52）

**发现**：Memory-R1 用仅 152 QA pairs 即泛化到 3 个 benchmark。Mem-alpha 训练 30K token 场景泛化到 400K+（13x）。

**影响**：我们不需要大量训练数据。当前 480 trajectories（sft_mixed_v2.jsonl）可能已经足够。

**建议**：如果 SFT v3 效果好，直接进入 GRPO 阶段，不需要扩充数据量。

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

1. **SFT v3：新工具接口训练**（当前优先）
   - v2b 完成：loss 1.785→0.674，smoke test 9 writes, 3/10 correct, reward=0.46
   - 但 v2b 用旧工具名（memory_store/memory_forget），上游已改为 Write/Edit/Read
   - 已生成新数据：`data/sft_mixed_v2.jsonl`（480 trajectories，Write/Edit/Read）
   - 训练 v3：用新数据 + 相同超参（8ep, lr=3e-5, lora-rank=32）
2. **GRPO v3：KL 正则化**
   - v2 实验确认 policy collapse（loss→负值，reward 不增）详见 `devlog/grpo-v2.md`
   - 已实现：`--kl-coeff 0.05`，用 peft disable_adapter_layers() 零拷贝获取 ref logits
   - 用 SFT v2b（或 v3）作为 base，对比效果
   - v2 运行中（GPU 0，step 8/10），完成后启动 v3
3. 更多 shaped reward 信号（如 search 精准度奖励、correction 完成奖励）
4. 多模板 curriculum 效果验证（lite → standard → multi）

## 已完成

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

