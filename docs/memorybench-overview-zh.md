# MemoryBench：LLM Agent 记忆管理能力评测系统

## 一、背景

### 为什么需要记忆评测？

大模型 Agent 正在从"单轮对话"走向"长期任务执行"。在长期任务中，Agent 需要：
- 处理超出上下文窗口的信息量
- 在不同时间点存储、更新、丢弃信息
- 在资源受限（写入次数、存储空间）下做出**选择性存储决策**

这就是**记忆管理能力**——不是"能不能检索到"，而是"该不该存、存什么、什么时候更新、什么时候丢弃"。

### 现有评测的不足

| 现有方案 | 测什么 | 不测什么 |
|---------|--------|---------|
| Needle-in-a-Haystack | 长上下文检索 | 不涉及存储决策 |
| RAG 评测（BEIR、MTEB） | 检索质量 | 不涉及写入时的选择 |
| LongBench | 长文本理解 | 不涉及外部记忆工具使用 |
| MemGPT 评测 | 记忆系统功能 | 不评估存储策略优劣 |

**核心空白**：目前没有评测系统专门测试 Agent 在**写入时**的记忆管理决策质量。MemoryBench 填补这个空白。

## 二、核心价值

### 1. 测试真实能力，而非可以 hack 的指标

MemoryBench 的设计核心是**反作弊**。我们用 6 种对抗策略验证评测不可作弊：

| 策略 | 行为 | 准确率 | 说明 |
|------|------|--------|------|
| perfect | 全存+全更新 | **100%** | 理论上限 |
| strategic | 选择性存+更新 | **63-65%** | 合理 Agent |
| naive | 随机存+不更新 | **18-19%** | 只存不维护 |
| guesser | 不存+随机猜 | **0%** | 随机猜零分 |
| abstainer | 全存+总说不知道 | **15%** | 弃权策略天花板 |
| smart_guesser | 不存+中位数猜测 | **0-1%** | 智能猜测也失败 |

关键性质：
- **不看文档不可能答对**（guesser = 0%）
- **不更新记忆不可能答对 update 题**（naive update = 0%）
- **总说不知道也不行**（abstainer 仅 15%，因为有伪弃权题）
- **智能猜测也失败**（V14 整数精确匹配，猜中概率 < 0.01%）

### 2. 三轴评估模型

| 评估轴 | 测什么 | 怎么测 |
|--------|--------|--------|
| 存储广度 | 在预算限制下存了多少实体 | retrieval 问题：直接问已存/未存实体的属性值 |
| 记忆维护 | 收到更正后是否更新 | update 问题：用**完全相同的措辞**问被纠正属性，GT 是更正后的值 |
| 推理能力 | 能否基于存储数据做计算 | synthesis/aggregation/conditional：比较、求和、条件筛选 |

### 3. 标准记忆接口

MemoryBench 使用 mem0 兼容的 5 个工具：
- `memory_store(content, memory_id?)` — 存储（消耗写入预算）
- `memory_search(query, top_k)` — 搜索（免费）
- `memory_get(memory_id)` — 按 ID 获取（免费）
- `memory_forget(memory_id)` — 删除（免费，不退预算）
- `memory_list()` — 列表（免费）

评测结果直接反映 Agent 在真实框架中的记忆管理水平。

## 三、反作弊机制

### V14 数值容差系统

| GT 类型 | 容差 | 原因 |
|---------|------|------|
| 整数（年份、人数、计数） | **精确匹配** | 猜中 1987 年的概率 = 1/73 ≈ 1.4% |
| 浮点数（营收、比率） | **±2%** | 容许显示格式差异（$1,234.5M → 1234.5） |

这彻底封杀了数值猜测攻击：
- 年份范围 1950-2023 → 猜中一个年份的概率 ≈ 1.4%
- 员工数范围 50-200000 → 猜中概率 ≈ 0.0005%
- 即使用中位数/四分位数策略（smart_guesser），准确率仍 < 1%

### 伪弃权题（Trick Retrieval）

