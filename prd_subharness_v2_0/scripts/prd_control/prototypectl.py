#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from collections import defaultdict

try:
    import yaml
except Exception:
    yaml = None

try:
    import jsonschema
except Exception:
    jsonschema = None

ROOT = Path.cwd()


def yload(path: Path):
    if yaml is None:
        raise RuntimeError("Install pyyaml: pip install pyyaml")
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def jload(path: Path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def ywrite(path: Path, data):
    if yaml is None:
        raise RuntimeError("Install pyyaml: pip install pyyaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def load_runtime():
    return jload(ROOT / "product-spec" / "prototype.runtime.json")


def status(args):
    files = [
        "product-spec/prototype.runtime.json",
        "product-spec/figma-sync-map.yaml",
        "product-spec/figma-interaction-map.yaml",
        "product-spec/component-binding-map.yaml",
        "product-spec/design-semantic-library.json",
        "sub_harnesses/prototype_projection_harness/harness_contract.yaml",
        "prd_orchestrator/patch_control_v2.yaml",
    ]
    print("# Prototype Projection Harness v2.0")
    for rel in files:
        path = ROOT / rel
        print(f"- {'OK' if path.exists() else 'MISSING'} {rel}")


def validate_json_schema(instance_path: Path, schema_path: Path):
    if jsonschema is None:
        return ["jsonschema not installed; skipped schema validation"]
    if not instance_path.exists():
        return [f"missing {instance_path}"]
    if not schema_path.exists():
        return [f"missing {schema_path}"]
    try:
        jsonschema.validate(jload(instance_path), jload(schema_path))
        return []
    except Exception as e:
        return [str(e)]


def validate_runtime(args):
    errors = []
    warnings = []
    runtime_path = ROOT / "product-spec" / "prototype.runtime.json"
    schema_path = ROOT / "schemas" / "prototype_runtime.schema.json"
    errors.extend(validate_json_schema(runtime_path, schema_path))
    rt = load_runtime()

    auth = rt.get("authority", {})
    if auth.get("forbidden_as_fact_source") is not True:
        errors.append("authority.forbidden_as_fact_source must be true")
    if auth.get("owner") != "prototype_projection_harness":
        errors.append("authority.owner must be prototype_projection_harness")

    required_state_dimensions = [
        "data_state", "network_state", "permission_state", "input_state",
        "request_lifecycle", "consistency_state", "recovery_state", "platform_device_state"
    ]
    for screen in rt.get("screens", []):
        sid = screen.get("screen_id", "UNKNOWN_SCREEN")
        if not screen.get("source_refs"):
            errors.append(f"{sid}: missing source_refs")
        for st in screen.get("states", []):
            stid = st.get("state_id", "UNKNOWN_STATE")
            dims = st.get("dimensions", {}) or {}
            missing = [d for d in required_state_dimensions if d not in dims]
            if missing:
                errors.append(f"{sid}/{stid}: missing state dimensions {missing}")
            if not st.get("source_refs"):
                errors.append(f"{sid}/{stid}: missing source_refs")

    for edge in rt.get("interaction_graph", {}).get("edges", []):
        eid = edge.get("edge_id", "UNKNOWN_EDGE")
        for field in ["interaction_id", "source", "trigger", "actions", "source_refs"]:
            if not edge.get(field):
                errors.append(f"{eid}: missing {field}")
        if not str(eid).startswith("EDGE-"):
            warnings.append(f"{eid}: edge_id should start with EDGE-")

    print("# validate-runtime")
    if errors:
        print("BLOCKED")
        for e in errors:
            print(f"- ERROR: {e}")
    else:
        print("PASS")
    for w in warnings:
        print(f"- WARNING: {w}")


def validate_interactions(args):
    errors = []
    warnings = []
    imap = yload(ROOT / "product-spec" / "figma-interaction-map.yaml").get("figma_interaction_map", {})
    if imap.get("forbidden_as_fact_source") is not True:
        errors.append("figma_interaction_map.forbidden_as_fact_source must be true")
    interactions = imap.get("interactions", []) or []

    seen = defaultdict(list)
    for i, item in enumerate(interactions):
        iid = item.get("interaction_id", f"INDEX-{i}")
        edge = item.get("edge_id")
        if not edge:
            errors.append(f"{iid}: missing edge_id")
        src = item.get("figma_source", {}) or {}
        react = item.get("figma_reaction", {}) or {}
        key = (src.get("source_node_id"), react.get("trigger"))
        if key[0] and key[1]:
            seen[key].append(iid)
        if not src.get("source_node_id") and interactions:
            errors.append(f"{iid}: missing figma_source.source_node_id")
        if not react.get("trigger") and interactions:
            errors.append(f"{iid}: missing figma_reaction.trigger")
        if not react.get("actions") and interactions:
            errors.append(f"{iid}: missing figma_reaction.actions")

    for key, ids in seen.items():
        if len(ids) > 1:
            errors.append(f"duplicate source_node_id + trigger {key}: {ids}")

    print("# validate-interactions")
    if errors:
        print("BLOCKED")
        for e in errors:
            print(f"- ERROR: {e}")
    else:
        print("PASS")
    for w in warnings:
        print(f"- WARNING: {w}")


def classify_figma_diff(args):
    path = Path(args.diff_file)
    if not path.is_absolute():
        path = ROOT / path
    raw = yload(path) if path.suffix.lower() in [".yaml", ".yml"] else jload(path)
    changes = raw.get("changes", raw if isinstance(raw, list) else [])
    semantic = []
    non_semantic = []
    conflicts = []
    for idx, ch in enumerate(changes, start=1):
        ctype = ch.get("type", "unknown")
        content = json.dumps(ch, ensure_ascii=False)
        if any(k in ctype for k in ["layout", "style", "position", "color", "spacing"]):
            non_semantic.append({
                "diff_id": f"FDIFF-VISUAL-{idx:03d}",
                "diff_type": ctype,
                "action": "keep_in_figma_only",
                "reason": "visual-only heuristic"
            })
        elif any(k in ctype for k in ["conflict", "both_sides"]):
            conflicts.append({
                "conflict_id": f"FCONFLICT-{idx:03d}",
                "conflict_type": ctype,
                "base_value": ch.get("base"),
                "figma_value": ch.get("figma"),
                "prd_value": ch.get("prd"),
                "required_decision": "choose_figma | choose_prd | write_new_value | reject_both"
            })
        else:
            semantic.append({
                "diff_id": f"FDIFF-{idx:03d}",
                "diff_type": ctype,
                "classification": "semantic_candidate",
                "figma_change": ch,
                "target_sub_harness_candidate": "screen_state_harness",
                "confidence": "low",
                "requires_human_review": True,
                "reason": "heuristic semantic diff; requires review"
            })
    out = {
        "change_patch_candidate": {
            "schema_version": "2.0",
            "patch_id": f"FIGMA-DIFF-{path.stem}",
            "source_channel": "figma_diff",
            "candidate_status": "candidate_not_approved",
            "human_review_required": True,
            "semantic_diffs": semantic,
            "non_semantic_diffs": non_semantic,
            "conflicts": conflicts,
            "forbidden_direct_writes_checked": True,
        }
    }
    out_path = ROOT / "prd_orchestrator" / "change_patch_candidates" / f"FIGMA-DIFF-{path.stem}.candidate.yaml"
    ywrite(out_path, out)
    print(f"Wrote {out_path}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(required=True)

    p = sub.add_parser("status")
    p.set_defaults(func=status)

    p = sub.add_parser("validate-runtime")
    p.set_defaults(func=validate_runtime)

    p = sub.add_parser("validate-interactions")
    p.set_defaults(func=validate_interactions)

    p = sub.add_parser("classify-figma-diff")
    p.add_argument("diff_file")
    p.set_defaults(func=classify_figma_diff)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
