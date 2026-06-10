# PRD Sub-Harness v3.0 DRD Mode

中文名：AI-ready PRD 子 Harness 架构 3.0  
版本：v3.0  
默认模式：`DRD_MODE` 设计评审文档模式  
定位：在 v2.1 PRD-first prototype projection 基线上，把原型 harness 升级为可分片、可审阅、可追踪的设计评审文档投射系统。

## Core Principles

- PRD / `prd_fact_bundle` 是事实源。
- Runtime 只做 validation、gap、candidate、review evidence。
- DRD mode 默认不写真实 Figma `node.reactions`。
- Figma Dev Mode annotations 是交互说明面；Pen logic lines 是文档说明线；二者都不是事实源。
- Payload 必须分片：manifest、source slices、common libs、board/page shards、flow shards、reports。
- Host surface inference 是通用层，不写输入法专属 validator。

## Minimal Commands

```bash
pip install -r requirements-dev.txt

python3 scripts/prd_control/harnessctl.py status
python3 scripts/prd_control/harnessctl.py validate-rule-specs
python3 scripts/prd_control/harnessctl.py validate-fixtures
python3 scripts/prd_control/harnessctl.py validate-prd-template
python3 scripts/prd_control/harnessctl.py check-prd-sync

python3 scripts/prd_control/prototypectl.py status
python3 scripts/prd_control/prototypectl.py validate-drd-package
python3 scripts/prd_control/prototypectl.py validate-run-manifest --manifest sub_harnesses/prototype_projection_harness/drd/examples/run_manifest.sample.yaml
python3 scripts/prd_control/prototypectl.py validate-source-slices --dir sub_harnesses/prototype_projection_harness/drd/examples/source_slices
python3 scripts/prd_control/prototypectl.py validate-board --board-dir sub_harnesses/prototype_projection_harness/drd/examples/boards/SCR-AI-TOOLBAR
python3 scripts/prd_control/prototypectl.py validate-pen-lines --packets sub_harnesses/prototype_projection_harness/drd/examples/boards/SCR-AI-TOOLBAR/pen_line_packets.sample.yaml
```

## Prototype Harness v3.0

`prototype_projection_harness` now owns DRD projection artifacts:

```text
prd_fact_bundle
→ source_slices
→ surface_decisions / morphology_decisions
→ materialization_manifest
→ board shards: frame/component/interaction/annotation/pen-line packets
→ Figma flat review boards + Dev Mode annotations + Pen logic lines
→ projection_report
```

`RND-07 Real Prototype Reactions` is skipped in `DRD_MODE`. The optional `INTERACTIVE_PLAYABLE_MODE` boundary is retained for later clickable-prototype work.

## DRD Package

The integrated DRD rules package lives at:

```text
sub_harnesses/prototype_projection_harness/drd/
```

Read these first when implementing or reviewing DRD projection behavior:

- `drd/codex/CODEX_EXECUTION_PROMPT.md`
- `drd/rules/prototype_harness_drd_complete_rules.yaml`
- `drd/package_manifest.yaml`

## Compatibility

v3.0 keeps v2.1 instance/run isolation, source baseline slicing, review decisions, fact owner boundaries and candidate-only reverse sync. It adds DRD sharding and review-board projection as the default prototype harness path.
