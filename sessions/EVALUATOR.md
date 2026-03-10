# EVALUATOR — 评测线程

> 启动方式：`/loop 30m 你是评测线程，读 sessions/EVALUATOR.md 执行下一个评测任务`
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
- 不要修改 sessions/EXECUTOR.md 或 CLAUDE.md
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

### 批次 9 — mem0 后端首测

Phase 48 完善了 mem0 集成，但从未用 mem0 跑过真实评测。这是首次 mem0 后端验证。

mem0 现在自动使用 CHUTES_API_KEY + Qwen3-235B 做 fact extraction（无需 OPENAI_API_KEY）。

**注意**：mem0 分数与 ChromaDB **不可直接比较**（存储粒度不同：mem0 拆分 facts，ChromaDB 存原文）。目标是验证 mem0 后端能跑通，不是对比分数。

```bash
# 冒烟测试：单个 seed + 模板，确认管线跑通
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template company --backend mem0

# 如果冒烟通过，再跑 2 个模板对比
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template research --backend mem0
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template city --backend mem0
```

**记录要点**：
- mem0 store() 是否抛 RuntimeError（无 facts 提取）？
- 搜索精度如何？（mem0 有自己的 LLM-based search）
- 与 ChromaDB 同模型/同 seed/同模板的分数对比（仅供参考）

## 已完成

### 批次 8 — multi tier 多会话首测（完成）

Phase 42 multi tier（3 sessions）。Kimi-K2.5 seed 0。

| 模型 | 模板 | Tier | Composite | Breadth | Maint. | Reasoning | Efficiency | Writes |
|------|------|------|-----------|---------|--------|-----------|------------|--------|
| Kimi-K2.5 | company | multi | **8%** | 22% | 0% | 0% | 7% | 29/30 |
| Kimi-K2.5 | research | multi | **20%** | 0% | 60% | 11% | — | 30/30 |
| Kimi-K2.5 | city | multi | **31%** | 20% | 90% | 0% | — | 28/30 |

**注意**：company multi 分数远低于 research/city，主要因为 maintenance=0%（3 sessions 后完全丢失更新信息）。

### 批次 7 — hard tier（完成）

| 模型 | 模板 | Tier | Composite | Breadth | Maint. | Reasoning | Efficiency | Writes |
|------|------|------|-----------|---------|--------|-----------|------------|--------|
| Kimi-K2.5 | company | hard | **24%** | 18% | 23% | 23% | 33% | 27/30 |

120 entities, 40 questions, 10 corrections。存储 25/120 (21%)。强项：multi_constraint=100%, enum_filter=100%, comparison=100%。弱项：temporal=0%, synthesis=0%。

### 批次 6 — standard tier（完成）

| 模型 | 模板 | Tier | Composite | Breadth | Maint. | Reasoning | Efficiency | Writes |
|------|------|------|-----------|---------|--------|-----------|------------|--------|
| Kimi-K2.5 | company | standard | **12%** | 11% | 31% | 0% | 7% | 28/30 |

60 entities, 20 questions, 5 corrections。存储 28/60 (47%)。Reasoning=0% 全部答错。

**跨 tier 对比（Kimi-K2.5 company s0）**：

| Tier | Entities | Questions | Composite | Breadth | Maint | Reasoning |
|------|----------|-----------|-----------|---------|-------|-----------|
| lite (B1) | 40 | 15 | 30% | 17% | 20% | 33% |
| standard (B6) | 60 | 20 | 12% | 11% | 31% | 0% |
| hard (B7) | 120 | 40 | 24% | 18% | 23% | 23% |
| multi (B8) | 60 | 20 | 8% | 22% | 0% | 0% |

**发现**：hard tier 反而比 standard 高，可能因为 40 题覆盖更多 competency 类型。multi tier 最低（8%），session break 严重影响记忆连续性。

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
| GLM-5 | movie | 0 | **0%** | 0% | 0% | 0% | 50% | 0/5 |

**GLM-5 分析**：company 26/30 writes 存了 32 个实体，movie 25/30 writes 存了 24 个实体，但搜索全部返回空 — 模型无法有效使用 search tool。非系统 bug。

### 批次 5 — Phase 38 对比验证（完成）

Phase 38 keyword fallback 效果对比（Kimi-K2.5 seed 0 重跑）：

| 模型 | 模板 | Seed | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections |
|------|------|------|-----------|---------|--------|-----------|------------|-------------|
| Kimi-K2.5 | company | 0 | **4%** | 11% | 0% | 0% | 100% | 2/5 |
| Kimi-K2.5 | research | 0 | **25%** | 0% | 33% | 11% | 100% | 3/5 |
| Kimi-K2.5 | city | 0 | **26%** | 0% | 97% | 0% | 100% | — |
| Kimi-K2.5 | hospital | 0 | **35%** | 11% | 60% | 0% | 100% | 2/5 |
| Kimi-K2.5 | sport | 0 | **5%** | 0% | 18% | 0% | 100% | — |
| Kimi-K2.5 | movie | 0 | **9%** | 12% | 0% | 17% | 100% | — |

**对比分析**（批次 1 vs 批次 5，均为 Kimi s0）：

| 模板 | B1 Composite | B5 Composite | 变化 | B1 Maint | B5 Maint | 备注 |
|------|-------------|-------------|------|---------|---------|------|
| company | 30% | 4% | ↓26% | 20% | 0% | 大幅下降 |
| research | 15% | 25% | ↑10% | 33% | 33% | 改善 |
| city | 20% | 26% | ↑6% | 31% | 97% | 维护大幅提升 |
| hospital | 17% | 35% | ↑18% | 26% | 60% | 显著改善 |
| sport | 10% | 5% | ↓5% | 0% | 18% | 略有波动 |
| movie | 21% | 9% | ↓12% | 62% | 0% | 下降 |

**结论**：Phase 38 效果不一致。hospital/city/research 改善，company/movie 下降。注意：同 seed 不同时间跑分数差异可能源于 API 非确定性（LLM 温度），而非 keyword fallback 本身。
