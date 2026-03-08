# AUTOPILOT

> 自治演进协议 + 任务队列。每次 `/loop` 读此文件。

## 演进闭环

```
北极星（CLAUDE.md）← 定义目标
  ↓
eval 数据（ROADMAP.md §3）← 衡量差距
  ↓
差距分析 ← 推导最高价值的改进方向
  ↓
执行 ← 写代码、跑测试、跑 eval
  ↓
(回到 eval 数据)
```

## 每次 /loop

```
1. 读本文件，执行当前任务
2. 代码变更 → python -m pytest tests/ -q
3. 评分/问题变更 → python -m memorygym.bench --seeds 3 --validate
4. 更新本文件：完成项移除，下一待办提升为当前任务
5. 逻辑单元完成 → 写 devlog/{date}-{n}.md，更新 ROADMAP.md
6. 待办空 → 战略推导
```

**战略推导**：读 ROADMAP.md → 对照北极星找最大差距 → 设计任务写入本文件 → 在 ROADMAP.md §4 记录推导依据。方向可偏离既有路线，只要有证据支持。战略推导时应研究前沿工作（ROADMAP.md §7 + 主动搜索），从中获取设计启发。参考项目如 [REDSearcher](https://github.com/RedSearchAgent/REDSearcher)，研究结果也保存到 devlog/。

**卡住**：技术问题最多 2 次不同方案，仍失败则跳过。外部阻塞立即跳过。

**新 session**：上下文不足时可读最近的 devlog 文件恢复决策背景。

---

## 当前任务

跑 Qwen3-235B × research × seed=1 (lite tier)
`python -m memorygym.bench --model chutes/Qwen3-235B --seed 1 --template research --tier lite`

## 待办

1. 跑 Qwen3-235B × city × seed=1 (lite tier)
2. 汇总多模板结果到 ROADMAP.md §3
3. 基于新 eval 数据重新评估 ROADMAP.md §4 优先级
4. 设计下一批任务
