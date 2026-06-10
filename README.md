# AI-ready Product PRD Sub-Harness

本仓库默认入口已升级到 **PRD Sub-Harness v3.0 DRD Mode**。

v3.0 在 v2.1 的 PRD-first prototype projection 基线上，引入 **DRD Mode（Design Review Documentation Mode，设计评审文档模式）**：

- PRD / PRD fact bundle 仍然是事实源。
- Runtime 只做 validation / gap / candidate / review evidence，不作为渲染事实源。
- 默认不写真实 Figma `node.reactions`。
- 默认输出平铺评审画布、必要状态、Figma Dev Mode annotations、Pen logic lines 和 projection report。
- Payload 使用 manifest + source slices + primitive libs + board/page shards + flow shards，不生成单体大 payload。

## Entrypoints

| Version | Path | Role |
| --- | --- | --- |
| v3.0 | [`prd_subharness_v3_0/`](prd_subharness_v3_0/) | 默认入口；DRD 设计评审文档模式。 |
| v2.1 | [`prd_subharness_v2_1/`](prd_subharness_v2_1/) | PRD-first prototype projection 回滚基线。 |
| v2.0 | [`prd_subharness_v2_0/`](prd_subharness_v2_0/) | prototype_projection_harness 初始集成基线。 |
| v1.0 | [`prd_subharness_v1_0/`](prd_subharness_v1_0/) | 原始多 sub-harness 基线。 |

## Quick Check

```bash
cd prd_subharness_v3_0
python3 scripts/prd_control/harnessctl.py status
python3 scripts/prd_control/harnessctl.py validate-rule-specs
python3 scripts/prd_control/prototypectl.py status
python3 scripts/prd_control/prototypectl.py validate-drd-package
```

真实 PRD 运行仍应使用 instance / run 隔离，避免把候选、报告或 Figma diff 写进 harness 工程包。
