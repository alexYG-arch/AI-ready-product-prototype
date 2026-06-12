# AGENTS.md

## 项目目标

本仓库是 PRD Sub-Harness v2.0。目标是通过总控 orchestrator 和多个子 harness，维护 AI-ready PRD package，并把结构化事实安全投射为 prototype runtime / Figma 原型。

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
- 不得把所有 PRD sub-harness 合并成一个大 harness；`prototype_projection_harness` 必须作为平级 projection harness 接入 `prd_orchestrator`。
- `prototype_projection_harness` 不得直接写 `requirements.yaml`、`screens.yaml`、`metrics.yaml`、`events.yaml` 或 `PRD.md`。
- Figma 修改只能进入 `figma_diff_report` 和 `change_patch_candidate`，必须经 `prd_orchestrator` 路由到事实 owner harness。
- Figma 节点 ID 不能作为业务事实 ID；业务对象必须使用稳定 semantic id，例如 `SCREEN-*`、`ST-*`、`CMP-*`、`INT-*`、`EDGE-*`、`OVERLAY-*`。
- Figma 原型连线必须来源于 `interaction_graph.edges[]`，每条线必须有 `interaction_id`、`source`、`trigger`、`actions`、`destination`、`source_refs`。
- 真实可点击原型使用 Figma reactions；评审说明线只能放在 Flow Map / Interaction Spec，不得替代真实 prototype reaction。
- 优先绑定已有 Figma component / pattern；无法绑定时才使用 JSON 语义库 fallback 或 low-fi placeholder，并产生 gap。
- 反向同步必须做三向 diff：上次 runtime、当前 Figma semantic extract、当前 PRD runtime。

## 子 Harness 路由规则

- 目标、范围、用户、风险 → `prd_core_harness`
- 功能需求、C-EARS、验收 → `requirement_harness`
- 页面、状态、异常、文案、可访问性 → `screen_state_harness`
- 指标、埋点、实验 → `metrics_events_harness`
- 灰度、监控、回滚、客服运营 → `release_ops_harness`
- PRD.md 完整投影 → `projection_sync_harness`
- 追踪、影响分析、局部重跑 → `traceability_harness`
- 原型、Figma、交互连线、component binding、prototype runtime → `prototype_projection_harness`

## Done Means

每个 patch 完成必须输出：

- patch_report
- change_patch
- impact_analysis

如果涉及 PRD.md，同步后必须运行：

- validate-prd-template
- check-prd-sync

如果涉及 prototype runtime / Figma projection，同步后必须运行：

- prototypectl status
- prototypectl validate-runtime
- prototypectl validate-interactions

完整旧 PRD 首次迁移还必须输出：

- structured_source_baseline
- STRUCTURED_SOURCE_EXTRACTION_REVIEW.md
- REVIEW.md
