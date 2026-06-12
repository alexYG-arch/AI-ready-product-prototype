# Prototype Harness Loop Upgrade v3.1（原型 Harness 反馈回路升级包 v3.1）

本包把 prototype harness 从一次性线性流水线升级为受控反馈回路系统。

核心目标：

- 将 loop（反馈回路）从 retry（重试）提升为 diagnose → route → repair → rerun → revalidate → exit 的工程机制。
- 保持 PRD-first / fact-bundle-first，loop 默认只修补 materialization artifacts（物化产物），不直接写 PRD fact store。
- 将 loop 分层：Inference Loop（推理回路）、Materialization Loop（物化回路）、Annotation / Sidecar Loop（说明侧车回路）、Layout Loop（布局回路）、Validation Repair Loop（校验修补回路）、Governance Loop（治理回路）。
- 提供三档 Loop Profile（回路配置档位）：simple / standard / complex。它们不是不可变硬编码规则，而是由任务风险、约束、系统交接、异步、恢复复杂度推导出的默认策略，可被配置覆盖。

主要入口：

- `docs/LOOP_ENGINEERING_DESIGN_GUIDE_v3_1.md`
- `rules/15_complete_loop_rules.yaml`
- `rules/12_harness_macro_loop_rules.yaml`
- `rules/08_stage_loop_contracts.yaml`
- `codex/CODEX_LOOP_UPGRADE_PROMPT.md`

校验：

```bash
python3 scripts/validate_yaml.py
```
