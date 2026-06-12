# harnessctl

```bash
python scripts/prd_control/harnessctl.py status
python scripts/prd_control/harnessctl.py validate-rule-specs
python scripts/prd_control/harnessctl.py validate-fixtures
python scripts/prd_control/harnessctl.py init-instance ../prd_instances/my-product-prd --instance-id my-product-prd
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-INITIAL-001 preflight-prd-run
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-INITIAL-001 run-prd-loop --source inputs/legacy_prd.md
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-INITIAL-001 extract-source-baseline inputs/legacy_prd.md
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-INITIAL-001 unified-review
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-INITIAL-001 core-review-md
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 route-change inputs/change_requests/CR-001.md
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 classify-change inputs/change_requests/CR-001.md
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 impact PRD-DELTA-001
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 rerun-plan PRD-DELTA-001
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 quality-gate
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 unified-review
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 review-decision prd_orchestrator/change_patch_candidates/CR-001.candidate.yaml --decision approve --reviewer alexYG --notes "人工确认可进入批准产物区"
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 promote-approved prd_orchestrator/change_patch_candidates/CR-001.candidate.yaml --promoter alexYG
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 stop-the-line --stage render_readiness --reason "runtime has no screens" --next-action "generate prototype runtime" --resume-condition "validate-render-readiness passes"
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 write-patch-report --patch-id PATCH-001 --summary "修复 render readiness gate" --root-cause "空 runtime 被允许进入 Figma" --changed-file scripts/prd_control/prototypectl.py --validation "validate-render-readiness blocks empty runtime"
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 write-loop-gate --stage RND-06B --trigger-source logic_sidecar_audit --severity blocker --failure-class FC-SIDECAR-MISSING --affected-artifact logic_sidecar_card_map.yaml --source-ref PRD.md#image-upload-rule --repair-hint "补齐缺失 sidecar card 和 anchor badge" --profile LOOP_PROFILE_COMPLEX
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-stop-the-line prd_orchestrator/stop_the_line/STL-001.stop_the_line.yaml
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-patch-report prd_orchestrator/patch_reports/PATCH-001.patch_report.yaml
python scripts/prd_control/harnessctl.py validate-prd-template
python scripts/prd_control/harnessctl.py check-prd-sync
python scripts/prd_control/harnessctl.py search REQ-AUTH-001
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 generate-prototype-artifacts --source inputs/PRD.md --codex-inference required
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-render-readiness --runtime runs/RUN-001/io/output/prototype.runtime.candidate.json --payload runs/RUN-001/io/output/prototype-render-payload.yaml
python scripts/prd_control/prototypectl.py validate-generation-lifecycle-rules
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-generation-job-queue --input runs/RUN-001/io/state/generation_job_queue.yaml
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-generation-trace --input runs/RUN-001/io/state/generation_trace.yaml
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-model-execution-contract --input runs/RUN-001/io/state/model_execution_contract.yaml
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-model-invocation-trace --input runs/RUN-001/io/state/model_invocation_trace.yaml
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-generated-artifact-manifest --input runs/RUN-001/io/state/generated_artifact_manifest.yaml
python scripts/prd_control/prototypectl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-001 validate-source-coverage --coverage runs/RUN-001/io/state/source_coverage_report.yaml --runtime runs/RUN-001/io/output/prototype.runtime.candidate.json --payload runs/RUN-001/io/output/prototype-render-payload.yaml
```

完整旧 PRD 首次迁移必须先运行 `extract-source-baseline inputs/legacy_prd.md`。该命令把源 PRD 提取成 `runs/<run-id>/prd_orchestrator/source_extraction/structured_source_baseline.yaml`，生成 `prd_orchestrator/source_extraction/sub_harness_inputs/<harness>.yaml` 输入切片，并生成 `human_review/STRUCTURED_SOURCE_EXTRACTION_REVIEW.md`。评审确认后，后续子 harness 消费自己的结构化输入切片，而不是重复直接读取散装源 PRD。

`preflight-prd-run` 是只读前置门禁。当前 run 如果没有 `inputs/*.md` 源 PRD、没有 `structured_source_baseline.yaml`，且 `product-spec/requirements.yaml` / `screens.yaml` 仍为空模板，会直接 `BLOCKED`。

`run-prd-loop` 是显式 loop 控制入口。它会在缺少 source baseline 时触发 `extract-source-baseline`，然后停在人工评审门禁；如果 source baseline 未批准、下游 requirement/screen generation 未产出、或 prototype runtime/render payload 未实现，也会明确 `BLOCKED` 并指出断点。它不会用 examples/sample 代替真实 PRD 输出。

