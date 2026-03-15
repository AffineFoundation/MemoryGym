# executor — 待办任务

## T1: 为 build_assistant_mask 添加单元测试（优先级: HIGH）

**背景**: `memorygym/training/common.py:build_assistant_mask()` 刚从 string-based 方法重构为 token-id O(n) 扫描。该函数在 SFT 训练中控制 loss masking（只训练 assistant turn），但**零测试覆盖**。训练线程正在活跃使用。

**目标**: 在 `tests/test_training.py` 中添加参数化测试，覆盖以下场景：

1. **基础功能**: 单轮 assistant turn — labels 仅在 assistant 内容区域有值
2. **多轮对话**: system + user + assistant + user + assistant — 两段 assistant 都被标记
3. **无 assistant turn**: 输入无 `<|im_start|>assistant` — fallback 返回 input_ids.clone()
4. **缺失 end marker**: assistant 开始但无 `<|im_end|>` — 标记到序列末尾
5. **空 assistant**: `<|im_start|>assistant\n<|im_end|>` — 不崩溃

**约束**:
- 使用 Qwen tokenizer（`from transformers import AutoTokenizer`）
- 测试标记 `@pytest.mark.slow`（需要下载 tokenizer）
- 验证 labels tensor 的 -100（masked）和非-100（unmasked）位置符合预期

**验收**: `python -m pytest tests/test_training.py -k "build_assistant_mask" -v` 全部通过

## T2: 提交未提交的训练代码改进

**背景**: 当前有 3 个训练相关文件的未提交改动，都是已验证的改进：
- `memorygym/evaluation/llm_judge.py`: MEMORYGYM_JUDGE_MODEL 环境变量覆盖
- `memorygym/training/common.py`: build_assistant_mask token-id O(n) 重构
- `memorygym/training/cli.py`: GRPO loss=None 日志修复

**目标**: 在 T1 完成后，连同新测试一起提交。commit message 格式: `fix(training): ...`
