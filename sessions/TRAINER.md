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

## 进度反馈机制

**每完成一个 Step，在本文件「进度日志」区追加一条记录**。审计线程通过读本文件跟踪进展。

格式：
```
### 进度日志
- [时间] Step N 完成/失败 — 关键信息（分数、错误、耗时）
```

**关键节点必须立即记录**：
1. Step 0 完成 — GPU 数量、CUDA 版本
2. Step 2 完成 — final training loss
3. Step 4 完成 — base 模型各轴分数（B/M/R/E/C）
4. Step 5 完成 — SFT 模型各轴分数
5. Step 6 完成 — before/after 对比表
6. 任何失败 — 错误信息 + 已尝试的解决方案

### 进度日志

- [2026-03-14 11:26] Step 0 完成 — 4× H200 (141GB HBM3e/卡), CUDA 12.8, Driver 570.195.03, Python 3.12.3
- [2026-03-14 11:29] 代码+数据传输完成 — memorygym + 320 SFT 轨迹 (sft_v6_mixed.jsonl)
- [2026-03-14 11:41] Step 1 完成 — 合并 320 行 SFT 数据
- [2026-03-14 12:14] Step 2 开始 — Qwen2.5-7B-Instruct, LoRA rank 64, 3 epochs, batch 2×4, lr 2e-5, max_length 8192
  - 修复：`build_assistant_mask` O(n²) tokenization 瓶颈改为 O(n) token-id 匹配（原 30min+ tokenization 降至 <2min）
  - 修复：远程 /tmp 挂载 noexec 导致 vLLM triton 编译失败，用 TMPDIR=/root/tmp 绕过
- [2026-03-14 12:51] Step 2 完成 — SFT 训练完成, checkpoint: runs/sft_qwen7b_v1/checkpoints/final/ (646MB adapter)
- [2026-03-14 13:17] Step 3 完成 — vLLM server 启动 (base Qwen2.5-7B-Instruct on GPU0, port 8000)
- [2026-03-14 13:18] Step 4 进行中 — Base 模型评测
  - 修复：judge 使用 Chutes API 模型名导致 vLLM 404，添加 MEMORYGYM_JUDGE_MODEL 环境变量覆盖
  - company s0: Score=3/20(15%), B=29%, M=0%, R=0%, E=?, C=10%, 耗时 468s
  - 批量评测进行中 (17/30 完成: company 10/10, university 7/10, city 0/10)
  - **Base 完成**: 30/30 runs, Overall C=13.8±8.4 (B=23.0,M=8.4,R=11.9,E=9.2)
    - company C=13.3%(B=27.7,M=5.6,R=7.4,E=8.7)
    - university C=11.8%(B=17.2,M=4.9,R=15.0,E=8.0)
    - city C=16.4%(B=24.0,M=14.7,R=13.4,E=11.0)
- [2026-03-14] Step 5 进行中 — SFT 模型评测 (LoRA merge + vLLM restart)
  - LoRA merge 成功，vLLM server 启动成功
  - **⚠️ SFT 模型分数下降**: 中期(16/30) SFT C=4.1±3.1% vs Base C=13.8±8.4%
    - company SFT C=3.2% (Base=13.3%), university SFT C=5.6% (Base=11.8%)
    - writes=30, stored=30, missed=30 → 存了但检索/回答质量差
    - 可能原因：LoRA merge 损坏 tool_call 格式 / SFT 训练数据格式不匹配
  - **SFT 完成 (30/30)**: SFT C=4.9±4.6% vs Base C=13.8±8.4% — **SFT 下降了 8.9pp**
    - company: SFT C=3.2% vs Base C=13.3% (-10.1pp)
    - university: SFT C=3.4% vs Base C=11.8% (-8.4pp)
    - city: SFT C=8.3% vs Base C=16.4% (-8.1pp)
  - **根因分析**: LoRA merge 后存储格式退化，存了 30 entries 但检索回答质量极差
- [2026-03-15] Step 5b — SFT 方案 B (vLLM --enable-lora, 不 merge)
  - vLLM 启动成功 (--enable-lora --max-lora-rank 64)
  - 中期结果 (13/30): company C=5.2% (n=10), university C=3.1% (n=3) — 仍低于 base
  - **结论**: SFT 训练本身导致退化（不是 merge 问题），数据格式与 Qwen2.5-7B 不兼容
  - **降级方案**: 记录 Base Qwen2.5-7B 作为 "small model baseline" 写入论文
- [2026-03-15] Phase T1 结论:
  - Base Qwen2.5-7B: C=13.8±8.4% (B=23.0,M=8.4,R=11.9,E=9.2) — 30 runs × 3 templates
  - SFT merged: C=4.9% — 退化 8.9pp
  - SFT LoRA: C≈5% — 退化 ~9pp
  - **SFT 在 Qwen2.5-7B 上无效**，需要排查 SFT 数据格式兼容性
- [2026-03-15] 根因排查:
  - SFT 数据格式正确（<tool_call> 标签存在，apply_chat_template 正常）
  - build_assistant_mask 正确（25% assistant tokens，包含 tool_call）
  - **根因: 过拟合！** 3 epochs loss=0.07（<0.5 阈值），严重过拟合
  - 重训: 1 epoch, lr=1e-5, loss=0.162（合理）
  - 1-epoch SFT company (5 seeds): 全部 15% (3/20) — 和 base 13.3% 持平，不退化不提升
  - **最终结论**:
    - 3 epochs: 严重过拟合 (loss=0.07), 退化 ~9pp
    - 1 epoch: 不退化不提升 (loss=0.16), SFT 信号对 7B 模型太弱
    - **SFT 对 Qwen2.5-7B 无效**，320 trajectories 不足以在 7B 模型上产生可测提升
    - 论文可用数据: Base Qwen2.5-7B C=13.8% 作为 "small model baseline"
    - 下一步: 需要 RL (GRPO) 才能产出 before/after 提升
- [2026-03-15] 排查#4: 试 Qwen2.5-3B-Instruct（更小模型，SFT 效果可能更明显）
  - 3B 下载 + 1ep SFT 训练完成 (loss=0.158, 4min)
  - vLLM 启动 (base 3B + sft3b LoRA)
  - **3B 结果 (company, 5 seeds)**:
    - Base 3B: accuracy=35.0%, C=28.9% (B=34.5,M=27.7,R=30.4,E=20.0)
    - SFT 3B: accuracy=28.0% → **退化 -7pp**，与 7B 模式一致
    - 意外发现: Base 3B (28.9%) >> Base 7B (13.3%)！小模型在 MemoryGym 上更强
  - **深入排查**: SFT 3B 的 tool_call 格式正确（29 writes, 5 searches），问题不是工具调用失败
  - SFT "perfect 策略" 的存储方式可能反而不如 base 的自然策略（过度压缩/打包）
  - **SFT 数据的训练信号方向可能有误**——需要重新设计 SFT 策略
  - **Base 3B 完整评测完成 (30/30)**:
    - company C=27.1% (B=33.0,M=18.9,R=34.5,E=19.3)
    - university C=27.3% (B=34.0,M=17.9,R=35.2,E=19.3)
    - city C=34.1% (B=42.2,M=25.1,R=41.8,E=23.7)
    - **Overall C=29.5±11.3%** — 比 7B 的 13.8% 高 15.7pp！
  - 论文可用数据: Base 3B C=29.5%, Base 7B C=13.8% — 模型尺寸对比
- [2026-03-15] Phase T2: GRPO on Base 3B（跳过 SFT 前提，直接 RL）
  - v1 配置: group_size=4, max_turns=100, max_new_tokens=512 → 太慢（67min 还没完成 1 step）
  - v2 配置: group_size=2, max_turns=40, max_new_tokens=256, 5 steps
  - **GRPO 完成**: reward 0.013→0.088, correct 1.5→1.5/10, **writes=0 所有 step**
  - 确认 F67: lite tier 文档在上下文内，模型"不存储直接答题"
  - GRPO 在 lite tier 上无法驱动 Write 行为——需要 standard tier 或 context 截断
  - 5 steps 不足以产出显著变化，但根本问题是 reward 信号方向
- [2026-03-15] GRPO standard tier on 3B（解决 lite tier writes=0 问题）
  - 配置: standard tier, group_size=2, max_turns=50, 5 steps
  - 进行中...

### ⚠️ 审计线程通知（2026-03-15）— GRPO 代码有严重 bug，必须更新

**Phase 135（commit `a6b9075`）修复了 GRPO 训练管线的 1 个 BLOCKER + 5 个 HIGH 级别 bug**。你当前的 GRPO 实验可能在旧代码上运行，结果不可信。

**必须立即执行**：
```bash
git pull --rebase origin main  # 获取 Phase 135 修复
```

**修复内容**：
1. **🔴 BLOCKER — 零损失 fallback 阻断梯度流**：当所有 trajectory 的 advantage ≈ 0 被跳过后，旧代码创建 `torch.tensor(0.0, requires_grad=True)` 无计算图张量 → `loss.backward()` 产生零梯度 → **模型完全不训练**。修复后返回 `None`，跳过该 step 的 backward
2. **per-token ratio clipping**：旧代码在 sequence-level 做 PPO clipping（ratio 被长序列稀释），修复为 per-token GRPO clipping — 每个 token 都有有效梯度
3. **KL 散度计算修正**：旧代码用几何均值（exp of mean log ratio），修复为正确的 per-token KL
4. **移除内循环 `torch.cuda.empty_cache()`**：预期 3-5x 训练速度提升
5. **loss 归一化统一**：n_valid==1 时也做归一化
6. **MemoryEnv 资源泄漏修复**：env.close() try/finally 保护
7. **静默跳过 warning**：现在会打印 `[GRPO] X/Y trajectories used (skipped Z with |advantage| < 1e-6)`

**影响评估**：你之前的 T2 结果（writes=0, reward 0.013→0.088）很可能受 BLOCKER 影响——模型参数可能根本没更新。pull 修复后重启 standard tier 实验。

---

## 当前状态（2026-03-14）

### ⚡ 紧急任务：NeurIPS 论文训练实验（4× H200）

**背景**：论文投 NeurIPS 2026 E&D Track（Abstract May 4, Paper May 6）。论文主体已完成（PA-17/18/19），但 **Contribution 3（训练环境）没有训练结果**，被审稿人红队标为 CRITICAL 弱点。现在有 4× H200，必须在最短时间内产出可写入论文的训练实验数据。

**GPU 资源**：4× H200（141GB HBM3e/卡，共 564GB）。连接方式由用户单独告知。

**目标产出**：一张 before/after 对比表，证明 MemoryEnv 训练确实提升记忆管理分数。这张表将直接写入论文 Section 6（Training Environment）。

---

### Phase T1 — SFT 基线实验（最高优先级）

**目标**：用 SFT 微调一个模型，在 MemoryGym 上 before/after 对比，证明训练有效。

---

#### Step 0: 环境准备（~30 min）

```bash
# 1. 克隆代码
git clone <repo_url> && cd memorybench-arena
pip install -e .
pip install torch transformers peft accelerate datasets

# 2. 验证 GPU
python -c "import torch; print(torch.cuda.device_count(), 'GPUs'); print(torch.cuda.get_device_name(0))"
# 期望输出：4 GPUs + NVIDIA H200

# 3. Smoke test（CPU，验证 memorygym 可导入）
python -m memorygym.training smoke

# 4. 验证 SFT 数据存在
wc -l data/sft_v6.jsonl data/sft_v6_strategic.jsonl
# 期望：160 + 160 = 320 行
```

**如果 Step 0 就失败了**：
- `pip install -e .` 失败 → 检查 `pyproject.toml` 的 dependencies，手动安装
- `torch.cuda` 不可用 → 检查 CUDA 版本：`nvidia-smi` 和 `python -c "import torch; print(torch.version.cuda)"`
- smoke test 失败 → 检查错误信息，通常是缺少某个包

---

#### Step 1: 合并训练数据

```bash
cat data/sft_v6.jsonl data/sft_v6_strategic.jsonl > data/sft_v6_mixed.jsonl
wc -l data/sft_v6_mixed.jsonl  # 必须为 320
```

