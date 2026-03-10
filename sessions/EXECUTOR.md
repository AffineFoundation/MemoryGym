# EXECUTOR — 执行线程

> 启动方式：`/loop 30m 你是执行线程，读 sessions/EXECUTOR.md 执行当前任务`
>
> 理解意图、设计方案、写代码、跑测试、提交。

## 每次 /loop

```
1. 读本文件，理解「当前任务」的真实意图
2. 系统性思考：任务要解决什么问题？为什么这样做？有没有更好的方案？
3. 设计方案 → 写代码 → 跑测试
4. 代码变更 → python -m pytest tests/ -q
5. 评分/问题变更 → python -m memorygym.bench --seeds 3 --validate
6. 任务完成 → 移入「已完成」，提升下一待办
7. Phase 完成 → 写 devlog/{date}-{n}.md，更新 ROADMAP.md §3/§4
8. 待办空 → 等待新任务写入，不做其他事
```

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

### Phase 48 — mem0 后端完善集成

**依据**：mem0 后端当前是名义存在但从未验证的空壳。具体缺口：

1. **违反"无 fallback"原则**：
   - `mem0_backend.py:71` — `return "unknown"` 当 LLM 未提取出 fact 时静默返回硬编码字符串
   - `mem0_backend.py:97-98` — `except Exception: return None`（get）
   - `mem0_backend.py:104-105` — `except Exception: return False`（forget）

2. **零测试**：`test_backend_bench.py` 只测 ChromaDB，mem0 无任何测试

3. **backend_bench 不支持**：`backend_bench.py:280` — `raise ValueError(f"Unsupported backend: {backend_type}")` 直接拒绝 mem0

4. **RL 训练硬编码 ChromaDB**：`training.py:350-359` — MemoryEnv 直接 `import chromadb`，无法切换到 mem0

5. **env.py 未传递 mem0 配置**：`env.py:246-248` — `Mem0Backend()` 无参数构造，默认需要 `OPENAI_API_KEY`，无法自定义 LLM/embedder

#### Step 1 — 修复 mem0_backend.py 反模式

```python
# Line 71: "unknown" fallback → 显式异常
def store(self, content: str, memory_id: str | None = None) -> str:
    ...
    entries = result.get("results", [])
    if not entries:
        raise RuntimeError(f"mem0 extracted no facts from content ({len(content)} chars)")
    return entries[0]["id"]

# Line 97-98, 104-105: 静默异常 → 只捕获 mem0 特定的 "not found" 类异常
# get: 如果 ID 不存在返回 None 是合理的，但不应吞掉所有异常
# forget: 同理
```

**原则**：ID 不存在 → 返回 None/False 是合理语义。但网络错误、SDK crash 等不应被吞掉。缩小 except 范围，只捕获 `ValueError`/`KeyError` 等预期异常。

#### Step 2 — 添加 mem0 测试

在 `tests/test_backend_bench.py` 中新增 mem0 测试，但 mem0 需要外部 LLM API。策略：

**方案 A（推荐）**：用 `pytest.mark.skipif` 跳过无 API key 的环境
```python
import pytest
HAS_MEM0_API = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("MEM0_API_KEY"))

@pytest.mark.skipif(not HAS_MEM0_API, reason="mem0 requires LLM API key")
def test_mem0_recall():
    from memorygym.memory.backends.mem0_backend import Mem0Backend
    backend = Mem0Backend()
    # ... 与 chromadb 测试对称的测试逻辑
```

**方案 B（补充）**：单元测试 mock mem0 SDK，验证接口适配逻辑正确
```python
def test_mem0_store_no_facts_raises():
    """mem0 store() must raise when no facts extracted."""
    # Mock mem0 返回 {"results": []}
    # 验证 RuntimeError 被抛出
```

两个方案都要做。方案 B 保证 CI 总能跑，方案 A 保证真实集成可验证。

#### Step 3 — backend_bench 支持 mem0

`backend_bench.py:273-280` — 加入 mem0 分支：

```python
elif backend_type == "mem0":
    from memorygym.memory.backends.mem0_backend import Mem0Backend
    backend = Mem0Backend(user_id=f"bench_{tname}_{seed}")
```

注意：每个 seed 用不同 user_id 隔离数据。

#### Step 4 — MemoryEnv 后端抽象

`training.py:350-359` — 将 ChromaDB 硬编码改为可配置：

```python
class MemoryEnv:
    def __init__(self, ..., backend_type: str = "chromadb"):
        self._backend_type = backend_type
        ...

    def reset(self, ...):
        # 在 reset 时创建新后端实例
        if self._backend_type == "mem0":
            from memorygym.memory.backends.mem0_backend import Mem0Backend
            self._backend = Mem0Backend(user_id=f"memenv_{uuid.uuid4().hex[:8]}")
        else:
            # 现有 ChromaDB 逻辑
            ...
```

同时更新 `env.py:246-250`，让 Actor 传递 backend_type 到 MemoryEnv。

#### Step 5 — mem0 配置传递

