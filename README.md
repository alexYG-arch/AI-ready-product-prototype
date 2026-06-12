# AI-ready Product PRD Sub-Harness

本仓库是 **AI-ready PRD 子 Harness 架构 v2.1** 的工程包。它把单体 PRD mini harness 拆成一个总控 Orchestrator 和多个专业 subharness，用来管理旧 PRD 迁移、自然语言变更、结构化需求、页面状态、指标埋点、发布计划、追踪矩阵、`PRD.md` 同步，以及 prototype runtime / Figma 原型投射。

核心原则很简单：

- LLM 只能生成 candidate，不能直接生成 confirmed fact。
- Validator 可以阻断不合格产物。
- 高风险变更必须人工 review。
- 人工批准前，不得写入 instance `product-spec/`、关闭 open question、确认 metric target 或 tombstone item。
- 真实 PRD 的输入、候选、报告和输出放在独立 `prd_instances/<instance_id>/`，不要污染 harness 工程包。
- `prototype_projection_harness` 只做投影和 diff candidate，不拥有需求、页面、指标、事件或 `PRD.md` 事实。

当前默认工程入口在 [`prd_subharness_v2_1/`](prd_subharness_v2_1/)；[`prd_subharness_v2_0/`](prd_subharness_v2_0/) 保留为 v2.0 回滚基线，[`prd_subharness_v1_0/`](prd_subharness_v1_0/) 保留为 v1.0 回滚基线。

## 快速开始

安装校验依赖：

```bash
cd prd_subharness_v2_1
python3 -m pip install -r requirements-dev.txt
```

检查 harness 基线：

```bash
python3 scripts/prd_control/harnessctl.py status
python3 scripts/prd_control/harnessctl.py validate-rule-specs
python3 scripts/prd_control/harnessctl.py validate-fixtures
python3 scripts/prd_control/prototypectl.py status
python3 scripts/prd_control/prototypectl.py validate-runtime
python3 scripts/prd_control/prototypectl.py validate-interactions
python3 scripts/prd_control/prototypectl.py validate-uxwriter --catalog sub_harnesses/prototype_projection_harness/examples/uxwriter-copy-catalog.sample.yaml
python3 scripts/prd_control/prototypectl.py validate-layout --plan sub_harnesses/prototype_projection_harness/examples/layout-route-plan.sample.yaml
python3 scripts/prd_control/prototypectl.py validate-comments --map sub_harnesses/prototype_projection_harness/examples/figma-comment-map.yaml
```

创建真实 PRD instance：

```bash
python3 scripts/prd_control/harnessctl.py init-instance ../prd_instances/my-product-prd --instance-id my-product-prd
```

首次导入旧 PRD 时，先提取源文档基线并人工 review：

```bash
python3 scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-INITIAL-001 extract-source-baseline inputs/legacy_prd.md
python3 scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-INITIAL-001 unified-review
python3 scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-INITIAL-001 core-review-md
```

日常自然语言变更走 change request 链路：

```bash
python3 scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 route-change inputs/change_requests/CR-001.md
python3 scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 classify-change inputs/change_requests/CR-001.md
python3 scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 impact PRD-DELTA-001
python3 scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 rerun-plan PRD-DELTA-001
python3 scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 quality-gate
python3 scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 unified-review
```

## 架构总览

```text
prd_subharness_v2_1/
  prd_orchestrator/
    routing_rules.yaml
    harness_registry.yaml
    dependency_graph.yaml
    impact_rules.yaml
    review_decisions/
    tombstones/

  sub_harnesses/
    prd_core_harness/
    requirement_harness/
    screen_state_harness/
    metrics_events_harness/
    release_ops_harness/
    projection_sync_harness/
    traceability_harness/
    prototype_projection_harness/
```

Orchestrator 只负责接收源 PRD 或变更请求、路由、影响分析、局部重跑计划、review/tombstone 记录和多文档隔离。它不生成产品事实。

Subharness 负责各自领域的候选产物、validator、patch contract、上下文包和人工 review 输入。

## Subharness 能力、场景和规则

