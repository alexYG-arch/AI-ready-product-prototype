# Prototype Projection Harness

## 1. 定位

`prototype_projection_harness` 是 v2.1 的平级 projection harness。它负责：

```text
structured PRD facts → prototype.runtime.base.json → prototype.runtime.json → renderer stage plan → Figma frames / reactions / comments / flow lines
Figma semantic diff → figma_diff_report → change_patch_candidate
```

它不拥有产品事实，不直接改 `requirements.yaml`、`screens.yaml`、`metrics.yaml`、`events.yaml` 或 `PRD.md`。

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
```

## 6. v2.1 Stage Contract

```text
PROTO-012 two-pass runtime reasoning completion
PROTO-013 renderer staged implementation
PROTO-014 Figma comment annotations
PROTO-015 UX writer copy stage
PROTO-016 layout routing and visual pen-line coupling
PROTO-017 advisory renderer skill hook
```

Renderer order is strict: input freeze, layout route blueprint, canvas skeleton, sequence/page render, component/pattern fill, copy application, interaction comments, prototype reactions, visual flow lines, final validation. Comments and visual lines are documentation-only; Figma reactions and `interaction_graph.edges[]` remain the interaction authority.
