# Package Manifest v2.0

## Docs

- README.md
- UPDATE_NOTES_v2.0.md
- ARCHITECTURE_v2.0_PROTOTYPE_PROJECTION.md
- PACKAGE_MANIFEST_v2.0.md
- USER_GUIDE_NON_BUILDERS.md
- SCENARIO_PATHS.md
- EXECUTION_GUIDE_CODEX.md
- EXECUTION_GUIDE_LLM_RUNTIME.md
- GLOSSARY.md
- prd_orchestrator/HARNESS_RULE_REVIEW.md
- prd_orchestrator/harness_rule_review_crosswalk.yaml
- prd_orchestrator/INSTANCE_RUN_ISOLATION.md
- prd_orchestrator/SUBHARNESS_WORKTREE_POLICY.md
- checklists/PRD_REVIEW_CHECKLIST.md

## Runtime

- prd_orchestrator/
- sub_harnesses/
- product-spec/
- scripts/prd_control/harnessctl.py
- scripts/prd_control/prototypectl.py
- fixtures/
- schemas/

## Profiles And Rules

- prd_core_harness/prd_core_profile.yaml
- projection_sync_harness/prd_template_profile.yaml
- projection_sync_harness/prd_section_projection_map.yaml
- requirement_harness/requirement_pattern_registry.yaml
- requirement_harness/cears_quality_profile.yaml
- screen_state_harness/state_reasoning_rules.yaml
- metrics_events_harness/metric_event_profile.yaml
- release_ops_harness/release_ops_profile.yaml
- traceability_harness/traceability_profile.yaml
- prototype_projection_harness/prototype_runtime_profile.yaml
- prototype_projection_harness/runtime_generation_rules.yaml
- prototype_projection_harness/figma_projection_rules.yaml
- prototype_projection_harness/interaction_projection_rules.yaml
- prototype_projection_harness/figma_reaction_mapping.yaml
- prototype_projection_harness/component_binding_policy.yaml
- prototype_projection_harness/pattern_projection_rules.yaml
- prototype_projection_harness/figma_diff_policy.yaml
- prototype_projection_harness/reverse_sync_policy.yaml

## Prototype Projection Additions

- prd_orchestrator/patch_control_v2.yaml
- prd_orchestrator/templates/change_patch_candidate.v2.template.yaml
- prd_orchestrator/templates/figma_diff_patch_candidate.template.yaml
- prd_orchestrator/templates/prototype_projection_plan.template.yaml
- prd_orchestrator/figma_diff_reports/.gitkeep
- prd_orchestrator/prototype_projection_reports/.gitkeep
- product-spec/prototype.runtime.json
- product-spec/figma-sync-map.yaml
- product-spec/figma-interaction-map.yaml
- product-spec/component-binding-map.yaml
- product-spec/design-semantic-library.json
- schemas/prototype_runtime.schema.json
- schemas/figma_sync_map.schema.json
- schemas/figma_interaction_map.schema.json
- schemas/figma_diff_patch_candidate.schema.json
- sub_harnesses/prototype_projection_harness/patch_contracts/PROTO-008-runtime-model.yaml
- sub_harnesses/prototype_projection_harness/patch_contracts/PROTO-009-figma-forward-projection.yaml
- sub_harnesses/prototype_projection_harness/patch_contracts/PROTO-010-figma-diff-ingest.yaml
- sub_harnesses/prototype_projection_harness/patch_contracts/PROTO-011-interaction-graph.yaml
