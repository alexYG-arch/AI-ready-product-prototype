#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except Exception:
    yaml = None

DEFAULT_HARNESS_ROOT = Path(__file__).resolve().parents[2]
HARNESS_ROOT = DEFAULT_HARNESS_ROOT
INSTANCE_ROOT = DEFAULT_HARNESS_ROOT
RUN_ROOT = DEFAULT_HARNESS_ROOT / "runs" / "manual"
RUN_ID = "manual"
INSTANCE_ROOT_PROVIDED = False
ALLOW_HARNESS_WRITES = False

WRITE_COMMANDS = {
    "extract-source-baseline",
    "route-change",
    "classify-change",
    "impact",
    "rerun-plan",
    "quality-gate",
    "unified-review",
    "core-review-md",
    "review-decision",
    "promote-approved",
    "run-prd-loop",
    "write-patch-report",
    "stop-the-line",
    "write-loop-gate",
}

SUB_HARNESS_ORDER = [
    "prd_core_harness",
    "requirement_harness",
    "screen_state_harness",
    "metrics_events_harness",
    "release_ops_harness",
    "traceability_harness",
    "projection_sync_harness",
]

SOURCE_BASELINE_REL = Path("prd_orchestrator/source_extraction/structured_source_baseline.yaml")
SOURCE_EXTRACTION_REVIEW_REL = Path("human_review/STRUCTURED_SOURCE_EXTRACTION_REVIEW.md")
CORE_FACT_CANDIDATES_REL = Path("sub_harnesses/prd_core_harness/candidates/CORE-000_CORE_FACT_CANDIDATES.yaml")
CORE_REVIEW_MD_REL = Path("sub_harnesses/prd_core_harness/reports/CORE-000_REVIEW.md")

def resolve_cli_path(path_text: str | None, default: Path | None = None) -> Path:
    if not path_text:
        if default is None:
            raise ValueError("path_text or default required")
        return default.resolve()
    path = Path(path_text)
    if path.is_absolute():
        return path.resolve()
    return (Path.cwd() / path).resolve()

def configure_paths(args):
    global HARNESS_ROOT, INSTANCE_ROOT, RUN_ROOT, RUN_ID, INSTANCE_ROOT_PROVIDED, ALLOW_HARNESS_WRITES
    HARNESS_ROOT = resolve_cli_path(getattr(args, "harness_root", None), DEFAULT_HARNESS_ROOT)
    INSTANCE_ROOT_PROVIDED = bool(getattr(args, "instance_root", None))
    INSTANCE_ROOT = resolve_cli_path(getattr(args, "instance_root", None), HARNESS_ROOT)
    RUN_ID = getattr(args, "run_id", None) or "manual"
    RUN_ROOT = (INSTANCE_ROOT / "runs" / RUN_ID).resolve()
    ALLOW_HARNESS_WRITES = bool(getattr(args, "allow_harness_writes", False))

