# EVALUATOR — 评测线程

> 启动方式：`/loop 10m 你是评测线程，读 sessions/EVALUATOR.md 执行下一个评测任务`
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
- `Qwen/Qwen3.5-397B-A17B-TEE` — 最强开源，397B MoE
- `Qwen/Qwen3-235B-A22B-Instruct-2507-TEE` — 第二强
- `moonshotai/Kimi-K2.5-TEE` — 数据最多的模型
- `MiniMaxAI/MiniMax-M2.5-TEE`
- `zai-org/GLM-5-TEE`

## 可用模板

company, research, city, hospital, sport, movie, university, codebase（共 8 个，每个 21-23 属性）

---

## 当前任务

### Batch 34 — Post-Phase 112 覆盖度补全（8 模板 × 多模型）

**背景**（A213 审计）：Phase 112（correction Edit 免预算）是项目历史最高影响变更，但仅 8/123 evals 是 post-Phase 112 (v>=0.10.15)。4 个模板完全没有 post-112 数据。LEADERBOARD 排名主要反映旧版本表现。

**目标**：补全 post-Phase 112 评测覆盖，每个缺失模板至少 2 evals。

**优先级 1 — 缺失模板**（0 post-112 evals）：
```bash
# university（2 evals）
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template university
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template university

# codebase（2 evals）
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template codebase
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template codebase

# sport（2 evals）
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template sport
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template sport

# movie（2 evals）
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template movie
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template movie
```

**优先级 2 — 已有少量数据的模板补测**：
```bash
# city（仅 1 post-112, M=0%）
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 1 --template city

# research（仅 1 post-112）
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 1 --template research
```

**完成标准**：至少 8 个新 eval（优先级 1），理想 10 个（含优先级 2）。全部 success:true。

**Priority 1 结果（8/8 完成 ✅，全部 v0.10.17）**：

| Model | Template | Comp | B | M | R | E | Stored |
|-------|----------|------|---|---|---|---|--------|
| Qwen3.5 | university s0 | **46%** | 57% | 33% | 57% | 30% | 36 |
| Qwen3.5 | movie s0 | **43%** | 57% | 50% | 33% | 27% | — |
| Kimi | codebase s0 | 19% | 20% | 33% | 11% | 10% | 34 |
| Kimi | university s0 | 14% | 14% | 33% | 0% | 7% | 33 |
| Qwen3.5 | codebase s0 | 12% | 0% | 33% | 11% | 7% | 35 |
| Qwen3.5 | sport s0 | 9% | 17% | 0% | 12% | 7% | 35 |
| Kimi | sport s0 | 9% | 17% | 0% | 12% | 7% | 15 |
| Kimi | movie s0 | 0% | 0% | 0% | 0% | 0% | 33 |

**P1 摘要**：M>0% = 5/8 (63%)。Qwen3.5 university/movie 突破 40%+。Kimi movie 全零（ChromaDB 检索全部失败）。

**Priority 2 结果（2/2 完成 ✅，全部 v0.10.17）**：

| Model | Template | Comp | B | M | R | E | Stored |
|-------|----------|------|---|---|---|---|--------|
| Qwen3.5 | research s1 | **24%** | 43% | 33% | 0% | 13% | 33 |
| Kimi | city s1 | **16%** | 12% | 24% | 17% | 10% | 29 |

**Batch 34 完成 ✅（10/10 evals, all v0.10.17）**

**Phase 112 关键发现**：
- **M>0%**: 7/10 (70%) — 远超 B33 的 44%
- **新全时高分**: Qwen3.5 university 46%, Qwen3.5 movie 43%
- **Movie M=50%**: 历史首次 maintenance 超过 33%
- **Kimi movie 0%**: ChromaDB 搜索完全失败（movie 实体名高相似度问题持续）
- **Sport M=0%**: 两模型均 0%（sport corrections 搜索困难）

---

### 批次 24 — 版本偏差验证（Qwen3.5 hospital s0 重跑） ✅

**目的**：验证版本偏差假说（H1 seed 方差 vs H2 版本回归）。

**结果**（v0.10.9, Qwen3.5-397B, hospital s0）：