每次评测包含 ~2 个伪弃权题：用标准措辞问真实实体的属性，GT 是实际数值。总是回答"不知道"的 Agent 会在这些题上失败。

### eval_salt 反指纹

`--eval-salt N` 参数按 5-15% 的范围扰动所有数值，保持实体名称和结构不变。同一 seed 加不同 salt → 数值不同 → 预计算答案失效。

### 其他防御

| 攻击方式 | 防御措施 |
|---------|---------|
| 题型识别 | Update/retrieval/trick_retrieval 使用完全相同的 `_q_text` 模板 |
| 名字填充 | `detect_stored_entities` 要求名字+数值同时出现在同一条记忆中 |
| 总猜最大值 | 双向合成（随机 max 或 min），不能总猜最大 |
| 上下文窗口记忆 | 核弹式清理（nuclear redaction）：每个事件处理后删除所有消息 |
| 合成题只猜名字 | `_synthesis_match` 要求名字+数值同时正确 |

## 四、技术架构

### 项目结构

```
memorybench/
├── bench.py                       # 统一 CLI（模拟 + 真实 LLM 评测）
├── worlds/
│   ├── base.py                    # WorldTemplate ABC，核心逻辑
│   ├── company.py                 # 公司财务模板
│   ├── research.py                # 学术研究模板
│   ├── city.py                    # 城市统计模板
│   ├── hospital.py                # 医疗机构模板
│   ├── sport.py                   # 体育队伍模板
│   ├── eval_task.py               # Inspect AI 任务
│   └── eval_scorer.py             # 6 轴评分器
├── evaluation/
│   ├── validators.py              # 4 层规则验证（模拟评测用）
│   └── llm_judge.py               # 多模型 LLM 判官（真实评测主验证器）
├── agents/
│   └── stream_agent.py            # 真实 LLM Agent 运行器
├── memory/
│   ├── backends/
│   │   ├── chromadb_backend.py    # 向量搜索（默认后端）
│   │   └── mem0_backend.py        # mem0 SDK 封装（可选）
│   └── budget.py                  # 写入预算管理
└── inspect_task/
    └── tools.py                   # Inspect AI 工具定义
```

### 评测流程

```
WorldTemplate.generate_world(seed)
    → 60-200 个实体 × 8-10 个属性
    → render_document() → 紧凑格式文档（~250 字符/实体）
    → Agent 在写入预算下存储（必须压缩/选择）
    → generate_corrections() → 更正通知（改变 GT）
    → Agent 更新已存记忆
    → generate_stream() → 交错事件流
        ├── [INGEST] 文档批次（10 实体/批）
        ├── [CORRECTION] 更正通知（~60% 进度时）
        └── [QUESTION] 自适应问题（40% 中途 + 60% 最后）
    → 答案验证（模拟：规则验证 / 真实 LLM：多模型判官） → 评分
```

### 5 个世界模板

| 模板 | 实体类型 | 名字空间 | 属性示例 | 分类数 |
|------|---------|---------|---------|--------|
| company | 公司 | 600（30前缀×20后缀） | 营收、员工、专利、创立年 | 12 行业 |
| research | 研究员 | 625（25名×25姓） | 引用数、h指数、资助额 | 10 会议 |
| city | 城市 | 600（30形容×20地名） | 人口、GDP、犯罪率 | 8 区域 |
| hospital | 医院 | 600（30形容×20名词） | 床位、再入院率、满意度 | 10 专科 |
| sport | 队伍 | 600（30城市×20吉祥物） | 胜率、得分、球员年龄 | 10 联赛 |

跨模板方差 < 3%（strategic: 63-65%），证明评测不依赖特定领域。

### 问题预算分配

| 题型 | 占比（有更正） | 占比（无更正） |
|------|--------------|--------------|
| retrieval（存储广度） | 40% | 50% |
| update（记忆维护） | 20% | 0% |
| comprehension（推理） | 25% | 40% |
| abstention（知识边界） | 15% | 10% |

其中 ~2 题为 trick_retrieval（伪弃权题），从 retrieval 预算中分配。

