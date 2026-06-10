# Harness Rule & Validator Review

Status: approved_by_human_review

本文件用于人工 review sub-harness 的规则和 validator。每条规则同时保留：

- 自然语言说明：给 PM、Tech Lead、QA、Data、Ops review。
- machine mapping：给后续脚本或 validator 实现使用。
- human review prompt：人工决策时要回答的问题。

## v3.0 Prototype DRD Mode Review Addendum

v3.0 将 `prototype_projection_harness` 默认升级为 DRD Mode（设计评审文档模式）。人工 review 时按以下边界判断：

- PRD / `prd_fact_bundle` 是事实源；runtime 只能作为 validation、gap、candidate、review evidence。
- DRD Mode 不写真实 Figma `node.reactions`；`RND-07` 必须 skipped。
- 渲染输入必须是 source slices、materialization manifest 和 board/page shards，不得回退为单体大 payload。
- 每个 board、frame、panel packet 必须声明 host surface 或 inherited host surface。
- 每个语义交互必须有 Figma Dev Mode annotation 或 collapsed summary annotation。
- 每条 Pen logic line 必须引用 `interaction_id` 和 `annotation_id`。
- Pen line 只做文档说明，不是真实交互行为，也不能创造 interaction packet 中不存在的新逻辑。
- Figma diff、annotation edit、Pen line edit 只能生成 candidate 或 review log，不能直接写 PRD fact store。

Prototype DRD review 必问：

- 是否只展示必要状态，而不是自动生成全量 loading/empty/error/success/recovery？
- 每个关键渲染字段是否能追踪到 source slice？
- host surface 推理是否有来源证据或明确 design assumption？
- annotations 是否锚定 source component、region、state frame 或 gateway，而不是 canvas note / REST comment？
- Pen line 是否 documentation-only，并且和 interaction packet / annotation packet 可回链？
- 是否有 harness audit/memory/candidate artifact 混入 product board？

## 1. 已补充文件清单

| Harness | 需要补充的文件 | 补充内容 |
|---|---|---|
| `prd_core_harness` | `prd_core_profile.yaml` | 新增核心事实类型、来源规则、边界规则、gap 规则。 |
| `prd_core_harness` | `validators.yaml` | 补充 contract/source/gap validator 的自然语言映射和机器规则。 |
| `requirement_harness` | `cears_quality_profile.yaml` | 补充 C-EARS 质量门禁、pattern、来源和数值规则映射。 |
| `requirement_harness` | `requirement_pattern_registry.yaml` | 补充多模式 C-EARS 选择规则、自然语言转换步骤和转换风险。 |
| `requirement_harness` | `validators.yaml` | 补充 requirement contract/source/gap validator 的自然语言映射和机器规则。 |
| `screen_state_harness` | `state_reasoning_rules.yaml` | 补充状态链、状态维度、文案与可访问性规则映射。 |
| `screen_state_harness` | `validators.yaml` | 补充 screen contract/source/gap validator 的自然语言映射和机器规则。 |
| `metrics_events_harness` | `metric_event_profile.yaml` | 补充 metric state、禁止编造 target、埋点计划规则映射。 |
| `metrics_events_harness` | `validators.yaml` | 补充 metrics/events contract/source/gap validator 的自然语言映射和机器规则。 |
| `release_ops_harness` | `release_ops_profile.yaml` | 补充发布字段、高风险人工 review、监控回滚规则映射。 |
| `release_ops_harness` | `validators.yaml` | 补充 release contract/source/gap validator 的自然语言映射和机器规则。 |
| `projection_sync_harness` | `prd_template_profile.yaml` | 补充模板完整性、来源追踪、占位符/空章节规则映射。 |
| `projection_sync_harness` | `prd_section_projection_map.yaml` | 补充章节来源和 forbidden fact source review 规则。 |
| `projection_sync_harness` | `validators.yaml` | 补充 projection contract/source/gap validator 的自然语言映射和机器规则。 |
| `traceability_harness` | `traceability_profile.yaml` | 补充追踪链、影响分析、覆盖状态规则映射。 |
| `traceability_harness` | `validators.yaml` | 补充 traceability contract/source/gap validator 的自然语言映射和机器规则。 |
| `scripts/prd_control/harnessctl.py` | `validate-rule-specs` command | 校验每个 validator 是否具备自然语言映射和机器规则字段。 |

## 2. 人工 Review 规则

### PRD Core Harness

Intent：保护背景、问题、用户、目标、范围、非目标、风险和开放问题的事实边界。

Review questions：

- 核心事实是否都有来源？
- 是否把未知信息写成了 confirmed？
- 是否越权批准了需求、页面、指标或发布事实？
- 缺失信息是否进入 `unknowns` 或 `open_questions`？

### Requirement Harness

Intent：把需求整理成 pattern-based C-EARS、语义槽、fit criteria、验收和 verification。

#### C-EARS 多模式转换

C-EARS 不是单一句式转换。人工 review 时必须先确认 pattern，再确认语义槽和转换结果。

