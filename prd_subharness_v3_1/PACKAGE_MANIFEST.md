# Package Manifest v3.1 DRD Deductive Upgrade

当前默认 manifest 为 v3.1。完整 v3.1 增量清单见 `PACKAGE_MANIFEST_v3.1.md`；下方保留 v2.1 基线清单，说明本包从哪个 prototype projection 基线演进而来。

---

# Package Manifest v2.1 Prototype Projection

## 基线文件

保留 v2.0 全部文件，并在 `prd_subharness_v2_1/` 中升级为 v2.1 默认 harness。`prd_subharness_v2_0/` 保留为回滚基线。

## 新增根文档

- `OPTIMIZATION_PACKAGE_README.md`
- `UPDATE_NOTES_v2.1.md`
- `ARCHITECTURE_v2.1_PROTOTYPE_PROJECTION.md`
- `MIGRATION_PLAN_v1_0_to_v2_0.md`
- `PACKAGE_MANIFEST_v2.1.md`

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
- `product-spec/prototype.runtime.base.json`
- `product-spec/figma-sync-map.yaml`
- `product-spec/figma-interaction-map.yaml`
- `product-spec/component-binding-map.yaml`
- `product-spec/design-semantic-library.json`

## 新增 Prototype Projection Harness

- `sub_harnesses/prototype_projection_harness/README.md`
- `sub_harnesses/prototype_projection_harness/harness_contract.yaml`
- `sub_harnesses/prototype_projection_harness/prototype_runtime_profile.yaml`
- `sub_harnesses/prototype_projection_harness/runtime_generation_rules.yaml`
- `sub_harnesses/prototype_projection_harness/runtime_inference_policy.yaml`
- `sub_harnesses/prototype_projection_harness/renderer_stage_plan.yaml`
- `sub_harnesses/prototype_projection_harness/figma_comment_annotation_policy.yaml`
- `sub_harnesses/prototype_projection_harness/uxwriter_stage_rules.yaml`
- `sub_harnesses/prototype_projection_harness/uxwriter_validators.yaml`
- `sub_harnesses/prototype_projection_harness/layout_routing_coupling_rules.yaml`
- `sub_harnesses/prototype_projection_harness/pen_line_routing_rules.yaml`
- `sub_harnesses/prototype_projection_harness/renderer_skill_hook_policy.yaml`
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
- `schemas/figma_comment_map.schema.json`
- `schemas/layout_route_plan.schema.json`
- `schemas/uxwriter_copy_catalog.schema.json`
- `schemas/renderer_skill_pack.schema.json`

## 新增 Prototype 2.1 Contracts / Examples

- `sub_harnesses/prototype_projection_harness/contracts/input_prd_fact_bundle.schema.json`
- `sub_harnesses/prototype_projection_harness/contracts/standalone_run_contract.yaml`
- `sub_harnesses/prototype_projection_harness/examples/prd_fact_bundle.sample.yaml`
- `sub_harnesses/prototype_projection_harness/examples/uxwriter-copy-catalog.sample.yaml`
- `sub_harnesses/prototype_projection_harness/examples/layout-route-plan.sample.yaml`
- `sub_harnesses/prototype_projection_harness/examples/figma-comment-map.yaml`
- `sub_harnesses/prototype_projection_harness/examples/renderer-skill-pack.sample.yaml`

## 新增脚本

- `scripts/prd_control/prototypectl.py`

## v2.1 兼容性改动

- `scripts/prd_control/harnessctl.py` 支持 flat validator spec v1.0、prototype grouped validator spec v2.0/v2.1。
- `scripts/prd_control/prototypectl.py` 集成 runtime、interaction、fact bundle、UX writer、layout、comments、skill pack 校验。
- `sub_harnesses/prototype_projection_harness/validators.yaml` 保留 runtime、uxwriter、renderer、interaction、comments、layout/lines、reverse sync stage validators。
- `prd_orchestrator/HARNESS_RULE_REVIEW.md` 与 `prd_orchestrator/harness_rule_review_crosswalk.yaml` 新增 `PROTO-GEN-009` 至 `PROTO-GEN-014` 规则映射。
