# DRD Mode Architecture（设计评审文档模式架构）

## 目标

当前阶段只实现：

```text
PRD facts → source slices → surface decisions → board/page shards → Figma 平铺画布 + Dev Mode annotations + Pen logic lines + projection report
```

暂时不实现真实点击原型：

```text
RND-07 Real Prototype Reactions（真实 Figma node.reactions 写入） = skipped
```

## 为什么不是单体 runtime / payload

单体 `screen -> states -> components` 会把页面状态、组件实例、布局、交互、备注、Pen 线全部压成语义目录。DRD 模式改为：

```text
materialization_manifest.yaml
  + source_slices/
  + decisions/
  + libs/
  + boards/<board_id>/
  + flows/<flow_id>/
  + reports/
```

## JSON 中文注释策略

严格 JSON 不支持注释。Codex 草稿可以使用 `.jsonc`；正式 JSON/YAML 输出应使用稳定英文 key，并将中文写在：

```text
*_zh
name_zh
description_zh
copy.zh-CN
x_comment_zh
```
