# Codex Stage10+ / FWRITE Upgrade Prompt（Codex 执行提示）

你正在升级 `prototype_projection_harness` 的 Stage10 及以后链路。请只修改 Stage10+ 与 Figma 写入相关规则，不改变 PRD fact authority。

## 必须完成

1. 新增 Stage10+ canonical pipeline：`GEN-10` 到 `GEN-20`。
2. 新增 FWRITE pipeline：`FWRITE-01` 到 `FWRITE-07`。
3. `GEN-20 COVERAGE-MANIFEST` 不再默认阻断在文字 review；gate 通过后直接进入 FWRITE。
4. 新增三个 FWRITE 前置硬 gate：
   - `USER-JOURNEY-GATE`
   - `INTERACTION-STATE-MACHINE-GATE`
   - `COMPONENT-BLUEPRINT-GATE`
5. 新增 `FIGMA-WRITE-READINESS-GATE`，只有所有必需 gate 通过才进入 FWRITE。
6. FWRITE 禁止任何模型推理，只能消费 final materialization 与 review view model。
7. 旧名称和旧 stage 只做 alias 兼容，新写入使用 v3.2 canonical names。

## 禁止

- 不得直接写 `requirements.yaml`、`screens.yaml`、`metrics.yaml`、`events.yaml`、`PRD.md`。
- 不得让 FWRITE 重新读取 PRD 并自由生成。
- 不得把 review report 当成默认人工阻断点。
- 不得让 `user_operation_chain` 继续使用松散 object-only schema。
- 不得让 component 只有 semantic_role 或 label，必须有 primitive_path / node type / state matrix。

## 验收

- `rules/17_complete_stage10_fwrite_rules.yaml` 可被 YAML parser 读取。
- `schemas/model_user_journey.schema.yaml` 要求 chain steps 必须具备 actor/surface/action/object/result。
- `schemas/model_interaction_state_machine.schema.yaml` 要求 transitions 必须具备 trigger/guard/effect。
- `schemas/model_component_blueprint.schema.yaml` 要求 component state matrix 与 content slots。
- `FIGMA-WRITE-READINESS-GATE` 通过后能进入 FWRITE，而不是停在文字 review。
