# PRD Sub-Harness v2.0 Prototype Projection 工程优化方案包

版本：v2.0-prototype-projection  
基线：`prd_subharness_v1_0`  
目标：在不破坏 v1.0 `prd_orchestrator + 多 sub_harness` 边界的前提下，新增 Figma 原型投射、交互连线投射、Figma 反向 diff 和 Patch Control v2。

---

## 1. 总体结论

本方案不把 PRD sub-harness 集合降格，也不把 PRD harness 与原型 harness 合并成一个大 harness。

正确工程形态是：

```text
prd_orchestrator
  ├─ fact harnesses
  │   ├─ prd_core_harness
  │   ├─ requirement_harness
  │   ├─ screen_state_harness
  │   ├─ metrics_events_harness
  │   ├─ release_ops_harness
  │   └─ traceability_harness
  │
  └─ projection harnesses
      ├─ projection_sync_harness       # YAML → PRD.md
      └─ prototype_projection_harness  # Runtime → Figma frames/reactions/flow map
```

`prototype_projection_harness` 是一个平级 projection harness。它可以生成原型 runtime、Figma 节点绑定、Figma interaction map、Figma diff report；但它不能直接修改产品事实。

---

## 2. 方案包包含什么

新增或修改的核心文件：

```text
OPTIMIZATION_PACKAGE_README.md
ARCHITECTURE_v2.0_PROTOTYPE_PROJECTION.md
MIGRATION_PLAN_v1_0_to_v2_0.md
PACKAGE_MANIFEST_v2.0.md

prd_orchestrator/
  harness_registry.yaml                         # 增加 prototype_projection_harness
  routing_rules.yaml                            # 增加 Figma/prototype/interaction 路由词
  impact_rules.yaml                             # 增加 prototype downstream 和 reverse sync 约束
  dependency_graph.yaml                         # 增加 runtime / Figma map / figma diff 依赖
  document_registry.yaml                        # 增加 prototype runtime 和 Figma map 文档权威边界
  patch_control_v2.yaml                         # 新增统一 patch control v2
  templates/change_patch_candidate.v2.template.yaml
  templates/figma_diff_patch_candidate.template.yaml
  templates/prototype_projection_plan.template.yaml
  figma_diff_reports/.gitkeep
  prototype_projection_reports/.gitkeep

product-spec/
  prototype.runtime.json
  figma-sync-map.yaml
  figma-interaction-map.yaml
  component-binding-map.yaml
  design-semantic-library.json

sub_harnesses/prototype_projection_harness/
  README.md
  harness_contract.yaml
  prototype_runtime_profile.yaml
  runtime_generation_rules.yaml
  figma_projection_rules.yaml
  interaction_projection_rules.yaml
  figma_reaction_mapping.yaml
  component_binding_policy.yaml
  pattern_projection_rules.yaml
  figma_diff_policy.yaml
  reverse_sync_policy.yaml
  validators.yaml
  patch_contracts/
    PROTO-008-runtime-model.yaml
    PROTO-009-figma-forward-projection.yaml
    PROTO-010-figma-diff-ingest.yaml
    PROTO-011-interaction-graph.yaml

schemas/
  prototype_runtime.schema.json
  figma_sync_map.schema.json
  figma_interaction_map.schema.json
  figma_diff_patch_candidate.schema.json

scripts/prd_control/prototypectl.py
```

---

## 3. 核心规则

1. `PRD.md` 继续只是 narrative projection，不能作为 structured fact 来源。
2. Figma 原型是 interactive projection，不能作为 confirmed fact 来源。
3. Figma 修改只能生成 semantic diff candidate，再由 `prd_orchestrator` 路由给 owner harness。
4. 原型 runtime 只能从结构化事实和受控 binding 生成。
5. Figma 蓝色原型连线必须由 `interaction_graph.edges[]` 投射为 node reactions。
6. Flow Map / Interaction Spec 中的说明线只是审阅辅助，不等于真实交互。
7. 组件优先使用已有 Figma design system component，其次 pattern，再其次 JSON 语义库 fallback，最后 placeholder。
8. 反向同步必须做三向 diff：上次 runtime、当前 Figma semantic extract、当前 PRD runtime。

---

## 4. 最小落地顺序

```text
Phase 1: 接入 prototype_projection_harness 和文档注册
Phase 2: 生成 prototype.runtime.json，不写 Figma
Phase 3: 生成低保真 Figma frame + reaction + Flow Map
Phase 4: 接入真实 component / pattern binding
Phase 5: 接入 Figma diff ingest 和 Patch Control v2
```

---

## 5. 本地校验命令

```bash
pip install -r requirements-dev.txt

python scripts/prd_control/harnessctl.py status
python scripts/prd_control/prototypectl.py status
python scripts/prd_control/prototypectl.py validate-runtime
python scripts/prd_control/prototypectl.py validate-interactions
```