| 模式 | 适用场景 | 转换规则 | Review 风险 |
|---|---|---|---|
| `event_driven` 事件触发型 | 点击、提交、收到事件后系统响应 | `trigger → component → response → acceptance` | 不要把持续状态误写成瞬时事件。 |
| `state_driven` 状态驱动型 | 用户或系统处于某状态时的行为 | `state → component → behavior → entry_condition → exit_condition` | 必须有进入/退出条件。 |
| `conditional` 条件型 | 满足条件时执行响应 | `condition → component → response` | 不要把异常恢复写成普通条件。 |
| `exception_handling` 异常处理型 | 失败、错误、超时、无权限、重试 | `failure_condition → user_visible_feedback → recovery_path` | 必须有用户可见反馈和恢复路径。 |
| `data_rule` 数据规则型 | 数据记录、校验、同步、埋点属性 | `event → data_service → properties → validation` | 需和 metrics/events 口径对齐。 |
| `permission_privacy` 权限/隐私型 | 授权、禁止行为、隐私边界 | `permission_condition → forbidden_action → fallback` | 不能只写“不得”，必须写 fallback。 |
| `non_functional_fit_criteria` 非功能数值型 | 性能、准确率、容量、时延等 | `scale → meter → baseline → target → verification` | baseline 不明不能编 target。 |
| `experiment` 实验型 | A/B、分组、变体、guardrail | `experiment_group → variant_behavior → metric → guardrail` | 指标需和 metrics harness 对齐。 |
| `release_rule` 发布型 | 发布条件、灰度、回滚 | `release_condition → release_owner → release_action → rollback_condition` | 应路由 release ops，不在需求层批准。 |
| `compliance` 合规型 | 审计、监管、证据留存 | `compliance_scope → compliance_behavior → evidence` | 必须说明证据和适用范围。 |

转换顺序：

1. 拆原子需求。
2. 选择 C-EARS 模式并记录选择理由。
3. 填 required slots，缺槽写 gap/open question。
4. 渲染中文 C-EARS。
5. 进入 REQ 结构化记录环节，形成 `requirement_candidate` 或 `requirement record`。
6. 补 acceptance 和 verification。
7. 做数值化审核。

#### C-EARS 后 REQ 环节

C-EARS 后不能直接跳到验收或数值化，必须先落成 REQ 记录。REQ 记录是后续排序、追踪、验收、测试、数值化和人工批准的载体。

REQ 记录必填字段：

| 字段 | 作用 |
|---|---|
| `id` | 稳定需求 id，用于 traceability 和 change patch。 |
| `title` | 人能快速理解的需求标题。 |
| `priority` | P0/P1/P2/P3，用于质量门禁强度。 |
| `evidence_status` | `confirmed`、`derived`、`candidate`、`assumed` 或 `missing`。 |
| `source_refs` | 来源引用；confirmed 必须有。 |
| `pattern_id` | C-EARS 模式。 |
| `cn_ears` | 中文 C-EARS 表达。 |
| `semantic_slots` | 从模式 required slots 填出的结构化语义。 |
| `gaps` | 缺来源、缺槽、缺验收、缺数值化时必须记录。 |

REQ 环节 review 必问：

- 这是一条可追踪的 requirement record，还是只是一句 C-EARS 文本？
- `evidence_status` 是否正确？LLM 生成是否被错误写成 confirmed？
- 缺槽、缺来源、缺验收或缺数值化时，是否进入 `gaps`？
- 该记录应进入 `requirement_candidates` 还是 `requirements`？

#### C-EARS 后数值化审核

REQ 记录建立后，不能直接算完成，必须做 `quantification_review`：

| 决策 | 何时使用 | 必填信息 |
|---|---|---|
| `quantified` | 需求可以被量化验收 | `scale`、`meter`、`baseline`、`target`、`tolerance`、`measurement_window`、`verification_method`、`source_refs` |
| `not_quantifiable_yet` | 应该量化，但现在缺 baseline、meter 或数据来源 | `missing_baseline_or_meter`、`owner_candidate`、`required_before`、`temporary_fit_criteria` |
| `not_applicable` | 该需求不适合数值化 | `reason`、`reviewer` |

数值化 review 必问：

- 这条需求是否需要量化？
- 如果量化，scale/meter/baseline/target 的来源是什么？
- target 是否能转成 fit criteria？
- verification_method 是否能真实验证？
- 如果不量化，是否有 reviewer 和 reason？

Review questions：

- pattern 是否合适，required slots 是否完整？
- P0/P1 是否有 source_refs、acceptance、verification、quality_profile？
- C-EARS 是否只是语法正确，还是已经可验收、可测试？
- 是否完成 `quantification_review`，并避免凭空生成数值 target？

### Screen State Harness

Intent：覆盖页面语义、入口出口、异常路径、恢复、文案和可访问性。

#### 状态链完整定义

“用户任务到状态结果的推理链完整”不是一句泛化描述，最低要求是：

| 字段 | 定义 |
|---|---|
| `feature` | 状态属于哪个功能。 |
| `task` | 用户试图完成什么任务。 |
| `journey_step` | 状态发生在用户旅程的哪个步骤。 |
| `decision_point` | 用户或系统需要判断什么。 |
| `interaction` | 用户执行了什么交互，或系统接收了什么输入。 |
| `trigger` | 什么事件触发状态变化。 |
| `system_operation` | 系统执行了什么操作。 |
| `outcome` | 操作结果是什么。 |
| `state` | 页面展示的明确状态。 |
| `recovery` | 失败、阻塞或异常时用户如何恢复。 |
| `acceptance_or_event` | 如何验收该状态，或用哪个事件观测它。 |

