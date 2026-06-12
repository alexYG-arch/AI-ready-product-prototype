# Prototype Harness Generation Lifecycle Upgrade v3.1.1

原型 Harness 生成生命周期升级包 v3.1.1。

本包用于补齐 v3.1 loop / repair crew 规则中的首轮生成缺口：之前已有 Loop Controller（反馈回路控制器）和 Repair Crew Generator（施工队生成器），但缺少 Build Crew Generator（建设队生成器）和 Stage Generator Contract（阶段生成契约）。缺少生成层时，运行会出现 required artifact 不存在，validator 直接 block，repair crew 也无对象可修。

## 核心原则

```text
Generate before validate.
先生成，再校验。

Build before repair.
先构建，再修补。

Validator must not be used as generator.
校验器不能承担生成职责。

Repair Crew must not be used for first-pass build.
修补施工队不能承担首轮构建职责。
```

## Codex 入口

优先读取：

```text
codex/CODEX_GENERATION_LIFECYCLE_UPGRADE_PROMPT.md
rules/09_complete_generation_lifecycle_rules.yaml
rules/00_stage_generation_controller.yaml
rules/01_build_crew_generator_rules.yaml
rules/02_stage_generate_contract.yaml
```

## 包含内容

- Stage Generation Controller（阶段生成控制器）
- Build Crew Generator（建设队生成器）
- Stage Generate Contract（阶段生成契约）
- Generation Worker Contracts（生成工种契约）
- Generation Trace（生成追踪）
- Generate → Self-check → Validate → Repair 生命周期
- Missing Artifact Bootstrap（缺失产物自举）
- Regeneration Policy（重生成策略）
- Validator Behavior Update（校验器行为更新）
- Repair Crew Integration（与施工队修补层集成）

## 适用方式

把本包叠加到 v3.1 loop / repair crew 包之后。它不替换 v3.1，而是补齐 v3.1 之前缺失的首轮生成能力。
