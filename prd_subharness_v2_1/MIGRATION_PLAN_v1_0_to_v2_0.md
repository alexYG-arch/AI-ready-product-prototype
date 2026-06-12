# v1.0 → v2.0 Prototype Projection 迁移计划

## 0. 迁移原则

不做大重构，不改变 v1.0 已有事实 owner。只新增一个平级 projection harness，并扩展 orchestrator 的 registry、routing、impact、document registry 和 patch control。

---

## Phase 1：注册新 harness

修改：

```text
prd_orchestrator/harness_registry.yaml
prd_orchestrator/routing_rules.yaml
prd_orchestrator/impact_rules.yaml
prd_orchestrator/dependency_graph.yaml
prd_orchestrator/document_registry.yaml
```

新增：

```text
sub_harnesses/prototype_projection_harness/
```

验收：

```bash
python scripts/prd_control/harnessctl.py status
python scripts/prd_control/prototypectl.py status
```

---

## Phase 2：生成 runtime，不写 Figma

新增并维护：

```text
product-spec/prototype.runtime.json
product-spec/component-binding-map.yaml
product-spec/design-semantic-library.json
```

规则：

```text
runtime 只能从 structured facts 和受控 binding 生成；
不得从 PRD.md 反推；
不得从 Figma frame 文案直接确认事实。
```

验收：

```bash
python scripts/prd_control/prototypectl.py validate-runtime
```

---

## Phase 3：低保真 Figma 投射

新增并维护：

```text
product-spec/figma-sync-map.yaml
product-spec/figma-interaction-map.yaml
```

投射内容：

```text
普通页面 frame
主要 screen-state frame
overlay / modal / toast frame
interaction reactions
Flow Map
Interaction Spec
```

验收：

```bash
python scripts/prd_control/prototypectl.py validate-interactions
```

---

## Phase 4：接入 design system component / pattern

按照优先级：

```text
已有 Figma component
→ 已有 Figma pattern/template
→ JSON semantic library composition
→ low-fi placeholder
```

所有无法绑定的组件都必须生成 gap，不能静默退化。

---

## Phase 5：反向同步

新增：

```text
prd_orchestrator/figma_diff_reports/
prd_orchestrator/templates/figma_diff_patch_candidate.template.yaml
prd_orchestrator/patch_control_v2.yaml
```

流程：

```text
Figma diff extract
→ visual / semantic / high-risk 分类
→ change_patch_candidate
→ prd_orchestrator route
→ owner harness review
```

验收：

```text
Figma 修改不会直接写 requirements.yaml / screens.yaml / metrics.yaml / events.yaml / PRD.md。
```

---

## 回滚策略

如果 v2.0 接入失败，只需要移除：

```text
sub_harnesses/prototype_projection_harness/
product-spec/prototype.runtime.json
product-spec/figma-sync-map.yaml
product-spec/figma-interaction-map.yaml
product-spec/component-binding-map.yaml
product-spec/design-semantic-library.json
prd_orchestrator/patch_control_v2.yaml
prd_orchestrator/figma_diff_reports/
```

并从 registry / impact / routing / document registry 中移除 `prototype_projection_harness` 相关条目。已有 PRD fact store 不受影响。