通过条件：

- 关键路径状态覆盖上述全部字段。
- 异常路径至少覆盖 `trigger`、`outcome`、`state`、`recovery`、`copy`、`acceptance_or_event`。
- 每个非成功状态都有 `user_visible_feedback` 和 `next_action`。
- 每个状态有 `source_refs`、`requirement_refs` 或 `candidate_reason`。
- 不适用字段必须写 `not_applicable reason`，不能留空。

失败条件：

- 只有页面名或状态名，没有触发、结果或恢复路径。
- 失败、错误、超时、无权限状态没有用户可见反馈。
- 状态链不能回连到需求、验收或事件。
- 关键状态维度缺失且没有 `screen_state_gap`。
- 把推测状态写成 confirmed。

常见流程最低状态覆盖：

- 输入/表单：`initial`、`editing`、`validating`、`submitting`、`success`、`field_error`、`request_error`、`disabled`、`retry_or_recovery`
- 数据读取：`loading`、`success_with_data`、`empty`、`partial_data`、`error`、`refreshing`、`offline_or_timeout`
- 权限/隐私：`permission_unknown`、`requesting_permission`、`permission_granted`、`permission_denied`、`fallback`、`privacy_notice`
- 异步操作：`queued`、`processing`、`completed`、`failed`、`cancelled`、`retrying`、`status_unknown`

Review questions：

- 用户任务到状态结果的推理链是否满足上述最低字段？
- loading、empty、error、permission、offline、retry 是否覆盖？
- 用户可见状态是否有文案和可访问性考虑？
- 是否越权批准了需求或指标？

### Metrics Events Harness

Intent：确保指标、事件、漏斗、实验和埋点计划有来源、口径和负责人。

Review questions：

- 指标当前状态是 measurable_now、needs_instrumentation、proxy_only、qualitative_prelaunch 还是 blocked？
- baseline 和 target 是否有来源？
- 需要埋点时是否写清 required_events、owner、required_before 和 forbidden_inference？
- 事件属性是否有触发条件、类型、owner 和来源？

### Release Ops Harness

Intent：确保发布、灰度、监控、回滚、运营和客服准备度可执行、可回退。

Review questions：

- 是否有 rollout_strategy、monitoring、rollback_conditions、ops_readiness、FAQ/support notes？
- GA、回滚条件、客服口径是否人工 review？
- 发生问题时如何发现、谁处理、什么时候回滚？

### Projection Sync Harness

Intent：确保 `PRD.md` 只是结构化事实的可读投影，不反向创造事实。

Review questions：

- `PRD.md` 是否有完整 14 章？
- 每章是否能回链到 `prd_section_projection_map.yaml` 中允许的来源？
- 是否还存在模板占位符或只有标题的章节？
- 是否在 `PRD.md` 中新增了 YAML 没有的 confirmed fact？

### Traceability Harness

Intent：确保 Goal、Requirement、Screen、Event、Acceptance、Test、Monitoring 可追踪。

Review questions：

- 追踪链是否覆盖关键目标和需求？
- partial、uncovered、blocked 是否有原因、owner 和 required_before？
- requirement/screen/metric/event/release/delete 变更是否都有 impact_analysis 和 partial_rerun_plan？
- 是否引用了不存在或已删除但未 tombstone 的 id？

## 3. Review Decision 建议

人工 review 每条规则时建议给出：

- `approved`: 可以进入后续 validator 实现。
- `revise`: 规则方向对，但需要改自然语言或机器字段。
- `rejected`: 不符合 harness intent，应删除或重写。

建议把人工结论写入 `prd_orchestrator/review_decisions/`，并在后续实现 validator 代码时引用该 decision。

## 4. 细颗粒度 Review Matrix

本节是人工 review 的逐条检查表。Reviewer 不应只判断“方向正确”，而应逐项确认生成/处理规则和 validator 规则是否可执行、可追溯、可被后续 harness 使用。

### 4.1 PRD Core Harness

Intent：把旧 PRD、变更请求和人工决策中的核心产品事实整理成可追溯的背景、问题、目标、范围、非目标、风险和开放问题，并守住“不替其他 harness 做事实确认”的边界。

#### 生成/处理规则

| Rule | 自然语言解释 | 输入 | 输出 | 人工 Review 判定 |
|---|---|---|---|---|
| `CORE-GEN-001` 来源盘点 | 先从旧 PRD、change request、review decision 中抽取核心事实，不能直接补脑。 | `legacy_prd.md`、change request、review decision | core fact candidates | 每条事实是否能指出来源位置？ |
| `CORE-GEN-002` 事实分类 | 把事实分为 problem、goal、scope、non_goal、risk、dependency、open_question。 | core fact candidates | typed core facts | 分类是否准确？是否把需求或发布决策混进 core？ |
| `CORE-GEN-003` 证据状态 | 给每条核心事实标 evidence status：confirmed、derived、candidate、assumed、missing。 | typed core facts | evidence_status | LLM 推断是否被错误标为 confirmed？ |
| `CORE-GEN-004` 缺口处理 | 目标用户、范围、成功标准、风险 owner 不足时写入 unknown/open question。 | missing core fields | `unknowns`、`open_questions` | 缺失是否被显式记录，还是被空白跳过？ |
| `CORE-GEN-005` 下游影响 | 核心事实变化影响需求、追踪或 PRD 投影时，必须产生 downstream routing。 | changed core facts | impact candidates | 是否触发 requirement/traceability/projection sync？ |

