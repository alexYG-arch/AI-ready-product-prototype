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
- 全局 run 控制证据：`patch_report` schema/template/CLI 和 `stop_the_line` schema/template/CLI。
- Loop v3.1 gate-only：归档 loop 升级包，新增 harness-aligned stage contracts、loop JSON Schema、validator 和 `write-loop-gate` evidence 写入命令。
- Prototype Artifact Generator v3.1.1：从 `inputs/PRD.md` 在隔离 run root 生成 source atoms、`prototype_source_brief`、DRD artifacts、runtime candidate、render payload、generation trace、artifact manifest、source coverage 和 projection report。

## v3.1 关键文件

- `sub_harnesses/prototype_projection_harness/drd_v3_1/profile.yaml`
- `sub_harnesses/prototype_projection_harness/drd_v3_1/package_manifest.yaml`
- `sub_harnesses/prototype_projection_harness/drd_v3_1/rules/12_complete_deductive_rules.yaml`
- `sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/*.schema.json`
- `sub_harnesses/prototype_projection_harness/drd_v3_1/examples/*.sample.yaml`
- `sub_harnesses/prototype_projection_harness/adapters/design_systems/sds_monochrome_adapter.yaml`
- `sub_harnesses/prototype_projection_harness/adapters/design_systems/figma-sds/`
- `schemas/patch_report.schema.json`
- `schemas/stop_the_line.schema.json`
- `prd_orchestrator/templates/patch_report.template.yaml`
- `prd_orchestrator/templates/patch_report.template.md`
- `prd_orchestrator/templates/stop_the_line.template.yaml`
- `prd_orchestrator/templates/stop_the_line.template.md`
- `sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/`
- `schemas/prototype_render_payload.schema.json`

## Orchestrator 同步

- `prd_orchestrator/harness_registry.yaml` version 升级到 `3.1` 并登记 DRD / SDS owns。
- `prd_orchestrator/document_registry.yaml` 登记 DRD rules/profile/schemas/samples 和 SDS adapter。
- `prd_orchestrator/dependency_graph.yaml` 登记 DRD artifact 链路和 SDS adapter 到 component binding 的依赖。
- `prd_orchestrator/routing_rules.yaml` 增加 DRD、sidecar、anchor、local materialization、SDS/monochrome 关键词。
- `prd_orchestrator/impact_rules.yaml` 将 DRD artifacts 列为 prototype projection output-only 产物。
- `prd_orchestrator/patch_control_v2.yaml` version 升级到 `3.1`，增加 DRD projection、local materialization patch 和 design system adapter source channels。
- `patch_report` 和 `stop_the_line` 采用 YAML + 同名 Markdown companion；YAML 为机器校验源，MD 为人工 review / stop-line 展示入口。
- Figma 仅用于最终原型画布写入；gate、review、validator、patch report、stop-line 结果不得写成 Figma page/frame/card。
- Loop gate 只写 `runs/<run-id>/prd_orchestrator/loop_gates/<gate-id>/` 下的 YAML/MD evidence；不执行 patch、rerun、payload generation 或 Figma write。
- Prototype generator 只写 `runs/<run-id>/io/output/`、`runs/<run-id>/io/state/` 和 `runs/<run-id>/prd_orchestrator/prototype_projection_reports/`；不写 `product-spec`、不跑 PRD harness、不中途写 Figma。

## 本地校验命令

```bash
python scripts/prd_control/prototypectl.py status --mode drd
python scripts/prd_control/prototypectl.py validate-drd-rules
python scripts/prd_control/prototypectl.py validate-design-system-adapters
python scripts/prd_control/prototypectl.py validate-role-obligations --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/screen_role_obligations.sample.yaml
python scripts/prd_control/prototypectl.py validate-design-kernel --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/design_kernel.sample.yaml
python scripts/prd_control/prototypectl.py validate-sidecar-cards --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/logic_sidecar_card_map.sample.yaml
python scripts/prd_control/prototypectl.py validate-local-patches --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/local_materialization_patch.sample.yaml
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 stop-the-line --stage render_readiness --reason "runtime has no screens" --next-action "generate prototype runtime" --resume-condition "validate-render-readiness passes"
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 write-patch-report --patch-id PATCH-001 --summary "修复 gate" --root-cause "空 runtime 被允许进入下游" --changed-file scripts/prd_control/prototypectl.py --validation "validate-render-readiness blocks empty runtime"
python scripts/prd_control/prototypectl.py validate-loop-rules
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 generate-prototype-artifacts --source inputs/PRD.md
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-render-readiness --runtime runs/RUN-001/io/output/prototype.runtime.candidate.json --payload runs/RUN-001/io/output/prototype-render-payload.yaml
python scripts/prd_control/prototypectl.py validate-generation-lifecycle-rules
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-generation-trace --input runs/RUN-001/io/state/generation_trace.yaml
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-generated-artifact-manifest --input runs/RUN-001/io/state/generated_artifact_manifest.yaml
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-source-coverage --coverage runs/RUN-001/io/state/source_coverage_report.yaml --runtime runs/RUN-001/io/output/prototype.runtime.candidate.json --payload runs/RUN-001/io/output/prototype-render-payload.yaml
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 write-loop-gate --stage RND-06B --trigger-source logic_sidecar_audit --severity blocker --failure-class FC-SIDECAR-MISSING --affected-artifact logic_sidecar_card_map.yaml --source-ref PRD.md#image-upload-rule --repair-hint "补齐缺失 sidecar card 和 anchor badge" --profile LOOP_PROFILE_COMPLEX
```

## 仍然延后

- 不生成真实 Figma DRD 画布。
- 不写真实 Figma reactions。
- 不自动生成 `ROLE-01 -> PATCH-01` artifacts。
- 不启用 loop 自动 patch / rerun。
- 不将 `local_materialization_patch` 写回 PRD fact store。
- 不在 generator 阶段写 Figma；最终 Figma writer 仍后置。
