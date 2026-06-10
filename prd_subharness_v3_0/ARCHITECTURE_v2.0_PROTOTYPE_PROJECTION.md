# 架构说明 v2.0：Prototype Projection Harness

## 1. 设计目标

v2.0 在 v1.0 的 PRD sub-harness 架构上增加 Figma 原型投射能力。目标不是做一个独立于 PRD 的设计稿生成器，而是建立：

```text
structured PRD facts
→ prototype runtime model
→ Figma frames / components / reactions / flow map
```

同时建立反向链路：

```text
Figma semantic diff
→ figma_diff_report
→ change_patch_candidate
→ prd_orchestrator route
→ owner fact harness
→ structured facts
→ PRD.md / Figma re-projection
```

---

## 2. 不变的架构原则

v1.0 中最重要的规则保持不变：

```text
orchestrator 不生成产品事实；
sub_harness 只拥有自己的专业域；
PRD.md 是 projection，不是事实源；
patch 必须可审计、可回滚、可 review。
```

v2.0 只是新增一个投影域：

```text
projection_sync_harness       owns YAML → PRD.md
prototype_projection_harness  owns runtime → Figma
```

---

## 3. 子 Harness 分层

```text
Fact Harnesses
  prd_core_harness
  requirement_harness
  screen_state_harness
  metrics_events_harness
  release_ops_harness
  traceability_harness

Projection Harnesses
  projection_sync_harness
  prototype_projection_harness
```

`prototype_projection_harness` 不拥有需求事实、页面事实或指标事实。它拥有的是：

```text
prototype_runtime_model
figma_projection_plan
figma_node_map
figma_interaction_map
component_binding
pattern_binding
figma_diff_ingest
prototype_projection_reports
```

---

## 4. Runtime Model 分层

原型 runtime 是中间模型，不是业务事实源。

```text
requirements.yaml
screens.yaml
metrics.yaml
events.yaml
traceability.md
component-binding-map.yaml
design-semantic-library.json
        ↓
prototype.runtime.json
        ↓
Figma projection
```

runtime 中必须显式包含：

```text
flows
screens
screen states
overlays
variables
component instances
interaction_graph.nodes
interaction_graph.edges
source_refs
prototype_gaps
```

---

## 5. Figma 投射层

Figma 投射由三类结果组成：

```text
1. Frame projection
   普通页面、页面状态、overlay、toast、modal。

2. Reaction projection
   将 interaction_graph.edges[] 写成 Figma node reactions。

3. Documentation projection
   生成 Flow Map / Interaction Spec，解释 trigger、guard、action chain、event、source_refs。
```

重要边界：

```text
Figma 中真实可播放交互 = node reactions。
Figma 中说明箭头 / 文本标注 = documentation，不等于真实交互。
```

---

## 6. Figma 反向同步

Figma 修改不能直接写 PRD facts。它必须被分级：

```text
visual_only
semantic_candidate
high_risk_candidate
ignored_generated_noise
conflict
```

然后生成：

```text
figma_diff_report
change_patch_candidate
```

由 `prd_orchestrator` 路由到：

```text
requirement_harness
screen_state_harness
metrics_events_harness
traceability_harness
```

---

## 7. 三向 Diff

反向同步必须比较三个模型：

```text
A = 上一次投射时的 prototype.runtime.json
B = 当前 Figma semantic extract
C = 当前 PRD structured facts 重新生成的 runtime
```

判断：

```text
A → B = Figma 侧改动
A → C = PRD 侧改动
B ↔ C = 冲突或可合并
```

同一 semantic field 两边都改时，必须生成 review decision，不得自动覆盖。

---

## 8. Patch Control v2

Patch Control v2 扩展了 v1.0 的自然语言 change request，使它能处理：

```text
natural_language
structured_yaml
figma_diff
prototype_runtime
generated_projection
```

但无论来源是什么，最终进入事实层都必须走：

```text
candidate → review → approved patch → owner harness write → projection rerun
```

---

## 9. Prototype Stage Contract

v2.0 的原型能力必须按 stage 保留和校验，不能把规则压平成单一说明文档：

```text
Stage 1: 注册 prototype_projection_harness 和文档权威边界
Stage 2: 从 structured facts 生成 prototype.runtime.json，不写 Figma
Stage 3: 从 runtime 投射低保真 Figma frames、reactions、Flow Map、Interaction Spec
Stage 4: 接入真实 component / pattern binding，无法绑定时生成 gap
Stage 5: Figma semantic diff → figma_diff_report → change_patch_candidate → owner harness review
```

对应 contract：

```text
PROTO-008 runtime model generation
PROTO-009 Figma forward projection
PROTO-010 Figma diff ingest
PROTO-011 interaction graph / reaction map consistency
```

---

## 10. 最小工程闭环

```text
需求更新
→ owner fact harness 写 structured facts
→ projection_sync_harness 更新 PRD.md
→ prototype_projection_harness 生成 runtime
→ prototype_projection_harness 投射 Figma frames/reactions
→ designer 修改 Figma
→ prototype_projection_harness 提取 diff
→ prd_orchestrator 生成 candidate
→ owner fact harness 决策
```