#### Validator 规则

| Validator | 粒度 | 通过条件 | 失败条件 | 人工 Review 问题 |
|---|---|---|---|---|
| `prd_core_harness_contract_validator` | ownership | 只修改核心事实或 orchestrator 证据文件。 | 写了 C-EARS、页面状态、metric target、release rollout。 | 这条变更是否越权？ |
| `prd_core_harness_source_ref_validator` | source | confirmed core fact 有 source_refs 或 review decision。 | assumed/missing 被写成 confirmed。 | 来源是否可被独立核对？ |
| `prd_core_harness_gap_validator` | gap | 缺失字段进入 unknown/open question，并有 owner/target harness。 | 关键字段空白但无 gap。 | 哪些缺口会阻塞首次迁移？ |

### 4.2 Requirement Harness

Intent：把自然语言需求拆成原子需求，选择合适的 C-EARS 模式，补齐语义槽，形成 REQ 结构化记录，并经过验收、验证、数值化和下游交接审核。

#### 生成/处理规则

| Rule | 自然语言解释 | 输入 | 输出 | 人工 Review 判定 |
|---|---|---|---|---|
| `REQ-GEN-001` 原子需求拆分 | 一条候选只能表达一个行为、条件、异常、数据或发布意图。 | raw requirement text | atomic requirement | 是否需要拆成多条？ |
| `REQ-GEN-002` C-EARS 模式选择 | 根据意图选择事件、状态、条件、异常、数据、权限、非功能、实验、发布或合规模式。 | atomic requirement | `pattern_id`、selection reason | 模式是否匹配原始意图？ |
| `REQ-GEN-003` 语义槽填充 | 按 pattern required_slots 填槽；缺槽写 gap，不硬补。 | pattern + atomic text | `semantic_slots`、slot gaps | 每个槽是否有来源？ |
| `REQ-GEN-004` C-EARS 渲染 | 用已填槽渲染中文 C-EARS，不能在句式化时新增事实。 | semantic slots | `cn_ears` | 句子是否忠实来源？ |
| `REQ-GEN-005` REQ 结构化记录 | C-EARS 后必须生成 `requirement_candidate` 或 `requirement record`，承载 id、priority、evidence、source、gaps。 | `cn_ears` + slots | REQ record | 是否只是句子，还是可追踪记录？ |
| `REQ-GEN-006` 验收与验证 | 给 REQ record 补 acceptance 和 verification；不可验证则不能 confirmed。 | REQ record | acceptance、verification | QA/工程能否判断完成？ |
| `REQ-GEN-007` 数值化审核 | 判断是否能量化；能则生成 scale/meter/baseline/target/tolerance/window，不能则给 reason。 | REQ record | `quantification_review`、fit criteria | 数字是否有来源，不能量化是否有 reviewer reason？ |
| `REQ-GEN-008` 下游交接 | 页面、指标、发布、追踪相关字段不得在 requirement 层最终批准，需写 impact/rerun。 | approved/candidate REQ | impact candidates | 是否交给 screen/data/release/traceability？ |

#### 推理补全规则

推理补全只允许补出候选，不允许把推断结果直接写成 confirmed。

| Rule | 自然语言解释 | 允许输入 | 输出 | 人工 Review 判定 |
|---|---|---|---|---|
| `REQ-INFER-001` 推断主体/组件 | 原句省略责任主体时，可从同一变更、相邻需求或旧 PRD 上下文推断候选 component。 | change request context、confirmed requirement refs、legacy PRD context | `semantic_slots.component`、`inference_notes`、`slot_gaps` | 这个主体是明示，还是推断？依据是什么？ |
| `REQ-INFER-002` 推断触发/条件/状态 | 原句暗含触发条件、状态或前置条件时，可补为候选 trigger/condition/state。 | raw text、neighboring requirements、screen state candidates | trigger/condition/state、`inference_notes` | 是否新增了产品决策，还是只显化原文隐含条件？ |
| `REQ-INFER-003` 推断验收候选 | 可从 response、fit criteria 或异常恢复中推导 acceptance candidate。 | `cn_ears`、semantic slots、fit criteria、verification hints | acceptance candidate、verification gaps | 验收是在验证需求，还是偷偷新增行为？ |
| `REQ-INFER-004` 推断下游交接 | 需求暗含页面、指标、事件或发布影响时，生成 downstream handoff candidate。 | pattern、slots、acceptance candidate、quantification review | target harness candidate、impact candidate、open questions | 是否交给正确下游 harness，且未越权确认？ |

#### C-EARS 转换自然语言解释

