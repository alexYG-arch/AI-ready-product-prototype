# Prototype Harness DRD Codex Package v3.0

本包用于让 Codex 基于现有 `prototype_projection_harness 2.1` 继续优化为 **DRD Mode（Design Review Documentation Mode，设计评审文档模式）**。

核心原则：

1. **PRD / PRD fact bundle 是事实源**。
2. **Runtime 只做 validation / gap / candidate / review evidence（校验、缺口、候选、评审证据）**，不作为渲染事实源。
3. **当前阶段不写真实 Figma `node.reactions`**，只做：平铺画布、必要状态展示、Dev Mode annotations（Dev Mode 备注）、Pen logic lines（Pen 逻辑线）、projection report（投射报告）。
4. **Payload 必须拆分**：manifest + source slices + common primitive libraries + board/page shards + flow shards。
5. **Host Surface Inference（宿主表面推理）是通用层**，支持 app page、modal、toast/snackbar、notification、attached panel、popover、system handoff、embedded widget、assistant panel 等，不写输入法专属 validator。
6. **组件库不是硬模板大全**。使用 seeded primitive library（基础原语库）提升稳定性，同时允许项目设计系统覆盖、扩展或替换。
7. **中文说明策略**：YAML 可直接用中文注释；严格 JSON 不支持注释，Codex 草稿可用 `.jsonc`，正式 JSON 用 `*_zh` / `description_zh` / `x_zh` 字段。

## 给 Codex 的最短使用方式

1. 先读 `codex/CODEX_EXECUTION_PROMPT.md`。
2. 再读 `rules/prototype_harness_drd_complete_rules.yaml`。
3. 生成或修改工程时，按 `package_manifest.yaml` 中的文件顺序执行。
4. 任何输出先通过 `scripts/validate_rules.py`。

```bash
python scripts/validate_rules.py
```

## 包结构

```text
prototype_harness_drd_codex_package_v3_0/
  README.md
  package_manifest.yaml
  codex/
  docs/
  rules/
  libs/
  schemas/
  examples/
  scripts/
```
