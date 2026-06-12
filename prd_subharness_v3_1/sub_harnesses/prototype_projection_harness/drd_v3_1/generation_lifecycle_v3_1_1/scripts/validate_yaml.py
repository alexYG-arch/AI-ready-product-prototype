#!/usr/bin/env python3
from pathlib import Path
import sys
try:
    import yaml
except Exception as e:
    print(f"PyYAML unavailable: {e}")
    sys.exit(1)

root = Path(__file__).resolve().parents[1]
required = [
    'README.md',
    'package_manifest.yaml',
    'codex/CODEX_GENERATION_LIFECYCLE_UPGRADE_PROMPT.md',
    'rules/00_stage_generation_controller.yaml',
    'rules/01_build_crew_generator_rules.yaml',
    'rules/02_stage_generate_contract.yaml',
    'rules/03_generation_worker_contracts.yaml',
    'rules/04_generation_trace_rules.yaml',
    'rules/05_generate_validate_repair_lifecycle.yaml',
    'rules/06_missing_artifact_bootstrap_rules.yaml',
    'rules/07_regeneration_policy.yaml',
    'rules/08_validator_behavior_update.yaml',
    'rules/09_complete_generation_lifecycle_rules.yaml',
    'rules/10_repair_crew_integration_rules.yaml',
    'rules/11_stage_generator_matrix.yaml',
    'rules/12_generation_safety_rules.yaml',
]
missing = [p for p in required if not (root / p).exists()]
if missing:
    print('MISSING REQUIRED FILES:')
    for p in missing:
        print(' -', p)
    sys.exit(2)

errors = []
for path in sorted(root.rglob('*.yaml')):
    try:
        with path.open('r', encoding='utf-8') as f:
            yaml.safe_load(f)
    except Exception as e:
        errors.append((path, e))

if errors:
    print('YAML VALIDATION ERRORS:')
    for path, err in errors:
        print(f' - {path.relative_to(root)}: {err}')
    sys.exit(3)
print('VALIDATION PASS')
