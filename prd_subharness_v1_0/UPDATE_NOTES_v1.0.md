# 更新说明：PRD Sub-Harness v1.0

## 0. 版本定位

v1.0 是从 v0.3 演进而来的“子 harness 架构版”。

v0.3 解决了：

```text
自然语言变更入口
多文档隔离
辅助式影响规划
局部重跑计划
C-EARS+RQV 质量关口
```

但 v0.3 仍然存在三个明显问题：

```text
1. product-spec/PRD.md 可能只保留大纲，未完整投影 YAML 内容。
2. C-EARS 容易变成模板化句式，不能表达多种需求类型。
3. 所有能力堆在一个 mini harness 中，体积变大，维护难度上升。
```

v1.0 的目标是拆分。

---

## 1. 架构升级

### v0.3

```text
一个 PRD mini harness
  ├─ change ingest
  ├─ requirements
  ├─ screens
  ├─ metrics/events
  ├─ traceability
  ├─ projection
  └─ impact
```

### v1.0

```text
prd_orchestrator
  ├─ routes change request
  ├─ controls documents
  ├─ computes impact
  ├─ schedules partial rerun
  └─ delegates to sub-harnesses

sub_harnesses
  ├─ prd_core_harness
  ├─ requirement_harness
  ├─ screen_state_harness
  ├─ metrics_events_harness
  ├─ release_ops_harness
  ├─ projection_sync_harness
  └─ traceability_harness
```

---

## 2. 新增子 harness

### 2.1 `prd_core_harness`

负责：

```text
TL;DR
背景与问题
用户与场景
目标与范围
Scope / Non-goals
风险、依赖、开放问题
```

### 2.2 `requirement_harness`

负责：

```text
需求表达
requirement patterns
C-EARS+RQV
semantic slots
fit criteria
acceptance
verification
gaps
open questions
```

### 2.3 `screen_state_harness`

负责：

```text
页面语义
页面目的
入口 / 出口
状态推理链
异常路径
恢复路径
文案
可访问性
```

### 2.4 `metrics_events_harness`

负责：

```text
目标与指标
baseline / target
needs_instrumentation
guardrail metrics
events
funnels
experiments
```

### 2.5 `release_ops_harness`

负责：

```text
灰度策略
发布计划
监控
回滚
FAQ
客服话术
运营准备
```

### 2.6 `projection_sync_harness`

负责：

```text
YAML → PRD.md 完整投影
PRD 14 章模板
PRD 内容覆盖校验
PRD 未来源事实阻断
```

### 2.7 `traceability_harness`

负责：

```text
Goal → Req → Screen → Event → Test
dependency graph
impact analysis
partial rerun plan
tombstone
change_patch
```

---

## 3. PRD.md 完整模板对齐

v1.0 将 `product-spec/PRD.md` 替换为完整 14 章模板：

```text
1. TL;DR
2. 背景与问题
3. 用户与场景
4. 目标与指标
5. Scope / Non-goals
6. 体验方案摘要
7. 页面语义说明
8. 功能需求
9. 非功能需求
10. 数据与实验
11. 验收标准
12. 发布计划
13. 风险、依赖、开放问题
14. 变更记录
```

并新增：

```text
sub_harnesses/projection_sync_harness/prd_template_profile.yaml
sub_harnesses/projection_sync_harness/prd_section_projection_map.yaml
```

---

## 4. Requirement Pattern Registry

v1.0 不再把 C-EARS 理解为一种固定句式，而是增加：

```text
sub_harnesses/requirement_harness/requirement_pattern_registry.yaml
```

支持：

```text
event_driven
state_driven
conditional
exception_handling
data_rule
permission_privacy
non_functional_fit_criteria
experiment
release_rule
compliance
```

---

## 5. 使用策略升级

v1.0 继续默认使用：

```text
Assisted Automation / 辅助自动化
```

也就是：

```text
LLM 提候选；
规则做计算；
Validator 做阻断；
人批准高风险。
```

禁止默认 full auto。

---

## 6. 从 v0.3 升级到 v1.0

### Step 1：复制 `sub_harnesses/`

新增所有子 harness 目录。

### Step 2：移动配置

从 v0.3 移动或引用：

```text
cears_quality_profile.yaml → requirement_harness
impact_rules.yaml → traceability_harness + orchestrator
PRD.md template → projection_sync_harness
```

### Step 3：替换 PRD.md

用 v1.0 的完整模板替换简化模板。

### Step 4：开始走子 harness 路由

自然语言变更不直接进入单体 patch，而是先由 orchestrator 判断：

```text
这项变更属于 core / requirement / screen / metrics / release / projection / traceability 哪个子 harness？
```

### Step 5：投影同步

每轮结构化 YAML 更新后，都由：

```text
projection_sync_harness
```

同步到 `PRD.md`。

---

## 7. v1.0 验收标准

```text
[ ] PRD.md 是完整 14 章模板。
[ ] PRD.md 不只是标题和占位符。
[ ] requirements.yaml 的 P0/P1 能投影到 PRD.md 第 8/11 章。
[ ] screens.yaml 能投影到 PRD.md 第 7 章。
[ ] metrics.yaml / events.yaml 能投影到 PRD.md 第 4/10 章。
[ ] release-plan.md 能投影到 PRD.md 第 12 章。
[ ] C-EARS 使用 pattern registry，而不是单一模板。
[ ] 每个子 harness 有自己的 contract、validators、patch queue。
[ ] orchestrator 不生成事实，只路由、调度、记录影响。
```
