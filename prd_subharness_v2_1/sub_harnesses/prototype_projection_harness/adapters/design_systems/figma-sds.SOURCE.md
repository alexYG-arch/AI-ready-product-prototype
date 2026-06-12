# Figma Simple Design System Snapshot

Source: https://github.com/figma/sds
Downloaded: 2026-06-11
Commit: be440d804c525a0d5654900161988edbe9754575
License: MIT
Local path: `figma-sds/`

## Harness Role

This snapshot is an external design-system adapter reference for `prototype_projection_harness`.
It is not a PRD fact source and must not write directly to product facts.

## Monochrome Constraint

The product prototype requires black, white, and gray only. Any SDS variables, styles,
tokens, or component states used in projection must pass through a monochrome adapter
before entering Figma output.

Allowed color values should satisfy `R = G = B`; semantic states such as danger,
warning, success, accent, selected, and focus must be represented with grayscale
contrast, border weight, icons, labels, or state text rather than hue.
