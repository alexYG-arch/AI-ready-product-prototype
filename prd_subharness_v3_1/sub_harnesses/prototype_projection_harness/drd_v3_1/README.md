# Prototype Harness DRD Deductive Upgrade v3.1（原型 Harness DRD 演绎推理升级包 v3.1）

本包用于在现有 Prototype Projection Harness 2.1 / DRD 规则基础上升级一条新的可执行链路：

```text
Screen Role Obligation（屏幕角色义务演算）
→ Design Kernel（设计内核）
→ Composition Generation（构图生成）
→ Interaction Hotspots（交互热点）
→ Logic Sidecar Audit（逻辑侧车审计）
→ Local Materialization Patch（局部物化修补）
→ Annotation Stub + Logic Sidecar Card（备注短桩 + 逻辑侧车卡片）
→ Anchor Badge / Leader Line（锚点编号 / 短引导线）
```

## 核心变化

1. `Screen Role（屏幕角色）` 不再主要依赖分类枚举，而是改成 `Obligation Calculus（义务演算）`：从动作、对象、约束、宿主表面、提交控件、反馈时机演绎出必要状态、热点、反馈和审计义务。
2. `Skill（技能包）` 不写具体业务模板，而写抽象方法论，例如边界值分析、最早可修正点、外部表面展开、禁用态解释。
3. `Annotation（Figma Dev Mode 备注）` 降级为短桩：只挂在节点上，写短摘要与 sidecar card id；完整逻辑写入画布左右两列的 `Logic Sidecar Cards（逻辑侧车卡片）`。
4. `Pen Line（Pen 线）` 不再承载完整跳转逻辑，只保留锚点短引导线和少量主流程概览线。
5. 输出是 Codex 可读取的 YAML 规则包，包含 validators、examples、migration guide 和执行 prompt。

## 入口文件

- `codex/CODEX_UPGRADE_PROMPT.md`：交给 Codex 的执行提示。
- `rules/12_complete_deductive_rules.yaml`：合并后的主规则索引。
- `rules/01_screen_role_obligation_rules.yaml`：屏幕角色义务演算核心规则。
- `rules/11_validators.yaml`：升级后的验证器。
- `examples/image_upload_3_5_walkthrough.yaml`：上传 3-5 张图片的演绎示例。

## 与 2.1 的兼容边界

保留 2.1 的核心约束：PRD-first / fact-bundle-first、runtime 只作 validation/gap/evidence、Figma behavior / annotation / visual line 分离、visual line 不是交互行为来源。新增规则只增强 DRD Mode 的推理和展示层，不把 prototype harness 提升为事实源。