| 指标 | B19 (v0.10.4) | B24 (v0.10.9) | 变化 |
|------|-------------|-------------|------|
| Composite | 45% | **25%** | -20% |
| Breadth | 56% | 44% | -12% |
| Maintenance | 0% | 0% | — |
| Reasoning | 33% | 33% | — |
| Efficiency | — | 16.7% | — |
| Stored | 36 | 30 | -6 |

**结论**：**H1 成立 + 新发现 H3（LLM API 非确定性）**。
- Phases 100-106 均为训练侧或 validator 补充，不影响 hospital s0 eval 路径
- 差异来源：B19 模型 packing（36 实体/30 writes），B24 未 packing（30 实体/30 writes）
- 这是 LLM API 行为方差（温度/采样），非版本回归
- 同 seed 单次 eval 方差可达 ±20%，需 ≥3 seeds 均值才可靠

---

### 批次 23 — Qwen3.5 多 seed 扩展（稳定排名 + 弱模板诊断） ✅

**Qwen3.5 三 seed 汇总（v0.10.5-0.10.9, chromadb）**：

| 模板 | s0 | s1 | s2 | 均值 | 标准差 | B均值 | R均值 |
|------|----|----|----|----|--------|-------|-------|
| university | 28.3% | 13.2% | 16.8% | **19.4%** | ±7.9% | 42.6% | 15.1% |
| research | 22.4% | 14.9% | 18.9% | **18.7%** | ±3.8% | 39.7% | 16.7% |
| company | 24.4% | 9.9% | 10.1% | **14.8%** | ±8.4% | 21.8% | 25.1% |
| movie | 18.3% | 4.4% | 9.9% | **10.9%** | ±7.0% | 28.0% | 3.7% |

**关键发现**：

1. **方差确认**：所有模板 s0 都是最高分（18-28%），s1-2 显著下降。s0 可能存在系统性乐观偏差（s0 是旧版本 v0.10.4-0.10.5，后续版本评分更严格？需审计线程调查）
2. **Movie reasoning 确认低**：3 seeds 均值仅 3.7%（s1=0%, s2=0%, 仅 s0=11%）
3. **Company reasoning 方差极大**：s0=50%, s1=14%, s2=11%
4. **Research 最稳定**：标准差仅 ±3.8%
5. **Maintenance 全零**：12/12 eval 均 0%

**模板难度排名（3-seed 均值）**：university(19.4%) > research(18.7%) > company(14.8%) > movie(10.9%)

---

### 批次 22 — Kimi 剩余 4 模板 + Qwen3.5 多 seed 方差测量 ✅

**Kimi-K2.5 post-Phase99 结果（v0.10.8, seed 0）**：

| 模板 | Composite | Stored | Breadth | Maint. | Reasoning | Abstention |
|------|-----------|--------|---------|--------|-----------|------------|
| sport | **26%** | 34 | 33% | 0% | 14% | 100% |
| research | **21%** | 33 | 33% | 0% | 0% | 100% |
| movie | **11%** | 15 | 0% | 0% | 0% | 100% |
| city | **0%** | 33 | 0% | 0% | 0% | 100% |

**Qwen3.5 hospital 方差测量**：

| Seed | Composite | Stored | Breadth | Maint. | Reasoning |
|------|-----------|--------|---------|--------|-----------|
| s0 | **45%** | 36 | 56% | 0% | 33% |
| s1 | **30%** | 30 | 43% | 0% | 33% |
| 差距 | -15% | -6 | -13% | — | — |

**关键发现**：
- **Kimi movie 只存 15 实体**（budget=30）— 极度保守策略，Composite 最低（11%）
- **Kimi sport 26%**：B1 era 最弱模板（10%），post-Phase99 显著提升
- **Kimi research Reasoning=0%**：8 道推理题全答"不确定"
- **Kimi city 0%**（v0.10.7 re-run）：存了 33 实体但所有轴均为 0%，搜索召回完全失败
- **Qwen3.5 hospital 方差 ±15%**：s0=45% vs s1=30%，seed 间方差显著，需更多 seed 才能稳定排名

**跨模型对比（post-Phase99 全 8 模板 s0）**：

