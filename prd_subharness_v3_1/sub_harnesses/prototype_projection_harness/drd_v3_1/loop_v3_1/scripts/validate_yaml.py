#!/usr/bin/env python3
from pathlib import Path
import sys
try:
    import yaml
except Exception as exc:
    print(f'YAML import failed: {exc}', file=sys.stderr)
    sys.exit(1)

root = Path(__file__).resolve().parents[1]
errors = []
for path in sorted(root.rglob('*.yaml')):
    try:
        with path.open('r', encoding='utf-8') as f:
            yaml.safe_load(f)
    except Exception as exc:
        errors.append(f'{path.relative_to(root)}: {exc}')

required = [
    'rules/15_complete_loop_rules.yaml',
    'rules/08_stage_loop_contracts.yaml',
    'rules/12_harness_macro_loop_rules.yaml',
    'docs/LOOP_ENGINEERING_DESIGN_GUIDE_v3_1.md',
    'codex/CODEX_LOOP_UPGRADE_PROMPT.md',
]
for rel in required:
    if not (root / rel).exists():
        errors.append(f'MISSING: {rel}')

if errors:
    print('VALIDATION FAILED')
    for e in errors:
        print(e)
    sys.exit(1)
print('VALIDATION PASS')