| Subharness | 核心能力 | 典型使用场景 | 使用规则 |
|---|---|---|---|
| `prd_core_harness` | 管理背景、问题、用户、目标、范围、非目标、风险和开放问题。 | 首次迁移旧 PRD 的核心事实盘点；补齐产品目标或范围边界；识别未知信息和 open question。 | 不能批准 C-EARS 细节、页面状态、指标埋点或发布灰度。CORE-000 只生成核心事实候选，必须经 `core-review-md` 和 review decision 后才能晋升。 |
| `requirement_harness` | 将需求整理为 pattern-based C-EARS、语义槽、fit criteria、验收、verification 和 gaps。 | 自然语言需求拆分；登录、验证码、权限、异常处理等功能需求结构化；P0/P1 需求质量检查。 | C-EARS 不是单一句式模板，必须先选 pattern，再补 required slots。缺来源、缺槽、缺验收或缺数值化时必须进入 gaps/open question。不能处理页面视觉、完整 PRD 投影或发布计划。 |
| `screen_state_harness` | 管理页面语义、入口出口、状态推理链、异常路径、恢复、文案和可访问性。 | 补齐 loading/empty/error/offline/permission/retry 状态；明确页面入口出口；为异常路径生成用户可见反馈和恢复路径。 | 关键路径状态必须有任务、触发、系统操作、结果、页面状态、恢复和验收/事件观测。不能批准需求、metric target 或发布计划。 |
| `metrics_events_harness` | 管理指标、baseline、target、needs_instrumentation、事件、漏斗和实验。 | 定义北极星指标、转化漏斗、埋点事件、实验 guardrail；判断当前是否可测或需要补埋点。 | baseline 和 target 必须有来源；缺数据时写 `needs_instrumentation`、`proxy_only`、`qualitative_prelaunch` 或 `blocked`，不能凭空生成 target。不能处理页面状态、需求批准或发布回滚。 |
| `release_ops_harness` | 管理灰度、监控、回滚、运营、客服和发布条件。 | 上线前准备；灰度策略；监控和告警；回滚条件；客服 FAQ/运营口径。 | GA、回滚条件、客服口径等高风险项必须人工 review。不能改需求语句、页面状态或埋点口径。 |
| `projection_sync_harness` | 将结构化 YAML 投影为完整 14 章 `PRD.md`，并校验模板结构和同步覆盖。 | 从 `requirements.yaml`、`screens.yaml`、`metrics.yaml`、`events.yaml` 等生成可读 PRD；检查 PRD 是否只有标题或占位符；同步 YAML 到 Markdown。 | `PRD.md` 只是事实投影，不能反向创造 confirmed fact，不能关闭 open question。每章事实必须能回链到允许来源。 |
| `traceability_harness` | 管理追踪矩阵、依赖图、影响分析、局部重跑计划和 tombstone。 | 评估变更影响；确认目标、需求、页面、事件、测试、监控之间的覆盖关系；删除需求后的 tombstone 和局部重跑。 | 不能生成需求内容或批准产品决策。任何 requirement/screen/metric/event/release/delete 变更都应有 impact analysis 和 partial rerun plan。 |
| `prototype_projection_harness` | 管理 two-pass prototype runtime、renderer stage plan、Figma frame/reaction/comment/line 投射、component binding、Figma diff candidate。 | 从 structured facts 生成可交互原型；校验 runtime/interaction/UX writer/layout/comments；把 Figma 修改回流为 candidate。 | 原型和 Figma 不是事实源；comments 和 visual lines 只是审阅/说明层；Figma diff 只能生成 report/candidate，必须经 owner harness review 后才能改事实。 |

## 场景路由

### 首次导入完整旧 PRD

```text
source PRD
→ extract-source-baseline
→ extraction review
→ structured_source_baseline
→ sub_harness_inputs
→ CORE-000 / CORE-001 / CORE-002
→ REQ-003A / REQ-003B / REQ-003C
→ SCREEN-004
→ DATA-005
→ TRACE-006
→ PROJ-007
```

规则：完整旧 PRD 只在入口处做一次结构化提取和人工 review。评审通过后，各 subharness 消费自己的 `sub_harness_inputs/<harness>.yaml`，不要重复直接读取散装源 PRD。

### 日常自然语言小改

```text
change_request.md
→ CHANGE-INGEST
→ route to sub-harness
→ PRD-DELTA
→ impact
→ rerun-plan
→ quality-gate
→ unified-review
→ promote-approved
→ PROJ sync
```

规则：`route-change` / `classify-change` 只用于日常小改，不用于首次完整 PRD 迁移。

### 一个 Markdown 内有多项变更

```text
CHANGE-INGEST
→ atomic changes
→ split recommendation
→ multiple PRD-DELTA patches
```

规则：登录、支付、会员、指标、页面、发布等多域变更不要压成一个 patch。先拆原子变更，再分别路由和 review。

### 回答 open question

```text
review_decision
→ requirement_harness 003C
→ impacted sub-harnesses
→ projection_sync_harness
```

规则：人工答案必须绑定 artifact path 和 sha256。只有 approved artifact 才能 promote。

### 补页面状态

```text
screen_state_harness
→ traceability_harness
→ projection_sync_harness
```

规则：页面状态变化要回连需求、验收或事件；非成功状态必须有用户可见反馈和恢复路径。