| 模板 | Qwen3.5 | Kimi | 差距 |
|------|---------|------|------|
| hospital | 45% | 40% | -5% |
| university | 40% | 25% | -15% |
| company | 40% | 25% | -15% |
| research | 35% | **21%** | -14% |
| codebase | 35% | 25% | -10% |
| movie | 30% | **11%** | -19% |
| sport | 25% | **26%** | **+1%** |
| city | 20% | **0%** | -20% |
| **均值** | **34%** | **22%** | -12% |

---

### 批次 21 — Qwen3.5 全 8 模板基线完成 + Kimi 新模板 ✅

**目的**：
1. Qwen3.5 movie + city s0 — 完成全 8 模板 post-Phase99 基线
2. Kimi-K2.5 university + codebase — 跨模型新模板覆盖

**Qwen3.5 结果（v0.10.5）**：

| 模板 | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections | Stored |
|------|-----------|---------|--------|-----------|------------|-------------|--------|
| movie | **30%** | 43% | 0% | 11% | 100% | **1/5** | 36 |
| city | **20%** | 12% | 0% | 0% | 100% | 0/5 | 36 |

**Kimi-K2.5 新模板结果（v0.10.5）**：

| 模板 | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections | Stored |
|------|-----------|---------|--------|-----------|------------|-------------|--------|
| university | **25%** | 14% | 0% | 14% | 100% | 0/5 | 17 |
| codebase | **25%** | 20% | 0% | 11% | 100% | 0/5 | 33 |

**关键发现**：
- **🎉 Movie Corrections 1/5**：`Steel Legacy.awards_count: search → edit` 成功！Qwen3.5 post-Phase99 **首次在真实 eval 完成 correction**
- **Movie conditional 100%**（1/1）：条件推理成功
- **City Reasoning 0%**：8 模板中唯一推理全零，存了 36 实体但检索/计算均失败
- **Kimi university 只存 17 实体**（budget=30），存储策略过于保守

**Qwen3.5 全 8 模板 post-Phase99 基线**：

| 模板 | Composite | Breadth | Reasoning | Corrections |
|------|-----------|---------|-----------|-------------|
| hospital | **45%** | 56% | 33% | 0/5 |
| university | **40%** | 57% | 29% | 0/5 |
| company | **40%** | 29% | 50% | 0/5 |
| research | **35%** | 43% | 25% | 0/5 |
| codebase | **35%** | 20% | 33% | 0/5 |
| movie | **30%** | 43% | 11% | **1/5** |
| sport | **25%** | 17% | 25% | 0/5 |
| city | **20%** | 12% | 0% | 0/5 |
| **均值** | **33%** | **35%** | **26%** | — |

**跨模型对比（post-Phase99 s0）**：
| 模板 | Qwen3.5 | Kimi-K2.5 | 差距 |
|------|---------|-----------|------|
| hospital | 45% | 40% | -5% |
| company | 40% | 25% | -15% |
| university | 40% | 25% | -15% |
| codebase | 35% | 25% | -10% |

---

### 批次 20 — 新模板首评 + 跨模型验证 ✅

**目的**：
1. University + Codebase 模板首次真实模型评测（Qwen3.5，seed 0）
2. Kimi-K2.5 post-Phase99 验证（hospital + company，对比 B19 Qwen3.5）

**任务**（4 个，可并发）：
```bash
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template university
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template codebase
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template hospital
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template company
```

**预期**：
- University/Codebase：首次数据，无基线对比。预期 Composite 25-40%（与其他模板范围一致）
- Kimi hospital：B1=17%，Phase 99 后预期提升
- Kimi company：B1=30%，Phase 99 后预期持平或提升

**Qwen3.5 新模板结果（v0.10.5）**：

| 模板 | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections | Stored |
|------|-----------|---------|--------|-----------|------------|-------------|--------|
| university | **40%** | 57% | 0% | 29% | 67% | 0/5 | 36 |
| codebase | **35%** | 20% | 0% | 33% | 100% | 0/5 | 36 |

**关键发现**：
- **University 40%**：首评即达历史第二高分（仅次 hospital 45%）。Breadth 57% 极强
- **Codebase 35%**：中等水平。Breadth 20% 较低，但 Reasoning 33% 稳定
- **University Abstention 67%**：**首次低于 100%**！模型对 1/3 未存储实体做了错误猜测，而非 abstain
- **relationship_lookup 100%**（codebase）：关系推理首次在真实 eval 成功
- **temporal_trend 100%**（university）：时间趋势推理成功
- **Corrections 全线 0/5**：与其他模板一致，预算耗尽

