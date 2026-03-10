# EVAL_QUEUE — 评测线程

> 启动方式：`/loop 30m 你是评测线程，读 EVAL_QUEUE.md 执行下一个评测任务`
>
> 评测专用线程。只跑模型评测，不改代码。
>
> **重要**: v1 数据（10 属性模板）已归档到 `eval/archive_v1/`。以下所有批次基于 Phase 16 增强模板（22-23 属性，6 种 dtype，18 种推理题型）。

## 工作流程

```
1. 读本文件，找到「当前任务」
2. 执行评测命令
   - 不同模型的评测可以并发执行（它们使用独立的 API 和独立的 eval 文件）
   - 同一模型的不同 seed/template 也可并发
   - 充分利用并发加速数据积累
3. 检查结果：success: true → 有效，否则按故障处理
4. 记录结果到「已完成」，更新 ROADMAP.md §3 数据表
5. 提升下一待办为当前任务
6. 队列空 → 停止，等待新任务写入
```

## 评测规范

**命令模板**：
```bash
python -m memorygym.bench --model <MODEL> --seed <SEED> --template <TEMPLATE> [--tier lite] [--backend chromadb]
```

**故障处理**：
- API 503/429/timeout → 结果文件重命名为 `*.503_error.json`，不计入数据表
- 只有 `"success": true` 的结果才是有效数据
- 连续 3 次 API 故障 → 跳过该任务，标记为阻塞，换下一个

**结果记录**：
- eval JSON 自动保存到 `eval/` 目录
- 每完成一个任务，将分数追加到本文件的「已完成」区域
- 每完成一批同类任务（如同模型多 seed），汇总均值±标准差到 ROADMAP.md §3

**不要做的事**：
- 不要修改代码（代码变更由开发 session 负责）
- 不要修改 AUTOPILOT.md 或 CLAUDE.md
- 不要跑测试（pytest）
- 不要提交代码（git commit）

## 可用模型

按评测价值排序（Chutes 平台，base_url 不需要指定，代码自动处理）：
- `Qwen/Qwen3.5-397B-A17B-TEE` — 最强开源
- `moonshotai/Kimi-K2.5-TEE` — 数据最多的模型
- `MiniMaxAI/MiniMax-M2.5-TEE`
- `zai-org/GLM-5-TEE`

## 可用模板

company, research, city, hospital, sport, movie（共 6 个，每个 22-23 属性）

---

## 当前任务

### 批次 1 — 冒烟测试（v2 首测）

验证增强后的模板 agent 能正常处理新 dtype（text/enum/list_float/date）：

```bash
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template company
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template research
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template city
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template hospital
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template sport
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template movie
```

### 批次 2 — Kimi-K2.5 新基线（多 seed 统计）

每模板 3 seeds 建立均值±标准差：

```bash
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 1 --template company
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 2 --template company
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 1 --template research
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 2 --template research
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 1 --template city
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 2 --template city
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 1 --template hospital
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 2 --template hospital
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 1 --template sport
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 2 --template sport
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 1 --template movie
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 2 --template movie
```

### 批次 3 — Qwen3.5-397B 横评

```bash
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template company
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template research
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template city
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template hospital
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template sport
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template movie
```

### 批次 4 — MiniMax + GLM-5 基线

```bash
python -m memorygym.bench --model MiniMaxAI/MiniMax-M2.5-TEE --seed 0 --template company
python -m memorygym.bench --model MiniMaxAI/MiniMax-M2.5-TEE --seed 0 --template movie
python -m memorygym.bench --model zai-org/GLM-5-TEE --seed 0 --template company
python -m memorygym.bench --model zai-org/GLM-5-TEE --seed 0 --template movie
```

### 批次 5 — Phase 38 对比验证（keyword fallback 效果）

Phase 38 加入了 ChromaDB keyword fallback。用 seed 0 重跑 6 个模板，与批次 1（pre-Phase-38）对比检索准确率。

**注意**：批次 1 的 seed 0 结果是 Phase 38 前跑的。这批用相同 seed 重跑，对比 breadth 和 composite 变化。

```bash
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template company
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template research
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template city
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template hospital
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template sport
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template movie
```

### 批次 6 — standard tier

```bash
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template company --tier standard
```

### 批次 7 — hard tier

```bash
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template company --tier hard
```