### 验证基线（30 种子 × 5 模板）

| 策略 | 准确率 | 检索 | 更新 | 推理 | 弃权 |
|------|--------|------|------|------|------|
| perfect | 100% | 100% | 100% | 100% | 100% |
| strategic（存 70%+更新） | 63-65% | 67-71% | 65-71% | 13-20% | 100% |
| naive（存 40%不更新） | 18-19% | 38-42% | **0%** | 0-10% | 0% |
| guesser（零存储） | 0% | 0% | 0% | 0% | 0% |
| abstainer（总说不知道） | 15% | 0% | 0% | 0% | 100% |
| smart_guesser（智能猜测） | 0-1% | 0-1% | 0-1% | 0% | 0% |

关键观察：
- naive 存了 40% 的实体但 update = **0%** → 存储 ≠ 维护
- naive abstention = **0%** → 覆盖率 < 50% 时无法自信说"不存在"
- strategic 推理 13-20% → 5 实体全存的概率 (0.7)^5 ≈ 17%

### 55 项自动验证

每个模板 11 项检查：
- perfect = 100%, guesser = 0%
- strategic > naive + 10%
- naive > guesser
- guesser < 5%
- strategic update > naive update
- abstainer < 20%
- smart_guesser < 5%
- guesser trick_retrieval = 0%
- 确定性验证（同 seed → 同输出）

## 五、使用方式

### 模拟评测（无需 API）

```bash
# 单 seed 详细输出
python -m memorybench.bench --seed 0 -v

# 10 seeds + 验证检查
python -m memorybench.bench --seeds 10 --validate

# 30 seeds 发布验证 + JSON 输出
python -m memorybench.bench --seeds 30 --validate -o results.json

# 指定模板和策略
python -m memorybench.bench --seed 0 --template company --strategy strategic guesser -v

# 反指纹测试
python -m memorybench.bench --seed 0 --eval-salt 42 --validate
```

### 真实 LLM 评测

真实 LLM 评测自动使用**多模型 LLM 判官**验证答案（无需额外参数）。判官模型列表硬编码在 `llm_judge.py` 中，按顺序尝试，每个模型允许重试一次：

1. Qwen3-32B
2. Qwen3-235B-A22B
3. Gemma-3-27B
4. GPT-OSS-120B

```bash
# 使用 OpenAI 兼容 API
export OPENAI_API_KEY=sk-...
python -m memorybench.bench --seed 0 --model gpt-4o -v

# 使用 Chutes API
export CHUTES_API_KEY=cpk-...
python -m memorybench.bench --seed 0 --model deepseek-ai/DeepSeek-V3 \
    --api-base https://llm.chutes.ai/v1 -v
```

### Inspect AI 集成

```bash
inspect eval memorybench/worlds/eval_task.py \
    -M openai/gpt-4o -T seed=42 -T template=company
```

## 六、与竞品对比

| 特性 | MemoryBench | Needle-in-Haystack | RAG 评测 | LongBench |
|------|-------------|-------------------|---------|-----------|
| 测试存储决策 | ✓ | ✗ | ✗ | ✗ |
| 测试记忆更新 | ✓ | ✗ | ✗ | ✗ |
| 写入预算限制 | ✓ | N/A | N/A | N/A |
| 反作弊验证 | 55 项 | 无 | 有限 | 有限 |
| 标准记忆接口 | mem0 兼容 | N/A | N/A | N/A |
| 流式评测 | ✓ | ✗ | ✗ | ✗ |
| 多领域模板 | 5 个 | 1 个 | 多个 | 多个 |
| 对抗策略验证 | 6 种 | 无 | 无 | 无 |

## 七、开发现状

- **Phase 0-4 已完成**：核心框架、流式交错、真实 Agent 接入、反作弊飞轮、5 个模板
- **Phase 5 进行中**：开源发布准备
  - ✅ pyproject.toml 配置
  - ✅ 遗留代码清理
  - ⬜ README.md
  - ⬜ GitHub Actions CI
  - ⬜ 示例脚本
  - ⬜ 论文/博客
