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
4. 任务完成 → 移除完成项，提升下一待办为当前任务
5. Phase 完成 → 写 devlog/{date}-{n}.md，更新 ROADMAP.md §3/§4
6. 待办空 → 战略推导
```

## 任务执行规范

**eval 任务**：默认模型见 CLAUDE.md。结果自动保存到 `eval/` 目录。跑完后将分数记录到 ROADMAP.md §3。

**代码任务**：改代码 → 跑测试 → 测试通过才算完成。

**完成判定**：任务有明确产出（eval JSON / 代码通过测试 / 文档已更新）即为完成。无产出不算完成。

**提交时机**：Phase 级别完成时提交（如 Phase 0 全部 eval 跑完并汇总后）。单个 eval 不需要单独提交。

**长时间任务**：eval 可能耗时较长，一次 loop 只执行一个 eval 任务即可，不必赶进度。

## 战略推导

读 ROADMAP.md → 对照北极星找最大差距 → 设计任务写入本文件 → 在 ROADMAP.md §4 记录推导依据。方向可偏离既有路线，只要有证据支持。战略推导时应研究前沿工作（ROADMAP.md §7 + 主动搜索），从中获取设计启发，研究结果也保存到 devlog/。

## 提示词自优化

每次更新文档时，从长期自我演进的全局角度审视文档本身足够友好合理，是否在拖慢演进——规则冗余则合并，约束过时则删除，流程低效则简化，也可以补充新的合理规则和记忆。文档服务于演进，不是演进服务于文档。如果一条规则从未触发过价值，它就是噪音。

## 卡住时逐级升级

- **任务级**：当前方案不通 → 分析根因，换方案或拆解为更小的子任务
- **方向级**：同一方向连续多个任务无进展 → 在 devlog 记录分析，质疑方向本身是否正确，考虑替代方向，更新 ROADMAP.md §4 优先级

## 新 session 引导

1. 读 `AUTOPILOT.md`（本文件）了解当前任务
2. 读 `CLAUDE.md` 了解北极星和开发规则
3. 上下文不足时读 `docs/ROADMAP.md` §0（当前状态）和最近的 `devlog/` 文件

---

## 当前任务

更新 ROADMAP.md §0：清除过时的"未提交代码"列表，反映当前真实状态（rename 已完成，代码已提交）

## 待办

> 初始队列。待办清空后通过战略推导自动补充。

### Phase 0 — 多模板基准数据（ROADMAP §4 优先级 1）
1. 跑 research 模板 eval（默认模型, seed=1, lite）
2. 跑 city 模板 eval（默认模型, seed=1, lite）
3. 跑 hospital 模板 eval（默认模型, seed=1, lite）
4. 汇总多模板结果到 ROADMAP.md §3，分析跨模板一致性

### Phase 1 — 跨模型工具兼容性（ROADMAP §4 优先级 2）
5. 分析 GPT-OSS-120B 零分根因（读 eval JSON，定位失败模式）
6. 用 DeepSeek-V3.2-TEE 跑 eval，验证跨厂商兼容性
7. 用 MiniMax-M2.5-TEE 跑 eval，验证第三厂商兼容性
8. 如有格式兼容问题 → 改进 stream_agent 工具解析 + 加测试

### Phase 2 — RL 训练闭环（ROADMAP §4 优先级 3）
9. MemoryEnv search 从 substring → embedding（消除训练/评测不一致）
10. GRPO 框架调研与选型（verl vs slime）
11. 小模型基线 eval（Qwen3-14B/32B），建立 RL 前基准