---

#### Step 2: SFT 训练（~1-2h）

**推荐模型**：`Qwen/Qwen2.5-7B-Instruct`

```bash
# 单卡即可（7B bf16 ≈ 14GB，H200 141GB 绰绰有余）
CUDA_VISIBLE_DEVICES=0 python -m memorygym.training sft \
  --model Qwen/Qwen2.5-7B-Instruct \
  --data data/sft_v6_mixed.jsonl \
  --lora --lora-rank 64 \
  --epochs 3 \
  --batch-size 2 \
  --grad-accum 4 \
  --lr 2e-5 \
  --max-length 8192 \
  -o runs/sft_qwen7b_v1
```

**SFT 完成检查**：
```bash
ls runs/sft_qwen7b_v1/checkpoints/final/
# 必须有 adapter_model.safetensors 和 tokenizer 文件
```

**SFT 故障处理**：

| 故障 | 症状 | 解决 |
|------|------|------|
| 模型下载失败 | `HTTPError` / 超时 | 设 `HF_ENDPOINT=https://hf-mirror.com` 或手动下载到本地后 `--model /path/to/local` |
| OOM | `CUDA out of memory` | `--batch-size 1 --grad-accum 8`。仍 OOM → `--max-length 4096` |
| chat template 错误 | `jinja2` 相关错误 | `pip install jinja2`。或换模型 `Qwen/Qwen2.5-3B-Instruct`（更小） |
| loss 不下降 | loss 稳定在 2-3+ | 训练数据格式可能不匹配。检查下一节"SFT 数据格式验证" |
| peft 版本问题 | `LoRA` 相关错误 | `pip install peft>=0.11` |

**SFT 数据格式验证**（如果 loss 不下降，先跑这个排查）：
```bash
python3 -c "
import json
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained('Qwen/Qwen2.5-7B-Instruct', trust_remote_code=True)
with open('data/sft_v6_mixed.jsonl') as f:
    d = json.loads(f.readline())
text = tok.apply_chat_template(d['messages'], tokenize=False)
print('Template applied OK, length:', len(text))
print('First 500 chars:', text[:500])
# 检查输出是否包含 <tool_call> 格式的工具调用
"
```

如果 `apply_chat_template` 报错或输出不含 `<tool_call>`，说明 Qwen2.5 的 chat template 和数据格式不兼容。**降级方案**：换 `Qwen/Qwen2.5-3B-Instruct` 或 `Qwen/Qwen3-4B`。

---

#### Step 3: 启动 vLLM Server（评测必需）

**关键**：`bench.py` 通过 OpenAI-compatible API 调用模型，不支持直接加载本地 checkpoint。必须用 vLLM 提供 API server。

**3a. Base 模型 server**：
```bash
pip install vllm

# Terminal 1: 启动 base 模型 server
CUDA_VISIBLE_DEVICES=0 python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --port 8000 \
  --max-model-len 32768 \
  --trust-remote-code

# 等待输出 "Uvicorn running on http://0.0.0.0:8000"
```

**验证 server 可用**：
```bash
curl -s http://localhost:8000/v1/models | python3 -m json.tool
# 应该返回模型列表
```

**vLLM 故障处理**：

| 故障 | 症状 | 解决 |
|------|------|------|
| 安装失败 | pip 编译错误 | `pip install vllm --no-build-isolation` 或用 `pip install sglang[all]` 替代 |
| OOM 启动时 | `CUDA out of memory` | `--max-model-len 16384` 或 `--gpu-memory-utilization 0.85` |
| 启动卡住 | 无输出 | 等 2-3 分钟（首次加载模型慢）。如 5+ 分钟无输出 → `Ctrl+C` 检查日志 |
| `RuntimeError: ... flash_attn` | flash attention 版本不匹配 | `pip install flash-attn --no-build-isolation` 或 `--disable-flash-attn` |

**如果 vLLM 完全无法安装**（降级方案）：
```bash
# 方案 B：用 transformers 的 pipeline server
pip install text-generation-inference  # 或用简单的 Flask wrapper

# 方案 C：用 SGLang
pip install "sglang[all]"
python -m sglang.launch_server --model Qwen/Qwen2.5-7B-Instruct --port 8000
```

---

#### Step 4: Base 模型评测（~1-2h with vLLM）

```bash
# Terminal 2（server 在 Terminal 1 运行中）：
# 设置环境变量指向本地 server
export OPENAI_API_KEY=dummy
export API_URL=http://localhost:8000/v1

# 10 seeds × 3 templates = 30 runs
for TMPL in company university city; do
  for SEED in 0 1 2 3 4 5 6 7 8 9; do
    python -m memorygym.bench \
      --model Qwen/Qwen2.5-7B-Instruct \
      --seed $SEED --template $TMPL --tier standard \
      --backend markdown \
      --api-base http://localhost:8000/v1 \
      -o eval/base_qwen7b_${TMPL}_s${SEED}.json
  done
  echo "=== $TMPL done ==="
done
```

**注意**：
- **串行跑**（不要并发）——vLLM server 已处理 batching，并发发请求只会增加 OOM 风险
- 每个 run 约 5-10 分钟（vLLM 比 API 快），30 runs ≈ 2.5-5h
- 如果某个 run 报错，跳过继续。最终有 20+ 成功 runs 就够用

**评测故障处理**：

| 故障 | 症状 | 解决 |
|------|------|------|
| `Connection refused` | server 没启动或 crash | 检查 Terminal 1，重启 server |
| `No API key found` | 环境变量没设 | `export OPENAI_API_KEY=dummy` |
| 模型输出空白 | `content: ""` | vLLM 的 `--max-model-len` 太小 → 升到 32768 |
| tool_call 解析失败 | `_extract_tool_calls` 返回空 | 模型输出可能不含 `<tool_call>` 标签。先手动测试（见下） |
| judge 报错 | `RuntimeError: No API key` | 忽略。judge 只处理 0.2% 的 rule-miss 答案，失败时判为错，不影响 before/after 对比 |
| run 卡住 > 20 min | 推理死循环 | `Ctrl+C` 跳过这个 seed，继续下一个 |

**手动测试 tool_call 输出**（如果评测全是 0 分，先跑这个）：
```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [
      {"role": "system", "content": "You are a memory management agent. Store information using tool calls.\n\nTools:\n<tool_call>{\"name\": \"Write\", \"arguments\": {\"content\": \"info\"}}</tool_call>"},
      {"role": "user", "content": "Store this: Apple has 164000 employees and $394B revenue."}
    ],
    "max_tokens": 512
  }' | python3 -c "import sys,json; print(json.load(sys.stdin)['choices'][0]['message']['content'])"
```

如果输出不含 `<tool_call>`，说明模型不会用这种格式。**解决方案**：
1. 检查是否是 Qwen2.5 而非 Qwen3（Qwen3 可能不支持 `<tool_call>` 格式）
2. 换模型试 `Qwen/Qwen2.5-14B-Instruct` 或 `Qwen/Qwen2.5-3B-Instruct`
3. 检查 `agents/stream_agent.py:120` 的 `_extract_tool_calls`，它支持 3 种格式：`<tool_call>` XML、markdown code block、bare JSON。大多数模型至少会用其中一种

---

#### Step 5: SFT 模型评测（~1-2h）

```bash
# 1. 停止 Terminal 1 的 base server（Ctrl+C）
# 2. 合并 LoRA adapter 到 base 模型（vLLM 需要完整模型）
python3 -c "
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

base = AutoModelForCausalLM.from_pretrained(
    'Qwen/Qwen2.5-7B-Instruct', torch_dtype=torch.bfloat16, device_map='cpu')
model = PeftModel.from_pretrained(base, 'runs/sft_qwen7b_v1/checkpoints/final')
merged = model.merge_and_unload()
merged.save_pretrained('runs/sft_qwen7b_v1_merged')
AutoTokenizer.from_pretrained('Qwen/Qwen2.5-7B-Instruct').save_pretrained('runs/sft_qwen7b_v1_merged')
print('Merged model saved to runs/sft_qwen7b_v1_merged')
"

# 3. 启动 SFT 模型 server
CUDA_VISIBLE_DEVICES=0 python -m vllm.entrypoints.openai.api_server \
  --model runs/sft_qwen7b_v1_merged \
  --port 8000 \
  --max-model-len 32768 \
  --trust-remote-code

# 4. 评测（同 Step 4，改 output 前缀）
export OPENAI_API_KEY=dummy
for TMPL in company university city; do
  for SEED in 0 1 2 3 4 5 6 7 8 9; do
    python -m memorygym.bench \
      --model sft-qwen7b \
      --seed $SEED --template $TMPL --tier standard \
      --backend markdown \
      --api-base http://localhost:8000/v1 \
      -o eval/sft_qwen7b_${TMPL}_s${SEED}.json
  done
  echo "=== $TMPL done ==="
done
```

**LoRA merge 故障处理**：

| 故障 | 症状 | 解决 |
|------|------|------|
| OOM merge | CPU 内存不足 | `device_map='auto'` 或在 GPU 上 merge |
| merge 后 tool_call 消失 | SFT 模型不出工具调用 | 已知问题（见历史记录）。不 merge，改用 vLLM 的 `--lora-modules` 参数 |

**如果 merge 导致 tool_call 消失**：
```bash
# 方案 B：vLLM 直接加载 LoRA（不 merge）
CUDA_VISIBLE_DEVICES=0 python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --port 8000 \
  --enable-lora \
  --lora-modules sft=runs/sft_qwen7b_v1/checkpoints/final \
  --max-model-len 32768

# 评测时 model 名改为 "sft"
python -m memorygym.bench --model sft --api-base http://localhost:8000/v1 ...
```

---

#### Step 6: 汇总结果

```bash
python3 -c "
import json, glob
for prefix in ['base_qwen7b', 'sft_qwen7b']:
    files = sorted(glob.glob(f'eval/{prefix}_*.json'))
    scores = {'B': [], 'M': [], 'R': [], 'E': [], 'C': []}
    for f in files:
        with open(f) as fh:
            d = json.load(fh)
        if not d.get('success'): continue
        ax = d['extra']['per_axis']
        scores['B'].append(ax['breadth']*100)
        scores['M'].append(ax['maintenance']*100)
        scores['R'].append(ax['reasoning']*100)
        scores['E'].append(ax['efficiency']*100)
        scores['C'].append(ax['composite']*100)
    n = len(scores['C'])
    print(f'{prefix} (n={n}):')
    for k in ['B','M','R','E','C']:
        vals = scores[k]
        if vals:
            avg = sum(vals)/len(vals)
            std = (sum((v-avg)**2 for v in vals)/len(vals))**0.5
            print(f'  {k}: {avg:.1f} +/- {std:.1f}')
    print()
"
```

**解读结果**：
- SFT composite > base composite（任何提升都是好结果）
- 特别关注 Breadth 和 Maintenance 轴的提升
- 如果 SFT 反而下降了 → 见"SFT 无提升排查"

---

### SFT 无提升排查（如果 SFT 分数 ≤ base）

**这是最可能遇到的问题。** 按顺序排查：

1. **SFT 模型是否在出 tool_call？**
   ```bash
   # 检查 eval JSON 的 conversation 字段
   python3 -c "
   import json
   with open('eval/sft_qwen7b_company_s0.json') as f:
       d = json.load(f)
   conv = d['extra']['conversation']
   tool_calls = sum(1 for m in conv if m.get('role')=='user' and m.get('content','').startswith('['))
   writes = d['extra'].get('writes_used', 0)
   print(f'Tool call responses: {tool_calls}, Writes used: {writes}')
   "
   ```
   - 如果 writes=0 → tool_call 格式不兼容，回到 Step 3 检查

2. **SFT 模型存了什么？**
   ```bash
   python3 -c "
   import json
   with open('eval/sft_qwen7b_company_s0.json') as f:
       d = json.load(f)
   print(f'stored_entities: {d[\"extra\"][\"stored_entities\"]}')
   print(f'missed_entities: {d[\"extra\"][\"missed_entities\"]}')
   print(f'writes_used: {d[\"extra\"][\"writes_used\"]}')
   "
   ```

