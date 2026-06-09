# AGENTS.md

## 项目目标

本仓库是 PRD Sub-Harness v1.0。目标是通过总控 orchestrator 和多个子 harness，维护 AI-ready PRD package。

## 硬规则

- 不得整体重写 `product-spec/legacy_prd.md`。
- 不得把 unknown / assumed / candidate 写成 confirmed。
- 不得把 PRD.md 投影内容反向写成 structured facts。
- 不得把 C-EARS 句式通过当成需求质量通过。
- 不得自动补 metric baseline / target。
- 不得把 proposed API 写成 existing API。
- 不得删除 item，除非有 review_decision + tombstone + change_patch。
- 不得让 LLM 批准 impact_analysis 或 partial_rerun_plan。
- 不得让一个 patch 处理多个无关模块。
- PRD.md 必须遵守完整 14 章模板，不能只有标题和占位符。
- 完整旧 PRD 首次迁移必须先运行 `extract-source-baseline` 并评审 `structured_source_baseline`；后续子 Harness 消费 `sub_harness_inputs/<harness>.yaml` 输入切片，不得各自重复直接读取散装源 PRD。
- `route-change` / `classify-change` 只用于日常 change request，不得作为完整旧 PRD 首次迁移的人工评审主入口。

## 子 Harness 路由规则

- 目标、范围、用户、风险 → `prd_core_harness`
- 功能需求、C-EARS、验收 → `requirement_harness`
- 页面、状态、异常、文案、可访问性 → `screen_state_harness`
- 指标、埋点、实验 → `metrics_events_harness`
- 灰度、监控、回滚、客服运营 → `release_ops_harness`
- PRD.md 完整投影 → `projection_sync_harness`
- 追踪、影响分析、局部重跑 → `traceability_harness`

## Done Means

每个 patch 完成必须输出：

- patch_report
- change_patch
- impact_analysis

如果涉及 PRD.md，同步后必须运行：

- validate-prd-template
- check-prd-sync

完整旧 PRD 首次迁移还必须输出：

- structured_source_baseline
- STRUCTURED_SOURCE_EXTRACTION_REVIEW.md
- REVIEW.md
