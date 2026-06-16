# Stage10+ / FWRITE 优化设计文档 v3.2

## 1. 背景

现有 v3.1 已经包含很多 Figma 写入前规则，例如 `figma_render_plan`、`prototype_ui_blueprint`、`playable_prototype_model`、`figma_prototype_materialization`、live readback、geometry audit、visual semantic audit 等。但仍然存在两个问题：

1. `GEN-COVERAGE-MANIFEST（覆盖清单）` 和 `review report（评审报告）` 之后容易停在文字 review；文字 review 可读性差，而且不是最终用户体验形态。
2. 真实用户链路、页面内状态机、组件元素构成还没有成为进入 Figma 写入前的硬 gate。

因此本包将 Stage10+ 改为：

```text
GEN-10 SOURCE-SLICES
GEN-11 DETERMINISTIC-DRAFT
GEN-12 CARRIER-HANDOFF-DRAFT
GEN-13 CONTRACT-PROMOTION
GEN-14 MODEL-SURFACE-OWNERSHIP
GEN-15 MODEL-USER-JOURNEY
GEN-16 MODEL-INTERACTION-STATE-MACHINE
GEN-17 MODEL-COMPONENT-BLUEPRINT
GEN-18 FINAL-MATERIALIZATION
GEN-19 REVIEW-VIEW-MODEL
GEN-20 COVERAGE-MANIFEST

FIGMA-WRITE-READINESS-GATE

FWRITE-01 FIGMA-WRITE-PREPARE
FWRITE-02 WRITE-BOARD-FRAMES
FWRITE-03 WRITE-COMPONENT-INSTANCES
FWRITE-04 WRITE-SIDECAR-CARDS
FWRITE-05 WRITE-ANNOTATION-STUBS
FWRITE-06 WRITE-ANCHOR-BADGES
FWRITE-07 WRITE-MAPS-AND-REPORTS
```

## 2. Review 方式调整

旧模式：

```text
生成 coverage / report → 停下来人工读文字 → 再决定是否写 Figma
```

新模式：

```text
coverage gate 通过
→ figma write readiness gate 通过
→ 自动进入 FWRITE
→ 最终人工 review Figma 生成物
```

文字 `review_view_model.yaml` 和 `projection_report.yaml` 降级为 audit evidence（审计证据），不再默认阻断。

## 3. FWRITE 的边界

FWRITE 是纯写入层，只允许：

- 写 board frames（状态画布）
- 写 component instances（组件实例）
- 写 Logic Sidecar Cards（逻辑侧车卡片）
- 写 Annotation Stubs（Dev Mode 备注短桩）
- 写 Anchor Badges（锚点编号）
- 写 maps / reports（映射与报告）

FWRITE 禁止：

- 重新推理页面职责
- 重新判断真实用户链路
- 重新构造状态机
- 新增无 source_refs 的文案或组件
- 直接读 PRD 自由生成 Figma
- 修改 PRD fact store

## 4. 三个写入前硬闸门

### 4.1 USER-JOURNEY-GATE（真实用户链路闸门）

检查用户链路是否是真实步骤，而不是一句 summary。每个 step 必须有 actor、surface、action、object、result。

### 4.2 INTERACTION-STATE-MACHINE-GATE（交互状态机闸门）

检查每个 transition 是否有 trigger、guard/no_guard_reason、source_state、target_state_or_effect、feedback_timing。

### 4.3 COMPONENT-BLUEPRINT-GATE（组件蓝图闸门）

检查每个可见/可交互组件是否有 primitive_path、figma node type、hotspot role、component_state_matrix、content_slots。

## 5. 版本兼容

v3.2 canonical names 使用：

- `model_user_journey.yaml`
- `model_interaction_state_machine.yaml`
- `model_component_blueprint.yaml`
- `final_materialization.yaml`
- `coverage_manifest.yaml`
- `figma_write_plan.yaml`
- `figma_write_report.yaml`

兼容读取旧名称：

- `user_operation_chain.yaml` → `model_user_journey.yaml`
- `prototype_ui_blueprint.yaml` → `model_component_blueprint.yaml`
- `figma-comment-map.yaml` → `figma-annotation-map.yaml`
- `frame_packets.yaml` → `board_frame_packets.yaml`

旧名称只读兼容，新增写入必须使用 canonical names。