| 模式 | 自然语言转换解释 |
|---|---|
| `event_driven` | 找出“发生了什么事件/动作”，写成 trigger；找出系统哪个部分响应，写成 component；把必须产生的结果写成 response；再补验收。 |
| `state_driven` | 先定义用户/系统所处状态，再定义该状态下组件必须表现出的行为，同时写清进入和退出条件。 |
| `conditional` | 把判断前提写成 condition，只在条件成立时要求 component 给出 response；失败恢复不走这个模式。 |
| `exception_handling` | 把失败原因写成 failure_condition，把用户能看到的提示写成 feedback，再写恢复路径。 |
| `data_rule` | 把触发数据处理的业务事件写成 event，把记录/处理方写成 data_service，把字段写成 properties，并写 validation。 |
| `permission_privacy` | 写清权限/隐私前提、禁止行为和 fallback；只有“不得”没有 fallback 不完整。 |
| `non_functional_fit_criteria` | 定义测量范围、量尺、baseline、target 和验证方法；baseline 不明时不能编 target。 |
| `experiment` | 写清实验组、变体行为、主指标和 guardrail，并交叉检查 data harness。 |
| `release_rule` | 写清发布条件、负责人、发布动作和回滚条件，并交给 release ops 细化。 |
| `compliance` | 写清合规范围、必须行为和证据来源。 |

#### Validator 规则

| Validator | 粒度 | 通过条件 | 失败条件 | 人工 Review 问题 |
|---|---|---|---|---|
| `requirement_harness_contract_validator` | shape + boundary | REQ record 完整，pattern 已知，slots 满足 required_slots，不越界。 | 只有 C-EARS 无 REQ record；写了页面/指标/发布 confirmed fact。 | 是否形成可追踪需求记录？ |
| `requirement_harness_source_ref_validator` | source | confirmed/approved 有 source_refs 或 review decision。 | LLM candidate 被直接 confirmed；unknown 写入需求正文。 | 这条需求凭什么确认？ |
| `requirement_harness_gap_validator` | quality | C-EARS、REQ record、acceptance、verification、quantification_review 都存在或有 gap。 | 缺槽、缺验收、缺数值化但通过质量门禁。 | 它是“像需求”，还是已可验收可测试？ |

### 4.3 Screen State Harness

Intent：把需求和页面语义推导成完整状态链，覆盖场景必备状态、异常恢复、用户文案、可访问性和验收/事件观测，同时防止把推测状态写成 confirmed。

#### 生成/处理规则

| Rule | 自然语言解释 | 输入 | 输出 | 人工 Review 判定 |
|---|---|---|---|---|
| `SCREEN-GEN-001` 场景分类 | 先判断是表单/输入、数据读取、权限隐私、异步操作或其他场景。 | requirement refs、screen text | scenario type | 场景类型是否正确？ |
| `SCREEN-GEN-002` 状态清单 | 根据场景列出必备状态，例如 loading、empty、error、retry、permission_denied。 | scenario type | state inventory | 是否漏掉用户会遇到的状态？ |
| `SCREEN-GEN-003` 状态链组装 | 每个关键状态要有 feature、task、journey_step、interaction、trigger、operation、outcome、state、recovery、acceptance/event。 | state inventory | state_reasoning_chain | 链路是否能从任务推到结果？ |
| `SCREEN-GEN-004` 状态维度覆盖 | 检查 data、network、permission、input、request_lifecycle、consistency、recovery、platform/device。 | state chain | dimension coverage | 缺失维度是否有 not_applicable reason？ |
| `SCREEN-GEN-005` 文案与可访问性 | 错误、空态、禁用、成功和恢复路径需要用户可见文案与可访问性说明。 | states | copy/a11y notes | 用户是否知道发生什么和下一步？ |
| `SCREEN-GEN-006` gap 记录 | 不确定的状态、文案、设计或验收事件写入 `screen_state_gaps`。 | missing states | gaps | 是否把推测写成 confirmed？ |

#### 推理补全规则

推理补全用于发现缺失状态和链路断点；补出的状态、恢复、文案、事件只能是 candidate 或 gap。

| Rule | 自然语言解释 | 允许输入 | 输出 | 人工 Review 判定 |
|---|---|---|---|---|
| `SCREEN-INFER-001` 补全必备状态 | 根据场景类型补出可能缺失的 loading、empty、error、permission、retry 等状态候选。 | scenario type、scenario required states、requirement refs | state candidates、screen_state_gaps、inference_notes | 这个状态是需求/设计明示，还是场景规则推断？ |
| `SCREEN-INFER-002` 补全恢复路径 | 错误、失败、超时、无权限、离线等非成功状态必须推导 recovery/next_action 候选。 | state、outcome、error reason、requirement refs | recovery、next_action、gaps | 用户失败后能做什么？不能确定是否记录 gap？ |
| `SCREEN-INFER-003` 补全文案与可访问性候选 | 根据状态和恢复路径生成 candidate copy/a11y，等待设计或人工 review。 | state、feedback、recovery、a11y context | candidate_copy、candidate_a11y、review_required | 是否需要设计、内容或合规确认？ |
| `SCREEN-INFER-004` 补全验收/事件链接 | 状态链末端需要验收或观测事件；缺失时生成 acceptance/event link candidate 并路由下游。 | state chain、requirement refs、event candidates | acceptance/event candidate、target harness candidate、open questions | 这个状态如何被验收或观测？ |

