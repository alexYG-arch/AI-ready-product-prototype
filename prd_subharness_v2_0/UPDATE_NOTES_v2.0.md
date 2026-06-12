# 更新说明：PRD Sub-Harness v2.0

## 0. 版本定位

v2.0 在 v1.0 的 orchestrator + 多 sub-harness 基线之上，新增 `prototype_projection_harness` 作为平级 projection harness。

v2.0 继续保留：

```text
instance / run 隔离
extract-source-baseline
structured_source_baseline review
sub_harness_inputs 输入切片
review_decision / promote-approved
PRD.md 只作为 projection
```

v2.0 新增：

```text
prototype.runtime.json
figma-sync-map.yaml
figma-interaction-map.yaml
component-binding-map.yaml
design-semantic-library.json
patch_control_v2.yaml
Figma diff report / candidate flow
```

---

## 1. 新增 Prototype Projection Harness

`prototype_projection_harness` 负责：

```text
structured PRD facts → prototype.runtime.json
prototype.runtime.json → Figma frames / reactions / Flow Map / Interaction Spec
Figma semantic diff → figma_diff_report → change_patch_candidate
```

它不负责：

```text
确认产品需求
确认页面事实
确认指标或事件事实
反向修改 PRD.md
直接写 requirements/screens/metrics/events
```

---

## 2. Stage Contracts

v2.0 保留并纳入校验的原型 stage：

```text
Stage 1: 接入 prototype_projection_harness 和文档注册
Stage 2: 生成 prototype.runtime.json，不写 Figma
Stage 3: 生成低保真 Figma frame + reaction + Flow Map
Stage 4: 接入真实 component / pattern binding
Stage 5: 接入 Figma diff ingest 和 Patch Control v2
```

对应 patch contracts：

```text
PROTO-008 runtime model generation
PROTO-009 Figma forward projection
PROTO-010 Figma diff ingest
PROTO-011 interaction graph consistency
```

---

## 3. Validator 升级

`harnessctl.py validate-rule-specs` 现在支持两类 validator：

```text
v1.0 flat validators: 现有事实 harness 继续使用
v2.0 grouped validators: prototype harness 使用 runtime / interaction / component / figma sync 分组
```

`prototype_projection_harness/validators.yaml` 包含 20 条 PROTO validators，并通过 `HARNESS_RULE_REVIEW.md` 与 `harness_rule_review_crosswalk.yaml` 映射到 `PROTO-GEN-*` 人审规则。

---

## 4. 本地校验

```bash
python3 scripts/prd_control/harnessctl.py status
python3 scripts/prd_control/harnessctl.py validate-rule-specs
python3 scripts/prd_control/harnessctl.py validate-fixtures
python3 scripts/prd_control/harnessctl.py validate-prd-template
python3 scripts/prd_control/harnessctl.py check-prd-sync
python3 scripts/prd_control/prototypectl.py status
python3 scripts/prd_control/prototypectl.py validate-runtime
python3 scripts/prd_control/prototypectl.py validate-interactions
```