### 批次 8 — multi tier（多会话首测）

Phase 42 新增的 multi tier（3 sessions）。对比 standard tier 分数下降幅度。

```bash
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template company --tier multi
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template research --tier multi
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template city --tier multi
```

## 已完成

### 批次 1 — 冒烟测试（完成）

| 模型 | 模板 | Seed | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections |
|------|------|------|-----------|---------|--------|-----------|------------|-------------|
| Kimi-K2.5 | company | 0 | **30%** | 17% | 20% | 33% | 100% | 4/5 |
| Kimi-K2.5 | research | 0 | **15%** | 0% | 33% | 0% | 100% | 3/5 |
| Kimi-K2.5 | city | 0 | **20%** | 33% | 31% | 0% | 100% | 2/5 |
| Kimi-K2.5 | hospital | 0 | **17%** | 11% | 26% | 20% | 100% | 2/5 |
| Kimi-K2.5 | sport | 0 | **10%** | 0% | 0% | 33% | 100% | 2/5 |
| Kimi-K2.5 | movie | 0 | **21%** | 12% | 62% | 0% | 100% | 2/3 |

### 批次 2 — Kimi-K2.5 多 seed（完成）

| 模型 | 模板 | Seed | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections |
|------|------|------|-----------|---------|--------|-----------|------------|-------------|
| Kimi-K2.5 | company | 1 | **41%** | 25% | 100% | 17% | 100% | 4/5 |
| Kimi-K2.5 | company | 2 | **15%** | 0% | 25% | 25% | 100% | 2/5 |
| Kimi-K2.5 | research | 1 | **42%** | 33% | 75% | 33% | 100% | 3/5 |
| Kimi-K2.5 | research | 2 | **34%** | 25% | 72% | 17% | 100% | 5/5 |
| Kimi-K2.5 | city | 1 | **36%** | 22% | 67% | 33% | 100% | 3/5 |
| Kimi-K2.5 | city | 2 | **0%** | 0% | 0% | 0% | 100% | 2/5 |
| Kimi-K2.5 | hospital | 1 | **0%** | 0% | 0% | 0% | 100% | 1/5 |
| Kimi-K2.5 | hospital | 2 | **14%** | 0% | 50% | 0% | 100% | 4/5 |
| Kimi-K2.5 | sport | 1 | **4%** | 12% | 0% | 0% | 100% | 2/5 |
| Kimi-K2.5 | sport | 2 | **32%** | 38% | 50% | 17% | 100% | 1/5 |
| Kimi-K2.5 | movie | 1 | **13%** | 12% | 33% | 0% | 100% | 3/5 |
| Kimi-K2.5 | movie | 2 | **31%** | 11% | 87% | 14% | 100% | 1/5 |

### 批次 3 — Qwen3.5-397B 横评（完成）

| 模型 | 模板 | Seed | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections |
|------|------|------|-----------|---------|--------|-----------|------------|-------------|
| Qwen3.5-397B | company | 0 | **40%** | 22% | 67% | 50% | 100% | 4/5 |
| Qwen3.5-397B | research | 0 | **14%** | 20% | 0% | 22% | 100% | 4/5 |
| Qwen3.5-397B | city | 0 | **0%** | 0% | 0% | 0% | 100% | 0/5 |
| Qwen3.5-397B | hospital | 0 | **19%** | 22% | 37% | 0% | 100% | 1/5 |
| Qwen3.5-397B | sport | 0 | **41%** | 22% | 100% | 20% | 100% | 2/5 |
| Qwen3.5-397B | movie | 0 | **13%** | 0% | 50% | 0% | 100% | 3/5 |

### 批次 4 — MiniMax + GLM-5 基线（完成）

| 模型 | 模板 | Seed | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections |
|------|------|------|-----------|---------|--------|-----------|------------|-------------|
| MiniMax-M2.5 | company | 0 | **13%** | 11% | 32% | 0% | 0% | 3/5 |
| MiniMax-M2.5 | movie | 0 | **4%** | 12% | 0% | 0% | 50% | 1/5 |
| GLM-5 | company | 0 | **0%** | 0% | 0% | 0% | 50% | 0/5 |

**GLM-5 分析**：26/30 writes，存了 32 个实体，但搜索全部返回空 — 模型无法有效使用 search tool。非系统 bug。
