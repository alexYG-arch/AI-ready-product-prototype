# AGENTS.md

本仓库是 PRD Sub-Harness v3.0。目标是通过总控 orchestrator 和多个子 harness 维护 AI-ready PRD package，并把结构化 PRD facts 安全投射为 DRD 设计评审文档画布。

## v3.0 Prototype Default

- 默认模式是 `DRD_MODE`。
- PRD / `prd_fact_bundle` 是事实源。
- Runtime 只做 validation / gap / candidate / review evidence。
- 默认不写真实 Figma `node.reactions`。
- 使用 Figma Dev Mode annotations 解释交互与状态。
- 使用 Pen logic lines 说明逻辑方向，但 Pen line 不是交互行为，也不是事实源。
- Payload 必须分片为 manifest、source slices、libs、board shards、flow shards 和 reports。

## Engineering Rules

- 保留 instance/run 隔离；真实 PRD 输入、候选和报告不要写入 harness 工程包。
- Prototype harness 不得直接写 requirements、screens、metrics、events 或 `PRD.md`。
- Figma diff 只能生成 candidate 或 review log，不能直接回写 fact store。
- 新增或修改 prototype DRD 规则后，运行 `prototypectl.py validate-drd-package` 和 `harnessctl.py validate-rule-specs`。
