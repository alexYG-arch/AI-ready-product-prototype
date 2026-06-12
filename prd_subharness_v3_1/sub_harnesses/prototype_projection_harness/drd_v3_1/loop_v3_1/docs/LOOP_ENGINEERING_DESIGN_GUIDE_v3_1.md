# Loop Engineering Design Guide v3.1（反馈回路工程设计指南 v3.1）

> 本文档用于 Codex / 工程实现。所有英文术语首次出现均给出中文翻译。

## 1. Loop（反馈回路）的通用定义

Loop（反馈回路）不是简单 retry（重试）。在 harness 中，loop 是：

```text
Observe（观察）
→ Compare（比较期望与实际）
→ Diagnose（诊断）
→ Route（路由到责任阶段）
→ Repair（修补）
→ Rerun（局部重跑）
→ Revalidate（复验）
→ Exit（退出或升级到人工评审）
```

对应 prototype harness：

```text
Expected Projection State（期望投射状态）
  = PRD facts + source slices + design kernel + materialization rules

Actual Projection State（实际投射状态）
  = board shards + frame packets + sidecar cards + annotations + leader lines + reports

Reconciliation（调和）
  = 将实际投射状态修补到满足期望投射状态
```

## 2. 文献和工程模式迁移

### 2.1 Reconciliation Loop（调和回路）

Kubernetes controller 的核心思想是让 current state（当前状态）靠近 desired state（期望状态）。在 prototype harness 中，desired state 是“PRD 与规则要求必须被表达的状态、说明、热点和审计证据”，actual state 是“当前生成出的 Figma/DRD artifact”。

### 2.2 Retry Policy（重试策略）

Temporal 的 Retry Policy（重试策略）说明 retry 应该是声明式配置，而不是散落在业务代码里的临时逻辑。prototype harness 也应将 retry / rerun / repair 写成 manifest 和 profile，而不是让每个 stage 自行猜测。

### 2.3 Event History（事件历史）

Temporal 的 Event History（事件历史）启发我们记录 loop_manifest：每次 finding、patch、rerun、exit 都要可审计、可复现。

### 2.4 Harness Engineering（Harness 工程）

Agentic harness 的 feedback controls（反馈控制）不只是最终报错，而要产生 LLM 可消费的纠错信号。prototype harness 的 validator 结果也应包含 repair_hint、route_target、rerun_scope。

### 2.5 Retry Safety（重试安全）

重试不能无限发生。必须有 max attempts（最大尝试次数）、idempotency（幂等性）、timeout（超时）、circuit breaker（熔断）和 human review escalation（升级人工评审）。

## 3. Loop 分层

### 3.1 按职责分层

- Inference Loop（推理回路）：修复推理漏项，例如 min/max 边界未展开。
- Design Kernel Loop（设计内核回路）：修复约束时机、最早可修正表面、控件状态义务。
- Materialization Loop（物化回路）：修复已推导但未生成 frame/card/hotspot 的问题。
- Annotation / Sidecar Loop（说明侧车回路）：修复说明、锚点、sidecar card、annotation stub。
- Layout Loop（布局回路）：修复版面密度、leader line、badge、侧栏溢出。
- Validation Repair Loop（校验修补回路）：把 validator failure 转成 repair plan。
- Governance Loop（治理回路）：防止越权写 PRD、无限 loop、skill 覆盖事实。

### 3.2 按执行范围分层

- Stage Micro-loop（阶段内微循环）：当前 stage 内 generate → validate → patch → revalidate。
- Adjacent Stage Loop（相邻阶段回流）：下游问题回到最近责任阶段。
- Board / Page Shard Loop（画布/页面分片回路）：只重跑受影响的 board shard。
- Harness Macro-loop（整体 Harness 大回路）：汇总所有 finding 并执行全局迭代。
- Human Review Loop（人工评审回路）：超过自动修补边界时停止并请求人工确认。

## 4. Loop Profile（回路配置档位）

三档 Loop Profile 不是不可变的硬编码规则。它们是由任务复杂度推导出来的默认策略，可通过 `loop_profile_policy.yaml` 配置覆盖。

- Simple（简单）：单页面、少状态、无约束、无系统交接。
- Standard（标准）：多状态、常规表单、轻量反馈、普通分支。
- Complex（复杂）：系统交接、权限、min/max 边界、异步、恢复、高风险动作。

## 5. 标准 loop contract

每个 stage 的 loop contract（回路契约）必须包含：

```yaml
loop:
  enabled: true
  loop_layer: inference_loop
  triggers: []
  diagnose: []
  repair_actions: []
  writes: []
  forbidden_writes: []
  rerun_scope: {}
  revalidate: []
  exit_conditions: []
  max_iterations: 2
```

## 6. 安全边界

- loop 默认只修补 materialization artifacts（物化产物）。
- loop 不直接写 PRD.md / requirements.yaml / screens.yaml / metrics.yaml / events.yaml。
- 每个 patch 必须有 finding_id 或 validator_id。
- 每次 loop 必须记录 before_hash / after_hash。
- 超过 max_iterations 必须停止并进入 human review。
