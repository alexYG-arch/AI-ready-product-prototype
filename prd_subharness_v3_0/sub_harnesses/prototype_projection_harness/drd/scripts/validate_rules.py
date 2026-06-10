#!/usr/bin/env python3
"""Validate YAML files in the Codex package.
验证 Codex 规则包中的 YAML 文件。"""
import pathlib, sys, re
try:
    import yaml
except Exception as e:
    print("FAIL: PyYAML is required", e)
    sys.exit(1)

ROOT = pathlib.Path(__file__).resolve().parents[1]
errors = []
for path in sorted(ROOT.rglob('*.yaml')):
    try:
        text = path.read_text(encoding='utf-8')
        yaml.safe_load(text)
    except Exception as e:
        errors.append(f"YAML parse error: {path.relative_to(ROOT)}: {e}")

# Simple JSONC warning only; do not parse as strict JSON.
for path in sorted(ROOT.rglob('*.json')):
    text = path.read_text(encoding='utf-8')
    if re.search(r'(^|\s)//|/\*', text):
        errors.append(f"Strict JSON contains comments: {path.relative_to(ROOT)}")

required = [
    'rules/prototype_harness_drd_complete_rules.yaml',
    'rules/18_validators.yaml',
    'libs/component_primitive_library.yaml',
    'examples/run_manifest.sample.yaml',
]
for rel in required:
    if not (ROOT / rel).exists():
        errors.append(f"Missing required file: {rel}")

if errors:
    print("FAIL")
    for e in errors:
        print("-", e)
    sys.exit(1)
print("PASS: all YAML files parse and required files exist")
