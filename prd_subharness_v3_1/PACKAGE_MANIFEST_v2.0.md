# Package Manifest v2.0 Prototype Projection

## 基线文件

保留 v1.0 全部文件，并在 `prd_subharness_v2_0/` 中升级为 v2.0 默认 harness。`prd_subharness_v1_0/` 保留为回滚基线。

## 新增根文档

- `OPTIMIZATION_PACKAGE_README.md`
- `UPDATE_NOTES_v2.0.md`
- `ARCHITECTURE_v2.0_PROTOTYPE_PROJECTION.md`
- `MIGRATION_PLAN_v1_0_to_v2_0.md`
- `PACKAGE_MANIFEST_v2.0.md`

## 修改 Orchestrator 文件

- `prd_orchestrator/harness_registry.yaml`
- `prd_orchestrator/routing_rules.yaml`
- `prd_orchestrator/impact_rules.yaml`
- `prd_orchestrator/dependency_graph.yaml`
- `prd_orchestrator/document_registry.yaml`

## 新增 Orchestrator 文件

- `prd_orchestrator/patch_control_v2.yaml`
- `prd_orchestrator/templates/change_patch_candidate.v2.template.yaml`
- `prd_orchestrator/templates/figma_diff_patch_candidate.template.yaml`
- `prd_orchestrator/templates/prototype_projection_plan.template.yaml`
- `prd_orchestrator/figma_diff_reports/.gitkeep`
- `prd_orchestrator/prototype_projection_reports/.gitkeep`

## 新增 Product Spec 文件

- `product-spec/prototype.runtime.json`
- `product-spec/figma-sync-map.yaml`
- `product-spec/figma-interaction-map.yaml`
- `product-spec/component-binding-map.yaml`
- `product-spec/design-semantic-library.json`

## 新增 Prototype Projection Harness

- `sub_harnesses/prototype_projection_harness/README.md`
- `sub_harnesses/prototype_projection_harness/harness_contract.yaml`
- `sub_harnesses/prototype_projection_harness/prototype_runtime_profile.yaml`
- `sub_harnesses/prototype_projection_harness/runtime_generation_rules.yaml`
- `sub_harnesses/prototype_projection_harness/figma_projection_rules.yaml`
- `sub_harnesses/prototype_projection_harness/interaction_projection_rules.yaml`
- `sub_harnesses/prototype_projection_harness/figma_reaction_mapping.yaml`
- `sub_harnesses/prototype_projection_harness/component_binding_policy.yaml`
- `sub_harnesses/prototype_projection_harness/pattern_projection_rules.yaml`
- `sub_harnesses/prototype_projection_harness/figma_diff_policy.yaml`
- `sub_harnesses/prototype_projection_harness/reverse_sync_policy.yaml`
- `sub_harnesses/prototype_projection_harness/validators.yaml`
- `sub_harnesses/prototype_projection_harness/patch_contracts/*.yaml`

## 新增 Schemas

- `schemas/prototype_runtime.schema.json`
- `schemas/figma_sync_map.schema.json`
- `schemas/figma_interaction_map.schema.json`
- `schemas/figma_diff_patch_candidate.schema.json`

## 新增脚本

- `scripts/prd_control/prototypectl.py`

## v2.0 兼容性改动

- `scripts/prd_control/harnessctl.py` 支持 flat validator spec v1.0 和 prototype grouped validator spec v2.0。
- `sub_harnesses/prototype_projection_harness/validators.yaml` 保留 runtime、interaction、component、figma sync 四组 stage validators。
- `prd_orchestrator/HARNESS_RULE_REVIEW.md` 与 `prd_orchestrator/harness_rule_review_crosswalk.yaml` 新增 `PROTO-GEN-*` 规则映射。
