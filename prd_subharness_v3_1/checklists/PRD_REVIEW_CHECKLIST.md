# PRD Review Checklist

Status: approved_by_human_review

## PRD 完整性

- [ ] 是否说明为什么现在做？
- [ ] 是否有目标用户？
- [ ] 是否有 in scope / out of scope / non-goals？
- [ ] 是否有成功标准？
- [ ] 指标不可测时是否有 unknown 规则？
- [ ] `PRD.md` 是否是可读投影，而不是只有标题或模板占位？

## 需求质量

- [ ] P0/P1 是否有 stable ID？
- [ ] 是否选择了 requirement pattern？
- [ ] 是否有 source_refs 或 review decision？
- [ ] 是否有验收和验证方法？
- [ ] 是否避免“快速/稳定/友好/优化/支持”等模糊词直接作为验收？
- [ ] C-EARS 后是否已经落成 requirement record？
- [ ] 是否完成 quantification_review 或写明不能量化原因？

## AI-ready

- [ ] YAML 可结构校验。
- [ ] unknowns 有 owner 和 required_before。
- [ ] non-goals 没被实现。
- [ ] downstream docs 保留 source_refs。
- [ ] candidate/promote 是否有人工 review decision。
