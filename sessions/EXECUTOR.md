# EXECUTOR — 执行线程

> 启动方式：`/loop 10m 你是执行线程，读 sessions/EXECUTOR.md 执行当前任务`
>
> 理解意图、设计方案、写代码、跑测试、提交。

## 每次 /loop

```
1. git pull --rebase origin main（同步训练者和其他开发者的变更）
2. 读本文件，理解「当前任务」的真实意图
3. 系统性思考：任务要解决什么问题？为什么这样做？有没有更好的方案？
4. 设计方案 → 写代码 → 跑测试
5. 代码变更 → python -m pytest tests/ -q
6. 评分/问题变更 → python -m memorygym.bench --seeds 3 --validate
7. 任务完成 → 移入「已完成」，提升下一待办
8. Phase 完成 → git add + git commit + git push origin main（**禁止** Co-Authored-By、Generated-by 等元数据行）
9. 待办空 → 等待新任务写入，不做其他事
```

**协作规则**：训练者是另一个独立开发者，会推送代码到同一个远程仓库。每次开发前必须 `git pull --rebase`，提交后必须 `git push`。如果 pull 有冲突，**在理解双方变更意图的基础上解决**，不要盲目接受任何一方。

## 思考规范

**理解意图**：每个任务都有表面需求和深层意图。审计线程写入的任务描述是起点而非终点——你必须理解问题的根因和解决方向，在此基础上设计最优方案。

**独立判断**：如果你在实施中发现任务描述的方案不是最优解，应该采用更好的方案并在 devlog 中说明理由。你是工程师，不是翻译机。

**全局视角**：改动任何代码前，先理解它在整个系统中的角色。读相关模块、理解调用链、考虑副作用。

## 执行规范

**代码任务**：理解意图 → 设计方案 → 改代码 → 跑测试 → 通过才算完成。

**eval 任务**：结果自动保存 `eval/`。API 故障（503/429/timeout）→ 重命名为 `*.503_error.json`，不计入数据表。只有 `success: true` 才是有效数据。一次 loop 只跑一个 eval 任务。

**完成判定**：有明确产出（eval JSON / 测试通过 / 文档更新）才算完成。

**闭环验证**：评分/问题/agent 逻辑变更后，必须跑 eval 验证效果。不能只改代码就宣布完成。

**提交粒度**：一个 Phase 一个 commit。提交时更新 `memorygym/__init__.py` 的 `__version__`（patch 递增）。

**文档同步**：Phase 完成时检查 CLAUDE.md 是否与代码一致。如有漂移，立即修正。

## 卡住时

- **任务级**：当前方案不通 → 换方案或拆解子任务
- **方向级**：连续多个任务无进展 → devlog 记录分析，更新 ROADMAP.md §4

## 新 session 引导

1. 读本文件了解当前任务
2. 读 CLAUDE.md 了解北极星
3. 上下文不足时读 `docs/ROADMAP.md` §0 和最近的 `devlog/`

---

## 当前任务

### Phase 57 — 系统提示词中立化（当前最高优先级）

**依据**：CLAUDE.md 新增"提示词中立"原则——系统提示词应描述任务和工具，不应规定存储策略。存储策略本身是被测能力的一部分。

**当前问题**：`stream_agent.py:111-116` 的 Storage Strategy 段落同时违反两个原则：
1. 规定了存储格式（`"EntityName | attr1: val1, attr2: val2, ..."`）→ 剥夺了"存储组织"能力的测试
2. 规定了存储策略（"Prioritize entities with extreme/distinctive values"、"Skip unremarkable entities"）→ 剥夺了"存储决策"能力的测试

#### Step 1 — 替换 Storage Strategy 为中立描述（stream_agent.py:111-116）

当前：
```
## Storage Strategy
- Store data compactly: "EntityName | attr1: val1, attr2: val2, ..."
- Prioritize entities with extreme/distinctive values
- Skip unremarkable entities when budget is tight
- IMPORTANT: Reserve ~20% of your budget for corrections. ...
```

改为（只描述约束，不规定策略）：
```
## Memory Budget
- You have limited store operations — plan your usage carefully
- Each memory_store or memory_update counts against your budget
- Corrections will arrive later and each update costs 1 write
```

保留预算提示（这是任务描述），删除所有策略指导（格式、优先级、取舍策略）。

#### Step 2 — 验证
```bash
python -m pytest tests/ -q
python -m memorygym.bench --seeds 3 --validate
```

#### Step 3 — 对比 eval
```bash
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --template company
```
记录结果到 devlog/。不要求分数提升，只需记录中立提示词下模型的自主策略选择。

**验证标准**：测试通过 + simulation 通过 + 有 eval 对比数据

---

### Phase 53 — RL 训练冒烟验证 ✅
### Phase 54 — 导入风格修正 ✅
### Phase 55 — 静默异常处理修正 ✅
### Phase 56 — 测试套件精简提效 ✅

### 低优先级 Backlog

- **Phase 52 — mem0 后端评测跑通**：qdrant readonly database + RuntimeError 处理。辅助后端，不阻塞主线评测
- **用户体验修正**：删除 docs/Design.md、填充 LEADERBOARD.md、README 补充、API key 错误信息
- **stream_agent.py 拆分**：972 行，提取事件处理函数降到 ~890 行
- **Promise/Progress Reward**：等简单 shaped reward 在真实训练中验证后，再决定是否需要更复杂的 reward 模型

## 已完成

### Phase 51 — MemoryEnv process-based reward 增强 ✅
### Phase 50 — verl_adapter 私有 API 修复 + 适配器健壮性 ✅
### Phase 49 — Inspect AI 完善 + 关键模块测试补全 ✅
### Phase 48 — mem0 后端完善集成 ✅
### Phase 47 — ChromaDB 搜索精度提升 ✅
### Phase 46 — 矛盾问题 GT 格式修复 ✅
### Phase 45 — 版本追踪 + 提交 ✅
### Phase 44 — RL shaped reward 修正 + 修正搜索 tightening ✅
### Phase 43 — 跨 session 修正测试补全 ✅
### Phase 42 — 多会话评测实现 ✅
### Phase 41 — 多会话评测设计 ✅
### Phase 40 — base.py 拆分 + movie.py 补全 ✅
### Phase 39 — 文档同步 + gen_question() API 完整性 ✅
### Phase 38 — 系统提示词修正 + ChromaDB 搜索改进 ✅
### Phase 37 — 新题型采样率提升 ✅
### Phase 36 — 模板策略差异化分析 ✅
### Phase 35 — V2 评测数据收集 ✅
### Phase 34 — 长上下文评测模式 ✅
### Phase 33 — 信息隐藏 + 噪声注入 ✅
### Phase 32 — 实体重要性分化 + 问题分布定制 ✅
### Phase 31 — 模板事件流差异化 ✅
### Phase 30 — 反事实推理 + 多约束过滤题型 ✅
### Phase 29 — 系统级重设计 ✅
### Phase 25-28 — 评分修复 + 红队审计 + 缺陷修复 ✅
### Phase 16-24 — 模板增强 + RL 训练 + SDK 验证 ✅
### Phase 3-15 — 基础系统 + 评测迭代 ✅
