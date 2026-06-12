# harnessctl

```bash
python scripts/prd_control/harnessctl.py status
python scripts/prd_control/harnessctl.py validate-rule-specs
python scripts/prd_control/harnessctl.py validate-fixtures
python scripts/prd_control/harnessctl.py init-instance ../prd_instances/my-product-prd --instance-id my-product-prd
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
python scripts/prd_control/harnessctl.py validate-prd-template
python scripts/prd_control/harnessctl.py check-prd-sync
python scripts/prd_control/harnessctl.py search REQ-AUTH-001
```

完整旧 PRD 首次迁移必须先运行 `extract-source-baseline inputs/legacy_prd.md`。该命令把源 PRD 提取成 `runs/<run-id>/prd_orchestrator/source_extraction/structured_source_baseline.yaml`，生成 `prd_orchestrator/source_extraction/sub_harness_inputs/<harness>.yaml` 输入切片，并生成 `human_review/STRUCTURED_SOURCE_EXTRACTION_REVIEW.md`。评审确认后，后续子 harness 消费自己的结构化输入切片，而不是重复直接读取散装源 PRD。

`unified-review` 会把 `structured_source_baseline` 或 `product-spec` 中各 sub-harness 的候选需求、页面状态、指标事件、发布、traceability 和开放问题合并成中文人工 review 入口，默认写入 `runs/<run-id>/human_review/REVIEW.md`。该 MD 会在每个模块开头说明本模块需要确认什么、应该怎么写、满足标准是什么，以及对后续 sub-harness 的影响；YAML 仍是 validator 和 quality gate 的机器源。

`core-review-md` 会读取当前 run 的 `sub_harnesses/prd_core_harness/candidates/CORE-000_CORE_FACT_CANDIDATES.yaml`，稳定生成 `sub_harnesses/prd_core_harness/reports/CORE-000_REVIEW.md`，作为 CORE-000 阶段的专属人工确认单。人工只需要确认、改写、不保留或暂缓；正式评审记录仍应绑定候选 YAML，而不是只绑定人工填写的 MD。

`extract-source-baseline`、`route-change`、`classify-change`、`impact`、`rerun-plan`、`quality-gate`、`unified-review`、`core-review-md`、`review-decision`、`promote-approved` 会生成候选、报告、review 决策或批准产物，默认必须带 `--instance-root` 和 `--run-id`，避免污染 harness 工程包。`route-change` / `classify-change` 只用于日常 change request，不用于完整旧 PRD 首次迁移。
