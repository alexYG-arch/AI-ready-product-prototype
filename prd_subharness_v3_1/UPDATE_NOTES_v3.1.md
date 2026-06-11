# PRD Sub-Harness v3.1 DRD Deductive Update Notes

v3.1 在 v2.1 prototype projection harness 上增加 DRD 演绎推理校验链路。

## 新增

- `DRD_MODE` profile。
- DRD 规则包、libs、examples、migration、Codex prompt 归档。
- 四类可执行 schema 和对应 sample artifacts。
- 负例样本覆盖缺 `source_refs`、缺 anchor badge、annotation stub 缺 `sidecar_card_id`、`writes_prd: true`。
- `validate-drd-rules`、`validate-role-obligations`、`validate-design-kernel`、`validate-sidecar-cards`、`validate-local-patches`、`validate-design-system-adapters`。
- SDS monochrome adapter 和 component-binding map 调用链。

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