3. **训练 loss 最终值？**
   - 如果 final loss > 1.5 → 训练不充分，增加 epochs 到 5 或 lr 到 5e-5
   - 如果 final loss < 0.5 → 可能过拟合，减少 epochs 到 1

4. **换更大/更小模型**：
   - Qwen2.5-7B 不行 → 试 `Qwen/Qwen2.5-14B-Instruct`（14B 可能工具调用更强）
   - 或试 `Qwen/Qwen2.5-3B-Instruct`（更小但训练更快，SFT 提升可能更明显）

5. **最终降级方案**：如果所有 SFT 实验都无提升，至少记录 base Qwen2.5-7B 的分数——这本身就是一个新数据点（论文当前没有 7B 模型的数据），可以写入论文作为 "small model baseline"。

---

### Phase T2 — GRPO 强化学习（如果 T1 完成且有时间）

**前提**：T1 SFT checkpoint 可用且 SFT 有提升。

```bash
CUDA_VISIBLE_DEVICES=0 python -m memorygym.training grpo \
  --model Qwen/Qwen2.5-7B-Instruct \
  --adapter runs/sft_qwen7b_v1/checkpoints/final \
  --steps 30 \
  --group-size 4 \
  --groups-per-step 2 \
  --tier lite \
  --lr 1e-5 \
  --temperature 0.7 \
  --lora-rank 16 \
  -o runs/grpo_qwen7b_v1
```

GRPO 每 step 约 30 min（4 episodes × ~7 min），30 steps ≈ 15h。**如果时间紧**：
- 减到 `--steps 10`（~5h），足够看趋势
- 或 `--tier lite`（更短 episodes）

评测同 Step 5，但用 GRPO checkpoint。

---

### 结果记录模板

完成后，将结果记录到 `devlog/training_results.md`：

```markdown
# Training Results for NeurIPS Paper

## Config
- Base model: Qwen2.5-7B-Instruct
- SFT data: 320 trajectories (160 perfect + 160 strategic)
- SFT: LoRA rank 64, 3 epochs, lr 2e-5, max_length 8192
- Eval: standard tier, 10 seeds × 3 templates (company/university/city)
- Backend: markdown
- Judge: rule-based only (no API judge)

## Results

| Model | N | S_B | S_M | S_R | S_E | S_C |
|-------|---|-----|-----|-----|-----|-----|
| Base Qwen2.5-7B | ? | ? | ? | ? | ? | ? |
| + SFT | ? | ? | ? | ? | ? | ? |
| + GRPO (optional) | ? | ? | ? | ? | ? | ? |

## Key Findings
- [填写]
```

---

### 优先级与时间分配

```
T1 SFT 实验 >>>>>>>> T2 GRPO
```

- T1 的 before/after 对比是论文的**最低需求**
- T2 是锦上添花
- 如果 T1 用了 12+ 小时，**不要跑 T2**，把 T1 结果记录好就行
- 如果 T1 SFT 无提升，排查+重试比跑 T2 更重要

### 历史记录（归档）

4-bit 低显存实验已完成（2026-03-12），技术可行但速度太慢。详见 `devlog/grpo-v4-4bit.md`。现在有 4× H200，直接用 bf16。

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

#### F70 — 4-bit 量化训练：技术可行但速度不实用（训练实验发现）

**发现**：在 ~11GB VRAM 中测试 Qwen3-4B 4-bit NF4 量化训练。5 组实验详见 `devlog/grpo-v4-4bit.md`。

**数据**：
- 4-bit 模型加载 ~3GB，总 VRAM ~10-11GB，无 OOM
- SFT 适配器 merge 到 4-bit 权重 → 工具调用格式丢失（舍入误差）
- 不 merge，保留双 LoRA（SFT + GRPO） → 工具调用推理正确
- 但 Qwen3 `<think>` 需 1024+ tokens → 4-bit 推理慢 2-3x → 单 episode 30-40 min

**影响**：4-bit 训练在技术上完全可行（管线端到端无 OOM），但实际速度太慢无法快速迭代。需要 bf16 + 完整 VRAM 才能在合理时间内完成训练。

**建议**：
1. 4-bit 仅用于推理验证（smoke_rollout），不用于正式训练
2. 正式训练需等待 GPU 容量（至少 1 张 A100 全量）
3. 代码已就绪：`--load-in-4bit` + `--backend markdown` 可随时启用

#### F70b — Fission-GRPO：工具调用错误恢复 RL（审计线程前沿搜索 A227）⭐⭐

**发现**：Fission-GRPO（arXiv 2601.15625, Jan 2026）将执行错误转化为 RL 纠正性监督。失败轨迹"裂变"为新训练实例（Error Simulator 生成诊断反馈 + on-policy 恢复 rollout）。Qwen3-8B BFCL v4 Multi-Turn: 错误恢复 +5.7%，整体 42.75%→46.75%。

**影响**：**高度相关，建议 GPU 恢复后立即探索**。
- MemoryGym correction 事件 = 工具调用后的状态变更恢复场景
- 77.4% 的失败是虚假弃权 → Fission 可处理"搜到了但说 IDK"错误模式
- 裂变机制可直接用于 GRPO v3+：correction 后未 Edit → 裂变为包含 Edit 恢复的新 rollout
- 比 binary reward 更精细，比 shaped reward（F43）更实用

**建议**：高优先级。GRPO v3+ 核心改进方向。

#### F71 — TL-GRPO：Turn-Level 轻量 GRPO（审计线程前沿搜索 A227）

**发现**：TL-GRPO（arXiv 2601.16480, Jan 2026）在 turn 级别做 group sampling 和优化，无需 critic 模型。比 GTPO（F26）更轻量，比 Turn-PPO（F45）无 critic 开销。

**影响**：与 F42（turn-level advantage 设计）直接互补。MemoryGym ~100 turn 中 Write > Read > 空 turn 价值差异大，turn-level sampling 提供更精确学习信号。

**建议**：中优先级。GRPO v3 基线后做消融对比。

#### F74 — AgeMem: Step-wise GRPO + 统一 LTM/STM 记忆训练（审计线程前沿搜索 A232）⭐⭐⭐

**发现**：AgeMem（arXiv 2601.01885, Jan 2026）将记忆操作（ADD/UPDATE/DELETE/SUMMARY/FILTER/RETRIEVE）暴露为 tool actions，三阶段渐进式 RL 训练。**Step-wise GRPO**: 终端 reward 广播到所有中间 tool steps，解决记忆操作的稀疏/不连续 reward。全基线最优（+13.9%/+21.7%/+16.1%）。

**影响**：**最高价值发现——直接适用于 MemoryGym GRPO v3+**。
- AgeMem 的工具接口 ≈ MemoryGym 的 Write/Edit/memory_search
- Step-wise GRPO 解决 MemoryGym 中"存储决策在前、reward 在后"的 credit assignment 问题
- 三阶段训练策略（存储→管理→推理）可直接映射到 MemoryGym 的 breadth→maintenance→reasoning 4 轴
- AgeMem 无信息过载/预算约束/correction tracking — MemoryGym 仍有独特价值

**建议**：最高优先级。GPU 恢复后立即实现 Step-wise GRPO。

#### F75 — RC-GRPO: Reward-Conditioned GRPO 解决多轮 Tool Calling Variance Collapse（审计线程前沿搜索 A232）⭐⭐

**发现**：RC-GRPO（arXiv 2602.03025, Feb 2026）用离散 reward token 标注轨迹，通过 reward-conditioned sampling 维持 GRPO 组内多样性。解决多轮 tool calling 中 variance collapse（模型重复同一行为模式）。

**影响**：直接相关。MemoryGym 中模型倾向重复"只用 Write 不用 Edit"的固定模式，RC-GRPO 可打破这种行为锁定。

**建议**：高优先级。与 F74 Step-wise GRPO 结合使用。

#### F76 — ALMA: 自动化记忆设计 Meta-Learning（审计线程前沿搜索 A232）

**发现**：ALMA（arXiv 2602.07755, Feb 2026, Jeff Clune 组）用 Meta Agent 搜索记忆设计（数据库 schema + 检索/更新机制）作为可执行代码。在 4 个顺序决策域超越所有人工设计基线。

**影响**：MemoryGym 可作为 ALMA 的评测环境。中期参考方向。

**建议**：低优先级。长期关注。

#### F77 — MemAgents Workshop (ICLR 2026) — 生态动态（审计线程前沿搜索 A232）

ICLR 2026 专门设立 Memory for LLM-Based Agentic Systems workshop。接收论文涵盖 episodic/semantic/working memory、外部存储接口。信号：记忆管理已成为独立研究领域。

#### F78 — Open-AgentRL / ART: 开源 Agent RL 训练框架（审计线程前沿搜索 A232）

Open-AgentRL 的 GRPO-TCR 和 ART 的 trajectory-level GRPO 均可作为 MemoryGym adapter 候选。ART 基于 Unsloth GRPOTrainer，轻量且支持 tool calls。

#### F79 — Memory-R1: 双 Agent 记忆 RL 框架（审计线程前沿搜索 A236）⭐⭐

