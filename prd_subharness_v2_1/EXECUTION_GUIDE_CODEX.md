# Codex 执行指南 v2.0

## Initial PRD Migration Prompt

```text
你正在导入完整旧 PRD，不是处理日常 change request。

Rules:
- 先运行 extract-source-baseline inputs/legacy_prd.md。
- 先评审 structured_source_baseline 和 STRUCTURED_SOURCE_EXTRACTION_REVIEW.md。
- 提取评审批准前，不直接把源 PRD 内容写成 product-spec confirmed facts。
- 后续子 Harness 消费 reviewed structured_source_baseline，不重复直接读取散装源 PRD。
- route-change / classify-change 只用于日常小改，不作为完整旧 PRD 首次迁移的主入口。

Output:
- runs/<run-id>/prd_orchestrator/source_extraction/structured_source_baseline.yaml
- runs/<run-id>/prd_orchestrator/source_extraction/sub_harness_inputs/<harness>.yaml
- runs/<run-id>/human_review/STRUCTURED_SOURCE_EXTRACTION_REVIEW.md
- runs/<run-id>/human_review/REVIEW.md
```

## Plan-only Prompt

```text
你现在只做计划，不要编辑任何文件。

Read:
- AGENTS.md
- prd_orchestrator/harness_registry.yaml
- prd_orchestrator/document_registry.yaml
- prd_orchestrator/routing_rules.yaml
- sub_harnesses/<target_harness>/harness_contract.yaml
- sub_harnesses/<target_harness>/patch_contracts/<PATCH_ID>.yaml

Task:
为 <PATCH_ID> 输出执行计划。

Output:
- 本 patch 属于哪个 sub harness
- allowed files

## Prototype Projection Prompt

```text
你正在运行 prototype_projection_harness，而不是事实 owner harness。

Rules:
- 只能从 requirements.yaml、screens.yaml、metrics.yaml、events.yaml、traceability.md 和受控 binding 文件生成 prototype runtime。
- 不得从 PRD.md、Figma frame 文案、Figma layer name 或 Flow Map annotation 反推 confirmed fact。
- 真实 Figma 交互必须来自 interaction_graph.edges[] 并投射为 node reactions。
- Figma diff 只能生成 figma_diff_report 和 change_patch_candidate；不得直接写 requirements/screens/metrics/events/PRD.md。
- 反向同步必须做三向 diff：last runtime、current Figma semantic extract、current PRD runtime。

Required checks:
- python3 scripts/prd_control/prototypectl.py validate-runtime
- python3 scripts/prd_control/prototypectl.py validate-interactions
```
- forbidden files
- 需要读取哪些结构化事实
- 需要更新哪些报告
- 需要哪些 validator
- 是否需要 human review
```

## Execute Prompt

```text
执行 <PATCH_ID>。

Rules:
- 只修改 patch contract 允许的文件。
- 不修改 forbidden files。
- 不把 unknown / assumed / candidate 写成 confirmed。
- 不把 PRD.md 投影内容反向写入 structured facts。
- 如果缺失信息，写 gaps/open_questions。
- 写 patch_report、change_patch、impact_analysis。
- 需要局部重跑时写 partial_rerun_plan。
```
