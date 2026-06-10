# Codex Execution Prompt（Codex 执行提示）

你正在维护 `prototype_projection_harness`。请按本包规则把现有 2.1 stage 升级为 DRD-first（设计评审文档优先）模式。

## 必须遵守

1. 不把 runtime 作为渲染事实源。
2. 不让 Figma / Pen line / annotation 反向成为 PRD 事实。
3. 当前 DRD Mode 不写真实 `node.reactions`。
4. 使用 `manifest + source slices + common libs + board shards + flow shards`，不要生成单体大 payload。
5. 每个 board/page 只展示必要状态，不能默认生成 loading/empty/error/success/recovery 全套状态。
6. Pen line 只做逻辑说明，必须引用 `interaction_id` 和 `annotation_id`。
7. 宿主表面推理必须通用化，不得写输入法专属 validator。
8. 机器 key 用英文 snake_case；中文写入 `*_zh`、`description_zh`、`copy.zh-CN` 或 YAML 注释。
9. 严格 JSON 不写注释；如果需要中文注释，使用 `.jsonc` 草稿或 YAML。

## 推荐修改顺序

1. 创建/更新 rules 文件。
2. 创建 common primitive libs。
3. 创建 schemas。
4. 创建 examples。
5. 更新 validator。
6. 运行 `python scripts/validate_rules.py`。
7. 输出 projection report，而不是直接改 PRD。