[arxiv:2508.19828](https://arxiv.org/abs/2508.19828)。双 agent：Memory Manager（ADD/UPDATE/DELETE/NOOP）+ Answer Agent（检索→筛选→推理）。仅 152 QA pairs 训练即泛化。再次验证小数据 RL 可行性。MemoryGym 差异：有预算+信息过载。

#### F80 — StructMemEval: 记忆组织结构评测（审计线程前沿搜索 A236）⭐⭐

[arxiv:2602.11243](https://arxiv.org/abs/2602.11243)，Yandex Research。评测 agent 将记忆组织为特定结构（账本/待办/树）的能力。发现 LLM 不自发选择正确结构。与 MemoryGym 互补："存什么" vs "怎么存"。中期参考方向。

#### F81 — LoCoMo-Plus: 认知记忆评测（审计线程前沿搜索 A236）⭐

[arxiv:2602.10715](https://arxiv.org/abs/2602.10715)。评估 cue-trigger 语义断裂下的隐含约束保持。MemoryGym 的 multi_constraint 题型已部分覆盖此维度。

#### F82 — Evo-Memory: 流式自进化记忆基准（审计线程前沿搜索 A236）⭐

[arxiv:2511.20857](https://arxiv.org/abs/2511.20857)，UIUC + Google DeepMind。评测 test-time learning（推理时学习经验积累）。方向与 MemoryGym（train-time）不同，低优先级。

#### F83 — GRPO++ 实践技巧汇总（审计线程前沿搜索 A236）⭐⭐

Rubric-based reward（多维可验证 reward）、DAPO 4 技巧、entropy collapse 预防。验证 MemoryGym GRPO v3 设计方向正确（IPS + DAPO Clip-Higher + shaped reward）。

#### F84 — GiGPO：Group-in-Group Policy Optimization（审计线程前沿搜索 A240）⭐⭐⭐

[arxiv:2505.10978](https://arxiv.org/abs/2505.10978)，NeurIPS 2025。两层 credit assignment：episode-level macro advantage（轨迹间比较）+ step-level micro advantage（anchor state grouping，跨轨迹相同状态处的 action 分组比较）。ALFWorld +12%、WebShop +9% over GRPO。**无额外 critic 模型，无额外 rollout**，GPU 开销与 GRPO 相同。官方代码 verl-agent（veRL 扩展）。**对 MemoryGym 极高价值**：记忆任务中每个 Write/Edit 决策的 credit 难以从 trajectory-level reward 分离，GiGPO 的 anchor state grouping 可直接解决。建议 GRPO v3 跑通后，替换为 GiGPO 作为下一步优化。

#### F85 — MEM1：记忆+推理协同的端到端 RL 框架（审计线程前沿搜索 A240）⭐⭐

[arxiv:2506.15841](https://arxiv.org/abs/2506.15841)，MIT。核心：agent 每轮更新一个 compact shared internal state（同时支持记忆整合和推理），reasoning 充当 working memory。MEM1-7B 在 16 目标多跳 QA 上比 Qwen2.5-14B 性能提升 3.5×、memory 占用降低 3.7×。**启示**：MemoryGym 当前 memory 和 reasoning 是分离的（存储 → 检索 → 推理），MEM1 表明统一表征更高效。长期方向参考，不改短期计划。

#### F86 — Mem2ActBench：记忆驱动工具调用基准（审计线程前沿搜索 A240）⭐

[arxiv:2601.19935](https://arxiv.org/abs/2601.19935)，Jan 2026。400 个 memory-dependent tool-use 任务（2029 对话提取），测试 agent 能否主动利用记忆执行工具调用（非被动回忆）。7 个记忆框架均表现不足。**差异化**：Mem2ActBench 关注"记忆→action grounding"，MemoryGym 关注"信息过载下的存储决策+更新追踪"，互补。竞品监控。

#### F87 — BCAS：预算约束 Agentic 搜索设计决策（审计线程前沿搜索 A240）⭐

[arxiv:2603.08877](https://arxiv.org/abs/2603.08877)，Mar 2026。对 budget-constrained RAG 进行系统实验：搜索深度、检索策略（hybrid lexical+dense+reranking 最优）、completion budget 的交互影响。**对 MemoryGym 的价值**：验证 hybrid 搜索（MarkdownBackend 已支持）在预算约束下优于纯 dense（ChromaDB），可作为推荐默认后端的实证支持。

#### F88 — λ-GRPO：GRPO 隐式 PRM + 修复方案（审计线程前沿搜索 A245）⭐⭐

[arxiv:2509.21154](https://arxiv.org/abs/2509.21154)。**理论贡献**：证明 GRPO 在 group 内共享 prefix 时自动产生 step-level process reward（隐式 PRM）。但 non-uniform 分布的 process steps 妨碍 exploration/exploitation。提出 λ-GRPO 简单修正，提升验证精度。**对 MemoryGym 的价值**：MemoryGym 的 multi-turn rollout 中大量 step 共享 prefix（同一文档流 → 不同 Write 决策），GRPO 本身已在做 step-level credit——不需要显式 PRM。λ-GRPO 修正可直接应用。

#### F89 — GRPO Survey：生成模型 GRPO 全景综述（审计线程前沿搜索 A245）⭐

[arxiv:2603.06623](https://arxiv.org/abs/2603.06623)，Mar 2026。涵盖 reward design、credit assignment、sampling efficiency、diversity preservation、reward hacking mitigation。作为 GRPO v3 调参和设计决策的参考手册。

#### F90 — TA-Mem：工具增强自主记忆检索（审计线程前沿搜索 A245）⭐

[arxiv:2603.09297](https://arxiv.org/abs/2603.09297)，Mar 2026。LLM agent 通过工具选择（key-based lookup + similarity search）自主探索记忆。在 LoCoMo 上超越 baselines。**差异化**：TA-Mem 设计记忆检索策略，MemoryGym 评测+训练存储决策。互补。

#### F91 — MemAgents Workshop (ICLR 2026) 更新（审计线程前沿搜索 A245）

Workshop April 26-27 Rio de Janeiro。接收论文通知 March 1 已发。Accepted papers list 尚未公开可查。下次前沿搜索时重查。

#### F92 — HCAPO：Hindsight Credit Assignment for Long-Horizon LLM Agents（审计线程前沿搜索 A250）⭐⭐⭐

[arxiv:2603.08754](https://arxiv.org/abs/2603.08754)，Mar 2026。**核心**：用 LLM 自身作为 post-hoc critic，通过 hindsight reasoning 精化 step-level Q-value，解决 GRPO 两大瓶颈（不精确的 step Q-value 估计 + 中间状态 value baseline 错位）。Multi-scale advantage 机制在关键决策点补充 baseline。WebShop +7.7%、ALFWorld +13.8% over GRPO (Qwen2.5-7B)。**对 MemoryGym 极高价值**：每个 Write/Edit 决策是关键决策点，HCAPO 的 hindsight critic 可回溯性评估"这个 Write 是否对最终得分有贡献"。与 GiGPO (F84) 互补：GiGPO 跨轨迹分组 vs HCAPO 轨迹内 hindsight。建议 GRPO v3 → GiGPO → HCAPO 作为训练算法演进路径。

#### F93 — Memex(RL)：Indexed Experience Memory + RL 预算下读写优化（审计线程前沿搜索 A250）⭐⭐⭐

[arxiv:2603.04257](https://arxiv.org/abs/2603.04257)，Mar 2026。indexed experience memory：维护 compact working context（摘要+索引）+ 外部 full-fidelity database，agent 按需 dereference 索引恢复原始证据。MemexRL 用 reward shaping 在 context budget 下优化 write/read 行为——agent 自主学习"存什么、怎么摘要、怎么索引、何时检索"。**与 MemoryGym 高度相关**：两者都在 budget 约束下训练存储决策，Memex 的 indexed memory 架构可作为 MemoryGym 后端的演进方向参考。

#### F94 — AMemGym：Interactive Memory Benchmarking（审计线程前沿搜索 A250）⭐⭐⭐

[arxiv:2603.01966](https://arxiv.org/abs/2603.01966)，Mar 2026，**ICLR 2026 accepted**。核心差异化：on-policy 交互式评测（LLM 模拟用户 role-play）+ structured state evolution + 支持 self-evolution 优化。评测 RAG/long-context/agentic memory 均有 gap。**直接竞品**。MemoryGym 差异化：(1) 信息过载+预算约束（AMemGym 无预算），(2) 修正/更新追踪，(3) RL 训练环境（MemoryEnv），(4) 确定性+反作弊。竞品数量更新：10+。

#### F95 — MemPO：Self-Memory Policy Optimization（审计线程前沿搜索 A250）⭐⭐

[arxiv:2603.00680](https://arxiv.org/abs/2603.00680)，Mar 2026。agent 自主管理记忆：3 个 action（<mem>, <think>, <tool_call>）。memory effectiveness-based credit assignment。F1 +25.98% over base，token 减少 67%。**启示**：MemPO 的 <mem> action 与 MemoryGym 的 Write 类似，credit assignment 方法可参考。验证记忆管理是可训练的核心能力。

#### F96 — Diagnosing Retrieval vs Utilization Bottlenecks（审计线程前沿搜索 A250）⭐⭐

[arxiv:2603.02473](https://arxiv.org/abs/2603.02473)，Mar 2026。3×3 实验：3 种 write 策略（raw chunks / Mem0 fact extraction / MemGPT summarization）× 3 种 retrieval（cosine / BM25 / hybrid reranking）。**关键发现**：retrieval 是主导因素（准确率跨 20pp），write 策略仅 3-8pp 差异。Raw chunks（零 LLM 调用）匹配或超越昂贵的替代方案。**对 MemoryGym 的启示**：验证了 breadth 是瓶颈的判断（A247）——存储广度受限时 retrieval 方法更重要。支持优先优化检索而非存储格式。

#### F97 — ProxMO：Proximity-Based Multi-Turn Optimization（审计线程前沿搜索 A255）⭐⭐

[arxiv:2602.19225](https://arxiv.org/abs/2602.19225)，Feb 2026。解决 multi-turn agent 训练中 GRPO 的 credit assignment 问题：task difficulty 波动导致 credit 误分配。ProxMO 引入 success-rate-aware modulation 动态调整梯度强度 + global context 感知。**对 MemoryGym 的价值**：MemoryGym 的 multi-turn rollout 中 task difficulty 随模板/seed 变化大，ProxMO 的 difficulty-aware 机制可改善训练稳定性。与 HCAPO (F92) 互补：HCAPO 精化单步 Q-value，ProxMO 调整全局梯度强度。

#### F98 — C3：Contextual Counterfactual Credit Assignment（审计线程前沿搜索 A255）⭐⭐

[arxiv:2603.06859](https://arxiv.org/abs/2603.06859)，Mar 2026。多 agent LLM 协作中的因果信用分配：冻结 transcript context → 评估 context-matched 替代方案 → LOO baseline。隔离单个 message 的因果影响。**对 MemoryGym 的价值**：虽然 MemoryGym 是单 agent，但 C3 的核心思想（冻结 context + 评估 counterfactual action）可应用于 Write/Edit 决策的 credit：固定其他决策不变，只变一个 Write → 观察最终得分变化。需要额外 rollout 但 credit 精度最高。

#### F99 — MemAgents Workshop (ICLR 2026) 状态更新（审计线程前沿搜索 A255）

Workshop April 26-27 Rio de Janeiro。Camera-ready deadline March 11 已过。OpenReview 页面 `ICLR.cc/2026/Workshop/MemAgent` 存在但 accepted papers list 仍未公开。下次前沿搜索时再查。

#### F100 — Stratified GRPO：异构轨迹的分层优势估计（ICLR 2026）⭐⭐⭐

[arxiv:2510.06214](https://arxiv.org/abs/2510.06214)，ICLR 2026 正式接收。核心问题：搜索 agent 轨迹结构异构（不同搜索调用次数/位置/结果），标准 GRPO 用全局 baseline 导致 cross-stratum bias（"苹果比橘子"）。提出 Stratified Advantage Normalization (SAN)：按结构属性（如工具调用次数）将轨迹分层，层内计算优势。理论上条件无偏 + 层内单位方差。实验 **+11.3pp**（最大改进），训练更稳定。**对 MemoryGym 的价值**：MemoryGym RL 轨迹同样异构——Write/Edit/Read 调用次数不同导致结构差异。SAN 可直接应用于 GRPO v3：按 tool call 数量分层计算优势。实现简单（分组 normalize），无需额外模型。**推荐优先级最高**。

#### F101 — GEM：Agentic LLM 通用训练环境（ICLR 2026）⭐⭐

[arxiv:2510.01051](https://arxiv.org/abs/2510.01051)，ICLR 2026。开源 agent 训练 gym：异步向量化执行、24 种环境、PPO/GRPO/REINFORCE 基线。提出 REINFORCE with Return Batch Normalization (ReBN) 作为 dense per-turn reward 的基线方法。代码 `github.com/axon-rl/gem`。**对 MemoryGym 的价值**：(1) 竞品参考——GEM 是通用 agent gym，MemoryGym 是记忆专用 gym；(2) 架构参考——异步向量化执行可提升 MemoryEnv 训练吞吐；(3) ReBN 方法可与 GRPO v3 对比。

#### F102 — GTPO/GRPO-S：Token/Sequence 级熵加权奖励塑形⭐⭐

[arxiv:2508.04349](https://arxiv.org/abs/2508.04349)，v2 Feb 2026。GRPO 的信用分配过粗（整个序列统一奖励）。GTPO 用 token 级熵加权 reward，GRPO-S 用 sequence 级熵加权。理论基于方差缩减。**对 MemoryGym 的价值**：MemoryGym 中 tool call token（Write/Edit 参数）比非工具 token 更重要。熵加权可自动聚焦高不确定性 token（通常是决策点）。但实现复杂度高于 Stratified GRPO。

#### F103 — Demystifying GRPO：U-统计量视角⭐⭐

[arxiv:2603.01162](https://arxiv.org/abs/2603.01162)，Mar 2026（最新）。证明 GRPO policy gradient 是 U-statistic。三个改进方向：修正 baseline term、修正 importance sampling ratio、不同 reward normalization。**对 MemoryGym 的价值**：理论基础——理解 GRPO 的统计性质有助于选择正确的 normalization 策略（与 F100 Stratified GRPO 互补）。

#### F104 — VSPO：Value-Based Sampling + Progressive Reward Shaping⭐⭐

[arxiv:2512.07478](https://arxiv.org/abs/2512.07478)，Dec 2025。针对 agentic RL 提出 Progressive Reward Shaping (PRS) + Value-based Sampling Policy Optimization (VSPO)。VSPO 用 task-value metric 替换低价值样本，value-smoothing clipping 稳定梯度。**对 MemoryGym 的价值**：PRS 可缓解 MemoryGym 的稀疏奖励问题（最终才给 4 轴分数）。按难度渐进奖励塑形与 MemoryGym 的 tier 系统天然契合（lite→standard→hard 渐进训练）。

#### F105 — HiPER：Hierarchical Plan-Execute RL + Credit Assignment（审计线程前沿搜索 A265）⭐⭐

[arxiv:2602.16165](https://arxiv.org/abs/2602.16165)，Feb 2026。将 agent 策略分解为 high-level planner（提出 subgoal）+ low-level executor（执行多步 action），引入 Hierarchical Advantage Estimation (HAE) 在两个层级分别做 credit assignment。理论上无偏且方差低于 flat GAE。ALFWorld 97.4%、WebShop 83.3%（Qwen2.5-7B，+6.6%/+8.3%）。**对 MemoryGym 的价值**：MemoryGym 的记忆任务天然两层——planner 决定"存哪些实体"，executor 决定"用 Write 还是 Edit、存储格式"。HAE 可在 subgoal 级别评估"选择存储实体 X"的价值，再在 action 级别评估"具体的 Write 参数"质量。与 HCAPO (F92) 互补：HCAPO 是 hindsight single-level，HiPER 是 foresight two-level。

#### F106 — InT：Self-Proposed Interventions 做 Step-Level Credit（审计线程前沿搜索 A265）⭐⭐

[arxiv:2601.14209](https://arxiv.org/abs/2601.14209)，Jan 2026，ICLR 2025。模型自己找到 reasoning trace 中第一个错误步 → 提出单步修正 → SFT 在修正后的轨迹上。解决标准 RL 对整个轨迹统一 reward 的 credit misassignment。IMO-AnswerBench +14%（4B 模型超越 20B）。**对 MemoryGym 的价值**：可应用于失败轨迹分析——模型回看自己的 Write/Edit 序列，找到第一个导致后续失败的存储决策，生成修正版 SFT 数据。与当前 SFT trajectory 生成（perfect + strategic）互补：增加"错误+修正"维度的训练信号。

#### F107 — MemAgents Workshop (ICLR 2026) 第四次状态检查（审计线程前沿搜索 A269）

Workshop April 26-27 Rio de Janeiro。Camera-ready deadline March 11 已过。OpenReview 页面 `ICLR.cc/2026/Workshop/MemAgent` 存在但 accepted papers list 仍未公开（第 4 次检查）。距 Workshop 还有 ~6 周。iclr.cc/virtual/2026/workshop/10000792 页面已创建。下次前沿搜索时继续跟踪。

#### F108 — Critique-GRPO：Natural Language Critique 突破 RL 训练平台期（审计线程前沿搜索 A269）⭐⭐

[arxiv:2506.03106](https://arxiv.org/abs/2506.03106)，v5 更新。核心观察：纯数值 reward 的 GRPO 存在三个根本局限——performance plateau、无效自我反思、persistent failures。Critique-GRPO 在 RL plateau 时引入自然语言 critique 引导模型修正失败方案，同时学习初始响应和 critique-guided refinement。Qwen +15-21% Pass@1，AIME 2024 +16.7%。代码开源 `github.com/zhangxy-2019/critique-GRPO`。**对 MemoryGym 的价值**：当 GRPO v3 训练 plateau 时（F68 已预见此问题），Critique-GRPO 提供突破方向——模型 critique 自己的 Write/Edit 决策序列（"这个 Write 存了冗余信息浪费预算"），生成修正版轨迹用于继续训练。与 InT (F106) 互补：InT 找第一个错误步，Critique-GRPO 提供自然语言修正理由。

#### F109 — ToolRM：Tool-call Reward Model 做 Per-Tool Credit（审计线程前沿搜索 A269）⭐⭐

[OpenReview](https://openreview.net/forum?id=LnBEASInVr) + [arxiv:2509.11963](https://arxiv.org/abs/2509.11963)。专门为 tool invocation 设计的 Process Reward Model。解决 outcome-only reward 的 gradient conflict：正确的 tool call 可能因最终答案错误而被惩罚。TRM 为每个 tool invocation 提供独立的 reward signal，与 PPO/GRPO 集成。**对 MemoryGym 的价值**：MemoryGym 的 Write/Edit/Read/memory_search 是标准 tool calls。TRM 可为每个 Write 评分（"这个 Write 存储了高价值实体 → positive reward"），解决 GRPO 的 sparse reward 问题。与 shaped reward (F68) 互补：shaped reward 是手工设计的，TRM 是学习到的。优先级：GRPO v3 基线跑通后评估。

#### F110 — Letta Leaderboard / Context-Bench：产品型 Agent Memory 排行榜（审计线程前沿搜索 A272）

[leaderboard.letta.com](https://leaderboard.letta.com/)。Letta 发布 agent memory 排行榜，测 LLM 在 Letta 框架中的 core memory（上下文内）+ archival memory（外部存储）管理能力。Claude Sonnet 4 和 GPT-4.1 领先。Context-Bench 额外测 filesystem 操作链和 skill 发现。**与 MemoryGym 差异**：Letta 测 framework-specific 能力（在 Letta API 下读写记忆），MemoryGym 测 model-agnostic 的记忆管理链（信息过载 + 预算 + 变更追踪）。非学术竞品，但产品影响力值得关注。

#### F111 — MemAgents Workshop ICLR 2026 状态（第 5 次检查，A272）

接受通知已于 2026-03-01 发出，OpenReview page 仍显示 loading spinner，accepted papers 未公开。Workshop 2026-04-26/27 举行。下次检查应在 3 月下旬或 4 月初。

#### F112 — MLMT-RL：Multi-Level Multi-Turn RL 超越 GRPO（审计线程前沿搜索 A277）⭐⭐

[OpenReview](https://openreview.net/forum?id=u1RjV99DPu)，Oct 2025。分解推理为高层 feedback 生成 + 低层响应修正的双层优化。2B MLMT-RL 超越 3B GRPO：MATH500 +3.1%，MBPP +5.2%，GPQA +4.8%。核心：textual feedback 提供 dense interpretable 学习信号，替代 sparse binary reward。**对 MemoryGym 的价值**：MemoryGym 的 GRPO 训练面临同样的 sparse reward 问题。MLMT-RL 的 bi-level 框架可映射到：高层 = 存储策略评估（"应该存哪些实体"），低层 = 具体 Write/Edit 执行。与 Critique-GRPO (F108) 互补但更系统化。优先级：GRPO v3 基线后评估。

#### F113 — Practitioner's Guide to Multi-turn Agentic RL（审计线程前沿搜索 A277）⭐⭐⭐

[arxiv:2510.01132](https://arxiv.org/abs/2510.01132) + [OpenReview](https://openreview.net/forum?id=K6T0o875zF)。系统性实证研究：multi-turn agent RL 的设计空间分解为 environment/reward/policy 三大支柱。关键发现：(1) dense turn-level rewards 加速训练但稳定性依赖 RL 算法选择；(2) PPO（biased）vs RLOO（unbiased）在 reward sparsity 不同时表现反转；(3) 简单环境的信号可泛化到复杂任务；(4) 存在最优 SFT→RL 训练比例。TextWorld/ALFWorld/SWE-gym 实验。**对 MemoryGym 的价值**：**最直接相关的指南**。MemoryGym 的 GRPO 训练正在三个支柱上做决策（环境=MemoryEnv tier 设计，reward=shaped vs sparse，policy=SFT→GRPO 比例）。F113 的 empirical recipe 可直接指导我们的超参选择。强烈建议 GPU 恢复后第一优先级参考。

#### F114 — MemAgents Workshop 状态（第 6 次检查，A277）

OpenReview 页面仍未显示 accepted papers。Workshop 2026-04-26/27，距今 ~6 周。

#### F115 — Agent Lightning：零代码 Agent RL 训练框架（审计线程前沿搜索 A281）⭐⭐

[arXiv:2508.03680](https://arxiv.org/abs/2508.03680) + [GitHub](https://github.com/microsoft/agent-lightning)。Microsoft 开源框架，核心创新：(1) 完全解耦 agent 执行与 RL 训练——支持 LangChain/AutoGen/自定义 agent 零代码接入；(2) LightningRL 层次化 RL 算法，内含 credit assignment 模块自动将轨迹分解为训练 transition；(3) formulate agent execution as MDP。**对 MemoryGym 的价值**：当前 verl/slime adapters 是手写适配层，Agent Lightning 可能直接替代——将 MemoryEnv 作为 environment 接入，无需维护 adapter 代码。GPU 恢复后值得评估是否能简化训练基础设施。

#### F116 — MemAgents Workshop 论文开始公开（第 7 次检查，A281）

Acceptance notification 已过（2026-03-01）。OpenReview 开始出现论文：(1) "Memory Is Reconstructed, Not Retrieved: Graph Memory for LLM Agents"（MRAgent，2026-03-03）；(2) "MemGen: Weaving Generative Latent Memory"；(3) MemAgent (Multi-Conv RL) 获 **Oral** 报告。Workshop 2026-04-27 Rio de Janeiro。完整 accepted papers 列表尚未统一发布，但已可逐篇浏览。

#### F117 — Fireworks Multi-Turn RL 实践指南（审计线程前沿搜索 A281）⭐

[Fireworks Blog](https://fireworks.ai/blog/best-practices-for-multi-turn-RL)。工业级 multi-turn RL 实践总结：(1) 基础模型需 ~20% zero-shot 成功率才能 RL（否则梯度被噪声主导）；(2) 最终 checkpoint 通常不是最优（RL 会过拟合 reward quirks）；(3) SFT golden traces 不够，agent 需从交互中学习。**对 MemoryGym 的价值**：当前模型 composite ~18%，接近 20% 阈值——SFT 可能刚好够 RL cold start。Checkpoint selection 策略需在 GRPO 训练中加入 eval-based early stopping。

#### F118 — A-GRAE：GRPO 隐式优势对称性问题诊断与修复（审计线程前沿搜索 A285）⭐⭐⭐

[arXiv:2602.05548](https://arxiv.org/abs/2602.05548)，Feb 2026。**诊断 GRPO 核心缺陷**：Group Relative Advantage Estimation 存在隐式对称性——(1) group level: 正确/错误轨迹权重严格对称，导致未采样 action logits 不变，阻碍新正确解的探索；(2) sample level: 隐式偏好中等难度样本，无法适应训练过程中难度焦点的变化。A-GRAE 通过非对称调制修复两个问题，7 个 benchmark 持续提升 GRPO 及其变体。**对 MemoryGym 的价值**：**最直接相关**。我们的 GRPO v2 出现 policy collapse，可能正是探索不足导致。A-GRAE 是 drop-in 修复：不改 GRPO 框架，只调优势估计的对称性。GPU 恢复后 **第一优先级实验**。

#### F119 — MemAgents Workshop 第 8 次检查（审计线程前沿搜索 A285）

OpenReview 页面存在但完整 accepted papers 列表仍未统一发布。个别论文可通过直接 URL 访问（MRAgent, MemGen, MEM-α）。Workshop 2026-04-27，距今 ~6 周。

#### F120 — MemAgents Workshop 第 9 次检查 + V21 无新发现（审计线程前沿搜索 A288）

ICLR schedule 显示 MemAgent Oral Session 1A 在 **April 23 (Thu) 10:30-12:00**（早于之前预计的 4/27）。"MemAgent: Reshaping Long-Context LLM with Multi-Conv RL-based Memory Agent" 确认获 Oral。V21 搜索无新的未跟踪论文——EMPO2(F8)、Memex(RL)(F10/F93)、MIRA(F7) 均已在追踪中。前沿跟踪趋于饱和。

---

#### F121 — AgeMem：Step-wise GRPO 训练记忆工具使用（审计线程前沿搜索 V24/A297）⭐⭐⭐

[arXiv:2601.01885] 统一 LTM/STM 为工具动作，3 阶段渐进 RL：先存储 → 再检索 → 再协调。核心创新：**step-wise GRPO** 将终端奖励广播到所有前序步骤，解决长程 credit assignment。ALFWorld/SciWorld/HotpotQA +4.8-8.6pp。**直接映射 MemoryGym 的 Write/Edit/Read 动作**，3 阶段课程对应 breadth → maintenance → reasoning 进阶。GPU 恢复后与 A-GRAE(F118) 并列**第一优先级**。

#### F122 — MemoryArena：多会话记忆基准（审计线程前沿搜索 V24/A297）

[arXiv:2602.16313] 跨会话记忆迁移评测，4 领域，57 步平均。**竞品**但无预算压力、无信息过载。MemoryGym 差异化维持。

#### F123 — AMA-Bench：长程 Agent 记忆基准（审计线程前沿搜索 V24/A297）

[arXiv:2602.22769] 首个用真实 agent 轨迹的记忆评测。因果图 + 工具增强检索。发现"相似度检索本质有损"，验证 MemoryGym 混合搜索方向。

#### F124 — ICRL：无 SFT 的工具使用 RL（审计线程前沿搜索 V24/A297）⭐⭐⭐

[arXiv:2603.08068] 用 few-shot prompting 替代 SFT 冷启动，渐进移除 in-context 示例，从模仿过渡到自主工具使用。**可能完全消除 SFT v6 依赖**。GPU 恢复后值得快速实验：MemoryGym Write/Edit/Read 能否纯 RL 学会？

#### F125 — T3RL：工具验证 + 测试时 RL（审计线程前沿搜索 V24/A297）⭐

[arXiv:2603.02203] 用工具执行结果验证 rollout 并加权奖励估计，难题增益更大。memory_search 结果可作为 GRPO 训练的验证信号。

#### F126 — MemSearcher：Multi-Context GRPO 跨上下文泛化（审计线程前沿搜索 V24/A297）⭐⭐

[arXiv:2511.02805] 维护紧凑记忆替代完整历史。**multi-context GRPO**：不同上下文下采样轨迹组并跨组传播优势。3B 超 7B baseline。直接适用 MemoryGym 跨 seed 泛化训练。

#### F127 — GRPO-CARE：一致性感知 GRPO（审计线程前沿搜索 V24/A297）⭐

[arXiv:2506.16141] 在 GRPO 上增加一致性奖励——不仅奖励正确答案，还奖励推理步骤与答案的逻辑一致性。可作为 MemoryGym GRPO 的奖励增强插件。

#### F128 — MemAgents Workshop 第 10 次检查（审计线程前沿搜索 V24/A297）

April 26-27, Rio de Janeiro. 接收论文列表仍未公布，预计 3 月下旬发布。

---

#### F129 — MASPO：软高斯门控替代 GRPO 硬裁剪（审计线程前沿搜索 V25/A302）⭐⭐

[arXiv:2602.17550] Mass-Adaptive Soft Policy Optimization。软高斯门控 + 质量自适应限制器 + 非对称风险控制器。替代 GRPO 硬裁剪，减少梯度信号浪费。MemoryGym 稀疏记忆奖励场景下硬裁剪问题严重，MASPO 可能更适合。

#### F130 — AERO：贝叶斯跳过零优势 rollout 组（审计线程前沿搜索 V25/A302）⭐⭐

[arXiv:2602.14338] Adaptive Efficient Rollout Optimization。贝叶斯后验判断零优势组并跳过 + 选择性拒绝裁剪。**48% 计算量减少，45% 墙钟加速**，精度不变。MemoryGym 记忆任务有大量全失败 rollout 组，AERO 可直接降低训练成本。

#### F131 — DPPO：无偏动态裁剪 + 密集 Prompt Packing（审计线程前沿搜索 V25/A302）⭐

[arXiv:2603.04135] Dynamic Pruning Policy Optimization。重要性采样校正 + prompt/completion 双层裁剪。2.37x 加速。可与 AERO 组合。

#### F132 — WS-GRPO：弱监督前缀停止信号减少过度推理（审计线程前沿搜索 V25/A302）⭐

[arXiv:2602.17025] 从结果标签训练偏好模型，产出前缀级 continue/stop 信号。减少 rollout 长度。记忆任务冗余推理问题适用。

#### F133 — UMA / Ledger-QA：端到端 RL 记忆 CRUD + 累积更新追踪基准（审计线程前沿搜索 V25/A302）⭐⭐⭐

[arXiv:2602.18493] Unified Memory Agent。单策略端到端 RL 统一 CRUD + QA。双记忆：紧凑核心摘要 + 结构化 Memory Bank。**Ledger-QA 基准**：从累积更新中推导潜在值——**与 MemoryGym maintenance 轴高度相似**，验证设计方向。直接竞品，需关注。

#### F134 — MemSifter：小模型代理检索 + 结果驱动 RL（审计线程前沿搜索 V25/A302）⭐

[arXiv:2603.03379] 小代理模型扫描原始历史，筛选关键证据，再喂给工作 LLM。零索引计算。双模型架构可启发 MemoryGym 训练设置。

#### F135 — StructMemEval：结构化记忆组织评测（审计线程前沿搜索 V25/A302）⭐⭐

[arXiv:2602.11243] Yandex Research。评测 agent 能否将记忆组织为任务适配结构（账本、待办、树）。关键发现：**LLM 不提示就不会正确组织记忆**。验证 MemoryGym 的 prompt 中立设计——存储策略本身是被测能力。

#### F136 — SSPO：序列级软门控 + 熵感知正则（审计线程前沿搜索 V25/A302）⭐

[arXiv:2602.19327] Soft Sequence Policy Optimization。几何均值序列级重要性权重。多轮记忆任务可能优于 token 级方法。

#### F137 — UI-Mem：分层经验记忆 + 分层组采样（审计线程前沿搜索 V25/A302）

[arXiv:2602.05832] GUI RL 中的分层组采样（混合引导/非引导轨迹）。可迁移到 MemoryGym GRPO 训练。中等相关。

#### F138 — MemAgents Workshop 第 11 次检查（审计线程前沿搜索 V25/A302）

接收论文列表仍未公布。April 26-27, Rio de Janeiro。

---

#### F139 — MemPO：自主记忆管理 + 记忆效果 credit assignment（审计线程前沿搜索 V26/A307）⭐⭐⭐

[arXiv:2603.00680] Self-Memory Policy Optimization。agent 自主总结和管理记忆，基于**记忆效果**做 credit assignment。+25.98% F1，减少 token 消耗。**直接解决 MemoryGym 核心问题**——预算压力下的记忆管理 + 记忆操作级奖励归因。GPU 恢复后与 AgeMem(F121) 比较实验设计。

#### F140 — Critique-GRPO：自然语言批评融入 GRPO 循环（审计线程前沿搜索 V26/A307）⭐⭐

[arXiv:2506.03106] 在 GRPO 在线 RL 中集成自然语言批评，解决纯数值奖励的训练瓶颈。+16.7% AIME。MemoryGym 多轴评分可生成结构化批评（如"存了实体但未更新修正"）作为辅助训练信号。

#### F141 — SGE：策略空间探索替代动作空间探索（审计线程前沿搜索 V26/A307）⭐⭐

[arXiv:2603.02045] Strategy-Guided Exploration。先生成自然语言策略，再执行动作。混合温度采样 + 策略反思。映射到 MemoryGym：探索不同记忆管理策略（"优先存可能被修正的实体" vs "最大化广度"）而非单个动作。

#### F142 — DCPO：解耦校准 + 准确率的 GRPO 变体（审计线程前沿搜索 V26/A307）⭐

[arXiv:2603.09117] Decoupled Calibration Policy Optimization。修复 GRPO 中准确率与校准的梯度冲突。直接映射 MemoryGym 元认知轴（知道自己不知道什么）。

#### F143 — RAPO：检索增强策略优化（审计线程前沿搜索 V26/A307）⭐

[arXiv:2603.03078] Retrieval-Augmented Policy Optimization (KDD'26)。检索成功策略扩展 on-policy 探索。可用于跨 seed/template 拉取成功记忆策略。

#### F144 — MemRL：Q 值记忆效用过滤（审计线程前沿搜索 V26/A307）

[arXiv:2601.03192] 非参数自我进化，两阶段检索（语义 + Q 值效用）。无需权重更新。Q 值记忆评分概念对应 MemoryGym 效率轴。

#### F145 — RLAR：自适应奖励工具合成（审计线程前沿搜索 V26/A307）

[arXiv:2603.00724] Agent 动态合成奖励工具代码。MemoryGym 已有确定性评分，低相关。

#### F146 — MemAgents Workshop 第 12 次检查（审计线程前沿搜索 V26/A307）

接收论文通知日期 March 1，OpenReview 页面应已有接收列表但搜索引擎未索引。April 26-27。

#### F147 — Scaf-GRPO：渐进式脚手架解决 GRPO 探索悬崖（审计线程前沿搜索 V27/A318）⭐⭐⭐

分层提示（抽象→具体步骤）当模型停滞时逐级加入。Qwen2.5-Math-7B AIME24 +44.3%。**直接可用**：MemoryGym 中 reasoning 轴困难时可加入存储策略提示作为脚手架。

#### F148 — SimpleTIR：Void-Turn Filtering 稳定多 Turn 工具 RL（审计线程前沿搜索 V27/A318）⭐⭐⭐

过滤既无代码也无答案的空转 turn，稳定多 turn TIR 训练。Qwen2.5-7B AIME24 22.1→50.5。**关键洞察**：MemoryGym 中不执行任何工具的 turn 应标记为 void turn 并降权/过滤。

#### F149 — RICOL：回顾式 ICL 做时序 Credit Assignment（审计线程前沿搜索 V27/A318）⭐⭐⭐

NeurIPS 2025。将稀疏 reward 转为密集 advantage（通过回顾 in-context learning），再用 advantage-weighted regression 优化。**直接适用**：MemoryGym 中 write 决策到 question 回答之间的时序 gap 是经典 credit assignment 问题。

#### F150 — Agent-R1：端到端多 Turn Agent RL 框架（审计线程前沿搜索 V27/A318）⭐⭐

模块化 MDP 建模 + GRPO 在 multi-hop QA 上最优。系统性框架可与 MemoryEnv 直接组合。

#### F151 — VerlTool：VeRL 扩展的多模态工具 RL 框架（审计线程前沿搜索 V27/A318）⭐⭐

统一多工具管理 + 异步 rollout。与 MemoryGym 的 verl adapter 架构兼容。TIGER-AI-Lab 出品。

#### F152 — MemBench：综合 Agent 记忆评测（审计线程前沿搜索 V27/A318）⭐⭐

评测记忆有效性/效率/容量，事实+反思记忆两层。新竞品，但无预算压力、无变更追踪、无 RL 训练环境。MemoryGym 差异化仍然成立。

#### F153 — Evo-Memory：自进化记忆的流式评测（审计线程前沿搜索 V27/A318）⭐⭐

UIUC+DeepMind。流式 benchmark 要求 agent 在交互中演化记忆。10+ 记忆模块评测。补充 MemoryGym 的 test-time learning 维度。

#### F154 — Off-Policy GRPO 理论分析（审计线程前沿搜索 V27/A318）⭐

GRPO 在 on-policy/off-policy 下的理论保证。off-policy + clipped surrogate 可用 replay buffer 提升训练效率。

#### F155 — M-GRPO：分层多 Agent GRPO 训练（审计线程前沿搜索 V28/A324）⭐

**发现**：M-GRPO（arXiv 2511.13288，Nov 2025）为垂直 multi-agent 系统设计分层 GRPO——main agent（planner）和 sub-agents（tool executors）各自计算 group-relative advantage，通过 trajectory-alignment 方案生成固定 batch。去耦训练管线（不同 server 上运行不同 agent）。GAIA、XBench-DeepSearch 上超越单 agent GRPO 和冻结 sub-agent GRPO。

**影响**：MemoryGym 当前是单 agent，但 Memory-R1(F79) 用了 dual-agent 方案。如果未来拆分为 Memory Manager + Answer Agent，M-GRPO 的分层 advantage 计算是更系统的参考。中期参考。

#### F156 — MRAgent：Graph Memory + Active Reconstruction（ICLR 2026 Workshop MemAgents）⭐

**发现**：MRAgent（ICLR 2026 Workshop，Mar 2026）提出 "memory is reconstructed, not retrieved"——用 Cue-Tag-Content 关联图表示记忆，LLM 在推理过程中动态探索/修剪检索路径（而非固定 retrieve-then-reason）。避免组合爆炸的同时适应推理上下文。

**影响**：对 MemoryGym 后端设计有启发——当前 ChromaDB/MarkdownBackend 是静态检索。如果训练出的模型能动态重构记忆检索路径，可能在推理轴上有提升。低优先级但方向新颖。

#### F157 — ICLR 2026 MemAgents Workshop（审计线程前沿搜索 V28/A324）⭐⭐⭐

**发现**：ICLR 2026 专门设立 "MemAgents: Memory for LLM-Based Agentic Systems" Workshop（April 27, Rio de Janeiro，hybrid）。接收 full(9p)/short(4p)/tiny(2p) papers。涵盖：episodic/semantic memory、working memory、RAG、context management、temporal credit assignment。投稿截止已过（Feb 13, 2026）。

**影响**：**极高战略价值**。
1. MemoryGym 论文的理想投稿目标（如果 NeurIPS 2025 来不及或想增加曝光）
2. 确认 agent memory 已成为 top venue 认可的独立研究方向
3. Workshop 论文和 poster 将是最直接的竞品情报来源
4. MemoryGym 应在 workshop 发布后跟进所有 accepted papers

#### F158 — RLFactory：veRL 多轮工具 RL 即插即用框架（审计线程前沿搜索 V29/A331）⭐⭐

**发现**：RLFactory（arXiv 2509.06980，Aug 2025）基于 veRL + Qwen-Agent + MCP 构建多轮工具调用 RL 框架。核心设计：(1) asyncio 异步工具调用；(2) 工具调用与训练模块解耦（减少环境配置成本）；(3) 多样化 reward 计算（rule-based / model judgment / tool verification）。Qwen3-4B 在 NQ 数据集上达 0.486，超越更大模型。训练吞吐量提升 6.8x。

**影响**：MemoryGym 的 veRL adapter 可参考 RLFactory 的异步工具调用和解耦架构。特别是 6.8x 吞吐量提升的工程技巧值得借鉴。

#### F159 — MemGen：生成式潜在记忆（ICLR 2026 Workshop MemAgents）⭐

**发现**：MemGen（arXiv 2509.24704，Sep 2025）提出动态生成式记忆框架，agent 自发演化出 planning memory / procedural memory / working memory 等人类认知记忆模式。在 8 个 benchmark 上超越 ExpeL/AWM 38.22%，超越 GRPO 13.44%。已被 MemAgents Workshop 接收。

**影响**：MemGen 的生成式记忆与 MemoryGym 的外部存储记忆是互补方向。MemGen 超越 GRPO 的数据点表明记忆专用训练方法优于通用 RL。

#### F160 — Tool-R1：样本高效工具 RL（审计线程前沿搜索 V29/A331）⭐

**发现**：Tool-R1（arXiv 2509.12867，Sep 2025）用 1,300 样本（MAT Agent 的 7%）+ GRPO 训练 Qwen2.5-7B/14B 做通用工具调用。Qwen2.5-7B accuracy 从 10.3%→19.4%。在 GAIA benchmark 上 Qwen2.5-14B 达 26.67%（开源最高）。生成可执行 Python 代码，跨步变量共享。

**影响**：证明 GRPO 在工具 RL 中的样本效率。MemoryGym 训练可参考其 outcome-based reward 设计（LLM judge + code execution success 组合）。

**建议**：论文线程应关注此 workshop——即使投稿截止已过，workshop 的 accepted papers（预计 4 月初公布）将是最密集的竞品分析来源。同时调整论文 related work 引用 workshop 中的代表性工作。

#### F161 — Rewarding the Unlikely：GRPO 分布锐化修复（审计线程前沿搜索 V30/A335）⭐⭐

**发现**：arXiv 2506.02355（CMU, Jun 2025）。揭示 GRPO 的"退化排名偏差"——高概率轨迹被强化，低概率但正确的轨迹被忽略。结果是"分布锐化"而非真正学习新能力。提出 unlikeliness reward 显式鼓励强化罕见正确解，pass@N 在大范围 N 上超越标准 GRPO。

**影响**：与 F17（DAPO Clip-Higher）互补。如果 GRPO v3 出现策略多样性不足（所有 group 样本生成相似轨迹），unlikeliness reward 可以改善。

**建议**：GRPO v3 观察 group 样本多样性指标。如果多样性下降，考虑引入 unlikeliness reward。

#### F162 — ToolBrain：工具 RL 工程框架（审计线程前沿搜索 V30/A335）⭐

**发现**：arXiv 2510.00023（Sep 2025）。支持 GRPO/DPO/SFT 的工具使用 RL 框架。LLM-as-judge reward、QLoRA via Unsloth、知识蒸馏、自动任务生成。CodeAct agent +30% 改进。

**影响**：工程参考——框架设计（非方法创新）。MemoryGym 的训练模块已有类似功能。

#### F163 — Memory Management 实证研究（审计线程前沿搜索 V30/A335）⭐

**发现**：arXiv 2505.16067（May 2025）。实证分析 memory management 如何影响 LLM agent 长期性能。发现"错误传播"和"经验重放偏差"两个关键问题——劣质记忆 compound over time。

**影响**：验证 MemoryGym 的核心假设——记忆质量（而非数量）决定 agent 性能。论文可引用此研究支撑"信息过载 + 预算限制"的设计动机。

#### F164 — BCAS：Budget-Constrained Agentic Search（审计线程前沿搜索 V31/A345）⭐⭐

**发现**：arXiv:2603.08877（Mar 2026）。6 个 LLM × 3 个 QA benchmark 上系统研究预算约束对 agentic search 的影响。直接验证 MemoryGym 核心假设。

**影响**：论文应引用。预算约束 + 决策质量的关系已有外部实证支撑。

#### F165 — Letta Context-Bench：Agentic Context Engineering（审计线程前沿搜索 V31/A345）⭐⭐

**发现**：Letta 发布 Context-Bench，filesystem 存储 74% on LoCoMo，超过专用记忆工具。论点："agentic context engineering"——agent 自主决定加载什么上下文。

**影响**：挑战复杂记忆工具的必要性。MemoryGym 测 what-to-store（上游决策），Context-Bench 测 what-to-load（下游检索）。互补而非竞争。

#### F166 — Memory in the Age of AI Agents 综述（审计线程前沿搜索 V31/A345）⭐⭐⭐

**发现**：arXiv:2512.13564。清华 C3I 团队系统综述。涵盖 benchmark 列表、开源框架、前沿方向（记忆自动化、RL 集成、多模态、可信度）。

**影响**：论文 related work 应引用。MemoryGym 在综述的 benchmark 分类中独占 budget+update+anti-gaming+RL 四合一位置。

#### F167 — verl-agent 官方支持 GiGPO（审计线程前沿搜索 V31/A345）⭐⭐

**发现**：verl-agent（veRL 扩展）现已支持 GRPO/PPO/DAPO/GSPO/RLOO/GiGPO。GitHub: langfengQ/verl-agent。

**影响**：MemoryGym 的 verl adapter 应评估迁移到 verl-agent。GiGPO 的 step-level credit assignment 对记忆任务特别有价值。

#### F168 — RetroAgent：Dual Intrinsic Feedback 驱动记忆更新（审计线程前沿搜索 V32/A349）⭐⭐⭐

**发现**：RetroAgent（arXiv:2603.08561）实现 retrospective + introspective 双重内在反馈机制，通过 SimUtil-UCB 记忆缓冲区产生数值信号和语言反馈。ALFWorld +18.3%, WebShop +15.4%，超过 GRPO 训练的 agent。

**影响**：直接解决 MemoryGym 的 maintenance 瓶颈——模型收到修正信息但不执行 Edit 的根因可能是缺乏"回顾"机制。双重反馈可作为 shaped reward 的设计参考。

#### F169 — OpenClaw-RL：全异步 Agent RL 训练框架（审计线程前沿搜索 V32/A349）⭐⭐⭐

**发现**：OpenClaw-RL（arXiv:2603.10165）全异步 RL 框架，GRPO binary rewards + On-Policy Distillation (OPD) 产生 token 级优势信号，支持 terminal/GUI/SWE/tool-call agents。与 OpenClaw 兼容。

**影响**：MemoryGym 使用 OpenClaw 兼容接口（Write/Edit/Read/memory_search），OpenClaw-RL 可能直接适配。异步架构解决我们的 episode 时长瓶颈（F69：单 episode 30-40 分钟）。

#### F170 — CogMem：三层认知记忆架构（审计线程前沿搜索 V32/A349）⭐⭐

**发现**：CogMem（arXiv:2512.14118）提出 LTM consolidation + Direct Access session memory + Focus of Attention 三层架构，TurnBench-MS 0.93 准确率（vs 0.76 baseline）。

**影响**：MemoryGym 当前只测试单层记忆后端（ChromaDB / Markdown）。多层架构是自然的训练目标——agent 学会分层存储可能提升 breadth+efficiency。

#### F171 — TopoCurate：拓扑感知工具 RL 数据筛选（审计线程前沿搜索 V33/A354）⭐⭐

**发现**：TopoCurate（arXiv:2603.01714）将多次 rollout 投影到语义商拓扑，捕捉工具调用如何驱动成功/失败分歧。SFT +4.2%, RL +6.9%（BFCLv3 + Tau2）。

**影响**：拓扑感知数据筛选可提升 MemoryGym SFT 数据质量——过滤掉工具调用模式无法区分好坏的低信息量轨迹。

#### F172 — ActMem/ActMemEval：因果图记忆推理基准（审计线程前沿搜索 V33/A354）⭐ — 竞品

**发现**：ActMem（arXiv:2603.00026）将对话历史转化为因果/语义图 + 反事实推理。ActMemEval 聚焦逻辑驱动记忆场景。

**影响**：新竞品，但关注对话记忆而非信息过载+预算+变更追踪。MemoryGym 差异化仍然成立。

#### F173 — PlugMem：任务无关插件记忆模块（审计线程前沿搜索 V33/A354）⭐

**发现**：PlugMem（arXiv:2603.03296）认知科学启发的知识中心记忆图，跨 3 个异构基准不变。

**影响**：可作为 MemoryGym 第三方记忆后端候选。其"任务无关"声称可用 MemoryGym 的多模板设置压力测试。

#### F174 — env.py 审计发现两个训练 bug（审计线程代码审计 A356）⭐⭐

**发现 1（HIGH）**：`MemoryEnv.step()` 中 `_stored_entity_names` 仅在 `reward_mode="shaped"` 分支更新（env.py:652）。`reward_mode="binary"` 时写入实体不更新跟踪集，导致 `get_verifiable_reward()` 计算 stored_count=0，maintenance 轴永远为 0。

**发现 2（MEDIUM）**：`MemoryEnv.__init__` 默认 `eval_salt=0`（env.py:401），但所有 TIERS 使用 `eval_salt=1`。无 tier 参数时训练/评测问题集不同，可能导致分布偏移。

**建议**：
1. 在 step() 的 Write 处理中，无论 reward_mode 都更新 `_stored_entity_names`
2. 将 eval_salt 默认值改为 1，或从 tier 中继承

#### F175 — BATS：Budget-Aware Tool-Use Scaling（审计线程前沿搜索 V34/A361）⭐⭐

[arXiv:2511.17006] Budget Tracker 持续追踪 tool-call 预算使用量，agent 的 planning/tool-use/verification 策略随预算动态调整。核心洞见：**tool-call budget 比 token budget 更适合约束 agent**——直接对应获取外部知识的能力。MemoryGym 的 write budget 即此类 budget constraint。可参考 BATS 的 Budget Tracker 设计改进 MemoryEnv 中的 budget 信号传递。

#### F176 — SE-Search：Self-Evolving Search Agent + Dense Reward（审计线程前沿搜索 V34/A361）⭐

[arXiv:2603.03293] 三组件：memory purification（清理无关记忆）、atomic query training、dense reward（细粒度 reward 信号）。核心方向与 MemoryGym 的 shaped reward 对齐——用 dense reward 替代 sparse 终端 reward。相关性中等，更偏搜索场景。

---

#### F177 — AMA-Bench：长时程 agentic 记忆基准（审计线程前沿搜索 V35/A374）⭐ — 竞品

[arXiv:2602.22769, Feb 2026] 评估 LLM agent 在真实 agentic 场景的长时程记忆。与现有 dialogue-centric 基准不同，AMA-Bench 关注 machine-generated 交互流（agent-environment interaction）。提出 AMA-Agent（因果图 + tool-augmented retrieval），57.22% 准确率超基线 11.16pp。**与 MemoryGym 定位互补**：AMA-Bench 测 retrieval 不测 storage triage，MemoryGym 测完整链条（信息摄入→存储决策→检索→更新→推理）。论文中可引用作对比。

#### F178 — MIRA：Memory-Integrated RL Agent（审计线程前沿搜索 V35/A374）⭐⭐

[arXiv:2602.17930, ICLR 2026] 将 LLM 指导 amortize 到持久化 memory graph 中，设计 utility signal 软调整 advantage estimation。训练推进后 utility 自然衰减，保留标准收敛保证。**对 MemoryGym 训练的启示**：(1) memory graph 作为训练中间产物可提供 dense reward signal；(2) utility decay 可避免 LLM supervisor 过拟合；(3) 在 sparse reward 环境（如 MemoryGym）尤其有效。

#### F179 — MemRL：Runtime RL on Episodic Memory（审计线程前沿搜索 V35/A374）⭐

[arXiv:2601.03192, Jan 2026] Self-evolving agents，运行时 RL + episodic memory。agent 在任务执行中积累 episode 经验，用 RL 优化 memory 的读写策略。方向与 MemoryGym 的 MemoryEnv 高度一致——都把记忆操作作为可学习的 action space。

#### F180 — AMemGym v2：Interactive Memory Evaluation（审计线程前沿搜索 V35/A374）⭐ — 竞品

[arXiv:2603.01966, Mar 2026] AMemGym 更新版，structured data sampling 预定义用户画像和状态演进轨迹，支持 on-policy 评估和优化。**与 MemoryGym 比较**：AMemGym 聚焦对话式个性化记忆，MemoryGym 聚焦信息过载+预算约束+更新追踪。互为不同维度的竞品。

#### F181 — Anatomy of Agentic Memory：分类法+系统局限分析（审计线程前沿搜索 V35/A374）

[arXiv:2602.19320, Feb 2026] Survey 性质，对 agentic memory 的评估和系统局限进行分类和实证分析。可作为论文 related work 引用来源。

#### F182 — A-MEM：Zettelkasten-inspired Agentic Memory（审计线程前沿搜索 V36/A384）⭐⭐ — 记忆组织

[arXiv:2502.12110, NeurIPS 2025] Xu et al. (Rutgers). LLM 自主组织记忆为互联知识网络，动态索引+链接+记忆进化。新记忆到达时自动更新关联旧记忆。6 个基础模型上超越 SOTA。直接对应 MemoryGym 的 breadth+maintenance 两轴，验证存储组织策略的重要性。

#### F183 — Agent-R1：端到端多轮 RL 训练 LLM Agents（审计线程前沿搜索 V36/A384）⭐⭐ — 训练框架

[arXiv:2511.14460, Nov 2025] Xi et al. (Renmin Univ). 开源模块化框架，支持 PPO/GRPO/REINFORCE++。多轮交互式 agent 的 MDP 形式化。GRPO 训练的 agent 超越商业模型。与 MemoryGym 的 GRPO v3 训练 pipeline 高度互补，可作为训练后端或论文对比。

#### F184 — Agent-Omit：自适应思维和观察省略的 Agentic RL（审计线程前沿搜索 V36/A384）⭐ — 效率训练

[arXiv:2602.04284, Feb 2026] Zhong et al. (HKUST). 训练 LLM agent 自适应跳过冗余思维和观察（冷启动 SFT + 双采样 RL）。Agent-Omit-8B 匹配 7 个前沿模型但更高效。直接对应 MemoryGym 效率轴（20% 权重），自适应省略概念映射到预算约束下的存储决策。

#### F185 — AgentGym-RL：ScalingInter-RL 多轮长期决策（审计线程前沿搜索 V36/A384）⭐ — 训练课程

[arXiv:2509.08755, ICLR 2026 under review] Xi et al. (Renmin Univ). 统一多轮 RL 框架 + ScalingInter-RL 课程（从利用到探索）。解耦架构（环境/agent/训练模块），支持 27 种任务。Qwen2.5-7B 超越 o3/Gemini-2.5-Pro。课程学习方法可解决 MemoryGym 训练中记忆操作的稀疏延迟奖励问题。

#### F186 — MemAgents Workshop @ ICLR 2026（审计线程前沿搜索 V36/A384）— 生态信号

[ICLR 2026 Workshop, Apr 27, Rio de Janeiro] "Memory for LLM-Based Agentic Systems" 专题研讨会，覆盖架构/RL/评估/神经科学。MemoryGym 作为评测+训练平台与此 workshop 主题高度契合。接收论文应关注。

#### F187 — Memo：Memory-Efficient Embodied Agents via RL（审计线程前沿搜索 V37/A391）⭐ — 架构参考

[arXiv:2510.19732, NeurIPS 2025 Spotlight] 基于 transformer 的 RL 架构，通过周期性 summarization tokens 压缩历史经验到记忆缓冲区。在 grid-world 和室内导航任务中超越长上下文 baseline，且推理时泛化到更长上下文。与 MemoryGym 差异：Memo 面向 embodied/visual 任务，MemoryGym 面向文本记忆管理。summarization token 思路可能启发 MemoryEnv 的 observation 压缩。

#### F188 — CloneMem：AI Clone 长期记忆评测（审计线程前沿搜索 V37/A391）⭐ — 竞品

[arXiv:2601.07023, Jan 2026] 评测 AI Clone 长期记忆，输入为日记/社交媒体/邮件等非对话数字痕迹（1-3 年跨度）。关注个人经历追踪、情感变化、观点演变。与 MemoryGym 差异：CloneMem 面向个性化/情感理解，MemoryGym 面向结构化实体记忆管理+预算约束。互补而非竞争。

#### F189 — RealMem：真实项目场景记忆评测（审计线程前沿搜索 V37/A391）⭐⭐ — 竞品

[arXiv:2601.06966, Jan 2026] 首个基于真实项目场景的记忆评测，2000+ 跨会话对话 × 11 场景。关注长期项目状态管理和动态上下文依赖。发现现有记忆系统在项目状态追踪上严重不足。与 MemoryGym 比较：RealMem 测跨会话项目记忆，MemoryGym 测单会话内信息过载下的存储决策。RealMem 缺少预算约束和 RL 训练环境。论文 related work 应引用。

#### F190 — KnowMe-Bench：个人理解评测（审计线程前沿搜索 V37/A391）— 间接相关

[arXiv:2601.04745, Jan 2026] 将叙事重构为闪回感知的时间锚定流，评测事实回忆、主观状态归因、原则级推理。RAG 系统主要提升事实准确度，时间推理和高阶推断仍有错误。与 MemoryGym 关系弱（面向个人理解而非实体记忆管理），但时间锚定评测方法可参考。

#### F191 — SUPO：Summarization-augmented Policy Optimization（审计线程前沿搜索 V38/A396）⭐⭐ — 训练方法

[arXiv:2510.06727, ICLR 2026 under review] ByteDance/Stanford/CMU。核心：多轮 RL 中周期性 LLM 摘要压缩工具调用历史，保持紧凑上下文的同时训练 agent 超越固定上下文窗口限制。形式化 summarization-augmented MDP，推导端到端策略梯度同时优化工具使用和摘要策略。BrowseComp-Plus +14.0% 绝对精度，60% 准确率（基线远低）。**与 MemoryGym 关系**：MemoryEnv 训练中 context overflow 是真实瓶颈（standard tier 60 实体 × narrative 文档），SUPO 的摘要压缩 + 端到端训练方法可直接用于解决 MemoryEnv 长 episode 训练问题。

#### F192 — MemoryRewardBench：奖励模型记忆管理评测（审计线程前沿搜索 V39/A401）⭐⭐ — 评测/训练

[arXiv:2601.11969, Jan 2026] 首个专门评测奖励模型对长期记忆管理质量判断的 benchmark。10 种设置，最长 128K context。核心发现：即使 Llama 3.3-70B 在 128K+ 也会退化；语义标签（A-Mem 风格）可提升 RM 准确率 10-15%。**与 MemoryGym 关系**：RL 训练中奖励信号质量是关键，MRB 的发现（语义标签提升 RM 准确率）可改进 MemoryEnv 的 reward shaping。

#### F193 — Hindsight：具有事后反思的 Agent 记忆系统（审计线程前沿搜索 V39/A401）⭐ — 系统

[arXiv:2512.12818, Dec 2025] Agent 记忆系统，通过事后反思机制学习和优化记忆性能。LongMemEval 91.4%、LoCoMo 89.6%。非 benchmark 而是系统方案，但其高分表明当前 benchmark 区分度可能不足。**与 MemoryGym 关系**：验证 MemoryGym 设计方向——budget 约束 + correction tracking 提供了 Hindsight 类系统无法绕过的挑战维度。

#### F194 — LongMemEval：长期交互记忆评测（审计线程前沿搜索 V39/A401）⭐ — 竞品 benchmark

[arXiv:2410.10813, ICLR 2025] 500 curated Qs，5 competencies（信息抽取、多会话推理、时间推理、知识更新、abstention），115K-1.5M token。GPT-4o 也有 30-60% 性能下降。**与 MemoryGym 关系**：竞品，但无 budget 约束、无 4 轴评分、无 world template 结构。论文 related work 应引用。

#### F195 — StructMemEval：结构化记忆组织评测（审计线程前沿搜索 V40/A411）⭐ — 竞品 benchmark

[arXiv:2602.11243, Feb 2026] 首个测试 LLM 结构化记忆组织能力的 benchmark（transaction ledgers, to-do lists, trees）。发现 LLM 在无显式提示时难以正确组织记忆结构；两种失败模式：无组织 vs 虚构组织。**与 MemoryGym 关系**：LOW 风险。StructMemEval 仅测结构类型选择（窄焦点），MemoryGym 测完整 7 阶段链条（信息摄入→存储决策→组织→检索→变更→推理→元认知）。正交而非竞争。

#### F196 — MemoryBench：持续学习记忆评测（审计线程前沿搜索 V41/A427）⭐ — 竞品 benchmark

[arXiv:2510.17281, Oct 2025] 评测 LLM 系统从用户反馈中持续学习的记忆能力。区分 declarative vs procedural 知识，多域多语种。发现现有记忆系统无法有效利用 procedural 知识。**与 MemoryGym 关系**：LOW 风险。MemoryBench 测跨 session 持续学习（用户反馈驱动），MemoryGym 测单 session 信息过载管理（budget + update tracking）。互补定位。论文 related work 可引用。

#### F197 — MemOS：AI 记忆操作系统 + OpenClaw 插件（审计线程前沿搜索 V41/A427）⭐⭐ — 基础设施

[arXiv:2507.03724, Jul 2025; v2.0 Dec 2025; OpenClaw Plugin Mar 2026] MemTensor 开源记忆 OS。核心抽象 MemCube（统一 plaintext/activation/parameter 记忆），三层架构（API/调度/存储）。v2.0 支持多模态记忆、工具记忆、企业优化。**与 MemoryGym 关系**：**生态机遇**。MemOS OpenClaw 插件（Mar 8, 2026）与 MemoryGym 的 OpenClaw 兼容接口天然对接——MemOS 可作为 MemoryGym 的第三个后端。中期关注。

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

