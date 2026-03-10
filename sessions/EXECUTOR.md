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

### Phase 57 — 系统提示词中立化 ✅

Storage Strategy → Memory Budget（只描述约束，不规定策略）。
测试 314 passed, simulation ALL PASS。eval 待 API 恢复后记录。

### Phase 58 — 移除 mem0 后端 ✅

删除 mem0_backend.py + 18 处引用 + 6 个 mock 测试。
`grep -r "mem0\|Mem0" --include="*.py" memorygym/` = 0 结果。
测试 314 passed, simulation ALL PASS。

---

### Phase 59 — 工具接口 OpenClaw 化（训练迁移核心）

**依据**：红队论证确认，MemoryGym 当前工具接口（memory_store/memory_forget）与 OpenClaw 的记忆接口（Write/Edit 文件 + memory_search）不兼容。训练出的模型在 OpenClaw 上存储执行层完全不迁移。将工具接口改为 OpenClaw 兼容，使 RL 训练出的 action pattern 直接可用于 OpenClaw。

**核心变更**：工具接口从"记忆 API 模式"改为"文件操作模式"

```
当前工具                          改为（= OpenClaw 原生语义）
───────                          ──────────────────────
memory_store(content)      →     Write(content)         追加到 MEMORY.md
memory_forget(id)+store    →     Edit(old_text, new_text) 原地编辑 MEMORY.md
memory_get(id)             →     Read(start_line?, n?)   读取 MEMORY.md
memory_search(query)       →     memory_search(query)    不变
submit_answer(answer)      →     submit_answer(answer)   不变（评测专用）
```

#### Step 1 — 新增 MarkdownBackend（`memorygym/memory/backends/markdown_backend.py`）

```python
class MarkdownBackend:
    """OpenClaw-compatible: Markdown file + hybrid search."""

    def __init__(self, memory_dir):
        self.memory_file = Path(memory_dir) / "MEMORY.md"
        # 向量索引（复用 all-MiniLM-L6-v2）+ BM25 索引
        # Markdown 按 ~400 token chunk，80 token overlap（与 OpenClaw QMD 一致）

    def write(self, content: str) -> str:
        """追加到 MEMORY.md，触发重索引，返回行范围"""

    def edit(self, old_text: str, new_text: str) -> bool:
        """原地编辑 MEMORY.md，触发重索引"""

    def read(self, start_line=None, num_lines=None) -> str:
        """读取 MEMORY.md 内容"""

    def search(self, query: str, top_k=5) -> list[dict]:
        """混合搜索：向量(70%) + BM25(30%) + RRF rerank"""
```

搜索实现：用 `sentence_transformers`（已有依赖）+ `rank_bm25`（新依赖，轻量）做混合搜索，与 OpenClaw QMD 逻辑一致。

#### Step 2 — stream_agent.py 工具接口改造

1. SYSTEM_PROMPT 中的工具描述改为 Write/Edit/Read/memory_search 语义
2. `_KNOWN_TOOLS` 更新为新工具名
3. `_execute_tool` 中各分支适配新工具语义：
   - `Write`：调 `backend.write(content)`，消耗 1 write budget
   - `Edit`：调 `backend.edit(old, new)`，消耗 1 write budget
   - `Read`：调 `backend.read()`，不消耗预算
   - `memory_search`：不变
   - `submit_answer`：不变

#### Step 3 — simulation.py 适配

策略核心逻辑（决定存什么）不变，只改接口调用：
- `backend.store(content)` → `backend.write(content)`
- `backend.forget(id) + backend.store(new)` → `backend.edit(old, new)`
- 9 种策略的选择逻辑保持不变

#### Step 4 — training/env.py 适配

MemoryEnv 的工具接口和 reward 信号适配：
- 工具名映射
- shaped reward：检测 Write 调用（而非 memory_store）
- episode 结束后读 MEMORY.md 评估存储质量

#### Step 5 — bench.py 适配

`--tool-mode` 参数暂不需要。直接用新接口作为默认。ChromaDB 后端仍可用（ChromaDBBackend 实现同样的 write/edit/read/search 接口），但 MarkdownBackend 为默认。

#### Step 6 — 测试

- 新增 MarkdownBackend 单元测试（write/edit/read/search 基本功能）
- 修改现有 simulation 测试适配新接口
- 确认 `python -m memorygym.bench --seeds 3 --validate` 通过

**验证标准**：
- MarkdownBackend 通过 write → search 闭环测试
- 混合搜索（向量 + BM25）recall >= 90%
- simulation 9 种策略不变量全部通过
- `python -m pytest tests/ -q` 全通过

