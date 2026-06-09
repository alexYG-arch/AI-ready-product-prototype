# 搭建者指南：PRD Sub-Harness v1.0

## 1. 初始化

```bash
git init
pip install -r requirements-dev.txt
python scripts/prd_control/harnessctl.py status
```

## 2. 放入旧 PRD

```bash
cp /path/to/old-prd.md product-spec/legacy_prd.md
git add .
git commit -m "baseline: add legacy PRD"
```

## 3. 首次迁移

按 `prd_orchestrator/patch_queue.yaml` 的 initial_migration 顺序执行：

```text
CORE-000
CORE-001
CORE-002
REQ-003A
REQ-003B
REQ-003C
SCREEN-004
DATA-005
TRACE-006
PROJ-007
```

## 4. 日常变更

```bash
cp change.md prd_orchestrator/change_requests/CR-001.md
python scripts/prd_control/harnessctl.py route-change prd_orchestrator/change_requests/CR-001.md
python scripts/prd_control/harnessctl.py classify-change prd_orchestrator/change_requests/CR-001.md
python scripts/prd_control/harnessctl.py impact PRD-DELTA-001
python scripts/prd_control/harnessctl.py rerun-plan PRD-DELTA-001
```

## 5. 验证 PRD.md 是否完整

```bash
python scripts/prd_control/harnessctl.py validate-prd-template
python scripts/prd_control/harnessctl.py check-prd-sync
```

## 6. 验证需求质量

```bash
python scripts/prd_control/harnessctl.py quality-gate
```

## 7. Codex 使用

- 一个 patch 一个 thread。
- 一个 patch 一个 worktree。
- 先 Plan-only。
- 再 Execute。
- Review pane 看 diff。
- 跑 harnessctl 校验。
- commit。

## 8. LLM Runtime 使用

LLM 只能输出候选：

```text
classification_candidate
impact_candidate
rerun_plan_candidate
patch_contract_draft
open_questions
```

后端/脚本负责：

```text
写文件
校验
生成 report
决定 rerun plan
记录 review decision
```