**Kimi-K2.5 结果（v0.10.5，post-Phase99）**：

| 模板 | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections | Stored |
|------|-----------|---------|--------|-----------|------------|-------------|--------|
| hospital | **40%** | 56% | 0% | 0% | 100% | 0/5 | 30 |
| company | **25%** | 14% | 0% | 17% | 100% | 0/5 | 35 |

**跨版本对比（Kimi-K2.5 s0）**：
| 模板 | B1(v1) | B20(v0.10.5) | 变化 |
|------|--------|-------------|------|
| hospital | 17% | **40%** | **+23%** |
| company | 30% | **25%** | -5% |

**跨模型对比（post-Phase99, s0）**：
| 模板 | Qwen3.5 | Kimi-K2.5 | 差距 |
|------|---------|-----------|------|
| hospital | 45% | 40% | -5% |
| company | 40% | 25% | -15% |

**关键发现**：
- **Kimi hospital +23%**：Phase 99 效果对 Kimi 同样显著
- **Kimi company -5%**（30→25%）：意外下降。Breadth 从 B1 的 17% 降到 14%。Kimi 在 company 的搜索召回率差
- **relationship_count 100%**：Kimi company 关系推理成功
- Kimi 整体弱于 Qwen3.5（hospital -5%, company -15%），主要差距在 Reasoning

---

### 批次 18 — Phase 98 Correction 引导验证 ✅

**目的**：Phase 98 增强了 correction 消息引导 + Edit 工具描述。验证 Corrections 是否从 0/5 提升。

**Qwen3.5-397B（seed 0，v0.10.3，chromadb）**：

| 模板 | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections | Stored |
|------|-----------|---------|--------|-----------|------------|-------------|--------|
| hospital | **25%** | 11% | 20% | 0% | 100% | 0/5 | 36 |
| company | **30%** | 29% | 0% | 17% | 100% | 0/5 | 36 |

**关键发现**：
- **Corrections 仍为 0/5**，但行为模式一致改善：所有 correction 操作都执行 search（Phase 98 引导有效）
- **根因确认（审计 A135）**：`generate_stream()` 的 ingest 文档使用修正后值渲染 → corrections 实质无效
  - 模型在 ingest 阶段存储的已经是修正后值，correction notice 是 no-op
  - 所有 5/5 corrections 的 writes 余额 = 0（即使没 bug，预算耗尽也阻塞 Edit）
- **Phase 99 已派发**（P0 最高优先级）修复此 bug
- Batch 18 数据标记为 **pre-fix**，Phase 99 后需重跑

**对比 Batch 17**：
| 指标 | B17 hospital | B18 hospital | B17 无 company |  B18 company |
|------|-------------|-------------|----------------|-------------|
| Composite | 25% | 25% | — | 30% |
| Maintenance | 0% | 20% | — | 0% |

---

### 批次 19 — Phase 99 修复后验证 ✅

**目的**：Phase 99 修复 ingest 文档渲染时序 bug 后，验证评测行为变化。

**全 4 模板对比（Qwen3.5-397B，seed 0，v0.10.4+ post-Phase99）**：

| 模板 | B17 Composite | B19 Composite | 变化 | B19 Breadth | B19 Reasoning | B19 Maint. | Stored |
|------|-------------|---------------|------|-------------|---------------|------------|--------|
| hospital | 25% | **45%** | **+20%** | 56% | 33% | 0% | 36 |
| company | 30% | **40%** | **+10%** | 29% | 50% | 0% | 32 |
| research | 35% | **35%** | — | 43% | 25% | 0% | 33 |
| sport | 15% | **25%** | **+10%** | 17% | 25% | 0% | 35 |
| **均值** | **26%** | **36%** | **+10%** | **36%** | **33%** | **0%** | **34** |

**Research 结果（v0.10.5）**：Composite 持平 35%，Breadth 43%（=B17），Reasoning 25%（B17=12%，+13%）。Corrections 0/5（5/5 search miss — 未存储的实体）。