`stop-the-line` 会把关键断点写成 `runs/<run-id>/prd_orchestrator/stop_the_line/*.stop_the_line.yaml`，并自动生成同名 `.md` 人工阅读版。YAML 是 validator / review-decision 的机器源；MD 是每个 stage 停线时给人看的入口，包含 `reason`、`required_next_action` 和 `resume_condition`。`run-prd-loop` 在自动停线时也会写这两份报告。

`write-patch-report` 会把修复原因、改动文件、验证结果和剩余缺口写成 `runs/<run-id>/prd_orchestrator/patch_reports/*.patch_report.yaml`，并自动生成同名 `.md` 人工阅读版。报告本身仍是候选证据，需要 `review-decision` 批准后才可 promote。

`write-loop-gate` 是 v3.1 loop 的 gate-only 入口。它只在 `runs/<run-id>/prd_orchestrator/loop_gates/<gate-id>/` 写入 `loop_finding.yaml`、`repair_plan.yaml`、`loop_manifest.yaml` 和 `final_loop_report.md`；遇到 `blocker` 或 `semantic_defect` 时还会复用 `stop-the-line` 写 YAML+MD。它不会执行 `apply_allowed_patches`，不会 `rerun_affected_scopes`，不会生成 prototype payload，不会写 Figma，也不会改 `product-spec`。

`unified-review` 会把 `structured_source_baseline` 或 `product-spec` 中各 sub-harness 的候选需求、页面状态、指标事件、发布、traceability 和开放问题合并成中文人工 review 入口，默认写入 `runs/<run-id>/human_review/REVIEW.md`。该 MD 会在每个模块开头说明本模块需要确认什么、应该怎么写、满足标准是什么，以及对后续 sub-harness 的影响；YAML 仍是 validator 和 quality gate 的机器源。

Figma 只用于最终原型画布写入。任何 gate 结果、validator 报告、stage review、patch report、stop-the-line 都必须通过 run 目录下的 Markdown 文件呈现，不能创建 Figma page/card/dashboard 作为状态展示。

Prototype-only 跑原型时使用 `prototypectl.py generate-prototype-artifacts --source inputs/PRD.md`。v3.1.1 会先把 Markdown 标题、流程、列表和表格逐行拆成可追溯 `source_atoms`，再生成 obligations、design kernel、composition、hotspots、sidecar、runtime 和 payload。该命令不触发 PRD harness，不生成 `source_extraction` / `human_review`，只在 run root 下写 `io/output`、`io/state` 和 `prototype_projection_reports`，随后用 generated runtime + payload + `source_coverage_report` 跑 `validate-render-readiness`。

`generate-prototype-artifacts --codex-inference required` 会调用 Codex CLI 做只读模型审查，并写入 `runs/<run-id>/io/state/codex_inference_review.yaml`；`off` 可用于结构化回归，`optional` 在 Codex CLI 不可用时不阻断。无论是否调用模型，都会生成 `runs/<run-id>/prd_orchestrator/prototype_projection_reports/prototype_blueprint_review.md` 作为写入 Figma 前的人工 review 蓝图，包含页面数量、页面归属、组件构成、交互链路、分支依据和模型审查意见。

生成链路拆成 deterministic generator 和 model generator。`generation_job_queue.yaml` 是机器可读队列，每个 job 都必须有 `completion_criteria`；deterministic jobs 生成 source atoms、DRD artifacts、runtime、payload、coverage 和 manifest，model job 只做 blueprint review。模型调用由 `model_execution_contract.yaml` 约束为只读审查，并由 `model_invocation_trace.yaml` 记录 prompt hash、只读命令、耗时、exit code、raw output path 和 completion criteria。

`core-review-md` 会读取当前 run 的 `sub_harnesses/prd_core_harness/candidates/CORE-000_CORE_FACT_CANDIDATES.yaml`，稳定生成 `sub_harnesses/prd_core_harness/reports/CORE-000_REVIEW.md`，作为 CORE-000 阶段的专属人工确认单。人工只需要确认、改写、不保留或暂缓；正式评审记录仍应绑定候选 YAML，而不是只绑定人工填写的 MD。

`extract-source-baseline`、`route-change`、`classify-change`、`impact`、`rerun-plan`、`quality-gate`、`unified-review`、`core-review-md`、`review-decision`、`promote-approved` 会生成候选、报告、review 决策或批准产物，默认必须带 `--instance-root` 和 `--run-id`，避免污染 harness 工程包。`route-change` / `classify-change` 只用于日常 change request，不用于完整旧 PRD 首次迁移。
