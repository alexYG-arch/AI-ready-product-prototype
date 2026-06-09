# PRD Core Harness

## 负责

背景、问题、用户、目标、范围、非目标、风险、开放问题。

## 不负责

C-EARS 细节、页面状态、指标埋点、发布灰度。

## 标准目录

```text
harness_contract.yaml
validators.yaml
patch_contracts/
context_packs/
schemas/
fixtures/
reports/
```

## CORE-000 评审产物

CORE-000 只生成核心事实候选，不直接写入 `product-spec`。

```bash
python scripts/prd_control/harnessctl.py --instance-root ../prd_instances/my-product-prd --run-id RUN-INITIAL-001 core-review-md
```

该命令读取当前 run 的 `sub_harnesses/prd_core_harness/candidates/CORE-000_CORE_FACT_CANDIDATES.yaml`，生成 `sub_harnesses/prd_core_harness/reports/CORE-000_REVIEW.md`。人工在 MD 中填写确认、改写、不保留或暂缓；正式评审记录由运行者绑定候选 YAML。
