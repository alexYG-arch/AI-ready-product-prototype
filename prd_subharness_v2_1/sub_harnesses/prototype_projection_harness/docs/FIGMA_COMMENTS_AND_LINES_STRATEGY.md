# Figma Comments and Lines Strategy

## Comments

v1.2 uses Figma comments as the primary interaction explanation surface. Each semantic interaction can create a comment anchored near its source component, hotspot, or frame region. The comment carries trigger, guard, actions, state effect, analytics event and source refs.

The REST API positions comments with `client_meta`, including frame-relative offset and region forms. The harness stores the semantic component target in `figma-comment-map.yaml` and computes a frame-relative comment pin for that component.

## Lines

Clickable behavior is written through Figma node reactions. Visual pen/line nodes are documentation only.

The line renderer runs after the layout route plan and real reactions. It uses corridors, lane indices, bundling and gateway nodes to avoid overlapping lines.

## Duplicate avoidance

- Same source + same trigger + same destination: dedupe to one canonical interaction.
- Same source + same trigger + different destinations: merge as conditional branch.
- Same semantic interaction across multiple states: one comment with `applies_to_state_list`; only draw state-specific lines where behavior differs.
- If more than five visible lines leave one frame, collapse to gateway or interaction spec panel.
