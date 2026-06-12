#!/usr/bin/env python3
from pathlib import Path
import sys
try:
    import yaml
except Exception as e:
    print("PyYAML is required for validation", file=sys.stderr)
    raise

root = Path(__file__).resolve().parents[1]
errors = []
for p in list(root.glob('rules/*.yaml')) + list(root.glob('libs/*.yaml')) + list(root.glob('examples/*.yaml')) + list(root.glob('schemas/*.yaml')) + [root/'package_manifest.yaml']:
    try:
        yaml.safe_load(p.read_text(encoding='utf-8'))
    except Exception as e:
        errors.append(f"{p.relative_to(root)}: {e}")

required = [
    'rules/12_complete_deductive_rules.yaml',
    'rules/01_screen_role_obligation_rules.yaml',
    'rules/11_validators.yaml',
    'codex/CODEX_UPGRADE_PROMPT.md',
]
for rel in required:
    if not (root/rel).exists():
        errors.append(f"missing required file: {rel}")

if errors:
    print('VALIDATION FAILED')
    for e in errors:
        print('-', e)
    sys.exit(1)
print('VALIDATION PASS')