**Sport 结果（v0.10.5）**：Composite 25%（+10%），Breadth 17%（B17=0%，+17%），Reasoning 25%（B17=12%，+13%）。Corrections 0/5。

**Hospital 结果（v0.10.4，post-Phase99）**：

| 指标 | B18 (pre-fix) | B19 (post-fix) | 变化 |
|------|-------------|---------------|------|
| **Composite** | 25% | **45%** | **+20%** |
| **Breadth** | 11% | **56%** | **+45%** |
| Maintenance | 20% | 0% | -20% |
| **Reasoning** | 0% | **33%** | **+33%** |
| Corrections | 0/5 | 0/5 | — |
| Stored | 36 | 36 | — |

**关键发现**：
- **Composite +20%**：Phase 99 修复文档一致性后，模型存储质量大幅提升
- **Breadth 56%**（历史最高）：ingest 文档使用原始值后，模型检索/回答一致性显著改善
- **Reasoning 33%**：从 0% 提升，说明模型存储了正确数据
- **Maintenance 0%**：预期行为——修复后 ingest 存原始值，correction 后模型未 Edit，update 问题 GT 是修正值 → 不匹配
- **Prairie Clinic: search → edit**：**历史首次**在真实 eval 中观测到模型尝试 Edit！

**Company 结果（v0.10.4，post-Phase99）**：

| 指标 | B18 (pre-fix) | B19 (post-fix) | 变化 |
|------|-------------|---------------|------|
| Composite | 30% | **40%** | **+10%** |
| Breadth | 29% | 29% | — |
| Maintenance | 0% | 0% | — |
| Reasoning | 17% | **50%** | **+33%** |
| Corrections | 0/5 | 0/5 | — |
| Stored | 36 | 32 | -4 |

**Batch 19 总结**：
- **Phase 99 验证成功**：4 模板均值 26→36%（+10%），3/4 模板 Composite 显著提升
- **Reasoning 是最大受益轴**：所有 4 模板 Reasoning 提升（hospital 0→33%, company 17→50%, research 12→25%, sport 12→25%）
- **Breadth**：hospital 56%（历史最高），research 43%（持平），sport 0→17%
- **Maintenance 全线 0%**：预期行为——模型用完 budget 无法 Edit
- **Corrections 全线 0/5**：根因是预算耗尽（writes=0 at correction time），需训练模型预留 budget
- **Research 持平**：35%→35%，Composite 未变但 Reasoning 内部改善（12→25%）
- **历史最高 composite**：hospital 45% 和 company 40% 均为 Qwen3.5 该模板历史最高

---

### 批次 17 — 多模板 v0.10.x 基线 ✅

**Qwen3.5-397B（seed 0，v0.10.2，chromadb）**：

| 模板 | Composite | Breadth | Maint. | Reasoning | Abstention | Corrections | Stored |
|------|-----------|---------|--------|-----------|------------|-------------|--------|
| hospital | **25%** | 22% | 0% | 0% | 100% | 0/5 | 36 |
| sport | **15%** | 0% | 0% | 12% | 100% | 0/5 | 35 |
| research | **35%** | 43% | 33% | 12% | 100% | 0/5 | 33 |

**关键发现**：
- Corrections = 0/5 across ALL 3 templates — 模型完全不执行修正操作（与 batch 12 v3 一致）
- Maintenance = 0% on hospital/sport（correction_rate=0.15/0.10 但模型不用 Edit）
- Research 最强（35%），breadth=43% 显著高于其他模板
- Sport 最弱（15%），breadth=0%（模型搜索召回差）
- Abstention = 100%（中立提示词有效）

**跨版本对比**（Qwen3.5 hospital s0）：
- v3 (batch 12, stdout): 45% → v0.6.7 (batch 13): 35% → **v0.10.2: 25%** — 持续下降
- 原因待分析：可能与 Phase 91 措辞变更、eval_salt 变化有关

---

### 批次 16 — Phase 77 修正后基线 ✅ (company 部分，hospital/sport 待 batch 17)

**目的**：Phase 77 修改了中流问题权重分配（使用 template question_weights 替代硬编码）和 contradiction batch 修复。对比 v0.7.x 前后分数变化。

**任务**：Qwen3.5（最强开源）× 3 模板 × seed 0，共 3 次评测。

