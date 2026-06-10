# Prototype Projection Harness

## 1. 定位

`prototype_projection_harness` 是 v2.0 新增的平级 projection harness。它负责：

```text
structured PRD facts → prototype.runtime.json → Figma frames / reactions / flow map
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
```
