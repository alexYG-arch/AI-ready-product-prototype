# Package Manifest v3.0 DRD Mode

This package keeps v2.1 as rollback baseline and adds `prd_subharness_v3_0/` as the default entrypoint.

## New v3.0 Entrypoints

- `README.md`
- `ARCHITECTURE_v3.0_DRD_MODE.md`
- `UPDATE_NOTES_v3.0.md`
- `PACKAGE_MANIFEST_v3.0.md`
- `prd_orchestrator/patch_control_v3.yaml`
- `sub_harnesses/prototype_projection_harness/drd/`

## DRD Package Contents

- `drd/rules/`
- `drd/libs/`
- `drd/schemas/`
- `drd/examples/`
- `drd/docs/`
- `drd/codex/`
- `drd/scripts/`

## Compatibility

- v2.1 runtime, UX writer, layout and Figma-map commands remain available.
- DRD mode adds source-slice and board-shard validators.
- `figma-comment-map` remains legacy compatibility; v3.0 annotation semantics use Dev Mode annotations.
