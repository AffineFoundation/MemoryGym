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

### 本线程负责

- `memorygym/training.py` — MemoryEnv RL 环境
- `memorygym/adapters/` — verl / slime 框架适配层
- `scripts/generate_train_data.py` — 训练数据生成
- `scripts/verl_memorygym.yaml` / `verl_curriculum.yaml` / `memorygym_agent.yaml` — 训练配置
- `tests/test_training.py` / `tests/test_adapters.py` — 训练相关测试
- 训练实验（SFT/GRPO）、reward 设计、curriculum 策略

### 不碰的文件（其他线程/工作流负责）

| 文件/目录 | 负责方 | 说明 |
|-----------|--------|------|
| `memorygym/worlds/` | 评测核心 | 世界模板、实体生成、问题生成、评分器 |
| `memorygym/evaluation/` | 评测核心 | 答案验证、LLM judge |
| `memorygym/simulation.py` | 评测核心 | 8 种策略验证评分有效性 |
| `memorygym/protocol.py` | 评测核心 | tier 定义、评分公式、JSON schema |
| `memorygym/memory/` | 评测核心 | 预算管理、ChromaDB/mem0 后端 |
| `memorygym/agents/stream_agent.py` | 评测核心 | 真实 LLM agent runner |
| `memorygym/bench.py` | 评测核心 | CLI 入口 |
| `sessions/EVALUATOR.md` | eval session | 评测任务队列 |
| `sessions/EXECUTOR.md` | 自治演进 | 自治循环任务 |
| `CLAUDE.md` | 全局 | 北极星，所有线程共享 |

### 共享依赖（只读使用，不修改）

- `memorygym/simulation.py` 中的 `TEMPLATES`, `_construct_and_validate`, `_data_available`, `_VALIDATOR`
- `memorygym/protocol.py` 中的 `TIERS`
- `memorygym/agents/stream_agent.py` 中的 `SYSTEM_PROMPT`
- `memorygym/worlds/base.py` 中的 `WorldTemplate`, `World`, `EntitySpec`

---

## 协作协议

### 对评测核心的依赖

本线程依赖评测核心的接口稳定。如果以下接口变更，需要同步更新训练代码：

| 接口 | 使用方 |
|------|--------|
| `WorldTemplate.generate_world()` | MemoryEnv.reset() |
| `WorldTemplate.generate_corrections()` | MemoryEnv.reset() |
| `WorldTemplate.generate_contradictions()` | MemoryEnv.reset() |
| `WorldTemplate.generate_stream()` | MemoryEnv.reset() |
| `WorldTemplate.render_document()` | generate_sft_trajectory() |
| `WorldTemplate._compact_document()` | generate_sft_trajectory() |
| `TIERS` dict 结构 | MemoryEnv.__init__(), generate_train_data.py |
| `SYSTEM_PROMPT` 模板 | get_system_prompt() |
| `_VALIDATOR.validate()` | MemoryEnv.step() (submit_answer) |

### 变更通知

- 评测核心变更以上接口时，需在本文件「接口变更日志」追加记录
- 训练线程变更共享测试时，确保 `pytest tests/ -q` 全量通过

### 接口变更日志

（暂无变更记录）

---

## 战略反馈区

> **写入规则**：训练线程在此记录实验发现、系统设计问题、改进建议。审计线程每次审计时读取此区域，将有价值的反馈转化为 Phase 任务。
>
> **格式**：每条反馈用 `#### F{编号} — 标题` 格式，包含：发现（数据/证据）、影响（对系统哪部分）、建议（如果有）。
>
> **生命周期**：审计线程读取并处理后，在反馈条目后标注 `→ 已读，处理方式：...`。训练者可以追加新条目但不要删除已有的（保留审计追踪）。

（暂无反馈）

---

## 当前任务

### GPU 状态

- GPU 开发机已解除阻塞，显存可用
- **仍需遵守共享规则**：使用前 `nvidia-smi` 确认空闲资源

### 端到端训练验证

- **GPU 端到端训练验证**：代码完成但未在真实 GPU 上跑过
- 冒烟脚本已就绪：`python scripts/smoke_test_gpu.py` (dry-run 通过)
- 推荐顺序：先 0.6B/3B 快速冒烟验证管线 → 再 7B 正式训练
- 成功标准（冒烟）：管线跑通，模型能产出 tool calls，不要求高分
- 成功标准（正式）：composite ≥ 45%, maintenance ≥ 30%

## 待办

1. **SFT 数据生成 + 微调**（当前优先）
   - 生成 SFT 轨迹 → 用 Qwen3-4B 微调，建立 tool-calling + 答题 baseline
   - GPU 机模型路径：`/home/xmyf/slime_assets/models/Qwen3-4B`
2. **GRPO 训练**（SFT baseline 后）
3. 训练超参调优（基于训练结果）
4. 更多 shaped reward 信号（如 search 精准度奖励）
5. 多模板 curriculum 效果验证

## 已完成

- MemoryEnv 完整实现（reset/step 接口，ChromaDB embedding search，binary + shaped reward）
- SFT 轨迹生成（perfect/strategic 策略，OpenAI messages 格式）
- verl 适配器（AgentLoopBase 集成，@register memorygym_agent）
- verl reward 函数（exact match + numeric tolerance + pre-computed reward）
- slime 适配器（custom generate/reward，multi-turn episode）
- 共享工具解析（_common.py：4 种格式解析 + episode runner）
- 训练数据生成脚本（单 tier / curriculum 混合 tier）
- 训练配置（GRPO + curriculum YAML）
- 完整测试覆盖（31 + 27 = 58 tests）
- noise/session_break 事件支持（training.py: _format_event + generate_sft_trajectory）
- GPU 冒烟测试脚本（scripts/smoke_test_gpu.py，dry-run 验证通过）
- GPU 端到端冒烟测试通过 ✅
  - Qwen3-4B: 143 tool calls, 15/15 writes, 0/10 correct (未训练), 管线全流程无 crash
  - Qwen2.5-0.5B: 管线跑通但模型太小无 tool calls (WARN_NO_TOOLS)
  - 修复: content 类型强制转换 (list→str), thinking mode 禁用, 上下文截断
  - GPU 机环境: 8x A100-80GB, 模型在 `/home/xmyf/slime_assets/models/`
  - 依赖已安装: torch 2.10, transformers 5.3, chromadb 1.5.4, sentence-transformers 5.2