def path_is_within(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False

def ensure_instance_write_allowed(command_name: str):
    if command_name not in WRITE_COMMANDS:
        return
    if INSTANCE_ROOT_PROVIDED and not path_is_within(INSTANCE_ROOT, HARNESS_ROOT):
        return
    if ALLOW_HARNESS_WRITES:
        return
    raise SystemExit(
        "BLOCKED: write commands require --instance-root to avoid polluting the harness package. "
        "Use init-instance first, then rerun with --instance-root <path> --run-id <id>. "
        "--instance-root must be outside the harness package."
    )

def instance_path(*parts: str) -> Path:
    return INSTANCE_ROOT.joinpath(*parts)

def harness_path(*parts: str) -> Path:
    return HARNESS_ROOT.joinpath(*parts)

def run_path(*parts: str) -> Path:
    return RUN_ROOT.joinpath(*parts)

def ensure_run_manifest(command_name: str):
    ensure_instance_write_allowed(command_name)
    manifest = run_path("run_manifest.yaml")
    if manifest.exists():
        return
    data = {
        "run_manifest": {
            "run_id": RUN_ID,
            "run_status": "candidate_requires_review",
            "harness_root": str(HARNESS_ROOT),
            "instance_root": str(INSTANCE_ROOT),
            "run_root": str(RUN_ROOT),
            "human_review_required": True,
            "review_decision_path": "prd_orchestrator/review_decisions/",
            "each_sub_harness_run_requires_review": True,
            "sub_harness_review_contract": "harness_contract.run_lifecycle.human_review_stage",
            "write_policy": {
                "harness_package_is_read_only": True,
                "candidate_outputs_go_to_run_root": True,
                "approved_outputs_require_review_decision": True,
            },
        }
    }
    ywrite(manifest, data)

def human_review_gate(stage_name: str, artifact_type: str):
    return {
        "required": True,
        "stage": stage_name,
        "artifact_type": artifact_type,
        "candidate_status_before_review": "candidate_not_approved",
        "decision_required_before": [
            "candidate_to_confirmed",
            "write_instance_product_spec",
            "close_open_question",
        ],
        "decision_path": "prd_orchestrator/review_decisions/",
    }

def utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def utc_slug_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def safe_slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-")
    return (slug or "artifact")[:80]

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def resolve_run_artifact(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        artifact = path.resolve()
    else:
        run_candidate = (RUN_ROOT / path).resolve()
        instance_candidate = (INSTANCE_ROOT / path).resolve()
        artifact = run_candidate if run_candidate.exists() else instance_candidate
    if not artifact.exists():
        raise SystemExit(f"BLOCKED: artifact not found: {path_text}")
    if not path_is_within(artifact, RUN_ROOT):
        raise SystemExit("BLOCKED: review/promote artifacts must be under <instance-root>/runs/<run-id>/")
    return artifact

def artifact_relpath(path: Path) -> str:
    return path.relative_to(RUN_ROOT).as_posix()

def infer_artifact_type(path: Path) -> str:
    data = yload(path) if path.suffix.lower() in [".yaml", ".yml"] else {}
    keys = list(data.keys()) if isinstance(data, dict) else []
    if len(keys) == 1:
        return str(keys[0])
    return safe_slug(path.stem)

def infer_sub_harness(path: Path, data: dict | None = None) -> str:
    parts = path.parts
    if "sub_harnesses" in parts:
        idx = parts.index("sub_harnesses")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    data = data or (yload(path) if path.suffix.lower() in [".yaml", ".yml"] else {})
    if isinstance(data, dict):
        candidate = data.get("sub_harness") or data.get("target_sub_harness_candidate")
        if candidate:
            return str(candidate)
    return "orchestrator"

def review_decision_dir() -> Path:
    return instance_path("prd_orchestrator", "review_decisions", RUN_ID)

def decision_path_by_id(decision_id: str) -> Path:
    safe_id = safe_slug(decision_id)
    if safe_id.endswith(".yaml"):
        safe_id = safe_id[:-5]
    return review_decision_dir() / f"{safe_id}.yaml"

def load_review_decision(path: Path) -> dict:
    return yload(path).get("review_decision", {})

def find_approved_decision(artifact: Path):
    rel = artifact_relpath(artifact)
    digest = sha256_file(artifact)
    for path in sorted(review_decision_dir().glob("*.yaml")):
        decision = load_review_decision(path)
        if decision.get("decision") != "approved":
            continue
        if decision.get("artifact_relpath") != rel:
            continue
        if decision.get("artifact_sha256") != digest:
            continue
        return path, decision
    return None, None

def resolve_input_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    if INSTANCE_ROOT_PROVIDED:
        instance_candidate = INSTANCE_ROOT / path
        if instance_candidate.exists():
            return instance_candidate
        run_candidate = RUN_ROOT / path
        if run_candidate.exists():
            return run_candidate
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
    instance_candidate = INSTANCE_ROOT / path
    if instance_candidate.exists():
        return instance_candidate
    run_candidate = RUN_ROOT / path
    if run_candidate.exists():
        return run_candidate
    return HARNESS_ROOT / path

def text_file_has_content(path: Path) -> bool:
    try:
        return bool(path.read_text(encoding="utf-8").strip())
    except Exception:
        return False

def discover_prd_input_files() -> list[Path]:
    if not INSTANCE_ROOT_PROVIDED:
        return []
    inputs_root = INSTANCE_ROOT / "inputs"
    if not inputs_root.exists():
        return []
    candidates = []
    for suffix in ["*.md", "*.markdown", "*.txt"]:
        candidates.extend(inputs_root.rglob(suffix))
    return sorted(
        path
        for path in candidates
        if path.is_file()
        and "change_requests" not in path.relative_to(inputs_root).parts
        and text_file_has_content(path)
    )

def product_spec_material_counts() -> dict:
    req = yload(instance_path("product-spec", "requirements.yaml"))
    screens = yload(instance_path("product-spec", "screens.yaml"))
    metrics = yload(instance_path("product-spec", "metrics.yaml"))
    events = yload(instance_path("product-spec", "events.yaml"))
    return {
        "goals": len(req.get("goals") or []),
        "requirements": len(req.get("requirements") or []),
        "requirement_candidates": len(req.get("requirement_candidates") or []),
        "screens": len(screens.get("screens") or []),
        "state_reasoning_chains": len(screens.get("state_reasoning_chains") or []),
        "metrics": len(metrics.get("metrics") or []),
        "events": len(events.get("events") or []),
    }

def has_product_spec_material() -> bool:
    return any(product_spec_material_counts().values())

def current_source_baseline_path() -> Path:
    return run_path(*SOURCE_BASELINE_REL.parts)

def prd_run_state() -> dict:
    inputs = discover_prd_input_files()
    baseline_path = current_source_baseline_path()
    counts = product_spec_material_counts() if INSTANCE_ROOT.exists() else {}
    baseline = yload(baseline_path).get("structured_source_baseline", {}) if baseline_path.exists() else {}
    approved_path = None
    if baseline_path.exists() and path_is_within(baseline_path, RUN_ROOT):
        approved_path, _decision = find_approved_decision(baseline_path)
    return {
        "instance_root": str(INSTANCE_ROOT),
        "run_id": RUN_ID,
        "prd_inputs": [str(path.relative_to(INSTANCE_ROOT)) for path in inputs],
        "source_baseline": artifact_relpath(baseline_path) if baseline_path.exists() and path_is_within(baseline_path, RUN_ROOT) else "",
        "source_baseline_status": baseline.get("status", ""),
        "source_baseline_review_approved": bool(approved_path),
        "source_baseline_review_decision": str(approved_path.relative_to(INSTANCE_ROOT)) if approved_path else "",
        "product_spec_material_counts": counts,
        "has_product_spec_material": any(counts.values()) if counts else False,
    }

def prd_input_blocker(command_name: str) -> str | None:
    state = prd_run_state()
    if state["prd_inputs"] or state["source_baseline"] or state["has_product_spec_material"]:
        return None
    return (
        f"BLOCKED: {command_name} requires a real PRD input before running. "
        "Put a source PRD markdown file under <instance-root>/inputs/ and run "
        "`extract-source-baseline inputs/<file>.md`, or run `run-prd-loop --source inputs/<file>.md`. "
        "Empty product-spec templates are not PRD input."
    )

def ensure_prd_input_or_block(command_name: str):
    blocker = prd_input_blocker(command_name)
    if blocker:
        raise SystemExit(blocker)

def display_path(path: Path) -> str:
    for base_name, base in [
        ("run", RUN_ROOT),
        ("instance", INSTANCE_ROOT),
        ("harness", HARNESS_ROOT),
    ]:
        try:
            return f"{base_name}:{path.relative_to(base)}"
        except ValueError:
            pass
    return str(path)

def yload(path: Path):
    if yaml is None:
        raise RuntimeError("Install pyyaml: pip install pyyaml")
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

def ywrite(path: Path, data):
    if yaml is None:
        raise RuntimeError("Install pyyaml: pip install pyyaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

def jload(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def validate_with_schema(instance_path: Path, schema_name: str) -> list[str]:
    try:
        from jsonschema import Draft202012Validator
    except Exception as exc:
        raise RuntimeError("Install jsonschema: pip install jsonschema") from exc
    schema_path = harness_path("schemas", schema_name)
    if not instance_path.exists():
        return [f"missing artifact {display_path(instance_path)}"]
    if not schema_path.exists():
        return [f"missing schema {display_path(schema_path)}"]
    schema = jload(schema_path)
    Draft202012Validator.check_schema(schema)
    data = yload(instance_path) if instance_path.suffix.lower() in [".yaml", ".yml"] else jload(instance_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda item: list(item.path))
    result = []
    for error in errors:
        path = ".".join(str(part) for part in error.path) or "<root>"
        schema_path_text = ".".join(str(part) for part in error.schema_path)
        result.append(f"{path}: {error.message} (schema: {schema_path_text})")
    return result

def validate_with_schema_path(instance_path: Path, schema_path: Path) -> list[str]:
    try:
        from jsonschema import Draft202012Validator
    except Exception as exc:
        raise RuntimeError("Install jsonschema: pip install jsonschema") from exc
    if not instance_path.exists():
        return [f"missing artifact {display_path(instance_path)}"]
    if not schema_path.exists():
        return [f"missing schema {display_path(schema_path)}"]
    schema = jload(schema_path)
    Draft202012Validator.check_schema(schema)
    data = yload(instance_path) if instance_path.suffix.lower() in [".yaml", ".yml"] else jload(instance_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda item: list(item.path))
    result = []
    for error in errors:
        path = ".".join(str(part) for part in error.path) or "<root>"
        schema_path_text = ".".join(str(part) for part in error.schema_path)
        result.append(f"{path}: {error.message} (schema: {schema_path_text})")
    return result

def print_blocking_validation(title: str, errors: list[str]):
    print(f"# {title}")
    print("PASS" if not errors else "BLOCKED")
    for error in errors:
        print(f"- ERROR: {error}")
    if errors:
        raise SystemExit(1)

def run_output_path(path_text: str | None, default: Path, option_name: str) -> Path:
    rel = run_relative_arg(path_text, default, option_name)
    return run_path(*rel.parts)

def markdown_companion_path(yaml_path: Path) -> Path:
    if yaml_path.suffix.lower() in {".yaml", ".yml"}:
        return yaml_path.with_suffix(".md")
    return yaml_path.with_name(f"{yaml_path.name}.md")

def md_inline(value) -> str:
    if value is None:
        text = ""
    elif isinstance(value, list):
        text = ", ".join(str(item) for item in value)
    else:
        text = str(value)
    return text.replace("\n", " ").replace("|", "\\|")

def md_list(items: list[str] | None) -> list[str]:
    if not items:
        return ["- 无"]
    return [f"- `{md_inline(item)}`" for item in items]

def write_stop_report_markdown(yaml_path: Path, report: dict):
    stop = report.get("stop_the_line", {})
    md_path = markdown_companion_path(yaml_path)
    lines = [
        "# Stop The Line",
        "",
        "本文件是人工阅读入口；同名 YAML 是机器校验源。",
        "",
        "## 状态",
        "",
        "| 字段 | 值 |",
        "|---|---|",
        f"| stop_id | `{md_inline(stop.get('stop_id'))}` |",
        f"| run_id | `{md_inline(stop.get('run_id'))}` |",
        f"| stage | `{md_inline(stop.get('stage'))}` |",
        f"| sub_harness | `{md_inline(stop.get('sub_harness'))}` |",
        f"| severity | `{md_inline(stop.get('severity'))}` |",
        f"| status | `{md_inline(stop.get('status'))}` |",
        f"| created_at | `{md_inline(stop.get('created_at'))}` |",
        "",
        "## 阻断原因",
        "",
        md_inline(stop.get("reason")),
        "",
        "## 下一步",
        "",
        md_inline(stop.get("required_next_action")),
        "",
        "## 恢复条件",
        "",
        md_inline(stop.get("resume_condition")),
        "",
        "## 来源证据",
        "",
        *md_list(stop.get("source_artifacts")),
        "",
        "## Review",
        "",
        f"- resolved_by_review_decision: `{md_inline(stop.get('resolved_by_review_decision'))}`",
        f"- owner: `{md_inline(stop.get('owner'))}`",
        f"- notes: {md_inline(stop.get('notes'))}",
        "",
        "## 机器源",
        "",
        f"- YAML: `{yaml_path.relative_to(RUN_ROOT).as_posix() if path_is_within(yaml_path, RUN_ROOT) else yaml_path}`",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path

def write_patch_report_markdown(yaml_path: Path, report: dict):
    patch = report.get("patch_report", {})
    md_path = markdown_companion_path(yaml_path)
    review = patch.get("human_review") or {}
    lines = [
        "# Patch Report",
        "",
        "本文件是人工阅读入口；同名 YAML 是机器校验源。",
        "",
        "## 状态",
        "",
        "| 字段 | 值 |",
        "|---|---|",
        f"| patch_id | `{md_inline(patch.get('patch_id'))}` |",
        f"| run_id | `{md_inline(patch.get('run_id'))}` |",
        f"| sub_harness | `{md_inline(patch.get('sub_harness'))}` |",
        f"| status | `{md_inline(patch.get('status'))}` |",
        "",
        "## Summary",
        "",
        md_inline(patch.get("summary")),
        "",
        "## Root Cause",
        "",
        md_inline(patch.get("root_cause")),
        "",
        "## Changed Files",
        "",
        *md_list(patch.get("changed_files")),
        "",
        "## Validation",
        "",
        *[f"- {md_inline(item)}" for item in (patch.get("validation") or [])],
        "",
        "## Remaining Gaps",
        "",
        *md_list(patch.get("remaining_gaps")),
        "",
        "## Stop The Line Refs",
        "",
        *md_list(patch.get("stop_the_line_refs")),
        "",
        "## Source Artifacts",
        "",
        *md_list(patch.get("source_artifacts")),
        "",
        "## Review",
        "",
        f"- required: `{md_inline(review.get('required'))}`",
        f"- stage: `{md_inline(review.get('stage'))}`",
        f"- decision_required_before: `{md_inline(review.get('decision_required_before'))}`",
        f"- decision_path: `{md_inline(review.get('decision_path'))}`",
        "",
        "## 机器源",
        "",
        f"- YAML: `{yaml_path.relative_to(RUN_ROOT).as_posix() if path_is_within(yaml_path, RUN_ROOT) else yaml_path}`",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path

def write_stop_report(
    *,
    stage: str,
    reason: str,
    required_next_action: str,
    resume_condition: str,
    severity: str = "blocker",
    sub_harness: str = "orchestrator",
    owner: str = "",
    source_artifacts: list[str] | None = None,
    notes: str = "",
    stop_id: str | None = None,
    output: str | None = None,
) -> Path:
    safe_stage = safe_slug(stage)
    stop_id = stop_id or f"STL-{RUN_ID}-{safe_stage}-{utc_slug_text()}"
    out = run_output_path(
        output,
        Path("prd_orchestrator") / "stop_the_line" / f"{safe_slug(stop_id)}.stop_the_line.yaml",
        "--output",
    )
    data = {
        "stop_the_line": {
            "schema_version": "1.0",
            "stop_id": stop_id,
            "run_id": RUN_ID,
            "stage": stage,
            "sub_harness": sub_harness,
            "severity": severity,
            "reason": reason,
            "required_next_action": required_next_action,
            "resume_condition": resume_condition,
            "owner": owner,
            "source_artifacts": source_artifacts or [],
            "status": "open",
            "created_at": utc_now_text(),
            "resolved_by_review_decision": "",
            "notes": notes,
        }
    }
    ywrite(out, data)
    errors = validate_with_schema(out, "stop_the_line.schema.json")
    if errors:
        raise SystemExit("BLOCKED: generated stop_the_line report failed schema validation:\n- " + "\n- ".join(errors))
    write_stop_report_markdown(out, data)
    return out

def status(args):
    reg = yload(harness_path("prd_orchestrator", "harness_registry.yaml")).get("harness_registry", {})
    q = yload(harness_path("prd_orchestrator", "patch_queue.yaml")).get("patch_queue", {})
    print("# PRD Sub-Harness v2.1")
    print("\n## Sub-Harnesses")
    for h in reg.get("sub_harnesses", []):
        print(f"- {h['id']}: {', '.join(h.get('owns', []))}")
    print("\n## Initial Migration")
    for p in q.get("initial_migration", []):
        print(f"- {p}")

def route_change(args):
    ensure_run_manifest("route-change")
    path = resolve_input_path(args.markdown)
    text = path.read_text(encoding="utf-8")
    rules = yload(harness_path("prd_orchestrator", "routing_rules.yaml")).get("routing_rules", {}).get("keyword_routes", {})
    hits = {}
    for harness, kws in rules.items():
        score = sum(1 for kw in kws if kw.lower() in text.lower())
        if score:
            hits[harness] = score
    ranked = sorted(hits.items(), key=lambda x: x[1], reverse=True)
    out = {
        "route_result": {
            "change_request": display_path(path),
            "route_status": "candidate_not_approved",
            "candidate_routes": [{"sub_harness": h, "score": s} for h, s in ranked],
            "default_if_empty": "open_question",
            "human_review": human_review_gate("route-change", "route_result"),
        }
    }
    out_path = run_path("prd_orchestrator", "impact_candidates", f"{path.stem}.route.yaml")
    ywrite(out_path, out)
    print(f"Wrote {out_path}")
    print(json.dumps(out["route_result"], ensure_ascii=False, indent=2))

def classify_change(args):
    ensure_run_manifest("classify-change")
    path = resolve_input_path(args.markdown)
    text = path.read_text(encoding="utf-8")
    items = []
    for i, unit in enumerate(markdown_review_units(text), start=1):
        typ, harness, doc, confidence, reason = classify_review_unit(unit)
        items.append({
            "change_id": f"{path.stem}-CHG-{i:03d}",
            "type": typ,
            "target_document_candidate": doc,
            "target_sub_harness_candidate": harness,
            "confidence": confidence,
            "content": unit["content"],
            "source_context": unit.get("context", ""),
            "source_kind": unit.get("kind", ""),
            "reason": reason,
        })
    data = {
        "change_patch_candidate": {
            "change_request_id": path.stem,
            "candidate_status": "candidate_not_approved",
            "extracted_changes": items,
            "split_recommendation": [],
            "open_questions": [{"question": it["content"]} for it in items if it["type"] == "unknown"],
            "human_review": human_review_gate("classify-change", "change_patch_candidate"),
        }
    }
    out = run_path("prd_orchestrator", "change_patch_candidates", f"{path.stem}.candidate.yaml")
    ywrite(out, data)
    print(f"Wrote {out}")

def impact(args):
    ensure_run_manifest("impact")
    candidates = list(run_path("prd_orchestrator", "change_patch_candidates").glob("*.candidate.yaml"))
    routes = {}
    docs = set()
    for p in candidates:
        data = yload(p).get("change_patch_candidate", {})
        for ch in data.get("extracted_changes", []):
            h = ch.get("target_sub_harness_candidate") or "unknown"
            routes[h] = routes.get(h, 0) + 1
            if ch.get("target_document_candidate"):
                docs.add(ch["target_document_candidate"])
    impact_rules = yload(harness_path("prd_orchestrator", "impact_rules.yaml")).get("impact_rules", {}).get("route_to_rerun", {})
    rerun = set()
    for h in routes:
        rerun.add(h)
        for d in impact_rules.get(h, {}).get("downstream", []):
            rerun.add(d)
    out = {
        "impact_analysis": {
            "patch_id": args.patch_id,
            "approved": False,
            "analysis_status": "candidate_requires_review",
            "affected_sub_harnesses": sorted(rerun),
            "affected_documents": sorted(docs),
            "human_review_required": True,
            "human_review": human_review_gate("impact", "impact_analysis"),
        }
    }
    out_path = run_path("prd_orchestrator", "impact_analysis", f"{args.patch_id}.yaml")
    ywrite(out_path, out)
    print(f"Wrote {out_path}")

def rerun_plan(args):
    ensure_run_manifest("rerun-plan")
    impact_path = run_path("prd_orchestrator", "impact_analysis", f"{args.patch_id}.yaml")
    impact = yload(impact_path).get("impact_analysis", {})
    rerun = impact.get("affected_sub_harnesses", [])
    out = {
        "partial_rerun_plan": {
            "plan_id": f"RERUN-{args.patch_id}",
            "source_patch_id": args.patch_id,
            "plan_status": "candidate_requires_review",
            "rerun_sub_harnesses": rerun,
            "skipped_sub_harnesses": [],
            "human_approval_required": True,
            "blockers": [] if rerun else ["no affected sub harnesses found"],
            "human_review": human_review_gate("rerun-plan", "partial_rerun_plan"),
        }
    }
    out_path = run_path("prd_orchestrator", "partial_rerun_plans", f"{args.patch_id}.yaml")
    ywrite(out_path, out)
    print(f"Wrote {out_path}")

def validate_prd_template(args):
    prd = instance_path("product-spec", "PRD.md").read_text(encoding="utf-8")
    profile = yload(harness_path("sub_harnesses", "projection_sync_harness", "prd_template_profile.yaml"))
    reqs = profile.get("prd_template_profile", {}).get("required_sections", [])
    missing = [s for s in reqs if s not in prd]
    if missing:
        print("BLOCKED: missing sections")
        for m in missing:
            print(f"- {m}")
    else:
        print("PASS: PRD.md contains all required 14 sections")

def check_prd_sync(args):
    prd = instance_path("product-spec", "PRD.md").read_text(encoding="utf-8")
    placeholders = ["待同步", "由 `requirements.yaml` 投影", "由 `screens.yaml` 投影", "[用一句话说明"]
    found = [p for p in placeholders if p in prd]
    if found:
        print("REVIEW_REQUIRED: PRD.md still has placeholders/projection-only markers:")
        for f in found:
            print(f"- {f}")
    else:
        print("PASS: no obvious placeholder/projection-only marker found")

def preflight_prd_run(args):
    state = prd_run_state()
    print(json.dumps({"prd_run_preflight": state}, ensure_ascii=False, indent=2))
    blocker = prd_input_blocker("preflight-prd-run")
    if blocker:
        raise SystemExit(blocker)
    if state["prd_inputs"] and not state["source_baseline"] and not state["has_product_spec_material"]:
        raise SystemExit(
            "BLOCKED: PRD input exists, but source extraction has not run. "
            "Run `run-prd-loop --source <input>` or `extract-source-baseline <input>`."
        )
    if state["source_baseline"] and not state["source_baseline_review_approved"]:
        raise SystemExit(
            "BLOCKED: structured_source_baseline exists but has no approved review decision. "
            "Review the extraction output before downstream harness generation."
        )
    if state["source_baseline_review_approved"] and not state["has_product_spec_material"]:
        raise SystemExit(
            "BLOCKED: source baseline is approved, but product-spec still has no generated requirements/screens. "
            "Downstream requirement/screen generation is the next loop stage and must run before prototype runtime."
        )
    print("PASS: PRD run preflight has source material for the current stage")

def quality_gate(args):
    ensure_prd_input_or_block("quality-gate")
    ensure_run_manifest("quality-gate")
    req = yload(instance_path("product-spec", "requirements.yaml"))
    items = (req.get("requirement_candidates") or []) + (req.get("requirements") or [])
    source_baseline, source_baseline_relpath = load_source_baseline()
    if source_baseline and not items:
        raise SystemExit(
            "BLOCKED: source baseline exists, but no requirements or requirement_candidates were generated. "
            f"Next breakpoint: project reviewed baseline `{source_baseline_relpath}` into requirement_harness outputs before quality-gate."
        )
    if not items:
        raise SystemExit(
            "BLOCKED: quality-gate found no requirements or requirement_candidates. "
            "Run source extraction and requirement_harness generation before quality-gate; "
            "0/0/0 is not a valid PRD run result."
        )

    profile = yload(harness_path("sub_harnesses", "requirement_harness", "cears_quality_profile.yaml")).get("cears_quality_profile", {})
    vague = profile.get("vague_terms", [])
    req_record = profile.get("requirement_record_after_cears", {})
    req_record_fields = req_record.get("required_fields", [])
    allowed_evidence_status = set(req_record.get("allowed_evidence_status", []))
    quant = profile.get("quantification_after_cears", {})
    allowed_quant_decisions = set(quant.get("allowed_decisions", []))
    counts = {"blocked": 0, "review_required": 0, "passed": 0}
    results = []
    for it in items:
        fid = it.get("id", "UNKNOWN")
        final = "passed"
        findings = []
        cn = it.get("cn_ears", "")
        missing_record_fields = [field for field in req_record_fields if field not in it]
        if cn and missing_record_fields:
            final = "blocked"; findings.append(f"cears_without_requirement_record:{','.join(missing_record_fields)}")
        evidence_status = it.get("evidence_status")
        if evidence_status and evidence_status not in allowed_evidence_status:
            final = "blocked"; findings.append("invalid_evidence_status")
        if it.get("status") == "confirmed" and not it.get("source_refs"):
            final = "blocked"; findings.append("confirmed_without_source_ref")
        if evidence_status == "confirmed" and not it.get("source_refs"):
            final = "blocked"; findings.append("confirmed_without_source_ref")
        if it.get("priority") in ["P0", "P1"] and not it.get("acceptance"):
            final = "blocked"; findings.append("p0_p1_missing_acceptance")
        if it.get("priority") in ["P0", "P1"] and not it.get("quantification_review"):
            final = "blocked"; findings.append("p0_p1_missing_quantification_review")
        if any(t in cn for t in vague) and not it.get("fit_criteria"):
            if final != "blocked": final = "review_required"
            findings.append("vague_without_fit_criteria")
        if not it.get("quality_profile"):
            if final != "blocked": final = "review_required"
            findings.append("missing_quality_profile")
        qreview = it.get("quantification_review") or {}
        if qreview:
            decision = qreview.get("decision") or qreview.get("status")
            if decision not in allowed_quant_decisions:
                if final != "blocked": final = "review_required"
                findings.append("invalid_quantification_decision")
            elif decision == "quantified":
                required = quant.get("quantified_required_fields", [])
                missing = [field for field in required if not qreview.get(field)]
                if missing:
                    final = "blocked"
                    findings.append(f"quantified_missing_fields:{','.join(missing)}")
                if not qreview.get("source_refs"):
                    final = "blocked"
                    findings.append("quantified_number_without_source")
            elif decision == "not_quantifiable_yet":
                required = quant.get("not_quantifiable_yet_required_fields", [])
                missing = [field for field in required if not qreview.get(field)]
                if missing:
                    if final != "blocked": final = "review_required"
                    findings.append(f"not_quantifiable_yet_missing_fields:{','.join(missing)}")
            elif decision == "not_applicable":
                required = quant.get("not_applicable_required_fields", [])
                missing = [field for field in required if not qreview.get(field)]
                if missing:
                    if final != "blocked": final = "review_required"
                    findings.append(f"not_applicable_missing_fields:{','.join(missing)}")
        counts[final] += 1
        results.append({"id": fid, "final": final, "findings": findings})
    out = {
        "quality_gate_report": {
            "report_status": "candidate_requires_review",
            "summary": counts,
            "results": results,
            "human_review": human_review_gate("quality-gate", "quality_gate_report"),
        }
    }
    out_path = run_path("sub_harnesses", "requirement_harness", "reports", "QUALITY_GATE_REPORT.yaml")
    ywrite(out_path, out)
    print(f"Wrote {out_path}")
    print(json.dumps(counts, ensure_ascii=False, indent=2))

def md_cell(value, limit: int | None = None) -> str:
    if value is None:
        text = ""
    elif isinstance(value, list):
        text = "、".join(str(v) for v in value)
    elif isinstance(value, dict):
        text = "；".join(f"{k}={v}" for k, v in value.items())
    else:
        text = str(value)
    machine_like = bool(
        re.search(r"[/#]", text)
        or re.search(r"\b[\w.-]+\.(?:yaml|yml|md|json)\b", text, re.IGNORECASE)
        or re.search(r"[A-Za-z0-9]+_[A-Za-z0-9_]+", text)
    )
    if not machine_like and "_" not in text:
        text = (
            text.replace("Review", "评审")
            .replace("review", "评审")
            .replace("Baseline", "基线")
            .replace("baseline", "基线")
            .replace("Target", "目标")
            .replace("target", "目标")
            .replace("Gap", "待补项")
            .replace("gap", "待补项")
        )
    if not machine_like:
        text = re.sub(r"(?<![A-Za-z])review(?![A-Za-z])", "评审", text, flags=re.IGNORECASE)
        text = text.replace("release owner", "发布负责人")
        text = text.replace("quality gate", "质量门禁")
        text = text.replace("基线 和 目标", "基线和目标")
        text = text.replace("没有 基线", "没有基线")
        text = text.replace(" 评审", "评审")
    text = text.replace("\n", "<br>").replace("|", "\\|")
    if limit and len(text) > limit:
        return text[: limit - 3] + "..."
    return text

def list_cell(value, limit: int | None = None) -> str:
    if not value:
        return ""
    if not isinstance(value, list):
        return md_cell(value, limit)
    items = [str(v) for v in value]
    if limit and len(items) > limit:
        items = items[:limit] + ["..."]
    return md_cell("、".join(items))

def quality_summary_for_review() -> dict:
    report = yload(run_path("sub_harnesses", "requirement_harness", "reports", "QUALITY_GATE_REPORT.yaml"))
    return report.get("quality_gate_report", {}).get("summary", {})

def is_markdown_table_separator(text: str) -> bool:
    if not text.startswith("|"):
        return False
    stripped = text.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")
    return stripped == ""

def is_horizontal_rule(text: str) -> bool:
    return bool(re.fullmatch(r"[-*_]{3,}", text.strip()))

def is_document_meta_line(text: str) -> bool:
    stripped = text.strip().strip("*")
    return stripped.startswith(("文档版本：", "创建日期：", "状态："))

def is_symbol_only_line(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped in {"↓", "↑", "→", "←", "▼", "▲"}:
        return True
    if re.search(r"[A-Za-z0-9\u4e00-\u9fff]", stripped):
        return False
    return bool(re.fullmatch(r"[\s`*_+\-=|:：.。·,，;；/\\<>()[\]{}~^│┃║┌┐└┘├┤┬┴┼─━▲▼↔→←↓↑]+", stripped))

def markdown_heading(line: str):
    m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
    if not m:
        return None
    title = re.sub(r"^\d+(?:\.\d+)*\s*", "", m.group(2).strip())
    return len(m.group(1)), title

def table_cells(text: str) -> list[str] | None:
    if not text.strip().startswith("|"):
        return None
    if is_markdown_table_separator(text):
        return None
    cells = [cell.strip() for cell in text.strip().strip("|").split("|")]
    if not any(cells):
        return None
    return cells

def table_content(header: list[str], cells: list[str]) -> str:
    pairs = []
    for idx, cell in enumerate(cells):
        if not cell:
            continue
        key = header[idx] if idx < len(header) and header[idx] else f"字段{idx + 1}"
        pairs.append(f"{key}={cell}")
    return "；".join(pairs)

def clean_code_block_line(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^[\s│┃║┌┐└┘├┤┬┴┼─━]+", "", stripped)
    stripped = re.sub(r"[\s│┃║┌┐└┘├┤┬┴┼─━]+$", "", stripped)
    return stripped.strip()

def current_context(headings: list[str]) -> str:
    return " > ".join(headings)

def add_review_unit(units: list[dict], content: str, kind: str, headings: list[str]):
    cleaned = content.strip()
    if not cleaned or is_symbol_only_line(cleaned) or is_document_meta_line(cleaned):
        return
    units.append({
        "content": cleaned,
        "kind": kind,
        "context": current_context(headings),
    })

def markdown_review_units(text: str) -> list[dict]:
    units = []
    headings: list[str] = []
    table_header: list[str] | None = None
    in_code = False
    code_lines: list[str] = []
    code_headings: list[str] = []

    def close_code_block():
        nonlocal code_lines, in_code
        significant = [
            clean_code_block_line(line)
            for line in code_lines
            if clean_code_block_line(line) and not is_symbol_only_line(clean_code_block_line(line))
        ]
        if significant:
            add_review_unit(units, "\n".join(significant), "code_block", code_headings or headings)
        code_lines = []
        in_code = False

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if in_code:
            if stripped.startswith("```"):
                close_code_block()
            else:
                code_lines.append(raw_line)
            continue
        if stripped.startswith("```"):
            in_code = True
            code_lines = []
            code_headings = list(headings)
            table_header = None
            continue

        heading = markdown_heading(stripped)
        if heading:
            level, title = heading
            headings = headings[: level - 1] + [title]
            table_header = None
            continue
        if not stripped or is_horizontal_rule(stripped):
            table_header = None
            continue
        if stripped.startswith("|") and is_markdown_table_separator(stripped):
            continue

        cells = table_cells(stripped)
        if cells:
            if table_header is None:
                table_header = cells
                continue
            add_review_unit(units, table_content(table_header, cells), "table_row", headings)
            continue
        table_header = None

        content = stripped.strip("- ").strip()
        if content.endswith(("：", ":")) and len(content) <= 18:
            continue
        add_review_unit(units, content, "line", headings)

    if in_code:
        close_code_block()
    return units

def classify_review_unit(unit: dict) -> tuple[str, str, str, str, str]:
    content = unit.get("content", "")
    context = unit.get("context", "")
    kind = unit.get("kind", "")
    basis = f"{context} {content}"
    prototype_keywords = [
        "Figma",
        "figma",
        "原型",
        "prototype",
        "runtime",
        "reaction",
        "hotspot",
        "flow map",
        "sync map",
        "interaction map",
        "comment map",
        "Figma comment",
        "figma comment",
        "layout route",
        "route plan",
        "visual line",
        "pen line",
        "documentation-only",
        "component-binding",
        "component binding",
        "renderer",
        "UX writer",
        "uxwriter",
        "copy catalog",
    ]
    if any(k in basis for k in prototype_keywords):
        target_doc = "product-spec/prototype.runtime.json"
        if any(k in basis for k in ["reaction", "interaction map", "hotspot", "Figma reaction", "figma reaction"]):
            target_doc = "product-spec/figma-interaction-map.yaml"
        elif any(k in basis for k in ["sync map", "node map", "frame", "Figma frame", "figma frame"]):
            target_doc = "product-spec/figma-sync-map.yaml"
        elif any(k in basis for k in ["component-binding", "component binding", "组件绑定"]):
            target_doc = "product-spec/component-binding-map.yaml"
        return (
            "prototype_projection_change",
            "prototype_projection_harness",
            target_doc,
            "medium",
            f"markdown {kind} routed by prototype/map/comment/line keywords; requires review",
        )

    if "Contacts" in context:
        return (
            "core_change",
            "prd_core_harness",
            "product-spec/requirements.yaml",
            "medium",
            f"markdown {kind} routed by PRD contacts context; requires review",
        )
    if "Assumptions" in context:
        return (
            "core_change",
            "prd_core_harness",
            "product-spec/requirements.yaml",
            "medium",
            f"markdown {kind} routed by assumptions/risk context; requires review",
        )
    if (
        any(k in context for k in ["Summary", "Background", "Market Segment", "Value Proposition"])
        or ("Objective" in context and not ("关键结果" in context and kind == "table_row"))
    ):
        return (
            "core_change",
            "prd_core_harness",
            "product-spec/requirements.yaml",
            "medium",
            f"markdown {kind} routed by PRD core section context; requires review",
        )
    if any(k in basis for k in ["指标", "当前值", "目标值", "使用率", "付费率", "转化率", "日使用人次", "埋点", "事件", "实验", "A/B", "baseline", "target"]):
        return (
            "metric_event_change",
            "metrics_events_harness",
            "product-spec/metrics.yaml",
            "medium",
            f"markdown {kind} routed by metric/event context; requires review",
        )
    if any(k in basis for k in ["发布", "灰度", "回滚", "监控", "客服", "FAQ", "发版", "上线", "Phase", "版本规划", "风险与应对"]):
        return (
            "release_ops_change",
            "release_ops_harness",
            "product-spec/release-plan.md",
            "medium",
            f"markdown {kind} routed by release/ops context; requires review",
        )
    if any(k in context for k in ["交互流程", "入口", "交互方式", "模块间关系"]) or kind == "code_block":
        return (
            "screen_state_change",
            "screen_state_harness",
            "product-spec/screens.yaml",
            "medium",
            f"markdown {kind} routed by screen/flow context; requires review",
        )
    if any(k in context for k in ["Solution", "功能", "核心规则", "输出格式", "付费逻辑", "亲密度", "分析维度", "数据输入", "与亲密度的联动"]):
        return (
            "requirement_change",
            "requirement_harness",
            "product-spec/requirements.yaml",
            "medium",
            f"markdown {kind} routed by feature/requirement context; requires review",
        )
    if any(k in basis for k in ["页面", "状态表", "Loading", "Error", "Empty", "Success", "文案", "错误", "失败", "重试"]):
        return (
            "screen_state_change",
            "screen_state_harness",
            "product-spec/screens.yaml",
            "medium",
            f"markdown {kind} routed by screen/state keywords; requires review",
        )
    if any(k in basis for k in ["需求", "功能", "应当", "不得", "默认", "支持", "上传", "推荐", "展示", "设置", "修改", "识别", "解锁"]):
        return (
            "requirement_change",
            "requirement_harness",
            "product-spec/requirements.yaml",
            "medium",
            f"markdown {kind} routed by requirement keywords; requires review",
        )
    if any(k in context for k in ["Contacts", "Summary", "Background", "Objective", "Market Segment", "Value Proposition", "Assumptions"]) or any(k in basis for k in ["目标", "背景", "用户", "范围", "约束", "风险", "痛点", "假设"]):
        return (
            "core_change",
            "prd_core_harness",
            "product-spec/requirements.yaml",
            "medium",
            f"markdown {kind} routed by PRD core context; requires review",
        )
    return (
        "unknown",
        "prd_core_harness",
        "",
        "low",
        f"markdown {kind} could not be routed confidently; requires review",
    )

def source_relpath_for_ref(path: Path) -> str:
    try:
        return path.relative_to(INSTANCE_ROOT).as_posix()
    except ValueError:
        return display_path(path)

def source_ref_for_unit(source_path: Path, context: str) -> str:
    anchor = safe_slug(context or "document-root")
    return f"{source_relpath_for_ref(source_path)}#{anchor}"

def plain_excerpt(text: str, limit: int = 220) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) > limit:
        return cleaned[: limit - 3] + "..."
    return cleaned

def markdown_source_sections(text: str) -> list[dict]:
    sections = []
    headings: list[str] = []
    current: dict | None = None

    def close_section(end_line: int):
        nonlocal current
        if not current:
            return
        content_lines = current.pop("_content_lines")
        content = "\n".join(content_lines).strip()
        current["line_end"] = end_line
        current["summary"] = plain_excerpt(content, 220)
        current["content_line_count"] = len([line for line in content_lines if line.strip()])
        sections.append(current)
        current = None

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        heading = markdown_heading(stripped)
        if heading:
            close_section(line_no - 1)
            level, title = heading
            headings = headings[: level - 1] + [title]
            current = {
                "id": f"SRC-SEC-{len(sections) + 1:03d}",
                "level": level,
                "title": title,
                "path": current_context(headings),
                "line_start": line_no,
                "_content_lines": [],
            }
            continue
        if current:
            current["_content_lines"].append(raw_line)

    close_section(len(text.splitlines()))
    return sections

def core_source_review_question(context: str, content: str) -> str:
    if "Summary" in context or "Objective" in context:
        return "是否作为产品目标、一期范围或成功标准候选？请确认来源、范围边界和是否需要保留为开放问题。"
    if "Background" in context and "现状" in context:
        return "是否作为现状基线或背景事实保留？若涉及数值，请同步给指标 Harness 校验来源。"
    if "Background" in context and "问题" in context:
        return "是否作为问题陈述、用户痛点或需求动机保留？请确认不要写成已验证结论。"
    if "Market Segment" in context:
        return "是否作为目标用户、使用约束或一期边界候选？请确认覆盖人群和排除范围。"
    if "Value Proposition" in context:
        return "是否作为用户价值或付费价值候选？请确认是否需要拆到需求或指标。"
    if "Assumptions" in context or "风险=" in content or "假设=" in content:
        return "是否作为风险、假设或验证任务保留？请确认风险等级、验证方式和关闭条件。"
    return "是否作为目标、范围、用户、约束、风险或开放问题候选？请确认只保留源 PRD 有依据的内容。"

def requirement_source_review_question(context: str, content: str) -> str:
    if "功能优先级" in context or "优先级=" in content:
        return "是否作为需求优先级候选？请确认 P0/P1/P2 范围，并拆成独立 REQ。"
    if "付费逻辑" in context or "付费" in content or "会员" in content:
        return "是否作为付费/免费可见规则候选？请确认权益边界、默认态和验收标准。"
    if "核心规则" in context or "输出格式" in context:
        return "是否作为功能规则候选？请拆成原子需求，并补齐触发、输出、异常和验收。"
    if "数据输入" in context or "分析维度" in context:
        return "是否作为数据输入或分析规则候选？请确认最小数据量、降级规则和隐私边界。"
    if "联动" in context or "模块间关系" in context:
        return "是否作为模块联动规则候选？请确认读取关系、手动同步边界和禁止自动变更条件。"
    return "是否应拆分为原子需求？请补齐来源、触发条件、验收、验证方式和质量画像。"

def screen_source_review_question(context: str, content: str) -> str:
    basis = f"{context} {content}"
    if "模块间关系" in basis or "联动" in basis:
        return "是否作为模块联动状态候选？请确认读取关系、手动同步边界、默认值和禁止自动变更条件。"
    if "入口" in basis or "工具栏" in basis:
        return "是否作为入口或页面导航候选？请确认入口名称、触发条件、可见性和目标页面。"
    if "→" in basis or "流程" in basis:
        return "是否作为流程/状态推理链候选？请确认每一步的触发、系统动作、成功态、失败态和恢复路径。"
    if "付费" in basis or "会员" in basis or "免费" in basis:
        return "是否作为付费可见状态候选？请确认免费态、会员态、点击行为和转化事件。"
    if "亲密度" in basis:
        return "是否作为亲密度设置状态候选？请确认未设置、已设置、修改、保存失败和默认值状态。"
    if "关系分析" in basis:
        return "是否作为关系分析流程候选？请确认上传、识别、分析中、结果展示、降级和手动同步状态。"
    return "是否作为页面/状态候选？请确认用户任务、入口、出口、异常反馈和恢复路径。"

def metric_source_review_question(context: str, content: str) -> str:
    if "当前值=-" in content or "目标值=待定" in content:
        return "该指标当前值或目标值未定，是否保持待基线后确认？请补 owner、时间窗口和所需事件。"
    if "当前值=" in content or "目标值=" in content:
        return "该指标的当前值、目标值和时间窗口是否有来源？请确认公式、分母、分子和数据源。"
    if "埋点" in context or "事件" in context:
        return "是否需要转成事件或埋点候选？请确认触发时机、属性、去重键和关联指标。"
    return "是否作为指标、事件或实验候选？请确认口径、基线、目标、数据源和上线后校验方式。"

def release_source_review_question(context: str, content: str) -> str:
    if "Phase" in context or "版本规划" in context:
        return "是否作为发布阶段候选？请确认阶段范围、进入/退出条件、负责人和必备门禁。"
    if "风险" in context or "风险=" in content:
        return "是否作为发布风险或运营风险候选？请确认应对措施、监控信号和回滚条件。"
    return "是否作为发布、运营、灰度、客服、合规或回滚候选？请确认可执行门禁和责任人。"

def source_item_review_question(item_type: str, unit: dict) -> str:
    context = unit.get("context", "")
    content = unit.get("content", "")
    if "Contacts" in context:
        return "负责人是否需要补齐为评审或发布前置项，并写入全局待确认项或发布计划？"
    if item_type == "core_change":
        return core_source_review_question(context, content)
    if item_type == "requirement_change":
        return requirement_source_review_question(context, content)
    if item_type == "screen_state_change":
        return screen_source_review_question(context, content)
    if item_type == "metric_event_change":
        return metric_source_review_question(context, content)
    if item_type == "release_ops_change":
        return release_source_review_question(context, content)
    return "应保留为开放问题，还是重新路由到某个子 Harness？"

def source_open_question_text(item: dict) -> str:
    context = item.get("section_path") or "源 PRD"
    content = str(item.get("content") or "")
    harness = item.get("target_sub_harness")
    if "Contacts" in context or "角色=" in content:
        return f"请确认 `{context}` 中的负责人/角色待定项是否需要补齐 owner 和 required_before。"
    if harness == "metrics_events_harness":
        return f"请确认 `{context}` 中未定的指标基线/目标/时间窗口，并说明是否保持 TBD_AFTER_BASELINE。"
    if harness == "release_ops_harness":
        return f"请确认 `{context}` 中未闭合的发布、风险、验证方式或回滚门禁。"
    if harness == "screen_state_harness":
        return f"请确认 `{context}` 中的页面、状态、异常和恢复路径是否完整。"
    if harness == "requirement_harness":
        return f"请确认 `{context}` 中的需求边界、优先级或付费逻辑是否需要拆分。"
    return f"请确认 `{context}` 中的待定信息：{md_cell(content, 90)}"

def source_item_has_unresolved_marker(item: dict) -> bool:
    content = str(item.get("content") or "")
    if any(marker in content for marker in ["待定", "待确认", "TBD", "[待定]", "unknown", "Unknown"]):
        return True
    return bool(re.search(r"(当前值|基线|baseline|目标值|目标|target)\s*=\s*(-|—|无|未知)(?:；|$)", content, re.IGNORECASE))

def build_source_review_items(source_path: Path, text: str) -> tuple[list[dict], dict[str, list[dict]], list[dict]]:
    flat_items = []
    by_harness = {harness: [] for harness in SUB_HARNESS_ORDER}
    open_questions = []
    seen_questions = set()

    for i, unit in enumerate(markdown_review_units(text), start=1):
        item_type, harness, doc, confidence, reason = classify_review_unit(unit)
        item = {
            "id": f"SRC-ITEM-{i:03d}",
            "status": "candidate_not_approved",
            "extraction_type": item_type,
            "target_sub_harness": harness,
            "target_document_candidate": doc,
            "confidence": confidence,
            "source_ref": source_ref_for_unit(source_path, unit.get("context", "")),
            "section_path": unit.get("context", ""),
            "source_kind": unit.get("kind", ""),
            "content": unit.get("content", ""),
            "review_question": source_item_review_question(item_type, unit),
            "reason": reason,
        }
        flat_items.append(item)
        by_harness.setdefault(harness, []).append(item)
        if source_item_has_unresolved_marker(item):
            question = source_open_question_text(item)
            if question not in seen_questions:
                open_questions.append({
                    "id": f"SRC-OQ-{len(open_questions) + 1:03d}",
                    "status": "candidate_not_approved",
                    "question": question,
                    "target_sub_harness": harness,
                    "source_refs": [item["source_ref"]],
                    "source_item_id": item["id"],
                    "required_before": "write_product_spec_or_confirm_baseline",
                })
                seen_questions.add(question)

    return flat_items, by_harness, open_questions

def source_structure_gaps(by_harness: dict[str, list[dict]]) -> list[dict]:
    gaps = []
    required = {
        "prd_core_harness": "目标、用户、范围、约束和风险边界",
        "requirement_harness": "功能需求、规则、付费逻辑和验收候选",
        "screen_state_harness": "入口、流程、页面状态、异常和恢复路径",
        "metrics_events_harness": "指标、事件、实验、基线和目标候选",
        "release_ops_harness": "发布阶段、灰度门禁、回滚、运营和风险应对",
    }
    for harness, description in required.items():
        if not by_harness.get(harness):
            gaps.append({
                "id": f"SRC-GAP-{len(gaps) + 1:03d}",
                "target_sub_harness": harness,
                "description": f"源 PRD 未抽取到明确的{description}。",
                "review_question": f"是否源文档确实缺失{description}，还是结构化提取遗漏？",
            })
    return gaps

def write_source_sub_harness_inputs(baseline: dict, baseline_relpath: str) -> list[str]:
    root = run_path("prd_orchestrator", "source_extraction", "sub_harness_inputs")
    written = []
    open_questions = baseline.get("open_questions") or []
    structure_gaps = baseline.get("structure_gaps") or []
    for harness in SUB_HARNESS_ORDER:
        items = (baseline.get("review_items_by_sub_harness") or {}).get(harness) or []
        harness_questions = [
            item for item in open_questions
            if item.get("target_sub_harness") == harness
        ]
        harness_gaps = [
            item for item in structure_gaps
            if item.get("target_sub_harness") == harness
        ]
        out = {
            "source_baseline_sub_harness_input": {
                "baseline_id": baseline.get("baseline_id"),
                "status": baseline.get("status"),
                "target_sub_harness": harness,
                "source_baseline_relpath": baseline_relpath,
                "source_prd": baseline.get("source_prd"),
                "source_sha256": baseline.get("source_sha256"),
                "consume_after_review_decision": True,
                "candidate_items": items,
                "open_questions": harness_questions,
                "structure_gaps": harness_gaps,
                "consumption_contract": {
                    "do_not_read_raw_prd_markdown_again": True,
                    "do_not_promote_to_confirmed_without_review_decision": True,
                    "write_product_spec_only_after_extraction_review": True,
                },
            }
        }
        path = root / f"{harness}.yaml"
        ywrite(path, out)
        written.append(artifact_relpath(path))
    return written

def write_source_extraction_review(review_path: Path, baseline: dict, baseline_relpath: str):
    counts = baseline.get("item_counts_by_sub_harness", {})
    sub_harness_inputs = baseline.get("sub_harness_input_slices") or []
    lines = [
        "# 源 PRD 结构化提取评审",
        "",
        f"状态：`{baseline.get('status')}`  ",
        f"运行 ID：`{RUN_ID}`  ",
        f"来源 PRD：`{baseline.get('source_prd')}`  ",
        f"结构化基线：`{baseline_relpath}`",
        f"子 Harness 输入切片：`{len(sub_harness_inputs)}` 个",
        "",
        "## 评审结论",
        "",
        "| 项 | 结论 | 评审人 | 备注 |",
        "|---|---|---|---|",
        "| 源文档结构是否完整 | 待评审 |  |  |",
        "| 子 Harness 映射是否正确 | 待评审 |  |  |",
        "| 待确认项是否完整 | 待评审 |  |  |",
        "| 是否允许后续子 Harness 消费该基线 | 待评审 |  |  |",
        "",
        "## 覆盖摘要",
        "",
        "| 子 Harness | 候选项数 |",
        "|---|---:|",
    ]
    for harness in SUB_HARNESS_ORDER:
        lines.append(f"| `{harness}` | {counts.get(harness, 0)} |")

    lines.extend([
        "",
        "## 全局待确认项",
        "",
        "| ID | 问题 | 目标子 Harness | 来源 |",
        "|---|---|---|---|",
    ])
    for item in baseline.get("open_questions") or []:
        lines.append(
            f"| `{md_cell(item.get('id'))}` | {md_cell(item.get('question'))} | `{md_cell(item.get('target_sub_harness'))}` | {list_cell(item.get('source_refs'))} |"
        )
    if not baseline.get("open_questions"):
        lines.append("| `SRC-OQ-CHECK` | 源 PRD 未识别到显式待定项；请人工确认是否遗漏 TBD / 待定 / owner / target / baseline。 | `prd_core_harness` | `structured_source_baseline.yaml` |")

    lines.extend([
        "",
        "## 结构缺口",
        "",
        "| ID | 目标子 Harness | 描述 | 评审问题 |",
        "|---|---|---|---|",
    ])
    for gap in baseline.get("structure_gaps") or []:
        lines.append(
            f"| `{md_cell(gap.get('id'))}` | `{md_cell(gap.get('target_sub_harness'))}` | {md_cell(gap.get('description'))} | {md_cell(gap.get('review_question'))} |"
        )
    if not baseline.get("structure_gaps"):
        lines.append("| `SRC-GAP-CHECK` | `orchestrator` | 所有核心子 Harness 都抽取到候选项；请人工确认映射不是过度泛化。 | 是否允许进入后续子 Harness？ |")

    lines.extend([
        "",
        "## 后续规则",
        "",
        "- 该基线只是源文档结构化候选，不是 confirmed product-spec。",
        "- 批准前，子 Harness 不应直接消费散装源 PRD。",
        "- 批准后，后续子 Harness 应读取自己的 `sub_harness_inputs/<harness>.yaml` 切片，再生成各自的 `product-spec` 候选。",
    ])
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def extract_source_baseline(args):
    ensure_run_manifest("extract-source-baseline")
    source_path = resolve_input_path(args.markdown)
    if not source_path.exists():
        raise SystemExit(f"BLOCKED: source PRD input not found: {args.markdown}")
    text = source_path.read_text(encoding="utf-8")
    if not text.strip():
        raise SystemExit(f"BLOCKED: source PRD input is empty: {source_path}")
    sections = markdown_source_sections(text)
    review_items, by_harness, open_questions = build_source_review_items(source_path, text)
    baseline = {
        "baseline_id": f"{RUN_ID}-structured-source-baseline",
        "status": "candidate_requires_extraction_review",
        "source_prd": source_relpath_for_ref(source_path),
        "source_sha256": sha256_file(source_path),
        "created_at": utc_now_text(),
        "purpose": "Reviewed source PRD structure for first migration; downstream sub-harnesses consume this baseline instead of raw PRD markdown.",
        "downstream_contract": {
            "requires_review_decision_before_sub_harness_consumption": True,
            "sub_harnesses_must_consume_structured_baseline": True,
            "raw_prd_markdown_is_not_a_sub_harness_fact_source": True,
            "product_spec_writes_require_approved_review_decision": True,
        },
        "sections": sections,
        "review_items": review_items,
        "review_items_by_sub_harness": {h: by_harness.get(h, []) for h in SUB_HARNESS_ORDER},
        "item_counts_by_sub_harness": {h: len(by_harness.get(h, [])) for h in SUB_HARNESS_ORDER},
        "open_questions": open_questions,
        "structure_gaps": source_structure_gaps(by_harness),
        "sub_harness_input_slices": [],
        "human_review": human_review_gate("extract-source-baseline", "structured_source_baseline"),
    }
    out_path = run_path(*SOURCE_BASELINE_REL.parts)
    ywrite(out_path, {"structured_source_baseline": baseline})
    baseline_relpath = artifact_relpath(out_path)
    baseline["sub_harness_input_slices"] = write_source_sub_harness_inputs(baseline, baseline_relpath)
    ywrite(out_path, {"structured_source_baseline": baseline})
    review_path = run_path(*SOURCE_EXTRACTION_REVIEW_REL.parts)
    write_source_extraction_review(review_path, baseline, baseline_relpath)
    print(f"Wrote {out_path}")
    print(f"Wrote {review_path}")
    print(json.dumps({
        "review_items": len(review_items),
        "open_questions": len(open_questions),
        "structure_gaps": len(baseline["structure_gaps"]),
    }, ensure_ascii=False, indent=2))

def load_source_baseline() -> tuple[dict, str]:
    path = run_path(*SOURCE_BASELINE_REL.parts)
    if not path.exists():
        return {}, ""
    baseline = yload(path).get("structured_source_baseline", {})
    return baseline, artifact_relpath(path)

def load_source_baseline_candidate_items(baseline: dict, baseline_relpath: str) -> list[dict]:
    items = []
    for harness_items in (baseline.get("review_items_by_sub_harness") or {}).values():
        for item in harness_items or []:
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            items.append({
                "change_id": item.get("id"),
                "type": item.get("extraction_type"),
                "target_document_candidate": item.get("target_document_candidate"),
                "target_sub_harness_candidate": item.get("target_sub_harness"),
                "confidence": item.get("confidence"),
                "content": content,
                "source_context": item.get("section_path", ""),
                "source_kind": item.get("source_kind", ""),
                "review_question": item.get("review_question", ""),
                "reason": item.get("reason", "from structured_source_baseline"),
                "_change_request_id": baseline.get("baseline_id"),
                "_candidate_relpath": baseline_relpath,
            })
    return items

def load_change_candidate_items() -> list[dict]:
    items = []
    candidate_dir = run_path("prd_orchestrator", "change_patch_candidates")
    for path in sorted(candidate_dir.glob("*.candidate.yaml")):
        data = yload(path).get("change_patch_candidate", {})
        request_id = data.get("change_request_id") or path.stem
        for item in data.get("extracted_changes") or []:
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            enriched = dict(item)
            enriched["_change_request_id"] = request_id
            enriched["_candidate_relpath"] = artifact_relpath(path)
            items.append(enriched)
    return items

def candidate_filter(items: list[dict], *, harness: str | None = None, types: set[str] | None = None) -> list[dict]:
    filtered = []
    for item in items:
        if harness and item.get("target_sub_harness_candidate") != harness:
            continue
        if types and item.get("type") not in types:
            continue
        filtered.append(item)
    return filtered

def candidate_mapping_cell(item: dict) -> str:
    rel = item.get("_candidate_relpath") or "prd_orchestrator/change_patch_candidates/"
    change_id = item.get("change_id") or ""
    return f"{rel}#{change_id}" if change_id else rel

def append_structure_gap(lines: list[str], gap_id: str, description: str, source: str, review_question: str):
    lines.append(
        f"| `{md_cell(gap_id)}` | {md_cell(description)} | {md_cell(source)} | {md_cell(review_question)} |"
    )

def item_review_question(item: dict, fallback: str) -> str:
    return str(item.get("review_question") or fallback)

def screen_candidate_label(item: dict) -> str:
    basis = f"{item.get('source_context', '')} {item.get('content', '')}"
    if "模块间关系" in basis or "联动" in basis:
        return "模块联动状态候选"
    if "话题推荐" in basis and ("入口" in basis or "工具栏" in basis):
        return "话题推荐入口候选"
    if "话题推荐" in basis or "推荐话题" in basis:
        return "话题推荐流程候选"
    if "关系分析" in basis or "聊天记录" in basis:
        return "关系分析流程候选"
    if "亲密度" in basis:
        return "亲密度设置状态候选"
    if "付费" in basis or "会员" in basis or "免费" in basis:
        return "付费可见状态候选"
    if "工具栏" in basis:
        return "AI 键盘工具栏候选"
    if "→" in basis:
        return "流程状态候选"
    return "页面/状态候选"

def screen_state_hint(item: dict) -> str:
    basis = f"{item.get('source_context', '')} {item.get('content', '')}"
    if "模块间关系" in basis or "联动" in basis:
        return "待拆：读取关系 / 同步关系 / 默认值 / 不自动变更"
    if "入口" in basis or "工具栏" in basis:
        return "待拆：可见 / 不可见 / 点击 / 跳转失败"
    if "上传" in basis or "截图" in basis or "AI分析" in basis or "OCR" in basis:
        return "待拆：选择图片 / 上传中 / 分析中 / 成功 / 失败 / 重试"
    if "付费" in basis or "会员" in basis or "免费" in basis:
        return "待拆：免费可见 / 会员可见 / 未开通 / 点击转化"
    if "亲密度" in basis:
        return "待拆：未设置 / 已设置 / 修改中 / 保存成功 / 保存失败"
    if "关系分析" in basis:
        return "待拆：上传中 / 识别中 / 分析中 / 结果展示 / 降级"
    return "待拆：触发 / 成功 / 失败 / 空态 / 恢复路径"

def run_relative_arg(path_text: str | None, default: Path, option_name: str) -> Path:
    path = Path(path_text) if path_text else default
    if path.is_absolute() or ".." in path.parts:
        raise SystemExit(f"BLOCKED: {option_name} must be a relative path under <instance-root>/runs/<run-id>/")
    return path

def validate_patch_report(args):
    artifact = resolve_run_artifact(args.artifact)
    print_blocking_validation("validate-patch-report", validate_with_schema(artifact, "patch_report.schema.json"))

def validate_stop_the_line(args):
    artifact = resolve_run_artifact(args.artifact)
    print_blocking_validation("validate-stop-the-line", validate_with_schema(artifact, "stop_the_line.schema.json"))

def stop_the_line(args):
    ensure_run_manifest("stop-the-line")
    out = write_stop_report(
        stage=args.stage,
        reason=args.reason,
        required_next_action=args.next_action,
        resume_condition=args.resume_condition,
        severity=args.severity,
        sub_harness=args.sub_harness,
        owner=args.owner,
        source_artifacts=args.source_artifact or [],
        notes=args.notes,
        stop_id=args.stop_id,
        output=args.output,
    )
    print(f"Wrote {out}")
    print(f"Wrote {markdown_companion_path(out)}")

def write_patch_report(args):
    ensure_run_manifest("write-patch-report")
    patch_id = args.patch_id or f"PATCH-{RUN_ID}-{utc_slug_text()}"
    out = run_output_path(
        args.output,
        Path("prd_orchestrator") / "patch_reports" / f"{safe_slug(patch_id)}.patch_report.yaml",
        "--output",
    )
    data = {
        "patch_report": {
            "schema_version": "1.0",
            "patch_id": patch_id,
            "run_id": RUN_ID,
            "sub_harness": args.sub_harness,
            "status": args.status,
            "summary": args.summary,
            "root_cause": args.root_cause,
            "source_artifacts": args.source_artifact or [],
            "changed_files": args.changed_file,
            "validation": args.validation,
            "remaining_gaps": args.remaining_gap or [],
            "stop_the_line_refs": args.stop_the_line_ref or [],
            "human_review": human_review_gate("patch-report", "patch_report"),
        }
    }
    ywrite(out, data)
    errors = validate_with_schema(out, "patch_report.schema.json")
    if errors:
        raise SystemExit("BLOCKED: generated patch_report failed schema validation:\n- " + "\n- ".join(errors))
    write_patch_report_markdown(out, data)
    print(f"Wrote {out}")
    print(f"Wrote {markdown_companion_path(out)}")

def loop_root_path() -> Path:
    return harness_path("sub_harnesses", "prototype_projection_harness", "drd_v3_1", "loop_v3_1")

def drd_root_path() -> Path:
    return loop_root_path().parent

def loop_schema_path(name: str) -> Path:
    return loop_root_path() / "schemas" / name

def loop_rules_path(name: str) -> Path:
    return loop_root_path() / "rules" / name

def collect_values_for_key(node, key: str) -> list[str]:
    values = []
    if isinstance(node, dict):
        for current_key, current_value in node.items():
            if current_key == key and isinstance(current_value, str):
                values.append(current_value)
            values.extend(collect_values_for_key(current_value, key))
    elif isinstance(node, list):
        for item in node:
            values.extend(collect_values_for_key(item, key))
    return values

def drd_rule_source_index() -> dict[str, str]:
    index = {}
    rules_root = drd_root_path() / "rules"
    for path in sorted(rules_root.glob("*.yaml")):
        data = yload(path)
        for rule_id in collect_values_for_key(data, "rule_id"):
            index.setdefault(rule_id, path.relative_to(drd_root_path()).as_posix())
    return index

def rule_projection_map() -> dict:
    return yload(drd_root_path() / "rules" / "13_rule_projection_map.yaml").get("prototype_rule_projection_map", {})

def normalize_rule_ids(rule_ids: list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    return sorted({str(rule_id) for rule_id in (rule_ids or []) if str(rule_id or "").strip()})

def stage_rule_ids(stage_id: str | None) -> list[str]:
    if not stage_id:
        return []
    return normalize_rule_ids((rule_projection_map().get("stages", {}) or {}).get(stage_id, []) or [])

def failure_class_rule_ids(failure_class: str | None) -> list[str]:
    if not failure_class:
        return []
    return normalize_rule_ids((rule_projection_map().get("failure_classes", {}) or {}).get(failure_class, []) or [])

def loop_gate_rule_trace(stage_id: str, failure_class: str) -> dict:
    rule_ids = normalize_rule_ids(stage_rule_ids(stage_id) + failure_class_rule_ids(failure_class))
    sources = drd_rule_source_index()
    projection = rule_projection_map()
    return {
        "trace_version": "3.1.1",
        "projection_map_id": projection.get("id", "RULE_PROJECTION_MAP_V3_1_1"),
        "stage_id": stage_id,
        "failure_class": failure_class,
        "rule_ids": rule_ids,
        "rule_sources": [
            {"rule_id": rule_id, "file": sources.get(rule_id, "")}
            for rule_id in rule_ids
        ],
        "validator_commands": ["validate-loop-finding", "validate-repair-plan", "validate-loop-manifest"],
    }

def loop_failure_classes() -> dict:
    rules = yload(loop_rules_path("04_failure_classification_rules.yaml")).get("failure_classification_rules", {})
    return {item.get("class_id"): item for item in rules.get("classes", []) or [] if item.get("class_id")}

def loop_router_table() -> dict:
    rules = yload(loop_rules_path("05_loop_router_rules.yaml")).get("loop_router_rules", {})
    return (rules.get("route_table") or {})

def loop_profiles() -> dict:
    policy = yload(loop_rules_path("02_loop_profile_policy.yaml")).get("loop_profile_policy", {})
    return {item.get("profile_id"): item for item in policy.get("profiles", []) or [] if item.get("profile_id")}

def loop_stage_contracts() -> dict:
    contracts = yload(loop_rules_path("17_harness_aligned_stage_loop_contracts.yaml")).get("harness_aligned_stage_loop_contracts", {})
    return {item.get("stage_id"): item for item in contracts.get("contracts", []) or [] if item.get("stage_id")}

def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()

def route_targets_for_failure(failure_class: str, stage: str) -> tuple[list[str], list[str], str, bool]:
    classes = loop_failure_classes()
    routers = loop_router_table()
    if failure_class not in classes:
        known = ", ".join(sorted(classes))
        raise SystemExit(f"BLOCKED: unknown failure_class {failure_class}. Known classes: {known}")
    class_rule = classes[failure_class]
    route_rule = routers.get(failure_class, {})
    route_targets = route_rule.get("route_to") or class_rule.get("default_route") or [stage]
    route_targets = [stage if target == "owning_stage" else target for target in route_targets]
    rerun_after = route_rule.get("rerun_after") or []
    patch_type = class_rule.get("patch_type") or "loop_repair_recommendation"
    stop_auto_patch = bool(route_rule.get("stop_auto_patch") or class_rule.get("auto_patch_allowed") is False)
    return route_targets, rerun_after, patch_type, stop_auto_patch

def loop_rerun_scope(severity: str, affected_artifacts: list[str], rerun_after: list[str], stop_auto_patch: bool) -> dict:
    if stop_auto_patch or severity == "semantic_defect":
        scope = "stop_auto_patch"
        reason = "semantic defect or rule-level stop_auto_patch; gate-only mode records evidence and stops."
    elif affected_artifacts:
        scope = "affected_artifact_only"
        reason = "gate-only mode records the affected artifact scope but does not rerun."
    else:
        scope = "stage_only"
        reason = "gate-only mode records the owning stage scope but does not rerun."
    return {
        "scope": scope,
        "reason": reason,
        "would_rerun_after": rerun_after,
        "actual_rerun_executed": False,
    }

def loop_profile_iteration_policy(profile_id: str) -> dict:
    profiles = loop_profiles()
    if profile_id not in profiles:
        known = ", ".join(sorted(profiles))
        raise SystemExit(f"BLOCKED: unknown loop profile {profile_id}. Known profiles: {known}")
    return profiles[profile_id].get("max_iterations", {}) or {}

def loop_gate_dir(gate_id: str) -> Path:
    return run_path("prd_orchestrator", "loop_gates", safe_slug(gate_id))

def write_loop_report_markdown(
    *,
    path: Path,
    gate_id: str,
    finding: dict,
    repair_plan: dict,
    manifest: dict,
    stop_line_relpath: str,
):
    lines = [
        "# Loop Gate Report",
        "",
        "本文件是人工阅读入口；同目录 YAML 是机器校验源。",
        "",
        "## 状态",
        "",
        "| 字段 | 值 |",
        "|---|---|",
        f"| gate_id | `{md_inline(gate_id)}` |",
        f"| run_id | `{md_inline(finding.get('run_id'))}` |",
        f"| stage | `{md_inline(finding.get('stage'))}` |",
        f"| severity | `{md_inline(finding.get('severity'))}` |",
        f"| failure_class | `{md_inline(finding.get('failure_class'))}` |",
        f"| rule_ids | `{md_inline(finding.get('rule_ids'))}` |",
        f"| profile | `{md_inline(repair_plan.get('selected_profile'))}` |",
        f"| final_status | `{md_inline(manifest.get('final_status'))}` |",
        "",
        "## Finding",
        "",
        f"- finding_id: `{md_inline(finding.get('finding_id'))}`",
        f"- trigger_source: `{md_inline(finding.get('trigger_source'))}`",
        f"- affected_artifacts: `{md_inline(finding.get('affected_artifacts'))}`",
        f"- source_refs: `{md_inline(finding.get('source_refs'))}`",
        f"- repair_hint_zh: {md_inline(finding.get('repair_hint_zh'))}",
        "",
        "## Repair Plan",
        "",
        f"- route_targets: `{md_inline(repair_plan.get('route_targets'))}`",
        f"- patch_set_count: `{len(repair_plan.get('patch_set') or [])}`",
        f"- rerun_scope: `{md_inline((repair_plan.get('rerun_scope') or {}).get('scope'))}`",
        f"- actual_patch_apply_executed: `{md_inline(repair_plan.get('actual_patch_apply_executed'))}`",
        f"- actual_rerun_executed: `{md_inline((repair_plan.get('rerun_scope') or {}).get('actual_rerun_executed'))}`",
        "",
        "## Stop Line",
        "",
        f"- stop_the_line: `{md_inline(stop_line_relpath or 'not_required')}`",
        "",
        "## 机器源",
        "",
        "- `loop_finding.yaml`",
        "- `repair_plan.yaml`",
        "- `loop_manifest.yaml`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def write_loop_gate(args):
    ensure_run_manifest("write-loop-gate")
    contracts = loop_stage_contracts()
    if args.stage not in contracts:
        known = ", ".join(sorted(contracts))
        raise SystemExit(f"BLOCKED: unknown stage {args.stage}. Known loop stages: {known}")

    gate_id = args.gate_id or f"LOOP-GATE-{RUN_ID}-{utc_slug_text()}"
    finding_id = f"{safe_slug(gate_id)}-FINDING"
    affected_artifacts = args.affected_artifact or [f"stage:{args.stage}"]
    source_refs = args.source_ref or [f"manual_review:{args.stage}"]
    route_targets, rerun_after, patch_type, stop_auto_patch = route_targets_for_failure(args.failure_class, args.stage)
    max_iterations = loop_profile_iteration_policy(args.profile)
    rule_trace = loop_gate_rule_trace(args.stage, args.failure_class)
    rule_ids = rule_trace["rule_ids"]
    input_lock_hash = sha256_text(json.dumps({
        "run_id": RUN_ID,
        "gate_id": gate_id,
        "stage": args.stage,
        "trigger_source": args.trigger_source,
        "severity": args.severity,
        "failure_class": args.failure_class,
        "rule_ids": rule_ids,
        "affected_artifacts": affected_artifacts,
        "source_refs": source_refs,
        "repair_hint_zh": args.repair_hint,
        "profile": args.profile,
    }, ensure_ascii=False, sort_keys=True))
    created_at = utc_now_text()

    finding = {
        "finding_id": finding_id,
        "run_id": RUN_ID,
        "stage": args.stage,
        "trigger_source": args.trigger_source,
        "severity": args.severity,
        "failure_class": args.failure_class,
        "rule_trace": rule_trace,
        "rule_ids": rule_ids,
        "affected_stage_candidate": route_targets,
        "affected_artifacts": affected_artifacts,
        "source_refs": source_refs,
        "repair_hint_zh": args.repair_hint,
        "created_at": created_at,
    }
    patch_id = f"{safe_slug(gate_id)}-PATCH-RECOMMENDATION"
    patch_set = [{
        "patch_id": patch_id,
        "patch_type": patch_type,
        "source_finding_id": finding_id,
        "rule_ids": rule_ids,
        "before_hash": input_lock_hash,
        "operations": [
            {"record_repair_hint_zh": args.repair_hint},
            {"route_targets": route_targets},
            {"gate_only_no_patch_apply": True},
        ],
        "after_hash": "sha256:not-applied-gate-only",
        "writes_prd": False,
        "source_refs": source_refs,
        "status": "recommendation_only",
    }]
    repair_plan = {
        "plan_id": f"{safe_slug(gate_id)}-REPAIR-PLAN",
        "loop_version": "3.1",
        "gate_only": True,
        "rule_trace": rule_trace,
        "rule_ids": rule_ids,
        "findings": [{
            "finding_id": finding_id,
            "failure_class": args.failure_class,
            "rule_ids": rule_ids,
        }],
        "selected_profile": args.profile,
        "route_targets": route_targets,
        "patch_set": patch_set,
        "rerun_scope": loop_rerun_scope(args.severity, affected_artifacts, rerun_after, stop_auto_patch),
        "revalidate": contracts[args.stage].get("revalidate", []) or [],
        "max_iterations_policy": max_iterations,
        "actual_patch_apply_executed": False,
        "apply_allowed_patches_executed": False,
    }
    stop_required = args.severity in {"blocker", "semantic_defect"} or stop_auto_patch
    manifest = {
        "run_id": RUN_ID,
        "loop_version": "3.1",
        "loop_profile": args.profile,
        "rule_trace": rule_trace,
        "rule_ids": rule_ids,
        "input_lock_hash": input_lock_hash,
        "iterations": [{
            "iteration_id": 1,
            "started_at": created_at,
            "input_hash": input_lock_hash,
            "rule_ids": rule_ids,
            "findings": [finding],
            "repair_plan": {
                "plan_id": repair_plan["plan_id"],
                "selected_profile": args.profile,
                "route_targets": route_targets,
            },
            "patch_set": patch_set,
            "rerun_scope": repair_plan["rerun_scope"],
            "revalidation_results": {
                "status": "blocked" if stop_required else "review_required",
                "reason": "gate-only mode records the finding; no patch apply or rerun was executed.",
            },
            "output_hash": "sha256:not-applied-gate-only",
            "exit_decision": "stop_line" if stop_required else "review_required",
        }],
        "final_status": "stop_line" if stop_required else "review_required",
        "final_exit_reason": "blocker or semantic defect recorded" if stop_required else "loop gate evidence recorded for review",
    }

    out_dir = loop_gate_dir(gate_id)
    finding_path = out_dir / "loop_finding.yaml"
    repair_path = out_dir / "repair_plan.yaml"
    manifest_path = out_dir / "loop_manifest.yaml"
    report_path = out_dir / "final_loop_report.md"
    ywrite(finding_path, finding)
    ywrite(repair_path, repair_plan)
    ywrite(manifest_path, manifest)

    generated_errors = []
    generated_errors.extend(validate_with_schema_path(finding_path, loop_schema_path("loop_finding.schema.json")))
    generated_errors.extend(validate_with_schema_path(repair_path, loop_schema_path("repair_plan.schema.json")))
    generated_errors.extend(validate_with_schema_path(manifest_path, loop_schema_path("loop_manifest.schema.json")))
    if generated_errors:
        raise SystemExit("BLOCKED: generated loop gate failed schema validation:\n- " + "\n- ".join(generated_errors))

    stop_line_relpath = ""
    if stop_required:
        stop_path = write_stop_report(
            stage=args.stage,
            reason=f"Loop gate recorded {args.severity} finding {finding_id}: {args.failure_class}.",
            required_next_action="Review final_loop_report.md and decide whether to implement a real prototype artifact generator, patch applier, or manual PRD clarification.",
            resume_condition="A human review decision exists and the artifact generator or manual repair path is explicitly selected.",
            severity="critical" if args.severity == "semantic_defect" else "blocker",
            sub_harness="prototype_projection_harness",
            source_artifacts=[
                artifact_relpath(finding_path),
                artifact_relpath(repair_path),
                artifact_relpath(manifest_path),
            ],
            notes="Generated by write-loop-gate in gate-only mode; no patch apply, rerun, product-spec write, or Figma write occurred.",
            stop_id=f"STL-{safe_slug(gate_id)}",
        )
        stop_line_relpath = artifact_relpath(stop_path)

    write_loop_report_markdown(
        path=report_path,
        gate_id=gate_id,
        finding=finding,
        repair_plan=repair_plan,
        manifest=manifest,
        stop_line_relpath=stop_line_relpath,
    )
    print(f"Wrote {finding_path}")
    print(f"Wrote {repair_path}")
    print(f"Wrote {manifest_path}")
    print(f"Wrote {report_path}")
    if stop_line_relpath:
        print(f"Wrote {run_path(*Path(stop_line_relpath).parts)}")
        print(f"Wrote {markdown_companion_path(run_path(*Path(stop_line_relpath).parts))}")

def core_review_category_specs() -> list[dict]:
    return [
        {
            "key": "success_criteria",
            "title": "成功标准",
            "default_action": "作为一期成功标准保留",
            "confirm": "确认它是否就是一期成功标准；如果太空，请直接写改写后的标准。",
        },
        {
            "key": "background_facts",
            "title": "背景事实",
            "default_action": "作为背景事实保留",
            "confirm": "确认它只作为背景事实；如果包含数值，请确认数值是否作为现状基线。",
        },
        {
            "key": "problem_motivations",
            "title": "需求动机",
            "default_action": "作为需求动机保留",
            "confirm": "确认它是否准确描述了为什么要做；不要把它改写成已验证结论。",
        },
        {
            "key": "goals",
            "title": "产品目标",
            "default_action": "作为产品目标保留",
            "confirm": "确认它是否是一阶段目标；如果目标过大，请在备注写收窄后的表达。",
        },
        {
            "key": "target_users",
            "title": "目标用户",
            "default_action": "作为目标用户保留",
            "confirm": "确认这类用户是否属于一期目标用户；如需排除人群，请在备注写清。",
        },
        {
            "key": "constraints",
            "title": "约束与一期边界",
            "default_action": "作为使用约束或一期边界保留",
            "confirm": "确认它是否是本期必须遵守的边界；如果只是建议，请标为改写或不保留。",
        },
        {
            "key": "user_values",
            "title": "用户价值与付费价值",
            "default_action": "作为用户价值保留",
            "confirm": "确认它是价值说明还是还需要拆成需求；如要拆，请确认拆分方向。",
        },
        {
            "key": "risks",
            "title": "风险",
            "default_action": "作为风险保留",
            "confirm": "确认风险是否真实存在；如风险等级、验证方式不对，请在备注直接改。",
        },
        {
            "key": "excluded_items",
            "title": "不保留项",
            "default_action": "不写入本期 PRD",
            "confirm": "确认它是否确实不保留；如果要保留，请在备注写应改成什么类别。",
        },
    ]

def friendly_harness_name(value: str | None) -> str:
    if not value:
        return ""
    mapping = {
        "prd_core_harness": "PRD 核心 Harness",
        "requirement_harness": "需求 Harness",
        "screen_state_harness": "页面/状态 Harness",
        "metrics_events_harness": "指标/事件 Harness",
        "release_ops_harness": "发布/运营 Harness",
        "traceability_harness": "可追踪性 Harness",
        "projection_sync_harness": "PRD 投影同步 Harness",
    }
    parts = re.split(r"\s*\+\s*", value)
    return " + ".join(mapping.get(part, part) for part in parts)

def core_route_map(routes: list[dict]) -> dict[str, list[dict]]:
    mapped: dict[str, list[dict]] = {}
    for route in routes:
        source_id = str(route.get("source_item_id") or "")
        if not source_id:
            continue
        mapped.setdefault(source_id, []).append(route)
    return mapped

def core_review_recommended_action(item: dict, spec: dict, routes_by_item: dict[str, list[dict]]) -> str:
    if item.get("promotion_allowed") is False or spec["key"] == "excluded_items":
        return "不写入本期 PRD"
    if item.get("split_to_requirement") is True:
        action = "保留价值说明，并在后续拆成需求"
    elif item.get("split_to_requirement") is False:
        action = "只作为价值说明保留，不拆成需求"
    else:
        action = spec["default_action"]
    routes = routes_by_item.get(str(item.get("id") or "")) or []
    if routes:
        harnesses = "、".join(friendly_harness_name(route.get("target_sub_harness")) for route in routes)
        action = f"{action}；后续由{harnesses} 继续处理"
    if item.get("risk_level"):
        action = f"{action}；风险等级：{item.get('risk_level')}"
    if item.get("validation"):
        action = f"{action}；验证方式：{item.get('validation')}"
    return action

def core_review_confirm_prompt(item: dict, spec: dict, routes_by_item: dict[str, list[dict]]) -> str:
    routes = routes_by_item.get(str(item.get("id") or "")) or []
    if routes and spec["key"] != "excluded_items":
        reasons = "；".join(str(route.get("reason") or "") for route in routes if route.get("reason"))
        return f"{spec['confirm']}同时确认后续处理方向是否正确：{reasons}"
    return spec["confirm"]

def append_core_review_section(lines: list[str], candidates: dict, spec: dict, routes_by_item: dict[str, list[dict]]):
    items = candidates.get(spec["key"]) or []
    lines.extend([
        "",
        f"## {spec['title']}",
        "",
        "可选结果：`确认` / `改写` / `不保留` / `暂缓`。如果选择 `改写`，直接在备注里写改后的中文。",
        "",
        "| ID | 需确认内容 | 推荐处理 | 你需要确认什么 | 确认结果 | 备注 |",
        "|---|---|---|---|---|---|",
    ])
    if not items:
        lines.append("| `无` | 当前没有该类候选 |  |  |  |  |")
        return
    for item in items:
        lines.append(
            f"| `{md_cell(item.get('id'))}` | {md_cell(item.get('title'), 180)} | {md_cell(core_review_recommended_action(item, spec, routes_by_item), 180)} | {md_cell(core_review_confirm_prompt(item, spec, routes_by_item), 180)} | 待填写 |  |"
        )

def core_open_question_answer(item: dict) -> str:
    parts = []
    if item.get("owner"):
        parts.append(f"owner：{item.get('owner')}")
    if item.get("required_before"):
        parts.append(f"required_before：{item.get('required_before')}")
    if item.get("time_window"):
        parts.append(f"时间窗口：{item.get('time_window')}")
    if not parts:
        for key, value in item.items():
            if key in {"id", "status", "review_decision_ref"}:
                continue
            if value:
                parts.append(f"{key}：{value}")
    return "；".join(parts) or "待补充"

def append_core_review_evidence(lines: list[str], candidates: dict):
    lines.extend([
        "",
        "## 附录：追源信息",
        "",
        "这部分只在需要核对来源时看。正常评审优先看上面的确认单。",
        "",
        "| ID | 来源 | 评审决策记录 |",
        "|---|---|---|",
    ])
    for spec in core_review_category_specs():
        for item in candidates.get(spec["key"]) or []:
            lines.append(
                f"| `{md_cell(item.get('id'))}` | {list_cell(item.get('source_refs'), 6)} | `{md_cell(item.get('review_decision_ref'))}` |"
            )

def core_review_md(args):
    ensure_run_manifest("core-review-md")
    candidates_rel = run_relative_arg(args.candidates, CORE_FACT_CANDIDATES_REL, "--candidates")
    output_rel = run_relative_arg(args.output, CORE_REVIEW_MD_REL, "--output")
    candidates_path = run_path(*candidates_rel.parts)
    if not candidates_path.exists():
        raise SystemExit(f"BLOCKED: core candidates not found: {artifact_relpath(candidates_path) if path_is_within(candidates_path, RUN_ROOT) else candidates_path}")
    candidates = yload(candidates_path).get("prd_core_fact_candidates", {})
    if not candidates:
        raise SystemExit(f"BLOCKED: invalid core candidates artifact: {display_path(candidates_path)}")

    summary = {}
    for spec in core_review_category_specs():
        summary[spec["key"]] = len(candidates.get(spec["key"]) or [])
    open_questions = candidates.get("open_questions") or []
    downstream_routes = candidates.get("downstream_routes") or []
    review = candidates.get("human_review") or {}
    routes_by_item = core_route_map(downstream_routes)

    lines = [
        "# CORE-000 核心事实确认单",
        "",
        f"状态：`{candidates.get('status')}`  ",
        f"运行 ID：`{RUN_ID}`  ",
        f"候选来源：`{artifact_relpath(candidates_path)}`",
        "",
        "## 怎么确认",
        "",
        "你只需要在每行的 `确认结果` 写一种结论：",
        "",
        "- `确认`：内容和推荐处理都同意。",
        "- `改写`：内容要保留，但表述要改；直接在备注写改后的中文。",
        "- `不保留`：这条不进入本期 PRD，也不交给后续子 Harness。",
        "- `暂缓`：现在不能确认；备注写缺什么信息、谁来确认、什么时候前确认。",
        "",
        "本阶段只确认核心事实和后续处理方向，不需要你填写 YAML 路径，也不需要在这里写正式评审记录命令。",
        "",
        "## 总确认",
        "",
        "| 需要你确认的事 | 确认方式 | 确认结果 | 备注 |",
        "|---|---|---|---|",
        "| 上方核心事实是否可以作为本期 PRD 候选继续处理 | 全部重要条目为 `确认` 或已在备注中 `改写` | 待填写 |  |",
        "| 不保留项是否确实不进入本期 PRD | 逐条确认“不保留项”表 | 待填写 |  |",
        "| 需要下游拆分的条目方向是否正确 | 逐条确认“后续处理确认”表 | 待填写 |  |",
        "| 是否允许进入下一个 subharness | 若没有 `暂缓` 或 `阻塞` 信息，写 `确认进入` | 待填写 |  |",
        "",
        "## 候选摘要",
        "",
        "| 类别 | 数量 |",
        "|---|---:|",
    ]
    for spec in core_review_category_specs():
        lines.append(f"| {spec['title']} | {summary.get(spec['key'], 0)} |")
    lines.extend([
        f"| 已回答开放问题 | {len(open_questions)} |",
        f"| 后续处理 | {len(downstream_routes)} |",
        "",
        "## 已补充信息确认",
        "",
        "这些是前一轮已经人工补充的信息。这里只确认“是否可以按这个答案继续”。",
        "",
        "| ID | 已补充信息 | 你需要确认什么 | 确认结果 | 备注 |",
        "|---|---|---|---|---|",
    ])
    if open_questions:
        for item in open_questions:
            lines.append(
                f"| `{md_cell(item.get('id'))}` | {md_cell(core_open_question_answer(item), 160)} | 是否同意按该补充信息关闭或继续使用？ | 待填写 |  |"
            )
    else:
        lines.append("| `无` | 当前没有已补充信息 |  |  |  |")

    for spec in core_review_category_specs():
        append_core_review_section(lines, candidates, spec, routes_by_item)

    lines.extend([
        "",
        "## 后续处理确认",
        "",
        "这些条目后续要交给其他子 Harness 继续拆分。这里只确认“交给谁”和“为什么交给它”是否正确。",
        "",
        "| 来源项 | 后续交给谁 | 为什么 | 确认结果 | 备注 |",
        "|---|---|---|---|---|",
    ])
    if downstream_routes:
        for route in downstream_routes:
            lines.append(
                f"| `{md_cell(route.get('source_item_id'))}` | {md_cell(friendly_harness_name(route.get('target_sub_harness')))} | {md_cell(route.get('reason'), 180)} | 待填写 |  |"
            )
    else:
        lines.append("| `无` |  |  |  |  |")

    lines.extend([
        "",
        "## 完成标准",
        "",
        "这份确认单可以进入下一阶段的条件：",
        "",
        "- `总确认` 四行都有明确结论。",
        "- 每个候选行的 `确认结果` 不是空白。",
        "- 所有 `改写` 都在备注里给出了改后的中文。",
        "- 所有 `暂缓` 都写清缺什么、谁确认、什么时候前确认。",
        "- 没有阻塞下一个 subharness 的未决问题。",
        "",
        "完成后，由 Harness 运行者把正式评审结论记录到候选 YAML 对应的评审记录。人工不需要在本 MD 里处理机器路径。",
        "",
        "## 运行信息",
        "",
        f"- 来源基线：`{md_cell(candidates.get('source_baseline'))}`",
        f"- 源基线批准记录：`{md_cell(candidates.get('approved_review_decision'))}`",
        f"- human_review.required：`{review.get('required')}`",
        f"- before：`{list_cell(review.get('before'))}`",
    ])
    append_core_review_evidence(lines, candidates)

    out_path = run_path(*output_rel.parts)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")

def unified_review(args):
    ensure_prd_input_or_block("unified-review")
    ensure_run_manifest("unified-review")
    output_rel = Path(args.output or "human_review/REVIEW.md")
    if output_rel.is_absolute() or ".." in output_rel.parts:
        raise SystemExit("BLOCKED: --output must be a relative path under <instance-root>/runs/<run-id>/")

    req = yload(instance_path("product-spec", "requirements.yaml"))
    screens = yload(instance_path("product-spec", "screens.yaml"))
    metrics = yload(instance_path("product-spec", "metrics.yaml"))
    events = yload(instance_path("product-spec", "events.yaml"))
    quality_summary = quality_summary_for_review()
    source_baseline, source_baseline_relpath = load_source_baseline()
    source_baseline_items = load_source_baseline_candidate_items(source_baseline, source_baseline_relpath) if source_baseline else []
    change_candidate_items = load_change_candidate_items()
    candidate_items = source_baseline_items or change_candidate_items

    requirement_items = req.get("requirement_candidates") or []
    screen_items = screens.get("screens") or []
    metric_items = metrics.get("metrics") or []
    event_items = events.get("events") or []
    unknown_candidate_items = candidate_filter(candidate_items, types={"unknown"})
    core_candidate_items = candidate_filter(candidate_items, types={"core_change"})
    risk_candidate_items = [
        item
        for item in core_candidate_items
        if any(k in f"{item.get('source_context', '')} {item.get('content', '')}" for k in ["风险", "假设", "Assumptions"])
    ]
    core_review_candidate_items = [
        item
        for item in core_candidate_items
        if item not in risk_candidate_items and "Contacts" not in str(item.get("source_context", ""))
    ]
    requirement_candidate_items = candidate_filter(candidate_items, types={"requirement_change"})
    screen_candidate_items = candidate_filter(candidate_items, types={"screen_state_change"})
    metric_event_candidate_items = candidate_filter(candidate_items, types={"metric_event_change"})
    release_candidate_items = candidate_filter(candidate_items, types={"release_ops_change"})
    candidate_count_by_harness = {}
    for item in candidate_items:
        harness = item.get("target_sub_harness_candidate") or "unknown"
        candidate_count_by_harness[harness] = candidate_count_by_harness.get(harness, 0) + 1
    candidate_count_text = "、".join(
        f"{harness}={count}" for harness, count in sorted(candidate_count_by_harness.items())
    ) or "无"

    lines = [
        "# 统一 Harness 人工评审",
        "",
        f"状态：`candidate_requires_review`  ",
        f"运行 ID：`{RUN_ID}`  ",
        f"实例根目录：`{INSTANCE_ROOT}`  ",
        f"来源 PRD：`{md_cell((source_baseline or {}).get('source_prd') or 'inputs/legacy_prd.md')}`",
        "",
        "## 0. 评审规则",
        "",
        "- YAML 文件是子 Harness 的机器可读源，用于结构校验、规则校验、质量门禁、追踪矩阵和后续自动处理。",
        "- 本 MD 是人工评审的统一入口。人工先在这里逐条审阅，再把已接受的修改回写到对应 YAML。",
        "- 本文件中的条目默认仍是 `candidate`，不是 `confirmed`；只有 `review-decision` 命令记录批准后才能提升状态。",
        "- 如果本 MD 与 YAML 不一致，YAML 仍是可运行源；不一致本身必须作为评审问题处理。",
        "- 完整旧 PRD 首次迁移必须先评审 `structured_source_baseline`；后续子 Harness 消费该基线，不重复直接读取散装源 PRD。",
        "",
        "### 0.1 统一回答格式",
        "",
        "每个评审问题建议按下面格式回答，避免只写“是 / 否”：",
        "",
        "```text",
        "结论：通过 / 需修改 / 阻塞",
        "依据：引用源 PRD、结构化 YAML、日志、埋点方案、设计稿、技术方案或人工决策。",
        "处理：保持 candidate / 回写字段 / 新增待补项 / 拆分需求 / 阻止 confirmed。",
        "回写：说明要改哪个 YAML 路径，例如 requirements.yaml#REQ-005。",
        "下游影响：说明会影响哪个后续子 Harness，例如 metrics_events_harness 或 traceability_harness。",
        "```",
        "",
        "具体评审口径、处理方式、通过标准和下游影响写在各模块开头；不要只看本节就做整体判断。",
        "",
        "### 0.2 本轮候选来源",
        "",
    ]
    if source_baseline:
        lines.extend([
            f"- 结构化源基线：`{source_baseline_relpath}`，状态 `{source_baseline.get('status')}`，候选项 `total={len(source_baseline_items)}`，{candidate_count_text}。",
            f"- 全局待确认项：`{len(source_baseline.get('open_questions') or [])}`；结构缺口：`{len(source_baseline.get('structure_gaps') or [])}`。",
            f"- 子 Harness 输入切片：`{len(source_baseline.get('sub_harness_input_slices') or [])}` 个，位于 `prd_orchestrator/source_extraction/sub_harness_inputs/`。",
            "- 本轮按首次完整 PRD 迁移处理；`change_patch_candidates/` 只作为日常变更链路兼容产物，不作为本评审主来源。",
        ])
        if change_candidate_items:
            lines.append(f"- 兼容提示：检测到旧变更候选 `total={len(change_candidate_items)}`，已被结构化源基线优先级覆盖。")
    else:
        lines.extend([
            f"- Orchestrator 候选抽取：`total={len(candidate_items)}`，{candidate_count_text}。",
            "- 下方来自 `prd_orchestrator/change_patch_candidates/` 的条目仍是候选，不是结构化事实；人工接受后必须回写到对应 YAML，再运行质量门禁。",
            "- 如果本轮是完整旧 PRD 首次迁移，请先运行 `extract-source-baseline inputs/legacy_prd.md`，不要直接用 `classify-change` 作为评审入口。",
        ])
    lines.extend([
        "",
        "## 1. 评审决策记录",
        "",
        "本章需要确认：每个子 Harness 当前是通过、需修改还是阻塞。",
        "",
        "应该怎么写：在对应行写清 `决策`、`评审人` 和 `备注`；备注必须说明依据和需要回写的 YAML。",
        "",
        "满足标准：每个子 Harness 至少有一个明确决策；如果不是通过，备注里必须写清下一步处理人、处理文件和阻塞原因。",
        "",
        "对后续子 Harness 的影响：只有通过或明确允许继续的模块，才能作为后续提升 confirmed、重跑 traceability 或进入发布门禁的依据。",
        "",
        "| 子 Harness | 决策 | 评审人 | 备注 | YAML 映射 |",
        "|---|---|---|---|---|",
        "| `prd_core_harness` | 待评审 |  |  | `product-spec/PRD.md`、`product-spec/requirements.yaml#goals/risks` |",
        "| `requirement_harness` | 待评审 |  |  | `product-spec/requirements.yaml` |",
        "| `screen_state_harness` | 待评审 |  |  | `product-spec/screens.yaml` |",
        "| `metrics_events_harness` | 待评审 |  |  | `product-spec/metrics.yaml`、`product-spec/events.yaml` |",
        "| `release_ops_harness` | 待评审 |  |  | `product-spec/release-plan.md` |",
        "| `traceability_harness` | 待评审 |  |  | `product-spec/traceability.md` |",
        "| `projection_sync_harness` | 待评审 |  |  | `product-spec/PRD.md` |",
        "",
        "## 2. 全局待确认项",
        "",
        "本章需要确认：所有跨模块开放问题是否是真实缺口，是否有目标子 Harness、owner 和解决时点。",
        "",
        "应该怎么写：对每个问题给出 `保留 / 关闭 / 转任务 / 改写`；保留时写 owner、required_before 和要回写的 YAML 字段。",
        "",
        "满足标准：不能只写“待确认”；必须说明缺什么、谁确认、确认后写到哪里。确认不了的项保持 candidate，不得写成 confirmed。",
        "",
        "对后续子 Harness 的影响：这些问题会决定哪些需求不能确认、哪些指标不能定目标、哪些页面状态或发布门禁必须继续保持 partial。",
        "",
        "| ID | 问题 | 目标子 Harness | 来源 / 影响范围 |",
        "|---|---|---|---|",
    ])

    global_question_written = False
    for item in req.get("unknowns") or []:
        lines.append(
            f"| `{md_cell(item.get('id'))}` | {md_cell(item.get('question'))} | `{md_cell(item.get('target_sub_harness'))}` | {list_cell(item.get('source_refs'))} |"
        )
        global_question_written = True
    for item in screens.get("screen_state_gaps") or []:
        lines.append(
            f"| `{md_cell(item.get('id'))}` | {md_cell(item.get('question'))} | `screen_state_harness` | {list_cell(item.get('affected_screens'))} |"
        )
        global_question_written = True
    for item in metrics.get("metric_gaps") or []:
        lines.append(
            f"| `{md_cell(item.get('id'))}` | {md_cell(item.get('question'))} | `metrics_events_harness` | {list_cell(item.get('affected_metrics'), 5)} |"
        )
        global_question_written = True
    for item in events.get("event_gaps") or []:
        lines.append(
            f"| `{md_cell(item.get('id'))}` | {md_cell(item.get('question'))} | `metrics_events_harness` | {list_cell(item.get('affected_events'), 5)} |"
        )
        global_question_written = True
    for item in (source_baseline.get("open_questions") or []) if source_baseline else []:
        lines.append(
            f"| `{md_cell(item.get('id'))}` | {md_cell(item.get('question'))} | `{md_cell(item.get('target_sub_harness'))}` | {list_cell(item.get('source_refs'))} |"
        )
        global_question_written = True
    if not global_question_written:
        for item in unknown_candidate_items:
            lines.append(
                f"| `{md_cell(item.get('change_id'))}` | {md_cell(item.get('content'), 140)} | `{md_cell(item.get('target_sub_harness_candidate'))}` | `{md_cell(candidate_mapping_cell(item))}` |"
            )
            global_question_written = True
    if not global_question_written:
        lines.append(
            "| `GLOBAL-OQ-CHECK` | 当前没有结构化待确认项；请人工确认源 PRD 是否确实没有 TBD、待定 owner、待定 baseline/target、范围缺口或状态缺口。 | `prd_core_harness` | `structured_source_baseline` / `product-spec` |"
        )

    lines.extend([
        "",
        "## 3. PRD 核心评审",
        "",
        "本章需要确认：目标、风险和范围是否忠实来自源 PRD，是否没有把后续规划、推断或非范围内容写成一期事实。",
        "",
        "应该怎么写：对每个目标/风险写 `通过 / 需修改 / 阻塞`，并引用源 PRD 章节；如果发现越界，写明要删除、降级为后续规划，还是转成开放问题。",
        "",
        "满足标准：每个目标和风险都有 source_refs；一期范围、非范围、风险边界清楚；无来源事实只能保持 candidate 或开放问题。",
        "",
        "对后续子 Harness 的影响：PRD 核心评审是后续需求、页面、指标、发布和追踪的边界；这里错了，下游会把错误范围继续扩散。",
        "",
        "| 核心项 ID | 内容 | 来源 | 人工评审问题 |",
        "|---|---|---|---|",
    ])
    for goal in req.get("goals") or []:
        lines.append(
            f"| `{md_cell(goal.get('id'))}` | {md_cell(goal.get('title'))} | {list_cell(goal.get('source_refs'))} | 是否忠实于源 PRD，且没有越过一期范围？ |"
        )
    if not req.get("goals"):
        for item in core_review_candidate_items:
            lines.append(
                f"| `{md_cell(item.get('change_id'))}` | {md_cell(item.get('content'), 120)} | `{md_cell(candidate_mapping_cell(item))}` | {md_cell(item_review_question(item, '是否应迁移为目标、范围、用户、约束或开放问题候选？'))} |"
            )
    if not req.get("goals") and not core_review_candidate_items and candidate_items:
        append_structure_gap(
            lines,
            "CORE-STRUCTURE-GAP",
            "结构化目标/范围尚未从源 PRD 迁移；需从本轮候选抽取中拆分 goals、scope、non_goals 与 risks。",
            source_baseline_relpath or "prd_orchestrator/change_patch_candidates/",
            "是否执行 prd_core_harness 迁移，并只把有源依据的内容写入 requirements.yaml？",
        )

    lines.extend([
        "",
        "### 风险",
        "",
        "| 风险 ID | 风险 | 应对 | 来源 |",
        "|---|---|---|---|",
    ])
    for risk in req.get("risks") or []:
        lines.append(
            f"| `{md_cell(risk.get('id'))}` | {md_cell(risk.get('title'))} | {md_cell(risk.get('mitigation'))} | {list_cell(risk.get('source_refs'))} |"
        )
    if not req.get("risks"):
        for item in risk_candidate_items:
            lines.append(
                f"| `{md_cell(item.get('change_id'))}` | {md_cell(item.get('content'), 110)} | 待确认 mitigation / validation | `{md_cell(candidate_mapping_cell(item))}` |"
            )
    if not req.get("risks") and not risk_candidate_items and candidate_items:
        lines.append(
            f"| `RISK-STRUCTURE-GAP` | 结构化风险尚未从源 PRD 迁移 | 从源 PRD 风险与 Assumptions 中提取，不能补未来源风险 | `{md_cell(source_baseline_relpath or 'prd_orchestrator/change_patch_candidates/')}` |"
        )

    qtext = "未运行"
    if source_baseline and not requirement_items:
        qtext = "源基线阶段暂不适用；待 requirement_harness 生成 requirements.yaml 候选后运行"
        qnote = "注意：源基线只代表提取候选覆盖，不代表需求质量通过。"
    elif quality_summary:
        qtext = f"blocked={quality_summary.get('blocked', 0)}，review_required={quality_summary.get('review_required', 0)}，passed={quality_summary.get('passed', 0)}"
        qnote = "注意：这里的 `passed` 只代表结构完整，不代表人工批准。"
    else:
        qnote = "注意：未运行质量门禁前，不得把需求候选提升为 confirmed。"
    lines.extend([
        "",
        "## 4. 需求 Harness 评审",
        "",
        "本章需要确认：每条需求是否原子、C-EARS 是否忠实，语义槽、验收、verification、数值化审核和待补项是否足够支撑后续实现与测试。",
        "",
        "应该怎么写：逐条写 `通过 / 需修改 / 阻塞`；需修改时说明要拆分、改模式、补语义槽、补验收、补量化字段，还是新增待补项。",
        "",
        "满足标准：P0/P1 需求必须有 source_refs、pattern、C-EARS、semantic_slots、acceptance、verification、quality_profile 和 quantification_review；无来源数值不能确认。",
        "",
        "对后续子 Harness 的影响：需求评审结果会驱动 screen_state_harness 的状态链、metrics_events_harness 的事件需求、test-plan 的测试覆盖和 traceability_harness 的追踪粒度。",
        "",
        f"需求质量门禁：`{qtext}`。{qnote}",
        "",
        "| 需求 ID | 标题 | 优先级 | 模式 | C-EARS | 数值化 / 量化审核 | 待补项 / 评审点 | YAML 映射 |",
        "|---|---|---:|---|---|---|---|---|",
    ])
    for item in requirement_items:
        q = item.get("quantification_review") or {}
        qdesc = q.get("decision") or q.get("status") or ""
        if qdesc == "quantified":
            qdesc = f"{qdesc}: {md_cell(q.get('target'), 80)}"
        lines.append(
            f"| `{md_cell(item.get('id'))}` | {md_cell(item.get('title'))} | {md_cell(item.get('priority'))} | `{md_cell(item.get('pattern_id'))}` | {md_cell(item.get('cn_ears'))} | {md_cell(qdesc)} | {list_cell(item.get('gaps'))} | `requirements.yaml#requirement_candidates.{md_cell(item.get('id'))}` |"
        )
    if not requirement_items:
        for item in requirement_candidate_items:
            lines.append(
                f"| `{md_cell(item.get('change_id'))}` | {md_cell(item.get('content'), 110)} | 待定 | `待选需求模式` | 待转换 C-EARS | 待量化审核 | {md_cell(item_review_question(item, '需拆分原子需求，并补齐来源、验收和验证方式'), 120)} | `{md_cell(candidate_mapping_cell(item))}` |"
            )

    lines.extend([
        "",
        "## 5. 页面 / 状态 Harness 评审",
        "",
        "本章需要确认：每个页面是否有明确目的、入口、出口、关键状态、异常状态、用户可见反馈、恢复路径和关联需求/事件。",
        "",
        "应该怎么写：对每个页面写 `通过 / 需修改 / 阻塞`；非成功状态缺反馈或恢复路径时，写明要补文案、补按钮、补状态、补事件，还是新增 screen_state_gap。",
        "",
        "满足标准：关键路径状态必须能从用户任务推到触发、系统操作、结果、页面状态、恢复路径和验收/事件；不能确定的状态保持 candidate。",
        "",
        "对后续子 Harness 的影响：页面状态会影响 requirement acceptance、events 触发时机、test-plan 用例、traceability 覆盖和 PRD.md 投影。",
        "",
        "| 页面 ID | 页面 | 目的 | 关键状态 | 关联需求 | 人工评审问题 | YAML 映射 |",
        "|---|---|---|---|---|---|---|",
    ])
    for screen in screen_items:
        state_names = [f"{st.get('id')}:{st.get('name')}" for st in screen.get("states", [])]
        lines.append(
            f"| `{md_cell(screen.get('id'))}` | {md_cell(screen.get('name'))} | {md_cell(screen.get('purpose'))} | {list_cell(state_names, 6)} | {list_cell(screen.get('related_requirements'))} | 非成功状态是否都有用户可见反馈和恢复路径？ | `screens.yaml#screens.{md_cell(screen.get('id'))}` |"
        )
    if not screen_items:
        for item in screen_candidate_items:
            lines.append(
                f"| `{md_cell(item.get('change_id'))}` | {md_cell(screen_candidate_label(item))} | {md_cell(item.get('content'), 100)} | {md_cell(screen_state_hint(item))} | 待生成 REQ 后关联 | {md_cell(item_review_question(item, '是否作为页面、状态或状态推理链候选？'))} | `{md_cell(candidate_mapping_cell(item))}` |"
            )

    lines.extend([
        "",
        "### 状态推理链",
        "",
        "| 推理链 ID | 用户任务 | 触发 | 系统操作 | 结果 | 页面状态 | 恢复路径 |",
        "|---|---|---|---|---|---|---|",
    ])
    for chain in screens.get("state_reasoning_chains") or []:
        lines.append(
            f"| `{md_cell(chain.get('id'))}` | {md_cell(chain.get('task'))} | {md_cell(chain.get('trigger'))} | {md_cell(chain.get('system_operation'))} | {md_cell(chain.get('outcome'))} | {md_cell(chain.get('state'))} | {md_cell(chain.get('recovery'))} |"
        )
    if not screens.get("state_reasoning_chains") and screen_candidate_items:
        lines.append(
            "| `STATE-STRUCTURE-GAP` | 待从页面/状态候选中提取用户任务 | 待确认触发 | 待确认系统操作 | 待确认成功/失败/降级结果 | 待映射页面状态 | 待定义恢复路径 |"
        )

    lines.extend([
        "",
        "## 6. 指标 / 事件 Harness 评审",
        "",
        "本章需要确认：指标是否真的可计算，事件是否能支撑指标公式、漏斗、失败分析、去重、分桶和跨系统对账。",
        "",
        "应该怎么写：指标和事件要分开评；指标回答口径和目标来源，事件回答触发时机和属性是否足够。缺字段时写清要补哪个事件、哪个属性、哪个外部系统。",
        "",
        "满足标准：指标不能凭空写目标；事件必须支持分子、分母、失败、重试、去重和连接键；跨会员、客服、风控或服务端日志的数据必须写清依赖。",
        "",
        "对后续子 Harness 的影响：指标/事件评审直接影响 release_ops_harness 的灰度门禁、traceability_harness 的监控链路和 projection_sync_harness 的指标说明。",
        "",
        "### 指标",
        "",
        "指标需要确认：基线、目标、公式、分子、分母、时间窗口、分层维度和数据来源是否明确。",
        "",
        "指标应该怎么写：如果没有历史数据或灰度数据，写 `保持 TBD_AFTER_BASELINE`，并补 owner、required_before 和所需事件；如果目标有来源，写明来源章节或人工决策。",
        "",
        "指标满足标准：能说明这个指标如何被算出；不能确认的基线/目标不能写成精确数值。",
        "",
        "指标对后续影响：决定发布门禁、A/B 实验判断、监控看板和回滚条件是否能成立。",
        "",
        "| 指标 ID | 指标 | 状态 | 口径 | 基线 | 目标 | 所需事件 | 人工评审问题 |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for metric in metric_items:
        data_source = metric.get("data_source") or {}
        lines.append(
            f"| `{md_cell(metric.get('id'))}` | {md_cell(metric.get('label_cn') or metric.get('name'))} | `{md_cell(metric.get('state'))}` | {md_cell(metric.get('definition'))} | {md_cell(metric.get('baseline'))} | {md_cell(metric.get('target'), 90)} | {list_cell(data_source.get('required_events'))} | 基线 / 目标是否有来源且可度量？ |"
        )
    if not metric_items:
        for item in metric_event_candidate_items:
            lines.append(
                f"| `{md_cell(item.get('change_id'))}` | {md_cell(item.get('content'), 100)} | `candidate_not_approved` | 待判断是指标、事件、实验还是埋点需求 | unknown | TBD_AFTER_BASELINE | 待倒推 | {md_cell(item_review_question(item, '是否有来源支撑基线/目标，是否需要转成事件候选？'))} |"
            )

    lines.extend([
        "",
        "### 事件",
        "",
        "事件需要确认：触发时机、必填属性、关联需求、关联指标，以及是否能支持成功/失败/取消/重试/发送等链路串联。",
        "",
        "事件应该怎么写：用指标公式倒推事件；缺少连接键、去重字段、错误码、耗时、功能模块、会员态、平台或外部系统字段时，明确写入需补属性。",
        "",
        "事件满足标准：同一业务链路能用 task_id 或等价 key 串起；关键分桶字段和错误字段存在；触发时机不会重复或漏记。",
        "",
        "事件对后续影响：决定指标是否可计算、traceability 是否能追到监控、release_ops 是否能用数据做灰度判断。",
        "",
        "| 事件 ID | 事件名 | 触发时机 | 属性 | 关联需求 | 关联指标 | 人工评审问题 |",
        "|---|---|---|---|---|---|---|",
    ])
    for event in event_items:
        lines.append(
            f"| `{md_cell(event.get('id'))}` | `{md_cell(event.get('event_name'))}` | {md_cell(event.get('trigger_timing'))} | {list_cell(event.get('properties'), 8)} | {list_cell(event.get('requirement_refs'))} | {list_cell(event.get('metric_refs'))} | 触发时机和必填属性是否足够支撑指标计算？ |"
        )
    if not event_items and metric_event_candidate_items:
        lines.append(
            "| `EVENT-STRUCTURE-GAP` | `待从指标/埋点候选提取事件` | 待确认 | 待定义连接键、去重字段、错误码、耗时、会员态等属性 | 待由 requirement_harness 生成 REQ 后关联 | 待关联指标 | 哪些候选必须写入 events.yaml 才能支撑指标计算？ |"
        )

    lines.extend([
        "",
        "## 7. 发布 / 运营 Harness 评审",
        "",
        "本章需要确认：灰度阶段、监控指标、回滚条件、运营准备、客服/FAQ、成本、隐私与合规门禁是否可执行。",
        "",
        "应该怎么写：写清发布负责人、每个阶段的进入/退出条件、监控看板、回滚阈值、客服口径和未闭合风险；不确定项写 owner 和 required_before。",
        "",
        "满足标准：发布计划不是时间表，而是可执行门禁；GA、回滚条件、客服对外口径和合规结论必须人工确认。",
        "",
        "对后续子 Harness 的影响：发布评审会消费 metrics_events_harness 的指标、traceability_harness 的监控链路，并决定 projection_sync_harness 中发布计划是否可读投影。",
        "",
        f"- 评审来源：`product-spec/release-plan.md`{('、`' + source_baseline_relpath + '`') if source_baseline_relpath else ''}。",
        "- 必须人工确认：发布负责人、阶段范围、进入/退出条件、回滚阈值、客服/FAQ、成本、隐私和合规结论。",
        "- 候选灰度链路和全量门禁必须来自源 PRD、结构化基线、指标事件方案或人工评审决策；不能沿用其他 PRD 的默认值。",
        "",
        "| 发布候选 ID | 内容 | 候选来源 | 人工评审问题 |",
        "|---|---|---|---|",
    ])
    for item in release_candidate_items:
        lines.append(
            f"| `{md_cell(item.get('change_id'))}` | {md_cell(item.get('content'), 120)} | `{md_cell(candidate_mapping_cell(item))}` | {md_cell(item_review_question(item, '是否需要写入发布计划、监控门禁、回滚条件或运营准备？'))} |"
        )
    if not release_candidate_items:
        lines.append(
            "| `REL-STRUCTURE-GAP` | 暂无 release_ops_change 候选；仍需人工确认发布负责人、回滚阈值、客服/FAQ 与合规门禁 | `product-spec/release-plan.md` | 是否需要补充 release_ops_harness 候选？ |"
        )

    impact_summaries = []
    for impact_path in sorted(run_path("prd_orchestrator", "impact_analysis").glob("*.yaml")):
        impact = yload(impact_path).get("impact_analysis", {})
        if impact:
            impact_summaries.append((impact_path, impact))
    rerun_summaries = []
    for plan_path in sorted(run_path("prd_orchestrator", "partial_rerun_plans").glob("*.yaml")):
        plan = yload(plan_path).get("partial_rerun_plan", {})
        if plan:
            rerun_summaries.append((plan_path, plan))
    if source_baseline:
        impact_summaries = []
        rerun_summaries = []

    lines.extend([
        "",
        "## 8. 可追踪性 Harness 评审",
        "",
        "本章需要确认：目标、需求、页面、事件、测试、监控之间是否能追通，partial/uncovered 是否是真实待补项。",
        "",
        "应该怎么写：对每个 partial 写清断在哪里、为什么断、由谁补、补到哪个 YAML；如果断点影响 P0 上线，标为阻塞。",
        "",
        "满足标准：P0 需求至少能追到关键 screen/event/test/monitoring；非 covered 状态必须有原因、owner 和 required_before。",
        "",
        "对后续子 Harness 的影响：traceability 决定局部重跑范围；任何 requirement、screen、event、metric、release 变更都要通过这里判断影响面。",
        "",
        f"- 评审来源：`product-spec/traceability.md`{('、`' + source_baseline_relpath + '`') if source_baseline_relpath else ''}。",
        "- 当前覆盖摘要：待由 traceability_harness 基于已评审的 structured_source_baseline 和 product-spec 候选生成。",
        "- 评审重点：不要把旧 run 的 impact/rerun 当成首次迁移结论；每个 partial 行都要能追到当前基线或评审决策。",
        "",
        "| 追踪/影响项 ID | 类型 | 影响范围 | 人工评审问题 |",
        "|---|---|---|---|",
    ])
    for impact_path, impact in impact_summaries:
        lines.append(
            f"| `{md_cell(impact.get('patch_id'))}` | impact_analysis | {list_cell(impact.get('affected_sub_harnesses'), 8)} | 是否同意这些子 harness 进入局部重跑？来源：`{md_cell(artifact_relpath(impact_path))}` |"
        )
    for plan_path, plan in rerun_summaries:
        lines.append(
            f"| `{md_cell(plan.get('plan_id'))}` | partial_rerun_plan | {list_cell(plan.get('rerun_sub_harnesses'), 8)} | 是否批准该 rerun plan？来源：`{md_cell(artifact_relpath(plan_path))}` |"
        )
    if not impact_summaries and not rerun_summaries:
        if source_baseline:
            lines.append(
                f"| `TRACE-SOURCE-BASELINE` | source_baseline 待消费 | `{md_cell(source_baseline_relpath)}` | 是否批准 traceability_harness 在基线评审后生成覆盖矩阵和局部重跑范围？ |"
            )
        else:
            lines.append(
                "| `TRACE-STRUCTURE-GAP` | impact/rerun 缺口 | 待运行 impact 与 rerun-plan | 是否需要先生成影响分析和局部重跑计划？ |"
            )

    lines.extend([
        "",
        "## 9. PRD 投影同步评审",
        "",
        "本章需要确认：`PRD.md` 是否只是 YAML 和源 PRD 的可读投影，没有新增机器源里不存在的 confirmed fact。",
        "",
        "应该怎么写：发现 PRD.md 中有新增事实时，说明要回写到哪个 YAML；如果只是表达问题，改 PRD.md 后也要同步 YAML 或记录同步问题。",
        "",
        "满足标准：关键事实能回到 `requirements.yaml`、`screens.yaml`、`metrics.yaml`、`events.yaml`、`traceability.md`、源 PRD 或评审决策。",
        "",
        "对后续子 Harness 的影响：投影同步防止人工文档和机器源分叉；如果只改 PRD.md，下一次投影或校验会丢失人工修改。",
        "",
        f"- 评审来源：`product-spec/PRD.md`{('、`' + source_baseline_relpath + '`') if source_baseline_relpath else ''}。",
        "- `PRD.md` 是可读投影，不是校验器的事实源。",
        "- 人工接受的 PRD.md 修改必须回写 YAML，否则下一次投影会丢失。",
        "",
        "## 10. 评审后回写规则",
        "",
        "- 修改 requirement 行：回写 `product-spec/requirements.yaml`。",
        "- 修改 screen/state 行：回写 `product-spec/screens.yaml`。",
        "- 修改 metric/event 行：回写 `product-spec/metrics.yaml` 或 `product-spec/events.yaml`。",
        "- 修改 release 决策：回写 `product-spec/release-plan.md`，必要时同步相关 requirement IDs。",
        "- 修改 trace 行：回写 `product-spec/traceability.md`。",
        "- 回写后必须重新运行校验器 / 质量门禁，再通过 `review-decision` 记录人工决策。",
        "",
        "## 11. 建议复核命令",
        "",
        "```bash",
        f"python3 prd_subharness_v2_0/scripts/prd_control/harnessctl.py --instance-root {INSTANCE_ROOT} --run-id {RUN_ID} extract-source-baseline inputs/legacy_prd.md",
        f"python3 prd_subharness_v2_0/scripts/prd_control/harnessctl.py --instance-root {INSTANCE_ROOT} --run-id {RUN_ID} quality-gate",
        f"python3 prd_subharness_v2_0/scripts/prd_control/harnessctl.py --instance-root {INSTANCE_ROOT} --run-id {RUN_ID} validate-prd-template",
        f"python3 prd_subharness_v2_0/scripts/prd_control/harnessctl.py --instance-root {INSTANCE_ROOT} --run-id {RUN_ID} check-prd-sync",
        "```",
    ])

    out_path = run_path(*output_rel.parts)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")

def normalize_decision(value: str) -> str:
    mapping = {
        "approve": "approved",
        "approved": "approved",
        "reject": "rejected",
        "rejected": "rejected",
        "request-changes": "changes_requested",
        "changes-requested": "changes_requested",
        "changes_requested": "changes_requested",
    }
    return mapping[value]

def review_decision(args):
    ensure_run_manifest("review-decision")
    artifact = resolve_run_artifact(args.artifact)
    data = yload(artifact) if artifact.suffix.lower() in [".yaml", ".yml"] else {}
    decision = normalize_decision(args.decision)
    decision_id = args.decision_id or f"{RUN_ID}-{safe_slug(artifact.stem)}-{decision}-{utc_slug_text()}"
    out_path = decision_path_by_id(decision_id)
    if out_path.exists() and not args.force:
        raise SystemExit(f"BLOCKED: review decision already exists: {display_path(out_path)}")

    record = {
        "decision_id": out_path.stem,
        "run_id": RUN_ID,
        "artifact_path": display_path(artifact),
        "artifact_relpath": artifact_relpath(artifact),
        "artifact_type": args.artifact_type or infer_artifact_type(artifact),
        "artifact_sha256": sha256_file(artifact),
        "sub_harness": args.sub_harness or infer_sub_harness(artifact, data),
        "decision": decision,
        "reviewer": args.reviewer,
        "reviewed_at": utc_now_text(),
        "notes": args.notes or "",
        "promote_allowed": decision == "approved",
        "promotion_policy": {
            "default_target_root": f"outputs/approved_artifacts/{RUN_ID}/",
            "write_product_spec_requires_explicit_flag": True,
        },
    }
    ywrite(out_path, {"review_decision": record})
    print(f"Wrote {out_path}")
    print(json.dumps({"decision_id": record["decision_id"], "decision": decision}, ensure_ascii=False, indent=2))

def promote_approved(args):
    ensure_run_manifest("promote-approved")
    artifact = resolve_run_artifact(args.artifact)
    rel = artifact_relpath(artifact)
    digest = sha256_file(artifact)

    if args.decision_id:
        decision_path = decision_path_by_id(args.decision_id)
        if not decision_path.exists():
            raise SystemExit(f"BLOCKED: review decision not found: {args.decision_id}")
        decision = load_review_decision(decision_path)
    else:
        decision_path, decision = find_approved_decision(artifact)
        if decision_path is None:
            raise SystemExit("BLOCKED: no approved review decision matches this artifact and sha256")

    if decision.get("decision") != "approved":
        raise SystemExit("BLOCKED: artifact can only be promoted after an approved review decision")
    if decision.get("artifact_relpath") != rel or decision.get("artifact_sha256") != digest:
        raise SystemExit("BLOCKED: review decision does not match the current artifact path and sha256")

    if args.target:
        target_rel = Path(args.target)
        if target_rel.is_absolute() or ".." in target_rel.parts:
            raise SystemExit("BLOCKED: --target must be a relative path inside the PRD instance")
    else:
        target_rel = Path("outputs") / "approved_artifacts" / RUN_ID / Path(rel)

    if not target_rel.parts or target_rel.parts[0] not in {"outputs", "product-spec"}:
        raise SystemExit("BLOCKED: promotion target must be under outputs/ or product-spec/")
    if target_rel.parts[0] == "product-spec" and not args.write_product_spec:
        raise SystemExit("BLOCKED: writing product-spec requires --write-product-spec and explicit reviewer approval")

    target = (INSTANCE_ROOT / target_rel).resolve()
    if not path_is_within(target, INSTANCE_ROOT):
        raise SystemExit("BLOCKED: promotion target escaped instance root")
    if target.exists() and not args.force:
        raise SystemExit(f"BLOCKED: promotion target already exists: {display_path(target)}")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artifact, target)
    decision["promotion"] = {
        "status": "promoted",
        "target_path": display_path(target),
        "target_relpath": target.relative_to(INSTANCE_ROOT).as_posix(),
        "promoted_by": args.promoter or decision.get("reviewer"),
        "promoted_at": utc_now_text(),
        "source_artifact_sha256": digest,
        "writes_product_spec": target_rel.parts[0] == "product-spec",
    }
    ywrite(decision_path, {"review_decision": decision})
    print(f"Promoted {artifact} -> {target}")

def validate_fixtures(args):
    try:
        from jsonschema import Draft202012Validator
    except Exception as exc:
        raise RuntimeError("Install jsonschema: pip install jsonschema") from exc

    issues = []
    summary = {
        "schemas": 0,
        "negative_fixtures": 0,
        "semantic_checks": 0,
    }

    for schema_path in sorted(harness_path("schemas").glob("*.schema.json")):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        summary["schemas"] += 1

    def require(condition: bool, fixture_id: str, message: str):
        summary["semantic_checks"] += 1
        if not condition:
            issues.append(f"{fixture_id}: {message}")

    for fixture_path in sorted(harness_path("fixtures", "negative").glob("*.yaml")):
        data = yload(fixture_path)
        fixture_id = data.get("fixture_id")
        expected = data.get("expected_result")
        summary["negative_fixtures"] += 1
        if not fixture_id:
            issues.append(f"{fixture_path}: missing fixture_id")
            continue
        if expected not in {"blocked", "review_required", "review_required_or_blocked"}:
            issues.append(f"{fixture_path}: invalid expected_result={expected}")
        if not data.get("reason"):
            issues.append(f"{fixture_path}: missing reason")

        if fixture_id == "syntax_pass_quality_fail":
            bad = data.get("bad_requirement") or {}
            require(bool(bad.get("cn_ears")), fixture_id, "bad requirement must include C-EARS text")
            require(not bad.get("acceptance"), fixture_id, "bad requirement should lack acceptance")
            require(not bad.get("quality_profile"), fixture_id, "bad requirement should lack quality_profile")
        elif fixture_id in {"prd_title_only", "prd_title_only_false_pass"}:
            bad_prd = data.get("bad_prd") or {}
            content = bad_prd.get("content") or "\n".join(bad_prd.get("sections") or [])
            non_heading_lines = [
                line.strip()
                for line in str(content).splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            require(len(non_heading_lines) == 0 or "only headings" in str(content), fixture_id, "fixture must represent a title-only PRD")
        elif fixture_id == "unknown_as_confirmed":
            bad = data.get("bad_requirement") or {}
            require(bad.get("status") in {"confirmed", "approved"}, fixture_id, "bad requirement must be confirmed/approved")
            require(bad.get("evidence_status") in {"assumed", "missing", "candidate"}, fixture_id, "bad requirement must have non-confirmed evidence")
            require(not bad.get("source_refs"), fixture_id, "bad requirement should lack source_refs")
        elif fixture_id == "metric_target_invented":
            bad = data.get("bad_metric") or {}
            baseline = bad.get("baseline") or {}
            target = bad.get("target") or {}
            baseline_value = baseline.get("value") if isinstance(baseline, dict) else baseline
            target_value = target.get("value") if isinstance(target, dict) else target
            require(str(baseline_value).lower() == "unknown", fixture_id, "baseline must be unknown")
            require(target_value not in {"TBD_AFTER_BASELINE", None, ""}, fixture_id, "target must be an invented concrete value")
        elif fixture_id == "state_list_without_reasoning_chain":
            bad = data.get("bad_screen") or {}
            require(bool(bad.get("states")), fixture_id, "bad screen must list states")
            require(not bad.get("state_reasoning_chains"), fixture_id, "bad screen should lack reasoning chains")

    print(json.dumps({"fixture_validation_summary": summary}, ensure_ascii=False, indent=2))
    if issues:
        print("\nBLOCKED: fixture issues")
        for issue in issues:
            print(f"- {issue}")
        raise SystemExit(1)
    print("\nPASS: schemas and negative fixtures are structurally valid and semantically targeted")

def validate_rule_specs(args):
    required_validator_keys = {
        "id",
        "severity",
        "natural_language",
        "applies_to",
        "machine_rule",
        "human_review",
    }
    issues = []
    summary = {}
    known_yaml_ids = set()

    def normalize_validators(validators_path: Path, data: dict):
        raw = data.get("validators") or []
        normalized = []
        groups = []
        if isinstance(raw, list):
            for idx, item in enumerate(raw):
                if not isinstance(item, dict):
                    issues.append(f"{validators_path}: validators[{idx}] must be an object")
                    continue
                normalized.append(item)
            return normalized, groups
        if isinstance(raw, dict):
            for group, items in raw.items():
                groups.append(group)
                if not isinstance(items, list):
                    issues.append(f"{validators_path}: validators.{group} must be a list")
                    continue
                for idx, item in enumerate(items):
                    if not isinstance(item, dict):
                        issues.append(f"{validators_path}: validators.{group}[{idx}] must be an object")
                        continue
                    item = dict(item)
                    item.setdefault("stage", group.replace("_validators", ""))
                    item["_validator_group"] = group
                    normalized.append(item)
            return normalized, groups
        issues.append(f"{validators_path}: validators must be a list or grouped mapping")
        return normalized, groups

    def collect_rule_ids(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {
                    "id",
                    "rule_id",
                    "step_id",
                    "pattern_id",
                    "validator_id",
                    "adapter_id",
                    "library_id",
                    "mode",
                    "profile_id",
                    "contract_id",
                } and isinstance(value, str):
                    known_yaml_ids.add(value)
                collect_rule_ids(value)
        elif isinstance(node, list):
            for value in node:
                collect_rule_ids(value)

    def is_internal_rule_asset(path: Path) -> bool:
        if path.name in {"validators.yaml", "harness_contract.yaml"}:
            return False
        rel_parts = path.relative_to(HARNESS_ROOT).parts
        return "figma-sds" not in rel_parts

    def harness_rule_files(harness_dir: Path) -> list[Path]:
        candidates = []
        for pattern in ("*.yaml", "*.yml"):
            candidates.extend(harness_dir.rglob(pattern))
        return sorted(p for p in candidates if is_internal_rule_asset(p))

    for harness_dir in sorted(harness_path("sub_harnesses").glob("*_harness")):
        if not harness_dir.is_dir():
            continue
        harness_id = harness_dir.name
        contract_path = harness_dir / "harness_contract.yaml"
        contract = yload(contract_path).get("harness_contract", {})
        collect_rule_ids(contract)
        review_stage = contract.get("run_lifecycle", {}).get("human_review_stage", {})
        if review_stage.get("required") is not True:
            issues.append(f"{contract_path}: missing required human_review_stage")
        if not review_stage.get("review_artifacts"):
            issues.append(f"{contract_path}: missing human_review_stage.review_artifacts")
        if not review_stage.get("approval_required_before"):
            issues.append(f"{contract_path}: missing human_review_stage.approval_required_before")
        validators_path = harness_dir / "validators.yaml"
        data = yload(validators_path)
        validators, validator_groups = normalize_validators(validators_path, data)
        grouped_validators = bool(validator_groups)
        allowed_specs = {"2.0", "2.1"} if grouped_validators else {"1.0"}
        if data.get("validator_spec_version") not in allowed_specs:
            allowed_text = " or ".join(sorted(allowed_specs))
            issues.append(f"{validators_path}: missing validator_spec_version={allowed_text}")
        if grouped_validators and not data.get("validator_group_spec"):
            issues.append(f"{validators_path}: grouped validators missing validator_group_spec")
        if data.get("review_status") != "approved_by_human_review":
            issues.append(f"{validators_path}: missing review_status=approved_by_human_review")
        if not data.get("intent"):
            issues.append(f"{validators_path}: missing intent")
        if not validators:
            issues.append(f"{validators_path}: validators list is empty")
        for item in validators:
            missing = sorted(required_validator_keys - set(item))
            if missing:
                issues.append(f"{validators_path}: {item.get('id', 'UNKNOWN')} missing {', '.join(missing)}")
            if grouped_validators and not item.get("stage"):
                issues.append(f"{validators_path}: {item.get('id', 'UNKNOWN')} missing stage")
            if not item.get("human_review", {}).get("reviewer_prompt"):
                issues.append(f"{validators_path}: {item.get('id', 'UNKNOWN')} missing human_review.reviewer_prompt")
            if not item.get("human_review", {}).get("evidence"):
                issues.append(f"{validators_path}: {item.get('id', 'UNKNOWN')} missing human_review.evidence")
            machine_rule = item.get("machine_rule", {})
            if not machine_rule.get("check_type"):
                issues.append(f"{validators_path}: {item.get('id', 'UNKNOWN')} missing machine_rule.check_type")
            if not machine_rule.get("pass_when"):
                issues.append(f"{validators_path}: {item.get('id', 'UNKNOWN')} missing machine_rule.pass_when")
            if not machine_rule.get("fail_when"):
                issues.append(f"{validators_path}: {item.get('id', 'UNKNOWN')} missing machine_rule.fail_when")

        rule_files = harness_rule_files(harness_dir)
        detailed_rule_items = 0

        def require_rule_fields(path, item, fields, item_label):
            for field in fields:
                current = item
                for part in field.split("."):
                    current = current.get(part) if isinstance(current, dict) else None
                if not current:
                    issues.append(f"{path}: {item_label} missing {field}")

        def inspect_rule_node(path, node):
            nonlocal detailed_rule_items
            if isinstance(node, dict):
                patch_contract = node.get("patch_contract")
                if isinstance(patch_contract, dict):
                    detailed_rule_items += 1
                    label = patch_contract.get("id") or patch_contract.get("patch_id") or "UNKNOWN_PATCH_CONTRACT"
                    if patch_contract.get("schema_version") in {"2.0", "2.1"}:
                        require_rule_fields(path, patch_contract, ["id", "name", "owner"], label)
                    else:
                        require_rule_fields(path, patch_contract, ["patch_id", "title"], label)
                for key in ["rule_mappings", "review_rules"]:
                    for rule in node.get(key) or []:
                        detailed_rule_items += 1
                        label = rule.get("rule_id", "UNKNOWN_RULE")
                        require_rule_fields(
                            path,
                            rule,
                            ["rule_id", "natural_language", "machine_mapping.check_type", "human_review_prompt"],
                            label,
                        )
                for step in node.get("transformation_pipeline") or []:
                    detailed_rule_items += 1
                    label = step.get("step_id", "UNKNOWN_STEP")
                    require_rule_fields(
                        path,
                        step,
                        ["step_id", "name", "natural_language", "machine_mapping.output_fields", "human_review_prompt"],
                        label,
                    )
                for rule in node.get("pattern_selection_rules") or []:
                    detailed_rule_items += 1
                    label = rule.get("pattern_id", "UNKNOWN_PATTERN")
                    require_rule_fields(
                        path,
                        rule,
                        ["pattern_id", "when_to_use", "conversion_rule", "conversion_explanation", "review_risk"],
                        label,
                    )
                for rule in node.get("reasoning_completion_rules") or []:
                    detailed_rule_items += 1
                    label = rule.get("rule_id", "UNKNOWN_INFERENCE_RULE")
                    require_rule_fields(
                        path,
                        rule,
                        [
                            "rule_id",
                            "name",
                            "natural_language",
                            "allowed_inputs",
                            "output_fields",
                            "pass_condition",
                            "fail_condition",
                            "human_review_prompt",
                        ],
                        label,
                    )
                for step in node.get("generation_pipeline") or []:
                    detailed_rule_items += 1
                    label = step.get("step", "UNKNOWN_PROTOTYPE_STEP") if isinstance(step, dict) else "UNKNOWN_PROTOTYPE_STEP"
                    if isinstance(step, dict):
                        require_rule_fields(path, step, ["step"], label)
                        if not step.get("rule") and not step.get("output") and not step.get("inputs"):
                            issues.append(f"{path}: {label} missing rule, output, or inputs")
                for rule in node.get("priority_order") or []:
                    if isinstance(rule, dict):
                        detailed_rule_items += 1
                        label = rule.get("id", "UNKNOWN_PRIORITY_RULE")
                        require_rule_fields(path, rule, ["id", "rule"], label)
                for key in ["classification_rules", "target_harness_routing", "frame_rules", "update_policy", "node_metadata", "gap_projection", "source_resolution", "destination_resolution", "trigger_policy", "action_order_policy", "conditional_policy", "overlay_policy", "multi_state_policy", "annotation_policy", "reverse_sync_policy", "three_way_diff", "merge_rules", "approval_gate"]:
                    if key in node:
                        detailed_rule_items += 1
                for value in node.values():
                    inspect_rule_node(path, value)
            elif isinstance(node, list):
                for value in node:
                    inspect_rule_node(path, value)

        for path in rule_files:
            rule_data = yload(path)
            collect_rule_ids(rule_data)
            inspect_rule_node(path, rule_data)
        collect_rule_ids(data)
        if detailed_rule_items == 0:
            issues.append(f"{harness_dir}: no detailed rule_mappings/review_rules/transformation rules found")
        summary[harness_id] = {
            "validators": len(validators),
            "validator_groups": validator_groups,
            "review_status": data.get("review_status"),
            "rule_files": len(rule_files),
            "detailed_rule_items": detailed_rule_items,
            "has_rule_mapping": detailed_rule_items > 0,
            "human_review_stage": bool(review_stage.get("required")),
        }

    for extra_asset in [
        harness_path("product-spec", "component-binding-map.yaml"),
        harness_path("product-spec", "design-semantic-library.json"),
        harness_path("prd_orchestrator", "patch_control_v2.yaml"),
        harness_path("prd_orchestrator", "automation_policy.yaml"),
        harness_path("prd_orchestrator", "document_registry.yaml"),
    ]:
        if extra_asset.exists():
            collect_rule_ids(yload(extra_asset))

    review_doc = harness_path("prd_orchestrator", "HARNESS_RULE_REVIEW.md")
    crosswalk_path = harness_path("prd_orchestrator", "harness_rule_review_crosswalk.yaml")
    crosswalk = yload(crosswalk_path).get("harness_rule_review_crosswalk", {})
    review_text = review_doc.read_text(encoding="utf-8") if review_doc.exists() else ""
    review_gen_ids = set(re.findall(r"`([A-Z]+-GEN-\d{3}[A-Z]?)`", review_text))
    crosswalk_mappings = crosswalk.get("mappings") or []
    mapped_gen_ids = {m.get("rule_id") for m in crosswalk_mappings if m.get("rule_id")}
    if crosswalk.get("review_status") != "approved_by_human_review":
        issues.append(f"{crosswalk_path}: missing review_status=approved_by_human_review")
    if review_gen_ids - mapped_gen_ids:
        issues.append(f"{crosswalk_path}: missing GEN mappings for {', '.join(sorted(review_gen_ids - mapped_gen_ids))}")
    if mapped_gen_ids - review_gen_ids:
        issues.append(f"{crosswalk_path}: mappings not present in review doc: {', '.join(sorted(mapped_gen_ids - review_gen_ids))}")
    for mapping in crosswalk_mappings:
        rule_id = mapping.get("rule_id", "UNKNOWN_GEN_RULE")
        if not mapping.get("harness_id") or not mapping.get("review_section"):
            issues.append(f"{crosswalk_path}: {rule_id} missing harness_id or review_section")
        if not mapping.get("maps_to"):
            issues.append(f"{crosswalk_path}: {rule_id} missing maps_to")
        for target in mapping.get("maps_to") or []:
            target_file = target.get("file")
            target_ids = target.get("ids") or []
            if not target_file:
                issues.append(f"{crosswalk_path}: {rule_id} has maps_to without file")
                continue
            target_path = harness_path(target_file)
            if not target_path.exists():
                issues.append(f"{crosswalk_path}: {rule_id} target file not found: {target_file}")
            for target_id in target_ids:
                if target_id not in known_yaml_ids:
                    issues.append(f"{crosswalk_path}: {rule_id} target id not found in YAML assets: {target_id}")
    summary["_review_crosswalk"] = {
        "review_status": crosswalk.get("review_status"),
        "gen_rules_in_review_doc": len(review_gen_ids),
        "mapped_gen_rules": len(mapped_gen_ids),
        "known_yaml_ids": len(known_yaml_ids),
    }

    print(json.dumps({"rule_spec_summary": summary}, ensure_ascii=False, indent=2))
    if issues:
        print("\nBLOCKED: rule spec issues")
        for issue in issues:
            print(f"- {issue}")
        raise SystemExit(1)
    print("\nPASS: all sub-harness rule specs include granular natural-language and machine-rule mappings")

def init_instance(args):
    target = resolve_cli_path(args.instance_root)
    if path_is_within(target, HARNESS_ROOT) and not args.force:
        raise SystemExit("BLOCKED: instance root must be outside the harness package unless --force is provided")

    dirs = [
        "inputs/change_requests",
        "inputs/references",
        "product-spec",
        "prd_orchestrator/review_decisions",
        "prd_orchestrator/open_questions",
        "prd_orchestrator/tombstones",
        "runs",
        "outputs/approved_artifacts",
        "outputs/approved_prd",
        "outputs/export",
    ]
    for d in dirs:
        (target / d).mkdir(parents=True, exist_ok=True)

    product_src = harness_path("product-spec")
    product_dst = target / "product-spec"
    for src in product_src.rglob("*"):
        if src.is_file():
            dst = product_dst / src.relative_to(product_src)
            if dst.exists() and not args.force:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    instance_id = args.instance_id or target.name
    manifest = {
        "prd_instance": {
            "instance_id": instance_id,
            "status": "draft",
            "harness_root": str(HARNESS_ROOT),
            "product_spec_root": "product-spec",
            "input_root": "inputs",
            "run_root": "runs",
            "output_root": "outputs",
            "review_policy": {
                "human_review_required_before_confirmed": True,
                "review_decisions_path": "prd_orchestrator/review_decisions",
                "runtime_outputs_are_not_source_of_truth": True,
            },
        }
    }
    ywrite(target / "instance.yaml", manifest)
    print(f"Initialized PRD instance at {target}")

def run_prd_loop(args):
    ensure_instance_write_allowed("run-prd-loop")
    state = prd_run_state()
    print(json.dumps({"prd_run_loop_state": state}, ensure_ascii=False, indent=2))

    baseline_path = current_source_baseline_path()
    if not baseline_path.exists():
        source = resolve_input_path(args.source) if args.source else None
        if source is None:
            inputs = discover_prd_input_files()
            if len(inputs) == 1:
                source = inputs[0]
            elif len(inputs) > 1:
                raise SystemExit(
                    "BLOCKED: multiple PRD inputs found. Re-run with --source and choose one: "
                    + ", ".join(str(path.relative_to(INSTANCE_ROOT)) for path in inputs)
                )
        if source is None or not source.exists() or not text_file_has_content(source):
            out = write_stop_report(
                stage="prd_input",
                reason="No real PRD input was found for this run.",
                required_next_action="Place a source PRD markdown file under <instance-root>/inputs/ and rerun run-prd-loop --source inputs/<file>.md.",
                resume_condition="discover_prd_input_files returns exactly one selected non-empty source PRD file.",
                sub_harness="prd_orchestrator",
            )
            raise SystemExit(f"{prd_input_blocker('run-prd-loop')}\nWrote stop-the-line report: {display_path(out)}")
        args.markdown = str(source)
        extract_source_baseline(args)
        out = write_stop_report(
            stage="source_extraction_review",
            reason="Source extraction was generated and requires human review before downstream harness stages.",
            required_next_action=f"Review and approve `{artifact_relpath(current_source_baseline_path())}` with review-decision.",
            resume_condition="An approved review_decision exists for the structured_source_baseline artifact and matching sha256.",
            sub_harness="prd_orchestrator",
            source_artifacts=[artifact_relpath(current_source_baseline_path())],
        )
        raise SystemExit(
            f"BLOCKED: source extraction was generated and now requires human review before downstream harness stages.\n"
            f"Wrote stop-the-line report: {display_path(out)}"
        )

    approved_path, _decision = find_approved_decision(baseline_path)
    if not approved_path:
        out = write_stop_report(
            stage="source_extraction_review",
            reason="Structured source baseline exists but has no approved review decision.",
            required_next_action=f"Review and approve `{artifact_relpath(baseline_path)}` with review-decision.",
            resume_condition="find_approved_decision(structured_source_baseline) returns a matching approved decision.",
            sub_harness="prd_orchestrator",
            source_artifacts=[artifact_relpath(baseline_path)],
        )
        raise SystemExit(
            "BLOCKED: source baseline exists but is not approved. "
            f"Review and approve `{artifact_relpath(baseline_path)}` before continuing the loop.\n"
            f"Wrote stop-the-line report: {display_path(out)}"
        )

    if not has_product_spec_material():
        out = write_stop_report(
            stage="downstream_fact_generation",
            reason="Approved source baseline exists, but requirement/screen generation has not produced product-spec material.",
            required_next_action="Run the downstream requirement_harness and screen_state_harness generators before quality-gate.",
            resume_condition="product-spec/requirements.yaml or product-spec/screens.yaml contains generated candidate material.",
            sub_harness="prd_orchestrator",
            source_artifacts=[artifact_relpath(baseline_path), approved_path.relative_to(INSTANCE_ROOT).as_posix()],
        )
        raise SystemExit(
            "BLOCKED: approved source baseline exists, but requirement/screen generation has not produced product-spec material. "
            "This is the current downstream generation breakpoint.\n"
            f"Wrote stop-the-line report: {display_path(out)}"
        )

    out = write_stop_report(
        stage="prototype_runtime_generation",
        reason="Product-spec has material, but prototype runtime/render payload generation loop is not implemented yet.",
        required_next_action="Implement and run prototype runtime plus render payload generation before Figma materialization.",
        resume_condition="validate-render-readiness passes with a non-empty runtime and render payload.",
        sub_harness="prototype_projection_harness",
    )
    raise SystemExit(
        "BLOCKED: product-spec has material, but prototype runtime/render payload generation loop is not implemented yet.\n"
        f"Wrote stop-the-line report: {display_path(out)}"
    )

def search(args):
    q = args.query
    search_roots = [
        instance_path("product-spec"),
        instance_path("prd_orchestrator"),
        run_path("prd_orchestrator"),
        run_path("sub_harnesses"),
        harness_path("prd_orchestrator"),
        harness_path("sub_harnesses"),
    ]
    for root in search_roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in [".md", ".yaml", ".yml", ".json"]:
                try:
                    if q in p.read_text(encoding="utf-8"):
                        print(display_path(p))
                except Exception:
                    pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness-root", default=str(DEFAULT_HARNESS_ROOT), help="Read-only harness package root")
    ap.add_argument("--instance-root", help="Isolated PRD instance root for product-spec, inputs, outputs, and runs")
    ap.add_argument("--run-id", default="manual", help="Run id under <instance-root>/runs")
    ap.add_argument("--allow-harness-writes", action="store_true", help=argparse.SUPPRESS)
    sub = ap.add_subparsers(required=True)
    for name, func in [
        ("status", status),
        ("validate-prd-template", validate_prd_template),
        ("check-prd-sync", check_prd_sync),
        ("preflight-prd-run", preflight_prd_run),
        ("quality-gate", quality_gate),
        ("validate-rule-specs", validate_rule_specs),
        ("validate-fixtures", validate_fixtures),
    ]:
        p = sub.add_parser(name)
        p.set_defaults(func=func)

    p = sub.add_parser("route-change")
    p.add_argument("markdown")
    p.set_defaults(func=route_change)

    p = sub.add_parser("classify-change")
    p.add_argument("markdown")
    p.set_defaults(func=classify_change)

    p = sub.add_parser("extract-source-baseline")
    p.add_argument("markdown")
    p.set_defaults(func=extract_source_baseline)

    p = sub.add_parser("impact")
    p.add_argument("patch_id")
    p.set_defaults(func=impact)

    p = sub.add_parser("rerun-plan")
    p.add_argument("patch_id")
    p.set_defaults(func=rerun_plan)

    p = sub.add_parser("unified-review")
    p.add_argument("--output", default="human_review/REVIEW.md", help="Run-relative Markdown output path")
    p.set_defaults(func=unified_review)

    p = sub.add_parser("core-review-md")
    p.add_argument("--candidates", default=str(CORE_FACT_CANDIDATES_REL), help="Run-relative CORE-000 candidate YAML path")
    p.add_argument("--output", default=str(CORE_REVIEW_MD_REL), help="Run-relative Markdown output path")
    p.set_defaults(func=core_review_md)

    p = sub.add_parser("review-decision")
    p.add_argument("artifact", help="Run artifact path relative to <instance-root>/runs/<run-id>")
    p.add_argument(
        "--decision",
        required=True,
        choices=["approve", "approved", "reject", "rejected", "request-changes", "changes-requested", "changes_requested"],
    )
    p.add_argument("--reviewer", required=True)
    p.add_argument("--notes", default="")
    p.add_argument("--artifact-type")
    p.add_argument("--sub-harness")
    p.add_argument("--decision-id")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=review_decision)

    p = sub.add_parser("promote-approved")
    p.add_argument("artifact", help="Run artifact path relative to <instance-root>/runs/<run-id>")
    p.add_argument("--decision-id")
    p.add_argument("--target", help="Relative target under outputs/ or product-spec/")
    p.add_argument("--write-product-spec", action="store_true")
    p.add_argument("--promoter")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=promote_approved)

    p = sub.add_parser("write-patch-report")
    p.add_argument("--patch-id")
    p.add_argument("--summary", required=True)
    p.add_argument("--root-cause", required=True)
    p.add_argument("--status", choices=["candidate", "applied", "blocked", "changes_requested", "superseded"], default="candidate")
    p.add_argument("--sub-harness", default="orchestrator")
    p.add_argument("--source-artifact", action="append")
    p.add_argument("--changed-file", action="append", required=True)
    p.add_argument("--validation", action="append", required=True)
    p.add_argument("--remaining-gap", action="append")
    p.add_argument("--stop-the-line-ref", action="append")
    p.add_argument("--output")
    p.set_defaults(func=write_patch_report)

    p = sub.add_parser("validate-patch-report")
    p.add_argument("artifact", help="Run artifact path relative to <instance-root>/runs/<run-id>")
    p.set_defaults(func=validate_patch_report)

    p = sub.add_parser("stop-the-line")
    p.add_argument("--stage", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--next-action", required=True)
    p.add_argument("--resume-condition", required=True)
    p.add_argument("--severity", choices=["blocker", "critical", "high"], default="blocker")
    p.add_argument("--sub-harness", default="orchestrator")
    p.add_argument("--owner", default="")
    p.add_argument("--source-artifact", action="append")
    p.add_argument("--notes", default="")
    p.add_argument("--stop-id")
    p.add_argument("--output")
    p.set_defaults(func=stop_the_line)

    p = sub.add_parser("validate-stop-the-line")
    p.add_argument("artifact", help="Run artifact path relative to <instance-root>/runs/<run-id>")
    p.set_defaults(func=validate_stop_the_line)

    p = sub.add_parser("write-loop-gate")
    p.add_argument("--gate-id")
    p.add_argument("--stage", required=True)
    p.add_argument(
        "--trigger-source",
        required=True,
        choices=[
            "validator_result",
            "logic_sidecar_audit",
            "projection_report",
            "layout_analyzer",
            "skill_trace",
            "manual_review",
        ],
    )
    p.add_argument("--severity", required=True, choices=["info", "minor", "major", "blocker", "semantic_defect"])
    p.add_argument("--failure-class", required=True)
    p.add_argument("--affected-artifact", action="append")
    p.add_argument("--source-ref", action="append")
    p.add_argument("--repair-hint", required=True)
    p.add_argument("--profile", required=True, choices=["LOOP_PROFILE_SIMPLE", "LOOP_PROFILE_STANDARD", "LOOP_PROFILE_COMPLEX"])
    p.set_defaults(func=write_loop_gate)

    p = sub.add_parser("run-prd-loop")
    p.add_argument("--source", help="Source PRD markdown under <instance-root>/inputs or an absolute path")
    p.set_defaults(func=run_prd_loop)

    p = sub.add_parser("search")
    p.add_argument("query")
    p.set_defaults(func=search)

    p = sub.add_parser("init-instance")
    p.add_argument("instance_root")
    p.add_argument("--instance-id")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=init_instance)

    args = ap.parse_args()
    configure_paths(args)
    args.func(args)

if __name__ == "__main__":
    main()
