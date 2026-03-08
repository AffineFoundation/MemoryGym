# MemoryBench 真实评测报告

**日期**: 2026-03-08
**版本**: v0.4.0（4轴评分 + 选择性红删）
**Backend**: ChromaDB

## 评测模型

| 模型 | 参数量 | API |
|------|--------|-----|
| Qwen3-235B-A22B (MoE) | 235B (22B active) | chutes.ai |
| Qwen3-32B | 32B | chutes.ai |
| GPT-OSS-120B | 120B | chutes.ai |
| DeepSeek-V3-0324 | 671B (37B active) | 历史数据 |

## 核心发现：选择性红删修复

### 问题

原始设计使用「核清洗」(nuclear redaction)：每个事件处理后删除全部对话历史，仅保留系统 prompt。
结果：模型在回答问题时完全不知道自己存了什么 → 大量空答案。

### 修复

选择性红删：事件后删除详细对话，但保留记忆状态摘要：
```
Your memory contains 14 entries: Entity1, Entity2, ...
Budget: 5 writes remaining.
```

### 修复前后对比（Qwen3-235B, company template）

| 指标 | 修复前 (seed=0, standard) | 修复后 (seed=1, lite) |
|------|--------------------------|----------------------|
| **总分** | 10% | **50%** |
| 空答案率 | 100% (20/20) | **0%** |
| Retrieval | 0% | **100%** (4/4) |
| Maintenance | 0% | 0% (0/3) |
| Reasoning | 0% | **50%** (1/2) |

## 修复后评测结果（seed=1, lite tier: 30e/10q/15b）

| 模型 | 准确率 | 存储量 | Breadth | Maint. | Reasoning | Abstention | 耗时 |
|------|--------|--------|---------|--------|-----------|------------|------|
| **Qwen3-235B** | **50%** | 14 | **100%** | 0% | **50%** | 0% | 266s |
| Qwen3-32B | 20% | 10 | 0% | 33% | 0% | **100%** | 2312s |

### 逐题分析

#### Qwen3-235B (seed=1, 5/10 correct)

| # | 类型 | 结果 | 验证方式 | 说明 |
|---|------|------|----------|------|
| 1 | update | - | judge | 空答案，未搜索更新后数据 |
| 2 | retrieval | + | rule | 精确匹配 110,702 |
| 3 | retrieval | + | rule | 精确匹配 19.94% |
| 4 | delta | - | judge | 空答案，不知道旧值 |
| 5 | abstention | - | rule | 空答案（应回答"I don't know"） |
| 6 | update | - | judge | 空答案 |
| 7 | comparison | + | rule | 正确比较 Argon Group vs Nimbus Labs |
| 8 | retrieval | + | rule | 精确匹配 9,712 |
| 9 | retrieval | + | rule | 精确匹配 $260,493.2M (trick_retrieval) |
| 10 | update | - | judge | 空答案 |

**模式**: 所有存储了的实体 retrieval 全部正确（4/4），comparison 也正确。
但 update/delta/abstention 全部失败 — 模型没有执行 correction 流程。

#### Qwen3-32B (seed=1, 2/10 correct)

| # | 类型 | 结果 | 验证方式 | 说明 |
|---|------|------|----------|------|
| 1 | update | - | judge | 错误答案 |
| 2 | retrieval | - | judge | 答案格式问题，rule 不匹配 |
| 3 | retrieval | - | judge | 答案格式问题 |
| 4 | delta | - | judge | 错误 |
| 5 | abstention | + | rule | 正确弃权 |
| 6 | update | + | rule | 正确更新！(唯一一个) |
| 7 | comparison | - | judge | 错误 |
| 8 | retrieval | - | judge | 答案格式问题 |
| 9 | retrieval | - | judge | 答案格式问题 |
| 10 | update | - | judge | 错误 |

**模式**: retrieval 全部落入 judge 验证 → 格式问题严重。
唯一的 update 正确是偶然（1/3）。

## 历史数据（修复前，标准级 standard: 60e/20q/30b）

### Qwen3-32B (3 seeds 平均, 修复前)

| Seed | 准确率 | 存储 | Retrieval | Update | Comprehension | Abstention |
|------|--------|------|-----------|--------|---------------|------------|
| 0 | 25% | 30 | 3/10 | 0/3 | 1/5 | 1/2 |
| 1 | 30% | 26 | 5/9 | 0/4 | 0/4 | 1/3 |
| 2 | 45% | 28 | 6/9 | 0/4 | 1/4 | 2/3 |
| **平均** | **33%** | 28 | **44%** | **0%** | **15%** | **50%** |

### GPT-OSS-120B (1 seed, 修复前)

| Seed | 准确率 | 存储 | 工具调用 | 说明 |
|------|--------|------|----------|------|
| 0 | 0% | 0 | 0 | 完全不使用工具 |

GPT-OSS-120B 无法解析 text-based tool calling 格式，0 个工具调用，0 分。

### DeepSeek-V3-0324 (3 seeds, 旧格式, 修复前)

| Seed | 准确率 | 存储 | Retrieval | Update | Comprehension | Abstention |
|------|--------|------|-----------|--------|---------------|------------|
| 0 | 45% | 22 | 2/7 | 0/3 | 6/7 | 1/2 |
| 1 | 35% | 28 | 2/9 | 0/3 | 3/5 | 2/2 |
| 2 | 30% | 35 | 1/9 | 0/2 | 3/6 | 2/3 |
| **平均** | **37%** | 28 | **22%** | **0%** | **67%** | **71%** |

## 跨模型总结

| 维度 | 最佳模型 | 得分 | 说明 |
|------|---------|------|------|
| **Retrieval** | Qwen3-235B (修复后) | 100% | 存储+精确回答 |
| **Update** | 全部失败 | 0-33% | 没有模型可靠执行 correction 流程 |
| **Reasoning** | DeepSeek-V3 (旧数据) | 67% | 强推理能力但旧评测 |
| **Abstention** | Qwen3-32B | 50-100% | 倾向于弃权 |
| **工具使用** | Qwen3-235B | 最高效 | 266s vs 2312s |

## 结论

1. **选择性红删是必要的系统修复** — 3 个模型在核清洗下都产生大量空答案，修复后 Qwen3-235B 从 10% → 50%
2. **Update 是当前所有模型的盲区** — 无模型可靠执行 search → forget → store 流程
3. **Qwen3-235B 是当前最佳选择** — 工具使用高效、retrieval 准确、速度快
4. **GPT-OSS-120B 不适合此任务** — 不支持 text-based tool calling
5. **需要更多 seeds 验证** — 当前修复后数据仅 1 seed，需要扩展到 10 seeds 获得统计显著性
