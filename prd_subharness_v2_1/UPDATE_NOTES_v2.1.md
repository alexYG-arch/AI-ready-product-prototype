# PRD Sub-Harness v2.1 Prototype Projection Update Notes

## What changed

v2.1 integrates the prototype projection overlay into the PRD sub-harness package with five major capabilities:

1. Two-pass runtime generation inside the runtime stage: base runtime from PRD facts, then explicit logic/state/interaction completion.
2. Skeleton-first renderer stages: global layout and routing blueprint, full canvas skeleton, sequence-group page rendering, comments, reactions, then visual pen lines.
3. Figma comments as the primary interaction explanation surface, anchored near source components or frame regions.
4. A renderer skill hook for later personal/team experience packs that can influence layout, copy tone, pattern choice and flow-line style.
5. A research-grounded UX writer stage with rules and validators for usability, readability, cognitive load, consistency, warmth, accessibility, localization, recovery, trust and more.

## Key decision

The runtime model is not generated in one opaque step. v2.1 uses:

```text
PRD fact bundle
  → prototype.runtime.base.json
  → logic/state/interaction reasoning completion
  → uxwriter copy catalog
  → prototype.runtime.json
```

The renderer never invents missing logic while drawing Figma frames.

## Rendering order

```text
RND-00 input_freeze
RND-01 layout_route_blueprint
RND-02 canvas_skeleton
RND-03 sequence_group_page_render
RND-04 component_and_pattern_fill
RND-05 copy_application
RND-06 figma_interaction_comments
RND-07 real_prototype_reactions
RND-08 visual_pen_line_flow_map
RND-09 final_validation
```

## Authority

Figma reactions are the actual clickable prototype behavior. Figma comments and pen lines are review aids. None of them are PRD fact sources.
