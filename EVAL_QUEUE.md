# EVAL_QUEUE

> 评测专用 session 协议。每次 `/loop` 读此文件，执行队列中的下一个评测任务。

## 工作流程

```
1. 读本文件，找到「当前任务」
2. 执行评测命令（一次只跑一个任务）
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

company, research, city, hospital, sport, movie（共 6 个）

---

## 当前任务

### 批次 2 — mem0 后端对比

用 Kimi-K2.5 跑 company 模板的 mem0 后端，与现有 chromadb 结果对比：

```bash
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template company --backend mem0
```

### 批次 3 — standard tier 验证

至少 1 个模型跑 standard tier（60 entities, 20 questions, budget=30）：

> ⚠️ 开发 session 已启动 company seed=0 standard tier eval，检查 `eval/moonshotai_Kimi-K2.5-TEE_company_s0.json` 是否已更新。如果已有 standard tier 结果则跳过。

```bash
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template company --tier standard
```

### 批次 4 — 核心模型多 seed 稳定性（改进后提示）

Kimi-K2.5 company 模板用改进后的 correction 提示重跑。seed 0 已有新数据（45%），补充 seed 1-4：

```bash
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 1 --template company
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 2 --template company
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 3 --template company
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 4 --template company
```

### 批次 5 — 多模型 movie 横评

```bash
python -m memorygym.bench --model MiniMaxAI/MiniMax-M2.5-TEE --seed 0 --template movie
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template movie
```

### 批次 6 — GLM-5 基线

新模型首测：

```bash
python -m memorygym.bench --model zai-org/GLM-5-TEE --seed 0 --template company
python -m memorygym.bench --model zai-org/GLM-5-TEE --seed 0 --template movie
```

### 批次 7 — hard tier 首测

hard tier（120 entities, 40 questions, budget=30, 压力比 4:1）目前 0 数据：

```bash
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template company --tier hard
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template company --tier hard
```

### 批次 8 — Qwen3.5-397B 补测（之前 503 作废）

3 个结果因 API 503 作废，重跑：

```bash
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template company
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 1 --template company
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 42 --template company
```

### 批次 9 — Qwen3.5-397B 全模板覆盖

当前只有 research/city/hospital 各 1 个，补齐剩余模板：

```bash
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template movie
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template sport
```

### 批次 10 — Kimi-K2.5 全模板多 seed（统计显著性）

目标：每模板至少 3 seeds，计算均值±标准差：

```bash
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 1 --template movie
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 2 --template movie
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 1 --template city
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 2 --template city
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 1 --template research
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 2 --template research
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 1 --template hospital
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 2 --template hospital
```

### 批次 11 — MiniMax 补测（多 seed + 缺失模板）

当前每模板仅 1 seed，补充 seed 1 + 缺失的 movie：

```bash
python -m memorygym.bench --model MiniMaxAI/MiniMax-M2.5-TEE --seed 1 --template company
python -m memorygym.bench --model MiniMaxAI/MiniMax-M2.5-TEE --seed 1 --template city
python -m memorygym.bench --model MiniMaxAI/MiniMax-M2.5-TEE --seed 1 --template research
python -m memorygym.bench --model MiniMaxAI/MiniMax-M2.5-TEE --seed 1 --template hospital
python -m memorygym.bench --model MiniMaxAI/MiniMax-M2.5-TEE --seed 1 --template sport
python -m memorygym.bench --model MiniMaxAI/MiniMax-M2.5-TEE --seed 1 --template movie
```

### 批次 12 — standard tier 多模型横评

在 standard tier 上建立可比基线：

```bash
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template company --tier standard
python -m memorygym.bench --model MiniMaxAI/MiniMax-M2.5-TEE --seed 0 --template company --tier standard
python -m memorygym.bench --model zai-org/GLM-5-TEE --seed 0 --template company --tier standard
```

### 批次 13 — hard tier 全模型

验证 hard tier 下模型能力衰减曲线：

```bash
python -m memorygym.bench --model MiniMaxAI/MiniMax-M2.5-TEE --seed 0 --template company --tier hard
python -m memorygym.bench --model zai-org/GLM-5-TEE --seed 0 --template company --tier hard
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template research --tier hard
```

## 已完成

### 批次 1 — 补充模板覆盖（movie + sport）✅

由开发 session 完成：

| 模型 | 模板 | Seed | Composite | Breadth | Maint. | Reasoning | Abstention |
|------|------|------|-----------|---------|--------|-----------|------------|
| Kimi-K2.5 | movie | 0 | **55%** | 56% | 25% | 60% | 100% |
| Kimi-K2.5 | sport | 0 | **30%** | 40% | 0% | 0% | 100% |
| Kimi-K2.5 | sport | 1 | **40%** | 12% | 33% | 50% | 100% |
