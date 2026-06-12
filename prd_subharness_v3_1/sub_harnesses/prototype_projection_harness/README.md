# Prototype Projection Harness

## 1. 定位

`prototype_projection_harness` 是 v3.1 的平级 projection harness。它保留 v2.1 的默认原型投射链路，并新增 DRD_MODE 设计评审文档模式的演绎规则校验入口。

```text
structured PRD facts → prototype.runtime.base.json → prototype.runtime.json → renderer stage plan → Figma frames / reactions / comments / flow lines
Figma semantic diff → figma_diff_report → change_patch_candidate
DRD_MODE source slices → screen role obligations → design kernel → sidecar card / local patch validation
```

它不拥有产品事实，不直接改 `requirements.yaml`、`screens.yaml`、`metrics.yaml`、`events.yaml` 或 `PRD.md`。
DRD v3.1 的 `local_materialization_patch` 也只允许修补投射层，不允许回写 PRD fact store。

---

## 2. 输入

允许读取：

```text
product-spec/requirements.yaml
product-spec/screens.yaml
product-spec/metrics.yaml
product-spec/events.yaml
product-spec/traceability.md
product-spec/component-binding-map.yaml
product-spec/design-semantic-library.json
sub_harnesses/prototype_projection_harness/drd_v3_1/rules/12_complete_deductive_rules.yaml
sub_harnesses/prototype_projection_harness/drd_v3_1/profile.yaml
sub_harnesses/prototype_projection_harness/adapters/design_systems/sds_monochrome_adapter.yaml
```

禁止把这些作为事实源：

```text
product-spec/PRD.md
Figma frame 文案
Figma layer name
Flow Map annotation text
```

---

## 3. 输出

```text
product-spec/prototype.runtime.json
product-spec/figma-sync-map.yaml
product-spec/figma-interaction-map.yaml
sub_harnesses/prototype_projection_harness/examples/uxwriter-copy-catalog.sample.yaml
sub_harnesses/prototype_projection_harness/examples/layout-route-plan.sample.yaml
sub_harnesses/prototype_projection_harness/examples/figma-comment-map.yaml
prd_orchestrator/figma_diff_reports/*.yaml
prd_orchestrator/prototype_projection_reports/*.yaml
prd_orchestrator/change_patch_candidates/*.candidate.yaml
sub_harnesses/prototype_projection_harness/drd_v3_1/examples/*.sample.yaml
sub_harnesses/prototype_projection_harness/adapters/design_systems/sds_monochrome_adapter.yaml
```

---

## 4. 三类投射

```text
Frame Projection       页面、状态、overlay、toast、modal
Reaction Projection    interaction_graph.edges[] → Figma node reactions
Documentation          Flow Map / Interaction Spec / annotation cards
```

真实可播放交互必须是 Figma reaction；说明箭头只是文档，不等于交互。

---

## 5. 本地命令

```bash
python scripts/prd_control/prototypectl.py status
python scripts/prd_control/prototypectl.py validate-runtime
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-render-readiness --payload runs/RUN-001/io/output/prototype-render-payload.yaml
python scripts/prd_control/prototypectl.py validate-interactions
python scripts/prd_control/prototypectl.py validate-fact-bundle --bundle sub_harnesses/prototype_projection_harness/examples/prd_fact_bundle.sample.yaml
python scripts/prd_control/prototypectl.py validate-uxwriter --catalog sub_harnesses/prototype_projection_harness/examples/uxwriter-copy-catalog.sample.yaml
python scripts/prd_control/prototypectl.py validate-layout --plan sub_harnesses/prototype_projection_harness/examples/layout-route-plan.sample.yaml
python scripts/prd_control/prototypectl.py validate-comments --map sub_harnesses/prototype_projection_harness/examples/figma-comment-map.yaml
python scripts/prd_control/prototypectl.py validate-skill-pack --pack sub_harnesses/prototype_projection_harness/examples/renderer-skill-pack.sample.yaml
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 generate-prototype-artifacts --source inputs/PRD.md --codex-inference required
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-runtime --runtime runs/RUN-001/io/output/prototype.runtime.candidate.json
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-render-readiness --runtime runs/RUN-001/io/output/prototype.runtime.candidate.json --payload runs/RUN-001/io/output/prototype-render-payload.yaml
python scripts/prd_control/prototypectl.py status --mode drd
python scripts/prd_control/prototypectl.py validate-drd-rules
python scripts/prd_control/prototypectl.py validate-role-obligations --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/screen_role_obligations.sample.yaml
python scripts/prd_control/prototypectl.py validate-design-kernel --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/design_kernel.sample.yaml
python scripts/prd_control/prototypectl.py validate-sidecar-cards --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/logic_sidecar_card_map.sample.yaml
python scripts/prd_control/prototypectl.py validate-local-patches --input sub_harnesses/prototype_projection_harness/drd_v3_1/examples/local_materialization_patch.sample.yaml
python scripts/prd_control/prototypectl.py validate-design-system-adapters
python scripts/prd_control/prototypectl.py validate-loop-rules
python scripts/prd_control/prototypectl.py validate-loop-finding --input sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/examples/harness_aligned_loop_finding.sample.yaml
python scripts/prd_control/prototypectl.py validate-repair-plan --input sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/examples/harness_aligned_repair_plan.sample.yaml
python scripts/prd_control/prototypectl.py validate-loop-manifest --input sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/examples/harness_aligned_loop_manifest.sample.yaml
python scripts/prd_control/prototypectl.py validate-stage-loop-contracts --input sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/17_harness_aligned_stage_loop_contracts.yaml
python scripts/prd_control/prototypectl.py validate-local-loop-patches --input sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/examples/harness_aligned_local_patches.sample.yaml
python scripts/prd_control/prototypectl.py validate-generation-lifecycle-rules
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-generation-job-queue --input runs/RUN-001/io/state/generation_job_queue.yaml
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-generation-trace --input runs/RUN-001/io/state/generation_trace.yaml
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-model-execution-contract --input runs/RUN-001/io/state/model_execution_contract.yaml
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-model-invocation-trace --input runs/RUN-001/io/state/model_invocation_trace.yaml
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-generated-artifact-manifest --input runs/RUN-001/io/state/generated_artifact_manifest.yaml
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-source-coverage --coverage runs/RUN-001/io/state/source_coverage_report.yaml --runtime runs/RUN-001/io/output/prototype.runtime.candidate.json --payload runs/RUN-001/io/output/prototype-render-payload.yaml
```

