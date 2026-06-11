# PRD: [产品 / 功能名]

> Status: Draft / Review / Approved / Changed / Deprecated
> Owner:
> Contributors:
> Target Release:
> Last Updated:
> Related Docs: requirements.yaml / screens.yaml / metrics.yaml / events.yaml / traceability.md / Figma / Tech Design / Test Plan / Analytics Spec

---

## 1. TL;DR

### 1.1 一句话说明
Gap：当前基线尚未迁移真实产品问题陈述；首次 PRD 迁移时必须从旧 PRD、变更请求或人工 review decision 中补齐 source-backed 一句话说明。

### 1.2 为什么现在做
- 用户侧原因：
- 业务侧原因：
- 技术/平台侧原因：
- 风险窗口或机会窗口：

### 1.3 目标用户
- Primary users:
- Secondary users:
- Excluded users:

### 1.4 成功标准
- Primary metric:
- Guardrail metrics:
- Qualitative validation:
- Failure criteria:

### 1.5 本次范围
- In scope:
- Out of scope:
- Non-goals:

### 1.6 最大风险
- Product risk:
- Engineering risk:
- Data risk:
- Compliance risk:

---

## 2. 背景与问题

### 2.1 当前链路
[描述用户当前怎么完成任务。]

### 2.2 用户问题
| 问题 ID | 用户 | 场景 | 问题 | 证据 | 严重度 |
|---|---|---|---|---|---|
| P-001 |  |  |  |  |  |

### 2.3 业务问题
| 问题 ID | 指标/现象 | 影响 | 证据 | 备注 |
|---|---|---|---|---|
| B-001 |  |  |  |  |

### 2.4 约束
- 平台约束：iOS / Android / Web / 小程序 / 多端一致性
- 法务合规约束：
- 隐私与权限约束：
- 性能与稳定性约束：
- 资源约束：排期、人力、依赖团队

---

## 3. 用户与场景

### 3.1 Persona
| Persona | 目标 | 痛点 | 典型设备/环境 | 备注 |
|---|---|---|---|---|
|  |  |  |  |  |

### 3.2 核心用户旅程
```text
入口 → 页面/动作 → 系统响应 → 成功状态 → 后续路径
```

### 3.3 主路径
1.
2.
3.

### 3.4 异常路径
| 异常场景 | 用户感知 | 系统行为 | 恢复方式 | 是否阻断 |
|---|---|---|---|---|
| 弱网 |  |  |  |  |
| 权限拒绝 |  |  |  |  |
| 服务失败 |  |  |  |  |
| 重复提交 |  |  |  |  |

---

## 4. 目标与指标

### 4.1 产品目标
| Goal ID | 目标 | 类型 | 状态 | 负责人 |
|---|---|---|---|---|
| G-001 |  | acquisition / activation / retention / revenue / quality / trust | measurable_now / needs_instrumentation / proxy_only / blocked |  |

### 4.2 指标定义
| Metric ID | 指标名 | 口径 | Baseline | Target | 状态 | 数据来源 | 观测周期 |
|---|---|---|---|---|---|---|---|
| M-001 |  |  | unknown | TBD_AFTER_BASELINE | needs_instrumentation |  |  |

### 4.3 Guardrail 指标
| Metric ID | 指标 | 不可突破阈值 | 原因 |
|---|---|---|---|
| GM-001 | Crash-free sessions | ≥ 99.8% | 防止增长目标损害稳定性 |

### 4.4 指标预留说明
如当前不可测，必须填写：

```yaml
metric_state: needs_instrumentation
reason: "当前缺少 xxx 埋点"
required_instrumentation:
  - DATA-001
  - DATA-002
required_before: beta_release
forbidden_inference: "baseline 未确认前，不得推导 target 或实验成功阈值"
```

---

## 5. Scope / Non-goals

### 5.1 In scope
| Scope ID | 内容 | 对应目标 | 优先级 |
|---|---|---|---|
| S-001 |  | G-001 | P0 |

### 5.2 Out of scope
| Item | 原因 | 后续可能版本 |
|---|---|---|
|  |  |  |

### 5.3 Non-goals
| Non-goal ID | 明确不追求的目标 | 原因 |
|---|---|---|
| NG-001 |  |  |

### 5.4 Release slicing
| 版本 | 范围 | 不包含 | 发布条件 |
|---|---|---|---|
| V1 |  |  |  |
| V1.1 |  |  |  |

---

## 6. 体验方案摘要

### 6.1 设计原则
-

### 6.2 信息架构
```text
[页面/模块层级]
```

### 6.3 页面流
```text
Screen A → Screen B → Screen C
```

### 6.4 设计稿
- Figma:
- Prototype:
- Design system components:

---

## 7. 页面语义说明

