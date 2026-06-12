# PRD Sub-Harness v3.1 DRD Deductive Update Notes

v3.1 在 v2.1 prototype projection harness 上增加 DRD 演绎推理校验链路。

## 新增

- `DRD_MODE` profile。
- DRD 规则包、libs、examples、migration、Codex prompt 归档。
- 四类可执行 schema 和对应 sample artifacts。
- 负例样本覆盖缺 `source_refs`、缺 anchor badge、annotation stub 缺 `sidecar_card_id`、`writes_prd: true`。
- `validate-drd-rules`、`validate-role-obligations`、`validate-design-kernel`、`validate-sidecar-cards`、`validate-local-patches`、`validate-design-system-adapters`。
- SDS monochrome adapter 和 component-binding map 调用链。
- `preflight-prd-run`、`run-prd-loop`、`validate-render-readiness`，用于阻断无 PRD 输入、空 runtime 和缺 render payload 的误运行。
- `patch_report` / `stop_the_line` schema、template、Markdown companion 和 CLI，用于记录修复回执、阻断原因、恢复条件和后续 review/promotion 证据。
- `loop_v3_1` gate-only 归档和对齐层，包括 loop rules、JSON Schema、样例、validator 和 `write-loop-gate`。
- `generation_lifecycle_v3_1_1` 归档和 harness-aligned 约束；其中 `image_upload_3_5_first_pass_generation.sample.yaml` 只作为回归 fixture，不作为通用规则输入。
- `generate-prototype-artifacts` v3.1.1，用于 prototype-only 从 `inputs/PRD.md` 逐 source atom / table row / state / constraint 生成 source brief、DRD artifacts、runtime candidate、render payload、generation trace、artifact manifest 和 source coverage。
- `validate-generation-lifecycle-rules`、`validate-generation-trace`、`validate-generated-artifact-manifest`、`validate-source-coverage`。

## 保留

- runtime 仍不是事实源。
- Figma 仍不是事实源。
- `local_materialization_patch` 只修补投射层。
- DRD 一期只做规则、schema、样例和只读校验。

## 关键约束

- 黑白灰是强约束，SDS tokens/components 必须经 `SDS_MONOCHROME_ADAPTER_V3_1`。
- DRD 默认不写真实 Figma reactions。
- DRD 默认不画全量 Pen line。
- 任何进入 PRD fact store 的语义变更仍必须走 owner harness + human review。
- 每次关键阻断应写入 `stop_the_line` YAML 和同名 MD；每次修复应写入 `patch_report` YAML 和同名 MD。YAML 是机器源，MD 是人工阅读入口，报告本身仍需 `review_decision` 批准后才能 promote。
- Loop 当前只做 gate evidence：记录 finding、repair_plan、manifest 和 final_loop_report，不执行自动 patch / rerun，不生成 prototype payload。
- Prototype generator 当前生成 candidate projection，不写 PRD fact store；`validate-render-readiness` 会阻断 sample payload、空 runtime、缺 SDS 黑白灰绑定、缺 source_refs 或缺 required atom coverage 的 payload。
- Figma 只用于最终原型画布写入，不用于展示 gate、stage review、validator、patch report 或 stop-line 结果。
