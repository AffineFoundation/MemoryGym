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

**eval 任务**：默认模型见 CLAUDE.md。结果自动保存到 `eval/` 目录。跑完后将分数记录到 ROADMAP.md §3。**注意**：如果 eval 因 API 故障（503/429/timeout）失败，将结果文件重命名为 `*.503_error.json`，不要计入 ROADMAP.md 数据表。只有 `success: true` 的结果才是有效数据。

**代码任务**：改代码 → 跑测试 → 测试通过才算完成。

**完成判定**：任务有明确产出（eval JSON / 代码通过测试 / 文档已更新）即为完成。无产出不算完成。

**闭环验证**：代码改进（评分/问题/agent 逻辑）后，必须跑一次 eval 验证改进效果。不能只改代码就宣布 Phase 完成——需要有 eval 数据证明改进有效或至少无退化。

**提交粒度**：每个 Phase 独立提交，一个 commit 对应一个 Phase。不合并多个 Phase 到一个 commit。

**文档同步**：每次 Phase 完成时检查 CLAUDE.md 是否与代码实际状态一致（模板数、评分权重、架构模块等）。如有漂移，立即修正。关键决策（框架选型、设计变更）必须同步到 ROADMAP.md §5。

**长时间任务**：eval 可能耗时较长，一次 loop 只执行一个 eval 任务即可，不必赶进度。

## 战略推导

待办空时执行。目标是找到**系统级的根本性问题**，而非代码细节。

```
1. 站在用户/训练者/攻击者的角度审视系统：
   - 这个 benchmark 真的能区分好模型和差模型吗？为什么？
   - 如果我是训练者，读了全部代码，能教模型走什么捷径？
   - 评分反映的是真实能力还是某种可学习的模式？
   - 问题够难吗？还是存储了就能答对？
   - 多个模板是否真的要求不同的记忆策略？还是一套通用策略就能通吃？
   - 在这个 benchmark 上训练出来的能力，能迁移到真实 agent 任务吗？模板设计与现实场景的差距在哪？
2. 用代码验证你的判断（读相关模块确认），不要只读文档就下结论
3. 设计具体任务写入待办区，在 ROADMAP.md §4 记录推导依据
4. 研究前沿工作获取启发，结果保存到 devlog/
```

**原则**：
- 先问"系统设计对不对"，再问"实现有没有 bug"
- 产出是具体的待办任务，不是"系统已成熟"的结论
- 如果真没发现问题，把分析过程写入 devlog/ 作为证据

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

（待办空，执行战略推导）

## 已完成

### Phase 28 — 关键缺陷修复 + 测试补全 ✅
- eval_scorer runtime crash 修复（n_total/n_correct 未定义）
- relationship 问题替换补全（fn_map 加入 5 种关系类型）
- questions.py 拆分（685 + 315 行，AdvancedQuestionMixin 独立文件）
- 新增 eval_scorer 运行时测试 + relationship GT 验证测试（263 tests total）

### Phase 27 — 红队发现修复 ✅
- temporal_trend 5 级答案（baseline 50%→20%）、eval_salt 官方配置、correction 时序随机化、multi-entity packing 设计决策

### Phase 26 — 抗博弈性红队审计 ✅
- 9 个攻击面分析（2 Medium-High, 2 Medium, 5 Low），无高威胁漏洞

### Phase 25 — 评分有效性系统性修复 ✅
- 评分公式统一到 compute_axis_scores()、效率轴 correct/budget、maintenance gate stored_count/n_entities、distractor 去标记

### Phase 24 — affinetes SDK 端到端验证 ✅
### Phase 23 — 模板差异化自审 ✅ (5/5 PASS)
### Phase 22 — 模板真正差异化 ✅ (6 模板 × 领域特定 list_float + 约束 + 18 competency)
### Phase 21 — MemoryEnv shaped reward ✅
### Phase 20 — eval JSON 完整对话历史 ✅
### Phase 19 — 评测数据重建 ✅ (v1 归档, v2 队列)
### Phase 18 — 项目全面自审 ✅
### Phase 16-17 — 模板结构分化 + 验证 ✅ (6 dtype, 18 competency)
### Phase 14-15 — 发布准备 + eval 完整性 ✅
### Phase 5-13 — 评测质量迭代 + 工具链 ✅
### Phase 3 — RL 训练闭环 (代码完成，待 GPU 验证)