```bash
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template company --official -o eval/Qwen_Qwen3.5-397B-A17B-TEE_company_s0_v3.json
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template hospital --official -o eval/Qwen_Qwen3.5-397B-A17B-TEE_hospital_s0_v3.json
python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template sport --official -o eval/Qwen_Qwen3.5-397B-A17B-TEE_sport_s0_v3.json
```

**重点关注**：
- hospital composite 变化（update 权重从硬编码 25% → 模板 30%）
- sport composite 变化（update 权重从 25% → 模板 25%，应基本不变）
- 与批次 14/15 数据的版本差异

---

### 批次 12 — v3 基线（⚠️ JSON 未保存，需重跑）

6/6 评测均完成计算但在保存 JSON 时 crash（`AttributeError: 'Namespace' object has no attribute 'backend'` at bench.py:316）。分数从 stdout 手动记录：

**Qwen3.5-397B（seed 0，v3 工具接口）**：

| 模型 | 模板 | Composite | Abstention | Retrieval | Update | Corrections |
|------|------|-----------|------------|-----------|--------|-------------|
| Qwen3.5-397B | company | **25%** | 100% | 11% | 33% | 0/5 |
| Qwen3.5-397B | research | **30%** | 100% | 20% | 0% | 0/5 |
| Qwen3.5-397B | hospital | **45%** | 100% | 33% | 60% | 0/5 |
| **均值** | | **33%** | 100% | 21% | 31% | |

**Kimi-K2.5（seed 0，v3 工具接口）**：

| 模型 | 模板 | Composite | Abstention | Retrieval | Update | Corrections |
|------|------|-----------|------------|-----------|--------|-------------|
| Kimi-K2.5 | company | **20%** | 100% | 11% | 0% | 0/5 |
| Kimi-K2.5 | research | **20%** | 100% | 0% | 0% | 0/5 |
| Kimi-K2.5 | hospital | **40%** | 100% | 22% | 20% | 0/5 |
| **均值** | | **27%** | 100% | 11% | 7% | |

**v3 基线分析**：
- **Corrections = 0/5 across ALL 6 evals**：模型用 Write 而非 Edit 做修正——修正事件消息仍说 search→forget→store（Bug 2），模型不知道该用 Edit
- Abstention = 100% 全部正确：中立提示词下模型不再瞎猜
- Qwen3.5 > Kimi（33% vs 27%），hospital 两者都最强
- **注意**：这些分数未保存为 JSON，修复 Phase 60 Bug 2+4 后需重跑

## 已完成

### 批次 15 — 弱模型覆盖扩展（完成 ✓，2026-03-11）

6/6 JSON 已保存（v0.6.7, chromadb, seed 1）。

**GLM-5（seed 1）**：

| 模型 | 模板 | Composite | B | M | R | Corrections |
|------|------|-----------|---|---|---|-------------|
| GLM-5 | company | **40%** | 25% | 67% | 29% | 2/5 |
| GLM-5 | research | **40%** | 29% | 33% | 29% | 0/5 |
| GLM-5 | hospital | **30%** | 25% | 14% | 33% | 0/5 |
| **均值** | | **37%** | 26% | 38% | 30% | |

**MiniMax-M2.5（seed 1）**：

| 模型 | 模板 | Composite | B | M | R | Corrections |
|------|------|-----------|---|---|---|-------------|
| MiniMax | company | **30%** | 0% | 33% | 43% | 0/5 |
| MiniMax | research | **15%** | 14% | 0% | 0% | 1/5 |
| MiniMax | hospital | **35%** | 25% | 43% | 0% | 1/5 |
| **均值** | | **27%** | 13% | 25% | 14% | |

**关键发现**：
- GLM-5 s1=37% 远超 s0=0%（s0 搜索全返回空是异常值，非真实能力）
- MiniMax s1=27% > s0=13%，更接近真实水平
- GLM-5 company corrections 2/5 是弱模型中最好的

### 批次 14 — MarkdownBackend 对比 ✅

Qwen3.5 × 3 模板 × seed 0，`--backend markdown`。

| 模型 | 模板 | ChromaDB | Markdown | 差异 |
|------|------|----------|----------|------|
| Qwen3.5 | company | 30% | 25% | -5% |
| Qwen3.5 | research | 30% | 35% | +5% |
| Qwen3.5 | hospital | 35% | 30% | -5% |
| **均值** | | **31.7%** | **30.0%** | **-1.7%** |

