# Prototype Harness Stage10+ / FWRITE Optimization v3.2（原型 Harness Stage10+ 与 Figma 写入优化包 v3.2）

本包用于在现有 `prd_subharness_v3_1` 的基础上，只重构 **Stage10 及以后** 的原型生成链路，并将 Figma 写入从推理链路中拆出为纯写入层。

## 核心结论

1. `GEN-10` 到 `GEN-20` 负责生成、模型推理、最终物化、覆盖清单。
2. `GEN-20 COVERAGE-MANIFEST（覆盖清单）` 不再默认停在文字 review；gate 通过后直接进入 Figma 写入。
3. 最终人工 review 的对象应是 Figma 生成物，而不是长篇 YAML / Markdown 文本报告。
4. Figma 写入完全重构为 `FWRITE-01` 到 `FWRITE-07`，只消费 `GEN-FINAL-MATERIALIZATION` 与 `GEN-REVIEW-VIEW-MODEL` 输出，不再做推理。
5. 真实链路、交互状态机、组件元素构成升级为 Figma 写入前的硬三闸门：
   - `USER-JOURNEY-GATE（真实用户链路闸门）`
   - `INTERACTION-STATE-MACHINE-GATE（交互状态机闸门）`
   - `COMPONENT-BLUEPRINT-GATE（组件蓝图闸门）`
6. 名称和版本兼容性通过 alias map 处理：旧 `RND-*`、旧 `figma-comment-map`、旧 `frame_packets` 等名称只读兼容，新写入使用 v3.2 canonical names。

## 建议默认 Profile

```text
DRD_TO_FIGMA_WRITE
设计评审文档到 Figma 写入模式
```

这个 profile 不默认写真实 `node.reactions`，但会写入 Figma 画布、组件实例、逻辑侧车卡片、Dev Mode 备注短桩、锚点编号、maps 和报告。可播放原型需单独启用 `PLAYABLE_PROTOTYPE_WRITE`。

## Codex 入口

优先读取：

```text
codex/CODEX_STAGE10_FWRITE_UPGRADE_PROMPT.md
rules/17_complete_stage10_fwrite_rules.yaml
rules/08_figma_write_readiness_gate.yaml
rules/09_fwrite_pipeline_rules.yaml
```

## 校验

```bash
python3 scripts/validate_yaml.py
python3 scripts/audit_v31_compat.py --root <prd_subharness_v3_1>
```
