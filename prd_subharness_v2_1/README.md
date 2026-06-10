# PRD Sub-Harness v2.1

中文名：AI-ready PRD 子 Harness 架构 2.1  
版本：v2.1  
定位：在 v2.0 的 **总控 Orchestrator + 多个子 Harness + prototype_projection_harness** 基线之上，新增 two-pass runtime reasoning、renderer stage plan、UX writer、Figma comments、layout routing 和 renderer skill hook。  
适用：已有 PRD 迁移、AI-ready PRD 维护、自然语言变更、多文档协作、PRD.md 与 YAML 同步、需求质量检查、状态推理、指标埋点、发布计划、追踪矩阵、prototype runtime 和 Figma 原型投射。

---

## 1. 核心变化

v0.3 是一个相对集中的 PRD mini harness。  
v2.1 继续使用：

```text
prd_orchestrator/
  负责调度、路由、多文档隔离、影响分析、局部重跑、使用策略。

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

通俗说：

```text
v0.3 像一个全能施工队；
v2.1 像一个总包工头 + 八个专业工种，其中原型 harness 只做 projection、renderer staging 和 diff candidate。
```

---

## 2. 解决的问题

v2.1 继承 v2.0 解决的四个问题，并加深原型投射阶段：

### 2.1 PRD.md 与 YAML 不同步

以前 `requirements.yaml / screens.yaml / metrics.yaml / events.yaml` 里有真实内容，但 `PRD.md` 可能只是标题和占位符。  
v1.0 新增：

```text
projection_sync_harness
```

它负责：

```text
YAML → 完整 14 章 PRD.md 投影
PRD.md 结构校验
PRD.md 内容覆盖校验
PRD.md 未来源事实拦截
```

### 2.2 C-EARS 过度模板化

以前 C-EARS 可能只是“当...时，系统应当...”的句式转换。  
v1.0 新增：

```text
requirement_pattern_registry.yaml
```

支持：

```text
事件触发型
状态驱动型
条件型
异常处理型
数据规则型
权限/隐私型
非功能数值规格型
实验型
发布型
合规型
```

### 2.3 单体 harness 越来越大

完整 PRD 架构有 14 章，不应该全部塞进一个 harness。  
v1.0 拆成多个子 harness，每个只管自己的领域。

### 2.4 Structured facts 难以生成可交互原型

v2.0 新增：

```text
prototype_projection_harness
```

它负责：

```text
structured facts → prototype.runtime.json → Figma frames / reactions / flow map
Figma semantic diff → figma_diff_report → change_patch_candidate
```

关键边界：

```text
原型不是事实源；
Figma 不是事实源；
Figma diff 只能生成 candidate；
真实 Figma 连线必须来自 interaction_graph.edges[]。
```

v2.1 在这个基础上新增：

```text
prototype.runtime.base.json → prototype.runtime.json with generation_lineage/reasoning_completion
renderer stage plan RND-00 到 RND-09
UX writer copy catalog
Figma comment map
layout route plan + documentation-only visual lines
renderer skill pack advisory hook
```

---

## 3. 给谁用？

| 角色 | 应该读什么 |
|---|---|
| 产品经理 / PM | `USER_GUIDE_NON_BUILDERS.md`、`SCENARIO_PATHS.md` |
| 需求评审者 | `USER_GUIDE_NON_BUILDERS.md`、`sub_harnesses/*/README.md` |
| 搭建者 / 工程实现者 | `BUILDER_SETUP_GUIDE.md`、`ARCHITECTURE_v1.0.md` |
| 使用 Codex 的人 | `AGENTS.md`、`EXECUTION_GUIDE_CODEX.md` |
| 使用 LLM API 的人 | `EXECUTION_GUIDE_LLM_RUNTIME.md` |

---

## 4. 最小命令

```bash
pip install -r requirements-dev.txt

python scripts/prd_control/harnessctl.py status
python scripts/prd_control/harnessctl.py validate-rule-specs
python scripts/prd_control/harnessctl.py validate-fixtures
python scripts/prd_control/prototypectl.py status
python scripts/prd_control/prototypectl.py validate-runtime
python scripts/prd_control/prototypectl.py validate-interactions
python scripts/prd_control/prototypectl.py validate-fact-bundle --bundle sub_harnesses/prototype_projection_harness/examples/prd_fact_bundle.sample.yaml
python scripts/prd_control/prototypectl.py validate-uxwriter --catalog sub_harnesses/prototype_projection_harness/examples/uxwriter-copy-catalog.sample.yaml
python scripts/prd_control/prototypectl.py validate-layout --plan sub_harnesses/prototype_projection_harness/examples/layout-route-plan.sample.yaml
python scripts/prd_control/prototypectl.py validate-comments --map sub_harnesses/prototype_projection_harness/examples/figma-comment-map.yaml
python scripts/prd_control/prototypectl.py validate-skill-pack --pack sub_harnesses/prototype_projection_harness/examples/renderer-skill-pack.sample.yaml
```

真实 PRD 运行应使用 instance 隔离：

```bash
python scripts/prd_control/harnessctl.py init-instance ../prd_instances/my-product-prd --instance-id my-product-prd
```

第一次导入完整旧 PRD 时，先做一次源文档结构化提取和提取评审。评审通过后，后续子 Harness 消费 `structured_source_baseline`，不要在每个子 Harness 前重复读取散装源 PRD：

```bash
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-INITIAL-001 extract-source-baseline inputs/legacy_prd.md
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-INITIAL-001 unified-review
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-INITIAL-001 core-review-md
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-INITIAL-001 review-decision prd_orchestrator/source_extraction/structured_source_baseline.yaml --decision approve --reviewer alexYG --notes "源 PRD 结构化提取已确认，可供后续子 Harness 消费"
```

`extract-source-baseline` 同时会生成 `prd_orchestrator/source_extraction/sub_harness_inputs/<harness>.yaml`。后续子 Harness 读取自己的输入切片，避免重复直接读取源 Markdown。

`core-review-md` 用于 CORE-000 阶段，把 `prd_core_harness` 的核心事实候选 YAML 展开成专属人工确认单 `sub_harnesses/prd_core_harness/reports/CORE-000_REVIEW.md`。人工只需要确认、改写、不保留或暂缓；正式评审记录仍绑定候选 YAML，避免人工 MD 和机器源分叉。

日常自然语言小改才走 change request 链路：

```bash
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 route-change inputs/change_requests/CR-001.md
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 classify-change inputs/change_requests/CR-001.md
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 impact PRD-DELTA-001
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 rerun-plan PRD-DELTA-001
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 quality-gate
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 review-decision prd_orchestrator/change_patch_candidates/CR-001.candidate.yaml --decision approve --reviewer alexYG --notes "人工确认可进入批准产物区"
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 promote-approved prd_orchestrator/change_patch_candidates/CR-001.candidate.yaml --promoter alexYG
```

兼容/框架检查只运行只读命令；会产生产物的命令必须使用上面的 instance 隔离参数：

```bash
python scripts/prd_control/harnessctl.py validate-prd-template
python scripts/prd_control/harnessctl.py check-prd-sync
python scripts/prd_control/harnessctl.py search REQ-AUTH-001
```

---

## 5. 推荐使用路径

第一次迁移旧 PRD：

```text
source PRD → extract-source-baseline → extraction review → structured_source_baseline
→ CORE-000 → CORE-001 → CORE-002
→ REQ-003A → REQ-003B → REQ-003C
→ SCREEN-004
→ DATA-005
→ TRACE-006
→ PROJ-007
→ PROTO-008
→ PROTO-009
→ PROTO-011
→ PROTO-012
→ PROTO-013
→ PROTO-014
→ PROTO-015
→ PROTO-016
→ PROTO-017
```

注意：`classify-change` 是小改入口，不是完整旧 PRD 首次迁移入口。

后续自然语言更新：

```text
CHANGE-INGEST
→ route to sub-harness
→ PRD-DELTA
→ impact
→ partial rerun plan
→ affected sub-harnesses
→ PROJ sync
→ PROTO projection rerun when structured facts changed
```

原型投射路径：

```text
Phase 1: 接入 prototype_projection_harness 和文档注册
Phase 2: 生成 prototype.runtime.base.json 和 completed prototype.runtime.json，不写 Figma
Phase 3: 先生成 layout route plan 和 canvas skeleton，再渲染页面细节
Phase 4: 接入 UX writer copy、component / pattern binding
Phase 5: 写入 Figma reactions、comments 和 documentation-only visual lines
Phase 6: Figma diff reverse sync 只生成 candidate
Phase 5: 接入 Figma diff ingest 和 Patch Control v2
```

完整说明见：

```text
USER_GUIDE_NON_BUILDERS.md
SCENARIO_PATHS.md
```