#### Validator 规则

| Validator | 粒度 | 通过条件 | 失败条件 | 人工 Review 问题 |
|---|---|---|---|---|
| `screen_state_harness_contract_validator` | chain completeness | 状态链满足 minimum_complete_chain，场景必备状态覆盖或 N/A。 | 只有页面/状态名称，没有 trigger/outcome/recovery。 | 用户任务到状态结果是否闭合？ |
| `screen_state_harness_source_ref_validator` | source | confirmed 状态引用 requirement/design/review decision。 | 推测状态写成 confirmed；文案无来源却 final。 | 状态来自哪里？ |
| `screen_state_harness_gap_validator` | state coverage | 缺状态、缺维度、缺文案、缺 a11y 都有 gap。 | error/offline/permission/retry 无反馈或恢复。 | 哪些用户路径还没覆盖？ |

### 4.4 Metrics Events Harness

Intent：把目标、需求和实验意图转成可度量的指标、事件、漏斗和埋点计划，明确 baseline/target 来源、采集状态、owner 和禁止推断边界。

#### 生成/处理规则

| Rule | 自然语言解释 | 输入 | 输出 | 人工 Review 判定 |
|---|---|---|---|---|
| `DATA-GEN-001` 指标意图识别 | 判断是成功指标、guardrail、诊断指标、漏斗指标还是实验指标。 | goals、requirements | metric candidates | 指标是否回答正确问题？ |
| `DATA-GEN-002` 度量状态判定 | 标记 measurable_now、needs_instrumentation、proxy_only、qualitative_prelaunch 或 blocked。 | metric candidate | metric state | 现在是否真的量得到？ |
| `DATA-GEN-003` baseline/target 审核 | baseline 和 target 必须有来源；没有 baseline 时 target 为 TBD_AFTER_BASELINE。 | metric state | baseline/target decision | 是否存在伪精确数字？ |
| `DATA-GEN-004` 事件设计 | 为指标列出 required events、trigger、properties、owner、source。 | metric candidate | event candidates | 事件是否足够支撑指标？ |
| `DATA-GEN-005` 埋点计划 | needs_instrumentation 时写 owner、required_before、forbidden_inference。 | event candidates | instrumentation plan | 工程/数据能否接手？ |
| `DATA-GEN-006` 隐私与属性检查 | 事件属性要检查敏感性、必要性和禁止推断。 | event properties | privacy notes/gaps | 是否收集了不该收集的数据？ |

#### Validator 规则

| Validator | 粒度 | 通过条件 | 失败条件 | 人工 Review 问题 |
|---|---|---|---|---|
| `metrics_events_harness_contract_validator` | metric/event shape | metric/event id、definition/trigger、owner、source_refs 完整。 | 缺 owner、重复 id、越界批准需求或发布。 | 数据模型是否可执行？ |
| `metrics_events_harness_source_ref_validator` | number/source | baseline、target、event trigger、properties 有来源。 | baseline 不明仍生成 target。 | 数字和属性是否编造？ |
| `metrics_events_harness_gap_validator` | instrumentation | needs_instrumentation 有事件、owner、required_before、forbidden_inference。 | 指标声称 measurable_now 但缺事件。 | 量不到的地方是否说清楚？ |

### 4.5 Release Ops Harness

Intent：把发布意图转成可执行、可监控、可回滚的发布计划，覆盖灰度阶段、负责人、监控、回滚、运营和客服准备，并标出高风险人工 review 点。

#### 生成/处理规则

| Rule | 自然语言解释 | 输入 | 输出 | 人工 Review 判定 |
|---|---|---|---|---|
| `REL-GEN-001` 发布阶段识别 | 判断 Alpha、Beta、GA 或分阶段灰度。 | requirements、risks | rollout stage | 阶段是否符合风险和准备度？ |
| `REL-GEN-002` 发布字段补齐 | 补 rollout_strategy、monitoring、rollback_conditions、ops_readiness、support notes。 | release intent | release plan | 缺项是否有 N/A reason 或 gap？ |
| `REL-GEN-003` 监控回滚绑定 | 每个 rollout 必须绑定监控指标和回滚条件。 | rollout plan | monitoring/rollback | 出问题如何发现和回退？ |
| `REL-GEN-004` 运营客服准备 | 用户可见变化需要 FAQ、客服口径、运营动作。 | release plan | ops/support notes | 对外口径是否需要人工批准？ |
| `REL-GEN-005` 高风险人工 review | GA、回滚条件变更、客服口径必须人工 review。 | release changes | review_required flags | 谁批准上线？ |

#### Validator 规则

| Validator | 粒度 | 通过条件 | 失败条件 | 人工 Review 问题 |
|---|---|---|---|---|
| `release_ops_harness_contract_validator` | release shape | 发布必填字段完整或有 N/A reason。 | 有 rollout 无 monitoring/rollback。 | 上线计划是否可执行？ |
| `release_ops_harness_source_ref_validator` | decision source | GA/rollback/support 有 source/reviewer。 | 对外口径无 review 即 final。 | 决策是否被负责人批准？ |
| `release_ops_harness_gap_validator` | readiness gaps | owner、monitoring、rollback、FAQ 缺失时有 gap。 | 空发布计划无 gap。 | 上线前还缺什么？ |

