# Codex Loop Upgrade Prompt（Codex 回路升级提示）

You are upgrading `prototype_projection_harness` with Controlled Feedback Loop v3.1.

你需要执行：

1. 读取 `rules/15_complete_loop_rules.yaml`。
2. 将 loop controller 作为 cross-cutting controller（横切控制器）接入现有 pipeline。
3. 不要让 loop 直接写 PRD fact store。
4. 所有 validator failure 必须被转成 finding，并通过 loop router 生成 repair plan。
5. 每个 stage 必须补 `loop` 契约。
6. 每次迭代必须生成 `loop_manifest.yaml`。
7. 支持三档 Loop Profile：simple / standard / complex。它们是可配置策略，不是硬编码。
8. 如果发现 semantic PRD defect（PRD 语义缺陷），停止自动 loop，生成 candidate，进入人工评审。

核心原则：

```text
Rule finds the problem.
Loop repairs the projection.
Validator proves the repair.
Report explains the decision.

规则发现问题。
回路修补投射。
校验证明修补有效。
报告解释决策。
```
