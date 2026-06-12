# 场景路径表 v2.0

## 场景 1：第一次导入完整旧 PRD

路径：

```text
source PRD → extract-source-baseline → extraction review → structured_source_baseline → sub_harness_inputs → CORE-000 → CORE-001 → CORE-002 → REQ-003A → REQ-003B → REQ-003C → SCREEN-004 → DATA-005 → TRACE-006 → PROJ-007 → PROTO-008 → PROTO-009 → PROTO-011
```

说明：完整旧 PRD 先做一次源文档结构化提取。评审通过后，所有子 Harness 消费自己的 `sub_harness_inputs/<harness>.yaml`，不要各自重复直接读取源 Markdown。

## 场景 2：日常自然语言小改

路径：

```text
change_request.md → CHANGE-INGEST → route to sub-harness → PRD-DELTA → impact → rerun-plan → PROJ sync → PROTO rerun when structured facts changed
```

说明：`route-change` / `classify-change` 只适用于这种日常小改，不适用于场景 1 的首次完整 PRD 迁移。

## 场景 3：一个 MD 多项变更

路径：

```text
CHANGE-INGEST → atomic changes → split recommendation → multiple PRD-DELTA patches
```

## 场景 4：回答 open question

路径：

```text
review_decision → requirement_harness 003C → impacted sub-harnesses → PROJ sync
```

## 场景 5：补页面状态

路径：

```text
screen_state_harness → traceability_harness → projection_sync_harness
```

## 场景 6：改指标或埋点

路径：

```text
metrics_events_harness → traceability_harness → projection_sync_harness
```

## 场景 7：准备上线

路径：

```text
release_ops_harness → traceability_harness → projection_sync_harness
```

## 场景 8：只更新 PRD.md 可读表达

路径：

```text
projection_sync_harness
```

注意：PRD.md 不得反向创造新的 confirmed fact。

## 场景 9：大版本 PRD 替换

路径：

```text
REBASE → baseline compare → impact → partial migration
```

## 场景 10：删除需求

路径：

```text
PRD-DELTA-delete → review_decision → tombstone → impact_analysis → partial_rerun_plan
```
