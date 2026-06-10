# 架构说明：Orchestrator + 子 Harness

## 1. 总体结构

```text
prd_orchestrator/
  harness_registry.yaml
  patch_queue.yaml
  document_registry.yaml
  dependency_graph.yaml
  impact_rules.yaml
  automation_policy.yaml
  routing_rules.yaml

sub_harnesses/
  prd_core_harness/
  requirement_harness/
  screen_state_harness/
  metrics_events_harness/
  release_ops_harness/
  projection_sync_harness/
  traceability_harness/
```

## 2. Orchestrator 负责什么？

Orchestrator 不生成产品事实。它只负责：

```text
接收完整源 PRD；
生成 structured_source_baseline 候选；
组织源文档提取评审；
接收 change_request；
识别变更类型；
路由到子 harness；
维护多文档隔离；
维护依赖图；
生成影响分析；
生成局部重跑计划；
记录 patch、review、tombstone。
```

## 3. 子 Harness 负责什么？

每个子 harness 都是一个小系统，至少包含：

```text
harness_contract.yaml
README.md
validators.yaml
patch_contracts/
context_packs/
schemas/
fixtures/
reports/
```

## 4. 数据流

第一次完整旧 PRD 迁移：

```text
source PRD markdown
→ orchestrator extract-source-baseline
→ human extraction review
→ structured_source_baseline
→ sub_harness_inputs/<harness>.yaml
→ sub_harnesses consume their reviewed input slices
→ sub_harnesses produce product-spec candidates
→ traceability_harness
→ projection_sync_harness updates PRD.md
```

日常变更：

```text
change_request.md
→ orchestrator classify
→ route to sub_harness
→ sub_harness produces structured output
→ traceability_harness updates impact
→ projection_sync_harness updates PRD.md
```

## 5. 子 Harness 边界

| 子 Harness | 负责 | 不负责 |
|---|---|---|
| prd_core | 目标、用户、范围、风险 | C-EARS 细节、页面状态 |
| requirement | 需求表达和质量 | 页面布局、发布计划 |
| screen_state | 页面语义和状态 | 指标 target、发布灰度 |
| metrics_events | 指标、事件、实验 | 页面文案、需求批准 |
| release_ops | 灰度、监控、回滚 | C-EARS 需求质量 |
| projection_sync | YAML → PRD.md | 新增事实、关闭问题 |
| traceability | 追踪、影响、局部重跑 | 生成需求内容 |