### 4.6 Projection Sync Harness

Intent：把结构化事实投影为完整可读的 `PRD.md`，保持章节完整、来源可追踪、无占位符，并防止 `PRD.md` 反向创造 confirmed fact。

#### 生成/处理规则

| Rule | 自然语言解释 | 输入 | 输出 | 人工 Review 判定 |
|---|---|---|---|---|
| `PROJ-GEN-001` 章节来源映射 | 每个 PRD 章节只从 projection map 允许的文档取事实。 | YAML + map | section source plan | 来源是否越界？ |
| `PROJ-GEN-002` 事实投影 | 把结构化事实转成可读 PRD，不新增 confirmed fact。 | source facts | PRD section draft | 叙述是否忠实来源？ |
| `PROJ-GEN-003` gap/N/A 展示 | 缺信息时写 gap 或 not_applicable reason，不留模板占位。 | missing facts | PRD gaps/N/A | 读者是否知道缺什么？ |
| `PROJ-GEN-004` 反向事实防护 | `PRD.md` 不作为 YAML confirmed fact 来源。 | PRD draft | projection report | 是否把 PRD 文案反写成事实？ |

#### Validator 规则

| Validator | 粒度 | 通过条件 | 失败条件 | 人工 Review 问题 |
|---|---|---|---|---|
| `projection_sync_harness_contract_validator` | template/boundary | 14 章齐全，章节来源合法，不新增事实。 | 非 projection patch 直接改 PRD fact。 | PRD 是否只是投影？ |
| `projection_sync_harness_source_ref_validator` | source trace | 关键事实能回链到 YAML/review/legacy source。 | PRD 有来源不存在的 confirmed fact。 | 抽查事实能回链吗？ |
| `projection_sync_harness_gap_validator` | substance | 无占位符，标题下有内容、gap 或 N/A reason。 | 章节 title-only 或保留模板文案。 | 哪些章节仍是模板？ |

### 4.7 Traceability Harness

Intent：建立 Goal、Requirement、Screen、Event、Acceptance、Test、Monitoring 的追踪链，并为变更、删除和覆盖缺口生成影响分析、局部重跑计划和 tombstone。

#### 生成/处理规则

| Rule | 自然语言解释 | 输入 | 输出 | 人工 Review 判定 |
|---|---|---|---|---|
| `TRACE-GEN-001` ID 盘点 | 收集 goal、requirement、screen、event、acceptance、test、monitoring id。 | source docs | id inventory | id 是否稳定且唯一？ |
| `TRACE-GEN-002` 链路建立 | 连接 Goal → Requirement → Screen → Event → Acceptance → Test → Monitoring。 | id inventory | trace links | 链路是否有断点？ |
| `TRACE-GEN-003` 覆盖状态 | 每段链路标 covered、partial、uncovered、blocked、deprecated。 | trace links | coverage status | 非 covered 是否有原因？ |
| `TRACE-GEN-004` 影响分析 | requirement/screen/metric/event/release/delete 变更必须产出 impact_analysis。 | changed ids | impact analysis | 下游影响是否完整？ |
| `TRACE-GEN-005` 局部重跑计划 | 根据 impact_analysis 生成 partial_rerun_plan。 | impact analysis | rerun plan | 是否漏 rerun projection/traceability？ |
| `TRACE-GEN-006` tombstone | 删除或废弃对象必须有 tombstone 和替代/影响说明。 | delete/deprecate patch | tombstone | 是否仍有链路引用旧 id？ |

#### Validator 规则

| Validator | 粒度 | 通过条件 | 失败条件 | 人工 Review 问题 |
|---|---|---|---|---|
| `traceability_harness_contract_validator` | trace shape/boundary | 只维护 trace/impact/rerun/tombstone，不生成新需求。 | 追踪 patch 发明 requirement。 | 是否越权创造事实？ |
| `traceability_harness_source_ref_validator` | ref integrity | 链接 id 存在或 tombstoned。 | 链接缺失 id，删除项无 tombstone。 | 是否有断链？ |
| `traceability_harness_gap_validator` | coverage | 非 covered 有 reason、owner、required_before。 | partial/uncovered/blocked 无原因。 | 未覆盖缺的是哪一环？ |

### 4.8 Prototype Projection Harness

Intent：把已批准的结构化 PRD facts 投射为 prototype runtime、Figma frame/reaction/map，并把 Figma semantic diff 回流为 candidate；原型和 Figma 永远不是事实源。

#### 生成/处理规则