> PRD 不复刻 Figma，不写像素；PRD 写页面目的、状态、规则、异常、数据、权限、埋点和验收。

### Screen: [SCREEN_ID]

| 字段 | 内容 |
|---|---|
| 页面名称 |  |
| 页面目的 |  |
| 设计稿 |  |
| 入口 |  |
| 出口 |  |
| 相关需求 |  |
| 相关埋点 |  |

#### 7.x.1 展示规则
-

#### 7.x.2 状态表
| 状态 ID | 状态名 | 触发条件 | 页面表现 | 用户可操作 | 系统行为 | 验收 |
|---|---|---|---|---|---|---|
| ST-001 | 初始 |  |  |  |  |  |
| ST-002 | Loading |  |  |  |  |  |
| ST-003 | Error |  |  |  |  |  |
| ST-004 | Empty |  |  |  |  |  |
| ST-005 | Success |  |  |  |  |  |

#### 7.x.3 关键规则
- 当 [...] 时，[客户端/服务端/系统] 应当 [...]。
- 如果 [...]，则 [客户端/服务端/系统] 应当 [...]。

#### 7.x.4 文案
| 文案 ID | 场景 | 中文文案 | 备注 |
|---|---|---|---|
| COPY-001 |  |  |  |

#### 7.x.5 可访问性
- 输入控件应当有可读 label。
- 错误提示应当可被屏幕阅读器识别。
- 不应仅依赖颜色表达状态。
- 焦点顺序应当符合页面阅读顺序。

---

## 8. 功能需求

> 使用 C-EARS / requirement pattern 写法。每条需求只表达一个行为。

| Req ID | Pattern | Parent Goal | 类型 | C-EARS 需求语句 | Priority | Rationale | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| REQ-001 | event_driven | G-001 | functional | 当 [...] 时，[系统] 应当 [...]。 | P0 |  |  | draft |

---

## 9. 非功能需求

### 9.1 性能
| Req ID | 需求 | 指标 | 验证方式 |
|---|---|---|---|
| NFR-PERF-001 |  | p95 ≤ x ms | 性能测试 / 线上监控 |

### 9.2 稳定性
| Req ID | 需求 | 指标 | 验证方式 |
|---|---|---|---|
| NFR-STAB-001 |  | crash-free sessions ≥ x% | 线上监控 |

### 9.3 兼容性
- iOS:
- Android:
- 平板 / 折叠屏 / 多窗口:
- 低端机:
- 弱网:

### 9.4 隐私、权限与安全
| Req ID | 需求 | 数据/权限 | 最小化原则 | 降级策略 |
|---|---|---|---|---|
| NFR-PRIV-001 |  |  |  |  |

### 9.5 可访问性
| Req ID | 需求 | 验证方式 |
|---|---|---|
| NFR-A11Y-001 |  | 手动检查 / 自动化扫描 / 用户测试 |

---

## 10. 数据与实验

### 10.1 埋点表
| Event ID | Event Name | 触发时机 | 属性 | 对应需求 | 验证方式 |
|---|---|---|---|---|---|
| EVT-001 |  |  |  | REQ-001 |  |

### 10.2 漏斗
```text
Step 1 → Step 2 → Step 3 → Success
```

### 10.3 实验方案
| Experiment ID | 假设 | 分组 | 指标 | 成功标准 | Guardrail |
|---|---|---|---|---|---|
| EXP-001 |  |  |  |  |  |

---

## 11. 验收标准

| Req ID | Given | When | Then | Verification Method | Test Owner | Blocking |
|---|---|---|---|---|---|---|
| REQ-001 |  |  |  | e2e_test / api_test / manual / monitoring |  | true |

---

## 12. 发布计划

### 12.1 灰度策略
| 阶段 | 人群 | 比例 | 放量条件 | 回滚条件 |
|---|---|---|---|---|
| Alpha | 内部 |  |  |  |
| Beta | 小流量 |  |  |  |
| GA | 全量 |  |  |  |

### 12.2 监控
- 功能成功率：
- 错误率：
- 延迟：
- Crash / ANR：
- 客诉：

### 12.3 回滚条件
-

### 12.4 运营与客服准备
- FAQ:
- 客服话术:
- 用户公告:

---

## 13. 风险、依赖、开放问题

| ID | 类型 | 描述 | 影响 | Owner | Due Date | 状态 |
|---|---|---|---|---|---|---|
| RISK-001 | product / engineering / data / legal |  |  |  |  | open |
| DEP-001 | dependency |  |  |  |  | open |
| U-001 | unknown |  |  |  |  | open |

---

## 14. 变更记录

| 日期 | 版本 | 变更 | 原因 | 决策人 | 影响范围 |
|---|---|---|---|---|---|
|  |  |  |  |  |  |
