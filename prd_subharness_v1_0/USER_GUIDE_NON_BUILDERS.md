# 使用手册：PRD Sub-Harness v1.0

> 读者：产品经理、需求评审者、设计、测试、数据、运营、项目负责人。  
> 你不需要理解代码，也不需要自己搭建。你只需要知道：什么时候提交什么、系统会怎么处理、你要看什么、你要回答什么。

---

## 0. 先用人话解释

你可以把这套系统想象成一个“PRD 施工管理系统”。

普通 AI 改 PRD 是：

```text
你发一段话；
AI 直接改文档；
你不知道它改了哪里、漏了什么、脑补了什么、删了什么。
```

这个 harness 的方式是：

```text
你发一段自然语言变更；
系统先登记；
再拆成小变更；
再判断属于哪个专业小组；
再只改对应文件；
再检查有没有漏；
再同步到 PRD.md；
最后留下变更记录。
```

它不是为了让你写更多文档。  
它是为了让你不用反复追问：

```text
这个需求来源是什么？
这个页面状态有没有补？
这个指标是不是 AI 瞎猜的？
这个 PRD.md 为什么只有标题？
这个改动影响了哪些测试和埋点？
```

---

## 1. 你会看到哪些文件？

### 1.1 `product-spec/PRD.md`

这是给人看的主 PRD。  
v1.0 里它应该是完整 14 章，不应该只有标题。

你主要读它：

```text
看背景
看范围
看目标
看页面
看需求
看验收
看风险
看发布
```

### 1.2 `requirements.yaml`

这是给 AI 和工具看的需求事实库。

你不一定要每天读它，但当你要确认某条需求是否清楚时，可以看：

```text
Req ID
C-EARS 句子
source_refs
acceptance
verification
gaps
status
```

### 1.3 `screens.yaml`

这是页面语义和状态表。

它回答：

```text
页面目的是什么？
入口在哪里？
出口在哪里？
有哪些状态？
失败后怎么恢复？
有哪些文案？
有什么可访问性要求？
```

### 1.4 `metrics.yaml` / `events.yaml`

这是指标和埋点。

它回答：

```text
指标怎么定义？
baseline 是否已知？
target 是否可以设？
需要哪些埋点？
哪些不能让 AI 推导？
```

### 1.5 `traceability.md`

这是追踪表。

它回答：

```text
这个目标对应哪些需求？
这个需求影响哪个页面？
这个页面需要哪些埋点？
这个需求有哪些测试？
```

---

## 2. 你需要知道的四条路径

### 路径 A：第一次导入旧 PRD

当你有一份旧 PRD，第一次要转成 AI-ready PRD 包时，走这条路径。

```text
CORE-000：盘点旧 PRD
CORE-001：建立文件骨架
CORE-002：迁移目标、范围、非目标

REQ-003A：转成需求候选
REQ-003B：检查需求质量
REQ-003C：人工回答后晋升需求

SCREEN-004：补页面语义和状态
DATA-005：补指标和埋点
TRACE-006：建立追踪矩阵
PROJ-007：同步完整 PRD.md
```

通俗说：

```text
先体检；
再搭架子；
再整理需求；
再补页面、指标、埋点；
最后生成给人看的完整 PRD。
```

你需要做什么？

```text
1. 提供旧 PRD。
2. 审查盘点报告。
3. 回答系统列出的阻断问题。
4. 批准或驳回关键需求。
```

---

### 路径 B：日常自然语言更新

你可以直接写自然语言，例如：

```markdown
验证码有效期改成 5 分钟，重新发送验证码冷却期是 60 秒。登录失败要有重试入口。不要影响微信登录。
```

你不需要写 YAML。

系统会先走：

```text
CHANGE-INGEST
```

它会拆成：

```text
变更 1：验证码有效期 = 5 分钟
变更 2：重新发送冷却期 = 60 秒
变更 3：登录失败需要重试入口
变更 4：微信登录不在范围
```

然后系统判断：

```text
变更 1 / 2 属于 requirement_harness；
变更 3 属于 screen_state_harness；
变更 4 是 out of scope 约束。
```

你需要做什么？

```text
确认拆分是否正确；
确认是否有漏掉的影响；
回答系统提出的问题。
```

---

### 路径 C：一个 MD 里有多项内容

如果你发来的 MD 同时包含：

```text
登录
支付
会员
指标
页面
发布
```

系统不应该一轮全改。

它会先拆分：

```text
PRD-DELTA-001 登录相关
PRD-DELTA-002 支付相关
PRD-DELTA-003 指标相关
PRD-DELTA-004 发布相关
```

为什么？

```text
因为登录和支付影响范围不同，评审人也可能不同。
一个 patch 全改，容易漏。
```

你需要做什么？

```text
确认拆分方案。
不要要求“一次全做完”。
```

---

### 路径 D：回答开放问题

系统可能问你：

```text
OQ-AUTH-001：验证码有效期是多少？
```

你回答：

```text
5 分钟。
```

这不是重跑完整 PRD。  
它只会触发相关局部更新：

```text
requirement_harness 更新需求；
screen_state_harness 更新页面状态；
metrics_events_harness 必要时更新事件；
traceability_harness 更新追踪；
projection_sync_harness 更新 PRD.md。
```

