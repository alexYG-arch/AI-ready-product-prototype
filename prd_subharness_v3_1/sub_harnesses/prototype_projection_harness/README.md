# Prototype Projection Harness

## 1. 定位

`prototype_projection_harness` 是 v3.1 的平级 projection harness。它保留 v2.1 的默认原型投射链路，并新增 DRD_MODE 设计评审文档模式的演绎规则校验入口。

```text
structured PRD facts → prototype.runtime.base.json → prototype.runtime.json → renderer stage plan → Figma frames / reactions / comments / flow lines
Figma semantic diff → figma_diff_report → change_patch_candidate
DRD_MODE source slices → screen role obligations → design kernel → sidecar card / local patch validation
```

它不拥有产品事实，不直接改 `requirements.yaml`、`screens.yaml`、`metrics.yaml`、`events.yaml` 或 `PRD.md`。
DRD v3.1 的 `local_materialization_patch` 也只允许修补投射层，不允许回写 PRD fact store。

---

## 2. 输入

允许读取：

```text
product-spec/requirements.yaml
product-spec/screens.yaml
product-spec/metrics.yaml
product-spec/events.yaml
product-spec/traceability.md
product-spec/component-binding-map.yaml
product-spec/design-semantic-library.json
sub_harnesses/prototype_projection_harness/drd_v3_1/rules/12_complete_deductive_rules.yaml
sub_harnesses/prototype_projection_harness/drd_v3_1/profile.yaml
sub_harnesses/prototype_projection_harness/adapters/design_systems/sds_monochrome_adapter.yaml
```

禁止把这些作为事实源：

```text
product-spec/PRD.md
Figma frame 文案
Figma layer name
Flow Map annotation text
```

---

## 3. 输出

```text
product-spec/prototype.runtime.json
product-spec/figma-sync-map.yaml
product-spec/figma-interaction-map.yaml
sub_harnesses/prototype_projection_harness/examples/uxwriter-copy-catalog.sample.yaml
sub_harnesses/prototype_projection_harness/examples/layout-route-plan.sample.yaml
sub_harnesses/prototype_projection_harness/examples/figma-comment-map.yaml
prd_orchestrator/figma_diff_reports/*.yaml
prd_orchestrator/prototype_projection_reports/*.yaml
prd_orchestrator/change_patch_candidates/*.candidate.yaml
sub_harnesses/prototype_projection_harness/drd_v3_1/examples/*.sample.yaml
sub_harnesses/prototype_projection_harness/adapters/design_systems/sds_monochrome_adapter.yaml
```

---

## 4. 三类投射

```text
Frame Projection       页面、状态、overlay、toast、modal
Reaction Projection    interaction_graph.edges[] → Figma node reactions
Documentation          Flow Map / Interaction Spec / annotation cards
```

真实可播放交互必须是 Figma reaction；说明箭头只是文档，不等于交互。

---

## 5. 本地命令

```bash
python scripts/prd_control/prototypectl.py status
python scripts/prd_control/prototypectl.py validate-runtime
python scripts/prd_control/prototypectl.py validate-interactions
python scripts/prd_control/prototypectl.py validate-fact-bundle --bundle sub_harnesses/prototype_projection_harness/examples/prd_fact_bundle.sample.yaml
python scripts/prd_control/prototypectl.py validate-uxwriter --catalog sub_harnesses/prototype_projection_harness/examples/uxwriter-copy-catalog.sample.yaml
python scripts/prd_control/prototypectl.py validate-layout --plan sub_harnesses/prototype_projection_harness/examples/layout-route-plan.sample.yaml
python scripts/prd_control/prototypectl.py validate-comments --map sub_harnesses/prototype_projection_harness/examples/figma-comment-map.yaml
python scripts/prd_control/prototypectl.py validate-skill-pack --pack sub_harnesses/prototype_projection_harness/examples/renderer-skill-pack.sample.yaml
python scripts/prd_control/prototypectl.py status --mode drd
python scripts/prd_control/prototypectl.py validate-drd-rules
python scripts/prd_control/prototypectl.py validate-role-obligations --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/screen_role_obligations.sample.yaml
python scripts/prd_control/prototypectl.py validate-design-kernel --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/design_kernel.sample.yaml
python scripts/prd_control/prototypectl.py validate-sidecar-cards --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/logic_sidecar_card_map.sample.yaml
python scripts/prd_control/prototypectl.py validate-local-patches --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/local_materialization_patch.sample.yaml
python scripts/prd_control/prototypectl.py validate-design-system-adapters
```

## 6. v2.1 Stage Contract Retained

```text
PROTO-012 two-pass runtime reasoning completion
PROTO-013 renderer staged implementation
PROTO-014 Figma comment annotations
PROTO-015 UX writer copy stage
PROTO-016 layout routing and visual pen-line coupling
PROTO-017 advisory renderer skill hook
```

Renderer order is strict: input freeze, layout route blueprint, canvas skeleton, sequence/page render, component/pattern fill, copy application, interaction comments, prototype reactions, visual flow lines, final validation. Comments and visual lines are documentation-only; Figma reactions and `interaction_graph.edges[]` remain the interaction authority.

## 7. DRD v3.1 First-Phase Boundary

```text
ROLE-01 / DK-01 / COMP-01 / HOT-01 / AUD-01 / PATCH-01 rules are archived and validated.
RND-06B sidecar card and RND-08A anchor leader-line rules are archived and validated.
Artifact generation and Figma canvas rendering are deferred.
```

DRD mode defaults:

```text
write_real_figma_reactions = false
draw_full_pen_lines = false
use_annotation_stub = true
use_logic_sidecar_cards = true
local_materialization_patches_write_prd = false
sds_monochrome_adapter_required = true
```
