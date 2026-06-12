# Codex Upgrade Prompt（Codex 升级执行提示）

你正在升级 `prototype_projection_harness`。请按本包规则实现 DRD v3.1 Deductive Upgrade（设计评审文档模式 v3.1 演绎升级）。

## 必须遵守

1. 不得让 prototype harness 直接写 PRD fact store。
2. 不得让 runtime 成为 renderer payload。
3. 不得把 Logic Sidecar Audit、review notes、candidate 记录画进产品主 UI。
4. Figma Dev Mode annotation 只作为 `Annotation Stub（备注短桩）`，完整逻辑必须进入 `Logic Sidecar Card（逻辑侧车卡片）`。
5. DRD 默认不写真实 Figma reactions；如需要 playable mode，必须单独开启。
6. Pen line 默认只作为 anchor leader line（锚点短引导线）或 primary overview line（主流程概览线）。
7. 规则文件必须通过 YAML 解析，机器 key 使用英文 snake_case，中文解释放在 `*_zh`、`description_zh`、`notes_zh` 等字段。

## 执行步骤

1. 读取 `rules/12_complete_deductive_rules.yaml`。
2. 将新增 stage 插入到现有 pipeline：`ROLE-01`、`DK-01`、`COMP-01`、`HOT-01`、`AUD-01`、`PATCH-01`、`RND-06B`、`RND-08A`。
3. 更新 renderer，使其从 `source slices + materialization shards + sidecar card map` 生成 DRD 画布，而不是单体 `prototype_render_payload.yaml`。
4. 为每个 stage 输出 YAML artifact，并把 hash / source refs 写入 run manifest。
5. 增加 validators：screen role obligation、kernel constraints、sidecar card、annotation stub、anchor badge、leader line、local patch。
6. 不添加业务专属示例作为生产规则；边界值测试使用通用非图片 fixture。
7. 保留旧命令兼容，但新增命令别名：
   - `validate-role-obligations`
   - `validate-design-kernel`
   - `validate-sidecar-cards`
   - `validate-local-patches`

## 验收标准

- 数量边界 fixture 不能只生成“入口 + 成功/失败”。
- 必须由源文本推导出 min-1/min/max/max+1 边界状态、确认按钮置灰/可用、before_confirm 强提醒、返回业务页、处理中、失败恢复。
- 全量 Pen 线不得出现；复杂逻辑写入 sidecar card。
- Annotation Stub 必须锚定真实节点并引用 sidecar_card_id。
