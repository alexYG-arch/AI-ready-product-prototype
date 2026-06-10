# Architecture v3.0: Prototype Harness DRD Mode

v3.0 将 `prototype_projection_harness` 的默认输出从可点击原型推进为 **DRD Mode（Design Review Documentation Mode）**。

## Pipeline

```text
PRD facts
→ source slices
→ host surface decisions
→ materialization manifest
→ board/page shards
→ Figma flat review boards
→ Dev Mode annotations
→ Pen logic lines
→ projection report
```

## Default Behavior

- `DRD_MODE` 不写 Figma `node.reactions`。
- `INTERACTIVE_PLAYABLE_MODE` 作为保留模式存在，但不是本次默认路径。
- 每个 board/page 只展示必要状态，不默认生成 loading/empty/error/success/recovery 全套状态。
- 每个 frame/board/panel packet 必须声明 host surface 或 inherited host surface。
- 每个语义交互必须有 annotation；每条 Pen line 必须引用 interaction 和 annotation。

## Authority Boundary

- Fact authority: PRD / `prd_fact_bundle` / owner harness fact stores。
- Render authority: board/page shards。
- Runtime authority: validation / gap / candidate / review evidence only。
- Figma authority: visual projection only。
- Reverse sync: candidate or review log only。

## Integrated DRD Package

The full executable rules package is mounted under:

```text
sub_harnesses/prototype_projection_harness/drd/
```

The canonical entrypoints are:

- `drd/codex/CODEX_EXECUTION_PROMPT.md`
- `drd/rules/prototype_harness_drd_complete_rules.yaml`
- `drd/package_manifest.yaml`