| Rule | 自然语言解释 | 输入 | 输出 | 人工 Review 判定 |
|---|---|---|---|---|
| `PROTO-GEN-001` Harness 边界注册 | 原型 harness 是平级 projection harness，只拥有 runtime、Figma map、interaction map、diff report 和 projection report。 | orchestrator registry / document registry | prototype harness boundary | 是否越权拥有需求、页面、指标或 PRD fact？ |
| `PROTO-GEN-002` Runtime 来源控制 | Runtime 只能从 requirements、screens、metrics、events、traceability 和受控 binding 生成，不能从 PRD.md 或 Figma 文案反推。 | structured facts + binding adapters | prototype.runtime.json | 是否有任何 runtime 事实来自不允许来源？ |
| `PROTO-GEN-003` Runtime 完整性与 gap | Runtime 对象必须有稳定 semantic id、source_refs、状态维度；缺失信息进入 prototype_gaps。 | runtime model | source/dimension/gap report | 是否脑补了缺失交互、状态、组件或目标？ |
| `PROTO-GEN-004` Figma frame 投射 | 通过 semantic_id patch managed nodes，写 metadata，默认不 full rebuild designer-owned zones。 | runtime + sync map | Figma frames / node metadata | 是否保护设计师拥有区域和视觉覆盖？ |
| `PROTO-GEN-005` Figma reaction 投射 | 真实可点击交互必须来自 interaction_graph.edges[] 并投射为 Figma node reactions；Flow Map 只是说明。 | runtime edges + reaction map | Figma reactions / Interaction Spec | 真实连线是否来自 runtime edge，而不是说明箭头？ |
| `PROTO-GEN-006` Component / pattern binding | 组件优先绑定现有 Figma component，其次 pattern，再其次 semantic library，最后 placeholder + gap。 | component-binding-map + semantic library | component instances / binding gaps | 是否有静默降级或语义角色变化未进 candidate？ |
| `PROTO-GEN-007` Figma diff 分类 | Figma 修改按 visual_only、semantic_candidate、high_risk_candidate、conflict 分类，只生成 report/candidate。 | Figma semantic extract | figma_diff_report / candidate | 是否有 Figma diff 直接写 fact store？ |
| `PROTO-GEN-008` 三向 reverse sync | 反向同步必须比较上次 runtime、当前 Figma extract、当前 PRD runtime；同字段双边修改必须人工决策。 | base runtime + Figma extract + PRD runtime | conflict-aware candidate | 是否有冲突被自动覆盖？ |
| `PROTO-GEN-009` Two-pass runtime reasoning | 先生成 `prototype.runtime.base.json`，再生成带 `generation_lineage` 和 `reasoning_completion` 的 completed runtime。 | PRD fact bundle + base runtime | completed runtime / reasoning report | 推理补全是否有 source_refs、confidence、inference_basis，且未变成 confirmed fact？ |
| `PROTO-GEN-010` Renderer staged plan | 渲染必须按 RND-00 到 RND-09 执行，先冻结输入、布局路由、canvas skeleton，再写页面细节。 | completed runtime + copy catalog + layout plan | renderer stage outputs | 是否跳过 skeleton-first 或在渲染时补造产品逻辑？ |
| `PROTO-GEN-011` UX writer copy stage | UX copy 必须进入 copy catalog，保留 intent、source_refs、validation/research evidence 和高风险人审。 | runtime + UX writer rules | uxwriter-copy-catalog | 文案优化是否有依据，是否反写 PRD fact？ |
| `PROTO-GEN-012` Figma comment annotations | 交互说明使用 Figma comments，锚定 source component/hotspot/frame region；comment edit 只能成为 candidate。 | runtime edge + comment policy | figma-comment-map | comment 是否只是审阅说明，而不是事实源？ |
| `PROTO-GEN-013` Layout route and visual lines | visual pen lines 必须跟随 layout route plan；它们只是 documentation，不能代表可点击行为。 | layout route plan + interaction map | visual flow line map | 是否存在重复线、越过 corridor 或把视觉线当 reaction 的情况？ |
| `PROTO-GEN-014` Renderer skill hook | renderer skill pack 只能 advisory，并且必须留下 influence trace；不能覆盖 facts、validators 或 review。 | optional skill pack | renderer skill influence trace | skill 建议是否可追踪，是否越权改变产品事实？ |

#### Validator 规则

| Validator | 粒度 | 通过条件 | 失败条件 | 人工 Review 问题 |
|---|---|---|---|---|
| `PROTO-RUNTIME-*` | runtime source/id/dimensions/gaps | runtime 只来自允许来源，对象有稳定 id、source_refs、required dimensions，缺失进入 gaps。 | 从 PRD.md/Figma 反推事实，缺维度或缺来源仍通过。 | Runtime 是否只是可追踪投影？ |
| `PROTO-INTERACTION-*` | interaction graph/reaction consistency | edge、source、trigger、action、destination、source_refs 可解析，modal/toast 生命周期闭合。 | 说明线替代真实 reaction，重复 trigger 冲突，缺目标。 | 真实可点击交互是否完整？ |
| `PROTO-COMP-*` | component/pattern binding | 组件按优先级解析，variant 覆盖所需状态，语义角色变化进 candidate。 | 静默 placeholder，角色变化当视觉变化处理。 | 组件绑定是否改变语义？ |
| `PROTO-FIGMA-*` | Figma sync/reverse sync | managed node metadata 完整，保护 designer-owned zones，diff 只出 candidate，三向 diff 完整。 | full rebuild、直接写事实、无三向 diff。 | Figma 侧变化是否安全回流？ |
