# Migration from 2.1 to 3.1（从 2.1 迁移到 3.1）

## 保留

- PRD-first / fact-bundle-first。
- runtime 只做 validation、gap、candidate、review evidence。
- Figma behavior / annotation / visual line 分离。
- Dev Mode annotations 仍然绑定真实节点。
- visual lines 仍然不是交互行为来源。

## 新增

1. 在 `SURF-02` 后插入 `ROLE-01`、`DK-01`、`COMP-01`、`HOT-01`、`AUD-01`、`PATCH-01`。
2. 在 `RND-06` 后插入 `RND-06B Logic Sidecar Cards`。
3. 将 `RND-08` 默认替换为 `RND-08A Anchor Badge / Leader Line`。
4. 增加 `rules/01_screen_role_obligation_rules.yaml` 到 `rules/12_complete_deductive_rules.yaml` 的规则加载链。
5. 增加 validators：`ROLE_VAL_*`、`DK_VAL_*`、`COMP_VAL_*`、`HOT_VAL_*`、`AUD_VAL_*`、`PATCH_VAL_*`、`SIDECAR_VAL_*`、`PEN_VAL_*`、`SKILL_VAL_*`。

## 旧输出到新输出映射

| 2.1 输出 | 3.1 输出 |
|---|---|
| prototype_render_payload.yaml | source slices + board/page shards + materialization manifest |
| annotation body full logic | annotation stub + logic sidecar card |
| visual_flow_line_map.yaml | anchor_leader_line_map.yaml + optional_flow_overview_map.yaml |
| runtime inferred states | runtime evidence only + local materialization patch candidate |

## Codex 执行建议

先实现 validators 和 artifact 输出，再接入实际 Figma renderer。不要先改视觉渲染，否则会继续把复杂逻辑压扁到页面和线里。
