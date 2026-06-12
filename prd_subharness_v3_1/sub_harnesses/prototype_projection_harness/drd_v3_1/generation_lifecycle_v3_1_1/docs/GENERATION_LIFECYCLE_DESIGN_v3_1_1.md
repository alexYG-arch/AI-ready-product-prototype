# Prototype Harness Generation Lifecycle Design v3.1.1

## 1. 目标

v3.1.1 的目标是补齐首轮生成生命周期，让每个 stage 都有明确的 generate contract，不再因为 required artifact 不存在而直接由 validator block。

## 2. 核心链路

```text
Stage Plan
  ↓
Stage Generation Controller（阶段生成控制器）
  ↓
Build Crew Generator（建设队生成器）
  ↓
Stage Generator Worker（阶段生成工种）
  ↓
Generated Artifact（生成产物）
  ↓
Self-check（自检）
  ↓
Validator（校验）
  ↓
Loop Controller（反馈回路控制器）
  ↓
Repair Crew Generator（施工队生成器）
  ↓
Dry Run Patch（试施工补丁）
  ↓
Apply Patch（应用补丁）
  ↓
Revalidate（复验）
```

## 3. 三个队伍的区别

| 角色 | 中文 | 触发 | 作用 |
| --- | --- | --- | --- |
| Build Crew | 建设队 | artifact 缺失、为空、上游改变 | 首轮生成最小可校验产物 |
| Validator | 校验器 | artifact 已存在 | 校验 schema、语义、来源、边界 |
| Repair Crew | 施工队 / 修补队 | artifact 存在但不合格 | 最小范围修补已有产物 |

## 4. 为什么不能用 Repair Crew 做首轮生成

Repair Crew 的输入是 finding，也就是 validator / audit 发现的问题。如果 artifact 根本不存在，finding 只能说“缺 artifact”，无法知道 artifact 内部应该修哪个字段。

因此：

```text
artifact missing → Build Crew
artifact invalid → Repair Crew
artifact unreadable → Regenerator
```

## 5. 生成层的产物边界

Build Crew 可以生成：

- source slices
- surface decisions
- screen role obligations
- design kernel
- composition plan
- frame packets
- hotspots
- sidecar cards
- annotation stubs
- anchor badges
- leader lines
- projection report

Build Crew 不可以生成：

- PRD.md
- requirements.yaml
- screens.yaml
- metrics.yaml
- events.yaml
- confirmed product fact store
- human approval

## 6. 每个 stage 的 generate contract

每个 stage 都必须声明：

```yaml
generate_contract:
  generator_id: GEN-...
  generate_when:
    - artifact_missing
    - artifact_empty
    - upstream_hash_changed
  inputs:
    required: []
    optional: []
  outputs: []
  algorithm: []
  minimum_viable_output:
    required_fields: []
  self_check: []
  forbidden: []
  on_generate_failure:
    action: emit_generation_gap
  generation_trace:
    required: true
```

## 7. 生成失败如何处理

生成失败不能返回空 YAML，也不能伪造产物。

必须输出：

```text
generation_gap_report.yaml
```

包含：

- gap_id
- missing_input
- affected_stage
- severity
- route_zh
- whether_blocking

## 8. 与 v3.1 Repair Crew 的关系

v3.1.1 不替换 v3.1 repair crew。它补在 repair crew 前面。

```text
缺产物 → Build Crew
坏产物 → Repair Crew
严重坏产物 → Regenerator
```
