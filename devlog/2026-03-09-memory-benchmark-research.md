# Memory Benchmark Research Survey (2024-2026)

> Date: 2026-03-09
> Purpose: Phase 29 前沿研究，为 V2 设计提供参考

## Benchmarks

### LoCoMo (2402.17753)
- 跨会话长期对话记忆
- 5 种问题：single-hop, multi-hop, temporal reasoning, open-domain, adversarial
- 评估 F1，无预算约束

### MemoryAgentBench (ICLR 2026)
- 4 能力：Accurate Retrieval, Test-Time Learning, Long-Range Understanding, Conflict Resolution
- "Inject once, query multiple times" 设计
- Conflict Resolution ≈ MemoryGym maintenance axis

### LongMemEval (ICLR 2025)
- 500 题 × 2 scale (115k / 1.5M tokens)
- 分析框架：indexing → retrieval → reading
- 商用系统仅 30-70%

### AMA-Bench (2602.22769)
- agent 环境交互轨迹记忆（非对话）
- 因果建模，GPT 5.2 仅 72.26%

### AMemGym (ICLR 2026, 2603.01966)
- 交互式在策略评测
- 发现 "Reuse Bias"：静态评测上表现好的 agent 在交互中可能失败

### MemoryBench (Tsinghua, 2510.17281)
- 声明式 + 程序式记忆
- 用户反馈持续学习

## Systems

### MemGPT / Letta (2310.08560)
- OS-inspired 分层记忆：main/recall/archival
- LLM 自主管理 paging
- DMR 93.4%

### A-Mem (2502.12110)
- Zettelkasten 灵感，原子笔记 + 动态链接
- 记忆自主演化（新信息更新旧表示）
- ~1,200 tokens/operation（85-93% 节省）

### Mem-alpha (2509.25911)
- RL 训练记忆策略
- 30k tokens 训练 → 400k+ 泛化
- 无硬预算约束

### Zep (2501.13956)
- Graphiti 时间感知知识图
- 94.8% DMR（优于 MemGPT）

### Mem0 (2504.19413)
- 动态提取/整合/检索
- Mem0g 图记忆变体
- MemoryGym 已用 mem0 兼容 API

## MemoryGym 独特定位

**唯一同时具备**：
1. 硬预算约束（存储决策测试）
2. 抗博弈验证（8 策略 simulation）
3. RL 训练环境（MemoryEnv）

**无其他基准测试**"在资源约束下该存什么"这一核心问题。

## 可借鉴设计

1. LongMemEval 的 indexing/retrieval/reading 诊断分解
2. MemoryAgentBench 的在线学习能力
3. Mem-alpha 的短→长泛化 RL 训练
4. AMA-Bench 的因果追踪
5. AMemGym 的在策略评测 → 验证 seed 生成方案
