# MemoryGym

构建一个**真实、不可作弊、有训练价值**的 LLM 记忆管理评测与训练平台。

核心约束（不可违反，任何代码变更都必须同时满足）：

1. **不可作弊**：任何背题、背模式、钻漏洞的策略都不能获得高分
2. **所见即所得**：评分反映真实能力，不存在取巧路径
3. **场景真实**：接近真实 agent 记忆场景（信息过载 + 预算有限 + 过时信息需更新）
4. **可训练**：不仅是评测工具，还是 RL 训练环境（MemoryEnv）
5. **确定性**：同一 seed → 完全相同的场景和评分

**核心流程**: seed → WorldTemplate → 生成实体 → 渲染文档 → agent 在预算内存储 → 修正事件改变世界状态 → 自适应提问 → 4 轴评分。

## 设计原则

### 评分有效性

评分必须只反映真实记忆管理能力。任何不理解内容、不做真实存储决策的策略都不能得高分。

通过 8 种 simulation 策略验证：每次变更评分或问题逻辑后，必须满足 perfect=100%, guesser=0%, smart_guesser<5%, abstainer<15%, strategic>naive+10%。

### 真实评估

- **无 fallback**：数据缺失或计算失败必须抛异常，禁止 `or 0` / `or "N/A"` / `except: return default`
- **GT 来自世界状态**：ground truth 从修正后的实体计算，无外部数据
- **确定性验证**：simulation 用规则匹配，真实 eval 用多模型 LLM judge

## 开发规则

1. **奥卡姆剃刀**：最少代码解决问题，不做过早抽象
2. **根因修复**：不打补丁，追溯到根因修复
3. **文件大小**：单个 `.py` 文件 ≤ 1000 行
4. **无 Fallback**：不允许静默错误掩盖，数据缺失必须显式抛出
5. **导入风格**：`memorygym/` 内用相对导入，跨包用绝对导入
6. **提交**：描述 why 不是 what。**禁止** Co-Authored-By、Generated-by 等元数据行。**只在阶段性完成当前开发任务才能提交**。用 `git add <具体文件>`，不用 `git add -A`
7. **先测试后提交**：新逻辑 → 先加测试

## 常用命令

```bash
python -m pytest tests/ -q                    # 全量测试
python tests/test_worlds.py                    # 世界模板测试（快速迭代）
python -m memorygym.bench --seeds 10 --validate  # Simulation 不变量检查
python -m memorygym.bench --model xxxxxx --seed 42 --template company  # 真实评测
```

每次代码变更必须通过 `python tests/test_worlds.py`。

## 评测系统

**4 轴评分**（预算压力：实体数远超写入预算，必须选择性存储）：

| 轴 | 问题类型 | 测什么 | 占比 |
|----|---------|--------|------|
| 存储广度 | retrieval | 你存了这个实体吗？ | 40% |
| 记忆维护 | update | 你更新了修正后的值吗？ | 20% |
| 推理能力 | comprehension | 你能从存储数据计算吗？ | 25% |
| — | abstention | 你能识别不知道的吗？ | 15% |

**可选模型**（Chutes 平台，按评测价值排序）：
- `Qwen/Qwen3.5-397B-A17B-TEE` — 最强开源，397B MoE
- `Qwen/Qwen3-235B-A22B-Instruct-2507-TEE`
- `MiniMaxAI/MiniMax-M2.5-TEE` — 第三家厂商，SWE-bench 80%+
- `moonshotai/Kimi-K2.5-TEE` — Moonshot 多模态
- `zai-org/GLM-5-TEE` — 智谱旗舰

**真实评测**：`bench.py --model <name>` 或 `inspect eval eval_task.py`，使用真实 LLM + 真实后端。

**Simulation**（`simulation.py`）：系统自测，非评估。8 种确定性策略验证评分不变量。

**记忆接口**：mem0 兼容（store/search/get/forget/list）。ChromaDB 和 mem0 后端的分数不可直接比较（存储粒度不同）。

## 架构

详细架构见 `docs/ROADMAP.md` §2。核心模块：

- `worlds/` — 6 个领域模板（company/research/city/hospital/sport/movie）+ 评分器 + Inspect AI 集成
- `evaluation/` — 答案验证 + LLM judge
- `memory/` — 预算管理 + 后端（ChromaDB/mem0）
- `agents/stream_agent.py` — 真实 LLM agent runner
- `simulation.py` — 8 种策略系统自测
- `bench.py` — CLI 入口
- `training.py` — SFT 轨迹 + MemoryEnv（RL 环境）

## 死胡同

| 方案 | 失败原因 |
|------|----------|
| 固定问题池 + 固定答案 | 可记忆 |
| 小实体集 (< 100) | 可枚举 |
| 结构化 needle | 可分类跳过 |
| WikiText 做 filler | perplexity 不可控 |
| 不同措辞区分题型 | 措辞攻击 |
| 先读完再答（纯 RAG） | 测检索不测记忆管理 |
| 只问最大值 | "总选最大的"攻击 |
| 问题随存储变化 | agent 通过选择性存储操纵问题 |

## 自治开发

`/loop` 时读 `AUTOPILOT.md`，其中包含演进协议和当前任务。
