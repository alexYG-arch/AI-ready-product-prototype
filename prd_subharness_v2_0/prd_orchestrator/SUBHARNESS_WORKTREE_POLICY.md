# Sub-Harness Worktree Policy

Status: approved_by_human_review

## 1. 结论

默认不为每个 sub-harness 常驻启用单独 worktree。当前优先使用 PRD instance 和 run 隔离，解决真实 PRD 输入、候选、报告和输出污染 harness 工程的问题。

单独 worktree 更适合 harness 开发隔离，不适合普通 PRD 运行隔离。

## 2. 什么时候启用

临时启用 sub-harness worktree 的条件：

- 多人或多个 agent 并行修改不同 sub-harness 的规则、validator、schema。
- 某个 sub-harness 正在做高风险实验，可能破坏共享 contract。
- requirement、screen、metrics 等规则要分别 review 和提交。
- 需要长时间保留某个 sub-harness 的实验分支。

## 3. 什么时候不要启用

不建议为普通 PRD 运行启用每个 sub-harness 一个 worktree：

- PRD 运行产物已经由 `prd_instances/<instance_id>/runs/<run_id>/` 隔离。
- sub-harness 之间共享 orchestrator、schema、traceability 和 projection contract，常驻拆分会增加同步成本。
- 每个 worktree 都可能产生不同版本的 harness 规则，人工 review 时更难判断哪个版本是事实基线。

## 4. 推荐模型

- 单一主 worktree：维护共享 orchestrator、schema、contract、validator 和基线规则。
- 独立 PRD instance：隔离每个真实 PRD 的输入、运行产物和输出。
- 临时 sub-harness worktree：只用于并行开发或高风险规则实验。
- 集成前必须回到主 worktree 跑 `validate-rule-specs` 和隔离 smoke。

## 5. 启用约束

如果启用 sub-harness worktree，应遵守：

- worktree 放在 harness 仓库外部或 `worktrees/` 忽略目录下。
- branch 命名建议：`harness/<sub_harness_id>/<topic>`。
- 不在 sub-harness worktree 中存放真实 `prd_instances/`。
- 修改共享文件时先回到集成分支，例如 `prd_orchestrator/*`、`schemas/*`、`scripts/*`。
- 合并前必须有人工 review 决策，确认自然语言规则、代码化规则和 validator 仍能一一映射。
