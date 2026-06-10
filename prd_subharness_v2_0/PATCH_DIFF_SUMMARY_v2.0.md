# v2.0 Prototype Projection Patch Diff Summary

## 修改的 v1.0 文件

- `README.md`
- `AGENTS.md`
- `.codex/rules/prototype-projection.rules`
- `prd_orchestrator/harness_registry.yaml`
- `prd_orchestrator/routing_rules.yaml`
- `prd_orchestrator/impact_rules.yaml`
- `prd_orchestrator/dependency_graph.yaml`
- `prd_orchestrator/document_registry.yaml`

## 新增的核心文件

- `prd_orchestrator/patch_control_v2.yaml`
- `product-spec/prototype.runtime.json`
- `product-spec/figma-sync-map.yaml`
- `product-spec/figma-interaction-map.yaml`
- `product-spec/component-binding-map.yaml`
- `product-spec/design-semantic-library.json`
- `sub_harnesses/prototype_projection_harness/*`
- `schemas/prototype_runtime.schema.json`
- `schemas/figma_sync_map.schema.json`
- `schemas/figma_interaction_map.schema.json`
- `schemas/figma_diff_patch_candidate.schema.json`
- `scripts/prd_control/prototypectl.py`

## 工程决策

- 新增 `prototype_projection_harness`，不合并现有 PRD sub-harness。
- Figma 原型作为 projection，而不是事实源。
- Figma 反向修改只生成 `figma_diff_report` 与 `change_patch_candidate`。
- Figma 连线作为 `interaction_graph.edges[]` 的投影，而不是单独画线。
- component/pattern 优先绑定已有 Figma design system；JSON 语义库只作为 adapter 与 fallback。
