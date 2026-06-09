# LLM Runtime 使用指南 v1.0

## 1. 角色边界

LLM 可以：

```text
分类自然语言变更；
提出影响候选；
起草 patch contract；
生成候选需求；
提出 open questions；
生成可读 PRD 文案候选。
```

LLM 不得：

```text
写 confirmed fact；
批准需求；
关闭 open question；
决定最终 impact_analysis；
直接写 validated_passed；
删除 item。
```

## 2. 推荐流程

```text
backend receives change_request.md
→ build input package
→ LLM structured output
→ deterministic validator
→ human review if high risk
→ write artifacts
```

## 3. 结构化输出建议

LLM 输出应符合：

```text
change_patch_candidate.schema.json
impact_candidate.schema.json
requirement_candidate.schema.json
```

## 4. API Key 安全

- API key 只放后端环境变量。
- 不写进前端。
- 不提交到 Git。