**注意**：这是一个大改动，建议分 2-3 个子 commit：
1. MarkdownBackend 实现 + 测试
2. stream_agent.py + simulation.py 工具接口改造
3. training/env.py + bench.py 适配

---

### Phase 60 — Phase 59 遗留 bug 修复（审计 A40 发现）✅

6/6 bug 全部修复。审计线程直接修复（执行者 7 轮未活动，Bug 2+4 已造成评测数据损失）。
340 passed, simulation ALL PASS。

#### Bug 1（HIGH）— stream_agent.py 工具调用计数遗漏

`_parse_and_execute()`（L313-316）和 `_run_tool_loop()`（L414-417）只统计 `memory_store`，不统计 `Write` 和 `Edit`。导致 trajectory stats 中 write 计数为 0。

修复：
```python
# L313-316
if name in ("Write", "Edit", "memory_store"):
    n_writes += 1
elif name in ("memory_search", "memory_list", "memory_get", "Read"):
    n_searches += 1

# L414-417 同上
```

#### Bug 2（HIGH）— stream_agent.py 修正事件消息仍用旧工具名

L668-675 修正事件的 ACTION REQUIRED 仍说 `memory_search → memory_forget → memory_store`，与 SYSTEM_PROMPT 中的 `search → Edit` 矛盾。模型收到冲突指令。

修复：
```python
f"ACTION REQUIRED: You must update your stored memory.\n"
f"1. memory_search \"{entity_name}\"\n"
f"2. Edit the old value to the corrected value\n"
```

#### Bug 3（HIGH）— adapters/_common.py 缺少新工具名

`_KNOWN_TOOLS`（L24-27）只有旧名（memory_store/forget/get/list），缺 Write/Edit/Read。`format_tool_result()`（L81-112）也没有新工具名分支。RL 训练时 verl/slime adapter 会**静默丢弃**模型的 Write/Edit/Read 调用。

修复：
- L24-27：`_KNOWN_TOOLS` 加入 `"Write", "Edit", "Read"`
- L81-112：`format_tool_result()` 加入 Write/Edit/Read 分支

#### Bug 4（MEDIUM）— bench.py args.backend 未定义

L316 引用 `args.backend`，但 `--backend` 参数已在 Phase 58 删除。运行 `bench.py --model` 会 crash。

修复：L316 改为 `"backend": "chromadb"`（硬编码，或改为检测实际后端类型）

#### Bug 5（LOW）— stream_agent.py 修正检测逻辑

修正成功检测（~L683-698）只检查 `memory_store` 调用，不检查 `Edit` 调用。Edit-based 修正不会被标记为成功。

修复：修正检测增加对 Edit 调用的检查。

#### Bug 6（LOW）— CLAUDE.md 文档漂移（3 处）

Phase 57-59 完成后 CLAUDE.md 有 3 处描述与代码不一致：

1. **L96**："8 种确定性策略" → 实际 9 种（Phase 31 加了 template_expert）
2. **L98**："记忆接口：mem0 兼容（store/search/get/forget/list）。ChromaDB 和 mem0 后端的分数不可直接比较" → mem0 已删除（Phase 58），工具接口改为 Write/Edit/Read（Phase 59）。改为描述当前接口：Write/Edit/Read/memory_search，后端 ChromaDB + MarkdownBackend
3. **L106**："后端（ChromaDB/mem0）" → 改为 "后端（ChromaDB/MarkdownBackend）"

#### 验证标准
- `python -m pytest tests/ -q` 全通过
- `python -m memorygym.bench --seeds 3 --validate` ALL PASS
- `python -m memorygym.bench --model Qwen/Qwen3.5-397B-A17B-TEE --seed 0 --template company` 不 crash（验证 Bug 4 修复）
- CLAUDE.md 中无 mem0 引用、策略数量正确

---

### Phase 53 — RL 训练冒烟验证 ✅
### Phase 54 — 导入风格修正 ✅
### Phase 55 — 静默异常处理修正 ✅
### Phase 56 — 测试套件精简提效 ✅

### Phase 61 — stream_agent.py 拆分 ✅

提取 execute_tool + 5 个辅助函数到 `_tool_helpers.py`（159 行）。
stream_agent.py 1017→884 行。340 passed, simulation ALL PASS。v0.6.4。

### 低优先级 Backlog

- **用户体验修正**：删除 docs/Design.md、填充 LEADERBOARD.md、README 补充、API key 错误信息
- **Promise/Progress Reward**：等简单 shaped reward 在真实训练中验证后，再决定是否需要更复杂的 reward 模型
- **legacy 工具名清理**：移除 _KNOWN_TOOLS 中的 memory_store/memory_forget/memory_get/memory_list（等 v3 评测基线稳定后）

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
