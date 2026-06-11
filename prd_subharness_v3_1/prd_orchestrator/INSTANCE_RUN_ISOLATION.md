# PRD Instance & Run Isolation

Status: approved_by_human_review

## 1. 目标

`prd_subharness_v2_0/` 是 harness 工程包，应该只存放规则、contract、validator、模板和脚本。真实 PRD 的输入、候选、报告、impact、rerun plan、日志和输出必须放在独立 instance 中，避免污染 harness 工程。

## 2. 标准目录

```text
prd_instances/<instance_id>/
  instance.yaml
  inputs/
    legacy_prd.md
    change_requests/
    references/
  product-spec/
    PRD.md
    requirements.yaml
    screens.yaml
    metrics.yaml
    events.yaml
    traceability.md
    release-plan.md
  prd_orchestrator/
    review_decisions/
    open_questions/
    tombstones/
  runs/
    <run_id>/
      run_manifest.yaml
      prd_orchestrator/
        impact_candidates/
        change_patch_candidates/
        impact_analysis/
        partial_rerun_plans/
      sub_harnesses/
        <sub_harness_id>/reports/
      human_review/
        REVIEW.md
      logs/
      temp/
  outputs/
    approved_artifacts/
    approved_prd/
    export/
```

## 3. 写入规则

- Harness 工程包只读：`prd_subharness_v2_0/` 不接收真实 PRD 的运行产物。
- 输入放 instance：`inputs/` 和 `product-spec/` 属于某个 PRD instance。
- 候选和报告放 run：route、classify、impact、rerun、quality report 都写入 `runs/<run_id>/`。
- 合并人工 review 放 run：`unified-review` 默认生成中文 `runs/<run_id>/human_review/REVIEW.md`，作为人工统一审阅入口。
- 人工 review 通过前，run outputs 不是事实源。
- 只有有 `review_decision` 后，才能 promote 到 instance 的 `product-spec/`。
- 当前 harness 仓库默认忽略 `prd_instances/`，避免真实 PRD 输入/输出混入 harness 基线。
- `promote-approved` 默认只把已批准 artifact 复制到 `outputs/approved_artifacts/<run_id>/`；写入 `product-spec/` 必须显式提供目标路径和 `--write-product-spec`。

## 4. 命令示例

```bash
python prd_subharness_v2_0/scripts/prd_control/harnessctl.py \
  init-instance prd_instances/my-product-prd --instance-id my-product-prd

python prd_subharness_v2_0/scripts/prd_control/harnessctl.py \
  --instance-root prd_instances/my-product-prd \
  --run-id RUN-001 \
  route-change inputs/change_requests/CR-001.md

python prd_subharness_v2_0/scripts/prd_control/harnessctl.py \
  --instance-root prd_instances/my-product-prd \
  --run-id RUN-001 \
  classify-change inputs/change_requests/CR-001.md

python prd_subharness_v2_0/scripts/prd_control/harnessctl.py \
  --instance-root prd_instances/my-product-prd \
  --run-id RUN-001 \
  impact PRD-DELTA-001

python prd_subharness_v2_0/scripts/prd_control/harnessctl.py \
  --instance-root prd_instances/my-product-prd \
  --run-id RUN-001 \
  rerun-plan PRD-DELTA-001

python prd_subharness_v2_0/scripts/prd_control/harnessctl.py \
  --instance-root prd_instances/my-product-prd \
  --run-id RUN-001 \
  quality-gate

python prd_subharness_v2_0/scripts/prd_control/harnessctl.py \
  --instance-root prd_instances/my-product-prd \
  --run-id RUN-001 \
  unified-review

python prd_subharness_v2_0/scripts/prd_control/harnessctl.py \
  --instance-root prd_instances/my-product-prd \
  --run-id RUN-001 \
  review-decision prd_orchestrator/change_patch_candidates/CR-001.candidate.yaml \
  --decision approve \
  --reviewer alexYG \
  --notes "人工确认可进入批准产物区"

python prd_subharness_v2_0/scripts/prd_control/harnessctl.py \
  --instance-root prd_instances/my-product-prd \
  --run-id RUN-001 \
  promote-approved prd_orchestrator/change_patch_candidates/CR-001.candidate.yaml \
  --promoter alexYG
```

## 5. 人工 Review 门槛

每个 sub-harness run 都必须具备 human review stage。以下动作必须有 review decision：

- candidate 转 confirmed
- 写入 instance `product-spec/`
- 关闭 open question
- 确认 metric target
- 改变 cross-document authority
- 删除或 tombstone item

`review-decision` 会记录 artifact path、sha256、decision、reviewer 和 notes。`promote-approved` 会重新校验 artifact path 与 sha256，只有匹配 approved 决策的 artifact 才能提升。