### 改指标或埋点

```text
metrics_events_harness
→ traceability_harness
→ projection_sync_harness
```

规则：新增 target、baseline、事件属性、实验 guardrail 时要有来源或明确标记为待补埋点。

### 准备上线

```text
release_ops_harness
→ traceability_harness
→ projection_sync_harness
```

规则：灰度、监控、回滚、客服和运营准备度必须可执行、可发现问题、可回退。

### 只更新 PRD.md 可读表达

```text
projection_sync_harness
```

规则：只允许从结构化事实投影到 `PRD.md`，不得在 Markdown 中新增 YAML 没有的 confirmed fact。

### 更新或生成可交互原型

```text
structured facts
→ prototype_projection_harness
→ prototype.runtime.json
→ figma-sync-map.yaml / figma-interaction-map.yaml
→ Figma frames / reactions / Flow Map / Interaction Spec
```

规则：runtime 只能从结构化事实和受控 binding 生成；真实可点击交互必须来自 `interaction_graph.edges[]`。

### Figma 修改回流

```text
Figma semantic diff
→ figma_diff_report
→ change_patch_candidate
→ prd_orchestrator route
→ owner fact harness review
```

规则：Figma 修改不得直接写 `requirements.yaml`、`screens.yaml`、`metrics.yaml`、`events.yaml` 或 `PRD.md`。

## 使用规则

### 1. 人工 Review 门槛

以下动作必须有 review decision：

- candidate 转 confirmed
- 写入 instance `product-spec/`
- 关闭 open question
- 确认 metric target
- 改变 cross-document authority
- 删除或 tombstone item

`review-decision` 记录 artifact path、sha256、decision、reviewer 和 notes。`promote-approved` 会重新校验 path 与 sha256，只有匹配 approved 决策的 artifact 才能提升。

### 2. Instance 与 Run 隔离

`prd_subharness_v2_0/` 是当前 harness 工程包，只存放规则、contract、validator、模板和脚本。真实 PRD 输入、候选、报告、impact、rerun plan、日志和输出应放在：

```text
prd_instances/<instance_id>/
  inputs/
  product-spec/
  runs/<run_id>/
  outputs/
```

仓库默认忽略 `prd_instances/`，避免真实 PRD 输入/输出混入 harness 基线。

### 3. 路由规则

Orchestrator 会按关键词和 ownership 路由：

- 目标、范围、背景、用户、风险 -> `prd_core_harness`
- 需求、功能、C-EARS、验收、验证码、登录 -> `requirement_harness`
- 页面、状态、错误、失败、重试、文案、可访问性 -> `screen_state_harness`
- 指标、埋点、事件、baseline、target、漏斗、实验 -> `metrics_events_harness`
- 发布、灰度、回滚、监控、客服、FAQ、运营 -> `release_ops_harness`

未匹配内容默认进入 open question，由 `prd_core_harness` 承接。

### 4. Worktree 规则

默认不为每个 subharness 常驻启用单独 worktree。普通 PRD 运行用 instance/run 隔离即可。只有多人或多个 agent 并行修改不同 subharness 规则、validator、schema，或进行高风险规则实验时，才临时启用 subharness worktree。

## 推荐阅读顺序

- PM / 需求评审者：[`prd_subharness_v2_0/USER_GUIDE_NON_BUILDERS.md`](prd_subharness_v2_0/USER_GUIDE_NON_BUILDERS.md)
- 场景路径：[`prd_subharness_v2_0/SCENARIO_PATHS.md`](prd_subharness_v2_0/SCENARIO_PATHS.md)
- 架构说明：[`prd_subharness_v2_0/ARCHITECTURE_v2.0_PROTOTYPE_PROJECTION.md`](prd_subharness_v2_0/ARCHITECTURE_v2.0_PROTOTYPE_PROJECTION.md)
- Codex 执行：[`prd_subharness_v2_0/EXECUTION_GUIDE_CODEX.md`](prd_subharness_v2_0/EXECUTION_GUIDE_CODEX.md)
- LLM Runtime 执行：[`prd_subharness_v2_0/EXECUTION_GUIDE_LLM_RUNTIME.md`](prd_subharness_v2_0/EXECUTION_GUIDE_LLM_RUNTIME.md)
- 搭建者指南：[`prd_subharness_v2_0/BUILDER_SETUP_GUIDE.md`](prd_subharness_v2_0/BUILDER_SETUP_GUIDE.md)

## 当前状态

该版本定位为 v2.0 harness 工程基线。v1.0 规则治理、source baseline、instance/run 隔离继续保留；v2.0 新增 prototype projection、Figma reaction map、Figma diff candidate 和 Patch Control v2。
