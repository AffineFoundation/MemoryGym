# EVAL_QUEUE (v2 — Phase 16 Enhanced Templates)

> 评测专用 session 协议。每次 `/loop` 读此文件，执行队列中的下一个评测任务。
>
> **重要**: v1 数据（10 属性模板）已归档到 `eval/archive_v1/`。以下所有批次基于 Phase 16 增强模板（22-23 属性，6 种 dtype，20 种推理题型）。

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

### 批次 5 — standard tier

```bash
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template company --tier standard
```

### 批次 6 — hard tier

```bash
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template company --tier hard
```

## 已完成

（v2 评测尚未开始）