**结论**：无显著差异。Retrieval 瓶颈在模型侧（entities_per_write=1.0），非后端搜索精度。

### 批次 13 — v3 基线重跑 ✅

2 模型 × 3 模板 × seed 0，v0.6.7。Bug 2+4 修复后数据完整。

| 模型 | 模板 | Score | Breadth | Maint. | Reasoning | Efficiency |
|------|------|-------|---------|--------|-----------|------------|
| Qwen3.5 | company | 30% | 11% | 67% | 17% | 13% |
| Qwen3.5 | research | 30% | 20% | 0% | 22% | 10% |
| Qwen3.5 | hospital | 35% | 22% | 20% | 33% | 13% |
| Kimi | company | 35% | 33% | 33% | — | — |
| Kimi | research | 25% | — | 20% | — | — |
| Kimi | hospital | 30% | — | 58% | — | — |

**改善 vs batch 12**：Corrections >0（Bug 2 修复确认），JSON 正常保存（Bug 4 修复确认）。

### 批次 11 — Qwen3-235B 全模板 + MiniMax 扩展（完成）

Qwen3-235B 6 模板 seed 0 + MiniMax 4 新模板 seed 0。

**Qwen3-235B（seed 0，lite tier）**：

| 模型 | 模板 | Composite | Breadth | Maint. | Reasoning | Efficiency | Writes |
|------|------|-----------|---------|--------|-----------|------------|--------|
| Qwen3-235B | company | **28%** | 33% | 58% | 0% | 17% | 30/30 |
| Qwen3-235B | research | **19%** | 20% | 33% | 11% | 10% | 30/30 |
| Qwen3-235B | city | **15%** | 10% | 42% | 0% | 7% | 25/30 |
| Qwen3-235B | hospital | **28%** | 33% | 54% | 0% | 20% | 30/30 |
| Qwen3-235B | sport | **14%** | 0% | 50% | 0% | 7% | 30/30 |
| Qwen3-235B | movie | **17%** | 12% | 48% | 0% | 7% | 25/30 |
| **均值** | | **20%** | 18% | 48% | 2% | 11% | |

**MiniMax-M2.5 新增模板（seed 0，lite tier）**：

| 模型 | 模板 | Composite | Breadth | Maint. | Reasoning | Efficiency | Writes |
|------|------|-----------|---------|--------|-----------|------------|--------|
| MiniMax-M2.5 | research | **12%** | 0% | 30% | 11% | 7% | 30/30 |
| MiniMax-M2.5 | city | **18%** | 0% | 50% | 17% | 7% | 30/30 |
| MiniMax-M2.5 | hospital | **0%** | 0% | 0% | 0% | 0% | 30/30 |
| MiniMax-M2.5 | sport | **21%** | 0% | 75% | 0% | 10% | 29/30 |
| **均值** | | **13%** | 0% | 39% | 7% | 6% | |

**分析**：
- Qwen3-235B 均值 20%，最强项是 Maintenance（48%），Reasoning 几乎为零（仅 research 11%）
- MiniMax hospital=0%：29 entities 存储但搜索全返回空（与 GLM-5 同类问题）
- MiniMax Breadth 全部 0%：搜索召回极差，但 Maintenance 反而不错（存了更新但找不到原始数据）

### 批次 10 — 跨 tier 多 seed 验证（之前完成，见上下文）

批次 6-8 发现 hard(24%) > standard(12%)，反直觉。批次 10 数据在前一轮 session 中完成。

### 批次 9 — mem0 后端评测（⛔ 阻塞，跳过）

连续 3 次失败，标记为阻塞。错误：
1. `attempt to write a readonly database` — qdrant/sqlite 并发锁问题，第一批 ingest 后 DB 变只读
2. `RuntimeError: mem0 extracted no facts from content` — mem0 LLM (Qwen3-235B) 无法从结构化文档提取事实

**根因**：mem0 内部使用 qdrant 本地模式（SQLite 存储），并发写入导致锁升级为只读。即使单次写入成功，后续写入也会因 readonly 失败。需要执行者重新审视 mem0 后端的并发安全性。

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