`env.py` 和 `bench.py` 的 `--backend mem0` 路径需要支持自定义 mem0 config：
- 从环境变量读 `MEM0_LLM_MODEL`、`MEM0_API_KEY` 等
- 或接受 `--mem0-config <json>` 参数
- 默认使用 `OPENAI_API_KEY`（mem0 SDK 默认行为）

#### 验证标准

1. `python -m pytest tests/ -q` 全部通过（mem0 集成测试在无 API key 时自动 skip）
2. `python -m memorygym.bench --seeds 3 --validate` 通过
3. `mem0_backend.py` 无 `return "unknown"`、无裸 `except Exception`
4. `backend_bench.py --backend mem0` 可运行（有 API key 时）
5. `training.py` MemoryEnv 支持 `backend_type="mem0"` 参数
6. 新增至少 2 个 mem0 mock 测试 + 2 个 mem0 集成测试（skipif）

#### 注意事项

- **预算语义**：mem0 内部可能一个 store() 拆成多条 fact。预算计量以用户调用次数为准（1 次 store = 1 次写入），不管内部拆了几条。当前 MemoryBudget 已经是这个语义，不需要改。
- **分数不可比**：CLAUDE.md 已声明 ChromaDB 和 mem0 分数不可直接比较。保留这个声明。
- **不改评估协议**：scoring、question generation 等与后端无关的代码不动。

---

### Phase 49 — Inspect AI 完善 + 关键模块测试补全

**依据**：审计发现 eval_task.py 不支持 tier 名称、env.py（Actor）零测试覆盖、eval_task.py 零测试。这些是部署和集成的关键路径。

#### Step 1 — eval_task.py 支持 tier 名称

当前（eval_task.py:405-409）只接受原始参数（n_entities, n_questions 等），不支持 `--tier lite`。

```python
# 当前：必须 inspect eval eval_task.py -T n_entities=30 -T n_corrections=3 ...
# 目标：inspect eval eval_task.py -T tier=lite
```

从 `protocol.py` 导入 `TIERS`，在 `worldbench()` 函数开头解析 tier 参数：
```python
if tier is not None:
    cfg = TIERS[tier]
    n_entities = cfg["entities"]
    n_questions = cfg["questions"]
    # ...
```

保留原始参数作为 override（tier 设默认值，单独参数覆盖 tier 的值）。

#### Step 2 — Actor 类（env.py）测试

`memorygym/env.py` 的 Actor 类是 OpenEnv 容器化接口，329 行代码零测试。新建 `tests/test_env.py`：

- `test_actor_init()` — 验证 Actor 构造，task_id 解析
- `test_parse_task_id()` — seed/template/tier 从 task_id 正确提取
- `test_actor_evaluate()` — 用 mock backend 跑一次完整 evaluate，验证返回 dict schema
- `test_actor_reset_step()` — OpenEnv 接口的 reset → step 循环

不需要真实 LLM 调用——mock `run_stream_agent` 返回预制结果即可。

#### Step 3 — eval_task.py 基础测试

在 `tests/test_worlds_features.py` 或新建 `tests/test_eval_task.py` 中：

- `test_worldbench_tier_param()` — 验证 tier="lite" 正确映射到 TIERS["lite"] 的参数
- `test_worldbench_all_tiers()` — lite/standard/hard/multi 都能成功创建 Task 对象
- `test_worldbench_backend_param()` — 验证 backend="chromadb" 和 "mem0" 都被正确传递

#### 验证标准

1. `python -m pytest tests/ -q` 全部通过
2. `inspect eval memorygym/worlds/eval_task.py -T tier=lite -T seed=0 -T template=company` 语法上可接受（不需要真实模型）
3. 新增 ≥ 5 个测试

---

### Phase 50 — verl_adapter 私有 API 修复 + 适配器健壮性

**依据**：verl_adapter.py:178-180 直接访问 MemoryEnv 私有属性 `env._stream[env._event_idx]` 和 `env._format_event()`。任何 MemoryEnv 内部重构都会导致训练管线静默崩溃。

#### Step 1 — MemoryEnv 暴露公共接口

在 `training.py` 的 MemoryEnv 中添加公共方法：

```python
def current_observation(self) -> str:
    """Return the formatted text of the current event."""
    if self._event_idx >= len(self._stream):
        return ""
    return self._format_event(self._stream[self._event_idx])
```

这比暴露 `_stream` 和 `_event_idx` 更安全——消费者不需要知道内部数据结构。

#### Step 2 — verl_adapter 改用公共 API

`memorygym/adapters/verl_adapter.py:178-180`：

```python
# Before:
next_obs = env._format_event(env._stream[env._event_idx])

# After:
next_obs = env.current_observation()
```

#### Step 3 — slime_adapter 基础测试

在 `tests/test_adapters.py` 中新增 slime 相关测试（不需要真实 slime 框架）：

- `test_slime_generate_signature()` — 验证函数签名匹配 slime 约定
- `test_slime_reward_func()` — 验证 reward 返回值格式
- mock `args.post` 跑一个简化 episode

#### 验证标准

1. `python -m pytest tests/ -q` 全部通过
2. verl_adapter.py 不再有 `env._stream` 或 `env._event_idx` 的直接访问
3. 新增 ≥ 3 个测试

## 已完成

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