你需要做什么？

```text
给清晰答案；
确认答案是否只适用于当前版本；
确认是否影响发布条件。
```

---

## 3. 子 Harness 是什么？

你可以把子 harness 理解为专业小组。

| 子 Harness | 人话解释 | 你什么时候会碰到 |
|---|---|---|
| `prd_core_harness` | 负责“为什么做、给谁做、做什么、不做什么”。 | 第一次迁移、改范围、改目标、改风险。 |
| `requirement_harness` | 负责把需求写清楚、写成可验证需求。 | 新增/修改功能需求。 |
| `screen_state_harness` | 负责页面、状态、错误、恢复路径。 | 改页面、补异常、补文案。 |
| `metrics_events_harness` | 负责指标、埋点、实验。 | 改指标、补埋点、做实验。 |
| `release_ops_harness` | 负责灰度、监控、回滚、客服运营。 | 准备上线、变更发布策略。 |
| `projection_sync_harness` | 负责把 YAML 内容同步成完整 PRD.md。 | 每次结构化事实更新后。 |
| `traceability_harness` | 负责追踪和影响分析。 | 每次变更后都可能用。 |

---

## 4. 为什么不让一个 harness 全部处理？

因为完整 PRD 很大。

一个 PRD 包含：

```text
目标
用户
范围
需求
页面
状态
指标
埋点
验收
发布
风险
变更
```

如果全部塞给一个 AI，很容易：

```text
上下文太长；
AI 漏掉内容；
错误同步；
维护困难；
review 很难看。
```

拆分后：

```text
每个子 harness 只看自己负责的内容；
总控 orchestrator 负责串起来。
```

---

## 5. C-EARS 现在不是死模板

以前可能只有：

```text
当 [...] 时，[系统] 应当 [...]。
```

v1.0 支持更多模式：

```text
事件触发型
状态驱动型
条件型
异常处理型
数据规则型
权限/隐私型
非功能数值规格型
实验型
发布型
合规型
```

比如：

### 事件触发型

```text
当用户点击“获取验证码”时，客户端应当校验手机号格式。
```

### 状态驱动型

```text
在验证码发送冷却期内，客户端应当禁用“获取验证码”按钮并展示剩余秒数。
```

### 异常处理型

```text
如果认证服务返回验证码发送失败，则客户端应当展示失败提示并提供重试入口。
```

### 非功能数值规格型

```text
当认证服务收到验证码发送请求时，认证服务应当在 p95 ≤ 2 秒内返回发送结果。
```

重点：

```text
句式像需求，不等于需求完整。
需求还要有来源、验收、数值、状态、追踪。
```

---

## 6. PRD.md 为什么不能只是标题？

因为 PRD.md 是给人看的。

如果 PRD.md 只有：

```text
## 功能需求
由 requirements.yaml 投影。
```

那产品、设计、研发、测试、数据和运营无法快速 review。

v1.0 要求 `projection_sync_harness` 把 YAML 内容投影到完整 PRD.md 中。

例如：

```text
requirements.yaml → PRD.md 第 8 章功能需求
screens.yaml → PRD.md 第 7 章页面语义说明
metrics.yaml → PRD.md 第 4 章目标与指标
events.yaml → PRD.md 第 10 章数据与实验
traceability.md → PRD.md 第 11/14 章
release-plan.md → PRD.md 第 12 章
```

---

## 7. 人工补充会不会很多？

会，但系统不会让你填整份 PRD。

它会把缺失项变成问题，并排序：

```text
Blocker：不回答就不能继续。
Review required：需要确认，但不一定阻断草稿。
Warning：建议补，可延期。
Deferred：后续版本处理。
```

你看到的不是：

```text
请补完整 14 章 PRD。
```

而是：

```text
请回答这 8 个阻断问题：
1. 验证码有效期是多少？
2. 冷却期是多少？
3. 失败后是否允许重试？
4. 登录成功率 baseline 是否已有？
...
```

---

## 8. 什么时候需要人工确认？

这些必须人工确认：

```text
删除需求；
新增 P0/P1；
候选需求变 approved；
assumption 变 confirmed；
metric baseline / target；
proposed API 变 existing API；
关闭 open question；
改变范围或 non-goal；
发布/灰度/回滚条件；
合规和隐私结论。
```

---

## 9. 你如何判断一个结果是否靠谱？

看四件事：

```text
source_refs：有没有来源？
gaps：缺什么？
status：是 approved 还是 review_required？
traceability：影响了哪些页面、指标、事件、测试？
```

如果没有 source_refs，却写 confirmed，要警惕。

如果写了“快速”“友好”“稳定”，但没有数值或验收，要要求补 gap。

如果 PRD.md 只有标题，要要求跑 projection_sync_harness。

---

## 10. 最短记忆版

```text
第一次导入旧 PRD：走初始迁移链路。
日常更新：写自然语言 change request。
多个变更：先拆，再分 patch。
PRD.md 不能是空壳，要由 YAML 投影完整内容。
C-EARS 不是死模板，要按需求类型选择 pattern。
AI 只提候选，不能自己批准。
高风险由人确认。
```