`generate-prototype-artifacts` 是 v3.1.1 的 prototype-only 生成入口。它读取 `<instance-root>/inputs/PRD.md`，先把 Markdown 标题、流程、列表和表格逐行拆成可追溯 `source_atoms`，再生成 `prototype_source_brief.yaml`、DRD artifacts、`prototype.runtime.candidate.json` 和 `prototype-render-payload.yaml`。它同时在 `runs/<run-id>/io/state/` 写 `source_slice_index.yaml`、`generation_trace.yaml`、`generated_artifact_manifest.yaml`、`source_coverage_report.yaml` 和可选的 `codex_inference_review.yaml`，并在 `prd_orchestrator/prototype_projection_reports/` 写 `prototype_projection_report.md` 与 `prototype_blueprint_review.md`。它不运行 PRD harness，不写 `product-spec`，不读取 sample，不写 Figma。

`--codex-inference required` 会调用 Codex CLI 执行只读模型审查；`off` 用于纯结构回归，`optional` 会在 Codex CLI 不可用时降级。`prototype_blueprint_review.md` 是最终写入 Figma 前的人工确认入口，会列出页面归属、组件规则、交互主路径/分支、destination frame、route basis 和模型审查意见。

生成阶段现在有显式 job queue：`generation_job_queue.yaml` 列出 deterministic jobs 和 model job，并要求每个 job 都带 `completion_criteria`。Deterministic generator 负责可重复的 source atoms、DRD artifacts、runtime、payload、coverage 和 manifest；Model generator 只负责只读审查，执行边界写在 `model_execution_contract.yaml`，每次调用或跳过写入 `model_invocation_trace.yaml`。

`validate-render-readiness` 是调用 Figma 之前的强门禁：没有真实 PRD 输入 / source baseline、runtime 没有 screens / interaction edges / component bindings、没有 render payload、payload 是 sample/example、payload 缺 source refs、缺 SDS 黑白灰绑定，或 `source_coverage_report` 没有覆盖 required atoms 时，必须 `BLOCKED`。由 `generate-prototype-artifacts` 生成的 runtime candidate + payload 可以通过该门禁；Figma 仍只允许在 PASS 后由最终 writer 写入。

Figma 仅用于最终原型画布写入。`status`、`validate-*`、`review`、`patch_report`、`stop-the-line`、`render-readiness` 等 gate/stage 结果必须写入 run 目录下的 Markdown 或 YAML 报告；不能为了展示状态而新建 Figma page、frame、card 或 dashboard。

## 6. v2.1 Stage Contract Retained

```text
PROTO-012 two-pass runtime reasoning completion
PROTO-013 renderer staged implementation
PROTO-014 Figma comment annotations
PROTO-015 UX writer copy stage
PROTO-016 layout routing and visual pen-line coupling
PROTO-017 advisory renderer skill hook
```

Renderer order is strict: input freeze, layout route blueprint, canvas skeleton, sequence/page render, component/pattern fill, copy application, interaction comments, prototype reactions, visual flow lines, final validation. Comments and visual lines are documentation-only; Figma reactions and `interaction_graph.edges[]` remain the interaction authority.

## 7. DRD v3.1 First-Phase Boundary

```text
ROLE-01 / DK-01 / COMP-01 / HOT-01 / AUD-01 / PATCH-01 rules are archived and validated.
RND-06B sidecar card and RND-08A anchor leader-line rules are archived and validated.
Prototype candidate artifact generation is implemented in the v3.1.1 lifecycle generator.
Real Figma canvas rendering remains deferred to the final writer after readiness PASS.
```

DRD mode defaults:

```text
write_real_figma_reactions = false
draw_full_pen_lines = false
use_annotation_stub = true
use_logic_sidecar_cards = true
local_materialization_patches_write_prd = false
sds_monochrome_adapter_required = true
```

## 8. Loop v3.1 Gate-Only Boundary

`drd_v3_1/loop_v3_1/` archives the downloaded loop upgrade package and adds harness-aligned rules/schemas for the current v3.1 artifact names. This phase only records gate evidence:

```text
loop_finding.yaml
repair_plan.yaml
loop_manifest.yaml
final_loop_report.md
stop_the_line.yaml / stop_the_line.md for blocker or semantic_defect
```

The loop gate does not apply patches, rerun scopes, generate prototype payloads, write product-spec files, or write Figma. `final_loop_report.md` is the human review entry; YAML/JSON remain the machine validation source.

## 9. Prototype Artifact Generator v3.1.1

The generator is deliberately conservative: it extracts candidate screens, states, interactions, sidecar annotations, and payload objects from source Markdown structure, table rows, explicit IDs, constraints, and product-action cues. Boundary states come from generic min/max expressions such as `at least`, `less than`, `more than`, `X to Y`, or their Chinese equivalents; the archived image-upload sample is a regression fixture only, not a production rule source. Ambiguous product logic remains in `prototype_gaps` or report notes. Generated files are candidates and remain `forbidden_as_fact_source`.
