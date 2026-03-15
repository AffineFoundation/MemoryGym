# memorybench-arena — 战略蓝图

> Lead 专属文档，其他角色只读。每 5 个 Loop 审查更新。

## 项目愿景

构建**真实、不可作弊、有训练价值**的 LLM 记忆管理评测与训练平台（MemoryGym）。目标：NeurIPS 2025 E&D Track 论文投稿（Abstract May 4, Paper May 6）。

## 当前阶段

**Phase 135 完成**（v0.10.37）— 评测系统成熟，训练模块初步可用。

### 已建立
- 10 个领域模板（company/research/city/hospital/sport/movie/university/codebase/project/agentteam），每模板 21-23 属性
- 20 种推理题型 + 4 轴评分（breadth 30% + maintenance 25% + reasoning 25% + efficiency 20%）
- 9 种 simulation 策略验证评分不变量
- 199 次成功评测，覆盖 8 个模型
- RL 训练管线（GRPO）初步跑通，SFT 已验证无效（退化 ~9pp）
- 论文 PA-23 完成，仍需持续打磨

### 关键指标
- 最强模型 Mistral-Small-24B: composite 24.3%（高方差）
- Maintenance 轴是独立瓶颈：M=13.5%，67% evals M=0
- Base 3B C=29.5% >> Base 7B C=13.8%（小模型反超）

## 技术路线

### 短期（2 周内）
1. **GRPO 30-step 长训练验证** — 确认 RL 是否能稳定提升记忆管理能力
2. **论文质量持续打磨** — PA-23 后仍有 3 项待完成（radar、ablation、behavior example）
3. **Maintenance 轴改善** — 模型不执行 correction Edit 是主因

### 中期（1-2 月）
4. **GiGPO 探索** — 两层信用分配，对多步骤记忆任务高度相关
5. **更多模型评测** — 扩大 leaderboard 覆盖
6. **训练 curriculum** — 基于 4 轴分数的自适应难度

### 长期
7. **多 agent 记忆协作** — 从单 agent 扩展到 multi-agent 场景
8. **训练效果迁移验证** — 验证训练后模型在真实 agent 场景的能力提升

## 架构决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 评分方式 | 4 轴独立 | 避免单一指标掩盖能力短板 |
| correction Edit 免费 | 是（Phase 112） | 不应因预算惩罚正确行为 |
| SFT 路线 | 已放弃 | 7B/3B 均退化，RL 更有前景 |
| 小模型优先 | 3B > 7B | 数据驱动，3B 基线更强 |
| 训练框架 | verl + slime | 多框架对冲风险 |

## 风险项

| 风险 | 影响 | 缓解 |
|------|------|------|
| GRPO 长训练不收敛 | 论文缺训练数据 | GiGPO 备选；调 reward shaping |
| NeurIPS deadline 紧迫 | Abstract May 4 | 论文线程持续打磨 |
| Maintenance 轴过低 | 评测区分度不足 | 分析模型行为模式，可能调整提示 |
