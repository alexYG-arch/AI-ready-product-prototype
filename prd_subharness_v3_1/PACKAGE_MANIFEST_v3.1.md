# Package Manifest v3.1 DRD Deductive Upgrade

## 基线

`prd_subharness_v3_1/` 以 `prd_subharness_v2_1/` 为基线，保留 v2.1 prototype runtime、renderer stage、Figma diff、UX writer、layout route、comment/reaction/visual-line 校验能力。

## v3.1 新增能力

- `DRD_MODE` 设计评审文档模式。
- DRD 演绎规则包：`sub_harnesses/prototype_projection_harness/drd_v3_1/rules/*.yaml`。
- 可执行 schema：`screen_role_obligations`、`design_kernel`、`logic_sidecar_card_map`、`local_materialization_patch`。
- 正/负样例 artifact，用于验证 schema 和 blocker 行为。
- SDS monochrome adapter，用于调用已下载的 Figma Simple Design System 快照，同时强制黑白灰策略。
- `prototypectl.py` 新增只读 DRD / design-system adapter 校验命令。

## v3.1 关键文件

- `sub_harnesses/prototype_projection_harness/drd_v3_1/profile.yaml`
- `sub_harnesses/prototype_projection_harness/drd_v3_1/package_manifest.yaml`
- `sub_harnesses/prototype_projection_harness/drd_v3_1/rules/12_complete_deductive_rules.yaml`
- `sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/*.schema.json`
- `sub_harnesses/prototype_projection_harness/drd_v3_1/examples/*.sample.yaml`
- `sub_harnesses/prototype_projection_harness/adapters/design_systems/sds_monochrome_adapter.yaml`
- `sub_harnesses/prototype_projection_harness/adapters/design_systems/figma-sds/`

## Orchestrator 同步

- `prd_orchestrator/harness_registry.yaml` version 升级到 `3.1` 并登记 DRD / SDS owns。
- `prd_orchestrator/document_registry.yaml` 登记 DRD rules/profile/schemas/samples 和 SDS adapter。
- `prd_orchestrator/dependency_graph.yaml` 登记 DRD artifact 链路和 SDS adapter 到 component binding 的依赖。
- `prd_orchestrator/routing_rules.yaml` 增加 DRD、sidecar、anchor、local materialization、SDS/monochrome 关键词。
- `prd_orchestrator/impact_rules.yaml` 将 DRD artifacts 列为 prototype projection output-only 产物。
- `prd_orchestrator/patch_control_v2.yaml` version 升级到 `3.1`，增加 DRD projection、local materialization patch 和 design system adapter source channels。

## 本地校验命令

```bash
python scripts/prd_control/prototypectl.py status --mode drd
python scripts/prd_control/prototypectl.py validate-drd-rules
python scripts/prd_control/prototypectl.py validate-design-system-adapters
python scripts/prd_control/prototypectl.py validate-role-obligations --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/screen_role_obligations.sample.yaml
python scripts/prd_control/prototypectl.py validate-design-kernel --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/design_kernel.sample.yaml
python scripts/prd_control/prototypectl.py validate-sidecar-cards --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/logic_sidecar_card_map.sample.yaml
python scripts/prd_control/prototypectl.py validate-local-patches --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/local_materialization_patch.sample.yaml
```

## 仍然延后

- 不生成真实 Figma DRD 画布。
- 不写真实 Figma reactions。
- 不自动生成 `ROLE-01 -> PATCH-01` artifacts。
- 不将 `local_materialization_patch` 写回 PRD fact store。
