# Codex Prompt: Apply Prototype Harness Generation Lifecycle Upgrade v3.1.1

You are updating the prototype_projection_harness rules and execution structure.

## Goal

Add a first-pass generation lifecycle so stages do not block only because required artifacts are missing.

## Required Upgrade

Install these concepts:

1. Stage Generation Controller（阶段生成控制器）
2. Build Crew Generator（建设队生成器）
3. Stage Generate Contract（阶段生成契约）
4. Generation Worker Contracts（生成工种契约）
5. Generation Trace（生成追踪）
6. Generate → Self-check → Validate → Repair lifecycle
7. Missing Artifact Bootstrap（缺失产物自举）
8. Regeneration Policy（重生成策略）
9. Validator missing-artifact behavior update（校验器缺失产物行为更新）
10. Build Crew ↔ Repair Crew integration（建设队与施工队集成）

## Critical Rule

Do not let validators act as generators.
Do not let repair crew perform first-pass build.
Do not write PRD facts from prototype generation.

## Execution Order

1. Read rules/09_complete_generation_lifecycle_rules.yaml
2. Install rules/00_stage_generation_controller.yaml
3. Install rules/01_build_crew_generator_rules.yaml
4. Add generate_contract to all non-validate-only stages.
5. Update validator behavior:
   - artifact missing -> needs_generation
   - artifact generated but invalid -> repair_crew
   - generator missing -> blocker
6. Add generation_trace to generated artifacts.
7. Wire Build Crew before Loop Controller / Repair Crew.
8. Add examples and CLI validation.

## Expected Lifecycle

```text
prepare
→ generate
→ self_check
→ validate
→ repair_if_needed
→ revalidate
→ report
```

## Forbidden

- Do not modify PRD.md.
- Do not modify requirements.yaml.
- Do not modify screens.yaml.
- Do not modify metrics.yaml.
- Do not modify events.yaml.
- Do not treat skill suggestions as product facts.
- Do not return empty placeholder YAML as successful generation.
