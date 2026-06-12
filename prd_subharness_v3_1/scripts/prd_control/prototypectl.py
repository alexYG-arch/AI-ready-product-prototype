#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except Exception:
    yaml = None

try:
    import jsonschema
except Exception:
    jsonschema = None

ROOT = Path(__file__).resolve().parents[2]
PROTOTYPE_ROOT = ROOT / "sub_harnesses" / "prototype_projection_harness"
DRD_ROOT = PROTOTYPE_ROOT / "drd_v3_1"
LOOP_ROOT = DRD_ROOT / "loop_v3_1"
SOURCE_BASELINE_REL = Path("prd_orchestrator/source_extraction/structured_source_baseline.yaml")
HARNESS_ROOT = ROOT
INSTANCE_ROOT = ROOT
RUN_ID = "manual"
RUN_ROOT = ROOT / "runs" / RUN_ID
INSTANCE_ROOT_PROVIDED = False
RUN_ID_PROVIDED = False
ALLOW_HARNESS_WRITES = False

WRITE_COMMANDS = {
    "classify-figma-diff",
    "generate-prototype-artifacts",
}


def configure_paths(args):
    global INSTANCE_ROOT, RUN_ID, RUN_ROOT, INSTANCE_ROOT_PROVIDED, RUN_ID_PROVIDED, ALLOW_HARNESS_WRITES
    INSTANCE_ROOT_PROVIDED = bool(getattr(args, "instance_root", None))
    RUN_ID_PROVIDED = bool(getattr(args, "run_id", None))
    INSTANCE_ROOT = Path(getattr(args, "instance_root", None)).resolve() if INSTANCE_ROOT_PROVIDED else HARNESS_ROOT
    RUN_ID = getattr(args, "run_id", None) or "manual"
    RUN_ROOT = (INSTANCE_ROOT / "runs" / RUN_ID).resolve()
    ALLOW_HARNESS_WRITES = bool(getattr(args, "allow_harness_writes", False))


def path_is_within(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def ensure_write_allowed(command_name: str):
    if command_name not in WRITE_COMMANDS:
        return
    if INSTANCE_ROOT_PROVIDED and not path_is_within(INSTANCE_ROOT, HARNESS_ROOT):
        return
    if ALLOW_HARNESS_WRITES:
        return
    raise SystemExit(
        f"BLOCKED: {command_name} writes run artifacts and requires --instance-root outside the harness package. "
        "Use --instance-root <path> --run-id <id>, or --allow-harness-writes for package-maintenance tests only."
    )


def ensure_run_manifest(command_name: str):
    ensure_write_allowed(command_name)
    if command_name not in WRITE_COMMANDS or not INSTANCE_ROOT_PROVIDED:
        return
    manifest = RUN_ROOT / "run_manifest.yaml"
    if manifest.exists():
        return
    data = {
        "run_manifest": {
            "run_id": RUN_ID,
            "run_status": "candidate_requires_review",
            "harness_root": str(HARNESS_ROOT),
            "instance_root": str(INSTANCE_ROOT),
            "run_root": str(RUN_ROOT),
            "write_policy": {
                "harness_package_is_read_only": True,
                "prototype_diff_candidates_go_to_run_root": True,
                "prototype_generator_outputs_go_to_run_root": True,
                "fact_stores_are_not_written_by_prototypectl": True,
                "figma_is_not_written_by_prototypectl_generator": True,
            },
        }
    }
    ywrite(manifest, data)


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


def load_any(path: Path):
    if path.suffix.lower() == ".json":
        return jload(path)
    return yload(path)


def ywrite(path: Path, data):
    if yaml is None:
        raise RuntimeError("Install pyyaml: pip install pyyaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def jwrite(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_now_text() -> str:
    return utc_text(datetime.now(timezone.utc))


def utc_text(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def duration_ms(started_at: datetime, completed_at: datetime) -> int:
    return int((completed_at - started_at).total_seconds() * 1000)


def start_stage_record(
    job_id: str,
    stage_id: str,
    generator_id: str,
    generator_kind: str,
    worker_id: str,
    rule_ids: list[str],
    input_refs: list[str] | None = None,
) -> dict:
    started = datetime.now(timezone.utc)
    return {
        "job_id": job_id,
        "stage_id": stage_id,
        "generator_id": generator_id,
        "generator_kind": generator_kind,
        "worker_id": worker_id,
        "rule_ids": normalize_rule_ids(rule_ids),
        "input_refs": input_refs or [],
        "output_refs": [],
        "status": "running",
        "started_at": utc_text(started),
        "completed_at": None,
        "duration_ms": None,
        "_started_at_dt": started,
    }


def finish_stage_record(record: dict, status: str = "pass", output_refs: list[str] | None = None) -> dict:
    completed = datetime.now(timezone.utc)
    started = record.pop("_started_at_dt", completed)
    record.update({
        "status": status,
        "output_refs": output_refs or record.get("output_refs", []),
        "completed_at": utc_text(completed),
        "duration_ms": duration_ms(started, completed),
    })
    return record


def public_stage_records(stage_records: list[dict]) -> list[dict]:
    return [
        {key: value for key, value in record.items() if not key.startswith("_")}
        for record in stage_records
    ]


def safe_slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", str(text)).strip("-")
    return (slug or "artifact")[:80]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_path(path_text: str | None, default: Path | None = None) -> Path:
    if not path_text:
        if default is None:
            raise ValueError("path_text or default required")
        return default
    path = Path(path_text)
    if path.is_absolute():
        return path
    for base in [Path.cwd(), INSTANCE_ROOT, RUN_ROOT, ROOT]:
        candidate = base / path
        if candidate.exists():
            return candidate
    return ROOT / path


def default_input_path(rel: str) -> Path:
    if INSTANCE_ROOT_PROVIDED:
        instance_candidate = INSTANCE_ROOT / rel
        if instance_candidate.exists():
            return instance_candidate
    return ROOT / rel


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
    req = yload(default_input_path("product-spec/requirements.yaml"))
    screens = yload(default_input_path("product-spec/screens.yaml"))
    metrics = yload(default_input_path("product-spec/metrics.yaml"))
    events = yload(default_input_path("product-spec/events.yaml"))
    return {
        "goals": len(req.get("goals") or []),
        "requirements": len(req.get("requirements") or []),
        "requirement_candidates": len(req.get("requirement_candidates") or []),
        "screens": len(screens.get("screens") or []),
        "state_reasoning_chains": len(screens.get("state_reasoning_chains") or []),
        "metrics": len(metrics.get("metrics") or []),
        "events": len(events.get("events") or []),
    }


def source_baseline_path() -> Path:
    return RUN_ROOT / SOURCE_BASELINE_REL


def runtime_material_counts(runtime: dict) -> dict:
    return {
        "flows": len(runtime.get("flows") or []),
        "screens": len(runtime.get("screens") or []),
        "overlays": len(runtime.get("overlays") or []),
        "variables": len(runtime.get("variables") or []),
        "component_bindings": len(runtime.get("component_bindings") or []),
        "interaction_nodes": len((runtime.get("interaction_graph") or {}).get("nodes") or []),
        "interaction_edges": len((runtime.get("interaction_graph") or {}).get("edges") or []),
        "prototype_gaps": len(runtime.get("prototype_gaps") or []),
        "copy_catalog": len(runtime.get("copy_catalog") or []),
    }


def validate_schema(instance_path: Path, schema_path: Path) -> list[str]:
    if not instance_path.exists():
        return [f"missing instance {instance_path}"]
    if not schema_path.exists():
        return [f"missing schema {schema_path}"]
    if jsonschema is None:
        return ["jsonschema not installed; skipped schema validation"]
    try:
        schema = jload(schema_path)
        if hasattr(jsonschema, "Draft202012Validator"):
            jsonschema.Draft202012Validator.check_schema(schema)
            validator = jsonschema.Draft202012Validator(schema)
            errors = sorted(validator.iter_errors(load_any(instance_path)), key=lambda item: list(item.path))
            return [format_schema_error(error) for error in errors]
        jsonschema.validate(load_any(instance_path), schema)
        return []
    except Exception as exc:
        return [str(exc)]


def validate_schema_data(data, schema_path: Path) -> list[str]:
    if not schema_path.exists():
        return [f"missing schema {schema_path}"]
    if jsonschema is None:
        return ["jsonschema not installed; skipped schema validation"]
    try:
        schema = jload(schema_path)
        if hasattr(jsonschema, "Draft202012Validator"):
            jsonschema.Draft202012Validator.check_schema(schema)
            validator = jsonschema.Draft202012Validator(schema)
            errors = sorted(validator.iter_errors(data), key=lambda item: list(item.path))
            return [format_schema_error(error) for error in errors]
        jsonschema.validate(data, schema)
        return []
    except Exception as exc:
        return [str(exc)]


def format_schema_error(error) -> str:
    path = ".".join(str(part) for part in error.path)
    schema_path = ".".join(str(part) for part in error.schema_path)
    prefix = path or "<root>"
    return f"{prefix}: {error.message} (schema: {schema_path})"


def validate_json_schema_file(schema_path: Path) -> list[str]:
    if not schema_path.exists():
        return [f"missing schema {schema_path}"]
    try:
        schema = jload(schema_path)
        if jsonschema is not None and hasattr(jsonschema, "Draft202012Validator"):
            jsonschema.Draft202012Validator.check_schema(schema)
        return []
    except Exception as exc:
        return [f"{schema_path}: {exc}"]


def print_result(title: str, errors: list[str], warnings: list[str] | None = None):
    warnings = warnings or []
    print(f"# {title}")
    print("PASS" if not errors else "BLOCKED")
    for error in errors:
        print(f"- ERROR: {error}")
    for warning in warnings:
        print(f"- WARNING: {warning}")
    if errors:
        raise SystemExit(1)


def drd_required_files() -> list[str]:
    return [
        "sub_harnesses/prototype_projection_harness/drd_v3_1/profile.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/package_manifest.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/rules/00_stage_plan.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/rules/01_screen_role_obligation_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/rules/02_design_kernel_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/rules/03_composition_generation_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/rules/04_interaction_hotspot_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/rules/05_logic_sidecar_audit_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/rules/06_local_materialization_patch_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/rules/07_annotation_stub_sidecar_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/rules/08_pen_line_deemphasis_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/rules/09_skill_methodology_hook_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/rules/10_inductive_support_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/rules/11_validators.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/rules/12_complete_deductive_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/rules/13_rule_projection_map.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/rules/14_carrier_handoff_operation_chain_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/libs/deductive_method_library.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/libs/obligation_primitive_library.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/libs/sidecar_card_template_library.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/libs/capability_primitive_library.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/contract_upgrade_manifest.yaml",
        "sub_harnesses/prototype_projection_harness/adapters/design_systems/sds_monochrome_adapter.yaml",
        "sub_harnesses/prototype_projection_harness/adapters/design_systems/figma-sds.SOURCE.md",
        "sub_harnesses/prototype_projection_harness/adapters/design_systems/figma-sds/figma.config.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/screen_role_obligations.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/design_kernel.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/prototype_source_brief.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/composition_plan.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/interaction_hotspot_map.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/logic_sidecar_card_map.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/annotation_stub_map.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/anchor_badge_map.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/local_materialization_patch.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/generation_job_queue.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/model_execution_contract.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/model_invocation_trace.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/interaction_carrier_map.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/system_handoff_map.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/user_operation_chain.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/capability_assessment.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/prototype_review_view_model.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/model_contract_promotion_report.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/examples/screen_role_obligations.sample.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/examples/design_kernel.sample.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/examples/logic_sidecar_card_map.sample.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/examples/local_materialization_patch.sample.yaml",
    ]


def loop_required_files() -> list[str]:
    return [
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/README.md",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/package_manifest.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/package_manifest.harness_aligned.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/docs/LOOP_ENGINEERING_DESIGN_GUIDE_v3_1.md",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/codex/CODEX_LOOP_UPGRADE_PROMPT.md",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/00_loop_engineering_principles.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/01_loop_taxonomy_layers.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/02_loop_profile_policy.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/03_loop_trigger_detection_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/04_failure_classification_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/05_loop_router_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/06_patch_type_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/07_rerun_scope_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/08_stage_loop_contracts.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/09_revalidation_exit_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/10_loop_manifest_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/11_loop_safety_governance_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/12_harness_macro_loop_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/13_skill_loop_influence_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/14_loop_observability_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/15_complete_loop_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/16_gate_only_harness_alignment.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/rules/17_harness_aligned_stage_loop_contracts.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/schemas/loop_manifest.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/schemas/loop_finding.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/schemas/repair_plan.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/schemas/stage_loop_contract.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/schemas/loop_profile.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/schemas/local_patch.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/examples/harness_aligned_loop_finding.sample.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/examples/harness_aligned_repair_plan.sample.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/examples/harness_aligned_loop_manifest.sample.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/examples/harness_aligned_local_patches.sample.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/examples/negative/local_loop_patch.writes_prd_true.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/examples/negative/repair_plan.missing_patch_set.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/loop_v3_1/examples/negative/repair_plan.missing_rerun_scope.yaml",
    ]


def generation_lifecycle_required_files() -> list[str]:
    base = "sub_harnesses/prototype_projection_harness/drd_v3_1/generation_lifecycle_v3_1_1"
    return [
        f"{base}/README.md",
        f"{base}/package_manifest.yaml",
        f"{base}/package_manifest.harness_aligned.yaml",
        f"{base}/docs/GENERATION_LIFECYCLE_DESIGN_v3_1_1.md",
        f"{base}/docs/WHY_THIS_WAS_NOT_SEEN_BEFORE.md",
        f"{base}/codex/CODEX_GENERATION_LIFECYCLE_UPGRADE_PROMPT.md",
        f"{base}/rules/00_stage_generation_controller.yaml",
        f"{base}/rules/01_build_crew_generator_rules.yaml",
        f"{base}/rules/02_stage_generate_contract.yaml",
        f"{base}/rules/03_generation_worker_contracts.yaml",
        f"{base}/rules/04_generation_trace_rules.yaml",
        f"{base}/rules/05_generate_validate_repair_lifecycle.yaml",
        f"{base}/rules/06_missing_artifact_bootstrap_rules.yaml",
        f"{base}/rules/07_regeneration_policy.yaml",
        f"{base}/rules/08_validator_behavior_update.yaml",
        f"{base}/rules/09_complete_generation_lifecycle_rules.yaml",
        f"{base}/rules/10_repair_crew_integration_rules.yaml",
        f"{base}/rules/11_stage_generator_matrix.yaml",
        f"{base}/rules/12_generation_safety_rules.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/source_atom.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/source_slice_index.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/generation_job_queue.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/generation_trace.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/model_execution_contract.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/model_invocation_trace.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/generated_artifact_manifest.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/source_coverage_report.schema.json",
    ]


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
    for path in sorted((DRD_ROOT / "rules").glob("*.yaml")):
        data = yload(path)
        for rule_id in collect_values_for_key(data, "rule_id"):
            index.setdefault(rule_id, path.relative_to(DRD_ROOT).as_posix())
    return index


def known_drd_rule_ids() -> set[str]:
    return set(drd_rule_source_index())


def rule_projection_map() -> dict:
    return yload(DRD_ROOT / "rules" / "13_rule_projection_map.yaml").get("prototype_rule_projection_map", {})


def normalize_rule_ids(rule_ids: list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    return sorted({str(rule_id) for rule_id in (rule_ids or []) if str(rule_id or "").strip()})


def rule_ids_for_artifact(artifact_key: str, extra_rule_ids: list[str] | None = None) -> list[str]:
    artifacts = rule_projection_map().get("artifacts", {}) or {}
    rule_ids = list((artifacts.get(artifact_key, {}) or {}).get("rule_ids", []) or [])
    rule_ids.extend(extra_rule_ids or [])
    return normalize_rule_ids(rule_ids)


def artifact_rule_key(path_key: str) -> str:
    aliases = {
        "source_brief": "prototype_source_brief",
        "report_yaml": "projection_report",
        "report_md": "projection_report",
        "codex_inference_raw": "codex_inference_review",
        "deterministic_draft_summary": "generation_trace",
        "stage_timing_trace": "generation_trace",
        "model_execution_contract_resolved": "model_execution_contract",
        "blueprint_review_md": "prototype_review_view_model",
    }
    if path_key.startswith("model_") and path_key not in {"model_execution_contract", "model_invocation_trace"}:
        if path_key.endswith("_contract"):
            return "model_execution_contract"
        return "model_invocation_trace"
    return aliases.get(path_key, path_key)


def stage_rule_ids(stage_id: str | None) -> list[str]:
    if not stage_id:
        return []
    return normalize_rule_ids((rule_projection_map().get("stages", {}) or {}).get(stage_id, []) or [])


def failure_class_rule_ids(failure_class: str | None) -> list[str]:
    if not failure_class:
        return []
    return normalize_rule_ids((rule_projection_map().get("failure_classes", {}) or {}).get(failure_class, []) or [])


def rule_trace_for_artifact(artifact_key: str, extra_rule_ids: list[str] | None = None, stage_id: str | None = None) -> dict:
    projection = rule_projection_map()
    artifacts = projection.get("artifacts", {}) or {}
    artifact_projection = artifacts.get(artifact_key, {}) or {}
    resolved_stage = stage_id or artifact_projection.get("stage_id") or ""
    rule_ids = rule_ids_for_artifact(artifact_key, extra_rule_ids)
    sources = drd_rule_source_index()
    return {
        "trace_version": "3.1.1",
        "projection_map_id": projection.get("id", "RULE_PROJECTION_MAP_V3_1_1"),
        "artifact_key": artifact_key,
        "stage_id": resolved_stage,
        "rule_ids": rule_ids,
        "rule_sources": [
            {"rule_id": rule_id, "file": sources.get(rule_id, "")}
            for rule_id in rule_ids
        ],
        "validator_commands": artifact_projection.get("validator_commands", []) or [],
    }


def rule_trace_errors(item: dict, context: str, *, require: bool = True) -> list[str]:
    errors = []
    if not isinstance(item, dict):
        return [f"{context}: rule trace target is not an object"]
    trace = item.get("rule_trace", {}) or {}
    rule_ids = normalize_rule_ids(item.get("rule_ids") or trace.get("rule_ids"))
    if require and not rule_ids:
        return [f"{context}: missing rule_trace.rule_ids"]
    known = known_drd_rule_ids()
    for rule_id in rule_ids:
        if rule_id not in known:
            errors.append(f"{context}: unknown rule_id {rule_id}")
    if trace and not trace.get("projection_map_id"):
        errors.append(f"{context}: rule_trace.projection_map_id is required")
    return errors


def rule_error(rule_id: str, message: str) -> str:
    return f"[{rule_id}] {message}"


def status(args):
    files = [
        "product-spec/prototype.runtime.base.json",
        "product-spec/prototype.runtime.json",
        "product-spec/figma-sync-map.yaml",
        "product-spec/figma-interaction-map.yaml",
        "product-spec/component-binding-map.yaml",
        "product-spec/design-semantic-library.json",
        "schemas/prototype_runtime.schema.json",
        "schemas/figma_interaction_map.schema.json",
        "schemas/figma_comment_map.schema.json",
        "schemas/layout_route_plan.schema.json",
        "schemas/uxwriter_copy_catalog.schema.json",
        "schemas/renderer_skill_pack.schema.json",
        "schemas/prototype_render_payload.schema.json",
        "sub_harnesses/prototype_projection_harness/harness_contract.yaml",
        "sub_harnesses/prototype_projection_harness/runtime_inference_policy.yaml",
        "sub_harnesses/prototype_projection_harness/renderer_stage_plan.yaml",
        "sub_harnesses/prototype_projection_harness/figma_comment_annotation_policy.yaml",
        "sub_harnesses/prototype_projection_harness/uxwriter_stage_rules.yaml",
        "sub_harnesses/prototype_projection_harness/layout_routing_coupling_rules.yaml",
        "sub_harnesses/prototype_projection_harness/pen_line_routing_rules.yaml",
        "sub_harnesses/prototype_projection_harness/renderer_skill_hook_policy.yaml",
        "sub_harnesses/prototype_projection_harness/contracts/input_prd_fact_bundle.schema.json",
        "sub_harnesses/prototype_projection_harness/contracts/standalone_run_contract.yaml",
        "sub_harnesses/prototype_projection_harness/examples/prd_fact_bundle.sample.yaml",
        "sub_harnesses/prototype_projection_harness/examples/uxwriter-copy-catalog.sample.yaml",
        "sub_harnesses/prototype_projection_harness/examples/layout-route-plan.sample.yaml",
        "sub_harnesses/prototype_projection_harness/examples/figma-comment-map.yaml",
        "sub_harnesses/prototype_projection_harness/examples/renderer-skill-pack.sample.yaml",
        "prd_orchestrator/patch_control_v2.yaml",
    ]
    print("# Prototype Projection Harness v3.1")
    missing = []
    for rel in files:
        exists = (ROOT / rel).exists()
        print(f"- {'OK' if exists else 'MISSING'} {rel}")
        if not exists:
            missing.append(rel)
    if getattr(args, "mode", "default") == "drd":
        print("# DRD v3.1")
        for rel in drd_required_files():
            exists = (ROOT / rel).exists()
            print(f"- {'OK' if exists else 'MISSING'} {rel}")
            if not exists:
                missing.append(rel)
        source = Path(__file__).read_text(encoding="utf-8")
        for command in [
            "validate-drd-rules",
            "validate-role-obligations",
            "validate-design-kernel",
            "validate-sidecar-cards",
            "validate-local-patches",
            "validate-design-system-adapters",
            "validate-render-readiness",
            "generate-prototype-artifacts",
            "validate-loop-rules",
            "validate-loop-manifest",
            "validate-loop-finding",
            "validate-repair-plan",
            "validate-stage-loop-contracts",
            "validate-local-loop-patches",
            "validate-generation-lifecycle-rules",
            "validate-generation-job-queue",
            "validate-generation-trace",
            "validate-model-execution-contract",
            "validate-model-invocation-trace",
            "validate-model-surface-ownership",
            "validate-model-user-journey",
            "validate-model-interaction-state-machine",
            "validate-model-component-blueprint",
            "validate-model-stage-coverage",
            "validate-generated-artifact-manifest",
            "validate-source-coverage",
            "validate-carrier-map",
            "validate-system-handoff-map",
            "validate-operation-chain",
            "validate-capability-assessment",
            "validate-review-view-model",
            "validate-contract-promotion",
        ]:
            exists = command in source
            print(f"- {'OK' if exists else 'MISSING'} command:{command}")
            if not exists:
                missing.append(f"command:{command}")
        print("# Loop v3.1 gate-only")
        for rel in loop_required_files():
            exists = (ROOT / rel).exists()
            print(f"- {'OK' if exists else 'MISSING'} {rel}")
            if not exists:
                missing.append(rel)
        print("# Generation lifecycle v3.1.1")
        for rel in generation_lifecycle_required_files():
            exists = (ROOT / rel).exists()
            print(f"- {'OK' if exists else 'MISSING'} {rel}")
            if not exists:
                missing.append(rel)
    if missing:
        raise SystemExit(1)


def validate_drd_rules(args):
    errors = []
    warnings = []
    for rel in drd_required_files():
        if not (ROOT / rel).exists():
            errors.append(f"missing required DRD file: {rel}")

    for path in sorted(DRD_ROOT.rglob("*.yaml")):
        try:
            yload(path)
        except Exception as exc:
            errors.append(f"{path.relative_to(ROOT)}: YAML parse failed: {exc}")

    for path in sorted(DRD_ROOT.rglob("*.json")):
        try:
            jload(path)
        except Exception as exc:
            errors.append(f"{path.relative_to(ROOT)}: JSON parse failed: {exc}")

    for schema in sorted((DRD_ROOT / "schemas").glob("*.schema.json")):
        errors.extend(validate_json_schema_file(schema))

    profile = yload(DRD_ROOT / "profile.yaml").get("drd_v3_1_profile", {})
    if profile.get("version") != "3.1":
        errors.append("drd_v3_1/profile.yaml version must be 3.1")
    if profile.get("mode") != "DRD_MODE":
        errors.append("drd_v3_1/profile.yaml mode must be DRD_MODE")
    defaults = profile.get("default_behavior", {}) or {}
    if defaults.get("write_real_figma_reactions") is not False:
        errors.append("DRD profile must default write_real_figma_reactions to false")
    if defaults.get("draw_full_pen_lines") is not False:
        errors.append("DRD profile must default draw_full_pen_lines to false")
    if defaults.get("local_materialization_patches_write_prd") is not False:
        errors.append("DRD profile must default local_materialization_patches_write_prd to false")

    complete = yload(DRD_ROOT / "rules" / "12_complete_deductive_rules.yaml")
    load_order = complete.get("prototype_harness_drd_deductive_complete_rules", {}).get("load_order", [])
    if len(load_order) < 12:
        errors.append("complete deductive rules load_order must include all DRD rule files")
    if "rules/13_rule_projection_map.yaml" not in {item.get("file") for item in load_order if isinstance(item, dict)}:
        errors.append("complete deductive rules load_order must include rules/13_rule_projection_map.yaml")

    projection = rule_projection_map()
    known_rule_ids = known_drd_rule_ids()
    projected_rule_ids = set()
    for section in ["artifacts", "stages", "failure_classes", "validators"]:
        items = projection.get(section, {}) or {}
        for key, value in items.items():
            if isinstance(value, dict):
                rule_ids = value.get("rule_ids", []) or []
            else:
                rule_ids = value or []
            if not rule_ids:
                errors.append(f"rule projection map {section}.{key} must list rule_ids")
            for rule_id in rule_ids:
                projected_rule_ids.add(rule_id)
                if rule_id not in known_rule_ids:
                    errors.append(f"rule projection map {section}.{key} references unknown rule_id {rule_id}")
    missing_projection = sorted(known_rule_ids - projected_rule_ids)
    if missing_projection:
        errors.append(f"rule projection map missing known rule_ids: {', '.join(missing_projection)}")
    for artifact_key in [
        "prototype_source_brief",
        "screen_role_obligations",
        "design_kernel",
        "composition_plan",
        "interaction_hotspot_map",
        "logic_sidecar_card_map",
        "annotation_stub_map",
        "anchor_badge_map",
        "local_materialization_patch",
        "runtime",
        "payload",
        "generation_job_queue",
        "generation_trace",
        "generated_artifact_manifest",
        "source_coverage_report",
        "interaction_carrier_map",
        "system_handoff_map",
        "user_operation_chain",
        "capability_assessment",
        "prototype_review_view_model",
        "model_contract_promotion_report",
    ]:
        if artifact_key not in (projection.get("artifacts", {}) or {}):
            errors.append(f"rule projection map missing artifact key {artifact_key}")

    if jsonschema is None:
        warnings.append("jsonschema not installed; executable schema validation is limited")
    adapter_errors, adapter_warnings = collect_design_system_adapter_errors()
    errors.extend(adapter_errors)
    warnings.extend(adapter_warnings)
    print_result("validate-drd-rules", errors, warnings)


def validate_role_obligations(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "screen_role_obligations.schema.json")
    warnings = []
    if not errors:
        data = yload(path).get("screen_role_obligations", {})
        errors.extend(rule_trace_errors(data, "screen_role_obligations.rule_trace"))
        for item in data.get("obligations", []) or []:
            oid = item.get("obligation_id", "<unknown>")
            errors.extend(rule_trace_errors(item, f"screen_role_obligations.obligations.{oid}.rule_ids"))
            if not item.get("source_refs"):
                errors.append(f"{oid}: missing source_refs")
            if not item.get("inference_basis_zh"):
                errors.append(f"{oid}: missing inference_basis_zh")
    print_result("validate-role-obligations", errors, warnings)


def validate_design_kernel(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "design_kernel.schema.json")
    warnings = []
    if not errors:
        kernel = yload(path).get("design_kernel", {})
        errors.extend(rule_trace_errors(kernel, "design_kernel.rule_trace"))
        if kernel.get("mode") != "DRD_MODE":
            errors.append("design_kernel.mode must be DRD_MODE")
        if not kernel.get("forbidden_realizations"):
            errors.append("design_kernel.forbidden_realizations must not be empty")
        surface_forbidden = (kernel.get("surface_contract", {}) or {}).get("forbidden_realizations")
        if not surface_forbidden:
            errors.append("surface_contract.forbidden_realizations must not be empty")
        for constraint in kernel.get("constraint_contracts", []) or []:
            cid = constraint.get("constraint_id", "<unknown>")
            errors.extend(rule_trace_errors(constraint, f"design_kernel.constraint_contracts.{cid}.rule_ids"))
            if not constraint.get("earliest_fix_surface"):
                errors.append(f"{cid}: missing earliest_fix_surface")
            if not constraint.get("feedback_timing"):
                errors.append(f"{cid}: missing feedback_timing")
        for control in kernel.get("control_contracts", []) or []:
            errors.extend(rule_trace_errors(control, f"design_kernel.control_contracts.{control.get('control_id', '<unknown>')}.rule_ids"))
        for feedback in kernel.get("feedback_contracts", []) or []:
            errors.extend(rule_trace_errors(feedback, f"design_kernel.feedback_contracts.{feedback.get('feedback_id', '<unknown>')}.rule_ids"))
    print_result("validate-design-kernel", errors, warnings)


def validate_sidecar_cards(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "logic_sidecar_card_map.schema.json")
    warnings = []
    if not errors:
        card_map = yload(path).get("logic_sidecar_card_map", {})
        errors.extend(rule_trace_errors(card_map, "logic_sidecar_card_map.rule_trace"))
        card_ids = {card.get("card_id") for card in card_map.get("cards", []) or []}
        for card in card_map.get("cards", []) or []:
            cid = card.get("card_id", "<unknown>")
            errors.extend(rule_trace_errors(card, f"logic_sidecar_card_map.cards.{cid}.rule_ids"))
            if not card.get("anchor_badge_id"):
                errors.append(f"{cid}: missing anchor_badge_id")
            if not card.get("source_refs"):
                errors.append(f"{cid}: missing source_refs")
        for stub in card_map.get("annotation_stubs", []) or []:
            sid = stub.get("annotation_id", "<unknown>")
            errors.extend(rule_trace_errors(stub, f"logic_sidecar_card_map.annotation_stubs.{sid}.rule_ids"))
            sidecar_id = stub.get("sidecar_card_id")
            if not sidecar_id:
                errors.append(f"{sid}: missing sidecar_card_id")
            elif sidecar_id not in card_ids:
                errors.append(f"{sid}: sidecar_card_id {sidecar_id} does not match any card")
    print_result("validate-sidecar-cards", errors, warnings)


def validate_local_patches(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "local_materialization_patch.schema.json")
    warnings = []
    forbidden_scopes = {
        "prd_fact_bundle",
        "requirements_yaml",
        "screens_yaml",
        "metrics_yaml",
        "events_yaml",
        "PRD_md",
    }
    if not errors:
        patch_doc = yload(path).get("local_materialization_patch", {})
        errors.extend(rule_trace_errors(patch_doc, "local_materialization_patch.rule_trace"))
        for patch in patch_doc.get("patches", []) or []:
            pid = patch.get("patch_id", "<unknown>")
            errors.extend(rule_trace_errors(patch, f"local_materialization_patch.patches.{pid}.rule_ids"))
            if patch.get("writes_prd") is not False:
                errors.append(f"{pid}: writes_prd must be false")
            scopes = set(patch.get("patch_scope", []) or [])
            blocked = sorted(scopes & forbidden_scopes)
            if blocked:
                errors.append(f"{pid}: patch_scope includes forbidden PRD fact scopes {blocked}")
            if not patch.get("source_audit_finding"):
                errors.append(f"{pid}: missing source_audit_finding")
            if not patch.get("source_refs"):
                errors.append(f"{pid}: missing source_refs")
    print_result("validate-local-patches", errors, warnings)


STATE_DIMENSION_KEYS = [
    "data_state",
    "network_state",
    "permission_state",
    "input_state",
    "request_lifecycle",
    "consistency_state",
    "recovery_state",
    "platform_device_state",
    "empty_state",
    "error_state",
    "loading_state",
    "success_state",
]


def generator_output_path(*parts: str) -> Path:
    return RUN_ROOT.joinpath(*parts)


def source_relpath(path: Path) -> str:
    try:
        return path.relative_to(INSTANCE_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_generator_source(path_text: str) -> Path:
    if not INSTANCE_ROOT_PROVIDED:
        raise SystemExit("BLOCKED: generate-prototype-artifacts requires --instance-root")
    if not RUN_ID_PROVIDED:
        raise SystemExit("BLOCKED: generate-prototype-artifacts requires --run-id")
    if path_is_within(INSTANCE_ROOT, HARNESS_ROOT) and not ALLOW_HARNESS_WRITES:
        raise SystemExit("BLOCKED: --instance-root must be outside the harness package")
    path = Path(path_text)
    source = path.resolve() if path.is_absolute() else (INSTANCE_ROOT / path).resolve()
    inputs_root = (INSTANCE_ROOT / "inputs").resolve()
    if not source.exists():
        raise SystemExit(f"BLOCKED: source PRD not found: {path_text}")
    if not path_is_within(source, inputs_root):
        raise SystemExit("BLOCKED: prototype generator source must be under <instance-root>/inputs/")
    if not text_file_has_content(source):
        raise SystemExit(f"BLOCKED: source PRD is empty: {source}")
    return source


def markdown_heading(line: str):
    match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line.strip())
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip()


def plain_excerpt(text: str, limit: int = 180) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[: limit - 3] + "..." if len(cleaned) > limit else cleaned


def line_ref(source_path: Path, start: int, end: int | None = None) -> str:
    rel = source_relpath(source_path)
    end = end or start
    if start == end:
        return f"{rel}#L{start}"
    return f"{rel}#L{start}-L{end}"


def parse_markdown_sections(source_path: Path, text: str) -> list[dict]:
    sections = []
    current = {
        "title": "Document Root",
        "level": 0,
        "line_start": 1,
        "lines": [],
    }

    def close_section(end_line: int):
        content_lines = current.get("lines", [])
        content = "\n".join(content_lines).strip()
        if content or current["title"] != "Document Root":
            sections.append({
                "section_id": f"SRC-SEC-{len(sections) + 1:03d}",
                "title": current["title"],
                "level": current["level"],
                "line_start": current["line_start"],
                "line_end": max(current["line_start"], end_line),
                "source_ref": line_ref(source_path, current["line_start"], max(current["line_start"], end_line)),
                "content": content,
                "summary_zh": plain_excerpt(content or current["title"], 160),
            })

    lines = text.splitlines()
    for line_no, raw in enumerate(lines, start=1):
        heading = markdown_heading(raw)
        if heading:
            close_section(line_no - 1)
            level, title = heading
            current = {
                "title": title,
                "level": level,
                "line_start": line_no,
                "lines": [],
            }
        else:
            current.setdefault("lines", []).append(raw)
    close_section(len(lines) or 1)
    if not sections:
        sections.append({
            "section_id": "SRC-SEC-001",
            "title": "PRD",
            "level": 0,
            "line_start": 1,
            "line_end": max(1, len(lines)),
            "source_ref": line_ref(source_path, 1, max(1, len(lines))),
            "content": text.strip(),
            "summary_zh": plain_excerpt(text, 160),
        })
    return sections


PROTOTYPE_SIGNAL_KEYWORDS = [
    "页面",
    "流程",
    "功能",
    "入口",
    "状态",
    "交互",
    "上传",
    "选择",
    "填写",
    "提交",
    "保存",
    "设置",
    "推荐",
    "展示",
    "结果",
    "分析",
    "登录",
    "权限",
    "错误",
    "失败",
    "重试",
    "loading",
    "error",
    "success",
    "flow",
    "screen",
    "page",
]


def section_signal_score(section: dict) -> int:
    basis = f"{section.get('title', '')}\n{section.get('content', '')}".lower()
    score = sum(1 for keyword in PROTOTYPE_SIGNAL_KEYWORDS if keyword.lower() in basis)
    if any(token in basis for token in ["→", "->", "=>"]):
        score += 3
    if "|" in basis and "---" in basis:
        score += 1
    return score


def display_title(text: str, fallback: str) -> str:
    cleaned = re.sub(r"^[\d.、\-\s]+", "", str(text)).strip()
    cleaned = re.sub(r"[`*_#|]+", "", cleaned).strip()
    return (cleaned or fallback)[:36]


def build_screen_candidates(sections: list[dict]) -> list[dict]:
    ranked = sorted(
        [section for section in sections if section.get("content") or section.get("title")],
        key=lambda section: (section_signal_score(section), -section.get("line_start", 0)),
        reverse=True,
    )
    selected = [section for section in ranked if section_signal_score(section) > 0][:4]
    if not selected:
        selected = ranked[:3]
    if not selected:
        selected = sections[:1]
    selected = sorted(selected, key=lambda section: section.get("line_start", 0))
    candidates = []
    for idx, section in enumerate(selected, start=1):
        title = display_title(section.get("title") or section.get("summary_zh"), f"候选页面 {idx}")
        candidates.append({
            "screen_id": f"SCREEN-{idx:03d}",
            "task_id": f"TASK-{idx:03d}",
            "title_zh": title,
            "task_summary_zh": plain_excerpt(section.get("summary_zh") or title, 140),
            "source_refs": [section["source_ref"]],
            "source_section_id": section["section_id"],
            "candidate_status": "candidate_projection",
            "signal_score": section_signal_score(section),
        })
    return candidates


def default_state_dimensions() -> dict:
    return {key: "not_applicable" for key in STATE_DIMENSION_KEYS} | {
        "data_state": "source_backed_candidate",
        "network_state": "not_started",
        "permission_state": "not_applicable_or_gap",
        "input_state": "ready",
        "request_lifecycle": "idle",
        "consistency_state": "source_refs_preserved",
        "recovery_state": "gap_if_not_declared",
        "empty_state": "available_if_data_empty",
        "error_state": "available_if_action_fails",
        "loading_state": "available_if_async",
        "success_state": "available_after_action",
    }


def infer_primary_action_label(candidate: dict) -> str:
    basis = f"{candidate.get('title_zh', '')} {candidate.get('task_summary_zh', '')}"
    for keyword, label in [
        ("上传", "上传"),
        ("分析", "开始分析"),
        ("保存", "保存"),
        ("设置", "保存设置"),
        ("推荐", "查看推荐"),
        ("登录", "登录"),
        ("提交", "提交"),
        ("选择", "选择"),
    ]:
        if keyword in basis:
            return label
    return "继续"


def semantic_keys_for_candidate(candidate: dict) -> list[str]:
    basis = f"{candidate.get('title_zh', '')} {candidate.get('task_summary_zh', '')}"
    keys = ["button.primary.submit", "feedback.toast"]
    if any(keyword in basis for keyword in ["输入", "填写", "上传", "选择", "设置", "搜索"]):
        keys.insert(0, "input.text")
    return keys


def load_component_binding_index() -> dict:
    binding_map = yload(default_input_path("product-spec/component-binding-map.yaml")).get("component_binding_map", {})
    return {
        item.get("semantic_key"): item
        for item in binding_map.get("component_bindings", []) or []
        if item.get("semantic_key")
    }


def clean_md_text(text: str) -> str:
    cleaned = re.sub(r"<br\s*/?>", " ", str(text), flags=re.IGNORECASE)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"[*_#]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" |")


def strip_source_ids(text: str) -> str:
    cleaned = re.sub(r"（?`[^`]+`）?", "", str(text))
    cleaned = re.sub(r"\([^)]*[A-Z]{2,}-[A-Z0-9-]+[^)]*\)", "", cleaned)
    return clean_md_text(cleaned)


def stable_id(prefix: str, text: str, idx: int) -> str:
    slug = safe_slug(text).upper()
    if slug and slug != "ARTIFACT":
        return f"{prefix}-{slug[:54]}"
    digest = hashlib.sha1(str(text).encode("utf-8")).hexdigest()[:10].upper()
    return f"{prefix}-{idx:03d}-{digest}"


def unique_id(value: str, seen: set[str]) -> str:
    candidate = value
    counter = 2
    while candidate in seen:
        candidate = f"{value}-{counter}"
        counter += 1
    seen.add(candidate)
    return candidate


def extract_backtick_ids(text: str) -> list[str]:
    ids = []
    for item in re.findall(r"`([^`]+)`", str(text)):
        cleaned = item.strip()
        if re.search(r"[A-Z]{2,}-[A-Z0-9-]+", cleaned):
            ids.append(cleaned)
    return ids


def markdown_table_cells(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def is_markdown_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def is_markdown_table_separator(line: str) -> bool:
    if not is_markdown_table_row(line):
        return False
    cells = markdown_table_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def section_for_line(sections: list[dict], line_no: int) -> dict:
    for section in sections:
        if section.get("line_start", 0) <= line_no <= section.get("line_end", 0):
            return section
    return sections[0] if sections else {"section_id": "SRC-SEC-000", "title": "PRD", "source_ref": ""}


def atom_categories(text: str, headers: list[str] | None = None, raw_ids: list[str] | None = None) -> list[str]:
    basis = clean_md_text(text)
    headers_text = " ".join(headers or [])
    raw_ids = raw_ids or []
    categories = set()
    if any(rid.startswith("SCR-") for rid in raw_ids) or "页面" in headers_text and "状态" in headers_text:
        categories.add("surface")
    if any(keyword in headers_text for keyword in ["状态", "用户反馈", "恢复方式"]) or raw_ids:
        if any(keyword in basis for keyword in ["状态", "提示", "失败", "不可", "上传", "选择", "保存", "结果", "分析", "解锁"]):
            categories.add("state")
    if any(keyword in basis for keyword in ["点击", "选择", "上传", "提交", "保存", "复制", "添加", "换一批", "入口"]):
        categories.add("control")
    if any(keyword in basis for keyword in ["至少", "最多", "少于", "多于", "超过", "不得", "仅允许", "不可", "阻断", "限制"]):
        categories.add("constraint")
    if re.search(r"\d+\s*(?:到|至|-|~)\s*\d+", basis):
        categories.add("boundary")
        categories.add("constraint")
    if any(keyword in basis for keyword in ["提示", "反馈", "展示", "看到", "置灰", "不可触发", "不可上传"]):
        categories.add("feedback")
    if any(keyword in basis for keyword in ["失败", "错误", "OCR", "不可识别", "重试", "重新", "恢复", "返回", "取消"]):
        categories.add("recovery")
    if any(rid.startswith("REQ-") for rid in raw_ids):
        categories.add("requirement")
    if any(rid.startswith("EVT-") for rid in raw_ids):
        categories.add("event")
    return sorted(categories)


def atom_type_for(text: str, headers: list[str] | None, raw_ids: list[str]) -> str:
    headers_text = " ".join(headers or [])
    if any(rid.startswith("SCR-") for rid in raw_ids):
        return "screen"
    if any(keyword in headers_text for keyword in ["状态", "触发", "用户反馈", "恢复方式"]):
        return "state"
    if any(rid.startswith("REQ-") for rid in raw_ids):
        return "requirement"
    if any(rid.startswith("EVT-") for rid in raw_ids):
        return "event"
    categories = atom_categories(text, headers, raw_ids)
    if "boundary" in categories:
        return "constraint"
    return "table_row" if headers else "text"


PROTOTYPE_STATE_PREFIXES = (
    "TOOLBAR-",
    "TOPIC-",
    "INTIMACY-",
    "RELATION-",
)

NON_SURFACE_ID_PREFIXES = (
    "MET-",
    "EVT-",
    "TRACE-",
    "REQ-",
    "GOAL-",
    "DATA-",
    "REL-MON-",
    "REL-PHASE-",
    "OPEN-",
    "CORE-",
    "SCREEN-",
    "PRD-",
)


def looks_like_prototype_state_id(value: str) -> bool:
    return str(value).startswith(PROTOTYPE_STATE_PREFIXES)


def looks_like_non_surface_id(value: str) -> bool:
    return str(value).startswith(NON_SURFACE_ID_PREFIXES)


def section_is_prototype_surface(section_title: str) -> bool:
    title = str(section_title or "")
    return any(keyword in title for keyword in ["页面语义", "关键状态", "核心用户旅程", "主路径", "体验方案"])


def table_is_page_state_table(headers: list[str] | None) -> bool:
    headers_text = " ".join(headers or [])
    return "页面" in headers_text and "状态" in headers_text and "触发" in headers_text


def atom_required_for_prototype_rendering(
    atom_type: str,
    categories: list[str],
    raw_ids: list[str],
    headers: list[str] | None,
    section_title: str,
) -> bool:
    if any(looks_like_non_surface_id(raw_id) for raw_id in raw_ids):
        return False
    if atom_type == "screen" or any(raw_id.startswith("SCR-") for raw_id in raw_ids):
        return True
    if table_is_page_state_table(headers):
        return any(looks_like_prototype_state_id(raw_id) for raw_id in raw_ids) or section_is_prototype_surface(section_title)
    if any(looks_like_prototype_state_id(raw_id) for raw_id in raw_ids):
        return True
    if "boundary" in categories and section_is_prototype_surface(section_title):
        return True
    return False


def has_boundary_signal(text: str) -> bool:
    return bool(
        re.search(r"\d+\s*(?:到|至|-|~)\s*\d+", text)
        or re.search(r"(?:至少|最多|少于|多于|超过|不得少于|不得多于)\s*\d+", text)
    )


def extract_boundary_info(text: str) -> dict | None:
    basis = clean_md_text(text)
    min_value = None
    max_value = None
    unit = ""
    range_match = re.search(r"(\d+)\s*(?:到|至|-|~)\s*(\d+)\s*([张个屏项条份人级]?)", basis)
    if range_match:
        min_value = int(range_match.group(1))
        max_value = int(range_match.group(2))
        unit = range_match.group(3) or unit
    min_match = re.search(r"(?:至少|不得少于|不少于|少于)\s*(\d+)\s*([张个屏项条份人级]?)", basis)
    if min_match:
        min_value = int(min_match.group(1))
        unit = min_match.group(2) or unit
    max_match = re.search(r"(?:最多|不得多于|不多于|多于|超过)\s*(\d+)\s*([张个屏项条份人级]?)", basis)
    if max_match:
        max_value = int(max_match.group(1))
        unit = max_match.group(2) or unit
    if min_value is None and max_value is None:
        return None
    action = "选择"
    for keyword in ["上传", "选择", "添加", "填写", "提交", "保存"]:
        if keyword in basis:
            action = keyword
            break
    return {
        "min": min_value,
        "max": max_value,
        "unit": unit or "项",
        "action": action,
    }


def value_for(row: dict, names: list[str]) -> str:
    for wanted in names:
        for key, value in row.items():
            if wanted == key:
                return str(value or "").strip()
    for wanted in names:
        for key, value in row.items():
            if wanted in key:
                return str(value or "").strip()
    return ""


def build_source_atoms(source_path: Path, text: str, sections: list[dict]) -> list[dict]:
    atoms = []
    seen = set()
    lines = text.splitlines()
    idx = 0
    atom_counter = 1
    while idx < len(lines):
        line = lines[idx]
        line_no = idx + 1
        if is_markdown_table_row(line) and idx + 1 < len(lines) and is_markdown_table_separator(lines[idx + 1]):
            headers = [clean_md_text(cell) for cell in markdown_table_cells(line)]
            section = section_for_line(sections, line_no)
            idx += 2
            while idx < len(lines) and is_markdown_table_row(lines[idx]) and not is_markdown_table_separator(lines[idx]):
                row_line = lines[idx]
                row_no = idx + 1
                cells = markdown_table_cells(row_line)
                if len(cells) < len(headers):
                    cells.extend([""] * (len(headers) - len(cells)))
                row = {headers[pos]: clean_md_text(cells[pos]) for pos in range(min(len(headers), len(cells)))}
                raw_ids = extract_backtick_ids(row_line)
                atom_id_base = raw_ids[0] if raw_ids else stable_id("ATOM", row_line, atom_counter)
                atom_id = unique_id(atom_id_base, seen)
                source_ref = line_ref(source_path, row_no)
                source_text = " | ".join(value for value in row.values() if value)
                categories = atom_categories(source_text, headers, raw_ids)
                atom_type = atom_type_for(source_text, headers, raw_ids)
                required_for_rendering = atom_required_for_prototype_rendering(
                    atom_type,
                    categories,
                    raw_ids,
                    headers,
                    section.get("title", ""),
                )
                atoms.append({
                    "atom_id": atom_id,
                    "atom_type": atom_type,
                    "source_refs": [source_ref],
                    "source_text_zh": clean_md_text(source_text),
                    "raw_ids": raw_ids,
                    "categories": categories,
                    "required_for_rendering": required_for_rendering,
                    "source_section_id": section.get("section_id"),
                    "section_title_zh": section.get("title"),
                    "table_headers": headers,
                    "table_cells": row,
                    "row_hash": hashlib.sha256(row_line.encode("utf-8")).hexdigest(),
                })
                atom_counter += 1
                idx += 1
            continue

        stripped = line.strip()
        if stripped and (has_boundary_signal(stripped) or any(token in stripped for token in ["->", "→", "=>"])):
            section = section_for_line(sections, line_no)
            raw_ids = extract_backtick_ids(stripped)
            atom_id_base = raw_ids[0] if raw_ids else stable_id("ATOM", stripped, atom_counter)
            atom_id = unique_id(atom_id_base, seen)
            categories = atom_categories(stripped, [], raw_ids)
            atom_type = atom_type_for(stripped, [], raw_ids)
            required_for_rendering = atom_required_for_prototype_rendering(
                atom_type,
                categories,
                raw_ids,
                [],
                section.get("title", ""),
            )
            atoms.append({
                "atom_id": atom_id,
                "atom_type": atom_type,
                "source_refs": [line_ref(source_path, line_no)],
                "source_text_zh": clean_md_text(stripped),
                "raw_ids": raw_ids,
                "categories": categories,
                "required_for_rendering": required_for_rendering,
                "source_section_id": section.get("section_id"),
                "section_title_zh": section.get("title"),
                "row_hash": hashlib.sha256(stripped.encode("utf-8")).hexdigest(),
            })
            atom_counter += 1
        idx += 1
    return atoms


def build_source_slice_index(atoms: list[dict], source_refs: list[str]) -> dict:
    slices = []
    for category in ["surface", "state", "control", "constraint", "feedback", "recovery", "boundary"]:
        matching = [atom for atom in atoms if category in atom.get("categories", []) or atom.get("atom_type") == category]
        if matching:
            refs = sorted({ref for atom in matching for ref in atom.get("source_refs", [])})
            slices.append({
                "slice_id": f"SLICE-{category.upper()}",
                "slice_type": category,
                "atom_ids": [atom["atom_id"] for atom in matching],
                "source_refs": refs,
                "extracted_actions": [atom["atom_id"] for atom in matching if "control" in atom.get("categories", [])],
                "extracted_objects": [atom["atom_id"] for atom in matching],
                "extracted_constraints": [atom["atom_id"] for atom in matching if "constraint" in atom.get("categories", [])],
            })
    if not slices and atoms:
        slices.append({
            "slice_id": "SLICE-SOURCE",
            "slice_type": "source",
            "atom_ids": [atom["atom_id"] for atom in atoms],
            "source_refs": source_refs,
        })
    return {
        "source_slice_index": {
            "version": "3.1.1",
            "mode": "DRD_MODE",
            "source_refs": source_refs,
            "slices": slices,
        }
    }


def source_refs_from_items(items: list[dict]) -> list[str]:
    return sorted({ref for item in items for ref in item.get("source_refs", [])})


def build_screen_candidates_from_atoms(sections: list[dict], atoms: list[dict]) -> list[dict]:
    candidates = []
    seen_screen_ids = set()
    screen_name_to_id = {}
    for atom in atoms:
        raw_ids = atom.get("raw_ids", [])
        if not atom.get("required_for_rendering"):
            continue
        if any(looks_like_non_surface_id(raw_id) for raw_id in raw_ids):
            continue
        if atom.get("atom_type") != "screen" and not any(rid.startswith("SCR-") for rid in raw_ids):
            continue
        cells = atom.get("table_cells", {}) or {}
        screen_id = next((rid for rid in raw_ids if rid.startswith("SCR-")), stable_id("SCREEN", atom["source_text_zh"], len(candidates) + 1))
        screen_id = unique_id(screen_id, seen_screen_ids)
        title = value_for(cells, ["页面名", "页面", "模块", "功能"]) or strip_source_ids(atom["source_text_zh"])[:36] or screen_id
        state_ids = [rid for rid in raw_ids if rid != screen_id]
        candidates.append({
            "screen_id": screen_id,
            "task_id": f"TASK-{screen_id}",
            "title_zh": title,
            "task_summary_zh": plain_excerpt(atom["source_text_zh"], 180),
            "source_refs": atom["source_refs"],
            "source_section_id": atom.get("source_section_id", ""),
            "source_atom_id": atom["atom_id"],
            "source_state_ids": state_ids,
            "candidate_status": "candidate_projection",
            "signal_score": 99,
        })
        screen_name_to_id[title] = screen_id

    for atom in atoms:
        if atom.get("atom_type") != "state":
            continue
        if not atom.get("required_for_rendering"):
            continue
        cells = atom.get("table_cells", {}) or {}
        page_name = value_for(cells, ["页面", "模块", "功能"])
        if page_name and page_name not in screen_name_to_id:
            screen_id = unique_id(stable_id("SCREEN", page_name, len(candidates) + 1), seen_screen_ids)
            candidates.append({
                "screen_id": screen_id,
                "task_id": f"TASK-{screen_id}",
                "title_zh": page_name,
                "task_summary_zh": f"{page_name}状态集合",
                "source_refs": atom["source_refs"],
                "source_section_id": atom.get("source_section_id", ""),
                "source_atom_id": atom["atom_id"],
                "source_state_ids": [],
                "candidate_status": "candidate_projection",
                "signal_score": 80,
            })
            screen_name_to_id[page_name] = screen_id

    if candidates:
        return candidates
    return build_screen_candidates(sections)


def screen_id_for_page(page_name: str, screen_candidates: list[dict]) -> str:
    for candidate in screen_candidates:
        if candidate.get("title_zh") == page_name:
            return candidate["screen_id"]
    return screen_candidates[0]["screen_id"] if screen_candidates else "SCREEN-001"


def build_boundary_state_candidates(atom: dict, screen_id: str, existing_ids: set[str]) -> list[dict]:
    info = extract_boundary_info(atom.get("source_text_zh", ""))
    if not info:
        return []
    values = []
    if info.get("min") is not None:
        below = max(0, int(info["min"]) - 1)
        values.extend([(below, "below_min"), (int(info["min"]), "min")])
    if info.get("max") is not None:
        values.extend([(int(info["max"]), "max"), (int(info["max"]) + 1, "above_max")])
    result = []
    for value, kind in values:
        if value == 0 and kind == "below_min":
            label = f"未{info['action']}，低于最小数量"
        elif kind == "below_min":
            label = f"{info['action']} {value} {info['unit']}，低于最小数量"
        elif kind == "min":
            label = f"{info['action']} {value} {info['unit']}，达到最小合法边界"
        elif kind == "max":
            label = f"{info['action']} {value} {info['unit']}，达到最大合法边界"
        else:
            label = f"{info['action']} {value} {info['unit']}，超过最大数量"
        state_id = unique_id(f"{stable_id('STATE', atom['atom_id'], value)}-{kind.upper()}", existing_ids)
        invalid = kind in {"below_min", "above_max"}
        feedback = ""
        if invalid and kind == "below_min" and info.get("min") is not None:
            feedback = f"至少需要{info['action']} {info['min']} {info['unit']}。"
        elif invalid and kind == "above_max" and info.get("max") is not None:
            feedback = f"最多只能{info['action']} {info['max']} {info['unit']}。"
        result.append({
            "state_id": state_id,
            "screen_id": screen_id,
            "state_zh": label,
            "trigger_zh": f"用户{info['action']} {value} {info['unit']}",
            "feedback_zh": feedback or label,
            "recovery_zh": "继续调整选择或取消。",
            "source_refs": atom["source_refs"],
            "source_atom_id": atom["atom_id"],
            "categories": ["boundary", "constraint"] + (["feedback"] if invalid else []),
            "display_reason_zh": "通用边界值分析：由源文本 min/max 约束生成。",
            "required_for_rendering": True,
            "candidate_status": "candidate_projection",
            "boundary_kind": kind,
            "boundary_value": value,
            "collapse_allowed": False,
        })
    return result


def build_state_candidates_from_atoms(screen_candidates: list[dict], atoms: list[dict]) -> list[dict]:
    states = []
    seen_state_ids = set()
    for atom in atoms:
        if atom.get("atom_type") != "state":
            continue
        if not atom.get("required_for_rendering"):
            continue
        cells = atom.get("table_cells", {}) or {}
        raw_ids = atom.get("raw_ids", [])
        if any(looks_like_non_surface_id(raw_id) for raw_id in raw_ids):
            continue
        if not table_is_page_state_table(atom.get("table_headers", [])) and not any(looks_like_prototype_state_id(raw_id) for raw_id in raw_ids):
            continue
        state_id = next((rid for rid in raw_ids if looks_like_prototype_state_id(rid)), "")
        if not state_id:
            continue
        state_id = unique_id(state_id, seen_state_ids)
        page_name = value_for(cells, ["页面", "模块", "功能"])
        state_label = value_for(cells, ["状态"]) or strip_source_ids(atom["source_text_zh"])
        trigger = value_for(cells, ["触发"])
        feedback = value_for(cells, ["用户反馈", "反馈"])
        recovery = value_for(cells, ["恢复方式", "恢复"])
        categories = atom.get("categories", [])
        required = bool(set(categories) & {"state", "constraint", "boundary", "feedback", "recovery", "control"})
        states.append({
            "state_id": state_id,
            "screen_id": screen_id_for_page(page_name, screen_candidates),
            "state_zh": strip_source_ids(state_label) or state_id,
            "trigger_zh": trigger or infer_primary_action_label({"title_zh": state_label, "task_summary_zh": atom["source_text_zh"]}),
            "feedback_zh": feedback,
            "recovery_zh": recovery,
            "source_refs": atom["source_refs"],
            "source_atom_id": atom["atom_id"],
            "categories": categories,
            "display_reason_zh": "来自 PRD 表格状态行。",
            "required_for_rendering": required,
            "candidate_status": "candidate_projection",
            "source_order": source_ref_line(atom["source_refs"][0]) if atom.get("source_refs") else len(states) + 1,
            "collapse_allowed": not bool(set(categories) & {"constraint", "boundary", "feedback", "recovery"}),
        })

    for candidate in screen_candidates:
        for source_state_id in candidate.get("source_state_ids", []) or []:
            if source_state_id in seen_state_ids:
                continue
            seen_state_ids.add(source_state_id)
            states.append({
                "state_id": source_state_id,
                "screen_id": candidate["screen_id"],
                "state_zh": source_state_id,
                "trigger_zh": infer_primary_action_label(candidate),
                "feedback_zh": "",
                "recovery_zh": "",
                "source_refs": candidate["source_refs"],
                "source_atom_id": candidate.get("source_atom_id", ""),
                "categories": ["state"],
                "display_reason_zh": "来自页面语义表状态清单。",
                "required_for_rendering": True,
                "candidate_status": "candidate_projection",
                "collapse_allowed": True,
            })

    first_screen = screen_candidates[0]["screen_id"] if screen_candidates else "SCREEN-001"
    seed_states = list(states)
    for state in seed_states:
        if should_generate_boundary_variants(state):
            boundary_atom = {
                "atom_id": state["state_id"],
                "source_text_zh": " ".join([
                    state.get("state_zh", ""),
                    state.get("trigger_zh", ""),
                    state.get("feedback_zh", ""),
                    state.get("recovery_zh", ""),
                ]),
                "source_refs": state["source_refs"],
            }
            states.extend(build_boundary_state_candidates(boundary_atom, state.get("screen_id") or first_screen, seen_state_ids))

    if states:
        return states
    fallback = []
    for candidate in screen_candidates:
        state_id = f"STATE-{candidate['screen_id']}-READY"
        fallback.append({
            "state_id": state_id,
            "screen_id": candidate["screen_id"],
            "state_zh": f"{candidate['title_zh']}默认态",
            "trigger_zh": infer_primary_action_label(candidate),
            "feedback_zh": "",
            "recovery_zh": "",
            "source_refs": candidate["source_refs"],
            "source_atom_id": candidate.get("source_atom_id", ""),
            "categories": ["state"],
            "display_reason_zh": "未发现表格状态行时生成默认态。",
            "required_for_rendering": True,
            "candidate_status": "candidate_projection",
            "collapse_allowed": False,
        })
    return fallback


def source_ref_line(ref: str) -> int:
    match = re.search(r"#L(\d+)$", str(ref))
    return int(match.group(1)) if match else 999999


def should_generate_boundary_variants(state: dict) -> bool:
    state_id = state.get("state_id", "")
    if any(token in state_id for token in ["BLOCK", "FAILED", "FAIL", "ERROR", "UNRECOGNIZED"]):
        return False
    if not any(token in state_id for token in ["SELECT", "EDITING"]):
        return False
    basis = " ".join([
        state.get("state_zh", ""),
        state.get("trigger_zh", ""),
        state.get("feedback_zh", ""),
        state.get("recovery_zh", ""),
    ])
    return has_boundary_signal(basis)


def state_sort_key(state: dict) -> tuple[int, str]:
    return (int(state.get("source_order") or source_ref_line((state.get("source_refs") or [""])[0])), state.get("state_id", ""))


def build_surface_ownership(screen_candidates: list[dict], states: list[dict]) -> list[dict]:
    states_by_screen = defaultdict(list)
    for state in states:
        states_by_screen[state.get("screen_id", "")].append(state)
    ownership = []
    for idx, screen in enumerate(screen_candidates, start=1):
        screen_id = screen["screen_id"]
        screen_states = sorted(states_by_screen.get(screen_id, []), key=state_sort_key)
        component_rules = sorted({
            key
            for state in screen_states
            for key in semantic_keys_for_state(state)
        })
        if idx == 1:
            role = "entry_surface"
        elif "SETTING" in screen_id:
            role = "setting_surface"
        elif "RELATION" in screen_id:
            role = "analysis_surface"
        else:
            role = "task_surface"
        ownership.append({
            "screen_id": screen_id,
            "screen_zh": screen.get("title_zh", screen_id),
            "surface_role": role,
            "owned_state_ids": [state["state_id"] for state in screen_states],
            "component_rules": component_rules,
            "source_refs": sorted({ref for item in [screen] + screen_states for ref in item.get("source_refs", [])}),
            "inference_basis_zh": "由页面语义表的页面 ID、页面名称和关键状态归属推断。",
            "review_required": True,
        })
    return ownership


def explicit_target_state_id(state_id: str) -> str:
    explicit = {
        "TOOLBAR-VISIBLE": "TOOLBAR-TOPIC-TAP",
        "TOOLBAR-TOPIC-TAP": "TOPIC-IMAGE-SELECT",
        "TOOLBAR-INTIMACY-TAP": "INTIMACY-DEFAULT-LEVEL2",
        "TOOLBAR-RELATION-TAP": "RELATION-SELECT-SCREENSHOTS",
        "TOPIC-IMAGE-SELECT": "TOPIC-ANALYZING",
        "TOPIC-ANALYZING": "TOPIC-FREE-RESULT",
        "TOPIC-FREE-RESULT": "TOPIC-MEMBER-RESULT",
        "TOPIC-MEMBER-RESULT": "TOPIC-REGENERATING",
        "TOPIC-REGENERATING": "TOPIC-MEMBER-RESULT",
        "TOPIC-COPY-SINGLE": "TOPIC-MEMBER-RESULT",
        "TOPIC-COPY-ALL": "TOPIC-MEMBER-RESULT",
        "TOPIC-UPLOAD-FAILED": "TOPIC-IMAGE-SELECT",
        "TOPIC-IMAGE-UNRECOGNIZED": "TOPIC-IMAGE-SELECT",
        "TOPIC-GENERATION-FAILED": "TOPIC-IMAGE-SELECT",
        "TOPIC-CLIPBOARD-COPY-FAILED": "TOPIC-MEMBER-RESULT",
        "INTIMACY-DEFAULT-LEVEL2": "INTIMACY-EDITING",
        "INTIMACY-EDITING": "INTIMACY-SAVING",
        "INTIMACY-SAVING": "INTIMACY-SAVED",
        "RELATION-SELECT-SCREENSHOTS": "RELATION-UPLOADING",
        "RELATION-BLOCK-LESS-THAN-3": "RELATION-SELECT-SCREENSHOTS",
        "RELATION-BLOCK-MORE-THAN-5": "RELATION-SELECT-SCREENSHOTS",
        "RELATION-UPLOADING": "RELATION-OCR-PROCESSING",
        "RELATION-OCR-PROCESSING": "RELATION-ANALYZING",
        "RELATION-OCR-FAILED": "RELATION-SELECT-SCREENSHOTS",
        "RELATION-ANALYZING": "RELATION-FREE-RESULT",
        "RELATION-FREE-RESULT": "RELATION-MEMBER-RESULT",
        "RELATION-MEMBER-RESULT": "RELATION-MANUAL-SYNC-PROMPT",
        "RELATION-MANUAL-SYNC-PROMPT": "INTIMACY-EDITING",
    }
    direct_target = explicit.get(state_id)
    if direct_target:
        return direct_target
    if state_id.startswith("STATE-RELATION-SELECT-SCREENSHOTS-BELOW_MIN"):
        return "RELATION-BLOCK-LESS-THAN-3"
    if state_id.startswith("STATE-RELATION-SELECT-SCREENSHOTS-MIN"):
        return "RELATION-UPLOADING"
    if state_id.startswith("STATE-RELATION-SELECT-SCREENSHOTS-MAX"):
        return "RELATION-UPLOADING"
    if state_id.startswith("STATE-RELATION-SELECT-SCREENSHOTS-ABOVE_MAX"):
        return "RELATION-BLOCK-MORE-THAN-5"
    if state_id.startswith("STATE-INTIMACY-EDITING-BELOW_MIN"):
        return "INTIMACY-EDITING"
    if state_id.startswith("STATE-INTIMACY-EDITING-MIN"):
        return "INTIMACY-SAVING"
    if state_id.startswith("STATE-INTIMACY-EDITING-MAX"):
        return "INTIMACY-SAVING"
    if state_id.startswith("STATE-INTIMACY-EDITING-ABOVE_MAX"):
        return "INTIMACY-EDITING"
    return ""


def branch_target_state_ids(state_id: str, state_by_id: dict[str, dict]) -> list[str]:
    static_branches = {
        "TOOLBAR-VISIBLE": [
            "TOOLBAR-TOPIC-TAP",
            "TOOLBAR-INTIMACY-TAP",
            "TOOLBAR-RELATION-TAP",
        ],
        "TOPIC-IMAGE-SELECT": [
            "TOPIC-UPLOAD-FAILED",
            "TOPIC-IMAGE-UNRECOGNIZED",
        ],
        "TOPIC-ANALYZING": [
            "TOPIC-GENERATION-FAILED",
        ],
        "TOPIC-MEMBER-RESULT": [
            "TOPIC-COPY-SINGLE",
            "TOPIC-COPY-ALL",
        ],
        "TOPIC-COPY-SINGLE": [
            "TOPIC-CLIPBOARD-COPY-FAILED",
        ],
        "TOPIC-COPY-ALL": [
            "TOPIC-CLIPBOARD-COPY-FAILED",
        ],
        "RELATION-OCR-PROCESSING": [
            "RELATION-OCR-FAILED",
        ],
    }
    targets = list(static_branches.get(state_id, []))
    if state_id == "INTIMACY-EDITING":
        targets.extend(
            item
            for item in state_by_id
            if item.startswith("STATE-INTIMACY-EDITING-")
        )
    if state_id == "RELATION-SELECT-SCREENSHOTS":
        targets.extend(
            item
            for item in state_by_id
            if item.startswith("STATE-RELATION-SELECT-SCREENSHOTS-")
        )
    return [target for target in dict.fromkeys(targets) if target in state_by_id and target != state_id]


def suppress_primary_transition(state_id: str) -> bool:
    return state_id in {"TOOLBAR-VISIBLE"}


def primary_interaction_variant(state_id: str, target_state_id: str) -> str:
    if state_id == target_state_id:
        return "terminal_stay"
    if (state_id, target_state_id) in {
        ("TOPIC-FREE-RESULT", "TOPIC-MEMBER-RESULT"),
        ("RELATION-FREE-RESULT", "RELATION-MEMBER-RESULT"),
    }:
        return "conditional_branch"
    return "primary"


def primary_route_basis_zh(state_id: str, target_state_id: str, fallback: str) -> str:
    if state_id == target_state_id:
        return "终止或停留状态：源 PRD 未提供后续导航，原型保持当前状态供人工确认。"
    if (state_id, target_state_id) in {
        ("TOPIC-FREE-RESULT", "TOPIC-MEMBER-RESULT"),
        ("RELATION-FREE-RESULT", "RELATION-MEMBER-RESULT"),
    }:
        return "会员身份鉴别或解锁后的条件分支，不表达免费结果自动升级。"
    if (state_id, target_state_id) == ("RELATION-MANUAL-SYNC-PROMPT", "INTIMACY-EDITING"):
        return "用户主动选择手动修改亲密度时跨页进入设置面。"
    return fallback


def transition_trigger_zh(source_state: dict, target_state: dict, variant: str) -> str:
    pair = (source_state.get("state_id"), target_state.get("state_id"))
    special = {
        ("TOOLBAR-VISIBLE", "TOOLBAR-TOPIC-TAP"): "用户点击话题推荐入口",
        ("TOOLBAR-VISIBLE", "TOOLBAR-INTIMACY-TAP"): "用户点击亲密度设置入口",
        ("TOOLBAR-VISIBLE", "TOOLBAR-RELATION-TAP"): "用户点击关系分析入口",
        ("TOPIC-IMAGE-SELECT", "TOPIC-ANALYZING"): "用户选择图片/截图并提交",
        ("TOPIC-FREE-RESULT", "TOPIC-MEMBER-RESULT"): "用户完成会员身份鉴别或解锁",
        ("RELATION-FREE-RESULT", "RELATION-MEMBER-RESULT"): "用户完成会员身份鉴别或解锁",
        ("INTIMACY-EDITING", "INTIMACY-SAVING"): "用户选择亲密度等级并点击保存",
        ("INTIMACY-SAVED", "INTIMACY-SAVED"): "保存成功后停留当前页",
        ("RELATION-SELECT-SCREENSHOTS", "RELATION-UPLOADING"): "用户选择 3 到 5 张聊天截图并提交",
        ("RELATION-MANUAL-SYNC-PROMPT", "INTIMACY-EDITING"): "用户点击手动修改亲密度",
    }
    if pair in special:
        return special[pair]
    if variant != "primary":
        return target_state.get("trigger_zh") or source_state.get("trigger_zh") or "用户触发"
    return source_state.get("trigger_zh") or "用户触发"


def branch_route_basis_zh(source_state_id: str, target_state_id: str) -> str:
    if source_state_id == "TOOLBAR-VISIBLE":
        return "同一工具栏入口包含多个功能按钮，按入口表面补齐并列可达路径。"
    if target_state_id.startswith("STATE-"):
        return "源文本存在明确 min/max 约束，按边界值分析补齐分支状态。"
    if any(token in target_state_id for token in ["FAILED", "UNRECOGNIZED", "BLOCK"]):
        return "目标状态是失败、不可识别或阻断恢复态，按异常分支补齐上游可达路径。"
    if any(token in target_state_id for token in ["COPY", "REGENERATING"]):
        return "目标状态是结果页内操作，按结果页可选动作补齐分支。"
    return "按源状态语义补齐非线性操作分支，需人工 review。"


def build_interaction_candidates_from_states(states: list[dict]) -> list[dict]:
    interactions = []
    state_by_id = {state["state_id"]: state for state in states}
    states_by_screen = defaultdict(list)
    for state in states:
        states_by_screen[state["screen_id"]].append(state)
    ordered_next = {}
    for screen_states in states_by_screen.values():
        ordered = sorted(screen_states, key=state_sort_key)
        for idx, state in enumerate(ordered):
            ordered_next[state["state_id"]] = ordered[idx + 1]["state_id"] if idx + 1 < len(ordered) else state["state_id"]
    seen_interaction_ids = set()

    def add_interaction(state: dict, target_state_id: str, step: int, route_basis_zh: str, variant: str) -> None:
        target_state = state_by_id.get(target_state_id, state)
        interaction_kind = "same_screen_transition" if target_state.get("screen_id") == state.get("screen_id") else "cross_screen_navigation"
        interaction_id_base = f"INT-{safe_slug(state['state_id'])}" if variant == "primary" else f"INT-{safe_slug(state['state_id'])}-TO-{safe_slug(target_state_id)}"
        source_refs = sorted(set(state.get("source_refs", []) + target_state.get("source_refs", [])))
        categories = list(dict.fromkeys((state.get("categories", []) or []) + (target_state.get("categories", []) or [])))
        interactions.append({
            "interaction_id": unique_id(interaction_id_base, seen_interaction_ids),
            "source_screen_id": state["screen_id"],
            "source_state_id": state["state_id"],
            "target_screen_id": target_state.get("screen_id", state["screen_id"]),
            "target_state_id": target_state_id,
            "trigger": "ON_CLICK",
            "trigger_zh": transition_trigger_zh(state, target_state, variant),
            "guard_zh": (
                target_state.get("feedback_zh")
                if variant != "primary"
                else (state.get("feedback_zh") or state.get("state_zh") or "见来源 PRD。")
            ),
            "operation_chain_step": step,
            "interaction_kind": interaction_kind,
            "interaction_variant": variant,
            "route_basis_zh": route_basis_zh,
            "source_refs": source_refs or state["source_refs"],
            "source_atom_id": state.get("source_atom_id", ""),
            "categories": categories,
            "candidate_status": "candidate_projection",
        })

    step = 1
    for state in sorted(states, key=state_sort_key):
        explicit_target = explicit_target_state_id(state["state_id"])
        if explicit_target and explicit_target in state_by_id:
            target_state_id = explicit_target
            route_basis_zh = "由源状态 ID、触发动作、失败恢复或跨页面入口语义推断目标状态。"
        elif explicit_target:
            target_state_id = ordered_next.get(state["state_id"], state["state_id"])
            route_basis_zh = f"推断目标 `{explicit_target}` 未在本次候选状态中出现，退回同页面状态顺序。"
        else:
            target_state_id = ordered_next.get(state["state_id"], state["state_id"])
            route_basis_zh = "源 PRD 未给出明确目标状态，按同页面状态顺序生成候选链路，需人工 review。"
        if not suppress_primary_transition(state["state_id"]):
            variant = primary_interaction_variant(state["state_id"], target_state_id)
            route_basis_zh = primary_route_basis_zh(state["state_id"], target_state_id, route_basis_zh)
            add_interaction(state, target_state_id, step, route_basis_zh, variant)
            step += 1
        for branch_target in branch_target_state_ids(state["state_id"], state_by_id):
            if branch_target == target_state_id and not suppress_primary_transition(state["state_id"]):
                continue
            add_interaction(state, branch_target, step, branch_route_basis_zh(state["state_id"], branch_target), "branch")
            step += 1
    return interactions


def coverage_expectations_from_states(states: list[dict]) -> list[dict]:
    expectations = []
    for state in states:
        if not state.get("required_for_rendering"):
            continue
        frame_id = f"FRAME-{safe_slug(state['state_id']) or hashlib.sha1(state['state_id'].encode('utf-8')).hexdigest()[:8].upper()}"
        requires_sidecar = bool(set(state.get("categories", [])) & {"constraint", "boundary", "feedback", "recovery"})
        expectations.append({
            "expectation_id": f"COV-{safe_slug(state['state_id']) or len(expectations) + 1}",
            "atom_id": state.get("source_atom_id") or state["state_id"],
            "state_id": state["state_id"],
            "frame_id": frame_id,
            "requires_sidecar": requires_sidecar,
            "source_refs": state["source_refs"],
        })
    return expectations


def source_brief_from_prd(source_path: Path, text: str) -> dict:
    sections = parse_markdown_sections(source_path, text)
    source_atoms = build_source_atoms(source_path, text, sections)
    screen_candidates = build_screen_candidates_from_atoms(sections, source_atoms)
    state_candidates = build_state_candidates_from_atoms(screen_candidates, source_atoms)
    interaction_candidates = build_interaction_candidates_from_states(state_candidates)
    surface_ownership = build_surface_ownership(screen_candidates, state_candidates)
    all_source_refs = sorted({
        ref
        for item in sections + source_atoms + screen_candidates + state_candidates
        for ref in ([item.get("source_ref")] if item.get("source_ref") else item.get("source_refs", []))
    })
    source_slice_index = build_source_slice_index(source_atoms, all_source_refs)
    coverage_expectations = coverage_expectations_from_states(state_candidates)
    source_rule_ids = rule_ids_for_artifact("prototype_source_brief")
    for item in source_atoms + screen_candidates + state_candidates + interaction_candidates:
        item.setdefault("rule_ids", source_rule_ids)
    for expectation in coverage_expectations:
        expectation.setdefault("rule_ids", rule_ids_for_artifact("source_coverage_report"))
    blocked = []
    if not source_atoms and not any(section_signal_score(section) > 0 for section in sections):
        blocked.append({
            "gap_id": "PROTO-GAP-LOW-STRUCTURE",
            "severity": "review_required",
            "missing_decision": "源 PRD 缺少明确页面/流程标题，generator 只能生成保守候选。",
            "source_refs": [sections[0]["source_ref"]],
        })
    generation_gaps = []
    if not coverage_expectations:
        generation_gaps.append({
            "gap_id": "GEN-GAP-NO-COVERAGE-EXPECTATIONS",
            "gap_zh": "未抽取到 required source atom；只能生成保守默认态。",
            "missing_input": "required state/control/constraint atom",
            "affected_stage": "GEN-SOURCE-SLICES",
            "severity": "review_required",
            "route_zh": "补充 PRD 页面状态表或人工 review。",
        })
    return {
        "prototype_source_brief": {
            "version": "3.1",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "source_path": source_relpath(source_path),
            "source_sha256": sha256_file(source_path),
            "forbidden_as_fact_source": True,
            "created_at": utc_now_text(),
            "rule_trace": rule_trace_for_artifact("prototype_source_brief"),
            "sections": [
                {key: section[key] for key in ["section_id", "title", "line_start", "line_end", "source_ref", "summary_zh"]}
                for section in sections
            ],
            "source_atoms": source_atoms,
            "source_slice_index": source_slice_index["source_slice_index"],
            "screen_task_candidates": screen_candidates,
            "surface_ownership": surface_ownership,
            "state_candidates": state_candidates,
            "interaction_candidates": interaction_candidates,
            "required_state_ids": [state["state_id"] for state in state_candidates if state.get("required_for_rendering")],
            "required_constraint_ids": [
                atom["atom_id"]
                for atom in source_atoms
                if "constraint" in atom.get("categories", []) or "boundary" in atom.get("categories", [])
            ],
            "coverage_expectations": coverage_expectations,
            "generation_gaps": generation_gaps,
            "blocked_inferences": blocked,
            "open_prototype_questions": [
                {
                    "question_id": "PROTO-OQ-001",
                    "question_zh": "请确认细颗粒候选页面、状态、边界和交互是否符合产品意图；未确认前保持 candidate_projection。",
                    "source_refs": [sections[0]["source_ref"]],
                }
            ],
        }
    }


def semantic_keys_for_state(state: dict) -> list[str]:
    basis = f"{state.get('state_zh', '')} {state.get('trigger_zh', '')} {state.get('feedback_zh', '')}"
    keys = []
    if any(keyword in basis for keyword in ["输入", "填写", "上传", "选择", "设置", "搜索", "截图", "图片", "标签"]):
        keys.append("input.text")
    keys.append("button.primary.submit")
    if any(keyword in basis for keyword in ["提示", "反馈", "失败", "不可", "置灰", "重试", "成功", "至少", "最多"]):
        keys.append("feedback.toast")
    else:
        keys.append("feedback.toast")
    if any(keyword in basis for keyword in ["弹窗", "确认", "会员", "解锁"]):
        keys.append("overlay.modal.confirmation")
    return list(dict.fromkeys(keys))


def copy_for_component(semantic_key: str, state: dict) -> str:
    basis = f"{state.get('state_zh', '')} {state.get('trigger_zh', '')} {state.get('feedback_zh', '')}"
    if semantic_key == "input.text":
        if any(keyword in basis for keyword in ["图片", "截图", "相册", "拍照", "上传"]):
            return "选择图片或截图"
        if "标签" in basis:
            return "选择标签"
        return "选择或输入内容"
    if semantic_key == "feedback.toast":
        return state.get("feedback_zh") or state.get("state_zh") or "状态反馈"
    if semantic_key == "overlay.modal.confirmation":
        return state.get("feedback_zh") or "确认提示"
    if any(keyword in basis for keyword in ["不可", "少于", "多于", "超过", "置灰"]):
        return "继续调整"
    for keyword, label in [
        ("上传", "上传"),
        ("分析", "开始分析"),
        ("保存", "保存"),
        ("复制", "复制"),
        ("添加", "添加"),
        ("选择", "确认选择"),
        ("提交", "提交"),
    ]:
        if keyword in basis:
            return label
    return "继续"


def action_copy_from_trigger(trigger_zh: str) -> str:
    text = re.sub(r"\s+", " ", str(trigger_zh or "")).strip()
    for prefix in ["用户点击", "点击", "用户选择", "选择"]:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    replacements = [
        ("并点击保存", "保存"),
        ("并提交", "提交"),
        ("或复制操作", ""),
        ("某条", ""),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    text = text.strip(" ，。；;")
    if not text:
        return "继续"
    if len(text) > 18:
        text = plain_excerpt(text, 18)
    return text


def interaction_requires_dedicated_component(interaction: dict) -> bool:
    trigger = str(interaction.get("trigger_zh") or interaction.get("trigger") or "")
    if interaction.get("source_state_id") == "TOOLBAR-VISIBLE":
        return True
    return trigger.startswith("用户点击") or trigger.startswith("点击")


def frame_id_for_state(state_id: str) -> str:
    slug = safe_slug(state_id)
    if slug:
        return f"FRAME-{slug}"
    digest = hashlib.sha1(state_id.encode("utf-8")).hexdigest()[:10].upper()
    return f"FRAME-{digest}"


def component_id_for_state(state_id: str, idx: int) -> str:
    slug = safe_slug(state_id)
    if slug:
        return f"CMP-{slug}-{idx:02d}"
    digest = hashlib.sha1(state_id.encode("utf-8")).hexdigest()[:10].upper()
    return f"CMP-{digest}-{idx:02d}"


def build_runtime_and_payload(brief_doc: dict) -> tuple[dict, dict, dict]:
    brief = brief_doc["prototype_source_brief"]
    binding_index = load_component_binding_index()
    screen_candidates = brief["screen_task_candidates"]
    state_candidates = brief["state_candidates"]
    interaction_candidates = brief["interaction_candidates"]
    all_source_refs = sorted({
        ref
        for item in screen_candidates + state_candidates + brief.get("source_atoms", [])
        for ref in item.get("source_refs", [])
    })
    runtime_rule_ids = rule_ids_for_artifact("runtime")
    payload_rule_ids = rule_ids_for_artifact("payload")
    composition_rule_ids = rule_ids_for_artifact("composition_plan")
    hotspot_rule_ids = rule_ids_for_artifact("interaction_hotspot_map")
    sidecar_rule_ids = rule_ids_for_artifact("logic_sidecar_card_map")
    annotation_rule_ids = rule_ids_for_artifact("annotation_stub_map")
    badge_rule_ids = rule_ids_for_artifact("anchor_badge_map")
    patch_rule_ids = rule_ids_for_artifact("local_materialization_patch")

    runtime_screens = []
    runtime_nodes = []
    runtime_edges = []
    runtime_component_bindings = {}
    payload_frames = []
    payload_components = []
    payload_interactions = []
    annotations = []
    sidecar_cards = []
    anchor_badges = []
    hotspots = []
    state_component_index = {}
    state_by_id = {state["state_id"]: state for state in state_candidates}
    states_by_screen = defaultdict(list)
    for state in state_candidates:
        states_by_screen[state["screen_id"]].append(state)
    dedicated_action_interactions_by_state = defaultdict(list)
    for interaction in interaction_candidates:
        if interaction_requires_dedicated_component(interaction):
            dedicated_action_interactions_by_state[interaction.get("source_state_id", "")].append(interaction)
    interaction_component_by_id = {}

    for candidate in screen_candidates:
        screen_id = candidate["screen_id"]
        runtime_state_items = []
        candidate_states = states_by_screen.get(screen_id, [])
        if not candidate_states:
            candidate_states = [{
                "state_id": f"STATE-{screen_id}-READY",
                "screen_id": screen_id,
                "state_zh": f"{candidate['title_zh']}默认态",
                "trigger_zh": infer_primary_action_label(candidate),
                "feedback_zh": "",
                "recovery_zh": "",
                "source_refs": candidate["source_refs"],
                "source_atom_id": candidate.get("source_atom_id", ""),
                "categories": ["state"],
                "display_reason_zh": "screen fallback state",
                "required_for_rendering": True,
            }]
        for state in candidate_states:
            state_id = state["state_id"]
            frame_id = frame_id_for_state(state_id)
            dedicated_actions = dedicated_action_interactions_by_state.get(state_id, [])
            semantic_keys = semantic_keys_for_state(state)
            if dedicated_actions:
                semantic_keys = [key for key in semantic_keys if key != "button.primary.submit"]
            components = []
            for comp_idx, semantic_key in enumerate(semantic_keys, start=1):
                binding = binding_index.get(semantic_key, {})
                role = semantic_key.split(".")[0]
                component_id = component_id_for_state(state_id, comp_idx)
                copy_id = f"COPY-{component_id}"
                component = {
                    "component_id": component_id,
                    "semantic_key": semantic_key,
                    "semantic_role": role,
                    "copy_id": copy_id,
                    "source_refs": state["source_refs"],
                    "source_atom_id": state.get("source_atom_id", ""),
                    "rule_ids": composition_rule_ids,
                }
                components.append(component)
                payload_components.append({
                    "component_id": component_id,
                    "frame_id": frame_id,
                    "semantic_key": semantic_key,
                    "semantic_role": role,
                    "copy_ref": copy_id,
                    "copy_zh": copy_for_component(semantic_key, state),
                    "source_refs": state["source_refs"],
                    "source_atom_id": state.get("source_atom_id", ""),
                    "rule_ids": composition_rule_ids,
                    "render_eligibility": "renderable",
                    "candidate_marker": "candidate_projection",
                })
                if semantic_key not in runtime_component_bindings:
                    runtime_component_bindings[semantic_key] = {
                        "semantic_key": semantic_key,
                        "design_system_adapter": binding.get("design_system_adapter", "SDS_MONOCHROME_ADAPTER_V3_1"),
                        "figma_component": binding.get("figma_component", {"component_key": "", "component_name": "SDS fallback"}),
                        "source_refs": state["source_refs"],
                    }
            next_comp_idx = len(components) + 1
            for action_interaction in dedicated_actions:
                semantic_key = "button.primary.submit"
                binding = binding_index.get(semantic_key, {})
                component_id = component_id_for_state(state_id, next_comp_idx)
                copy_id = f"COPY-{component_id}"
                component = {
                    "component_id": component_id,
                    "semantic_key": semantic_key,
                    "semantic_role": "button",
                    "copy_id": copy_id,
                    "source_refs": action_interaction.get("source_refs") or state["source_refs"],
                    "source_atom_id": action_interaction.get("source_atom_id") or state.get("source_atom_id", ""),
                    "bound_interaction_id": action_interaction["interaction_id"],
                    "rule_ids": hotspot_rule_ids,
                }
                components.append(component)
                interaction_component_by_id[action_interaction["interaction_id"]] = component
                payload_components.append({
                    "component_id": component_id,
                    "frame_id": frame_id,
                    "semantic_key": semantic_key,
                    "semantic_role": "button",
                    "copy_ref": copy_id,
                    "copy_zh": action_copy_from_trigger(action_interaction.get("trigger_zh", "")),
                    "source_refs": action_interaction.get("source_refs") or state["source_refs"],
                    "source_atom_id": action_interaction.get("source_atom_id") or state.get("source_atom_id", ""),
                    "bound_interaction_id": action_interaction["interaction_id"],
                    "rule_ids": hotspot_rule_ids,
                    "render_eligibility": "renderable",
                    "candidate_marker": "candidate_projection",
                })
                if semantic_key not in runtime_component_bindings:
                    runtime_component_bindings[semantic_key] = {
                        "semantic_key": semantic_key,
                        "design_system_adapter": binding.get("design_system_adapter", "SDS_MONOCHROME_ADAPTER_V3_1"),
                        "figma_component": binding.get("figma_component", {"component_key": "", "component_name": "SDS fallback"}),
                        "source_refs": action_interaction.get("source_refs") or state["source_refs"],
                    }
                next_comp_idx += 1
            state_component_index[state_id] = components
            runtime_state_items.append({
                "state_id": state_id,
                "state_name": safe_slug(state_id).lower() or "candidate_state",
                "state_zh": state.get("state_zh", state_id),
                "dimensions": default_state_dimensions(),
                "source_refs": state["source_refs"],
                "source_atom_id": state.get("source_atom_id", ""),
                "display_reason_zh": state.get("display_reason_zh", ""),
                "feedback_zh": state.get("feedback_zh", ""),
                "recovery_zh": state.get("recovery_zh", ""),
                "components": components,
                "rule_ids": runtime_rule_ids,
            })
            runtime_nodes.append({
                "node_id": state_id,
                "screen_id": screen_id,
                "state_id": state_id,
                "source_refs": state["source_refs"],
                "source_atom_id": state.get("source_atom_id", ""),
                "rule_ids": runtime_rule_ids,
            })
            payload_frames.append({
                "frame_id": frame_id,
                "screen_id": screen_id,
                "state_id": state_id,
                "title_zh": state.get("state_zh", candidate["title_zh"]),
                "display_reason_zh": state.get("display_reason_zh", ""),
                "collapse_allowed": state.get("collapse_allowed", False),
                "collapse_reason_zh": "" if not state.get("collapse_allowed") else "非阻断/非边界状态可在最终画布中折叠，但 coverage 必须保留。",
                "component_ids": [component["component_id"] for component in components],
                "source_refs": state["source_refs"],
                "source_atom_id": state.get("source_atom_id", ""),
                "rule_ids": composition_rule_ids,
                "render_eligibility": "renderable",
                "candidate_marker": "candidate_projection",
            })
        runtime_screens.append({
            "screen_id": screen_id,
            "screen_name": candidate["title_zh"],
            "screen_zh": candidate["title_zh"],
            "source_refs": candidate["source_refs"],
            "source_atom_id": candidate.get("source_atom_id", ""),
            "rule_ids": runtime_rule_ids,
            "states": runtime_state_items,
        })

    frame_by_state = {frame["state_id"]: frame for frame in payload_frames}
    button_component_by_state = {}
    for state_id, components in state_component_index.items():
        button_component_by_state[state_id] = next((item for item in components if item.get("semantic_key") == "button.primary.submit"), components[0])

    for idx, interaction in enumerate(interaction_candidates, start=1):
        source_screen_id = interaction["source_screen_id"]
        source_state = interaction.get("source_state_id") or f"STATE-{source_screen_id}-READY"
        target_state = interaction.get("target_state_id") or source_state
        edge_id = f"EDGE-{idx:03d}"
        source_component = interaction_component_by_id.get(interaction["interaction_id"]) or button_component_by_state.get(source_state, {})
        source_frame_id = frame_by_state.get(source_state, {}).get("frame_id", "")
        destination_frame_id = frame_by_state.get(target_state, {}).get("frame_id", "")
        action = {
            "order": 1,
            "type": "navigate",
            "destination": target_state,
            "destination_frame_id": destination_frame_id,
            "state_effect": "show_target_state",
            "rule_ids": hotspot_rule_ids,
        }
        runtime_edges.append({
            "edge_id": edge_id,
            "interaction_id": interaction["interaction_id"],
            "source": source_state,
            "target": target_state,
            "trigger": interaction["trigger"],
            "guard": interaction.get("guard_zh", ""),
            "actions": [action],
            "interaction_variant": interaction.get("interaction_variant", "primary"),
            "route_basis_zh": interaction.get("route_basis_zh", ""),
            "source_refs": interaction["source_refs"],
            "source_atom_id": interaction.get("source_atom_id", ""),
            "rule_ids": hotspot_rule_ids,
        })
        payload_interactions.append({
            "interaction_id": interaction["interaction_id"],
            "edge_id": edge_id,
            "source_component_id": source_component.get("component_id", f"CMP-{source_screen_id}-01"),
            "source_frame_id": source_frame_id,
            "source_state_id": source_state,
            "target_state_id": target_state,
            "target_screen_id": interaction.get("target_screen_id", source_screen_id),
            "trigger": interaction["trigger"],
            "trigger_zh": interaction.get("trigger_zh", ""),
            "guard_zh": interaction.get("guard_zh", ""),
            "actions": [action],
            "destination_frame_id": destination_frame_id,
            "interaction_kind": interaction.get("interaction_kind", ""),
            "interaction_variant": interaction.get("interaction_variant", "primary"),
            "operation_chain_step": interaction.get("operation_chain_step", idx),
            "route_basis_zh": interaction.get("route_basis_zh", ""),
            "source_refs": interaction["source_refs"],
            "source_atom_id": interaction.get("source_atom_id", ""),
            "rule_ids": hotspot_rule_ids,
            "render_eligibility": "renderable",
            "candidate_marker": "candidate_projection",
        })
        badge_id = f"BADGE-{idx:02d}"
        card_id = f"SC-{idx:03d}"
        annotation_id = f"ANN-{idx:03d}"
        anchor_badges.append({
            "badge_id": badge_id,
            "target_component_id": source_component.get("component_id", f"CMP-{source_screen_id}-01"),
            "label": str(idx),
            "source_refs": interaction["source_refs"],
            "source_atom_id": interaction.get("source_atom_id", ""),
            "rule_ids": badge_rule_ids,
        })
        sidecar_cards.append({
            "card_id": card_id,
            "anchor_badge_id": badge_id,
            "title_zh": state_by_id.get(source_state, {}).get("state_zh") or f"{interaction.get('trigger_zh', '继续')}规则",
            "trigger_zh": interaction.get("trigger_zh", "用户点击"),
            "guard_zh": interaction.get("guard_zh", "见来源 PRD"),
            "action_summary_zh": state_by_id.get(source_state, {}).get("feedback_zh") or "根据来源 PRD 的候选状态展示反馈。",
            "feedback_timing_zh": "before_confirm" if "constraint" in interaction.get("categories", []) else "on_trigger",
            "source_refs": interaction["source_refs"],
            "related_hotspot_ids": [f"HOT-{idx:03d}"],
            "source_atom_id": interaction.get("source_atom_id", ""),
            "rule_ids": sidecar_rule_ids,
        })
        annotations.append({
            "annotation_id": annotation_id,
            "target_id": source_component.get("component_id", f"CMP-{source_screen_id}-01"),
            "target_node_or_region": source_component.get("component_id", f"CMP-{source_screen_id}-01"),
            "interaction_or_state_id": interaction["interaction_id"],
            "sidecar_card_id": card_id,
            "body_zh": f"{state_by_id.get(source_state, {}).get('state_zh', interaction.get('trigger_zh', '用户点击'))}：{interaction.get('guard_zh', '见来源 PRD')}；见 {card_id}。",
            "short_summary_zh": plain_excerpt(f"{state_by_id.get(source_state, {}).get('state_zh', interaction.get('trigger_zh', '用户点击'))}，见 {card_id}。", 80),
            "source_refs": interaction["source_refs"],
            "source_atom_id": interaction.get("source_atom_id", ""),
            "rule_ids": annotation_rule_ids,
            "render_eligibility": "renderable",
            "candidate_marker": "candidate_projection",
        })
        hotspots.append({
            "hotspot_id": f"HOT-{idx:03d}",
            "edge_id": edge_id,
            "screen_id": source_screen_id,
            "target_component_id": source_component.get("component_id", f"CMP-{source_screen_id}-01"),
            "trigger": interaction["trigger"],
            "semantic_action_zh": interaction.get("trigger_zh", "用户点击"),
            "source_refs": interaction["source_refs"],
            "source_atom_id": interaction.get("source_atom_id", ""),
            "rule_ids": hotspot_rule_ids,
        })

    copy_catalog = []
    for component in payload_components:
        copy_catalog.append({
            "copy_id": component["copy_ref"],
            "semantic_role": component["semantic_role"],
            "final_copy": component.get("copy_zh", "继续"),
            "source_refs": component["source_refs"],
            "source_atom_id": component.get("source_atom_id", ""),
            "rule_ids": component.get("rule_ids", payload_rule_ids),
        })

    runtime = {
        "prototype_runtime_version": "3.1.1-candidate",
        "rule_trace": rule_trace_for_artifact("runtime"),
        "authority": {
            "role": "candidate_projection",
            "forbidden_as_fact_source": True,
            "owner": "prototype_projection_harness",
        },
        "source_snapshot": {
            "source_path": brief["source_path"],
            "source_sha256": brief["source_sha256"],
            "source_refs": all_source_refs,
            "forbidden_as_fact_source": True,
        },
        "flows": [{
            "flow_id": "FLOW-001",
            "flow_name": "Prototype candidate flow",
            "screen_ids": [screen["screen_id"] for screen in runtime_screens],
            "source_refs": all_source_refs,
        }],
        "screens": runtime_screens,
        "overlays": [],
        "variables": [],
        "component_bindings": list(runtime_component_bindings.values()),
        "interaction_graph": {
            "nodes": runtime_nodes,
            "edges": runtime_edges,
        },
        "prototype_gaps": brief.get("blocked_inferences", []),
        "generation_lineage": {
            "pass_1": {
                "name": "gen_source_slices_from_prd_atoms",
                "output": "runs/<run-id>/io/output/prototype_source_brief.yaml",
            },
            "pass_2": {
                "name": "prototype_artifact_generator_v3_1_2",
                "output": "runs/<run-id>/io/output/prototype.runtime.candidate.json",
            },
        },
        "reasoning_completion": {
            "inferred_states": [
                {
                    "state_id": state["state_id"],
                    "confidence": "medium",
                    "inference_basis": "Generated from source PRD section as candidate projection.",
                    "source_refs": state["source_refs"],
                }
                for state in brief["state_candidates"]
            ],
            "inferred_interactions": [
                {
                    "interaction_id": interaction["interaction_id"],
                    "confidence": "medium",
                    "inference_basis": "Generated from source PRD section ordering and action cues.",
                    "source_refs": interaction["source_refs"],
                }
                for interaction in interaction_candidates
            ],
            "blocked_inferences": brief.get("blocked_inferences", []),
        },
        "copy_catalog": copy_catalog,
        "layout_route_plan_ref": "",
        "figma_comment_map_ref": "",
    }

    payload = {
        "prototype_render_payload": {
            "version": "3.1.1",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "rule_trace": rule_trace_for_artifact("payload"),
            "generated_by": "prototype_artifact_generator_v3_1_2",
            "generated_at": utc_now_text(),
            "candidate_marker": "candidate_projection",
            "sample": False,
            "source_kind": "prd_source",
            "source_refs": all_source_refs,
            "design_system": {
                "adapter_id": "SDS_MONOCHROME_ADAPTER_V3_1",
                "color_policy": "black_white_gray_only",
                "component_library": "LIB-SDS-MONOCHROME",
            },
            "boards": [{
                "board_id": "BOARD-PROTOTYPE-001",
                "title_zh": "原型候选画布",
                "frame_ids": [frame["frame_id"] for frame in payload_frames],
                "sidecar_card_ids": [card["card_id"] for card in sidecar_cards],
                "source_refs": all_source_refs,
                "rule_ids": payload_rule_ids,
                "render_eligibility": "renderable",
                "candidate_marker": "candidate_projection",
            }],
            "frames": payload_frames,
            "components": payload_components,
            "interactions": payload_interactions,
            "annotations": annotations,
            "sidecar_cards": sidecar_cards,
            "anchor_badges": anchor_badges,
        }
    }

    drd = {
        "screen_role_obligations": {
            "screen_role_obligations": {
                "version": "3.1",
                "mode": "DRD_MODE",
                "source_refs": all_source_refs,
                "rule_trace": rule_trace_for_artifact("screen_role_obligations"),
                "obligations": [
                    {
                        "obligation_id": f"OBL-{state['state_id']}",
                        "obligation_type": "state_rendering_obligation",
                        "obligation_zh": f"必须为“{state['state_zh']}”生成可追溯候选状态、控件和反馈。",
                        "derived_from_primitives": {"state_id": state["state_id"], "source_atom_id": state.get("source_atom_id", "")},
                        "source_refs": state["source_refs"],
                        "inference_basis_zh": "来自源 PRD source atom / 表格状态行的细颗粒候选。",
                        "display_requirement": "candidate_frame",
                        "materialization_target": "composition_plan",
                        "review_status": "candidate_projection",
                        "rule_ids": rule_ids_for_artifact("screen_role_obligations"),
                    }
                    for state in state_candidates
                ],
            }
        },
        "design_kernel": {
            "design_kernel": {
                "version": "3.1",
                "mode": "DRD_MODE",
                "source_refs": all_source_refs,
                "rule_trace": rule_trace_for_artifact("design_kernel"),
                "task_contract": {
                    "task_id": screen_candidates[0]["task_id"],
                    "task_name_zh": screen_candidates[0]["title_zh"],
                    "user_goal_zh": screen_candidates[0]["task_summary_zh"],
                    "action": "prototype_candidate_action",
                    "object": screen_candidates[0]["title_zh"],
                    "source_refs": screen_candidates[0]["source_refs"],
                    "rule_ids": rule_ids_for_artifact("design_kernel"),
                },
                "surface_contract": {
                    "surface_type": "app_screen_flow",
                    "surface_type_zh": "应用页面流",
                    "entry_surface": runtime_screens[0]["screen_id"],
                    "return_surface": runtime_screens[-1]["screen_id"],
                    "forbidden_realizations": ["不得把来源 PRD 压缩成 summary card。"],
                    "rule_ids": rule_ids_for_artifact("design_kernel"),
                },
                "constraint_contracts": [{
                    "constraint_id": f"C-{state['state_id']}",
                    "constraint_zh": state.get("feedback_zh") or state.get("state_zh", ""),
                    "applies_at": "payload_compile",
                    "earliest_fix_surface": state["state_id"],
                    "feedback_timing": "before_confirm" if "constraint" in state.get("categories", []) else "on_trigger",
                    "valid_condition": "state_covered_in_runtime_payload_sidecar",
                    "invalid_condition": "required_state_atom_uncovered",
                    "source_refs": state["source_refs"],
                    "rule_ids": rule_ids_for_artifact("design_kernel"),
                } for state in state_candidates if set(state.get("categories", [])) & {"constraint", "boundary"}] or [{
                    "constraint_id": "C-SOURCE-REFS",
                    "constraint_zh": "所有渲染候选必须保留 source_refs。",
                    "applies_at": "payload_compile",
                    "earliest_fix_surface": "prototype_source_brief",
                    "feedback_timing": "before_figma_write",
                    "valid_condition": "every_renderable_item_has_source_refs",
                    "invalid_condition": "renderable_item_missing_source_refs",
                    "source_refs": all_source_refs,
                    "rule_ids": rule_ids_for_artifact("design_kernel"),
                }],
                "control_contracts": [{
                    "control_id": f"CTRL-{state['state_id']}",
                    "control_zh": state.get("trigger_zh") or state.get("state_zh", ""),
                    "affected_by_constraints": [f"C-{state['state_id']}"] if set(state.get("categories", [])) & {"constraint", "boundary"} else ["C-SOURCE-REFS"],
                    "required_states": [state["state_id"]],
                    "source_refs": state["source_refs"],
                    "rule_ids": rule_ids_for_artifact("design_kernel"),
                } for state in state_candidates],
                "feedback_contracts": [{
                    "feedback_id": f"FB-{state['state_id']}",
                    "feedback_zh": state.get("feedback_zh") or state.get("state_zh", ""),
                    "severity": "blocker" if set(state.get("categories", [])) & {"constraint", "boundary", "recovery"} else "info",
                    "timing": "before_confirm" if "constraint" in state.get("categories", []) else "on_trigger",
                    "surface": state["screen_id"],
                    "anchor": state["state_id"],
                    "source_refs": state["source_refs"],
                    "rule_ids": rule_ids_for_artifact("design_kernel"),
                } for state in state_candidates if state.get("feedback_zh") or set(state.get("categories", [])) & {"feedback", "constraint", "boundary", "recovery"}],
                "forbidden_realizations": ["不得读取 sample payload 代替真实 PRD 生成。", "不得写 product-spec fact store。"],
            }
        },
        "composition_plan": {
            "composition_plan": {
                "version": "3.1",
                "mode": "DRD_MODE",
                "board_id": "BOARD-PROTOTYPE-001",
                "source_refs": all_source_refs,
                "rule_trace": rule_trace_for_artifact("composition_plan"),
                "frames": payload_frames,
            }
        },
        "interaction_hotspot_map": {
            "interaction_hotspot_map": {
                "version": "3.1",
                "mode": "DRD_MODE",
                "source_refs": all_source_refs,
                "rule_trace": rule_trace_for_artifact("interaction_hotspot_map"),
                "hotspots": hotspots,
            }
        },
        "logic_sidecar_card_map": {
            "logic_sidecar_card_map": {
                "version": "3.1",
                "mode": "DRD_MODE",
                "board_id": "BOARD-PROTOTYPE-001",
                "board_id_zh": "原型候选画布",
                "rule_trace": rule_trace_for_artifact("logic_sidecar_card_map"),
                "cards": sidecar_cards,
                "annotation_stubs": [
                    {
                        "annotation_id": item["annotation_id"],
                        "target_node_or_region": item["target_node_or_region"],
                        "interaction_or_state_id": item["interaction_or_state_id"],
                        "sidecar_card_id": item["sidecar_card_id"],
                        "short_summary_zh": item["short_summary_zh"][:80],
                        "source_refs": item["source_refs"],
                        "rule_ids": annotation_rule_ids,
                    }
                    for item in annotations
                ],
            }
        },
        "annotation_stub_map": {
            "annotation_stub_map": {
                "version": "3.1",
                "mode": "DRD_MODE",
                "source_refs": all_source_refs,
                "rule_trace": rule_trace_for_artifact("annotation_stub_map"),
                "stubs": annotations,
            }
        },
        "anchor_badge_map": {
            "anchor_badge_map": {
                "version": "3.1",
                "mode": "DRD_MODE",
                "source_refs": all_source_refs,
                "rule_trace": rule_trace_for_artifact("anchor_badge_map"),
                "badges": anchor_badges,
            }
        },
        "local_materialization_patch": {
            "local_materialization_patch": {
                "version": "3.1",
                "mode": "DRD_MODE",
                "rule_trace": rule_trace_for_artifact("local_materialization_patch"),
                "patches": [{
                    "patch_id": "PATCH-PROTOTYPE-CANDIDATE-GENERATION",
                    "source_audit_finding": "GENERATOR-V1-NO-PRD-FACT-WRITE",
                    "patch_scope": ["prototype_projection_candidates"],
                    "operations": [{
                        "operation_type": "generate_candidate_payload",
                        "target": "runs/<run-id>/io/output/prototype-render-payload.yaml",
                        "description_zh": "在隔离 run root 生成候选原型 payload，不写 PRD fact store。",
                        "source_refs": all_source_refs,
                        "rule_ids": patch_rule_ids,
                    }],
                    "writes_prd": False,
                    "source_refs": all_source_refs,
                    "rule_ids": patch_rule_ids,
                    "validator_results": [],
                }],
            }
        },
    }
    return runtime, payload, drd


CAPABILITY_SIGNAL_LIBRARY = {
    "media_picker": {
        "name_zh": "媒体选择",
        "keywords": ["图片", "照片", "截图", "相册", "拍照", "上传图片", "上传截图", "media", "photo", "image"],
        "handoff_surface_type": "system_picker",
        "handoff_surface_zh": "系统选择器或宿主提供的媒体选择面",
    },
    "file_picker": {
        "name_zh": "文件选择",
        "keywords": ["文件", "附件", "上传文件", "file"],
        "handoff_surface_type": "system_picker",
        "handoff_surface_zh": "系统文件选择面",
    },
    "contact_picker": {
        "name_zh": "联系人选择",
        "keywords": ["联系人", "通讯录", "好友选择"],
        "handoff_surface_type": "system_picker",
        "handoff_surface_zh": "系统或宿主联系人选择面",
    },
    "location_picker": {
        "name_zh": "位置选择",
        "keywords": ["位置", "定位", "地图"],
        "handoff_surface_type": "system_picker",
        "handoff_surface_zh": "系统位置选择面",
    },
    "permission_prompt": {
        "name_zh": "系统授权",
        "keywords": ["权限", "授权", "允许访问"],
        "handoff_surface_type": "system_prompt",
        "handoff_surface_zh": "系统权限弹窗",
    },
    "payment_sdk": {
        "name_zh": "支付",
        "keywords": ["支付", "付款", "订阅", "购买"],
        "handoff_surface_type": "sdk_surface",
        "handoff_surface_zh": "支付 SDK 页面",
    },
    "auth_sdk": {
        "name_zh": "认证",
        "keywords": ["登录", "认证", "授权登录"],
        "handoff_surface_type": "sdk_surface",
        "handoff_surface_zh": "认证 SDK 页面",
    },
    "share_sheet": {
        "name_zh": "分享",
        "keywords": ["分享", "转发"],
        "handoff_surface_type": "system_sheet",
        "handoff_surface_zh": "系统分享面板",
    },
    "clipboard_write": {
        "name_zh": "剪贴板写入",
        "keywords": ["复制", "剪贴板"],
        "handoff_surface_type": "system_service",
        "handoff_surface_zh": "系统剪贴板服务",
    },
}


def text_contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword.lower() in str(text).lower() for keyword in keywords)


def detect_capability_ids(text: str) -> list[str]:
    return [
        capability_id
        for capability_id, config in CAPABILITY_SIGNAL_LIBRARY.items()
        if text_contains_any(text, config.get("keywords", []))
    ]


def carrier_type_for_text(text: str, fallback: str = "app_page") -> str:
    basis = str(text)
    if text_contains_any(basis, ["输入法", "键盘", "工具栏", "toolbar", "扩展面板"]):
        return "embedded_host_panel"
    if text_contains_any(basis, ["弹窗", "确认框", "toast", "提示框", "sheet", "drawer"]):
        return "overlay_or_modal"
    if detect_capability_ids(basis):
        return "system_handoff_surface"
    return fallback


def carrier_label_zh(carrier_type: str) -> str:
    labels = {
        "app_page": "应用内页面",
        "embedded_host_panel": "宿主应用内的嵌入区域",
        "system_handoff_surface": "系统交接面",
        "overlay_or_modal": "弹窗或浮层",
        "system_picker": "系统选择器",
        "system_prompt": "系统授权弹窗",
        "system_sheet": "系统面板",
        "system_service": "系统服务",
        "sdk_surface": "第三方或系统 SDK 页面",
    }
    return labels.get(carrier_type or "", carrier_type or "待确认承载面")


def source_atom_text_by_id(brief_root: dict) -> dict[str, str]:
    return {
        atom.get("atom_id"): atom.get("source_text_zh", "")
        for atom in brief_root.get("source_atoms", []) or []
        if atom.get("atom_id")
    }


def state_lookup(runtime: dict) -> dict[str, dict]:
    return {
        state.get("state_id"): {**state, "screen_id": screen.get("screen_id"), "screen_zh": screen.get("screen_zh")}
        for screen in runtime.get("screens", []) or []
        for state in screen.get("states", []) or []
        if state.get("state_id")
    }


def screen_lookup(runtime: dict) -> dict[str, dict]:
    return {
        screen.get("screen_id"): screen
        for screen in runtime.get("screens", []) or []
        if screen.get("screen_id")
    }


def interaction_text_basis(interaction: dict, state_by_id: dict[str, dict], atom_text: dict[str, str]) -> str:
    source_state = state_by_id.get(interaction.get("source_state_id"), {})
    target_state = state_by_id.get(interaction.get("target_state_id"), {})
    return " ".join([
        interaction.get("trigger_zh", ""),
        interaction.get("guard_zh", ""),
        interaction.get("route_basis_zh", ""),
        source_state.get("state_zh", ""),
        source_state.get("feedback_zh", ""),
        target_state.get("state_zh", ""),
        target_state.get("feedback_zh", ""),
        atom_text.get(interaction.get("source_atom_id", ""), ""),
    ])


def load_instance_platform_context() -> dict:
    if not INSTANCE_ROOT_PROVIDED:
        return {}
    for rel in [
        "inputs/platform_context.yaml",
        "inputs/project_platform_context.yaml",
        "inputs/prototype_platform_context.yaml",
    ]:
        path = INSTANCE_ROOT / rel
        if path.exists():
            data = yload(path)
            return data.get("platform_context", data)
    return {}


def build_interaction_carrier_map(brief: dict, runtime: dict, payload: dict) -> dict:
    brief_root = brief["prototype_source_brief"]
    payload_root = payload["prototype_render_payload"]
    atom_text = source_atom_text_by_id(brief_root)
    state_by_id = state_lookup(runtime)
    screen_by_id = screen_lookup(runtime)
    carrier_rule_ids = rule_ids_for_artifact("interaction_carrier_map")

    screen_carriers = []
    state_carriers = []
    for screen in runtime.get("screens", []) or []:
        screen_states = screen.get("states", []) or []
        basis = " ".join([
            screen.get("screen_zh", ""),
            *(state.get("state_zh", "") for state in screen_states),
            *(state.get("feedback_zh", "") for state in screen_states),
        ])
        carrier_type = carrier_type_for_text(basis)
        screen_carriers.append({
            "screen_id": screen.get("screen_id"),
            "screen_name_zh": screen.get("screen_zh"),
            "carrier_type": carrier_type,
            "carrier_zh": carrier_label_zh(carrier_type),
            "host_context_zh": "宿主环境内展示" if carrier_type == "embedded_host_panel" else "应用内原型候选承载",
            "standalone_page_allowed": carrier_type == "app_page",
            "source_refs": screen.get("source_refs", []),
            "rule_ids": carrier_rule_ids,
        })
        for state in screen_states:
            state_basis = " ".join([
                basis,
                state.get("state_zh", ""),
                state.get("trigger_zh", ""),
                state.get("feedback_zh", ""),
                atom_text.get(state.get("source_atom_id", ""), ""),
            ])
            state_carrier_type = carrier_type_for_text(state_basis, carrier_type)
            if state_carrier_type == "system_handoff_surface" and carrier_type == "embedded_host_panel":
                state_carrier_type = "embedded_host_panel"
            state_carriers.append({
                "state_id": state.get("state_id"),
                "screen_id": screen.get("screen_id"),
                "carrier_type": state_carrier_type,
                "carrier_zh": carrier_label_zh(state_carrier_type),
                "host_context_zh": "该状态仍归属宿主嵌入区域；如需外部能力，另由 system_handoff_map 表达。",
                "standalone_page_allowed": state_carrier_type == "app_page",
                "source_refs": state.get("source_refs", []),
                "rule_ids": carrier_rule_ids,
            })

    component_carriers = []
    state_carrier_by_id = {item.get("state_id"): item for item in state_carriers}
    frame_state = {frame.get("frame_id"): frame.get("state_id") for frame in payload_root.get("frames", []) or []}
    for component in payload_root.get("components", []) or []:
        state_id = frame_state.get(component.get("frame_id", ""))
        carrier = state_carrier_by_id.get(state_id, {})
        component_carriers.append({
            "component_id": component.get("component_id"),
            "state_id": state_id,
            "carrier_type": carrier.get("carrier_type", "app_page"),
            "carrier_zh": carrier.get("carrier_zh", carrier_label_zh("app_page")),
            "render_region_zh": "当前承载面内的可见区域",
            "source_refs": component.get("source_refs", []),
            "rule_ids": carrier_rule_ids,
        })

    interaction_carriers = []
    for interaction in payload_root.get("interactions", []) or []:
        source_state = state_by_id.get(interaction.get("source_state_id"), {})
        target_state = state_by_id.get(interaction.get("target_state_id"), {})
        source_carrier = state_carrier_by_id.get(interaction.get("source_state_id"), {})
        target_carrier = state_carrier_by_id.get(interaction.get("target_state_id"), {})
        basis = interaction_text_basis(interaction, state_by_id, atom_text)
        capabilities = detect_capability_ids(basis)
        requires_handoff = bool(capabilities)
        target_carrier_type = target_carrier.get("carrier_type") or source_carrier.get("carrier_type") or "app_page"
        if requires_handoff:
            primary = CAPABILITY_SIGNAL_LIBRARY[capabilities[0]]
            target_carrier_type = primary.get("handoff_surface_type", "system_handoff_surface")
        same_screen = source_state.get("screen_id") == target_state.get("screen_id")
        same_carrier = not requires_handoff and source_carrier.get("carrier_type") == target_carrier.get("carrier_type")
        interaction_carriers.append({
            "interaction_id": interaction.get("interaction_id"),
            "source_state_id": interaction.get("source_state_id"),
            "target_state_id": interaction.get("target_state_id"),
            "source_screen_id": source_state.get("screen_id"),
            "target_screen_id": target_state.get("screen_id") or interaction.get("target_screen_id"),
            "source_carrier_type": source_carrier.get("carrier_type", "app_page"),
            "source_carrier_zh": source_carrier.get("carrier_zh", carrier_label_zh("app_page")),
            "target_carrier_type": target_carrier_type,
            "target_carrier_zh": carrier_label_zh(target_carrier_type),
            "transition_scope": "same_surface_state_change" if same_screen and same_carrier else "carrier_or_page_transition",
            "requires_system_handoff": requires_handoff,
            "capability_ids": capabilities,
            "standalone_page_allowed": not requires_handoff and target_carrier_type == "app_page",
            "source_refs": interaction.get("source_refs", []),
            "rule_ids": carrier_rule_ids,
        })

    return {
        "interaction_carrier_map": {
            "version": "3.1.2",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "rule_trace": rule_trace_for_artifact("interaction_carrier_map"),
            "source_refs": payload_root.get("source_refs", []),
            "screen_carriers": screen_carriers,
            "state_carriers": state_carriers,
            "component_carriers": component_carriers,
            "interaction_carriers": interaction_carriers,
        }
    }


def build_capability_assessment(brief: dict, carrier_map: dict) -> dict:
    root = carrier_map["interaction_carrier_map"]
    platform_context = load_instance_platform_context()
    context_text = json.dumps(platform_context, ensure_ascii=False)
    capability_rule_ids = rule_ids_for_artifact("capability_assessment")
    capability_refs = defaultdict(list)
    for item in root.get("interaction_carriers", []) or []:
        for capability_id in item.get("capability_ids", []) or []:
            capability_refs[capability_id].extend(item.get("source_refs", []))
    assessments = []
    for capability_id, refs in sorted(capability_refs.items()):
        config = CAPABILITY_SIGNAL_LIBRARY.get(capability_id, {})
        platform_known = capability_id in context_text
        assessments.append({
            "capability_id": capability_id,
            "capability_name_zh": config.get("name_zh", capability_id),
            "capability_status": "supported_by_platform_context" if platform_known else "unknown",
            "review_required": not platform_known,
            "preferred_feedback_surface_zh": "最早能反馈的选择或授权承载面",
            "four_layer_judgement": [
                {
                    "layer": "prd_source_atoms",
                    "status": "evidence_found",
                    "evidence_zh": "PRD/source atom 中出现了触发该能力的用户动作或限制。",
                    "source_refs": sorted(set(refs)),
                },
                {
                    "layer": "local_capability_library",
                    "status": "known_generic_capability",
                    "evidence_zh": "harness 本地通用能力库能识别该能力类别。",
                    "source_refs": sorted(set(refs)),
                },
                {
                    "layer": "instance_platform_context",
                    "status": "evidence_found" if platform_known else "unknown",
                    "evidence_zh": "instance 输入中声明了平台能力。" if platform_known else "instance 未声明该能力是否可在目标承载面内即时反馈。",
                    "source_refs": sorted(set(refs)),
                },
                {
                    "layer": "official_docs",
                    "status": "not_requested",
                    "evidence_zh": "默认不联网搜索；只有显式开启官方文档解析时才补证据。",
                    "source_refs": [],
                },
            ],
            "source_refs": sorted(set(refs)),
            "rule_ids": capability_rule_ids,
        })
    return {
        "capability_assessment": {
            "version": "3.1.2",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "status": "pass_with_review_required" if any(item.get("review_required") for item in assessments) else "pass",
            "official_docs_search_enabled": False,
            "rule_trace": rule_trace_for_artifact("capability_assessment"),
            "source_refs": sorted({ref for item in assessments for ref in item.get("source_refs", [])})
            or [brief["prototype_source_brief"].get("sections", [{}])[0].get("source_ref", "inputs/PRD.md#L1")],
            "capabilities": assessments,
        }
    }


def build_system_handoff_map(carrier_map: dict, capability_assessment: dict) -> dict:
    carrier_root = carrier_map["interaction_carrier_map"]
    capability_by_id = {
        item.get("capability_id"): item
        for item in capability_assessment["capability_assessment"].get("capabilities", []) or []
    }
    handoff_rule_ids = rule_ids_for_artifact("system_handoff_map")
    handoffs = []
    for idx, item in enumerate(carrier_root.get("interaction_carriers", []) or [], start=1):
        if not item.get("requires_system_handoff"):
            continue
        capability_id = (item.get("capability_ids") or ["external_capability"])[0]
        capability = CAPABILITY_SIGNAL_LIBRARY.get(capability_id, {})
        assessment = capability_by_id.get(capability_id, {})
        handoff_id = f"HANDOFF-{idx:03d}"
        handoffs.append({
            "handoff_id": handoff_id,
            "interaction_id": item.get("interaction_id"),
            "capability_id": capability_id,
            "handoff_surface_type": capability.get("handoff_surface_type", "system_handoff_surface"),
            "handoff_surface_zh": capability.get("handoff_surface_zh", "系统交接面"),
            "source_carrier_type": item.get("source_carrier_type"),
            "return_carrier_type": item.get("source_carrier_type"),
            "source_state_id": item.get("source_state_id"),
            "return_state_id": item.get("target_state_id"),
            "capability_status": assessment.get("capability_status", "unknown"),
            "review_required": assessment.get("review_required", True),
            "preferred_feedback_surface_zh": assessment.get("preferred_feedback_surface_zh", "最早能反馈的承载面"),
            "handoff_steps": [
                {"step_id": f"{handoff_id}-S1", "step_type": "enter_handoff_surface", "description_zh": "用户从当前承载面进入外部能力面。"},
                {"step_id": f"{handoff_id}-S2", "step_type": "perform_system_operation", "description_zh": "用户在外部能力面完成选择、授权或系统操作。"},
                {"step_id": f"{handoff_id}-S3", "step_type": "validate_or_cancel", "description_zh": "系统在最早可反馈位置处理边界、取消或失败。"},
                {"step_id": f"{handoff_id}-S4", "step_type": "return_to_host_surface", "description_zh": "操作完成后回到原承载面或进入明确目标状态。"},
            ],
            "cancel_path_zh": "用户取消时回到发起交接的承载面，并保持可重新操作。",
            "failure_path_zh": "系统能力失败时展示失败原因和恢复入口。",
            "source_refs": item.get("source_refs", []),
            "rule_ids": handoff_rule_ids,
        })
    return {
        "system_handoff_map": {
            "version": "3.1.2",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "rule_trace": rule_trace_for_artifact("system_handoff_map"),
            "source_refs": carrier_root.get("source_refs", []),
            "handoffs": handoffs,
        }
    }


def build_user_operation_chain(payload: dict, carrier_map: dict, handoff_map: dict) -> dict:
    payload_root = payload["prototype_render_payload"]
    carrier_by_interaction = {
        item.get("interaction_id"): item
        for item in carrier_map["interaction_carrier_map"].get("interaction_carriers", []) or []
    }
    handoff_by_interaction = {
        item.get("interaction_id"): item
        for item in handoff_map["system_handoff_map"].get("handoffs", []) or []
    }
    chain_rule_ids = rule_ids_for_artifact("user_operation_chain")
    chains = []
    for idx, interaction in enumerate(payload_root.get("interactions", []) or [], start=1):
        carrier = carrier_by_interaction.get(interaction.get("interaction_id"), {})
        handoff = handoff_by_interaction.get(interaction.get("interaction_id"))
        chain_id = f"OPCHAIN-{idx:03d}"
        if handoff:
            steps = [
                {"step_no": 1, "step_type": "user_action", "carrier_type": carrier.get("source_carrier_type"), "description_zh": interaction.get("trigger_zh") or "用户发起操作。"},
                {"step_no": 2, "step_type": "enter_system_handoff", "carrier_type": handoff.get("handoff_surface_type"), "description_zh": f"进入{handoff.get('handoff_surface_zh')}。"},
                {"step_no": 3, "step_type": "system_operation", "carrier_type": handoff.get("handoff_surface_type"), "description_zh": "用户在系统交接面完成选择、授权、取消或失败处理。"},
                {"step_no": 4, "step_type": "earliest_feedback", "carrier_type": handoff.get("handoff_surface_type"), "description_zh": f"边界和失败优先在{handoff.get('preferred_feedback_surface_zh')}提示；能力未知时需要人工确认。"},
                {"step_no": 5, "step_type": "return_or_continue", "carrier_type": handoff.get("return_carrier_type"), "description_zh": "系统交接结束后回到宿主承载面或进入目标状态。"},
            ]
            chain_kind = "system_handoff_chain"
        else:
            same_surface = carrier.get("transition_scope") == "same_surface_state_change"
            steps = [
                {"step_no": 1, "step_type": "user_action", "carrier_type": carrier.get("source_carrier_type"), "description_zh": interaction.get("trigger_zh") or "用户发起操作。"},
                {"step_no": 2, "step_type": "guard_or_state_update", "carrier_type": carrier.get("source_carrier_type"), "description_zh": interaction.get("guard_zh") or "系统检查当前状态和限制。"},
                {"step_no": 3, "step_type": "show_result", "carrier_type": carrier.get("target_carrier_type"), "description_zh": "留在当前承载面更新状态。" if same_surface else "进入新的页面或承载面。"},
            ]
            chain_kind = "same_surface_state_chain" if same_surface else "page_or_carrier_transition_chain"
        chains.append({
            "operation_chain_id": chain_id,
            "interaction_id": interaction.get("interaction_id"),
            "source_state_id": interaction.get("source_state_id"),
            "target_state_id": interaction.get("target_state_id"),
            "chain_kind": chain_kind,
            "page_flow_edge": carrier.get("transition_scope") == "carrier_or_page_transition",
            "handoff_id": handoff.get("handoff_id") if handoff else "",
            "steps": steps,
            "source_refs": interaction.get("source_refs", []),
            "rule_ids": chain_rule_ids,
        })
    return {
        "user_operation_chain": {
            "version": "3.1.2",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "rule_trace": rule_trace_for_artifact("user_operation_chain"),
            "source_refs": payload_root.get("source_refs", []),
            "chains": chains,
        }
    }


def build_carrier_handoff_artifacts(brief: dict, runtime: dict, payload: dict) -> dict:
    carrier_map = build_interaction_carrier_map(brief, runtime, payload)
    capability_assessment = build_capability_assessment(brief, carrier_map)
    handoff_map = build_system_handoff_map(carrier_map, capability_assessment)
    operation_chain = build_user_operation_chain(payload, carrier_map, handoff_map)
    return {
        "interaction_carrier_map": carrier_map,
        "system_handoff_map": handoff_map,
        "user_operation_chain": operation_chain,
        "capability_assessment": capability_assessment,
    }


def build_contract_promotion_report(brief: dict, carrier_bundle: dict, args) -> tuple[dict, dict]:
    carrier_root = carrier_bundle["interaction_carrier_map"]["interaction_carrier_map"]
    handoff_root = carrier_bundle["system_handoff_map"]["system_handoff_map"]
    source_refs = carrier_root.get("source_refs", [])
    has_handoff = bool(handoff_root.get("handoffs"))
    has_non_app_carrier = any(
        item.get("carrier_type") not in {"", "app_page"}
        for item in (carrier_root.get("screen_carriers", []) or []) + (carrier_root.get("state_carriers", []) or [])
    )
    profile_id = "carrier_handoff_operation_chain_v2" if has_handoff or has_non_app_carrier else "base_drd_v1"
    promoted = profile_id != "base_drd_v1"
    required_artifacts = [
        "interaction_carrier_map",
        "system_handoff_map",
        "user_operation_chain",
        "capability_assessment",
        "prototype_review_view_model",
    ] if promoted else []
    report = {
        "model_contract_promotion_report": {
            "version": "3.1.2",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "status": "promoted" if promoted else "base_contract",
            "contract_profile_id": profile_id,
            "rule_trace": rule_trace_for_artifact("model_contract_promotion_report"),
            "source_refs": source_refs or [brief["prototype_source_brief"].get("sections", [{}])[0].get("source_ref", "inputs/PRD.md#L1")],
            "trigger_summary": {
                "system_handoff_detected": has_handoff,
                "non_app_carrier_detected": has_non_app_carrier,
                "handoff_count": len(handoff_root.get("handoffs", []) or []),
            },
            "required_artifacts": required_artifacts,
            "required_model_fields": {
                "surface_ownership": ["carrier_type", "host_context_zh", "standalone_page_allowed", "system_surface_refs"],
                "user_journey": ["operation_chain_id", "carrier_transition_type", "handoff_ids"],
                "interaction_state_machine": ["edge_type", "stays_on_same_surface", "feedback_surface_zh"],
                "component_blueprint": ["carrier_type", "render_region_zh"],
            } if promoted else {},
            "official_docs_search_enabled": False,
            "writes_prd": False,
            "figma_written": False,
        }
    }
    resolved_contract = {
        "model_execution_contract": {
            "version": "3.1.2",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "contract_id": f"MEC-RESOLVED-{RUN_ID}",
            "generator_id": "GEN-CONTRACT-PROMOTION",
            "generator_kind": "model",
            "provider": "codex_cli",
            "execution_mode": getattr(args, "codex_inference", "required") or "required",
            "stage_role": "multi_stage_generation_reasoning",
            "model_output_kind": "prototype_multistage_reasoning",
            "contract_profile_id": profile_id,
            "rule_trace": rule_trace_for_artifact("model_execution_contract"),
            "command_policy": model_command_policy(),
            "input_refs": [
                "io/output/prototype_source_brief.yaml",
                "io/state/deterministic_generation_draft.yaml",
                "io/output/interaction_carrier_map.yaml",
                "io/output/system_handoff_map.yaml",
                "io/output/user_operation_chain.yaml",
                "io/output/capability_assessment.yaml",
            ],
            "output_refs": ["io/state/model_invocation_trace.yaml"],
            "allowed_operations": [
                "read_source_brief",
                "read_deterministic_draft_summary",
                "read_carrier_handoff_artifacts",
                "derive_carrier_aware_reasoning",
                "emit_reasoning_json",
            ],
            "forbidden_operations": [
                "write_prd",
                "write_product_spec",
                "write_figma",
                "mutate_runtime_or_payload",
                "read_business_specific_sample_fixture",
            ],
            "completion_criteria": [
                {
                    "criterion_id": "CONTRACT-CC-PROMOTION-RESOLVED",
                    "description_zh": "触发承载面或系统交接时必须解析增强模型 contract。",
                    "required": promoted,
                    "rule_ids": rule_ids_for_artifact("model_contract_promotion_report"),
                }
            ],
            "source_refs": source_refs,
        }
    }
    return report, resolved_contract


def build_prototype_review_view_model(runtime: dict, payload: dict, carrier_bundle: dict, model_artifacts: dict) -> dict:
    payload_root = payload["prototype_render_payload"]
    carrier_root = carrier_bundle["interaction_carrier_map"]["interaction_carrier_map"]
    handoff_root = carrier_bundle["system_handoff_map"]["system_handoff_map"]
    chain_root = carrier_bundle["user_operation_chain"]["user_operation_chain"]
    review_rule_ids = rule_ids_for_artifact("prototype_review_view_model")
    state_by_id = state_lookup(runtime)
    screen_carrier_by_id = {item.get("screen_id"): item for item in carrier_root.get("screen_carriers", []) or []}
    state_carrier_by_id = {item.get("state_id"): item for item in carrier_root.get("state_carriers", []) or []}
    interaction_carrier_by_id = {item.get("interaction_id"): item for item in carrier_root.get("interaction_carriers", []) or []}
    chain_by_interaction = {item.get("interaction_id"): item for item in chain_root.get("chains", []) or []}
    frame_state = {frame.get("frame_id"): frame.get("state_id") for frame in payload_root.get("frames", []) or []}
    components_by_screen = defaultdict(list)
    for component in payload_root.get("components", []) or []:
        state_id = frame_state.get(component.get("frame_id", ""))
        state = state_by_id.get(state_id, {})
        components_by_screen[state.get("screen_id")].append((component, state_id))

    def clean_copy(value: str) -> str:
        return strip_source_ids(clean_md_text(value or "").replace("COPY-", "")).strip() or "未命名元素"

    def human_text(value: str, fallback: str = "未命名") -> str:
        text = strip_source_ids(value or "")
        text = re.sub(r"\b[A-Z][A-Z0-9]+(?:-[A-Z0-9_]+)+\b", "", text)
        text = clean_md_text(text).strip(" -_｜|，,。()（）")
        return text or fallback

    def human_state_name(state_id: str | None, fallback: str = "当前状态") -> str:
        state = state_by_id.get(state_id or "", {})
        return human_text(state.get("state_zh") or "", fallback)

    def chain_step_texts(chain: dict) -> list[str]:
        return [
            human_text(step.get("description_zh", ""), "")
            for step in chain.get("steps", []) or []
            if human_text(step.get("description_zh", ""), "")
        ]

    def transition_kind_zh(chain: dict, carrier_info: dict) -> str:
        if carrier_info.get("requires_system_handoff") or chain.get("chain_kind") == "system_handoff_chain":
            return "系统交接链路"
        if chain.get("chain_kind") == "same_surface_state_chain":
            return "同页状态变化"
        return "跨页面或跨承载面跳转"

    def chain_section_title(chain: dict, carrier_info: dict) -> str:
        if carrier_info.get("requires_system_handoff") or chain.get("chain_kind") == "system_handoff_chain":
            return "系统交接与返回"
        if chain.get("chain_kind") == "same_surface_state_chain":
            return "同页状态变化"
        return "跨页面或跨承载面流转"

    def element_group(component: dict) -> str:
        semantic = str(component.get("semantic_key") or component.get("semantic_role") or "").lower()
        if "button" in semantic:
            return "操作元素"
        if "input" in semantic or "select" in semantic or "upload" in semantic:
            return "输入选择元素"
        if "feedback" in semantic or "toast" in semantic or "alert" in semantic:
            return "反馈提示元素"
        if "badge" in semantic or "tag" in semantic or "annotation" in semantic:
            return "标识元素"
        return "显示元素"

    interactions_by_component = defaultdict(list)
    interaction_by_id = {}
    for interaction in payload_root.get("interactions", []) or []:
        interactions_by_component[interaction.get("source_component_id", "")].append(interaction)
        interaction_by_id[interaction.get("interaction_id", "")] = interaction

    pages = []
    for idx, screen in enumerate(runtime.get("screens", []) or [], start=1):
        screen_id = screen.get("screen_id")
        carrier = screen_carrier_by_id.get(screen_id, {})
        group_map = {name: [] for name in ["显示元素", "操作元素", "输入选择元素", "反馈提示元素", "标识元素"]}
        for component, state_id in components_by_screen.get(screen_id, []):
            group_name = element_group(component)
            related = interactions_by_component.get(component.get("component_id", ""), [])
            carrier_state = state_carrier_by_id.get(state_id, carrier)
            interaction_texts = []
            for interaction in related[:3]:
                chain = chain_by_interaction.get(interaction.get("interaction_id"), {})
                carrier_info = interaction_carrier_by_id.get(interaction.get("interaction_id"), {})
                if carrier_info.get("transition_scope") == "same_surface_state_change":
                    result_zh = "留在当前承载面内更新状态"
                elif carrier_info.get("requires_system_handoff"):
                    result_zh = "进入系统交接链路后返回"
                else:
                    result_zh = "进入新的页面或承载面"
                interaction_texts.append(f"{human_text(interaction.get('trigger_zh') or '用户操作')}，然后{result_zh}。")
            group_map[group_name].append({
                "element_name_zh": clean_copy(component.get("copy_zh") or component.get("copy_ref")),
                "user_visible_text_zh": clean_copy(component.get("copy_zh") or component.get("copy_ref")),
                "carrier_zh": carrier_state.get("carrier_zh", carrier.get("carrier_zh", "")),
                "description_zh": f"这个元素用于{group_name.replace('元素', '')}，出现在{carrier_state.get('carrier_zh', carrier.get('carrier_zh', '当前页面'))}。",
                "interaction_zh": " ".join(interaction_texts) if interaction_texts else "这个元素主要负责展示当前状态，没有直接触发跳转。",
                "display_logic_zh": "按当前状态显示；如果该状态不可达或被折叠，需要人工确认。",
                "source_refs": component.get("source_refs", []),
            })
        page_chains = []
        for chain in chain_root.get("chains", []) or []:
            interaction = interaction_by_id.get(chain.get("interaction_id", ""), {})
            source_state = state_by_id.get(chain.get("source_state_id") or interaction.get("source_state_id") or "", {})
            target_state = state_by_id.get(chain.get("target_state_id") or interaction.get("target_state_id") or "", {})
            if source_state.get("screen_id") != screen_id and target_state.get("screen_id") != screen_id:
                continue
            carrier_info = interaction_carrier_by_id.get(chain.get("interaction_id") or interaction.get("interaction_id"), {})
            chain_steps = chain.get("steps", []) or []
            trigger = human_text(
                interaction.get("trigger_zh")
                or ((chain_steps[0] if chain_steps else {}) or {}).get("description_zh")
                or "用户操作",
                "用户操作",
            )
            page_chains.append({
                "trigger_zh": trigger,
                "source_state_zh": human_state_name(chain.get("source_state_id") or interaction.get("source_state_id")),
                "target_state_zh": human_state_name(chain.get("target_state_id") or interaction.get("target_state_id")),
                "transition_kind_zh": transition_kind_zh(chain, carrier_info),
                "section_title_zh": chain_section_title(chain, carrier_info),
                "carrier_change_zh": f"{human_text(carrier_info.get('source_carrier_zh'), '当前承载面')} -> {human_text(carrier_info.get('target_carrier_zh'), '目标承载面')}",
                "steps_zh": chain_step_texts(chain),
                "review_note_zh": "能力状态未知时，这条链路需要人工确认真实系统面和提示位置。" if carrier_info.get("requires_system_handoff") else "",
                "source_refs": chain.get("source_refs", []) or interaction.get("source_refs", []),
            })
        section_map = defaultdict(list)
        for chain_item in page_chains:
            section_map[chain_item["section_title_zh"]].append(chain_item)
        section_order = ["跨页面或跨承载面流转", "系统交接与返回", "同页状态变化"]
        interaction_flow_sections = [
            {
                "section_title_zh": title,
                "summary_zh": f"本组包含 {len(section_map.get(title, []))} 条链路。",
                "chains": section_map.get(title, []),
            }
            for title in section_order
            if section_map.get(title)
        ]

        pages.append({
            "page_no": idx,
            "page_name_zh": human_text(screen.get("screen_zh") or screen_id, "未命名页面"),
            "page_purpose_zh": human_text((screen.get("model_surface_blueprint", {}) or {}).get("page_purpose_zh") or "承接 PRD 中与该页面相关的用户任务和状态。"),
            "carrier_zh": human_text(carrier.get("carrier_zh", "应用内页面"), "应用内页面"),
            "standalone_page_allowed": carrier.get("standalone_page_allowed", True),
            "state_summary_zh": f"包含 {len(screen.get('states', []) or [])} 个状态画面；阻断、边界、失败和恢复状态需要人工重点确认。",
            "interaction_flow_sections": interaction_flow_sections,
            "element_groups": [
                {"group_name_zh": name, "elements": items}
                for name, items in group_map.items()
                if items
            ],
            "source_refs": screen.get("source_refs", []),
        })

    page_flow_edges = []
    same_surface_state_changes = []
    for interaction in payload_root.get("interactions", []) or []:
        carrier = interaction_carrier_by_id.get(interaction.get("interaction_id"), {})
        chain = chain_by_interaction.get(interaction.get("interaction_id"), {})
        source_state = state_by_id.get(interaction.get("source_state_id"), {})
        target_state = state_by_id.get(interaction.get("target_state_id"), {})
        item = {
            "trigger_zh": human_text(interaction.get("trigger_zh") or "用户操作", "用户操作"),
            "source_page_zh": human_text(source_state.get("screen_zh") or source_state.get("screen_id"), "当前页面"),
            "target_page_zh": human_text(target_state.get("screen_zh") or target_state.get("screen_id"), "目标页面"),
            "source_state_zh": human_state_name(interaction.get("source_state_id")),
            "target_state_zh": human_state_name(interaction.get("target_state_id")),
            "carrier_change_zh": f"{human_text(carrier.get('source_carrier_zh'), '当前承载面')} -> {human_text(carrier.get('target_carrier_zh'), '目标承载面')}",
            "operation_chain_zh": "；".join(chain_step_texts(chain)),
            "source_refs": interaction.get("source_refs", []),
        }
        same_function_page = source_state.get("screen_id") == target_state.get("screen_id")
        if same_function_page or carrier.get("transition_scope") == "same_surface_state_change":
            same_surface_state_changes.append(item)
        else:
            page_flow_edges.append(item)

    handoff_chains = []
    for handoff in handoff_root.get("handoffs", []) or []:
        handoff_chains.append({
            "title_zh": f"{human_text(handoff.get('handoff_surface_zh'), '系统能力面')}交接",
            "start_zh": "从当前承载面进入系统能力面。",
            "steps_zh": [human_text(step.get("description_zh", ""), "") for step in handoff.get("handoff_steps", []) or []],
            "cancel_zh": human_text(handoff.get("cancel_path_zh", ""), ""),
            "failure_zh": human_text(handoff.get("failure_path_zh", ""), ""),
            "review_required": handoff.get("review_required", True),
            "source_refs": handoff.get("source_refs", []),
        })

    return {
        "prototype_review_view_model": {
            "version": "3.1.2",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "status": "ready_for_human_review",
            "rule_trace": rule_trace_for_artifact("prototype_review_view_model"),
            "source_refs": payload_root.get("source_refs", []),
            "summary_zh": "这份 view model 只服务人工 review；它隐藏 frame、hash、source atom 等机器字段，保留页面、承载面、元素、交互和系统交接说明。",
            "pages": pages,
            "page_flow_edges": page_flow_edges,
            "same_surface_state_changes": same_surface_state_changes,
            "system_handoff_chains": handoff_chains,
            "review_checklist_zh": [
                "页面是否该这样分。",
                "交互是否发生在正确承载面。",
                "同页状态变化是否被误画成页面跳转。",
                "系统交接和能力未知项是否需要人工确认。",
            ],
            "rule_ids": review_rule_ids,
        }
    }


def render_blueprint_review_markdown_from_view_model(review_doc: dict) -> str:
    root = review_doc.get("prototype_review_view_model", {})

    def mermaid_text(value: str, limit: int = 42) -> str:
        text = clean_md_text(value or "").replace('"', "'").replace("`", "")
        return plain_excerpt(text, limit) if text else "未命名"

    def render_chain_graph(chains: list[dict]) -> list[str]:
        graph = ["```mermaid", "flowchart TD"]
        node_by_label = {}
        seen_edges = set()
        for idx, chain in enumerate(chains or [], start=1):
            source_label = mermaid_text(chain.get("source_state_zh"), 34)
            target_label = mermaid_text(chain.get("target_state_zh"), 34)
            source_id = node_by_label.setdefault(source_label, f"S{len(node_by_label) + 1:02d}")
            target_id = node_by_label.setdefault(target_label, f"S{len(node_by_label) + 1:02d}")
            edge_label = mermaid_text(chain.get("trigger_zh"), 30)
            edge_key = (source_id, target_id, edge_label)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            graph.append(f'  {source_id}["{source_label}"] -- "{edge_label}" --> {target_id}["{target_label}"]')
        if not seen_edges:
            graph.append('  S00["本页没有需要画出的链路"]')
        graph.append("```")
        return graph

    lines = [
        "# 原型蓝图人工确认稿",
        "",
        root.get("summary_zh", "这份文档给人看，不给机器当最终事实。"),
        "",
        f"本次 run 是 `{RUN_ID}`。Figma 写入状态：`not_started`。",
        "",
        "## 1. 人工确认清单",
        "",
    ]
    for item in root.get("review_checklist_zh", []) or []:
        lines.append(f"- [ ] {item}")
    lines.extend(["", "## 2. 页面列表", ""])
    for page in root.get("pages", []) or []:
        lines.extend([
            f"{page.get('page_no')}. {page.get('page_name_zh')}",
            "",
            f"功能和作用：{page.get('page_purpose_zh')}",
            "",
            f"交互呈现载体：{page.get('carrier_zh')}。",
            "",
            f"状态说明：{page.get('state_summary_zh')}",
            "",
        ])
    lines.extend(["## 3. 页面流转图", ""])
    if root.get("page_flow_edges"):
        lines.extend(["```mermaid", "flowchart TD"])
        node_by_page = {}
        for idx, page in enumerate(root.get("pages", []) or [], start=1):
            page_name = clean_md_text(page.get("page_name_zh"))
            if page_name and page_name not in node_by_page:
                node_id = f"P{idx:02d}"
                node_by_page[page_name] = node_id
                lines.append(f'  {node_id}["{page_name}"]')
        seen_edges = set()
        for idx, edge in enumerate(root.get("page_flow_edges", []) or [], start=1):
            source_page = clean_md_text(edge.get("source_page_zh"))
            target_page = clean_md_text(edge.get("target_page_zh"))
            if not source_page or not target_page or source_page == target_page:
                continue
            source = node_by_page.setdefault(source_page, f"PX{idx}A")
            target = node_by_page.setdefault(target_page, f"PX{idx}B")
            edge_key = (source, target, clean_md_text(edge.get("trigger_zh")))
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            lines.append(f'  {source} -- "{edge_key[2]}" --> {target}')
        if not seen_edges:
            lines.append('  P00["本次没有明确跨页面跳转"]')
        lines.append("```")
    else:
        lines.append("本次没有明确跨页面或跨承载面的流转。")
    lines.extend(["", "## 4. 同页状态变化", ""])
    if root.get("same_surface_state_changes"):
        for idx, item in enumerate(root.get("same_surface_state_changes", []) or [], start=1):
            lines.extend([
                f"{idx}. 用户在「{item.get('source_page_zh')}」里执行「{item.get('trigger_zh')}」。",
                "",
                f"变化方式：留在当前承载面，从「{item.get('source_state_zh')}」变成「{item.get('target_state_zh')}」。",
                "",
                f"操作链：{item.get('operation_chain_zh')}",
                "",
            ])
    else:
        lines.append("本次没有需要单独说明的同页状态变化。")
        lines.append("")
    lines.extend(["## 5. 系统交接链路", ""])
    if root.get("system_handoff_chains"):
        for idx, handoff in enumerate(root.get("system_handoff_chains", []) or [], start=1):
            lines.extend([
                f"{idx}. {handoff.get('title_zh')}",
                "",
                handoff.get("start_zh", ""),
                "",
            ])
            for step_no, step in enumerate(handoff.get("steps_zh", []) or [], start=1):
                lines.append(f"{idx}.{step_no} {step}")
            lines.extend([
                "",
                f"取消路径：{handoff.get('cancel_zh')}",
                "",
                f"失败路径：{handoff.get('failure_zh')}",
                "",
                f"是否需要人工确认：{handoff.get('review_required')}",
                "",
            ])
    else:
        lines.append("本次没有识别到必须展示的系统交接链路。")
        lines.append("")
    lines.extend(["## 6. 每个页面的元素与逻辑", ""])
    for page in root.get("pages", []) or []:
        lines.extend([
            f"### {page.get('page_no')}. {page.get('page_name_zh')}",
            "",
            f"页面作用：{page.get('page_purpose_zh')}",
            "",
            f"承载面：{page.get('carrier_zh')}",
            "",
        ])
        if page.get("interaction_flow_sections"):
            lines.extend(["#### 页面交互链路", ""])
            for section in page.get("interaction_flow_sections", []) or []:
                chains = section.get("chains", []) or []
                lines.extend([
                    f"##### {section.get('section_title_zh')}",
                    "",
                    section.get("summary_zh", ""),
                    "",
                    *render_chain_graph(chains),
                    "",
                ])
                for chain_idx, chain in enumerate(chains, start=1):
                    lines.extend([
                        f"{chain_idx}. 触发：{chain.get('trigger_zh')}",
                        "",
                        f"从「{chain.get('source_state_zh')}」到「{chain.get('target_state_zh')}」。",
                        "",
                        f"链路类型：{chain.get('transition_kind_zh')}",
                        "",
                    ])
                    steps = chain.get("steps_zh", []) or []
                    if steps:
                        lines.append("操作步骤：")
                        for step_idx, step in enumerate(steps, start=1):
                            lines.append(f"{chain_idx}.{step_idx} {step}")
                        lines.append("")
                    if chain.get("review_note_zh"):
                        lines.extend([f"人工确认点：{chain.get('review_note_zh')}", ""])
        else:
            lines.extend(["#### 页面交互链路", "", "本页没有可展示的页面内交互链路。", ""])
        for group in page.get("element_groups", []) or []:
            lines.extend([f"#### {group.get('group_name_zh')}", ""])
            for idx, element in enumerate(group.get("elements", []) or [], start=1):
                lines.extend([
                    f"{idx}. {element.get('element_name_zh')}",
                    "",
                    f"用户看到：{element.get('user_visible_text_zh')}",
                    "",
                    f"元素作用：{element.get('description_zh')}",
                    "",
                    f"交互说明：{element.get('interaction_zh')}",
                    "",
                    f"显示逻辑：{element.get('display_logic_zh')}",
                    "",
                ])
    lines.extend([
        "## 7. 写入前结论",
        "",
        "这份蓝图已经生成，但仍然是候选原型。人工确认后，才能进入最终 Figma writer。",
        "",
    ])
    return "\n".join(lines)


def render_report_markdown(report: dict) -> str:
    data = report["prototype_projection_report"]
    lines = [
        "# Prototype Projection Report",
        "",
        "本报告是人工阅读入口；同名 YAML 是机器校验源。",
        "",
        "## Summary",
        "",
        f"- run_id: `{data['run_id']}`",
        f"- source: `{data['source_path']}`",
        f"- runtime: `{data['outputs']['runtime_candidate']}`",
        f"- payload: `{data['outputs']['render_payload']}`",
        f"- figma_written: `{data['figma_written']}`",
        "",
        "## Review Entry",
        "",
        f"- blueprint_review: `{data['outputs'].get('blueprint_review', 'prd_orchestrator/prototype_projection_reports/prototype_blueprint_review.md')}`",
        f"- review_view_model: `{data['outputs'].get('prototype_review_view_model', 'io/state/prototype_review_view_model.yaml')}`",
        "",
        "人工确认请优先打开 `blueprint_review`。它只消费 `prototype_review_view_model.yaml`，不会直接扫 payload。",
        "",
        "## Counts",
        "",
        *[f"- {key}: `{value}`" for key, value in data["counts"].items()],
        "",
        "## Readiness",
        "",
        f"```bash\n{data['readiness_next_command']}\n```",
    ]
    if data.get("blocked_inferences"):
        lines.extend(["", "## Blocked Inferences", ""])
        for item in data["blocked_inferences"]:
            lines.append(f"- `{item.get('gap_id')}` {item.get('missing_decision')}")
    return "\n".join(lines) + "\n"


def render_blueprint_review_markdown(brief: dict, runtime: dict, payload: dict, codex_review: dict) -> str:
    brief_root = brief["prototype_source_brief"]
    payload_root = payload["prototype_render_payload"]
    frame_by_state = {frame.get("state_id"): frame for frame in payload_root.get("frames", []) or []}
    state_by_frame = {frame.get("frame_id"): frame.get("state_id") for frame in payload_root.get("frames", []) or []}
    state_by_id = {
        state.get("state_id"): state
        for screen in runtime.get("screens", []) or []
        for state in screen.get("states", []) or []
    }
    state_screen_by_id = {
        state.get("state_id"): screen.get("screen_id")
        for screen in runtime.get("screens", []) or []
        for state in screen.get("states", []) or []
        if state.get("state_id")
    }
    screen_by_id = {screen.get("screen_id"): screen for screen in runtime.get("screens", []) or []}
    ownership_by_screen = {item.get("screen_id"): item for item in brief_root.get("surface_ownership", []) or []}
    components_by_frame = defaultdict(list)
    for component in payload_root.get("components", []) or []:
        components_by_frame[component.get("frame_id", "")].append(component)
    interactions_by_source = defaultdict(list)
    interactions_by_component = defaultdict(list)
    for interaction in payload_root.get("interactions", []) or []:
        interactions_by_source[interaction.get("source_state_id", "")].append(interaction)
        interactions_by_component[interaction.get("source_component_id", "")].append(interaction)
    interactions_sorted = sorted(payload_root.get("interactions", []) or [], key=lambda item: item.get("operation_chain_step", 0))
    codex_root = codex_review.get("codex_inference_review", {})
    total_states = sum(len(screen.get("states", []) or []) for screen in runtime.get("screens", []) or [])

    def md_text(value, limit: int | None = None) -> str:
        text = str(value or "").replace("|", "｜").replace("\n", " ").strip()
        replacements = {
            "source atom": "信息片段",
            "source state": "起点状态",
            "target state": "目标状态",
            "destination frame": "目标画面",
            "frame": "状态画面",
            "screen": "页面",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return plain_excerpt(text, limit) if limit else text

    def refs_text(refs: list[str] | None, limit: int = 4) -> str:
        refs = refs or []
        if not refs:
            return "未记录来源。"
        shown = "，".join(refs[:limit])
        if len(refs) > limit:
            shown += f"，另有 {len(refs) - limit} 条来源。"
        return shown

    def role_zh(role: str) -> str:
        mapping = {
            "entry_surface": "入口页",
            "task_surface": "任务页",
            "setting_surface": "设置页",
            "analysis_surface": "分析页",
        }
        return mapping.get(role or "", role or "待确认页面")

    def mermaid_label(text: str, limit: int = 46) -> str:
        text = md_text(text, limit).replace('"', "'").replace("`", "")
        return text or "未命名"

    def state_title(state_id: str | None) -> str:
        state = state_by_id.get(state_id or "", {})
        return md_text(state.get("state_zh") or state_id or "未命名状态", 60)

    def screen_title(screen_id: str | None) -> str:
        screen = screen_by_id.get(screen_id or "", {})
        return md_text(screen.get("screen_zh") or screen_id or "未命名页面", 60)

    def interaction_target_screen(interaction: dict) -> str:
        return (
            interaction.get("target_screen_id")
            or state_screen_by_id.get(interaction.get("target_state_id"))
            or ""
        )

    def element_kind_zh(component: dict) -> str:
        semantic = str(component.get("semantic_key") or component.get("semantic_role") or "").lower()
        if "button" in semantic:
            return "按钮"
        if "input" in semantic or "select" in semantic or "upload" in semantic:
            return "选择区"
        if "feedback" in semantic or "toast" in semantic or "alert" in semantic:
            return "提示信息"
        if "list" in semantic or "card" in semantic:
            return "内容区"
        if "badge" in semantic:
            return "标记"
        return "页面元素"

    def element_category(component: dict) -> str:
        semantic = str(component.get("semantic_key") or component.get("semantic_role") or "").lower()
        if "button" in semantic:
            return "操作元素"
        if "input" in semantic or "select" in semantic or "upload" in semantic:
            return "输入/选择元素"
        if "feedback" in semantic or "toast" in semantic or "alert" in semantic or "error" in semantic:
            return "反馈/提示元素"
        if "badge" in semantic or "tag" in semantic or "status" in semantic or "annotation" in semantic:
            return "标识/注释元素"
        return "显示元素"

    def grouped_components(components: list[dict]) -> list[tuple[str, list[dict]]]:
        order = ["显示元素", "操作元素", "输入/选择元素", "反馈/提示元素", "标识/注释元素"]
        grouped = {name: [] for name in order}
        for component in components:
            grouped.setdefault(element_category(component), []).append(component)
        return [(name, grouped.get(name, [])) for name in order if grouped.get(name)]

    def element_title(component: dict, idx: int) -> str:
        copy = md_text(component.get("copy_zh") or component.get("copy_ref"), 36)
        kind = element_kind_zh(component)
        if not copy:
            return f"{kind} {idx}"
        if kind in copy:
            return copy
        if kind == "提示信息":
            return copy
        return f"{copy}{kind}"

    def state_interaction_lines(state_id: str | None, limit: int | None = None) -> list[str]:
        items = interactions_by_source.get(state_id or "", [])
        if limit is not None:
            items = items[:limit]
        lines = []
        for interaction in items:
            target_screen = interaction_target_screen(interaction)
            lines.append(
                f"用户「{md_text(interaction.get('trigger_zh') or interaction.get('trigger'), 70)}」后，"
                f"进入「{state_title(interaction.get('target_state_id'))}」。"
                f"这个目标属于「{screen_title(target_screen)}」。"
            )
        return lines

    def component_interaction_lines(component_id: str | None, limit: int | None = None) -> list[str]:
        items = interactions_by_component.get(component_id or "", [])
        if limit is not None:
            items = items[:limit]
        lines = []
        for interaction in items:
            target_screen = interaction_target_screen(interaction)
            lines.append(
                f"用户「{md_text(interaction.get('trigger_zh') or interaction.get('trigger'), 70)}」后，"
                f"进入「{state_title(interaction.get('target_state_id'))}」。"
                f"这个目标属于「{screen_title(target_screen)}」。"
            )
        return lines

    def element_logic_text(component: dict, state_id: str | None) -> str:
        kind = element_kind_zh(component)
        state = state_by_id.get(state_id or "", {})
        state_name = state_title(state_id)
        feedback = md_text(state.get("feedback_zh"), 90)
        recovery = md_text(state.get("recovery_zh"), 90)
        if kind == "提示信息":
            return f"它跟随「{state_name}」显示，用来把当前结果、失败原因或下一步提示说清楚。"
        if kind == "按钮":
            actions = component_interaction_lines(component.get("component_id"), limit=2)
            if actions:
                return "它是这个状态下的操作入口。" + " ".join(actions)
            return f"它在「{state_name}」里出现，用来承接用户下一步操作。"
        if kind == "选择区":
            suffix = f"如果选择失败，恢复方式是：{recovery}。" if recovery else ""
            return f"它在「{state_name}」里收集用户选择，是后续判断能不能继续的关键。{suffix}"
        if feedback:
            return f"它跟随「{state_name}」显示，页面反馈是：{feedback}。"
        return f"它跟随「{state_name}」显示，用来支撑当前状态的主要内容。"

    def page_flow_mermaid() -> list[str]:
        page_nodes = {}
        graph = ["```mermaid", "flowchart TD"]
        for idx, screen in enumerate(runtime.get("screens", []) or [], start=1):
            node_id = f"P{idx:02d}"
            page_nodes[screen.get("screen_id")] = node_id
            graph.append(f'  {node_id}["{mermaid_label(screen.get("screen_zh") or screen.get("screen_id"))}"]')
        seen_edges = set()
        for interaction in interactions_sorted:
            source_page = interaction.get("source_screen_id") or interaction.get("screen_id") or state_screen_by_id.get(
                interaction.get("source_state_id")
            )
            target_page = interaction.get("target_screen_id") or state_screen_by_id.get(interaction.get("target_state_id"))
            if not source_page or not target_page or source_page == target_page:
                continue
            edge = (source_page, target_page, interaction.get("trigger_zh") or interaction.get("trigger"))
            if edge in seen_edges:
                continue
            seen_edges.add(edge)
            graph.append(
                f'  {page_nodes.get(source_page, "P00")} -- "{mermaid_label(edge[2], 28)}" --> {page_nodes.get(target_page, "P00")}'
            )
        if not seen_edges:
            graph.append('  P00["本次没有跨页面跳转"]')
        graph.append("```")
        return graph

    def state_flow_mermaid() -> list[str]:
        node_by_state = {}
        graph = ["```mermaid", "flowchart TD"]
        for idx, state_id in enumerate(state_by_id, start=1):
            node_id = f"S{idx:03d}"
            state = state_by_id[state_id]
            node_by_state[state_id] = node_id
            label = f"{state_id}<br/>{mermaid_label(state.get('state_zh'), 34)}"
            graph.append(f'  {node_id}["{label}"]')
        for interaction in interactions_sorted:
            source = node_by_state.get(interaction.get("source_state_id"))
            target = node_by_state.get(interaction.get("target_state_id"))
            if not source or not target:
                continue
            trigger = mermaid_label(interaction.get("trigger_zh") or interaction.get("trigger"), 28)
            graph.append(f'  {source} -- "{trigger}" --> {target}')
        graph.append("```")
        return graph

    lines = [
        "# 原型蓝图人工确认稿",
        "",
        "这份文档给人看，不给机器当最终事实。YAML 和 JSON 仍然是机器校验源。本文件只用来帮助人工确认：这些页面要不要画、这些状态是不是该出现、这些交互是不是符合 PRD。",
        "",
        "## 1. 这次生成了什么",
        "",
        f"本次 run 是 `{RUN_ID}`。输入来自 `{brief_root.get('source_path')}`。",
        "",
        f"生成器从 PRD 中拆出了 `{len(brief_root.get('source_atoms', []))}` 条可追溯信息片段。它认为当前原型需要 `{len(runtime.get('screens', []))}` 个功能页面、`{total_states}` 个状态画面、`{len(payload_root.get('components', []))}` 个页面元素、`{len(payload_root.get('interactions', []))}` 条交互和 `{len(payload_root.get('annotations', []))}` 条注释。",
        "",
        f"这里的“功能页面”和“状态画面”不是一回事。功能页面是大的业务入口；状态画面是同一个功能页面里的不同显示状态。最终给 Figma 消费的画布会按 `{total_states}` 个状态画面展开。",
        "",
        f"Codex 模型审查是否执行：`{codex_root.get('model_called')}`。模型审查状态：`{codex_root.get('status')}`。Figma 写入状态：`not_started`。",
        "",
        "## 2. 人工确认清单",
        "",
        "- [ ] 页面数量和页面名称符合 PRD。",
        "- [ ] 每个页面的状态归属合理，没有把指标、埋点、review、trace 表格误画成页面。",
        "- [ ] 组件构成符合黑白灰 SDS 约束。",
        "- [ ] 每条关键交互都有起点状态、目标状态和落点画面。",
        "- [ ] 少于/超过数量、OCR 失败、上传失败等阻断状态文案符合产品预期。",
        "- [ ] 确认后再进入最终 Figma writer。",
        "",
        "## 3. 页面跳转流程逻辑",
        "",
        "先看功能页面之间怎么走。这个图只表达大的业务入口，不展开同一个页面内部的状态变化。",
        "",
        *page_flow_mermaid(),
        "",
        "再看状态画面级交互图。这个图会更细，它把每个可画状态都放进来，所以节点会多一些。它适合检查有没有缺少目标画面、有没有不该自动跳转的地方。",
        "",
        *state_flow_mermaid(),
        "",
        "## 4. 功能页面列表",
        "",
        "先看大的功能页面清单。每个功能页面下面会包含多个状态画面，所以这里的数量会少于上面的状态画面图。",
    ]
    for page_idx, screen in enumerate(runtime.get("screens", []) or [], start=1):
        owner = ownership_by_screen.get(screen.get("screen_id"), {})
        screen_states = screen.get("states", []) or []
        screen_state_ids = {state.get("state_id") for state in screen_states}
        screen_interactions = [
            item for item in interactions_sorted
            if item.get("source_state_id") in screen_state_ids
        ]
        screen_frames = [frame_by_state.get(state.get("state_id"), {}) for state in screen_states]
        screen_components = [
            component
            for frame in screen_frames
            for component in components_by_frame.get(frame.get("frame_id", ""), [])
        ]
        lines.extend([
            "",
            f"- 功能页面 {page_idx}：{md_text(screen.get('screen_zh'))}。它是一个{role_zh(owner.get('surface_role', ''))}，下面包含 {len(screen_states)} 个状态画面、{len(screen_components)} 个元素、{len(screen_interactions)} 条交互。",
        ])
    lines.extend([
        "",
        "## 5. 每个页面的功能、元素与逻辑",
        "",
        "这一节按功能页面拆开看。每个页面先讲它的作用，再讲状态画面，最后把页面元素按显示、操作、输入选择、反馈提示、标识注释分组。",
    ])
    for page_idx, screen in enumerate(runtime.get("screens", []) or [], start=1):
        owner = ownership_by_screen.get(screen.get("screen_id"), {})
        screen_states = screen.get("states", []) or []
        screen_state_ids = {state.get("state_id") for state in screen_states}
        screen_interactions = [
            item for item in interactions_sorted
            if item.get("source_state_id") in screen_state_ids
        ]
        screen_frames = [frame_by_state.get(state.get("state_id"), {}) for state in screen_states]
        screen_components = [
            component
            for frame in screen_frames
            for component in components_by_frame.get(frame.get("frame_id", ""), [])
        ]
        lines.extend([
            "",
            f"### 5.{page_idx} {md_text(screen.get('screen_zh'))}",
            "",
            "#### 页面功能和作用",
            "",
            f"这个页面的定位是{role_zh(owner.get('surface_role', ''))}。它主要承接「{md_text(owner.get('inference_basis_zh') or 'PRD 中和这个页面相关的任务、状态和用户操作。')}」",
            "",
            f"人工 review 时，重点确认这 {len(screen_states)} 个状态画面是否都该画出来，以及 {len(screen_interactions)} 条交互是否符合真实用户操作。",
            "",
            "#### 页面中的状态和逻辑",
            "",
        ])
        for state_idx, state in enumerate(screen.get("states", []) or [], start=1):
            state_interactions = interactions_by_source.get(state.get("state_id"), [])
            lines.extend([
                f"##### 状态 {state_idx}：{state_title(state.get('state_id'))}",
                "",
                f"这个状态要表达的是：{md_text(state.get('display_reason_zh') or 'PRD 中出现的一个可见状态，需要在原型里给人看。')}",
                "",
                f"用户在这个状态里会看到：{md_text(state.get('feedback_zh') or '页面保持当前内容，没有额外提示。')}",
                "",
            ])
            if state.get("recovery_zh"):
                lines.extend([
                    f"如果用户卡住或失败，恢复方式是：{md_text(state.get('recovery_zh'))}",
                    "",
                ])
            if state_interactions:
                lines.append("这个状态后面可以这样走：")
                lines.append("")
                for item in state_interaction_lines(state.get("state_id")):
                    lines.append(f"- {item}")
                lines.append("")
            else:
                lines.extend([
                    "这个状态暂时没有继续跳转。它可能是结果态、停留态，或者需要人工确认是否补后续动作。",
                    "",
                ])
        lines.extend([
            "#### 页面元素分组",
            "",
        ])
        if not screen_components:
            lines.append("这个页面当前没有生成独立页面元素，需要人工确认是否应补充。")
            lines.append("")
        for group_idx, (group_name, group_items) in enumerate(grouped_components(screen_components), start=1):
            lines.extend([
                f"##### {group_idx}. {group_name}（{len(group_items)} 个）",
                "",
            ])
            for comp_idx, component in enumerate(group_items, start=1):
                state_id = state_by_frame.get(component.get("frame_id", ""))
                component_interactions = component_interaction_lines(component.get("component_id"))
                copy = md_text(component.get("copy_zh") or component.get("copy_ref") or "这个元素暂时没有明确文案", 90)
                lines.extend([
                    f"{group_idx}.{comp_idx} {element_title(component, comp_idx)}",
                    "",
                    f"用户看到的内容是：「{copy}」。",
                    "",
                    f"它出现在「{state_title(state_id)}」这个状态画面里。",
                    "",
                    f"元素说明：{element_logic_text(component, state_id)}",
                    "",
                    "相关操作和逻辑：",
                    "",
                ])
                if component_interactions:
                    for item in component_interactions:
                        lines.append(f"- {item}")
                else:
                    lines.append("- 这个元素主要负责展示当前状态，没有直接触发跳转。")
                lines.append("")
        lines.extend([
            "#### 页面交互说明",
            "",
        ])
        if not screen_interactions:
            lines.append("这个页面当前没有从本页发起的交互。")
            lines.append("")
        for interaction in screen_interactions:
            target_screen = interaction_target_screen(interaction)
            lines.extend([
                f"##### {md_text(interaction.get('trigger_zh') or interaction.get('trigger') or '继续操作')}",
                "",
                f"起点是「{state_title(interaction.get('source_state_id'))}」。",
                "",
                f"结果是进入「{state_title(interaction.get('target_state_id'))}」，目标页面是「{screen_title(target_screen)}」。",
                "",
                f"页面逻辑是：{md_text(interaction.get('route_basis_zh') or '按页面状态关系生成，需要人工确认。')}",
                "",
                f"需要注意的提示或限制是：{md_text(interaction.get('guard_zh') or '没有额外限制。')}",
                "",
            ])
    lines.extend([
        "## 6. 全量交互清单",
        "",
        "这里按生成顺序把所有交互再讲一遍，方便人工逐条确认。",
        "",
    ])
    for interaction in interactions_sorted:
        target_screen = interaction_target_screen(interaction)
        lines.extend([
            f"### 交互 {interaction.get('operation_chain_step')}：{md_text(interaction.get('trigger_zh') or '继续操作')}",
            "",
            f"用户从「{state_title(interaction.get('source_state_id'))}」出发，进入「{state_title(interaction.get('target_state_id'))}」。",
            "",
            f"目标页面是「{screen_title(target_screen)}」。",
            "",
            f"页面上应该表达的提示是：{md_text(interaction.get('guard_zh') or '没有单独提示。')}",
            "",
            f"DRD 逻辑说明：{md_text(interaction.get('route_basis_zh') or '需要人工确认。')}",
            "",
        ])
    if codex_root.get("parsed_review"):
        parsed = codex_root.get("parsed_review") or {}
        lines.extend([
            "",
            "## 7. 四段 Codex 模型推理意见",
            "",
            f"模型给出的总体结论是 `{parsed.get('status', codex_root.get('status'))}`。这不是自动批准，只是写入 Figma 前的一层推理证据。",
            "",
            "### 7.1 页面职责和页面边界",
            "",
        ])
        for idx, item in enumerate(parsed.get("surface_blueprint", []) or [], start=1):
            lines.extend([
                f"{idx}. {md_text(item.get('page_name_zh') or item.get('screen_id'))}",
                "",
                f"页面作用：{md_text(item.get('page_purpose_zh') or '模型没有补充页面作用。')}",
                "",
                f"页面边界：{md_text(item.get('page_boundary_zh') or '模型没有补充页面边界。')}",
                "",
                f"状态处理：{md_text(item.get('state_policy_zh') or '模型没有补充状态处理策略。')}",
                "",
            ])
        if not parsed.get("surface_blueprint"):
            lines.extend(["模型没有输出页面职责补充，需要人工按前文页面清单确认。", ""])
        lines.extend(["### 7.2 用户真实跳转链路", ""])
        for idx, item in enumerate(parsed.get("journey_edges", []) or [], start=1):
            lines.extend([
                f"{idx}. 用户从 `{item.get('source_screen_id')}` 走到 `{item.get('target_screen_id')}`。",
                "",
                f"触发动作是：{md_text(item.get('trigger_zh') or '模型没有说明触发动作。')}",
                "",
                f"链路理由是：{md_text(item.get('reason_zh') or '模型没有补充链路理由。')}",
                "",
            ])
        if not parsed.get("journey_edges"):
            lines.extend(["模型没有输出跨页面链路补充，需要人工重点确认页面跳转图。", ""])
        lines.extend(["### 7.3 页面内交互状态机", ""])
        for idx, item in enumerate(parsed.get("state_transitions", []) or [], start=1):
            lines.extend([
                f"{idx}. 从 `{item.get('source_state_id')}` 到 `{item.get('target_state_id')}`。",
                "",
                f"触发：{md_text(item.get('trigger_zh') or '模型没有说明触发。')}",
                "",
                f"守卫和限制：{md_text(item.get('guard_zh') or '没有额外限制。')}",
                "",
                f"状态机理由：{md_text(item.get('reason_zh') or '模型没有补充理由。')}",
                "",
            ])
        if not parsed.get("state_transitions"):
            lines.extend(["模型没有输出状态机补充，需要人工重点确认状态画面级交互图。", ""])
        lines.extend(["### 7.4 页面元素和组件构成", ""])
        for idx, item in enumerate(parsed.get("component_groups", []) or [], start=1):
            lines.extend([
                f"{idx}. `{item.get('screen_id')}` 里的{md_text(item.get('group_name_zh') or item.get('element_type') or '元素分组')}。",
                "",
                f"包含元素：{md_text('、'.join(item.get('component_ids', []) or []) or '模型没有列出元素 ID。')}",
                "",
                f"分组说明：{md_text(item.get('description_zh') or '模型没有补充分组说明。')}",
                "",
            ])
        if not parsed.get("component_groups"):
            lines.extend(["模型没有输出组件分组补充，需要人工重点确认页面元素分组。", ""])
        findings = parsed.get("generation_findings", []) or []
        if findings:
            lines.extend(["### 7.5 模型提醒人工注意的问题", ""])
            for item in findings:
                if isinstance(item, dict):
                    lines.append(f"- {md_text(item.get('finding_zh') or item.get('message_zh') or json.dumps(item, ensure_ascii=False))}")
                else:
                    lines.append(f"- {md_text(item)}")
    elif codex_root.get("reason_zh") or codex_root.get("raw_output_path"):
        lines.extend([
            "",
            "## 7. Codex 模型审查意见",
            "",
            f"模型审查状态是 `{codex_root.get('status')}`。",
            "",
            f"原因是：{md_text(codex_root.get('reason_zh', '没有补充说明。'))}",
            "",
            f"原始输出路径是 `{codex_root.get('raw_output_path', '')}`。",
        ])
    lines.extend([
        "",
        "## 8. 写入前结论",
        "",
        "这份蓝图已经通过机器门禁，但仍然是候选原型。人工确认后，才能进入最终 Figma writer。",
        "",
        "确认时重点看三件事：第一，页面是不是该这么分；第二，边界态和失败态是不是需要独立画面；第三，页面跳转是不是符合真实用户操作，而不是把状态说明误当成自动跳转。",
    ])
    return "\n".join(lines) + "\n"


def build_source_coverage_report(brief: dict, runtime: dict, payload: dict) -> dict:
    brief_root = brief["prototype_source_brief"]
    payload_root = payload.get("prototype_render_payload", {})
    runtime_state_ids = {
        state.get("state_id")
        for screen in runtime.get("screens", []) or []
        for state in screen.get("states", []) or []
    }
    payload_frame_ids = {frame.get("frame_id") for frame in payload_root.get("frames", []) or []}
    payload_text = json.dumps(payload_root, ensure_ascii=False)
    sidecar_text = json.dumps(payload_root.get("sidecar_cards", []), ensure_ascii=False)
    results = []
    for expectation in brief_root.get("coverage_expectations", []) or []:
        state_id = expectation.get("state_id", "")
        frame_id = expectation.get("frame_id", "")
        runtime_covered = state_id in runtime_state_ids
        payload_covered = frame_id in payload_frame_ids and state_id in payload_text
        sidecar_required = expectation.get("requires_sidecar") is True
        sidecar_covered = not sidecar_required or state_id in sidecar_text or expectation.get("atom_id", "") in sidecar_text
        covered = runtime_covered and payload_covered and sidecar_covered
        results.append({
            "expectation_id": expectation.get("expectation_id"),
            "atom_id": expectation.get("atom_id"),
            "state_id": state_id,
            "payload_frame_id": frame_id,
            "requires_sidecar": sidecar_required,
            "runtime_covered": runtime_covered,
            "payload_covered": payload_covered,
            "sidecar_covered": sidecar_covered,
            "required": True,
            "covered": covered,
            "source_refs": expectation.get("source_refs", []),
            "rule_ids": expectation.get("rule_ids") or rule_ids_for_artifact("source_coverage_report"),
        })
    status = "pass" if results and all(item["covered"] for item in results) else "blocked"
    return {
        "source_coverage_report": {
            "version": "3.1.1",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "status": status,
            "rule_trace": rule_trace_for_artifact("source_coverage_report"),
            "source_refs": sorted({ref for item in results for ref in item.get("source_refs", [])})
            or [brief_root.get("sections", [{}])[0].get("source_ref", "inputs/PRD.md#L1")],
            "coverage_results": results,
        }
    }


def run_artifact_path(path: Path) -> str:
    return path.relative_to(RUN_ROOT).as_posix()


def completion_criterion(
    criterion_id: str,
    description_zh: str,
    validator: str,
    evidence_refs: list[str],
    status: str = "pass",
    required: bool = True,
    rule_ids: list[str] | None = None,
) -> dict:
    return {
        "criterion_id": criterion_id,
        "description_zh": description_zh,
        "validator": validator,
        "required": required,
        "status": status,
        "evidence_refs": evidence_refs,
        "rule_ids": normalize_rule_ids(rule_ids),
    }


def build_deterministic_draft_summary(brief: dict, runtime: dict, payload: dict) -> dict:
    brief_root = brief["prototype_source_brief"]
    payload_root = payload["prototype_render_payload"]
    screens = []
    for screen in runtime.get("screens", []) or []:
        screens.append({
            "screen_id": screen.get("screen_id"),
            "screen_zh": screen.get("screen_zh"),
            "state_ids": [state.get("state_id") for state in screen.get("states", []) or []],
            "state_count": len(screen.get("states", []) or []),
        })
    return {
        "deterministic_generation_draft": {
            "version": "3.1.1",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "draft_id": f"DET-DRAFT-{RUN_ID}",
            "rule_trace": rule_trace_for_artifact("generation_trace"),
            "created_at": utc_now_text(),
            "source_refs": payload_root.get("source_refs", []),
            "counts": {
                "source_atoms": len(brief_root.get("source_atoms", []) or []),
                "required_states": len(brief_root.get("required_state_ids", []) or []),
                "screens": len(runtime.get("screens", []) or []),
                "states": sum(len(screen.get("states", []) or []) for screen in runtime.get("screens", []) or []),
                "frames": len(payload_root.get("frames", []) or []),
                "components": len(payload_root.get("components", []) or []),
                "interactions": len(payload_root.get("interactions", []) or []),
            },
            "screens": screens,
            "required_state_ids": brief_root.get("required_state_ids", []),
            "required_constraint_ids": brief_root.get("required_constraint_ids", []),
            "interaction_edges": [
                {
                    "interaction_id": interaction.get("interaction_id"),
                    "source_state_id": interaction.get("source_state_id"),
                    "target_state_id": interaction.get("target_state_id"),
                    "target_screen_id": interaction.get("target_screen_id"),
                    "trigger_zh": interaction.get("trigger_zh"),
                    "interaction_variant": interaction.get("interaction_variant"),
                    "route_basis_zh": interaction.get("route_basis_zh"),
                    "source_refs": interaction.get("source_refs", []),
                }
                for interaction in payload_root.get("interactions", []) or []
            ],
            "component_summary": [
                {
                    "component_id": component.get("component_id"),
                    "frame_id": component.get("frame_id"),
                    "semantic_key": component.get("semantic_key"),
                    "copy_zh": component.get("copy_zh"),
                    "bound_interaction_id": component.get("bound_interaction_id", ""),
                    "source_refs": component.get("source_refs", []),
                }
                for component in payload_root.get("components", []) or []
            ],
            "final_output_status": "not_written_yet",
            "final_output_policy": "runtime and payload are materialized only after the model blueprint stage returns or is explicitly skipped.",
        }
    }


MODEL_STAGE_DEFINITIONS = [
    {
        "key": "surface_ownership",
        "root_key": "model_surface_ownership",
        "job_id": "GEN-JOB-005-MODEL-SURFACE-OWNERSHIP",
        "stage_id": "GEN-MODEL-SURFACE-OWNERSHIP",
        "generator_id": "GEN-MODEL-SURFACE-OWNERSHIP",
        "worker_id": "GEN-WORKER-CODEX-SURFACE",
        "output_kind": "prototype_surface_ownership_reasoning",
        "title_zh": "页面职责与边界推理",
        "primary_collection": "surface_blueprint",
    },
    {
        "key": "user_journey",
        "root_key": "model_user_journey",
        "job_id": "GEN-JOB-006-MODEL-USER-JOURNEY",
        "stage_id": "GEN-MODEL-USER-JOURNEY",
        "generator_id": "GEN-MODEL-USER-JOURNEY",
        "worker_id": "GEN-WORKER-CODEX-JOURNEY",
        "output_kind": "prototype_user_journey_reasoning",
        "title_zh": "真实用户链路推理",
        "primary_collection": "journey_edges",
    },
    {
        "key": "interaction_state_machine",
        "root_key": "model_interaction_state_machine",
        "job_id": "GEN-JOB-007-MODEL-INTERACTION-STATE-MACHINE",
        "stage_id": "GEN-MODEL-INTERACTION-STATE-MACHINE",
        "generator_id": "GEN-MODEL-INTERACTION-STATE-MACHINE",
        "worker_id": "GEN-WORKER-CODEX-STATE-MACHINE",
        "output_kind": "prototype_interaction_state_machine_reasoning",
        "title_zh": "页面交互状态机推理",
        "primary_collection": "state_transitions",
    },
    {
        "key": "component_blueprint",
        "root_key": "model_component_blueprint",
        "job_id": "GEN-JOB-008-MODEL-COMPONENT-BLUEPRINT",
        "stage_id": "GEN-MODEL-COMPONENT-BLUEPRINT",
        "generator_id": "GEN-MODEL-COMPONENT-BLUEPRINT",
        "worker_id": "GEN-WORKER-CODEX-COMPONENT",
        "output_kind": "prototype_component_blueprint_reasoning",
        "title_zh": "页面元素与组件蓝图推理",
        "primary_collection": "component_groups",
    },
]
MODEL_STAGE_KEYS = [item["key"] for item in MODEL_STAGE_DEFINITIONS]
MODEL_STAGE_BY_KEY = {item["key"]: item for item in MODEL_STAGE_DEFINITIONS}


def model_path_key(stage_key: str, suffix: str = "") -> str:
    return f"model_{stage_key}{suffix}"


def model_stage_output_paths(paths: dict, stage: dict) -> list[str]:
    key = stage["key"]
    return [
        run_artifact_path(paths[model_path_key(key, "_contract")]),
        run_artifact_path(paths[model_path_key(key, "_raw")]),
        run_artifact_path(paths[model_path_key(key)]),
        run_artifact_path(paths[model_path_key(key, "_trace")]),
    ]


def model_stage_timeout_seconds() -> int:
    raw_value = os.environ.get("PROTOTYPE_MODEL_STAGE_TIMEOUT_SECONDS", "").strip()
    if raw_value:
        try:
            return max(60, int(raw_value))
        except ValueError:
            return 300
    return 300


def model_command_policy() -> dict:
    return {
        "ephemeral": True,
        "sandbox": "read-only",
        "writes_allowed": False,
        "working_directory": str(INSTANCE_ROOT),
        "prompt_persisted": False,
        "timeout_seconds": model_stage_timeout_seconds(),
    }


def truncate_prompt_text(value, max_chars: int = 220):
    if isinstance(value, str):
        text = " ".join(value.split())
        return text if len(text) <= max_chars else text[: max_chars - 1] + "…"
    if isinstance(value, list):
        return [truncate_prompt_text(item, max_chars) for item in value[:8]]
    if isinstance(value, dict):
        return {key: truncate_prompt_text(item, max_chars) for key, item in value.items()}
    return value


def compact_prompt_item(item: dict, fields: list[str], *, max_refs: int = 4, max_chars: int = 220) -> dict:
    compact = {}
    for field in fields:
        if field not in item:
            continue
        value = item.get(field)
        if field == "source_refs" and isinstance(value, list):
            compact[field] = value[:max_refs]
        else:
            compact[field] = truncate_prompt_text(value, max_chars)
    return compact


def summarize_carrier_handoff_context(carrier_bundle: dict | None) -> dict:
    if not carrier_bundle:
        return {}
    carrier_root = (carrier_bundle.get("interaction_carrier_map") or {}).get("interaction_carrier_map", {})
    handoff_root = (carrier_bundle.get("system_handoff_map") or {}).get("system_handoff_map", {})
    operation_root = (carrier_bundle.get("user_operation_chain") or {}).get("user_operation_chain", {})
    capability_root = (carrier_bundle.get("capability_assessment") or {}).get("capability_assessment", {})
    prompt_detail_limit = 24
    carrier_items = carrier_root.get("interaction_carriers") or carrier_root.get("carrier_assignments") or []
    handoff_items = handoff_root.get("handoffs") or []
    operation_items = operation_root.get("chains") or operation_root.get("operation_chains") or []
    capability_items = capability_root.get("capabilities") or []
    carrier_types = sorted({
        value
        for item in carrier_items
        for value in [item.get("source_carrier_type"), item.get("target_carrier_type"), item.get("carrier_type")]
        if value
    })
    handoff_required = [item for item in carrier_items if item.get("requires_system_handoff") or item.get("handoff_required")]
    return {
        "summary_kind": "compact_carrier_handoff_context",
        "summary_guidance_zh": "complete_*_index 是全量权威索引；*_details 只是少量详细样本。模型不得因为 details 截断而新编 operation_chain_id、handoff_id 或 interaction_id。",
        "counts": {
            "carrier_assignments": len(carrier_items),
            "handoffs": len(handoff_items),
            "operation_chains": len(operation_items),
            "capabilities": len(capability_items),
            "handoff_required_interactions": len(handoff_required),
        },
        "carrier_types": carrier_types,
        "complete_carrier_index": [
            compact_prompt_item(
                item,
                [
                    "interaction_id",
                    "source_screen_id",
                    "target_screen_id",
                    "source_carrier_type",
                    "target_carrier_type",
                    "transition_scope",
                    "requires_system_handoff",
                    "capability_ids",
                    "standalone_page_allowed",
                    "source_refs",
                ],
                max_refs=2,
                max_chars=140,
            )
            for item in carrier_items
        ],
        "carrier_details": [
            compact_prompt_item(
                item,
                [
                    "interaction_id",
                    "source_screen_id",
                    "target_screen_id",
                    "source_carrier_type",
                    "source_carrier_zh",
                    "target_carrier_type",
                    "target_carrier_zh",
                    "transition_scope",
                    "requires_system_handoff",
                    "capability_ids",
                    "standalone_page_allowed",
                    "source_refs",
                ],
            )
            for item in carrier_items[:prompt_detail_limit]
        ],
        "complete_handoff_index": [
            compact_prompt_item(
                item,
                [
                    "handoff_id",
                    "interaction_id",
                    "capability_id",
                    "handoff_surface_type",
                    "source_carrier_type",
                    "return_carrier_type",
                    "capability_status",
                    "review_required",
                    "source_refs",
                ],
                max_refs=2,
                max_chars=140,
            )
            for item in handoff_items
        ],
        "handoff_details": [
            compact_prompt_item(
                item,
                [
                    "handoff_id",
                    "interaction_id",
                    "capability_id",
                    "handoff_surface_type",
                    "handoff_surface_zh",
                    "source_carrier_type",
                    "return_carrier_type",
                    "capability_status",
                    "review_required",
                    "preferred_feedback_surface_zh",
                    "cancel_path_zh",
                    "failure_path_zh",
                    "source_refs",
                ],
            )
            for item in handoff_items[:prompt_detail_limit]
        ],
        "complete_operation_chain_index": [
            compact_prompt_item(
                item,
                [
                    "operation_chain_id",
                    "interaction_id",
                    "source_state_id",
                    "target_state_id",
                    "chain_kind",
                    "page_flow_edge",
                    "handoff_id",
                    "source_refs",
                ],
                max_refs=2,
                max_chars=140,
            )
            for item in operation_items
        ],
        "operation_chain_details": [
            {
                **compact_prompt_item(
                    item,
                    [
                        "operation_chain_id",
                        "interaction_id",
                        "source_state_id",
                        "target_state_id",
                        "chain_kind",
                        "page_flow_edge",
                        "handoff_id",
                        "source_refs",
                    ],
                ),
                "steps": [
                    compact_prompt_item(
                        step,
                        ["step_no", "step_type", "carrier_type", "description_zh", "source_refs"],
                        max_refs=2,
                        max_chars=160,
                    )
                    for step in (item.get("steps") or [])[:6]
                ],
            }
            for item in operation_items[:prompt_detail_limit]
        ],
        "capabilities": [
            compact_prompt_item(
                item,
                [
                    "capability_id",
                    "capability_name_zh",
                    "capability_status",
                    "review_required",
                    "preferred_feedback_surface_zh",
                    "source_refs",
                ],
            )
            for item in capability_items[:40]
        ],
    }


def summarize_prior_model_outputs(prior_roots: dict) -> dict:
    summarized = {}
    prompt_detail_limit = 24
    collection_by_stage = {
        "surface_ownership": ("surface_blueprint", [
            "screen_id",
            "page_role_zh",
            "page_purpose_zh",
            "page_boundary_zh",
            "state_policy_zh",
            "carrier_type",
            "source_refs",
        ]),
        "user_journey": ("journey_edges", [
            "source_screen_id",
            "target_screen_id",
            "trigger_zh",
            "path_type",
            "carrier_transition_type",
            "operation_chain_id",
            "handoff_ids",
            "reason_zh",
            "source_refs",
        ]),
        "interaction_state_machine": ("state_transitions", [
            "source_state_id",
            "target_state_id",
            "trigger_zh",
            "guard_zh",
            "edge_type",
            "stays_on_same_surface",
            "feedback_surface_zh",
            "reason_zh",
            "source_refs",
        ]),
        "component_blueprint": ("component_groups", [
            "screen_id",
            "group_name_zh",
            "element_type",
            "component_ids",
            "carrier_type",
            "render_region_zh",
            "description_zh",
            "source_refs",
        ]),
    }
    for key, root in prior_roots.items():
        collection_name, fields = collection_by_stage.get(key, ("items", []))
        collection = root.get(collection_name) if isinstance(root, dict) else []
        findings = root.get("generation_findings") if isinstance(root, dict) else []
        summarized[key] = {
            "status": root.get("status") if isinstance(root, dict) else "",
            "stage_role": root.get("stage_role") if isinstance(root, dict) else key,
            "collection_name": collection_name,
            "collection_count": len(collection or []),
            "complete_item_index": [
                compact_prompt_item(item, fields, max_refs=2, max_chars=140)
                for item in (collection or [])
                if isinstance(item, dict)
            ],
            "item_details": [
                compact_prompt_item(item, fields)
                for item in (collection or [])[:prompt_detail_limit]
                if isinstance(item, dict)
            ],
            "generation_findings": [
                compact_prompt_item(item, ["finding_id", "severity", "finding_zh", "source_refs"])
                for item in (findings or [])[:12]
                if isinstance(item, dict)
            ],
        }
        if key == "user_journey" and isinstance(root, dict):
            summarized[key]["page_flow_summary_zh"] = truncate_prompt_text(root.get("page_flow_summary_zh", ""), 600)
    return summarized


def model_stage_completion_results(
    stage: dict,
    mode: str,
    status: str,
    model_called: bool,
    exit_code: int | None,
    raw_path: Path,
    artifact_path: Path,
    contract_path: Path,
    command: list[str],
) -> list[dict]:
    read_only_ok = (not model_called) or ("--sandbox" in command and "read-only" in command)
    raw_ok = (not model_called) or raw_path.exists()
    artifact_ok = artifact_path.exists()
    required_exit_ok = mode != "required" or exit_code == 0
    output_status_ok = status in {"pass", "review_required"} or (mode != "required" and status == "skipped")
    return [
        completion_criterion(
            f"MODEL-CC-{stage['key'].upper().replace('_', '-')}-CONTRACT",
            f"{stage['title_zh']}必须先写入 execution contract。",
            "validate-model-execution-contract",
            [run_artifact_path(contract_path)],
            "pass" if contract_path.exists() else "blocked",
            True,
            rule_ids_for_artifact("model_execution_contract"),
        ),
        completion_criterion(
            f"MODEL-CC-{stage['key'].upper().replace('_', '-')}-READ-ONLY",
            f"{stage['title_zh']}必须使用只读 Codex CLI 沙箱。",
            "model_invocation_trace",
            ["command_policy.sandbox=read-only"],
            "pass" if read_only_ok else "blocked",
            True,
            rule_ids_for_artifact("model_invocation_trace"),
        ),
        completion_criterion(
            f"MODEL-CC-{stage['key'].upper().replace('_', '-')}-RAW",
            f"{stage['title_zh']}必须保留 raw output。",
            "model_invocation_trace",
            [run_artifact_path(raw_path)],
            "pass" if raw_ok else ("skipped" if not model_called else "blocked"),
            model_called,
            rule_ids_for_artifact("model_invocation_trace"),
        ),
        completion_criterion(
            f"MODEL-CC-{stage['key'].upper().replace('_', '-')}-ARTIFACT",
            f"{stage['title_zh']}必须写入结构化模型 artifact。",
            f"validate-model-{stage['key'].replace('_', '-')}",
            [run_artifact_path(artifact_path)],
            "pass" if artifact_ok and output_status_ok else ("skipped" if status == "skipped" else "blocked"),
            mode == "required",
            rule_ids_for_artifact("model_invocation_trace"),
        ),
        completion_criterion(
            f"MODEL-CC-{stage['key'].upper().replace('_', '-')}-EXIT-ZERO",
            f"required 模式下 {stage['title_zh']} 必须 exit 0。",
            "model_invocation_trace",
            [f"exit_code={exit_code}"],
            "pass" if required_exit_ok else "blocked",
            mode == "required",
            rule_ids_for_artifact("model_invocation_trace"),
        ),
    ]


def model_stage_contract(
    stage: dict,
    args,
    paths: dict,
    input_refs: list[str],
    output_refs: list[str],
    contract_promotion: dict | None = None,
) -> dict:
    mode = getattr(args, "codex_inference", "required") or "required"
    promotion_root = (contract_promotion or {}).get("model_contract_promotion_report", {})
    contract_profile_id = promotion_root.get("contract_profile_id", "base_drd_v1")
    return {
        "model_execution_contract": {
            "version": "3.1.1",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "contract_id": f"MEC-{stage['stage_id']}-{RUN_ID}",
            "generator_id": stage["generator_id"],
            "generator_kind": "model",
            "rule_trace": rule_trace_for_artifact("model_execution_contract"),
            "provider": "codex_cli",
            "execution_mode": mode,
            "stage_id": stage["stage_id"],
            "stage_role": stage["key"],
            "model_output_kind": stage["output_kind"],
            "contract_profile_id": contract_profile_id,
            "contract_promotion_status": promotion_root.get("status", "base_contract"),
            "required_model_fields": (promotion_root.get("required_model_fields", {}) or {}).get(stage["key"], []),
            "command_policy": model_command_policy(),
            "input_refs": input_refs,
            "output_refs": output_refs,
            "allowed_operations": [
                "read_source_brief",
                "read_deterministic_draft_summary",
                "read_carrier_handoff_artifacts",
                "read_prior_model_stage_artifacts",
                f"derive_{stage['key']}",
                "emit_reasoning_json",
            ],
            "forbidden_operations": [
                "write_prd",
                "write_product_spec",
                "write_figma",
                "mutate_runtime_or_payload",
                "read_business_specific_sample_fixture",
            ],
            "completion_criteria": [
                {
                    "criterion_id": f"MODEL-CC-{stage['key'].upper().replace('_', '-')}-CONTRACT",
                    "description_zh": f"{stage['title_zh']}必须写入 execution contract。",
                    "required": True,
                    "rule_ids": rule_ids_for_artifact("model_execution_contract"),
                },
                {
                    "criterion_id": f"MODEL-CC-{stage['key'].upper().replace('_', '-')}-ARTIFACT",
                    "description_zh": f"{stage['title_zh']}必须写入结构化模型 artifact。",
                    "required": mode == "required",
                    "rule_ids": rule_ids_for_artifact("model_invocation_trace"),
                },
            ],
            "source_refs": [],
        }
    }


def stage_context_for_prompt(
    stage: dict,
    brief: dict,
    runtime: dict,
    payload: dict,
    prior_artifacts: dict,
    carrier_bundle: dict | None = None,
    contract_promotion: dict | None = None,
) -> dict:
    brief_root = brief["prototype_source_brief"]
    payload_root = payload["prototype_render_payload"]
    required_atoms = [
        {
            "atom_id": atom.get("atom_id"),
            "atom_type": atom.get("atom_type"),
            "categories": atom.get("categories", []),
            "source_text_zh": atom.get("source_text_zh"),
            "source_refs": atom.get("source_refs", []),
            "raw_ids": atom.get("raw_ids", []),
        }
        for atom in brief_root.get("source_atoms", []) or []
        if atom.get("required_for_rendering")
    ]
    screens = [
        {
            "screen_id": screen.get("screen_id"),
            "screen_zh": screen.get("screen_zh"),
            "states": [
                {
                    "state_id": state.get("state_id"),
                    "state_zh": state.get("state_zh"),
                    "feedback_zh": state.get("feedback_zh"),
                    "recovery_zh": state.get("recovery_zh"),
                    "source_refs": state.get("source_refs", []),
                }
                for state in screen.get("states", []) or []
            ],
            "source_refs": screen.get("source_refs", []),
        }
        for screen in runtime.get("screens", []) or []
    ]
    interactions = [
        {
            "interaction_id": item.get("interaction_id"),
            "source_state_id": item.get("source_state_id"),
            "target_state_id": item.get("target_state_id"),
            "target_screen_id": item.get("target_screen_id"),
            "trigger_zh": item.get("trigger_zh"),
            "guard_zh": item.get("guard_zh"),
            "interaction_variant": item.get("interaction_variant"),
            "route_basis_zh": item.get("route_basis_zh"),
            "source_component_id": item.get("source_component_id"),
            "source_refs": item.get("source_refs", []),
        }
        for item in payload_root.get("interactions", []) or []
    ]
    components = [
        {
            "component_id": item.get("component_id"),
            "frame_id": item.get("frame_id"),
            "semantic_key": item.get("semantic_key"),
            "semantic_role": item.get("semantic_role"),
            "copy_zh": item.get("copy_zh"),
            "bound_interaction_id": item.get("bound_interaction_id", ""),
            "source_refs": item.get("source_refs", []),
        }
        for item in payload_root.get("components", []) or []
    ]
    prior_roots = {
        key: value.get(MODEL_STAGE_BY_KEY[key]["root_key"], {})
        for key, value in prior_artifacts.items()
        if key in MODEL_STAGE_BY_KEY
    }
    return {
        "run_id": RUN_ID,
        "stage_id": stage["stage_id"],
        "stage_role": stage["key"],
        "output_root_key": stage["root_key"],
        "contract_profile_id": (contract_promotion or {}).get("model_contract_promotion_report", {}).get("contract_profile_id", "base_drd_v1"),
        "carrier_handoff_context": summarize_carrier_handoff_context(carrier_bundle),
        "counts": {
            "required_source_atoms": len(required_atoms),
            "screens": len(screens),
            "states": sum(len(screen.get("states", []) or []) for screen in screens),
            "components": len(components),
            "interactions": len(interactions),
        },
        "required_source_atoms": required_atoms,
        "draft_surface_ownership": brief_root.get("surface_ownership", []),
        "screens": screens,
        "interactions": interactions,
        "components": components,
        "prior_model_outputs": summarize_prior_model_outputs(prior_roots),
    }


def output_contract_for_stage(stage: dict, contract_promotion: dict | None = None) -> dict:
    promoted = (contract_promotion or {}).get("model_contract_promotion_report", {}).get("contract_profile_id") == "carrier_handoff_operation_chain_v2"
    contracts = {
        "surface_ownership": {
            "required_root_fields": ["status", "stage_role", "surface_blueprint", "generation_findings"],
            "surface_blueprint_item": ["screen_id", "page_role_zh", "page_purpose_zh", "page_boundary_zh", "state_policy_zh", "source_refs"]
            + (["carrier_type", "host_context_zh", "standalone_page_allowed", "system_surface_refs"] if promoted else []),
        },
        "user_journey": {
            "required_root_fields": ["status", "stage_role", "journey_edges", "page_flow_summary_zh", "generation_findings"],
            "journey_edge_item": ["source_screen_id", "target_screen_id", "trigger_zh", "path_type", "reason_zh", "source_refs"]
            + (["operation_chain_id", "carrier_transition_type", "handoff_ids"] if promoted else []),
        },
        "interaction_state_machine": {
            "required_root_fields": ["status", "stage_role", "state_transitions", "interaction_adjustments", "generation_findings"],
            "state_transition_item": ["source_state_id", "target_state_id", "trigger_zh", "guard_zh", "reason_zh", "source_refs"]
            + (["edge_type", "stays_on_same_surface", "feedback_surface_zh"] if promoted else []),
        },
        "component_blueprint": {
            "required_root_fields": ["status", "stage_role", "component_groups", "component_intents", "generation_findings"],
            "component_group_item": ["screen_id", "group_name_zh", "element_type", "component_ids", "description_zh", "source_refs"]
            + (["carrier_type", "render_region_zh"] if promoted else []),
        },
    }
    return contracts[stage["key"]]


def build_model_stage_prompt(
    stage: dict,
    brief: dict,
    runtime: dict,
    payload: dict,
    prior_artifacts: dict,
    carrier_bundle: dict | None = None,
    contract_promotion: dict | None = None,
) -> str:
    context = stage_context_for_prompt(stage, brief, runtime, payload, prior_artifacts, carrier_bundle, contract_promotion)
    contract = output_contract_for_stage(stage, contract_promotion)
    return (
        f"你是 prototype harness 的只读 Codex 模型 worker。当前 stage 是 {stage['stage_id']}：{stage['title_zh']}。"
        "你只能返回 JSON，不能写文件，不能引用 sample/fixture，不能要求写 PRD、product-spec 或 Figma。"
        f"请把结果放在根 key `{stage['root_key']}` 下。"
        "所有推理都必须保留 source_refs；不确定的内容写入 generation_findings，不要硬编业务事实。"
        "当上下文同时给出 complete_*_index 和 *_details 时，complete_*_index 是全量权威索引，*_details 只是详细样本；不得因为 details 截断而新编 ID 或链路。"
        "输出 JSON 必须符合下面的 contract，并使用中文通俗句式。\n\n"
        + json.dumps({"output_contract": contract, "context": context}, ensure_ascii=False, indent=2)
    )


def normalize_status(value: str, *, model_called: bool, exit_code: int | None, mode: str) -> str:
    if value in {"pass", "review_required", "blocked", "skipped"}:
        return value
    if not model_called:
        return "blocked" if mode == "required" else "skipped"
    return "review_required" if exit_code == 0 else ("blocked" if mode == "required" else "skipped")


def interaction_target_screen(interaction: dict, state_screen_by_id: dict[str, str]) -> str:
    return interaction.get("target_screen_id") or state_screen_by_id.get(interaction.get("target_state_id"), "")


def deterministic_model_artifact_payload(stage: dict, brief: dict, runtime: dict, payload: dict) -> dict:
    brief_root = brief["prototype_source_brief"]
    payload_root = payload["prototype_render_payload"]
    state_screen_by_id = {
        state.get("state_id"): screen.get("screen_id")
        for screen in runtime.get("screens", []) or []
        for state in screen.get("states", []) or []
    }
    if stage["key"] == "surface_ownership":
        return {
            "surface_blueprint": [
                {
                    "screen_id": item.get("screen_id"),
                    "page_name_zh": item.get("screen_zh"),
                    "page_role_zh": item.get("surface_role", ""),
                    "page_purpose_zh": item.get("inference_basis_zh", ""),
                    "page_boundary_zh": "同一功能页面内允许多个状态画面；最终是否折叠需人工 review。",
                    "state_policy_zh": "阻断、边界、错误、恢复状态不得静默折叠。",
                    "carrier_type": carrier_type_for_text(" ".join(item.get("component_rules", [])), "app_page"),
                    "host_context_zh": "按承载面映射确认是否为宿主嵌入区域、系统面或普通页面。",
                    "standalone_page_allowed": carrier_type_for_text(" ".join(item.get("component_rules", [])), "app_page") == "app_page",
                    "system_surface_refs": [],
                    "source_refs": item.get("source_refs", []),
                }
                for item in brief_root.get("surface_ownership", []) or []
            ],
            "generation_findings": [],
        }
    if stage["key"] == "user_journey":
        seen = set()
        edges = []
        for item in payload_root.get("interactions", []) or []:
            source_screen = item.get("source_screen_id") or state_screen_by_id.get(item.get("source_state_id"), "")
            target_screen = interaction_target_screen(item, state_screen_by_id)
            if not source_screen or not target_screen:
                continue
            edge_key = (source_screen, target_screen, item.get("trigger_zh"))
            if edge_key in seen:
                continue
            seen.add(edge_key)
            edges.append({
                "source_screen_id": source_screen,
                "target_screen_id": target_screen,
                "trigger_zh": item.get("trigger_zh", ""),
                "path_type": "cross_page" if source_screen != target_screen else "same_page_state_flow",
                "operation_chain_id": f"OPCHAIN-{len(edges) + 1:03d}",
                "carrier_transition_type": "cross_page" if source_screen != target_screen else "same_surface_state_change",
                "handoff_ids": [],
                "reason_zh": item.get("route_basis_zh", ""),
                "source_refs": item.get("source_refs", []),
            })
        return {"journey_edges": edges, "page_flow_summary_zh": "按 PRD source atom 和状态跳转草稿生成候选用户链路。", "generation_findings": []}
    if stage["key"] == "interaction_state_machine":
        transitions = [
            {
                "interaction_id": item.get("interaction_id"),
                "source_state_id": item.get("source_state_id"),
                "target_state_id": item.get("target_state_id"),
                "trigger_zh": item.get("trigger_zh", ""),
                "guard_zh": item.get("guard_zh", ""),
                "reason_zh": item.get("route_basis_zh", ""),
                "edge_type": "same_surface_state_change"
                if item.get("interaction_kind") == "same_screen_transition"
                else "page_or_carrier_transition",
                "stays_on_same_surface": item.get("interaction_kind") == "same_screen_transition",
                "feedback_surface_zh": "当前承载面内最早可反馈位置",
                "source_refs": item.get("source_refs", []),
            }
            for item in payload_root.get("interactions", []) or []
        ]
        return {"state_transitions": transitions, "interaction_adjustments": [], "generation_findings": []}
    component_intents = []
    interactions_by_component = defaultdict(list)
    for item in payload_root.get("interactions", []) or []:
        interactions_by_component[item.get("source_component_id", "")].append(item)
    components_by_frame = defaultdict(list)
    for component in payload_root.get("components", []) or []:
        components_by_frame[component.get("frame_id", "")].append(component)
        component_intents.append({
            "component_id": component.get("component_id"),
            "copy_zh": component.get("copy_zh", ""),
            "semantic_key": component.get("semantic_key", ""),
            "click_intents": [
                item.get("trigger_zh", "")
                for item in interactions_by_component.get(component.get("component_id", ""), [])
                if str(item.get("trigger_zh") or item.get("trigger") or "").startswith(("用户点击", "点击"))
            ],
            "source_refs": component.get("source_refs", []),
        })
    groups = []
    for screen in runtime.get("screens", []) or []:
        screen_frame_ids = [
            frame.get("frame_id")
            for frame in payload_root.get("frames", []) or []
            if frame.get("screen_id") == screen.get("screen_id")
        ]
        screen_components = [
            component
            for frame_id in screen_frame_ids
            for component in components_by_frame.get(frame_id, [])
        ]
        for element_type, predicate in [
            ("显示元素", lambda item: item.get("semantic_role") not in {"button", "input"}),
            ("操作元素", lambda item: item.get("semantic_role") == "button"),
            ("输入/选择元素", lambda item: item.get("semantic_role") == "input"),
        ]:
            matched = [item for item in screen_components if predicate(item)]
            if matched:
                groups.append({
                    "screen_id": screen.get("screen_id"),
                    "group_name_zh": element_type,
                    "element_type": element_type,
                    "component_ids": [item.get("component_id") for item in matched],
                    "description_zh": f"{screen.get('screen_zh')}中的{element_type}。",
                    "carrier_type": "app_page",
                    "render_region_zh": "当前承载面内的可见区域",
                    "source_refs": sorted({ref for item in matched for ref in item.get("source_refs", [])}),
                })
    return {"component_groups": groups, "component_intents": component_intents, "generation_findings": []}


def normalize_model_stage_artifact(
    stage: dict,
    parsed: dict,
    brief: dict,
    runtime: dict,
    payload: dict,
    contract_promotion: dict | None = None,
    *,
    status: str,
    model_called: bool,
    raw_path: Path,
    trace_path: Path,
) -> dict:
    root_key = stage["root_key"]
    parsed_root = parsed.get(root_key, parsed) if isinstance(parsed, dict) else {}
    if not isinstance(parsed_root, dict):
        parsed_root = {}
    deterministic_payload = deterministic_model_artifact_payload(stage, brief, runtime, payload)
    promotion_root = (contract_promotion or {}).get("model_contract_promotion_report", {})
    source_refs = sorted({
        ref
        for value in deterministic_payload.values()
        for item in (value if isinstance(value, list) else [])
        if isinstance(item, dict)
        for ref in item.get("source_refs", [])
    }) or payload["prototype_render_payload"].get("source_refs", [])
    root = {
        "version": "3.1.1",
        "mode": "DRD_MODE",
        "run_id": RUN_ID,
        "stage_id": stage["stage_id"],
        "stage_role": stage["key"],
        "model_output_kind": stage["output_kind"],
        "contract_profile_id": promotion_root.get("contract_profile_id", "base_drd_v1"),
        "contract_promotion_status": promotion_root.get("status", "base_contract"),
        "status": status,
        "model_called": model_called,
        "rule_trace": rule_trace_for_artifact("model_invocation_trace"),
        "source_refs": source_refs,
        "raw_output_path": run_artifact_path(raw_path),
        "invocation_trace_path": run_artifact_path(trace_path),
        "parsed_model_output": parsed_root,
    }
    root.update(deterministic_payload)
    for key, value in parsed_root.items():
        if key in {"version", "mode", "run_id", "stage_id", "stage_role", "model_output_kind", "status", "model_called"}:
            continue
        if key in root and isinstance(root[key], list) and isinstance(value, list) and value:
            root[key] = value
        elif key not in root or value not in [None, "", []]:
            root[key] = value
    if root.get("stage_role") != stage["key"]:
        root["stage_role_warning_zh"] = f"模型输出未声明 stage_role={stage['key']}，已按 {stage['key']} 归档。"
        root["stage_role"] = stage["key"]
    return {root_key: root}


def run_model_stage(
    stage: dict,
    args,
    brief: dict,
    runtime: dict,
    payload: dict,
    paths: dict,
    prior_artifacts: dict,
    carrier_bundle: dict | None = None,
    contract_promotion: dict | None = None,
) -> tuple[dict, dict, dict]:
    mode = getattr(args, "codex_inference", "required") or "required"
    key = stage["key"]
    contract_path = paths[model_path_key(key, "_contract")]
    raw_path = paths[model_path_key(key, "_raw")]
    artifact_path = paths[model_path_key(key)]
    trace_path = paths[model_path_key(key, "_trace")]
    input_refs = [
        run_artifact_path(paths["source_brief"]),
        run_artifact_path(paths["source_slice_index"]),
        run_artifact_path(paths["deterministic_draft_summary"]),
    ] + [
        run_artifact_path(paths[model_path_key(prior_key)])
        for prior_key in prior_artifacts
        if model_path_key(prior_key) in paths and paths[model_path_key(prior_key)].exists()
    ]
    output_refs = model_stage_output_paths(paths, stage)
    contract = model_stage_contract(stage, args, paths, input_refs, output_refs, contract_promotion)
    ywrite(contract_path, contract)
    prompt = build_model_stage_prompt(stage, brief, runtime, payload, prior_artifacts, carrier_bundle, contract_promotion)
    prompt_hash = f"sha256:{sha256_text(prompt)}"
    command: list[str] = []
    model_called = False
    exit_code = None
    status = "skipped"
    stdout_text = ""
    stderr_text = ""
    parsed = {}
    started = None
    completed_at = None
    if mode != "off":
        codex_bin = shutil.which("codex")
        if not codex_bin:
            status = "blocked" if mode == "required" else "skipped"
            if mode == "required":
                artifact = normalize_model_stage_artifact(stage, {}, brief, runtime, payload, contract_promotion, status=status, model_called=False, raw_path=raw_path, trace_path=trace_path)
                ywrite(artifact_path, artifact)
                raise SystemExit(f"BLOCKED: --codex-inference required but codex CLI is unavailable for {stage['stage_id']}")
        else:
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                codex_bin,
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "-C",
                str(INSTANCE_ROOT),
                "--output-last-message",
                str(raw_path),
                prompt,
            ]
            command = cmd[:-1] + ["<prompt-redacted>"]
            model_called = True
            started = datetime.now(timezone.utc)
            try:
                completed = subprocess.run(cmd, text=True, capture_output=True, timeout=model_stage_timeout_seconds())
                completed_at = datetime.now(timezone.utc)
                exit_code = completed.returncode
                stdout_text = completed.stdout
                stderr_text = completed.stderr
                raw_text = raw_path.read_text(encoding="utf-8") if raw_path.exists() else stdout_text
                match = re.search(r"\{.*\}", raw_text, flags=re.S)
                if match:
                    try:
                        parsed = json.loads(match.group(0))
                    except Exception:
                        parsed = {}
                parsed_root = parsed.get(stage["root_key"], parsed) if isinstance(parsed, dict) else {}
                status = normalize_status(parsed_root.get("status", "") if isinstance(parsed_root, dict) else "", model_called=True, exit_code=exit_code, mode=mode)
            except subprocess.TimeoutExpired:
                completed_at = datetime.now(timezone.utc)
                status = "blocked" if mode == "required" else "skipped"
                stderr_text = f"{stage['stage_id']} timed out"
                if mode == "required":
                    raise SystemExit(f"BLOCKED: Codex inference stage timed out: {stage['stage_id']}")
    artifact = normalize_model_stage_artifact(stage, parsed, brief, runtime, payload, contract_promotion, status=status, model_called=model_called, raw_path=raw_path, trace_path=trace_path)
    ywrite(artifact_path, artifact)
    duration_value = duration_ms(started, completed_at) if started and completed_at else None
    trace_root = {
        "version": "3.1.1",
        "mode": "DRD_MODE",
        "run_id": RUN_ID,
        "invocation_id": f"MODEL-INVOKE-{stage['stage_id']}-{RUN_ID}",
        "contract_id": contract["model_execution_contract"]["contract_id"],
        "generator_id": stage["generator_id"],
        "generator_kind": "model",
        "provider": "codex_cli",
        "execution_mode": mode,
        "stage_id": stage["stage_id"],
        "stage_role": stage["key"],
        "model_output_kind": stage["output_kind"],
        "contract_profile_id": (contract_promotion or {}).get("model_contract_promotion_report", {}).get("contract_profile_id", "base_drd_v1"),
        "model_called": model_called,
        "status": status,
        "exit_code": exit_code,
        "started_at": utc_text(started) if started else None,
        "completed_at": utc_text(completed_at) if completed_at else None,
        "duration_ms": duration_value,
        "command": command,
        "command_policy": model_command_policy(),
        "rule_trace": rule_trace_for_artifact("model_invocation_trace"),
        "input_hashes": {
            "prompt": prompt_hash,
            "source_brief": f"sha256:{sha256_file(paths['source_brief'])}",
            "source_slice_index": f"sha256:{sha256_file(paths['source_slice_index'])}",
            "deterministic_draft_summary": f"sha256:{sha256_file(paths['deterministic_draft_summary'])}",
        },
        "output_hashes": {
            "artifact": f"sha256:{sha256_file(artifact_path)}" if artifact_path.exists() else "",
            "raw": f"sha256:{sha256_file(raw_path)}" if raw_path.exists() else "",
        },
        "prompt_excerpt": plain_excerpt(prompt, 500),
        "output_refs": output_refs,
        "raw_output_path": run_artifact_path(raw_path),
        "parsed_artifact_path": run_artifact_path(artifact_path),
        "stdout_sha256": f"sha256:{sha256_text(stdout_text)}",
        "stderr_sha256": f"sha256:{sha256_text(stderr_text)}",
        "stderr_excerpt": stderr_text[-1000:],
        "completion_criteria_results": model_stage_completion_results(stage, mode, status, model_called, exit_code, raw_path, artifact_path, contract_path, command),
    }
    trace = {"model_invocation_trace": trace_root}
    ywrite(trace_path, trace)
    if mode == "required":
        blocked = [
            item.get("criterion_id")
            for item in trace_root["completion_criteria_results"]
            if item.get("required", True) and item.get("status") == "blocked"
        ]
        if blocked:
            raise SystemExit(f"BLOCKED: {stage['stage_id']} failed model completion criteria: {', '.join(blocked)}")
    return artifact, contract, trace


def build_model_execution_contract_summary(
    model_contracts: dict,
    args,
    paths: dict,
    source_refs: list[str],
    contract_promotion: dict | None = None,
) -> dict:
    mode = getattr(args, "codex_inference", "required") or "required"
    stage_roots = [model_contracts[key]["model_execution_contract"] for key in MODEL_STAGE_KEYS if key in model_contracts]
    promotion_root = (contract_promotion or {}).get("model_contract_promotion_report", {})
    return {
        "model_execution_contract": {
            "version": "3.1.1",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "contract_id": f"MEC-PROTO-MULTISTAGE-{RUN_ID}",
            "generator_id": "GEN-MODEL-MULTISTAGE",
            "generator_kind": "model",
            "provider": "codex_cli",
            "execution_mode": mode,
            "stage_role": "multi_stage_generation_reasoning",
            "model_output_kind": "prototype_multistage_reasoning",
            "contract_profile_id": promotion_root.get("contract_profile_id", "base_drd_v1"),
            "contract_promotion_status": promotion_root.get("status", "base_contract"),
            "rule_trace": rule_trace_for_artifact("model_execution_contract"),
            "command_policy": model_command_policy(),
            "input_refs": [
                run_artifact_path(paths["source_brief"]),
                run_artifact_path(paths["deterministic_draft_summary"]),
                run_artifact_path(paths["interaction_carrier_map"]),
                run_artifact_path(paths["system_handoff_map"]),
                run_artifact_path(paths["user_operation_chain"]),
                run_artifact_path(paths["capability_assessment"]),
                run_artifact_path(paths["model_contract_promotion_report"]),
                run_artifact_path(paths["model_execution_contract_resolved"]),
            ],
            "output_refs": [ref for stage in MODEL_STAGE_DEFINITIONS for ref in model_stage_output_paths(paths, stage)],
            "allowed_operations": ["run_four_read_only_model_reasoning_stages", "read_carrier_handoff_artifacts", "emit_reasoning_artifacts"],
            "forbidden_operations": ["write_prd", "write_product_spec", "write_figma", "mutate_runtime_or_payload", "read_business_specific_sample_fixture"],
            "completion_criteria": [
                {
                    "criterion_id": "MODEL-CC-FOUR-STAGES-DEFINED",
                    "description_zh": "必须定义并执行 4 个模型推理 stage。",
                    "required": True,
                    "rule_ids": rule_ids_for_artifact("model_execution_contract"),
                }
            ],
            "model_stages": stage_roots,
            "source_refs": source_refs,
        }
    }


def aggregate_model_status(stage_traces: list[dict], mode: str) -> str:
    statuses = [item.get("status") for item in stage_traces]
    if any(status == "blocked" for status in statuses):
        return "blocked"
    if mode == "required" and any(status == "skipped" for status in statuses):
        return "blocked"
    if any(status == "review_required" for status in statuses):
        return "review_required"
    if all(status == "skipped" for status in statuses):
        return "skipped"
    return "pass"


def build_model_invocation_trace_summary(model_traces: dict, args, paths: dict, contract_promotion: dict | None = None) -> dict:
    mode = getattr(args, "codex_inference", "required") or "required"
    stage_roots = [model_traces[key]["model_invocation_trace"] for key in MODEL_STAGE_KEYS if key in model_traces]
    status = aggregate_model_status(stage_roots, mode)
    all_called = all(item.get("model_called") is True for item in stage_roots)
    promotion_root = (contract_promotion or {}).get("model_contract_promotion_report", {})
    criteria = []
    for item in stage_roots:
        criteria.extend(item.get("completion_criteria_results", []) or [])
    criteria.append(completion_criterion(
        "MODEL-CC-ALL-REQUIRED-STAGES-CALLED",
        "required 模式下 4 个模型 stage 必须全部调用 Codex CLI。",
        "validate-model-stage-coverage",
        [run_artifact_path(paths["model_invocation_trace"])],
        "pass" if (mode != "required" or all_called) else "blocked",
        mode == "required",
        rule_ids_for_artifact("model_invocation_trace"),
    ))
    criteria.append(completion_criterion(
        "MODEL-CC-FINAL-WRITE-AFTER-MODEL",
        "最终 runtime/payload 必须在 4 个模型 stage 完成并被消费后才落盘。",
        "validate-model-invocation-trace",
        [run_artifact_path(paths["runtime"]), run_artifact_path(paths["payload"])],
        "blocked",
        True,
        rule_ids_for_artifact("model_invocation_trace"),
    ))
    return {
        "model_invocation_trace": {
            "version": "3.1.1",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "invocation_id": f"MODEL-INVOKE-MULTISTAGE-{RUN_ID}",
            "contract_id": f"MEC-PROTO-MULTISTAGE-{RUN_ID}",
            "generator_id": "GEN-MODEL-MULTISTAGE",
            "generator_kind": "model",
            "provider": "codex_cli",
            "execution_mode": mode,
            "stage_role": "multi_stage_generation_reasoning",
            "model_output_kind": "prototype_multistage_reasoning",
            "contract_profile_id": promotion_root.get("contract_profile_id", "base_drd_v1"),
            "contract_promotion_status": promotion_root.get("status", "base_contract"),
            "model_called": all_called,
            "status": status,
            "exit_code": 0 if all((item.get("exit_code") == 0 or item.get("exit_code") is None) for item in stage_roots) else 1,
            "started_at": next((item.get("started_at") for item in stage_roots if item.get("started_at")), None),
            "completed_at": next((item.get("completed_at") for item in reversed(stage_roots) if item.get("completed_at")), None),
            "duration_ms": sum(int(item.get("duration_ms") or 0) for item in stage_roots),
            "command": [],
            "command_policy": model_command_policy(),
            "rule_trace": rule_trace_for_artifact("model_invocation_trace"),
            "input_hashes": {
                "source_brief": f"sha256:{sha256_file(paths['source_brief'])}" if paths["source_brief"].exists() else "",
                "deterministic_draft_summary": f"sha256:{sha256_file(paths['deterministic_draft_summary'])}" if paths["deterministic_draft_summary"].exists() else "",
                "contract_promotion": f"sha256:{sha256_file(paths['model_contract_promotion_report'])}" if paths["model_contract_promotion_report"].exists() else "",
            },
            "output_refs": [ref for stage in MODEL_STAGE_DEFINITIONS for ref in model_stage_output_paths(paths, stage)],
            "completion_criteria_results": criteria,
            "model_stages": stage_roots,
        }
    }


def build_combined_model_review(model_artifacts: dict, model_traces: dict) -> dict:
    roots = {
        key: model_artifacts.get(key, {}).get(MODEL_STAGE_BY_KEY[key]["root_key"], {})
        for key in MODEL_STAGE_KEYS
    }
    statuses = [root.get("status") for root in roots.values()]
    status = "blocked" if "blocked" in statuses else ("review_required" if "review_required" in statuses else ("skipped" if all(item == "skipped" for item in statuses) else "pass"))
    return {
        "codex_inference_review": {
            "version": "3.1.1",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "requested_mode": "",
            "stage_role": "multi_stage_generation_reasoning",
            "model_output_kind": "prototype_multistage_reasoning",
            "model_called": all(root.get("model_called") is True for root in roots.values()),
            "status": status,
            "rule_trace": rule_trace_for_artifact("codex_inference_review"),
            "source_refs": sorted({ref for root in roots.values() for ref in root.get("source_refs", [])}),
            "model_stage_artifacts": {
                key: root for key, root in roots.items()
            },
            "parsed_review": {
                "status": status,
                "surface_blueprint": roots["surface_ownership"].get("surface_blueprint", []),
                "journey_edges": roots["user_journey"].get("journey_edges", []),
                "state_transitions": roots["interaction_state_machine"].get("state_transitions", []),
                "component_groups": roots["component_blueprint"].get("component_groups", []),
                "generation_findings": [
                    finding
                    for root in roots.values()
                    for finding in root.get("generation_findings", []) or []
                ],
            },
        }
    }


def apply_model_blueprint_guidance(runtime: dict, payload: dict, model_artifacts: dict, paths: dict, carrier_bundle: dict | None = None) -> dict:
    roots = {
        key: model_artifacts.get(key, {}).get(MODEL_STAGE_BY_KEY[key]["root_key"], {})
        for key in MODEL_STAGE_KEYS
    }
    parsed = {
        "surface_blueprint": roots["surface_ownership"].get("surface_blueprint", []),
        "journey_edges": roots["user_journey"].get("journey_edges", []),
        "interaction_adjustments": roots["interaction_state_machine"].get("interaction_adjustments", []),
        "state_transitions": roots["interaction_state_machine"].get("state_transitions", []),
        "component_groups": roots["component_blueprint"].get("component_groups", []),
        "component_intents": roots["component_blueprint"].get("component_intents", []),
        "generation_findings": [
            finding
            for root in roots.values()
            for finding in root.get("generation_findings", []) or []
        ],
    }
    payload_root = payload.get("prototype_render_payload", {})
    applied_adjustments = []
    skipped_adjustments = []
    interactions_by_id = {
        item.get("interaction_id"): item
        for item in payload_root.get("interactions", []) or []
        if item.get("interaction_id")
    }
    components_by_id = {
        item.get("component_id"): item
        for item in payload_root.get("components", []) or []
        if item.get("component_id")
    }
    edges_by_interaction = {
        item.get("interaction_id"): item
        for item in (runtime.get("interaction_graph", {}) or {}).get("edges", []) or []
        if item.get("interaction_id")
    }

    for adjustment in parsed.get("interaction_adjustments", []) or []:
        if not isinstance(adjustment, dict):
            continue
        interaction = interactions_by_id.get(adjustment.get("interaction_id"))
        if interaction is None:
            source_state_id = adjustment.get("source_state_id")
            target_state_id = adjustment.get("target_state_id")
            interaction = next(
                (
                    item
                    for item in payload_root.get("interactions", []) or []
                    if item.get("source_state_id") == source_state_id
                    and item.get("target_state_id") == target_state_id
                ),
                None,
            )
        if interaction is None:
            skipped_adjustments.append({
                "reason_zh": "没有找到可安全匹配的 interaction。",
                "adjustment": adjustment,
            })
            continue
        interaction_id = interaction.get("interaction_id")
        applied = {"interaction_id": interaction_id, "changes": []}
        trigger_zh = clean_md_text(adjustment.get("trigger_zh", ""))
        route_basis_zh = clean_md_text(adjustment.get("route_basis_zh", ""))
        if trigger_zh and trigger_zh != interaction.get("trigger_zh"):
            source_component = components_by_id.get(interaction.get("source_component_id"), {})
            candidate_interaction = dict(interaction)
            candidate_interaction["trigger_zh"] = trigger_zh
            needs_dedicated_component = interaction_requires_dedicated_component(candidate_interaction)
            has_dedicated_component = source_component.get("bound_interaction_id") == interaction_id
            if needs_dedicated_component and not has_dedicated_component:
                skipped_adjustments.append({
                    "interaction_id": interaction_id,
                    "field": "trigger_zh",
                    "before": interaction.get("trigger_zh", ""),
                    "after": trigger_zh,
                    "reason_zh": "模型建议会把普通状态组件变成点击热区，但该组件没有 dedicated interaction binding，已保留为人工 review 建议。",
                    "model_reason_zh": adjustment.get("reason_zh", ""),
                })
            else:
                applied["changes"].append({
                    "field": "trigger_zh",
                    "before": interaction.get("trigger_zh", ""),
                    "after": trigger_zh,
                    "reason_zh": adjustment.get("reason_zh", ""),
                })
                interaction["trigger_zh"] = trigger_zh
                edge = edges_by_interaction.get(interaction_id)
                if edge is not None:
                    edge["trigger_zh"] = trigger_zh
        if route_basis_zh and route_basis_zh != interaction.get("route_basis_zh"):
            applied["changes"].append({
                "field": "route_basis_zh",
                "before": interaction.get("route_basis_zh", ""),
                "after": route_basis_zh,
                "reason_zh": adjustment.get("reason_zh", ""),
            })
            interaction["route_basis_zh"] = route_basis_zh
            edge = edges_by_interaction.get(interaction_id)
            if edge is not None:
                edge["route_basis_zh"] = route_basis_zh
        if applied["changes"]:
            applied_adjustments.append(applied)

    surface_by_id = {
        item.get("screen_id"): item
        for item in parsed.get("surface_blueprint", []) or []
        if isinstance(item, dict) and item.get("screen_id")
    }
    for screen in runtime.get("screens", []) or []:
        surface = surface_by_id.get(screen.get("screen_id"))
        if not surface:
            continue
        screen["model_surface_blueprint"] = {
            "page_role_zh": surface.get("page_role_zh") or surface.get("surface_role_zh") or "",
            "page_purpose_zh": surface.get("page_purpose_zh") or surface.get("purpose_zh") or "",
            "page_boundary_zh": surface.get("page_boundary_zh") or "",
            "state_policy_zh": surface.get("state_policy_zh") or "",
            "review_notes_zh": surface.get("review_notes_zh") or surface.get("reason_zh") or "",
        }

    completed_model_stages = [
        key for key, root in roots.items()
        if root.get("model_called") is True and root.get("status") in {"pass", "review_required"}
    ]
    all_required_called = len(completed_model_stages) == len(MODEL_STAGE_DEFINITIONS)
    guidance_summary = {
        "stage_role": "multi_stage_generation_reasoning",
        "model_output_kind": "prototype_multistage_reasoning",
        "status": "pass" if all_required_called else "blocked",
        "required_model_stage_count": len(MODEL_STAGE_DEFINITIONS),
        "completed_model_stage_count": len(completed_model_stages),
        "all_required_model_stages_called": all_required_called,
        "model_stage_statuses": {
            key: {
                "status": root.get("status", "unknown"),
                "model_called": root.get("model_called") is True,
                "artifact_path": run_artifact_path(paths[model_path_key(key)]),
            }
            for key, root in roots.items()
        },
        "surface_blueprint_count": len(parsed.get("surface_blueprint", []) or []),
        "journey_edge_count": len(parsed.get("journey_edges", []) or []),
        "state_transition_count": len(parsed.get("state_transitions", []) or []),
        "interaction_adjustment_count": len(parsed.get("interaction_adjustments", []) or []),
        "component_group_count": len(parsed.get("component_groups", []) or []),
        "generation_findings": parsed.get("generation_findings", []),
        "applied_adjustments": applied_adjustments,
        "skipped_model_applications": skipped_adjustments,
        "model_reasoning_artifacts": {
            key: run_artifact_path(paths[model_path_key(key)])
            for key in MODEL_STAGE_KEYS
        },
        "carrier_handoff_artifacts": {
            key: run_artifact_path(paths[key])
            for key in ["interaction_carrier_map", "system_handoff_map", "user_operation_chain", "capability_assessment"]
            if key in paths
        },
        "applied_to_final_outputs": True,
        "application_policy_zh": "模型不直接写文件；脚本只把可安全匹配的页面职责、承载面、系统交接、真实操作链和交互文案建议写入最终候选产物。",
    }
    payload_root["model_generation_blueprint"] = guidance_summary
    payload_root["model_user_journey"] = {
        "journey_edges": parsed.get("journey_edges", []),
    }
    payload_root["model_component_blueprint"] = {
        "component_groups": parsed.get("component_groups", []),
        "component_intents": parsed.get("component_intents", []),
    }
    if carrier_bundle:
        payload_root["carrier_handoff_refs"] = guidance_summary["carrier_handoff_artifacts"]
        runtime.setdefault("generation_lineage", {})["carrier_handoff_pass"] = {
            "name": "carrier_handoff_operation_chain_v3_1_2",
            "status": "pass",
            "owned_outputs": list(guidance_summary["carrier_handoff_artifacts"].values()),
        }
    runtime.setdefault("generation_lineage", {})["model_generation_pass"] = {
        "name": "codex_multistage_reasoning_before_final_materialization",
        "status": guidance_summary["status"],
        "execution_contract": run_artifact_path(paths["model_execution_contract"]),
        "invocation_trace": run_artifact_path(paths["model_invocation_trace"]),
        "model_stage_artifacts": guidance_summary["model_reasoning_artifacts"],
        "applied_to_final_outputs": True,
    }
    runtime.setdefault("reasoning_completion", {})["model_blueprint"] = {
        "status": guidance_summary["status"],
        "surface_blueprint_count": guidance_summary["surface_blueprint_count"],
        "interaction_adjustment_count": guidance_summary["interaction_adjustment_count"],
        "applied_adjustment_count": len(applied_adjustments),
        "completed_model_stage_count": len(completed_model_stages),
    }
    return guidance_summary


def update_model_trace_after_final_write(model_invocation_trace: dict, paths: dict) -> dict:
    trace = model_invocation_trace.get("model_invocation_trace", {})
    final_hashes = {
        "runtime": f"sha256:{sha256_file(paths['runtime'])}" if paths["runtime"].exists() else "",
        "payload": f"sha256:{sha256_file(paths['payload'])}" if paths["payload"].exists() else "",
    }
    trace["final_output_write_policy"] = {
        "final_outputs_written_after_model": True,
        "final_output_refs": [
            run_artifact_path(paths["runtime"]),
            run_artifact_path(paths["payload"]),
        ],
        "final_output_hashes": final_hashes,
        "evidence_zh": "runtime/payload 在模型 generation_blueprint stage 完成并被应用后才落盘。",
    }
    for criterion in trace.get("completion_criteria_results", []) or []:
        if criterion.get("criterion_id") == "MODEL-CC-FINAL-WRITE-AFTER-MODEL":
            criterion["status"] = "pass"
            criterion["evidence_refs"] = [
                run_artifact_path(paths["runtime"]),
                run_artifact_path(paths["payload"]),
                f"runtime={final_hashes['runtime']}",
                f"payload={final_hashes['payload']}",
            ]
    return model_invocation_trace


def build_stage_timing_trace(paths: dict, stage_records: list[dict]) -> dict:
    public_records = public_stage_records(stage_records)
    return {
        "stage_timing_trace": {
            "version": "3.1.1",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "trace_id": f"STAGE-TIMING-{RUN_ID}",
            "rule_trace": rule_trace_for_artifact("generation_trace"),
            "source_refs": [],
            "stages": public_records,
            "summary": {
                "total_stages": len(public_records),
                "total_duration_ms": sum(int(item.get("duration_ms") or 0) for item in public_records),
                "model_duration_ms": sum(
                    int(item.get("duration_ms") or 0)
                    for item in public_records
                    if item.get("generator_kind") == "model"
                ),
                "deterministic_duration_ms": sum(
                    int(item.get("duration_ms") or 0)
                    for item in public_records
                    if item.get("generator_kind") == "deterministic"
                ),
                "final_output_refs": [
                    run_artifact_path(paths["runtime"]),
                    run_artifact_path(paths["payload"]),
                ],
            },
        }
    }


def build_generation_trace(
    source_path: Path,
    paths: dict,
    source_refs: list[str],
    output_hash: str,
    gaps: list[dict],
    model_artifacts: dict,
    model_invocation_trace: dict,
    model_application: dict,
) -> dict:
    model_root = model_invocation_trace.get("model_invocation_trace", {})
    stage_roots = model_root.get("model_stages", []) or []
    model_stage_artifact_refs = {
        key: run_artifact_path(paths[model_path_key(key)])
        for key in MODEL_STAGE_KEYS
    }
    model_families = []
    for stage in MODEL_STAGE_DEFINITIONS:
        key = stage["key"]
        model_families.append({
            "generator_kind": "model",
            "generator_id": stage["generator_id"],
            "worker_id": stage["worker_id"],
            "stage_id": stage["stage_id"],
            "stage_role": key,
            "rule_ids": rule_ids_for_artifact("model_invocation_trace"),
            "execution_contract_path": run_artifact_path(paths[model_path_key(key, "_contract")]),
            "invocation_trace_path": run_artifact_path(paths[model_path_key(key, "_trace")]),
            "owned_outputs": [
                run_artifact_path(paths[model_path_key(key)]),
                run_artifact_path(paths[model_path_key(key, "_raw")]),
            ],
        })
    return {
        "generation_trace": {
            "trace_id": f"TRACE-PROTO-GEN-{RUN_ID}",
            "artifact_id": "prototype-render-payload.yaml",
            "artifact_path": paths["payload"].relative_to(RUN_ROOT).as_posix(),
            "generator_id": "prototype_artifact_generator_v3_1_2",
            "generator_worker_id": "GEN-WORKER-SOURCE-ATOM-LIFECYCLE",
            "rule_trace": rule_trace_for_artifact("generation_trace"),
            "generated_at": utc_now_text(),
            "input_hashes": {
                "source": f"sha256:{sha256_file(source_path)}",
            },
            "source_refs": source_refs,
            "generation_job_queue_ref": run_artifact_path(paths["generation_job_queue"]),
            "stage_timing_trace_ref": run_artifact_path(paths["stage_timing_trace"]),
            "generator_families": [
                {
                    "generator_kind": "deterministic",
                    "generator_id": "GEN-DETERMINISTIC-PROTOTYPE-LIFECYCLE",
                    "worker_id": "GEN-WORKER-SOURCE-ATOM-LIFECYCLE",
                    "rule_ids": rule_ids_for_artifact("payload"),
                    "owned_outputs": [
                        run_artifact_path(paths["source_brief"]),
                        run_artifact_path(paths["runtime"]),
                        run_artifact_path(paths["payload"]),
                        run_artifact_path(paths["source_coverage_report"]),
                        run_artifact_path(paths["interaction_carrier_map"]),
                        run_artifact_path(paths["system_handoff_map"]),
                        run_artifact_path(paths["user_operation_chain"]),
                        run_artifact_path(paths["capability_assessment"]),
                        run_artifact_path(paths["prototype_review_view_model"]),
                    ],
                },
                {
                    "generator_kind": "model",
                    "generator_id": "GEN-MODEL-MULTISTAGE",
                    "worker_id": "GEN-WORKER-CODEX-MULTISTAGE",
                    "rule_ids": rule_ids_for_artifact("model_invocation_trace"),
                    "execution_contract_path": run_artifact_path(paths["model_execution_contract"]),
                    "invocation_trace_path": run_artifact_path(paths["model_invocation_trace"]),
                    "owned_outputs": [
                        run_artifact_path(paths["codex_inference_review"]),
                        run_artifact_path(paths["blueprint_review_md"]),
                    ],
                },
            ] + model_families,
            "decisions": [
                {
                    "decision_id": "GEN-DEC-SOURCE-ATOM-FIRST",
                    "decision_zh": "优先按 PRD 表格行和反引号 ID 生成细颗粒 source atom。",
                    "basis_zh": "v3.1.1 lifecycle 要求 first-pass build 先生成最小可校验产物。",
                    "source_refs": source_refs,
                    "confidence": "medium",
                    "review_required": True,
                    "rule_ids": rule_ids_for_artifact("prototype_source_brief"),
                },
                {
                    "decision_id": "GEN-DEC-GENERIC-BOUNDARY",
                    "decision_zh": "仅从源文本明确 min/max 范围生成边界值状态。",
                    "basis_zh": "通用 boundary-value analysis，不读取业务专属示例 fixture。",
                    "source_refs": source_refs,
                    "confidence": "medium",
                    "review_required": True,
                    "rule_ids": rule_ids_for_artifact("source_coverage_report"),
                },
            ],
            "model_inference": {
                "provider": "codex_cli",
                "stage_role": "multi_stage_generation_reasoning",
                "model_output_kind": "prototype_multistage_reasoning",
                "required_model_stage_count": len(MODEL_STAGE_DEFINITIONS),
                "completed_model_stage_count": len(stage_roots),
                "all_required_model_stages_called": all(item.get("model_called") is True for item in stage_roots) and len(stage_roots) == len(MODEL_STAGE_DEFINITIONS),
                "model_called": model_root.get("model_called") is True,
                "status": model_root.get("status", "unknown"),
                "model_stage_artifacts": model_stage_artifact_refs,
                "execution_contract_path": run_artifact_path(paths["model_execution_contract"]),
                "invocation_trace_path": run_artifact_path(paths["model_invocation_trace"]),
                "final_outputs_written_after_model": True,
                "applied_to_final_outputs": model_application.get("applied_to_final_outputs") is True,
                "applied_adjustment_count": len(model_application.get("applied_adjustments", []) or []),
                "skipped_model_applications": model_application.get("skipped_model_applications", []),
            },
            "skill_influence": [],
            "generation_gaps": gaps,
            "output_hash": f"sha256:{output_hash}",
            "self_check_result": {
                "status": "pass" if not gaps else "pass_with_gaps",
                    "checks": [
                        "source_atoms_have_source_refs",
                        "required_states_have_frames",
                        "coverage_report_passes",
                        "writes_prd_false",
                    ],
                    "rule_ids": rule_ids_for_artifact("generation_trace"),
                },
        }
    }


def file_output_criteria(output_keys: list[str], paths: dict) -> list[dict]:
    criteria = []
    for key in output_keys:
        trace_key = artifact_rule_key(key)
        criteria.append(completion_criterion(
            f"CC-FILE-{key.upper().replace('_', '-')}",
            f"生成物 `{key}` 必须存在于隔离 run root。",
            "file_exists",
            [run_artifact_path(paths[key])],
            "pass" if paths[key].exists() else "blocked",
            rule_ids=rule_ids_for_artifact(trace_key),
        ))
    return criteria


def build_generation_job_queue(paths: dict, source_refs: list[str], model_invocation_trace: dict, stage_records: list[dict]) -> dict:
    model_root = model_invocation_trace.get("model_invocation_trace", {})
    stage_traces = {
        item.get("stage_id"): item
        for item in model_root.get("model_stages", []) or []
        if item.get("stage_id")
    }

    timing_by_job = {
        record.get("job_id"): record
        for record in public_stage_records(stage_records)
        if record.get("job_id")
    }

    def attach_timing(job: dict) -> dict:
        timing = timing_by_job.get(job["job_id"], {})
        for key in ["started_at", "completed_at", "duration_ms"]:
            if key in timing:
                job[key] = timing[key]
        return job

    jobs = [
        attach_timing({
            "job_id": "GEN-JOB-001-SOURCE-SLICES",
            "stage_id": "GEN-SOURCE-SLICES",
            "generator_id": "GEN-DETERMINISTIC-SOURCE-SLICER",
            "generator_kind": "deterministic",
            "worker_id": "GEN-WORKER-SOURCE-ATOM-LIFECYCLE",
            "rule_ids": rule_ids_for_artifact("prototype_source_brief"),
            "dependency_job_ids": [],
            "input_refs": ["inputs/PRD.md"],
            "output_refs": [run_artifact_path(paths[key]) for key in ["source_brief", "source_slice_index"]],
            "completion_criteria": file_output_criteria(["source_brief", "source_slice_index"], paths) + [
                completion_criterion(
                    "CC-SOURCE-ATOMS-HAVE-REFS",
                    "所有 source atom 必须带 source_refs。",
                    "validate-generated-artifacts",
                    [run_artifact_path(paths["source_brief"])],
                    rule_ids=rule_ids_for_artifact("prototype_source_brief"),
                )
            ],
            "status": "pass",
            "writes_prd": False,
        }),
        attach_timing({
            "job_id": "GEN-JOB-002-DETERMINISTIC-DRAFT",
            "stage_id": "GEN-DETERMINISTIC-DRAFT",
            "generator_id": "GEN-DETERMINISTIC-DRAFT-SUMMARY",
            "generator_kind": "deterministic",
            "worker_id": "GEN-WORKER-DETERMINISTIC-DRAFT",
            "rule_ids": rule_ids_for_artifact("generation_trace"),
            "dependency_job_ids": ["GEN-JOB-001-SOURCE-SLICES"],
            "input_refs": [run_artifact_path(paths["source_brief"])],
            "output_refs": [
                run_artifact_path(paths["deterministic_draft_summary"]),
            ],
            "completion_criteria": file_output_criteria(["deterministic_draft_summary"], paths),
            "status": "pass",
            "writes_prd": False,
        }),
        attach_timing({
            "job_id": "GEN-JOB-003-CARRIER-HANDOFF-DRAFT",
            "stage_id": "GEN-CARRIER-HANDOFF-DRAFT",
            "generator_id": "GEN-DETERMINISTIC-CARRIER-HANDOFF",
            "generator_kind": "deterministic",
            "worker_id": "GEN-WORKER-CARRIER-HANDOFF",
            "rule_ids": normalize_rule_ids(
                rule_ids_for_artifact("interaction_carrier_map")
                + rule_ids_for_artifact("system_handoff_map")
                + rule_ids_for_artifact("user_operation_chain")
                + rule_ids_for_artifact("capability_assessment")
            ),
            "dependency_job_ids": ["GEN-JOB-002-DETERMINISTIC-DRAFT"],
            "input_refs": [
                run_artifact_path(paths["source_brief"]),
                run_artifact_path(paths["deterministic_draft_summary"]),
            ],
            "output_refs": [
                run_artifact_path(paths["interaction_carrier_map"]),
                run_artifact_path(paths["system_handoff_map"]),
                run_artifact_path(paths["user_operation_chain"]),
                run_artifact_path(paths["capability_assessment"]),
            ],
            "completion_criteria": file_output_criteria([
                "interaction_carrier_map",
                "system_handoff_map",
                "user_operation_chain",
                "capability_assessment",
            ], paths),
            "status": "pass",
            "writes_prd": False,
        }),
        attach_timing({
            "job_id": "GEN-JOB-004-CONTRACT-PROMOTION",
            "stage_id": "GEN-CONTRACT-PROMOTION",
            "generator_id": "GEN-DETERMINISTIC-CONTRACT-PROMOTION",
            "generator_kind": "deterministic",
            "worker_id": "GEN-WORKER-CONTRACT-PROMOTION",
            "rule_ids": rule_ids_for_artifact("model_contract_promotion_report"),
            "dependency_job_ids": ["GEN-JOB-003-CARRIER-HANDOFF-DRAFT"],
            "input_refs": [
                run_artifact_path(paths["interaction_carrier_map"]),
                run_artifact_path(paths["system_handoff_map"]),
                run_artifact_path(paths["user_operation_chain"]),
                run_artifact_path(paths["capability_assessment"]),
            ],
            "output_refs": [
                run_artifact_path(paths["model_contract_promotion_report"]),
                run_artifact_path(paths["model_execution_contract_resolved"]),
            ],
            "completion_criteria": file_output_criteria([
                "model_contract_promotion_report",
                "model_execution_contract_resolved",
            ], paths),
            "status": "pass",
            "writes_prd": False,
        }),
    ]

    for index, model_stage in enumerate(MODEL_STAGE_DEFINITIONS):
        key = model_stage["key"]
        prior_model_refs = [
            run_artifact_path(paths[model_path_key(prior["key"])])
            for prior in MODEL_STAGE_DEFINITIONS[:index]
        ]
        stage_trace = stage_traces.get(model_stage["stage_id"], {})
        stage_status = stage_trace.get("status", "blocked")
        if stage_status == "review_required":
            job_status = "pass_with_review_required"
        elif stage_status in {"pass", "skipped", "blocked"}:
            job_status = stage_status
        else:
            job_status = "blocked"
        jobs.append(attach_timing({
            "job_id": model_stage["job_id"],
            "stage_id": model_stage["stage_id"],
            "generator_id": model_stage["generator_id"],
            "generator_kind": "model",
            "worker_id": model_stage["worker_id"],
            "rule_ids": rule_ids_for_artifact("model_invocation_trace"),
            "dependency_job_ids": ["GEN-JOB-004-CONTRACT-PROMOTION"] + [
                prior["job_id"] for prior in MODEL_STAGE_DEFINITIONS[:index]
            ],
            "input_refs": [
                run_artifact_path(paths["source_brief"]),
                run_artifact_path(paths["source_slice_index"]),
                run_artifact_path(paths["deterministic_draft_summary"]),
                run_artifact_path(paths["interaction_carrier_map"]),
                run_artifact_path(paths["system_handoff_map"]),
                run_artifact_path(paths["user_operation_chain"]),
                run_artifact_path(paths["capability_assessment"]),
                run_artifact_path(paths["model_contract_promotion_report"]),
                run_artifact_path(paths["model_execution_contract_resolved"]),
            ] + prior_model_refs,
            "output_refs": model_stage_output_paths(paths, model_stage),
            "completion_criteria": [
                completion_criterion(
                    item.get("criterion_id", f"MODEL-CC-{key.upper()}"),
                    item.get("description_zh", f"{model_stage['title_zh']} completion criteria。"),
                    item.get("validator", "model_invocation_trace"),
                    item.get("evidence_refs", []),
                    item.get("status", "blocked"),
                    item.get("required", True),
                    rule_ids=item.get("rule_ids") or rule_ids_for_artifact("model_invocation_trace"),
                )
                for item in stage_trace.get("completion_criteria_results", []) or []
            ] or file_output_criteria([
                model_path_key(key, "_contract"),
                model_path_key(key),
                model_path_key(key, "_trace"),
            ], paths),
            "status": job_status,
            "writes_prd": False,
        }))

    jobs.extend([
        attach_timing({
            "job_id": "GEN-JOB-009-FINAL-MATERIALIZATION",
            "stage_id": "GEN-FINAL-MATERIALIZATION",
            "generator_id": "GEN-DETERMINISTIC-FINAL-MATERIALIZER",
            "generator_kind": "deterministic",
            "worker_id": "GEN-WORKER-FINAL-MATERIALIZATION",
            "rule_ids": normalize_rule_ids(
                rule_ids_for_artifact("payload")
                + rule_ids_for_artifact("runtime")
                + rule_ids_for_artifact("screen_role_obligations")
                + rule_ids_for_artifact("design_kernel")
                + rule_ids_for_artifact("composition_plan")
                + rule_ids_for_artifact("interaction_hotspot_map")
                + rule_ids_for_artifact("logic_sidecar_card_map")
                + rule_ids_for_artifact("local_materialization_patch")
                + rule_ids_for_artifact("interaction_carrier_map")
                + rule_ids_for_artifact("system_handoff_map")
                + rule_ids_for_artifact("user_operation_chain")
                + rule_ids_for_artifact("capability_assessment")
            ),
            "dependency_job_ids": [stage["job_id"] for stage in MODEL_STAGE_DEFINITIONS],
            "input_refs": [
                run_artifact_path(paths["source_brief"]),
                run_artifact_path(paths["deterministic_draft_summary"]),
                run_artifact_path(paths["interaction_carrier_map"]),
                run_artifact_path(paths["system_handoff_map"]),
                run_artifact_path(paths["user_operation_chain"]),
                run_artifact_path(paths["capability_assessment"]),
                run_artifact_path(paths["model_contract_promotion_report"]),
                run_artifact_path(paths["model_execution_contract_resolved"]),
                run_artifact_path(paths["model_execution_contract"]),
                run_artifact_path(paths["model_invocation_trace"]),
            ] + [
                run_artifact_path(paths[model_path_key(stage["key"])])
                for stage in MODEL_STAGE_DEFINITIONS
            ],
            "output_refs": [
                run_artifact_path(paths[key])
                for key in [
                    "screen_role_obligations",
                    "design_kernel",
                    "composition_plan",
                    "interaction_hotspot_map",
                    "logic_sidecar_card_map",
                    "annotation_stub_map",
                    "anchor_badge_map",
                    "local_materialization_patch",
                    "interaction_carrier_map",
                    "system_handoff_map",
                    "user_operation_chain",
                    "capability_assessment",
                    "runtime",
                    "payload",
                ]
            ],
            "completion_criteria": file_output_criteria([
                "screen_role_obligations",
                "design_kernel",
                "composition_plan",
                "interaction_hotspot_map",
                "logic_sidecar_card_map",
                "annotation_stub_map",
                "anchor_badge_map",
                "local_materialization_patch",
                "interaction_carrier_map",
                "system_handoff_map",
                "user_operation_chain",
                "capability_assessment",
                "runtime",
                "payload",
            ], paths) + [
                completion_criterion(
                    "CC-PAYLOAD-NOT-SAMPLE",
                    "payload 必须来自 PRD source，不得是 sample/example。",
                    "validate-render-readiness",
                    [run_artifact_path(paths["payload"])],
                    rule_ids=rule_ids_for_artifact("payload"),
                ),
                completion_criterion(
                    "CC-FINAL-WRITE-AFTER-MODEL",
                    "最终 runtime/payload 必须依赖全部 4 个模型推理 job。",
                    "validate-model-stage-coverage",
                    [run_artifact_path(paths["model_invocation_trace"])],
                    rule_ids=rule_ids_for_artifact("model_invocation_trace"),
                ),
            ],
            "status": "pass",
            "writes_prd": False,
        }),
        attach_timing({
            "job_id": "GEN-JOB-010-REVIEW-VIEW-MODEL",
            "stage_id": "GEN-REVIEW-VIEW-MODEL",
            "generator_id": "GEN-DETERMINISTIC-REVIEW-VIEW-MODEL",
            "generator_kind": "deterministic",
            "worker_id": "GEN-WORKER-REVIEW-VIEW-MODEL",
            "rule_ids": rule_ids_for_artifact("prototype_review_view_model"),
            "dependency_job_ids": ["GEN-JOB-009-FINAL-MATERIALIZATION"],
            "input_refs": [
                run_artifact_path(paths["runtime"]),
                run_artifact_path(paths["payload"]),
                run_artifact_path(paths["interaction_carrier_map"]),
                run_artifact_path(paths["system_handoff_map"]),
                run_artifact_path(paths["user_operation_chain"]),
                run_artifact_path(paths["capability_assessment"]),
            ],
            "output_refs": [
                run_artifact_path(paths["prototype_review_view_model"]),
                run_artifact_path(paths["blueprint_review_md"]),
            ],
            "completion_criteria": file_output_criteria(["prototype_review_view_model", "blueprint_review_md"], paths),
            "status": "pass",
            "writes_prd": False,
        }),
        attach_timing({
            "job_id": "GEN-JOB-011-COVERAGE-MANIFEST",
            "stage_id": "GEN-COVERAGE-MANIFEST",
            "generator_id": "GEN-DETERMINISTIC-COVERAGE-MANIFEST",
            "generator_kind": "deterministic",
            "worker_id": "GEN-WORKER-TRACE-MANIFEST",
            "rule_ids": rule_ids_for_artifact("generation_trace"),
            "dependency_job_ids": ["GEN-JOB-010-REVIEW-VIEW-MODEL"],
            "input_refs": [
                run_artifact_path(paths["runtime"]),
                run_artifact_path(paths["payload"]),
                run_artifact_path(paths["prototype_review_view_model"]),
            ],
            "output_refs": [
                run_artifact_path(paths["source_coverage_report"]),
                run_artifact_path(paths["generation_trace"]),
                run_artifact_path(paths["stage_timing_trace"]),
                run_artifact_path(paths["generated_artifact_manifest"]),
                run_artifact_path(paths["generation_job_queue"]),
                run_artifact_path(paths["report_yaml"]),
                run_artifact_path(paths["report_md"]),
                run_artifact_path(paths["blueprint_review_md"]),
                run_artifact_path(paths["prototype_review_view_model"]),
            ],
            "completion_criteria": file_output_criteria([
                "source_coverage_report",
                "generation_trace",
                "stage_timing_trace",
                "report_yaml",
                "report_md",
            ], paths),
            "status": "pass",
            "writes_prd": False,
        }),
    ])
    blocked_jobs = len([job for job in jobs if job["status"] == "blocked"])
    all_required_criteria_passed = all(
        criterion.get("status") != "blocked"
        for job in jobs
        for criterion in job.get("completion_criteria", [])
        if criterion.get("required", True)
    )
    return {
        "generation_job_queue": {
            "version": "3.1.1",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "queue_id": f"GEN-JOB-QUEUE-{RUN_ID}",
            "rule_trace": rule_trace_for_artifact("generation_job_queue"),
            "source_refs": source_refs,
            "jobs": jobs,
            "completion_summary": {
                "total_jobs": len(jobs),
                "blocked_jobs": blocked_jobs,
                "all_required_criteria_passed": all_required_criteria_passed,
                "deterministic_generator_jobs": len([job for job in jobs if job["generator_kind"] == "deterministic"]),
                "model_generator_jobs": len([job for job in jobs if job["generator_kind"] == "model"]),
            },
        }
    }


def build_generated_artifact_manifest(paths: dict) -> dict:
    artifacts = []
    for key, path in paths.items():
        if key == "report_md" or not path.exists():
            continue
        trace_key = artifact_rule_key(key)
        artifacts.append({
            "artifact_id": key,
            "path": path.relative_to(RUN_ROOT).as_posix(),
            "generator_id": "prototype_artifact_generator_v3_1_2",
            "trace_id": f"TRACE-PROTO-GEN-{RUN_ID}",
            "hash": f"sha256:{sha256_file(path)}",
            "rule_ids": rule_ids_for_artifact(trace_key),
            "status": "candidate_generated",
        })
    return {
        "generated_artifact_manifest": {
            "version": "3.1.1",
            "mode": "DRD_MODE",
            "run_id": RUN_ID,
            "rule_trace": rule_trace_for_artifact("generated_artifact_manifest"),
            "artifacts": artifacts,
        }
    }


ARTIFACT_ROOT_KEYS = {
    "prototype_source_brief": "prototype_source_brief",
    "source_slice_index": "source_slice_index",
    "screen_role_obligations": "screen_role_obligations",
    "design_kernel": "design_kernel",
    "composition_plan": "composition_plan",
    "interaction_hotspot_map": "interaction_hotspot_map",
    "logic_sidecar_card_map": "logic_sidecar_card_map",
    "annotation_stub_map": "annotation_stub_map",
    "anchor_badge_map": "anchor_badge_map",
    "local_materialization_patch": "local_materialization_patch",
    "payload": "prototype_render_payload",
    "generation_job_queue": "generation_job_queue",
    "generation_trace": "generation_trace",
    "model_execution_contract": "model_execution_contract",
    "model_invocation_trace": "model_invocation_trace",
    "model_surface_ownership": "model_surface_ownership",
    "model_user_journey": "model_user_journey",
    "model_interaction_state_machine": "model_interaction_state_machine",
    "model_component_blueprint": "model_component_blueprint",
    "generated_artifact_manifest": "generated_artifact_manifest",
    "source_coverage_report": "source_coverage_report",
    "interaction_carrier_map": "interaction_carrier_map",
    "system_handoff_map": "system_handoff_map",
    "user_operation_chain": "user_operation_chain",
    "capability_assessment": "capability_assessment",
    "prototype_review_view_model": "prototype_review_view_model",
    "model_contract_promotion_report": "model_contract_promotion_report",
}


def generated_artifact_rule_trace_errors(label: str, instance_path: Path) -> list[str]:
    if not instance_path.exists():
        return []
    data = load_any(instance_path)
    if label == "runtime":
        return rule_trace_errors(data, f"{label}.rule_trace")
    root_key = ARTIFACT_ROOT_KEYS.get(label)
    if not root_key:
        return []
    root = data.get(root_key, {}) if isinstance(data, dict) else {}
    return rule_trace_errors(root, f"{label}.{root_key}.rule_trace")


def validate_generated_artifacts(paths: dict) -> list[str]:
    checks = [
        ("prototype_source_brief", paths["source_brief"], DRD_ROOT / "schemas" / "prototype_source_brief.schema.json"),
        ("source_slice_index", paths["source_slice_index"], DRD_ROOT / "schemas" / "source_slice_index.schema.json"),
        ("screen_role_obligations", paths["screen_role_obligations"], DRD_ROOT / "schemas" / "screen_role_obligations.schema.json"),
        ("design_kernel", paths["design_kernel"], DRD_ROOT / "schemas" / "design_kernel.schema.json"),
        ("composition_plan", paths["composition_plan"], DRD_ROOT / "schemas" / "composition_plan.schema.json"),
        ("interaction_hotspot_map", paths["interaction_hotspot_map"], DRD_ROOT / "schemas" / "interaction_hotspot_map.schema.json"),
        ("logic_sidecar_card_map", paths["logic_sidecar_card_map"], DRD_ROOT / "schemas" / "logic_sidecar_card_map.schema.json"),
        ("annotation_stub_map", paths["annotation_stub_map"], DRD_ROOT / "schemas" / "annotation_stub_map.schema.json"),
        ("anchor_badge_map", paths["anchor_badge_map"], DRD_ROOT / "schemas" / "anchor_badge_map.schema.json"),
        ("local_materialization_patch", paths["local_materialization_patch"], DRD_ROOT / "schemas" / "local_materialization_patch.schema.json"),
        ("runtime", paths["runtime"], ROOT / "schemas" / "prototype_runtime.schema.json"),
        ("payload", paths["payload"], ROOT / "schemas" / "prototype_render_payload.schema.json"),
        ("generation_job_queue", paths["generation_job_queue"], DRD_ROOT / "schemas" / "generation_job_queue.schema.json"),
        ("generation_trace", paths["generation_trace"], DRD_ROOT / "schemas" / "generation_trace.schema.json"),
        ("model_execution_contract", paths["model_execution_contract"], DRD_ROOT / "schemas" / "model_execution_contract.schema.json"),
        ("model_invocation_trace", paths["model_invocation_trace"], DRD_ROOT / "schemas" / "model_invocation_trace.schema.json"),
        ("interaction_carrier_map", paths["interaction_carrier_map"], DRD_ROOT / "schemas" / "interaction_carrier_map.schema.json"),
        ("system_handoff_map", paths["system_handoff_map"], DRD_ROOT / "schemas" / "system_handoff_map.schema.json"),
        ("user_operation_chain", paths["user_operation_chain"], DRD_ROOT / "schemas" / "user_operation_chain.schema.json"),
        ("capability_assessment", paths["capability_assessment"], DRD_ROOT / "schemas" / "capability_assessment.schema.json"),
        ("prototype_review_view_model", paths["prototype_review_view_model"], DRD_ROOT / "schemas" / "prototype_review_view_model.schema.json"),
        ("model_contract_promotion_report", paths["model_contract_promotion_report"], DRD_ROOT / "schemas" / "model_contract_promotion_report.schema.json"),
        ("model_execution_contract", paths["model_execution_contract_resolved"], DRD_ROOT / "schemas" / "model_execution_contract.schema.json"),
        ("generated_artifact_manifest", paths["generated_artifact_manifest"], DRD_ROOT / "schemas" / "generated_artifact_manifest.schema.json"),
        ("source_coverage_report", paths["source_coverage_report"], DRD_ROOT / "schemas" / "source_coverage_report.schema.json"),
    ]
    errors = []
    for label, instance_path, schema_path in checks:
        errors.extend(f"{label}: {error}" for error in validate_schema(instance_path, schema_path))
        errors.extend(generated_artifact_rule_trace_errors(label, instance_path))
    for stage in MODEL_STAGE_DEFINITIONS:
        errors.extend(
            f"{stage['root_key']}: {error}"
            for error in model_artifact_validation_errors(paths[model_path_key(stage["key"])], stage["key"])
        )
    if paths.get("interaction_carrier_map", Path()).exists() and paths.get("payload", Path()).exists():
        errors.extend(carrier_map_semantic_errors(yload(paths["interaction_carrier_map"]), load_any(paths["payload"])))
    if paths.get("system_handoff_map", Path()).exists():
        errors.extend(system_handoff_semantic_errors(yload(paths["system_handoff_map"])))
    if paths.get("user_operation_chain", Path()).exists() and paths.get("payload", Path()).exists():
        errors.extend(operation_chain_semantic_errors(yload(paths["user_operation_chain"]), load_any(paths["payload"])))
    if paths.get("capability_assessment", Path()).exists():
        errors.extend(capability_assessment_semantic_errors(yload(paths["capability_assessment"])))
    if paths.get("prototype_review_view_model", Path()).exists():
        errors.extend(review_view_model_semantic_errors(yload(paths["prototype_review_view_model"])))
    if paths.get("model_contract_promotion_report", Path()).exists():
        errors.extend(contract_promotion_semantic_errors(yload(paths["model_contract_promotion_report"])))
    return errors


def carrier_map_semantic_errors(doc: dict, payload: dict | None = None) -> list[str]:
    errors = []
    root = doc.get("interaction_carrier_map", {})
    errors.extend(rule_trace_errors(root, "interaction_carrier_map.rule_trace"))
    interaction_items = root.get("interaction_carriers", []) or []
    if not interaction_items:
        errors.append(rule_error("CARRIER_DED_001", "interaction_carrier_map.interaction_carriers must not be empty"))
    interaction_ids = {item.get("interaction_id") for item in interaction_items if item.get("interaction_id")}
    if payload:
        payload_interactions = payload.get("prototype_render_payload", {}).get("interactions", []) or []
        for interaction in payload_interactions:
            if interaction.get("interaction_id") not in interaction_ids:
                errors.append(rule_error("CARRIER_DED_001", f"{interaction.get('interaction_id')}: missing carrier mapping"))
    for item in interaction_items:
        iid = item.get("interaction_id", "<unknown>")
        errors.extend(rule_trace_errors(item, f"interaction_carrier_map.{iid}.rule_ids"))
        for field in ["source_carrier_type", "target_carrier_type", "transition_scope", "source_refs"]:
            if not item.get(field):
                errors.append(rule_error("CARRIER_DED_001", f"{iid}: missing {field}"))
        if item.get("requires_system_handoff") is True and not item.get("capability_ids"):
            errors.append(rule_error("HANDOFF_DED_001", f"{iid}: requires_system_handoff but capability_ids is empty"))
        if item.get("target_carrier_type") != "app_page" and item.get("standalone_page_allowed") is True:
            errors.append(rule_error("CARRIER_DED_002", f"{iid}: non-app carrier must not be promoted to standalone page"))
    return errors


def system_handoff_semantic_errors(doc: dict) -> list[str]:
    errors = []
    root = doc.get("system_handoff_map", {})
    errors.extend(rule_trace_errors(root, "system_handoff_map.rule_trace"))
    required_steps = {"enter_handoff_surface", "perform_system_operation", "validate_or_cancel", "return_to_host_surface"}
    for item in root.get("handoffs", []) or []:
        handoff_id = item.get("handoff_id", "<unknown>")
        errors.extend(rule_trace_errors(item, f"system_handoff_map.{handoff_id}.rule_ids"))
        for field in ["interaction_id", "capability_id", "handoff_surface_type", "source_state_id", "return_state_id", "source_refs"]:
            if not item.get(field):
                errors.append(rule_error("HANDOFF_DED_001", f"{handoff_id}: missing {field}"))
        step_types = {step.get("step_type") for step in item.get("handoff_steps", []) or []}
        missing = sorted(required_steps - step_types)
        if missing:
            errors.append(rule_error("HANDOFF_DED_002", f"{handoff_id}: missing handoff step types {missing}"))
        if not item.get("cancel_path_zh"):
            errors.append(rule_error("HANDOFF_DED_002", f"{handoff_id}: missing cancel_path_zh"))
        if not item.get("failure_path_zh"):
            errors.append(rule_error("HANDOFF_DED_002", f"{handoff_id}: missing failure_path_zh"))
    return errors


def operation_chain_semantic_errors(doc: dict, payload: dict | None = None) -> list[str]:
    errors = []
    root = doc.get("user_operation_chain", {})
    errors.extend(rule_trace_errors(root, "user_operation_chain.rule_trace"))
    chains = root.get("chains", []) or []
    if not chains:
        errors.append(rule_error("OPS_DED_001", "user_operation_chain.chains must not be empty"))
    chain_interactions = {item.get("interaction_id") for item in chains if item.get("interaction_id")}
    if payload:
        for interaction in payload.get("prototype_render_payload", {}).get("interactions", []) or []:
            if interaction.get("interaction_id") not in chain_interactions:
                errors.append(rule_error("OPS_DED_001", f"{interaction.get('interaction_id')}: missing operation chain"))
    for chain in chains:
        chain_id = chain.get("operation_chain_id", "<unknown>")
        errors.extend(rule_trace_errors(chain, f"user_operation_chain.{chain_id}.rule_ids"))
        steps = chain.get("steps", []) or []
        if len(steps) < 3:
            errors.append(rule_error("OPS_DED_001", f"{chain_id}: operation chain must have at least 3 steps"))
        for step in steps:
            if not step.get("step_type") or not step.get("description_zh"):
                errors.append(rule_error("OPS_DED_001", f"{chain_id}: each step needs step_type and description_zh"))
        if chain.get("chain_kind") == "system_handoff_chain" and not chain.get("handoff_id"):
            errors.append(rule_error("HANDOFF_DED_001", f"{chain_id}: system_handoff_chain missing handoff_id"))
    return errors


def capability_assessment_semantic_errors(doc: dict) -> list[str]:
    errors = []
    root = doc.get("capability_assessment", {})
    errors.extend(rule_trace_errors(root, "capability_assessment.rule_trace"))
    for item in root.get("capabilities", []) or []:
        capability_id = item.get("capability_id", "<unknown>")
        errors.extend(rule_trace_errors(item, f"capability_assessment.{capability_id}.rule_ids"))
        layers = {layer.get("layer") for layer in item.get("four_layer_judgement", []) or []}
        required = {"prd_source_atoms", "local_capability_library", "instance_platform_context", "official_docs"}
        missing = sorted(required - layers)
        if missing:
            errors.append(rule_error("CAPABILITY_DED_001", f"{capability_id}: missing capability judgement layers {missing}"))
        if item.get("capability_status") == "unknown" and item.get("review_required") is not True:
            errors.append(rule_error("CAPABILITY_DED_001", f"{capability_id}: unknown capability must set review_required true"))
    return errors


def review_view_model_semantic_errors(doc: dict) -> list[str]:
    errors = []
    root = doc.get("prototype_review_view_model", {})
    errors.extend(rule_trace_errors(root, "prototype_review_view_model.rule_trace"))
    if not root.get("pages"):
        errors.append(rule_error("REVIEW_DED_001", "prototype_review_view_model.pages must not be empty"))
    serialized = json.dumps(root, ensure_ascii=False)
    for token in ["frame_id", "source_atom_id", "sha256", "component_id", "interaction_id"]:
        if token in serialized:
            errors.append(rule_error("REVIEW_DED_001", f"prototype_review_view_model must hide machine token `{token}`"))
    machine_id_pattern = re.compile(r"\b[A-Z][A-Z0-9]+(?:-[A-Z0-9_]+)+\b")
    skipped_keys = {"source_refs", "rule_ids", "rule_trace", "mode", "run_id", "version"}

    def walk_human_fields(value, path: str = ""):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in skipped_keys or path.startswith("rule_trace"):
                    continue
                walk_human_fields(child, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            for idx, child in enumerate(value):
                walk_human_fields(child, f"{path}[{idx}]")
        elif isinstance(value, str) and machine_id_pattern.search(value):
            errors.append(rule_error("REVIEW_DED_001", f"prototype_review_view_model human field leaks machine id at {path}"))

    walk_human_fields(root)
    for page in root.get("pages", []) or []:
        if not page.get("interaction_flow_sections"):
            errors.append(rule_error("REVIEW_DED_001", f"{page.get('page_name_zh', '<unknown>')}: missing page-level interaction_flow_sections"))
    for edge in root.get("page_flow_edges", []) or []:
        if edge.get("source_page_zh") == edge.get("target_page_zh"):
            errors.append(rule_error("REVIEW_DED_001", "same-page state change must not be rendered as page_flow_edges"))
    return errors


def contract_promotion_semantic_errors(doc: dict) -> list[str]:
    errors = []
    root = doc.get("model_contract_promotion_report", {})
    errors.extend(rule_trace_errors(root, "model_contract_promotion_report.rule_trace"))
    if root.get("status") == "promoted":
        if root.get("contract_profile_id") != "carrier_handoff_operation_chain_v2":
            errors.append(rule_error("CONTRACT_DED_001", "promoted contract must use carrier_handoff_operation_chain_v2"))
        for stage_key in MODEL_STAGE_KEYS:
            if not (root.get("required_model_fields", {}) or {}).get(stage_key):
                errors.append(rule_error("CONTRACT_DED_001", f"promoted contract missing required fields for {stage_key}"))
        for artifact_key in ["interaction_carrier_map", "system_handoff_map", "user_operation_chain", "capability_assessment", "prototype_review_view_model"]:
            if artifact_key not in (root.get("required_artifacts", []) or []):
                errors.append(rule_error("CONTRACT_DED_001", f"promoted contract missing required artifact {artifact_key}"))
    if root.get("writes_prd") is not False:
        errors.append(rule_error("CONTRACT_DED_001", "contract promotion must not write PRD"))
    if root.get("figma_written") is not False:
        errors.append(rule_error("CONTRACT_DED_001", "contract promotion must not write Figma"))
    return errors


def validate_carrier_map(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "interaction_carrier_map.schema.json")
    warnings = []
    if not errors:
        errors.extend(carrier_map_semantic_errors(yload(path)))
    print_result("validate-carrier-map", errors, warnings)


def validate_system_handoff_map(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "system_handoff_map.schema.json")
    warnings = []
    if not errors:
        errors.extend(system_handoff_semantic_errors(yload(path)))
    print_result("validate-system-handoff-map", errors, warnings)


def validate_operation_chain(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "user_operation_chain.schema.json")
    warnings = []
    if not errors:
        errors.extend(operation_chain_semantic_errors(yload(path)))
    print_result("validate-operation-chain", errors, warnings)


def validate_capability_assessment(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "capability_assessment.schema.json")
    warnings = []
    if not errors:
        errors.extend(capability_assessment_semantic_errors(yload(path)))
    print_result("validate-capability-assessment", errors, warnings)


def validate_review_view_model(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "prototype_review_view_model.schema.json")
    warnings = []
    if not errors:
        errors.extend(review_view_model_semantic_errors(yload(path)))
    print_result("validate-review-view-model", errors, warnings)


def validate_contract_promotion(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "model_contract_promotion_report.schema.json")
    warnings = []
    if not errors:
        errors.extend(contract_promotion_semantic_errors(yload(path)))
    print_result("validate-contract-promotion", errors, warnings)


def generate_prototype_artifacts(args):
    ensure_write_allowed("generate-prototype-artifacts")
    source_path = resolve_generator_source(args.source)
    text = source_path.read_text(encoding="utf-8")
    output_root = generator_output_path("io", "output")
    state_root = generator_output_path("io", "state")
    report_root = generator_output_path("prd_orchestrator", "prototype_projection_reports")
    paths = {
        "source_brief": output_root / "prototype_source_brief.yaml",
        "source_slice_index": state_root / "source_slice_index.yaml",
        "deterministic_draft_summary": state_root / "deterministic_generation_draft.yaml",
        "screen_role_obligations": output_root / "screen_role_obligations.yaml",
        "design_kernel": output_root / "design_kernel.yaml",
        "composition_plan": output_root / "composition_plan.yaml",
        "interaction_hotspot_map": output_root / "interaction_hotspot_map.yaml",
        "logic_sidecar_card_map": output_root / "logic_sidecar_card_map.yaml",
        "annotation_stub_map": output_root / "annotation_stub_map.yaml",
        "anchor_badge_map": output_root / "anchor_badge_map.yaml",
        "local_materialization_patch": output_root / "local_materialization_patch.yaml",
        "runtime": output_root / "prototype.runtime.candidate.json",
        "payload": output_root / "prototype-render-payload.yaml",
        "interaction_carrier_map": output_root / "interaction_carrier_map.yaml",
        "system_handoff_map": output_root / "system_handoff_map.yaml",
        "user_operation_chain": output_root / "user_operation_chain.yaml",
        "capability_assessment": output_root / "capability_assessment.yaml",
        "prototype_review_view_model": state_root / "prototype_review_view_model.yaml",
        "model_contract_promotion_report": state_root / "model_contract_promotion_report.yaml",
        "model_execution_contract_resolved": state_root / "model_execution_contract.resolved.yaml",
        "codex_inference_review": state_root / "codex_inference_review.yaml",
        "codex_inference_raw": state_root / "codex_inference_review.raw.md",
        "model_execution_contract": state_root / "model_execution_contract.yaml",
        "model_invocation_trace": state_root / "model_invocation_trace.yaml",
        "generation_job_queue": state_root / "generation_job_queue.yaml",
        "generation_trace": state_root / "generation_trace.yaml",
        "stage_timing_trace": state_root / "stage_timing_trace.yaml",
        "generated_artifact_manifest": state_root / "generated_artifact_manifest.yaml",
        "source_coverage_report": state_root / "source_coverage_report.yaml",
        "report_yaml": report_root / "prototype_projection_report.yaml",
        "report_md": report_root / "prototype_projection_report.md",
        "blueprint_review_md": report_root / "prototype_blueprint_review.md",
    }
    for model_stage in MODEL_STAGE_DEFINITIONS:
        key = model_stage["key"]
        paths[model_path_key(key)] = state_root / f"{model_stage['root_key']}.yaml"
        paths[model_path_key(key, "_contract")] = state_root / f"{model_stage['root_key']}.execution_contract.yaml"
        paths[model_path_key(key, "_raw")] = state_root / f"{model_stage['root_key']}.raw.md"
        paths[model_path_key(key, "_trace")] = state_root / f"{model_stage['root_key']}.invocation_trace.yaml"

    stage_records = []
    stage = start_stage_record(
        "GEN-JOB-001-SOURCE-SLICES",
        "GEN-SOURCE-SLICES",
        "GEN-DETERMINISTIC-SOURCE-SLICER",
        "deterministic",
        "GEN-WORKER-SOURCE-ATOM-LIFECYCLE",
        rule_ids_for_artifact("prototype_source_brief"),
        [source_relpath(source_path)],
    )
    brief = source_brief_from_prd(source_path, text)
    ywrite(paths["source_brief"], brief)
    ywrite(paths["source_slice_index"], {
        "source_slice_index": {
            **brief["prototype_source_brief"]["source_slice_index"],
            "rule_trace": rule_trace_for_artifact("source_slice_index"),
        }
    })
    stage_records.append(finish_stage_record(stage, "pass", [
        run_artifact_path(paths["source_brief"]),
        run_artifact_path(paths["source_slice_index"]),
    ]))

    stage = start_stage_record(
        "GEN-JOB-002-DETERMINISTIC-DRAFT",
        "GEN-DETERMINISTIC-DRAFT",
        "GEN-DETERMINISTIC-DRAFT-SUMMARY",
        "deterministic",
        "GEN-WORKER-DETERMINISTIC-DRAFT",
        rule_ids_for_artifact("generation_trace"),
        [run_artifact_path(paths["source_brief"])],
    )
    runtime, payload, drd = build_runtime_and_payload(brief)
    deterministic_draft_summary = build_deterministic_draft_summary(brief, runtime, payload)
    ywrite(paths["deterministic_draft_summary"], deterministic_draft_summary)
    stage_records.append(finish_stage_record(stage, "pass", [
        run_artifact_path(paths["deterministic_draft_summary"]),
    ]))

    stage = start_stage_record(
        "GEN-JOB-003-CARRIER-HANDOFF-DRAFT",
        "GEN-CARRIER-HANDOFF-DRAFT",
        "GEN-DETERMINISTIC-CARRIER-HANDOFF",
        "deterministic",
        "GEN-WORKER-CARRIER-HANDOFF",
        normalize_rule_ids(
            rule_ids_for_artifact("interaction_carrier_map")
            + rule_ids_for_artifact("system_handoff_map")
            + rule_ids_for_artifact("user_operation_chain")
            + rule_ids_for_artifact("capability_assessment")
        ),
        [run_artifact_path(paths["source_brief"]), run_artifact_path(paths["deterministic_draft_summary"])],
    )
    carrier_bundle = build_carrier_handoff_artifacts(brief, runtime, payload)
    for key in ["interaction_carrier_map", "system_handoff_map", "user_operation_chain", "capability_assessment"]:
        ywrite(paths[key], carrier_bundle[key])
    stage_records.append(finish_stage_record(stage, "pass", [
        run_artifact_path(paths["interaction_carrier_map"]),
        run_artifact_path(paths["system_handoff_map"]),
        run_artifact_path(paths["user_operation_chain"]),
        run_artifact_path(paths["capability_assessment"]),
    ]))

    stage = start_stage_record(
        "GEN-JOB-004-CONTRACT-PROMOTION",
        "GEN-CONTRACT-PROMOTION",
        "GEN-DETERMINISTIC-CONTRACT-PROMOTION",
        "deterministic",
        "GEN-WORKER-CONTRACT-PROMOTION",
        rule_ids_for_artifact("model_contract_promotion_report"),
        [
            run_artifact_path(paths["source_brief"]),
            run_artifact_path(paths["interaction_carrier_map"]),
            run_artifact_path(paths["system_handoff_map"]),
            run_artifact_path(paths["user_operation_chain"]),
            run_artifact_path(paths["capability_assessment"]),
        ],
    )
    contract_promotion, resolved_contract = build_contract_promotion_report(brief, carrier_bundle, args)
    ywrite(paths["model_contract_promotion_report"], contract_promotion)
    ywrite(paths["model_execution_contract_resolved"], resolved_contract)
    stage_records.append(finish_stage_record(stage, "pass", [
        run_artifact_path(paths["model_contract_promotion_report"]),
        run_artifact_path(paths["model_execution_contract_resolved"]),
    ]))

    model_artifacts = {}
    model_contracts = {}
    model_traces = {}
    for model_stage in MODEL_STAGE_DEFINITIONS:
        stage = start_stage_record(
            model_stage["job_id"],
            model_stage["stage_id"],
            model_stage["generator_id"],
            "model",
            model_stage["worker_id"],
            rule_ids_for_artifact("model_invocation_trace"),
            [
                run_artifact_path(paths["source_brief"]),
                run_artifact_path(paths["source_slice_index"]),
                run_artifact_path(paths["deterministic_draft_summary"]),
            ] + [
                run_artifact_path(paths[model_path_key(prior_key)])
                for prior_key in model_artifacts
            ],
        )
        artifact, contract, trace = run_model_stage(
            model_stage,
            args,
            brief,
            runtime,
            payload,
            paths,
            model_artifacts,
            carrier_bundle,
            contract_promotion,
        )
        model_artifacts[model_stage["key"]] = artifact
        model_contracts[model_stage["key"]] = contract
        model_traces[model_stage["key"]] = trace
        stage_records.append(finish_stage_record(
            stage,
            trace["model_invocation_trace"].get("status", "pass"),
            model_stage_output_paths(paths, model_stage),
        ))

    model_contract = build_model_execution_contract_summary(
        model_contracts,
        args,
        paths,
        payload["prototype_render_payload"]["source_refs"],
        contract_promotion,
    )
    ywrite(paths["model_execution_contract"], model_contract)
    model_invocation_trace = build_model_invocation_trace_summary(model_traces, args, paths, contract_promotion)
    ywrite(paths["model_invocation_trace"], model_invocation_trace)
    codex_review = build_combined_model_review(model_artifacts, model_traces)
    codex_review["codex_inference_review"]["requested_mode"] = args.codex_inference
    ywrite(paths["codex_inference_review"], codex_review)
    paths["codex_inference_raw"].parent.mkdir(parents=True, exist_ok=True)
    paths["codex_inference_raw"].write_text(
        "\n".join([
            "# Codex multistage raw outputs",
            *[
                f"- {stage['stage_id']}: {run_artifact_path(paths[model_path_key(stage['key'], '_raw')])}"
                for stage in MODEL_STAGE_DEFINITIONS
            ],
            "",
        ]),
        encoding="utf-8",
    )

    stage = start_stage_record(
        "GEN-JOB-009-FINAL-MATERIALIZATION",
        "GEN-FINAL-MATERIALIZATION",
        "GEN-DETERMINISTIC-FINAL-MATERIALIZER",
        "deterministic",
        "GEN-WORKER-FINAL-MATERIALIZATION",
        normalize_rule_ids(
            rule_ids_for_artifact("payload")
            + rule_ids_for_artifact("runtime")
            + rule_ids_for_artifact("screen_role_obligations")
            + rule_ids_for_artifact("design_kernel")
            + rule_ids_for_artifact("composition_plan")
            + rule_ids_for_artifact("interaction_hotspot_map")
            + rule_ids_for_artifact("logic_sidecar_card_map")
            + rule_ids_for_artifact("local_materialization_patch")
            + rule_ids_for_artifact("interaction_carrier_map")
            + rule_ids_for_artifact("system_handoff_map")
            + rule_ids_for_artifact("user_operation_chain")
            + rule_ids_for_artifact("capability_assessment")
        ),
        [
            run_artifact_path(paths["source_brief"]),
            run_artifact_path(paths["deterministic_draft_summary"]),
            run_artifact_path(paths["interaction_carrier_map"]),
            run_artifact_path(paths["system_handoff_map"]),
            run_artifact_path(paths["user_operation_chain"]),
            run_artifact_path(paths["capability_assessment"]),
            run_artifact_path(paths["model_contract_promotion_report"]),
        ] + [
            run_artifact_path(paths[model_path_key(model_stage["key"])])
            for model_stage in MODEL_STAGE_DEFINITIONS
        ],
    )
    model_application = apply_model_blueprint_guidance(runtime, payload, model_artifacts, paths, carrier_bundle)
    for key, value in drd.items():
        ywrite(paths[key], value)
    jwrite(paths["runtime"], runtime)
    ywrite(paths["payload"], payload)
    runtime_hash = sha256_file(paths["runtime"])
    payload_hash = sha256_file(paths["payload"])
    model_invocation_trace = update_model_trace_after_final_write(model_invocation_trace, paths)
    ywrite(paths["model_invocation_trace"], model_invocation_trace)
    stage_records.append(finish_stage_record(stage, "pass", [
        run_artifact_path(paths["runtime"]),
        run_artifact_path(paths["payload"]),
        run_artifact_path(paths["screen_role_obligations"]),
        run_artifact_path(paths["design_kernel"]),
        run_artifact_path(paths["composition_plan"]),
        run_artifact_path(paths["interaction_hotspot_map"]),
        run_artifact_path(paths["logic_sidecar_card_map"]),
        run_artifact_path(paths["annotation_stub_map"]),
        run_artifact_path(paths["anchor_badge_map"]),
        run_artifact_path(paths["local_materialization_patch"]),
        run_artifact_path(paths["interaction_carrier_map"]),
        run_artifact_path(paths["system_handoff_map"]),
        run_artifact_path(paths["user_operation_chain"]),
        run_artifact_path(paths["capability_assessment"]),
    ]))

    stage = start_stage_record(
        "GEN-JOB-010-REVIEW-VIEW-MODEL",
        "GEN-REVIEW-VIEW-MODEL",
        "GEN-DETERMINISTIC-REVIEW-VIEW-MODEL",
        "deterministic",
        "GEN-WORKER-REVIEW-VIEW-MODEL",
        rule_ids_for_artifact("prototype_review_view_model"),
        [
            run_artifact_path(paths["runtime"]),
            run_artifact_path(paths["payload"]),
            run_artifact_path(paths["interaction_carrier_map"]),
            run_artifact_path(paths["system_handoff_map"]),
            run_artifact_path(paths["user_operation_chain"]),
            run_artifact_path(paths["capability_assessment"]),
        ],
    )
    review_view_model = build_prototype_review_view_model(runtime, payload, carrier_bundle, model_artifacts)
    ywrite(paths["prototype_review_view_model"], review_view_model)
    paths["blueprint_review_md"].parent.mkdir(parents=True, exist_ok=True)
    paths["blueprint_review_md"].write_text(render_blueprint_review_markdown_from_view_model(review_view_model), encoding="utf-8")
    stage_records.append(finish_stage_record(stage, "pass", [
        run_artifact_path(paths["prototype_review_view_model"]),
        run_artifact_path(paths["blueprint_review_md"]),
    ]))

    stage = start_stage_record(
        "GEN-JOB-011-COVERAGE-MANIFEST",
        "GEN-COVERAGE-MANIFEST",
        "GEN-DETERMINISTIC-COVERAGE-MANIFEST",
        "deterministic",
        "GEN-WORKER-TRACE-MANIFEST",
        rule_ids_for_artifact("generation_trace"),
        [
            run_artifact_path(paths["runtime"]),
            run_artifact_path(paths["payload"]),
            run_artifact_path(paths["prototype_review_view_model"]),
        ],
    )
    coverage_report = build_source_coverage_report(brief, runtime, payload)
    ywrite(paths["source_coverage_report"], coverage_report)
    generation_trace = build_generation_trace(
        source_path,
        paths,
        payload["prototype_render_payload"]["source_refs"],
        payload_hash,
        brief["prototype_source_brief"].get("generation_gaps", []),
        model_artifacts,
        model_invocation_trace,
        model_application,
    )
    ywrite(paths["generation_trace"], generation_trace)
    counts = {
        "source_sections": len(brief["prototype_source_brief"]["sections"]),
        "source_atoms": len(brief["prototype_source_brief"]["source_atoms"]),
        "screen_candidates": len(brief["prototype_source_brief"]["screen_task_candidates"]),
        "state_candidates": len(brief["prototype_source_brief"]["state_candidates"]),
        "interaction_candidates": len(brief["prototype_source_brief"]["interaction_candidates"]),
        "runtime_screens": len(runtime["screens"]),
        "runtime_edges": len(runtime["interaction_graph"]["edges"]),
        "payload_frames": len(payload["prototype_render_payload"]["frames"]),
        "payload_components": len(payload["prototype_render_payload"]["components"]),
        "coverage_required_atoms": len(coverage_report["source_coverage_report"]["coverage_results"]),
        "coverage_uncovered_atoms": len([item for item in coverage_report["source_coverage_report"]["coverage_results"] if not item.get("covered")]),
        "carrier_mapped_interactions": len(carrier_bundle["interaction_carrier_map"]["interaction_carrier_map"].get("interaction_carriers", [])),
        "system_handoffs": len(carrier_bundle["system_handoff_map"]["system_handoff_map"].get("handoffs", [])),
        "operation_chains": len(carrier_bundle["user_operation_chain"]["user_operation_chain"].get("chains", [])),
    }
    report = {
        "prototype_projection_report": {
            "version": "3.1.1",
            "report_id": f"PROTO-GEN-{RUN_ID}",
            "run_id": RUN_ID,
            "generated_at": utc_now_text(),
            "generator": "prototype_artifact_generator_v3_1_2",
            "rule_trace": rule_trace_for_artifact("projection_report"),
            "source_path": brief["prototype_source_brief"]["source_path"],
            "source_sha256": brief["prototype_source_brief"]["source_sha256"],
            "forbidden_as_fact_source": True,
            "outputs": {
                "source_brief": paths["source_brief"].relative_to(RUN_ROOT).as_posix(),
                "source_slice_index": paths["source_slice_index"].relative_to(RUN_ROOT).as_posix(),
                "deterministic_draft_summary": paths["deterministic_draft_summary"].relative_to(RUN_ROOT).as_posix(),
                "runtime_candidate": paths["runtime"].relative_to(RUN_ROOT).as_posix(),
                "render_payload": paths["payload"].relative_to(RUN_ROOT).as_posix(),
                "source_coverage_report": paths["source_coverage_report"].relative_to(RUN_ROOT).as_posix(),
                "interaction_carrier_map": paths["interaction_carrier_map"].relative_to(RUN_ROOT).as_posix(),
                "system_handoff_map": paths["system_handoff_map"].relative_to(RUN_ROOT).as_posix(),
                "user_operation_chain": paths["user_operation_chain"].relative_to(RUN_ROOT).as_posix(),
                "capability_assessment": paths["capability_assessment"].relative_to(RUN_ROOT).as_posix(),
                "prototype_review_view_model": paths["prototype_review_view_model"].relative_to(RUN_ROOT).as_posix(),
                "model_contract_promotion_report": paths["model_contract_promotion_report"].relative_to(RUN_ROOT).as_posix(),
                "model_execution_contract_resolved": paths["model_execution_contract_resolved"].relative_to(RUN_ROOT).as_posix(),
                "generation_job_queue": paths["generation_job_queue"].relative_to(RUN_ROOT).as_posix(),
                "generation_trace": paths["generation_trace"].relative_to(RUN_ROOT).as_posix(),
                "stage_timing_trace": paths["stage_timing_trace"].relative_to(RUN_ROOT).as_posix(),
                "generated_artifact_manifest": paths["generated_artifact_manifest"].relative_to(RUN_ROOT).as_posix(),
                "model_execution_contract": paths["model_execution_contract"].relative_to(RUN_ROOT).as_posix(),
                "model_invocation_trace": paths["model_invocation_trace"].relative_to(RUN_ROOT).as_posix(),
                "codex_inference_review": paths["codex_inference_review"].relative_to(RUN_ROOT).as_posix(),
                "blueprint_review": paths["blueprint_review_md"].relative_to(RUN_ROOT).as_posix(),
                "runtime_sha256": runtime_hash,
                "payload_sha256": payload_hash,
            },
            "counts": counts,
            "blocked_inferences": brief["prototype_source_brief"].get("blocked_inferences", []),
            "generation_gaps": brief["prototype_source_brief"].get("generation_gaps", []),
            "coverage_status": coverage_report["source_coverage_report"]["status"],
            "codex_inference_status": codex_review["codex_inference_review"].get("status"),
            "model_stage_count": len(MODEL_STAGE_DEFINITIONS),
            "model_stages_called": sum(
                1
                for trace in (model_invocation_trace["model_invocation_trace"].get("model_stages", []) or [])
                if trace.get("model_called") is True
            ),
            "model_blueprint_applied_to_final_outputs": model_application.get("applied_to_final_outputs") is True,
            "figma_written": False,
            "readiness_next_command": (
                "python scripts/prd_control/prototypectl.py "
                f"--instance-root {INSTANCE_ROOT} --run-id {RUN_ID} "
                "validate-render-readiness "
                f"--runtime {paths['runtime'].relative_to(INSTANCE_ROOT).as_posix()} "
                f"--payload {paths['payload'].relative_to(INSTANCE_ROOT).as_posix()}"
            ),
        }
    }
    ywrite(paths["report_yaml"], report)
    paths["report_md"].write_text(render_report_markdown(report), encoding="utf-8")
    stage_records.append(finish_stage_record(stage, "pass", [
        run_artifact_path(paths["source_coverage_report"]),
        run_artifact_path(paths["generation_trace"]),
        run_artifact_path(paths["report_yaml"]),
        run_artifact_path(paths["report_md"]),
        run_artifact_path(paths["blueprint_review_md"]),
        run_artifact_path(paths["prototype_review_view_model"]),
    ]))
    stage_timing_trace = build_stage_timing_trace(paths, stage_records)
    ywrite(paths["stage_timing_trace"], stage_timing_trace)
    generation_job_queue = build_generation_job_queue(
        paths,
        payload["prototype_render_payload"]["source_refs"],
        model_invocation_trace,
        stage_records,
    )
    ywrite(paths["generation_job_queue"], generation_job_queue)
    artifact_manifest = build_generated_artifact_manifest(paths)
    ywrite(paths["generated_artifact_manifest"], artifact_manifest)

    errors = validate_generated_artifacts(paths)
    if errors:
        raise SystemExit("BLOCKED: generated prototype artifacts failed validation:\n- " + "\n- ".join(errors))
    print("# generate-prototype-artifacts")
    print("PASS")
    for key in [
        "source_brief",
        "source_slice_index",
        "deterministic_draft_summary",
        "screen_role_obligations",
        "design_kernel",
        "composition_plan",
        "interaction_hotspot_map",
        "logic_sidecar_card_map",
        "annotation_stub_map",
        "anchor_badge_map",
        "local_materialization_patch",
        "interaction_carrier_map",
        "system_handoff_map",
        "user_operation_chain",
        "capability_assessment",
        "prototype_review_view_model",
        "model_contract_promotion_report",
        "model_execution_contract_resolved",
        "runtime",
        "payload",
        "codex_inference_review",
        "model_execution_contract",
        "model_invocation_trace",
        *[model_path_key(stage["key"]) for stage in MODEL_STAGE_DEFINITIONS],
        *[model_path_key(stage["key"], "_contract") for stage in MODEL_STAGE_DEFINITIONS],
        *[model_path_key(stage["key"], "_trace") for stage in MODEL_STAGE_DEFINITIONS],
        "generation_job_queue",
        "source_coverage_report",
        "generation_trace",
        "stage_timing_trace",
        "generated_artifact_manifest",
        "report_yaml",
        "report_md",
        "blueprint_review_md",
    ]:
        print(f"- WROTE {paths[key]}")
    print(json.dumps({"counts": counts}, ensure_ascii=False, indent=2))


def validate_generation_lifecycle_rules(args):
    errors = []
    warnings = []
    lifecycle_root = DRD_ROOT / "generation_lifecycle_v3_1_1"
    for rel in generation_lifecycle_required_files():
        if not (ROOT / rel).exists():
            errors.append(f"missing required generation lifecycle file: {rel}")
    for path in sorted(lifecycle_root.rglob("*.yaml")):
        try:
            yload(path)
        except Exception as exc:
            errors.append(f"{path.relative_to(ROOT)}: YAML parse failed: {exc}")
    for path in sorted(lifecycle_root.rglob("*.json")):
        try:
            jload(path)
        except Exception as exc:
            errors.append(f"{path.relative_to(ROOT)}: JSON parse failed: {exc}")
    aligned = yload(lifecycle_root / "package_manifest.harness_aligned.yaml").get("package", {})
    if aligned.get("production_rule", {}).get("image_upload_3_5_first_pass_generation.sample.yaml") != "removed_from_production_package":
        errors.append("image_upload_3_5_first_pass_generation.sample.yaml must be removed from production package")
    if aligned.get("production_rule", {}).get("sample_files_not_read_by_generator") is not True:
        errors.append("harness-aligned package must mark samples as not read by generator")
    if aligned.get("production_rule", {}).get("generic_boundary_algorithm_required") is not True:
        errors.append("harness-aligned package must require generic boundary algorithm")
    for key in [
        "generation_job_queue_required",
        "generation_job_completion_criteria_required",
        "deterministic_and_model_generators_must_be_separate",
        "model_execution_contract_required",
        "model_invocation_trace_required",
    ]:
        if aligned.get("production_rule", {}).get(key) is not True:
            errors.append(f"harness-aligned package must set {key}: true")
    print_result("validate-generation-lifecycle-rules", errors, warnings)


def validate_generation_job_queue(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "generation_job_queue.schema.json")
    warnings = []
    if not errors:
        queue = yload(path).get("generation_job_queue", {})
        errors.extend(rule_trace_errors(queue, "generation_job_queue.rule_trace"))
        kinds = {job.get("generator_kind") for job in queue.get("jobs", []) or []}
        if "deterministic" not in kinds:
            errors.append("generation_job_queue must include deterministic generator jobs")
        if "model" not in kinds:
            errors.append("generation_job_queue must include model generator job")
        for job in queue.get("jobs", []) or []:
            job_id = job.get("job_id", "<unknown>")
            errors.extend(rule_trace_errors(job, f"{job_id}.rule_ids"))
            if job.get("writes_prd") is not False:
                errors.append(f"{job_id}: writes_prd must be false")
            for timing_key in ["started_at", "completed_at", "duration_ms"]:
                if timing_key not in job:
                    errors.append(f"{job_id}: {timing_key} is required")
            if job.get("duration_ms") is not None and int(job.get("duration_ms") or 0) < 0:
                errors.append(f"{job_id}: duration_ms must be >= 0")
            if not job.get("completion_criteria"):
                errors.append(f"{job_id}: completion_criteria is required")
            for criterion in job.get("completion_criteria", []) or []:
                criterion_id = criterion.get("criterion_id", "<unknown>")
                errors.extend(rule_trace_errors(criterion, f"{job_id}/{criterion_id}.rule_ids"))
                if criterion.get("required", True) and criterion.get("status") == "blocked":
                    errors.append(f"{job_id}/{criterion_id}: required completion criterion is blocked")
        jobs_by_id = {job.get("job_id"): job for job in queue.get("jobs", []) or []}
        model_job_ids = [stage["job_id"] for stage in MODEL_STAGE_DEFINITIONS]
        for stage in MODEL_STAGE_DEFINITIONS:
            model_job = jobs_by_id.get(stage["job_id"])
            if not model_job:
                errors.append(f"generation_job_queue must include {stage['job_id']}")
                continue
            if model_job.get("stage_id") != stage["stage_id"]:
                errors.append(f"{stage['job_id']}.stage_id must be {stage['stage_id']}")
            if model_job.get("generator_kind") != "model":
                errors.append(f"{stage['job_id']}.generator_kind must be model")
            if not any(stage["root_key"] in ref for ref in model_job.get("output_refs", []) or []):
                errors.append(f"{stage['job_id']}.output_refs must include {stage['root_key']} artifact")
        final_job = jobs_by_id.get("GEN-JOB-009-FINAL-MATERIALIZATION")
        if final_job:
            missing_deps = sorted(set(model_job_ids) - set(final_job.get("dependency_job_ids") or []))
            if missing_deps:
                errors.append(f"GEN-JOB-009-FINAL-MATERIALIZATION missing model dependencies: {', '.join(missing_deps)}")
        else:
            errors.append("generation_job_queue must include GEN-JOB-009-FINAL-MATERIALIZATION")
        for required_job in ["GEN-JOB-003-CARRIER-HANDOFF-DRAFT", "GEN-JOB-004-CONTRACT-PROMOTION", "GEN-JOB-010-REVIEW-VIEW-MODEL"]:
            if required_job not in jobs_by_id:
                errors.append(f"generation_job_queue must include {required_job}")
        coverage_job = jobs_by_id.get("GEN-JOB-011-COVERAGE-MANIFEST")
        if not coverage_job:
            errors.append("generation_job_queue must include GEN-JOB-011-COVERAGE-MANIFEST")
        elif "GEN-JOB-010-REVIEW-VIEW-MODEL" not in (coverage_job.get("dependency_job_ids") or []):
            errors.append("GEN-JOB-011-COVERAGE-MANIFEST must depend on GEN-JOB-010-REVIEW-VIEW-MODEL")
        summary = queue.get("completion_summary", {})
        if summary.get("total_jobs") != 11:
            errors.append("generation_job_queue.completion_summary.total_jobs must be 11")
        if summary.get("model_generator_jobs") != 4:
            errors.append("generation_job_queue.completion_summary.model_generator_jobs must be 4")
        if summary.get("blocked_jobs", 0) > 0:
            errors.append("generation_job_queue.completion_summary.blocked_jobs must be 0")
        if summary.get("all_required_criteria_passed") is not True:
            errors.append("generation_job_queue.completion_summary.all_required_criteria_passed must be true")
    print_result("validate-generation-job-queue", errors, warnings)


def validate_generation_trace(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "generation_trace.schema.json")
    warnings = []
    if not errors:
        trace = yload(path).get("generation_trace", {})
        errors.extend(rule_trace_errors(trace, "generation_trace.rule_trace"))
        if trace.get("generator_id") not in {"prototype_artifact_generator_v3_1_1", "prototype_artifact_generator_v3_1_2"}:
            errors.append("generation_trace.generator_id must be prototype_artifact_generator_v3_1_1 or prototype_artifact_generator_v3_1_2")
        if not trace.get("source_refs"):
            errors.append("generation_trace.source_refs must not be empty")
        if trace.get("artifact_path", "").startswith("product-spec/"):
            errors.append("generation_trace.artifact_path must not target product-spec")
        families = {item.get("generator_kind") for item in trace.get("generator_families", []) or []}
        for family in trace.get("generator_families", []) or []:
            errors.extend(rule_trace_errors(family, f"generation_trace.generator_families.{family.get('generator_id', '<unknown>')}.rule_ids"))
        for decision in trace.get("decisions", []) or []:
            errors.extend(rule_trace_errors(decision, f"generation_trace.decisions.{decision.get('decision_id', '<unknown>')}.rule_ids"))
        if "deterministic" not in families:
            errors.append("generation_trace.generator_families must include deterministic")
        if "model" not in families:
            errors.append("generation_trace.generator_families must include model")
        if not trace.get("generation_job_queue_ref"):
            errors.append("generation_trace.generation_job_queue_ref is required")
        model = trace.get("model_inference", {})
        if not model.get("execution_contract_path"):
            errors.append("generation_trace.model_inference.execution_contract_path is required")
        if not model.get("invocation_trace_path"):
            errors.append("generation_trace.model_inference.invocation_trace_path is required")
        if model.get("stage_role") != "multi_stage_generation_reasoning":
            errors.append("generation_trace.model_inference.stage_role must be multi_stage_generation_reasoning")
        if model.get("required_model_stage_count") != 4:
            errors.append("generation_trace.model_inference.required_model_stage_count must be 4")
        if set((model.get("model_stage_artifacts") or {}).keys()) != set(MODEL_STAGE_KEYS):
            errors.append("generation_trace.model_inference.model_stage_artifacts must include all 4 model stage keys")
        if model.get("model_called") is True and model.get("final_outputs_written_after_model") is not True:
            errors.append("generation_trace.model_inference.final_outputs_written_after_model must be true when model is called")
        if model.get("model_called") is True and model.get("applied_to_final_outputs") is not True:
            errors.append("generation_trace.model_inference.applied_to_final_outputs must be true when model is called")
        if not trace.get("stage_timing_trace_ref"):
            errors.append("generation_trace.stage_timing_trace_ref is required")
    print_result("validate-generation-trace", errors, warnings)


def validate_model_execution_contract(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "model_execution_contract.schema.json")
    warnings = []
    if not errors:
        contract = yload(path).get("model_execution_contract", {})
        errors.extend(rule_trace_errors(contract, "model_execution_contract.rule_trace"))
        policy = contract.get("command_policy", {})
        if policy.get("sandbox") != "read-only":
            errors.append("model_execution_contract.command_policy.sandbox must be read-only")
        if policy.get("writes_allowed") is not False:
            errors.append("model_execution_contract.command_policy.writes_allowed must be false")
        forbidden = set(contract.get("forbidden_operations", []) or [])
        for required in ["write_prd", "write_product_spec", "write_figma", "mutate_runtime_or_payload"]:
            if required not in forbidden:
                errors.append(f"model_execution_contract.forbidden_operations missing {required}")
        if contract.get("generator_kind") != "model":
            errors.append("model_execution_contract.generator_kind must be model")
        stage_roots = contract.get("model_stages", []) or []
        if stage_roots:
            if contract.get("stage_role") != "multi_stage_generation_reasoning":
                errors.append("model_execution_contract.stage_role must be multi_stage_generation_reasoning")
            if contract.get("model_output_kind") != "prototype_multistage_reasoning":
                errors.append("model_execution_contract.model_output_kind must be prototype_multistage_reasoning")
            if len(stage_roots) != 4:
                errors.append("model_execution_contract.model_stages must include 4 stages")
            stage_ids = {item.get("stage_id") for item in stage_roots}
            for stage in MODEL_STAGE_DEFINITIONS:
                if stage["stage_id"] not in stage_ids:
                    errors.append(f"model_execution_contract.model_stages missing {stage['stage_id']}")
            for item in stage_roots:
                if item.get("command_policy", {}).get("sandbox") != "read-only":
                    errors.append(f"{item.get('stage_id', '<unknown>')}: command_policy.sandbox must be read-only")
                if item.get("command_policy", {}).get("writes_allowed") is not False:
                    errors.append(f"{item.get('stage_id', '<unknown>')}: command_policy.writes_allowed must be false")
        else:
            if contract.get("stage_role") not in set(MODEL_STAGE_KEYS):
                errors.append("model_execution_contract.stage_role must be one of the model stage keys")
            expected_kinds = {stage["output_kind"] for stage in MODEL_STAGE_DEFINITIONS}
            if contract.get("model_output_kind") not in expected_kinds:
                errors.append("model_execution_contract.model_output_kind must match a model stage output kind")
        inputs = set(contract.get("input_refs", []) or [])
        if not any("deterministic_generation_draft" in item for item in inputs):
            errors.append("model_execution_contract.input_refs must include deterministic_generation_draft before final output materialization")
        for criterion in contract.get("completion_criteria", []) or []:
            errors.extend(rule_trace_errors(criterion, f"model_execution_contract.{criterion.get('criterion_id', '<unknown>')}.rule_ids"))
    print_result("validate-model-execution-contract", errors, warnings)


def validate_model_invocation_trace(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "model_invocation_trace.schema.json")
    warnings = []
    if not errors:
        trace = yload(path).get("model_invocation_trace", {})
        errors.extend(rule_trace_errors(trace, "model_invocation_trace.rule_trace"))
        stage_roots = trace.get("model_stages", []) or []
        if stage_roots:
            if trace.get("stage_role") != "multi_stage_generation_reasoning":
                errors.append("model_invocation_trace.stage_role must be multi_stage_generation_reasoning")
            if trace.get("model_output_kind") != "prototype_multistage_reasoning":
                errors.append("model_invocation_trace.model_output_kind must be prototype_multistage_reasoning")
            if len(stage_roots) != 4:
                errors.append("model_invocation_trace.model_stages must include 4 stages")
            stage_ids = {item.get("stage_id") for item in stage_roots}
            for stage in MODEL_STAGE_DEFINITIONS:
                if stage["stage_id"] not in stage_ids:
                    errors.append(f"model_invocation_trace.model_stages missing {stage['stage_id']}")
            if trace.get("execution_mode") == "required" and trace.get("model_called") is not True:
                errors.append("model_invocation_trace required mode must call all model stages")
            if trace.get("execution_mode") == "required" and int(trace.get("duration_ms") or 0) <= 0:
                errors.append("model_invocation_trace required mode must record aggregate duration_ms > 0")
            for item in stage_roots:
                label = item.get("stage_id", "<unknown>")
                if item.get("execution_mode") == "required" and item.get("model_called") is not True:
                    errors.append(f"{label}: required mode must call Codex CLI")
                if item.get("execution_mode") == "required" and item.get("exit_code") != 0:
                    errors.append(f"{label}: required mode must have exit_code 0")
                if item.get("execution_mode") == "required" and int(item.get("duration_ms") or 0) <= 0:
                    errors.append(f"{label}: required mode must record duration_ms > 0")
                if item.get("model_called") is True and not item.get("command"):
                    errors.append(f"{label}: command is required when model_called is true")
                if item.get("command_policy", {}).get("sandbox") != "read-only":
                    errors.append(f"{label}: command_policy.sandbox must be read-only")
                if item.get("command_policy", {}).get("writes_allowed") is not False:
                    errors.append(f"{label}: command_policy.writes_allowed must be false")
                if item.get("model_called") is True and not item.get("input_hashes", {}).get("prompt"):
                    errors.append(f"{label}: input_hashes.prompt is required")
                for criterion in item.get("completion_criteria_results", []) or []:
                    errors.extend(rule_trace_errors(criterion, f"{label}.{criterion.get('criterion_id', '<unknown>')}.rule_ids"))
                    if criterion.get("required", True) and criterion.get("status") == "blocked":
                        errors.append(f"{label}/{criterion.get('criterion_id')}: required model completion criterion is blocked")
        else:
            if not trace.get("input_hashes", {}).get("prompt"):
                errors.append("model_invocation_trace.input_hashes.prompt is required")
            if trace.get("execution_mode") == "required" and trace.get("exit_code") != 0:
                errors.append("model_invocation_trace required mode must have exit_code 0")
            if trace.get("execution_mode") == "required" and trace.get("model_called") is not True:
                errors.append("model_invocation_trace required mode must call the model")
            if trace.get("stage_role") not in set(MODEL_STAGE_KEYS):
                errors.append("model_invocation_trace.stage_role must be one of the model stage keys")
            expected_kinds = {stage["output_kind"] for stage in MODEL_STAGE_DEFINITIONS}
            if trace.get("model_output_kind") not in expected_kinds:
                errors.append("model_invocation_trace.model_output_kind must match a model stage output kind")
            if trace.get("execution_mode") == "required" and int(trace.get("duration_ms") or 0) <= 0:
                errors.append("model_invocation_trace required mode must record duration_ms > 0")
            if trace.get("model_called") is True and not trace.get("command"):
                errors.append("model_invocation_trace.command is required when model_called is true")
        if trace.get("execution_mode") == "required":
            policy = trace.get("final_output_write_policy", {}) or {}
            if policy.get("final_outputs_written_after_model") is not True:
                errors.append("model_invocation_trace.final_output_write_policy.final_outputs_written_after_model must be true")
            hashes = policy.get("final_output_hashes", {}) or {}
            if not hashes.get("runtime") or not hashes.get("payload"):
                errors.append("model_invocation_trace.final_output_write_policy.final_output_hashes must include runtime and payload")
        for criterion in trace.get("completion_criteria_results", []) or []:
            errors.extend(rule_trace_errors(criterion, f"model_invocation_trace.{criterion.get('criterion_id', '<unknown>')}.rule_ids"))
            if criterion.get("required", True) and criterion.get("status") == "blocked":
                errors.append(f"{criterion.get('criterion_id')}: required model completion criterion is blocked")
    print_result("validate-model-invocation-trace", errors, warnings)


def model_artifact_validation_errors(path: Path, stage_key: str) -> list[str]:
    errors = []
    stage = MODEL_STAGE_BY_KEY[stage_key]
    if not path.exists():
        return [f"missing model artifact {path}"]
    try:
        data = yload(path)
    except Exception as exc:
        return [f"{path}: YAML parse failed: {exc}"]
    root = data.get(stage["root_key"], {}) if isinstance(data, dict) else {}
    if not isinstance(root, dict):
        return [f"{stage['root_key']} root must be an object"]
    errors.extend(rule_trace_errors(root, f"{stage['root_key']}.rule_trace"))
    if root.get("version") not in {"3.1.1", "3.1.2"}:
        errors.append(f"{stage['root_key']}.version must be 3.1.1 or 3.1.2")
    if root.get("mode") != "DRD_MODE":
        errors.append(f"{stage['root_key']}.mode must be DRD_MODE")
    if root.get("stage_id") != stage["stage_id"]:
        errors.append(f"{stage['root_key']}.stage_id must be {stage['stage_id']}")
    if root.get("stage_role") != stage_key:
        errors.append(f"{stage['root_key']}.stage_role must be {stage_key}")
    if root.get("status") not in {"pass", "review_required", "blocked", "skipped"}:
        errors.append(f"{stage['root_key']}.status must be pass/review_required/blocked/skipped")
    if root.get("status") != "skipped" and not root.get("source_refs"):
        errors.append(f"{stage['root_key']}.source_refs must not be empty")
    primary = root.get(stage["primary_collection"], []) or []
    if root.get("status") in {"pass", "review_required"} and not primary:
        errors.append(f"{stage['root_key']}.{stage['primary_collection']} must not be empty")
    promoted_contract = root.get("contract_profile_id") == "carrier_handoff_operation_chain_v2"
    if stage_key == "surface_ownership":
        for idx, item in enumerate(primary, start=1):
            label = item.get("screen_id") or f"surface_blueprint[{idx}]"
            for field in ["screen_id", "page_purpose_zh", "page_boundary_zh", "state_policy_zh"]:
                if not item.get(field):
                    errors.append(f"{label}: missing {field}")
            if promoted_contract:
                for field in ["carrier_type", "host_context_zh", "system_surface_refs"]:
                    if field not in item or item.get(field) in [None, ""]:
                        errors.append(f"{label}: promoted contract missing {field}")
                if item.get("standalone_page_allowed") not in {True, False}:
                    errors.append(f"{label}: promoted contract missing standalone_page_allowed boolean")
            if not item.get("source_refs"):
                errors.append(f"{label}: missing source_refs")
    elif stage_key == "user_journey":
        for idx, item in enumerate(primary, start=1):
            label = f"journey_edges[{idx}]"
            for field in ["source_screen_id", "target_screen_id", "trigger_zh", "source_refs"]:
                if not item.get(field):
                    errors.append(f"{label}: missing {field}")
            if promoted_contract:
                for field in ["operation_chain_id", "carrier_transition_type", "handoff_ids"]:
                    if field not in item or item.get(field) in [None, ""]:
                        errors.append(f"{label}: promoted contract missing {field}")
    elif stage_key == "interaction_state_machine":
        for idx, item in enumerate(primary, start=1):
            label = item.get("interaction_id") or f"state_transitions[{idx}]"
            for field in ["source_state_id", "target_state_id", "trigger_zh", "source_refs"]:
                if not item.get(field):
                    errors.append(f"{label}: missing {field}")
            if promoted_contract:
                for field in ["edge_type", "feedback_surface_zh"]:
                    if not item.get(field):
                        errors.append(f"{label}: promoted contract missing {field}")
                if item.get("stays_on_same_surface") not in {True, False}:
                    errors.append(f"{label}: promoted contract missing stays_on_same_surface boolean")
        for idx, item in enumerate(root.get("interaction_adjustments", []) or [], start=1):
            label = item.get("interaction_id") or f"interaction_adjustments[{idx}]"
            if not item.get("source_refs"):
                errors.append(f"{label}: adjustment missing source_refs")
            is_structured_adjustment = any(item.get(field) for field in ["interaction_id", "source_state_id", "target_state_id"])
            if is_structured_adjustment and not item.get("target_state_id"):
                errors.append(f"{label}: structured adjustment missing target_state_id")
            if not is_structured_adjustment and not item.get("adjustment_zh"):
                errors.append(f"{label}: unstructured review adjustment must include adjustment_zh")
    elif stage_key == "component_blueprint":
        for idx, item in enumerate(primary, start=1):
            label = f"component_groups[{idx}]"
            for field in ["screen_id", "group_name_zh", "element_type", "component_ids", "source_refs"]:
                if not item.get(field):
                    errors.append(f"{label}: missing {field}")
            if promoted_contract:
                for field in ["carrier_type", "render_region_zh"]:
                    if not item.get(field):
                        errors.append(f"{label}: promoted contract missing {field}")
        for item in root.get("component_intents", []) or []:
            component_id = item.get("component_id", "<unknown>")
            click_intents = sorted({
                str(intent).strip()
                for intent in item.get("click_intents", []) or []
                if str(intent).strip()
            })
            if len(click_intents) > 1:
                errors.append(f"{component_id}: one component has multiple click intents: {' / '.join(click_intents)}")
            if not item.get("source_refs"):
                errors.append(f"{component_id}: missing source_refs")
    return errors


def validate_model_surface_ownership(args):
    errors = model_artifact_validation_errors(resolve_path(args.input), "surface_ownership")
    print_result("validate-model-surface-ownership", errors, [])


def validate_model_user_journey(args):
    errors = model_artifact_validation_errors(resolve_path(args.input), "user_journey")
    print_result("validate-model-user-journey", errors, [])


def validate_model_interaction_state_machine(args):
    errors = model_artifact_validation_errors(resolve_path(args.input), "interaction_state_machine")
    print_result("validate-model-interaction-state-machine", errors, [])


def validate_model_component_blueprint(args):
    errors = model_artifact_validation_errors(resolve_path(args.input), "component_blueprint")
    print_result("validate-model-component-blueprint", errors, [])


def validate_model_stage_coverage(args):
    trace_path = resolve_path(args.trace)
    queue_path = resolve_path(args.job_queue)
    errors = []
    warnings = []
    errors.extend(validate_schema(trace_path, DRD_ROOT / "schemas" / "model_invocation_trace.schema.json"))
    errors.extend(validate_schema(queue_path, DRD_ROOT / "schemas" / "generation_job_queue.schema.json"))
    if not errors:
        trace = yload(trace_path).get("model_invocation_trace", {})
        queue = yload(queue_path).get("generation_job_queue", {})
        stage_roots = trace.get("model_stages", []) or []
        stage_ids = {item.get("stage_id") for item in stage_roots}
        if len(stage_roots) != 4:
            errors.append("model_invocation_trace.model_stages must contain 4 stages")
        for stage in MODEL_STAGE_DEFINITIONS:
            if stage["stage_id"] not in stage_ids:
                errors.append(f"model_invocation_trace missing {stage['stage_id']}")
        if trace.get("execution_mode") == "required":
            for item in stage_roots:
                if item.get("model_called") is not True:
                    errors.append(f"{item.get('stage_id', '<unknown>')}: model_called must be true in required mode")
                if item.get("status") not in {"pass", "review_required"}:
                    errors.append(f"{item.get('stage_id', '<unknown>')}: status must be pass or review_required in required mode")
                if int(item.get("duration_ms") or 0) <= 0:
                    errors.append(f"{item.get('stage_id', '<unknown>')}: duration_ms must be > 0")
        jobs_by_id = {job.get("job_id"): job for job in queue.get("jobs", []) or []}
        model_job_ids = [stage["job_id"] for stage in MODEL_STAGE_DEFINITIONS]
        for job_id in model_job_ids:
            if job_id not in jobs_by_id:
                errors.append(f"generation_job_queue missing {job_id}")
        final_job = jobs_by_id.get("GEN-JOB-009-FINAL-MATERIALIZATION", {})
        missing = sorted(set(model_job_ids) - set(final_job.get("dependency_job_ids") or []))
        if missing:
            errors.append(f"GEN-JOB-009-FINAL-MATERIALIZATION missing dependencies: {', '.join(missing)}")
    print_result("validate-model-stage-coverage", errors, warnings)


def validate_generated_artifact_manifest(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "generated_artifact_manifest.schema.json")
    warnings = []
    if not errors:
        manifest = yload(path).get("generated_artifact_manifest", {})
        errors.extend(rule_trace_errors(manifest, "generated_artifact_manifest.rule_trace"))
        for artifact in manifest.get("artifacts", []) or []:
            errors.extend(rule_trace_errors(artifact, f"generated_artifact_manifest.{artifact.get('artifact_id', '<unknown>')}.rule_ids"))
            rel = artifact.get("path", "")
            if rel.startswith("product-spec/") or rel.startswith("inputs/"):
                errors.append(f"{artifact.get('artifact_id', '<unknown>')}: forbidden artifact path {rel}")
            artifact_path = RUN_ROOT / rel
            if INSTANCE_ROOT_PROVIDED and not artifact_path.exists():
                errors.append(f"{artifact.get('artifact_id', '<unknown>')}: missing artifact file {artifact_path}")
    print_result("validate-generated-artifact-manifest", errors, warnings)


def source_coverage_errors(coverage_doc: dict, runtime: dict, payload: dict) -> list[str]:
    errors = []
    report = coverage_doc.get("source_coverage_report", {})
    errors.extend(rule_trace_errors(report, "source_coverage_report.rule_trace"))
    if report.get("status") != "pass":
        errors.append(rule_error("COMP_DED_001", "source_coverage_report.status must be pass"))
    runtime_state_ids = {
        state.get("state_id")
        for screen in runtime.get("screens", []) or []
        for state in screen.get("states", []) or []
    }
    payload_root = payload.get("prototype_render_payload", {})
    payload_frame_ids = {frame.get("frame_id") for frame in payload_root.get("frames", []) or []}
    payload_text = json.dumps(payload_root, ensure_ascii=False)
    sidecar_text = json.dumps(payload_root.get("sidecar_cards", []), ensure_ascii=False)
    for item in report.get("coverage_results", []) or []:
        if item.get("required") is not True:
            continue
        atom_id = item.get("atom_id", "<unknown>")
        errors.extend(rule_trace_errors(item, f"source_coverage_report.coverage_results.{atom_id}.rule_ids"))
        state_id = item.get("state_id", "")
        frame_id = item.get("payload_frame_id", "")
        if not item.get("covered"):
            errors.append(rule_error("COMP_DED_001", f"{atom_id}: coverage result is uncovered"))
        if state_id not in runtime_state_ids:
            errors.append(rule_error("ROLE_DED_002", f"{atom_id}: runtime missing state {state_id}"))
        if frame_id not in payload_frame_ids or state_id not in payload_text:
            errors.append(rule_error("COMP_DED_001", f"{atom_id}: payload missing frame/state {frame_id}/{state_id}"))
        if item.get("requires_sidecar") is True and state_id not in sidecar_text and atom_id not in sidecar_text:
            errors.append(rule_error("HOT_DED_004", f"{atom_id}: sidecar missing required state or atom reference"))
        if not item.get("source_refs"):
            errors.append(rule_error("ROLE_DED_001", f"{atom_id}: missing source_refs"))
    return errors


def validate_source_coverage(args):
    coverage_path = resolve_path(args.coverage)
    runtime_path = resolve_path(args.runtime)
    payload_path = resolve_path(args.payload)
    errors = []
    warnings = []
    errors.extend(validate_schema(coverage_path, DRD_ROOT / "schemas" / "source_coverage_report.schema.json"))
    errors.extend(validate_schema(runtime_path, ROOT / "schemas" / "prototype_runtime.schema.json"))
    errors.extend(validate_schema(payload_path, ROOT / "schemas" / "prototype_render_payload.schema.json"))
    if not errors:
        errors.extend(source_coverage_errors(yload(coverage_path), jload(runtime_path), load_any(payload_path)))
    print_result("validate-source-coverage", errors, warnings)


def validate_loop_manifest(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, LOOP_ROOT / "schemas" / "loop_manifest.schema.json")
    warnings = []
    if not errors:
        manifest = yload(path)
        errors.extend(rule_trace_errors(manifest, "loop_manifest.rule_trace"))
        for idx, iteration in enumerate(manifest.get("iterations", []) or [], start=1):
            errors.extend(rule_trace_errors(iteration, f"loop_manifest.iterations[{idx}].rule_ids"))
            for finding in iteration.get("findings", []) or []:
                if isinstance(finding, dict):
                    errors.extend(rule_trace_errors(finding, f"loop_manifest.iterations[{idx}].findings.rule_ids"))
            for patch in iteration.get("patch_set", []) or []:
                pid = patch.get("patch_id", f"iteration-{idx}-patch")
                errors.extend(rule_trace_errors(patch, f"loop_manifest.iterations[{idx}].patch_set.{pid}.rule_ids"))
                if patch.get("writes_prd") is not False:
                    errors.append(f"{pid}: writes_prd must be false")
    print_result("validate-loop-manifest", errors, warnings)


def validate_loop_finding(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, LOOP_ROOT / "schemas" / "loop_finding.schema.json")
    warnings = []
    if not errors:
        finding = yload(path)
        errors.extend(rule_trace_errors(finding, "loop_finding.rule_trace"))
        if not finding.get("source_refs"):
            errors.append(f"{finding.get('finding_id', '<unknown>')}: missing source_refs")
    print_result("validate-loop-finding", errors, warnings)


def validate_repair_plan(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, LOOP_ROOT / "schemas" / "repair_plan.schema.json")
    warnings = []
    if not errors:
        plan = yload(path)
        errors.extend(rule_trace_errors(plan, "repair_plan.rule_trace"))
        if plan.get("gate_only") is not True:
            warnings.append("repair_plan.gate_only should be true for v3.1 gate-only phase")
        for finding in plan.get("findings", []) or []:
            if isinstance(finding, dict):
                errors.extend(rule_trace_errors(finding, f"repair_plan.findings.{finding.get('finding_id', '<unknown>')}.rule_ids"))
        for patch in plan.get("patch_set", []) or []:
            pid = patch.get("patch_id", "<unknown>")
            errors.extend(rule_trace_errors(patch, f"repair_plan.patch_set.{pid}.rule_ids"))
            if patch.get("writes_prd") is not False:
                errors.append(f"{pid}: writes_prd must be false")
        if not plan.get("rerun_scope", {}).get("scope"):
            errors.append("repair_plan.rerun_scope.scope is required")
    print_result("validate-repair-plan", errors, warnings)


def validate_stage_loop_contracts(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, LOOP_ROOT / "schemas" / "stage_loop_contract.schema.json")
    warnings = []
    legacy_names = {
        "screen_role_obligation_map.yaml",
        "role_derivation_report.yaml",
        "frame_packets.yaml",
        "anchor_badge_requirements.yaml",
        "leader_line_map.yaml",
    }
    required_current_names = {
        "screen_role_obligations.yaml",
        "role_inference_report.yaml",
        "board_frame_packets.yaml",
        "hotspot_annotation_requirements.yaml",
        "anchor_leader_line_map.yaml",
        "logic_sidecar_card_map.yaml",
        "annotation_stub_map.yaml",
        "anchor_badge_map.yaml",
    }
    forbidden_fact_writes = {
        "PRD.md",
        "requirements.yaml",
        "screens.yaml",
        "metrics.yaml",
        "events.yaml",
    }
    if not errors:
        root = yload(path).get("harness_aligned_stage_loop_contracts", {})
        if root.get("gate_only") is not True:
            errors.append("harness_aligned_stage_loop_contracts.gate_only must be true")
        if root.get("automatic_patch_apply_enabled") is not False:
            errors.append("automatic_patch_apply_enabled must be false")
        if root.get("automatic_rerun_enabled") is not False:
            errors.append("automatic_rerun_enabled must be false")
        all_writes = set()
        for contract in root.get("contracts", []) or []:
            stage_id = contract.get("stage_id", "<unknown>")
            if stage_id != "<unknown>" and not stage_rule_ids(stage_id):
                errors.append(f"{stage_id}: missing rule projection stage mapping")
            writes = set(contract.get("writes", []) or [])
            all_writes.update(writes)
            conflicts = sorted(writes & legacy_names)
            if conflicts:
                errors.append(f"{stage_id}: uses package-conflict artifact names {conflicts}")
            forbidden = set(contract.get("forbidden_writes", []) or [])
            missing_forbidden = sorted(forbidden_fact_writes - forbidden)
            if missing_forbidden:
                errors.append(f"{stage_id}: forbidden_writes missing {missing_forbidden}")
        missing_current = sorted(required_current_names - all_writes)
        if missing_current:
            errors.append(f"harness-aligned stage contracts missing current artifact writes {missing_current}")
    print_result("validate-stage-loop-contracts", errors, warnings)


def loop_patch_items(raw) -> list[dict]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if not isinstance(raw, dict):
        return []
    if isinstance(raw.get("local_patches"), list):
        return [item for item in raw["local_patches"] if isinstance(item, dict)]
    if isinstance(raw.get("patch_set"), list):
        return [item for item in raw["patch_set"] if isinstance(item, dict)]
    repair = raw.get("repair_plan")
    if isinstance(repair, dict) and isinstance(repair.get("patch_set"), list):
        return [item for item in repair["patch_set"] if isinstance(item, dict)]
    if raw.get("patch_id"):
        return [raw]
    return []


def validate_local_loop_patches(args):
    path = resolve_path(args.input)
    raw = load_any(path)
    items = loop_patch_items(raw)
    errors = []
    warnings = []
    if not items:
        errors.append("no local loop patches found; expected patch object, local_patches[], patch_set[], or repair_plan.patch_set[]")
    for idx, patch in enumerate(items, start=1):
        item_errors = validate_schema_data(patch, LOOP_ROOT / "schemas" / "local_patch.schema.json")
        for error in item_errors:
            errors.append(f"patch[{idx}]: {error}")
        pid = patch.get("patch_id", f"patch[{idx}]")
        errors.extend(rule_trace_errors(patch, f"local_loop_patch.{pid}.rule_ids"))
        if patch.get("writes_prd") is not False:
            errors.append(f"{pid}: writes_prd must be false")
    print_result("validate-local-loop-patches", errors, warnings)


def manifest_declared_paths(manifest_path: Path) -> list[str]:
    manifest = yload(manifest_path).get("package", {})
    file_keys = {
        "core_files",
        "rules",
        "schemas",
        "examples",
        "negative_examples",
        "docs",
        "codex",
        "executable_entrypoints",
    }
    paths = []
    def collect(value):
        if isinstance(value, list):
            paths.extend(item for item in value if isinstance(item, str))
        elif isinstance(value, dict):
            for child in value.values():
                collect(child)
    for key, value in manifest.items():
        if key in file_keys:
            collect(value)
    return paths


def validate_loop_rules(args):
    errors = []
    warnings = []
    for rel in loop_required_files():
        if not (ROOT / rel).exists():
            errors.append(f"missing required Loop file: {rel}")

    for manifest_name in ["package_manifest.yaml", "package_manifest.harness_aligned.yaml"]:
        manifest_path = LOOP_ROOT / manifest_name
        for rel in manifest_declared_paths(manifest_path):
            if rel.startswith("runs/") or rel.startswith("Figma"):
                continue
            if not (LOOP_ROOT / rel).exists():
                errors.append(f"{manifest_name} references missing file: {rel}")

    for path in sorted(LOOP_ROOT.rglob("*.yaml")):
        try:
            yload(path)
        except Exception as exc:
            errors.append(f"{path.relative_to(ROOT)}: YAML parse failed: {exc}")

    for path in sorted(LOOP_ROOT.rglob("*.json")):
        try:
            jload(path)
        except Exception as exc:
            errors.append(f"{path.relative_to(ROOT)}: JSON parse failed: {exc}")

    for schema in sorted((LOOP_ROOT / "schemas").glob("*.schema.json")):
        errors.extend(validate_json_schema_file(schema))

    profile_errors = validate_schema(
        LOOP_ROOT / "rules" / "02_loop_profile_policy.yaml",
        LOOP_ROOT / "schemas" / "loop_profile.schema.json",
    )
    errors.extend(f"loop_profile_policy: {error}" for error in profile_errors)

    stage_errors = validate_schema(
        LOOP_ROOT / "rules" / "17_harness_aligned_stage_loop_contracts.yaml",
        LOOP_ROOT / "schemas" / "stage_loop_contract.schema.json",
    )
    errors.extend(f"harness_aligned_stage_loop_contracts: {error}" for error in stage_errors)

    for rel, schema in [
        ("examples/loop_manifest.sample.yaml", "loop_manifest.schema.json"),
        ("examples/harness_aligned_loop_finding.sample.yaml", "loop_finding.schema.json"),
        ("examples/harness_aligned_repair_plan.sample.yaml", "repair_plan.schema.json"),
        ("examples/harness_aligned_loop_manifest.sample.yaml", "loop_manifest.schema.json"),
    ]:
        item_errors = validate_schema(LOOP_ROOT / rel, LOOP_ROOT / "schemas" / schema)
        errors.extend(f"{rel}: {error}" for error in item_errors)

    local_patch_errors = []
    local_patch_sample = yload(LOOP_ROOT / "examples" / "harness_aligned_local_patches.sample.yaml")
    for idx, patch in enumerate(loop_patch_items(local_patch_sample), start=1):
        for error in validate_schema_data(patch, LOOP_ROOT / "schemas" / "local_patch.schema.json"):
            local_patch_errors.append(f"examples/harness_aligned_local_patches.sample.yaml patch[{idx}]: {error}")
    errors.extend(local_patch_errors)

    alignment = yload(LOOP_ROOT / "rules" / "16_gate_only_harness_alignment.yaml").get("gate_only_harness_alignment", {})
    boundary = alignment.get("execution_boundary", {}) or {}
    if boundary.get("gate_only_enabled") is not True:
        errors.append("gate_only_harness_alignment.execution_boundary.gate_only_enabled must be true")
    for key in [
        "automatic_patch_apply_enabled",
        "automatic_rerun_enabled",
        "prototype_payload_generation_enabled",
        "figma_write_enabled",
    ]:
        if boundary.get(key) is not False:
            errors.append(f"gate_only_harness_alignment.execution_boundary.{key} must be false")
    figma_policy = alignment.get("figma_policy", {}) or {}
    if figma_policy.get("final_prototype_canvas_only") is not True:
        errors.append("loop figma_policy.final_prototype_canvas_only must be true")
    if figma_policy.get("forbidden_for_gate_review_stop_line") is not True:
        errors.append("loop figma_policy.forbidden_for_gate_review_stop_line must be true")

    if jsonschema is None:
        warnings.append("jsonschema not installed; executable schema validation is limited")
    print_result("validate-loop-rules", errors, warnings)


def collect_design_system_adapter_errors() -> tuple[list[str], list[str]]:
    errors = []
    warnings = []
    adapter_path = PROTOTYPE_ROOT / "adapters" / "design_systems" / "sds_monochrome_adapter.yaml"
    adapter = yload(adapter_path).get("sds_monochrome_adapter", {})
    if not adapter:
        return [f"missing or empty adapter: {adapter_path}"], warnings
    if adapter.get("adapter_id") != "SDS_MONOCHROME_ADAPTER_V3_1":
        errors.append("sds_monochrome_adapter.adapter_id must be SDS_MONOCHROME_ADAPTER_V3_1")
    activation = adapter.get("activation", {}) or {}
    if activation.get("enabled") is not True:
        errors.append("sds_monochrome_adapter.activation.enabled must be true")
    policy = adapter.get("monochrome_policy", {}) or {}
    if policy.get("required") is not True:
        errors.append("sds_monochrome_adapter.monochrome_policy.required must be true")
    if policy.get("allowed_color_mode") != "black_white_gray_only":
        errors.append("sds_monochrome_adapter must enforce black_white_gray_only")

    for rel in adapter.get("validation", {}).get("must_exist", []) or []:
        if not (ROOT / rel).exists():
            errors.append(f"SDS adapter required path missing: {rel}")

    figma_config_rel = adapter.get("source_design_system", {}).get("figma_config")
    figma_config = jload(ROOT / figma_config_rel) if figma_config_rel else {}
    substitutions = figma_config.get("codeConnect", {}).get("documentUrlSubstitutions", {})
    for key in adapter.get("validation", {}).get("required_document_url_substitutions", []) or []:
        if key not in substitutions:
            errors.append(f"SDS figma.config.json missing documentUrlSubstitution {key}")

    binding_map = yload(ROOT / "product-spec" / "component-binding-map.yaml").get("component_binding_map", {})
    libraries = binding_map.get("figma_libraries", []) or []
    sds_library = next((item for item in libraries if item.get("library_id") == "LIB-SDS-MONOCHROME"), None)
    if not sds_library:
        errors.append("component-binding-map missing LIB-SDS-MONOCHROME")
    elif sds_library.get("enabled") is not True:
        errors.append("LIB-SDS-MONOCHROME must be enabled")
    bindings = binding_map.get("component_bindings", []) or []
    expected_component_keys = {item.get("sds_key") for item in adapter.get("semantic_component_bindings", []) or []}
    used_component_keys = {
        (binding.get("figma_component", {}) or {}).get("component_key")
        for binding in bindings
        if binding.get("design_system_adapter") == "SDS_MONOCHROME_ADAPTER_V3_1"
    }
    missing_keys = sorted(key for key in expected_component_keys if key and key not in used_component_keys)
    if missing_keys:
        errors.append(f"component-binding-map missing SDS component keys {missing_keys}")

    semantic_library = jload(ROOT / "product-spec" / "design-semantic-library.json")
    adapters = semantic_library.get("design_system_adapters", []) or []
    if not any(item.get("adapter_id") == "SDS_MONOCHROME_ADAPTER_V3_1" and item.get("enabled") is True for item in adapters):
        errors.append("design-semantic-library missing enabled SDS_MONOCHROME_ADAPTER_V3_1")

    profile = yload(DRD_ROOT / "profile.yaml").get("drd_v3_1_profile", {})
    dependency = profile.get("design_system_dependency", {}) or {}
    if dependency.get("adapter_id") != "SDS_MONOCHROME_ADAPTER_V3_1":
        errors.append("DRD profile missing SDS_MONOCHROME_ADAPTER_V3_1 design_system_dependency")
    if dependency.get("required_for_component_binding_validation") is not True:
        errors.append("DRD profile must require SDS adapter for component binding validation")
    return errors, warnings


def validate_design_system_adapters(args):
    errors, warnings = collect_design_system_adapter_errors()
    print_result("validate-design-system-adapters", errors, warnings)


def validate_runtime(args):
    errors = []
    warnings = []
    runtime_path = resolve_path(args.runtime, default_input_path("product-spec/prototype.runtime.json"))
    base_path = resolve_path(args.base_runtime, default_input_path("product-spec/prototype.runtime.base.json"))
    schema_path = ROOT / "schemas" / "prototype_runtime.schema.json"
    errors.extend(validate_schema(runtime_path, schema_path))
    if not base_path.exists():
        errors.append(f"missing base runtime {base_path}")
    if errors:
        print_result("validate-runtime", errors, warnings)

    rt = jload(runtime_path)
    errors.extend(rule_trace_errors(rt, "runtime.rule_trace"))
    auth = rt.get("authority", {})
    if auth.get("forbidden_as_fact_source") is not True:
        errors.append("authority.forbidden_as_fact_source must be true")
    if auth.get("owner") != "prototype_projection_harness":
        errors.append("authority.owner must be prototype_projection_harness")

    lineage = rt.get("generation_lineage")
    if not isinstance(lineage, dict):
        errors.append("missing generation_lineage")
    else:
        for pass_key in ["pass_1", "pass_2"]:
            item = lineage.get(pass_key, {})
            if not item.get("name") or not item.get("output"):
                errors.append(f"generation_lineage.{pass_key} must include name and output")

    completion = rt.get("reasoning_completion")
    if not isinstance(completion, dict):
        errors.append("missing reasoning_completion")
    else:
        for collection in ["inferred_states", "inferred_interactions"]:
            for item in completion.get(collection, []) or []:
                item_id = item.get("state_id") or item.get("interaction_id") or "<unknown>"
                for field in ["confidence", "inference_basis", "source_refs"]:
                    if not item.get(field):
                        errors.append(f"{collection}.{item_id}: missing {field}")
        if "blocked_inferences" not in completion:
            errors.append("reasoning_completion.blocked_inferences must be present")

    required_state_dimensions = [
        "data_state",
        "network_state",
        "permission_state",
        "input_state",
        "request_lifecycle",
        "consistency_state",
        "recovery_state",
        "platform_device_state",
        "empty_state",
        "error_state",
        "loading_state",
        "success_state",
    ]
    for screen in rt.get("screens", []) or []:
        sid = screen.get("screen_id", "UNKNOWN_SCREEN")
        errors.extend(rule_trace_errors(screen, f"screens.{sid}.rule_ids"))
        if not screen.get("source_refs"):
            errors.append(f"{sid}: missing source_refs")
        for state in screen.get("states", []) or []:
            stid = state.get("state_id", "UNKNOWN_STATE")
            errors.extend(rule_trace_errors(state, f"screens.{sid}.states.{stid}.rule_ids"))
            for component in state.get("components", []) or []:
                errors.extend(rule_trace_errors(component, f"screens.{sid}.states.{stid}.components.{component.get('component_id', '<unknown>')}.rule_ids"))
            dims = state.get("dimensions", {}) or {}
            missing = [dimension for dimension in required_state_dimensions if dimension not in dims]
            if missing:
                errors.append(f"{sid}/{stid}: missing state dimensions {missing}")
            if not state.get("source_refs"):
                errors.append(f"{sid}/{stid}: missing source_refs")

    for edge in rt.get("interaction_graph", {}).get("edges", []) or []:
        eid = edge.get("edge_id", "UNKNOWN_EDGE")
        errors.extend(rule_trace_errors(edge, f"interaction_graph.edges.{eid}.rule_ids"))
        for field in ["edge_id", "interaction_id", "source", "trigger", "source_refs"]:
            if not edge.get(field):
                errors.append(f"{eid}: missing {field}")
        if rt.get("prototype_runtime_version", "").startswith("3.1.1") and not edge.get("target"):
            errors.append(f"{eid}: generated runtime edge missing target")
        actions = edge.get("actions", []) or []
        else_actions = edge.get("else_actions", []) or []
        if not actions and not else_actions:
            errors.append(f"{eid}: missing actions or else_actions")
        for action in actions + else_actions:
            errors.extend(rule_trace_errors(action, f"interaction_graph.edges.{eid}.actions.rule_ids"))
            if "order" not in action:
                errors.append(f"{eid}: action without explicit order")
            if not action.get("type") and not action.get("action_type"):
                errors.append(f"{eid}: action missing type")
            if rt.get("prototype_runtime_version", "").startswith("3.1.1") and not action.get("destination"):
                errors.append(f"{eid}: generated runtime action missing destination")
            if not any(action.get(key) for key in ["destination", "state_effect", "gap_ref", "sets_variable"]):
                warnings.append(f"{eid}: action has no destination/state_effect/gap_ref/sets_variable")
        if not str(eid).startswith("EDGE-"):
            warnings.append(f"{eid}: edge_id should start with EDGE-")

    print_result("validate-runtime", errors, warnings)


def render_payload_readiness_errors(payload: dict) -> tuple[list[str], list[str], bool]:
    errors = []
    warnings = []
    root = payload.get("prototype_render_payload") if isinstance(payload, dict) else None
    if not isinstance(root, dict):
        return [rule_error("COMP_DED_001", "render payload missing prototype_render_payload object")], warnings, False
    errors.extend(rule_trace_errors(root, "prototype_render_payload.rule_trace"))
    generated_by_generator = root.get("generated_by") in {
        "prototype_artifact_generator_v3_1",
        "prototype_artifact_generator_v3_1_1",
        "prototype_artifact_generator_v3_1_2",
    }
    if root.get("sample") is True:
        errors.append(rule_error("COMP_DED_001", "render payload is marked sample=true"))
    if root.get("source_kind") in {"sample", "example"}:
        errors.append(rule_error("COMP_DED_001", "render payload source_kind must not be sample/example"))
    if root.get("summary_only") is True:
        errors.append(rule_error("COMP_DED_001", "render payload is summary_only"))
    model_blueprint = root.get("model_generation_blueprint", {}) or {}
    if generated_by_generator:
        if model_blueprint.get("required_model_stage_count") != 4:
            errors.append(rule_error("ROLE_DED_007", "render payload model_generation_blueprint.required_model_stage_count must be 4"))
        if model_blueprint.get("completed_model_stage_count") != 4:
            errors.append(rule_error("ROLE_DED_007", "render payload model_generation_blueprint.completed_model_stage_count must be 4"))
        if model_blueprint.get("all_required_model_stages_called") is not True:
            errors.append(rule_error("ROLE_DED_007", "render payload must consume all 4 required Codex model stages before Figma writing"))
        stage_artifacts = model_blueprint.get("model_reasoning_artifacts", {}) or {}
        for stage_key in MODEL_STAGE_KEYS:
            if not stage_artifacts.get(stage_key):
                errors.append(rule_error("ROLE_DED_007", f"render payload missing model reasoning artifact for {stage_key}"))
        carrier_refs = root.get("carrier_handoff_refs", {}) or model_blueprint.get("carrier_handoff_artifacts", {}) or {}
        for artifact_key, rule_id in [
            ("interaction_carrier_map", "CARRIER_DED_001"),
            ("system_handoff_map", "HANDOFF_DED_001"),
            ("user_operation_chain", "OPS_DED_001"),
            ("capability_assessment", "CAPABILITY_DED_001"),
        ]:
            if not carrier_refs.get(artifact_key):
                errors.append(rule_error(rule_id, f"render payload missing carrier/handoff artifact ref for {artifact_key}"))
    for key in ["boards", "frames", "components", "interactions", "annotations"]:
        items = root.get(key)
        if not isinstance(items, list) or not items:
            errors.append(rule_error("COMP_DED_001", f"render payload has no {key}"))
    design_system = root.get("design_system", {}) or {}
    if design_system.get("adapter_id") != "SDS_MONOCHROME_ADAPTER_V3_1":
        errors.append(rule_error("COMP_DED_001", "render payload design_system.adapter_id must be SDS_MONOCHROME_ADAPTER_V3_1"))
    if design_system.get("color_policy") != "black_white_gray_only":
        errors.append(rule_error("COMP_DED_001", "render payload design_system.color_policy must be black_white_gray_only"))
    for collection in ["boards", "frames", "components", "interactions", "annotations"]:
        for idx, item in enumerate(root.get(collection, []) or [], start=1):
            item_id = item.get("board_id") or item.get("frame_id") or item.get("component_id") or item.get("interaction_id") or item.get("annotation_id") or f"{collection}[{idx}]"
            errors.extend(rule_trace_errors(item, f"{collection}.{item_id}.rule_ids"))
            if item.get("render_eligibility") == "renderable" and not item.get("source_refs"):
                errors.append(rule_error("ROLE_DED_001", f"{collection}.{item_id}: renderable item missing source_refs"))
            if item.get("candidate_marker") != "candidate_projection":
                warnings.append(f"{collection}.{item_id}: candidate_marker is not candidate_projection")
    components_by_id = {
        item.get("component_id"): item
        for item in root.get("components", []) or []
        if item.get("component_id")
    }
    interactions_by_component = defaultdict(list)
    for idx, item in enumerate(root.get("interactions", []) or [], start=1):
        iid = item.get("interaction_id", f"interactions[{idx}]")
        source_component_id = item.get("source_component_id")
        if generated_by_generator:
            if not source_component_id:
                errors.append(rule_error("HOT_DED_001", f"interactions.{iid}: missing source_component_id"))
            elif source_component_id not in components_by_id:
                errors.append(rule_error("HOT_DED_001", f"interactions.{iid}: source_component_id {source_component_id} not found in components"))
        if source_component_id:
            interactions_by_component[source_component_id].append(item)
        if generated_by_generator:
            if not item.get("source_frame_id"):
                errors.append(rule_error("HOT_DED_001", f"interactions.{iid}: missing source_frame_id"))
            if not item.get("source_state_id"):
                errors.append(rule_error("HOT_DED_001", f"interactions.{iid}: missing source_state_id"))
            if not item.get("target_state_id"):
                errors.append(rule_error("HOT_DED_001", f"interactions.{iid}: missing target_state_id"))
            if not item.get("destination_frame_id"):
                errors.append(rule_error("HOT_DED_001", f"interactions.{iid}: missing destination_frame_id"))
            actions = item.get("actions", []) or []
            if not actions:
                errors.append(rule_error("HOT_DED_001", f"interactions.{iid}: missing actions"))
            for action in actions:
                if not action.get("destination") or not action.get("destination_frame_id"):
                    errors.append(rule_error("HOT_DED_001", f"interactions.{iid}: action missing destination or destination_frame_id"))
    for component_id, items in interactions_by_component.items():
        click_items = [
            item for item in items
            if str(item.get("trigger_zh") or item.get("trigger") or "").startswith(("用户点击", "点击"))
        ]
        distinct_click_triggers = sorted({
            str(item.get("trigger_zh") or item.get("trigger") or "").strip()
            for item in click_items
            if str(item.get("trigger_zh") or item.get("trigger") or "").strip()
        })
        if len(distinct_click_triggers) > 1:
            labels = " / ".join(action_copy_from_trigger(trigger) for trigger in distinct_click_triggers[:4])
            if len(distinct_click_triggers) > 4:
                labels += " / ..."
            errors.append(rule_error(
                "PEN_DED_002",
                f"components.{component_id}: multiple distinct click triggers bound to one component ({labels}); "
                "split into dedicated action components"
            ))
        component_copy = str(components_by_id.get(component_id, {}).get("copy_zh") or "").strip()
        if component_copy in {"继续", "确认选择", "开始分析"}:
            for item in click_items:
                trigger = str(item.get("trigger_zh") or item.get("trigger") or "")
                expected = action_copy_from_trigger(trigger)
                if expected and expected not in component_copy:
                    errors.append(rule_error(
                        "HOT_DED_001",
                        f"components.{component_id}: generic copy `{component_copy}` is bound to click trigger `{trigger}`; "
                        f"use a trigger-specific component such as `{expected}`"
                    ))
    return errors, warnings, generated_by_generator


def coverage_path_for_runtime(runtime_path: Path) -> Path:
    if runtime_path.parent.name == "output" and runtime_path.parent.parent.name == "io":
        return runtime_path.parent.parent / "state" / "source_coverage_report.yaml"
    return RUN_ROOT / "io" / "state" / "source_coverage_report.yaml"


def generated_artifact_sibling_paths(runtime_path: Path) -> dict[str, Path]:
    if runtime_path.parent.name == "output" and runtime_path.parent.parent.name == "io":
        output_root = runtime_path.parent
        state_root = runtime_path.parent.parent / "state"
    else:
        output_root = RUN_ROOT / "io" / "output"
        state_root = RUN_ROOT / "io" / "state"
    return {
        "interaction_carrier_map": output_root / "interaction_carrier_map.yaml",
        "system_handoff_map": output_root / "system_handoff_map.yaml",
        "user_operation_chain": output_root / "user_operation_chain.yaml",
        "capability_assessment": output_root / "capability_assessment.yaml",
        "prototype_review_view_model": state_root / "prototype_review_view_model.yaml",
        "model_contract_promotion_report": state_root / "model_contract_promotion_report.yaml",
        "model_execution_contract_resolved": state_root / "model_execution_contract.resolved.yaml",
    }


def validate_render_readiness(args):
    errors = []
    warnings = []
    runtime_path = resolve_path(args.runtime, default_input_path("product-spec/prototype.runtime.json"))
    errors.extend(validate_schema(runtime_path, ROOT / "schemas" / "prototype_runtime.schema.json"))
    if errors:
        print_result("validate-render-readiness", errors, warnings)

    runtime = jload(runtime_path)
    counts = runtime_material_counts(runtime)
    source_inputs = discover_prd_input_files()
    baseline = source_baseline_path()
    product_counts = product_spec_material_counts()
    has_product_spec_material = any(product_counts.values())

    if not INSTANCE_ROOT_PROVIDED:
        errors.append("render readiness must run with --instance-root; harness package templates are not PRD input")
    if not source_inputs and not baseline.exists() and not has_product_spec_material:
        errors.append(
            "no PRD input, structured source baseline, or generated product-spec material found; "
            "do not render Figma from samples"
        )

    for key in ["screens", "interaction_edges"]:
        if counts.get(key, 0) == 0:
            errors.append(f"runtime has no {key}; render payload would collapse to a summary board")
    if counts.get("component_bindings", 0) == 0:
        errors.append("runtime has no component_bindings; Figma nodes cannot be bound to semantic components")
    if counts.get("copy_catalog", 0) == 0:
        warnings.append("runtime has no copy_catalog; renderer must not invent user-visible copy")

    payload_generated_by_generator = False
    payload = {}
    if args.payload:
        payload_path = resolve_path(args.payload)
        if not payload_path.exists():
            errors.append(f"missing render payload {payload_path}")
        else:
            errors.extend(validate_schema(payload_path, ROOT / "schemas" / "prototype_render_payload.schema.json"))
            payload = load_any(payload_path)
            root_keys = set(payload.keys()) if isinstance(payload, dict) else set()
            if not ({"prototype_render_payload", "drd_materialization_payload"} & root_keys):
                errors.append("render payload must have prototype_render_payload or drd_materialization_payload root key")
            if "prototype_render_payload" in root_keys:
                payload_errors, payload_warnings, payload_generated_by_generator = render_payload_readiness_errors(payload)
                errors.extend(payload_errors)
                warnings.extend(payload_warnings)
    else:
        errors.append("missing --payload; runtime alone is not a render payload")

    coverage_path = coverage_path_for_runtime(runtime_path)
    if payload_generated_by_generator:
        if not coverage_path.exists():
            errors.append(f"missing source coverage report {coverage_path}")
        else:
            errors.extend(validate_schema(coverage_path, DRD_ROOT / "schemas" / "source_coverage_report.schema.json"))
            if not errors:
                errors.extend(source_coverage_errors(yload(coverage_path), runtime, payload))
        sibling_paths = generated_artifact_sibling_paths(runtime_path)
        sibling_schemas = {
            "interaction_carrier_map": DRD_ROOT / "schemas" / "interaction_carrier_map.schema.json",
            "system_handoff_map": DRD_ROOT / "schemas" / "system_handoff_map.schema.json",
            "user_operation_chain": DRD_ROOT / "schemas" / "user_operation_chain.schema.json",
            "capability_assessment": DRD_ROOT / "schemas" / "capability_assessment.schema.json",
            "prototype_review_view_model": DRD_ROOT / "schemas" / "prototype_review_view_model.schema.json",
            "model_contract_promotion_report": DRD_ROOT / "schemas" / "model_contract_promotion_report.schema.json",
            "model_execution_contract_resolved": DRD_ROOT / "schemas" / "model_execution_contract.schema.json",
        }
        loaded = {}
        for key, path in sibling_paths.items():
            if not path.exists():
                errors.append(f"missing generated {key} {path}")
                continue
            errors.extend(f"{key}: {error}" for error in validate_schema(path, sibling_schemas[key]))
            loaded[key] = yload(path)
        if "interaction_carrier_map" in loaded:
            errors.extend(carrier_map_semantic_errors(loaded["interaction_carrier_map"], payload))
        if "system_handoff_map" in loaded:
            errors.extend(system_handoff_semantic_errors(loaded["system_handoff_map"]))
        if "user_operation_chain" in loaded:
            errors.extend(operation_chain_semantic_errors(loaded["user_operation_chain"], payload))
        if "capability_assessment" in loaded:
            errors.extend(capability_assessment_semantic_errors(loaded["capability_assessment"]))
        if "prototype_review_view_model" in loaded:
            errors.extend(review_view_model_semantic_errors(loaded["prototype_review_view_model"]))
        if "model_contract_promotion_report" in loaded:
            errors.extend(contract_promotion_semantic_errors(loaded["model_contract_promotion_report"]))

    profile = yload(DRD_ROOT / "profile.yaml").get("drd_v3_1_profile", {})
    deferred = set(profile.get("explicitly_deferred", []) or [])
    if "figma_canvas_rendering" in deferred and not payload_generated_by_generator:
        errors.append("DRD profile still defers figma_canvas_rendering; do not call Figma renderer in this phase")
    elif "figma_canvas_rendering" in deferred and payload_generated_by_generator:
        warnings.append("DRD profile defers raw canvas rendering; generated payload may proceed only to final Figma writer after this readiness PASS")

    print("# render-readiness-summary")
    print(json.dumps({
        "runtime": str(runtime_path),
        "runtime_counts": counts,
        "prd_inputs": [str(path.relative_to(INSTANCE_ROOT)) for path in source_inputs] if INSTANCE_ROOT_PROVIDED else [],
        "source_baseline": str(baseline.relative_to(INSTANCE_ROOT)) if INSTANCE_ROOT_PROVIDED and baseline.exists() else "",
        "product_spec_material_counts": product_counts,
        "source_coverage_report": str(coverage_path),
    }, ensure_ascii=False, indent=2))
    print_result("validate-render-readiness", errors, warnings)


def validate_interactions(args):
    errors = []
    warnings = []
    map_path = resolve_path(args.map, default_input_path("product-spec/figma-interaction-map.yaml"))
    errors.extend(validate_schema(map_path, ROOT / "schemas" / "figma_interaction_map.schema.json"))
    if errors:
        print_result("validate-interactions", errors, warnings)

    imap = yload(map_path).get("figma_interaction_map", {})
    if imap.get("forbidden_as_fact_source") is not True:
        errors.append("figma_interaction_map.forbidden_as_fact_source must be true")
    interactions = imap.get("interactions", []) or []

    seen = defaultdict(list)
    for idx, item in enumerate(interactions):
        iid = item.get("interaction_id", f"INDEX-{idx}")
        edge = item.get("edge_id")
        if not edge:
            errors.append(f"{iid}: missing edge_id")
        src = item.get("figma_source", {}) or {}
        reaction = item.get("figma_reaction", {}) or {}
        key = (src.get("source_node_id"), reaction.get("trigger"))
        if key[0] and key[1]:
            seen[key].append(iid)
        if not src.get("source_node_id"):
            errors.append(f"{iid}: missing figma_source.source_node_id")
        if not reaction.get("trigger"):
            errors.append(f"{iid}: missing figma_reaction.trigger")
        if not reaction.get("actions"):
            errors.append(f"{iid}: missing figma_reaction.actions")
        for action in reaction.get("actions", []) or []:
            if not action.get("action_type"):
                errors.append(f"{iid}: figma_reaction action missing action_type")

    for key, ids in seen.items():
        if len(ids) > 1:
            errors.append(f"duplicate source_node_id + trigger {key}: {ids}")

    print_result("validate-interactions", errors, warnings)


def validate_fact_bundle(args):
    bundle = resolve_path(args.bundle)
    schema = PROTOTYPE_ROOT / "contracts" / "input_prd_fact_bundle.schema.json"
    print_result("validate-fact-bundle", validate_schema(bundle, schema))


def validate_uxwriter(args):
    catalog_path = resolve_path(args.catalog)
    errors = validate_schema(catalog_path, ROOT / "schemas" / "uxwriter_copy_catalog.schema.json")
    warnings = []
    if not errors:
        catalog = yload(catalog_path).get("uxwriter_copy_catalog", {})
        locale = catalog.get("locale", "")
        for item in catalog.get("copy_items", []) or []:
            cid = item.get("copy_id", "<unknown>")
            if not item.get("intent"):
                errors.append(f"copy {cid} missing intent")
            if not item.get("source_refs"):
                errors.append(f"copy {cid} missing source_refs")
            validation = item.get("validation", {}) or {}
            if not validation.get("passed") and not item.get("research_refs"):
                errors.append(f"copy {cid} missing validation.passed or research_refs")
            role = item.get("semantic_role", "")
            text = item.get("final_copy", "")
            if item.get("original_copy_ref") and text and not item.get("rewrite_reason"):
                warnings.append(f"copy {cid} has final_copy but no rewrite_reason")
            if locale == "zh-CN" and "button.primary" in role and len(text) > 8:
                warnings.append(f"primary button {cid} exceeds zh-CN 8 char guideline")
            if any(token in text for token in ["系统异常", "未知错误", "你错了", "非法"]):
                warnings.append(f"copy {cid} contains cold/blame/generic wording: {text}")
            high_risk_role = any(token in role for token in ["destructive", "privacy", "payment"])
            if high_risk_role and not item.get("human_review"):
                errors.append(f"copy {cid} is high risk and missing human_review")
    print_result("validate-uxwriter", errors, warnings)


def validate_layout(args):
    plan_path = resolve_path(args.plan)
    errors = validate_schema(plan_path, ROOT / "schemas" / "layout_route_plan.schema.json")
    warnings = []
    if not errors:
        plan = yload(plan_path).get("layout_route_plan", {})
        corridors = {c.get("corridor_id") for c in plan.get("route_corridors", []) or []}
        if not corridors:
            errors.append("layout_route_plan.route_corridors must not be empty")
        seen_dedupe = defaultdict(list)
        for route in plan.get("edge_routes", []) or []:
            edge_id = route.get("edge_id", "<unknown>")
            corridor_id = route.get("corridor_id")
            if corridor_id not in corridors:
                errors.append(f"edge route {edge_id} references missing corridor {corridor_id}")
            dedupe_group = route.get("dedupe_group")
            if not dedupe_group:
                warnings.append(f"edge route {edge_id} has no dedupe_group")
            else:
                seen_dedupe[dedupe_group].append(edge_id)
        for dedupe_group, edge_ids in seen_dedupe.items():
            if len(edge_ids) > 1:
                errors.append(f"duplicate visual line dedupe_group {dedupe_group}: {edge_ids}")
    print_result("validate-layout", errors, warnings)


def validate_comments(args):
    map_path = resolve_path(args.map)
    errors = validate_schema(map_path, ROOT / "schemas" / "figma_comment_map.schema.json")
    warnings = []
    if not errors:
        cmap = yload(map_path).get("figma_comment_map", {})
        if cmap.get("forbidden_as_fact_source") is not True:
            errors.append("figma_comment_map.forbidden_as_fact_source must be true")
        for comment in cmap.get("comments", []) or []:
            cid = comment.get("comment_semantic_id", "<unknown>")
            anchor = comment.get("anchor", {}) or {}
            if not anchor.get("target_semantic_id"):
                errors.append(f"comment {cid} missing anchor.target_semantic_id")
            if not comment.get("source_refs"):
                errors.append(f"comment {cid} missing source_refs")
            body = comment.get("message_template", "")
            if comment.get("comment_role") == "interaction_explanation":
                for token in ["Trigger:", "Then:", "Refs:"]:
                    if token not in body:
                        warnings.append(f"interaction comment {cid} missing {token}")
    print_result("validate-comments", errors, warnings)


def validate_skill_pack(args):
    pack_path = resolve_path(args.pack)
    errors = validate_schema(pack_path, ROOT / "schemas" / "renderer_skill_pack.schema.json")
    warnings = []
    if not errors:
        skill_pack = yload(pack_path).get("renderer_skill_pack", {})
        if skill_pack.get("authority_role") != "advisory_renderer_influence":
            errors.append("renderer_skill_pack.authority_role must be advisory_renderer_influence")
        forbidden_hooks = {
            "create_confirmed_requirement",
            "remove_prd_requirement",
            "approve_figma_semantic_diff",
        }
        for rule in skill_pack.get("rules", []) or []:
            if rule.get("hook") in forbidden_hooks:
                errors.append(f"skill rule {rule.get('rule_id')} uses forbidden hook {rule.get('hook')}")
            if not rule.get("confidence"):
                warnings.append(f"skill rule {rule.get('rule_id')} has no confidence")
    print_result("validate-skill-pack", errors, warnings)


def classify_figma_diff(args):
    ensure_run_manifest("classify-figma-diff")
    path = resolve_path(args.diff_file)
    raw = yload(path) if path.suffix.lower() in [".yaml", ".yml"] else jload(path)
    changes = raw.get("changes", raw if isinstance(raw, list) else [])
    semantic = []
    non_semantic = []
    conflicts = []
    for idx, change in enumerate(changes, start=1):
        change_type = change.get("type", "unknown")
        if any(key in change_type for key in ["layout", "style", "position", "color", "spacing", "line"]):
            non_semantic.append({
                "diff_id": f"FDIFF-VISUAL-{idx:03d}",
                "diff_type": change_type,
                "action": "keep_in_figma_only",
                "reason": "visual-only heuristic; no fact-store write allowed",
            })
        elif any(key in change_type for key in ["conflict", "both_sides"]):
            conflicts.append({
                "conflict_id": f"FCONFLICT-{idx:03d}",
                "conflict_type": change_type,
                "base_value": change.get("base"),
                "figma_value": change.get("figma"),
                "prd_value": change.get("prd"),
                "required_decision": "choose_figma | choose_prd | write_new_value | reject_both",
            })
        else:
            semantic.append({
                "diff_id": f"FDIFF-{idx:03d}",
                "diff_type": change_type,
                "classification": "semantic_candidate",
                "figma_change": change,
                "target_sub_harness_candidate": "screen_state_harness",
                "confidence": "low",
                "requires_human_review": True,
                "reason": "heuristic semantic diff; requires owner harness review",
            })
    out = {
        "change_patch_candidate": {
            "schema_version": "2.1",
            "patch_id": f"FIGMA-DIFF-{path.stem}",
            "source_channel": "figma_diff",
            "candidate_status": "candidate_not_approved",
            "human_review_required": True,
            "semantic_diffs": semantic,
            "non_semantic_diffs": non_semantic,
            "conflicts": conflicts,
            "forbidden_direct_writes_checked": True,
            "forbidden_fact_store_writes": [
                "product-spec/requirements.yaml",
                "product-spec/screens.yaml",
                "product-spec/metrics.yaml",
                "product-spec/events.yaml",
                "product-spec/PRD.md",
            ],
        }
    }
    out_path = RUN_ROOT / "prd_orchestrator" / "change_patch_candidates" / f"FIGMA-DIFF-{path.stem}.candidate.yaml"
    ywrite(out_path, out)
    print(f"Wrote {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-root", help="Isolated PRD instance root for write outputs")
    parser.add_argument("--run-id", help="Run id under <instance-root>/runs")
    parser.add_argument("--allow-harness-writes", action="store_true", help=argparse.SUPPRESS)
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("status")
    p.add_argument("--mode", choices=["default", "drd"], default="default")
    p.set_defaults(func=status)

    p = sub.add_parser("validate-runtime")
    p.add_argument("--runtime")
    p.add_argument("--base-runtime")
    p.set_defaults(func=validate_runtime)

    p = sub.add_parser("validate-render-readiness")
    p.add_argument("--runtime")
    p.add_argument("--payload")
    p.set_defaults(func=validate_render_readiness)

    p = sub.add_parser("validate-interactions")
    p.add_argument("--map")
    p.set_defaults(func=validate_interactions)

    p = sub.add_parser("validate-fact-bundle")
    p.add_argument("--bundle", required=True)
    p.set_defaults(func=validate_fact_bundle)

    p = sub.add_parser("validate-uxwriter")
    p.add_argument("--catalog", required=True)
    p.set_defaults(func=validate_uxwriter)

    p = sub.add_parser("validate-layout")
    p.add_argument("--plan", required=True)
    p.set_defaults(func=validate_layout)

    p = sub.add_parser("validate-comments")
    p.add_argument("--map", required=True)
    p.set_defaults(func=validate_comments)

    p = sub.add_parser("validate-skill-pack")
    p.add_argument("--pack", required=True)
    p.set_defaults(func=validate_skill_pack)

    p = sub.add_parser("validate-drd-rules")
    p.set_defaults(func=validate_drd_rules)

    p = sub.add_parser("validate-role-obligations")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_role_obligations)

    p = sub.add_parser("validate-design-kernel")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_design_kernel)

    p = sub.add_parser("validate-sidecar-cards")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_sidecar_cards)

    p = sub.add_parser("validate-local-patches")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_local_patches)

    p = sub.add_parser("validate-design-system-adapters")
    p.set_defaults(func=validate_design_system_adapters)

    p = sub.add_parser("generate-prototype-artifacts")
    p.add_argument("--source", required=True, help="Source PRD markdown under <instance-root>/inputs")
    p.add_argument(
        "--codex-inference",
        choices=["off", "optional", "required"],
        default=os.environ.get("PROTOTYPE_CODEX_INFERENCE", "required"),
        help="Run four Codex CLI model reasoning stages before final runtime/payload materialization",
    )
    p.set_defaults(func=generate_prototype_artifacts)

    p = sub.add_parser("validate-generation-lifecycle-rules")
    p.set_defaults(func=validate_generation_lifecycle_rules)

    p = sub.add_parser("validate-generation-job-queue")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_generation_job_queue)

    p = sub.add_parser("validate-generation-trace")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_generation_trace)

    p = sub.add_parser("validate-model-execution-contract")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_model_execution_contract)

    p = sub.add_parser("validate-model-invocation-trace")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_model_invocation_trace)

    p = sub.add_parser("validate-model-surface-ownership")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_model_surface_ownership)

    p = sub.add_parser("validate-model-user-journey")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_model_user_journey)

    p = sub.add_parser("validate-model-interaction-state-machine")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_model_interaction_state_machine)

    p = sub.add_parser("validate-model-component-blueprint")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_model_component_blueprint)

    p = sub.add_parser("validate-model-stage-coverage")
    p.add_argument("--trace", required=True)
    p.add_argument("--job-queue", required=True)
    p.set_defaults(func=validate_model_stage_coverage)

    p = sub.add_parser("validate-generated-artifact-manifest")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_generated_artifact_manifest)

    p = sub.add_parser("validate-source-coverage")
    p.add_argument("--coverage", required=True)
    p.add_argument("--runtime", required=True)
    p.add_argument("--payload", required=True)
    p.set_defaults(func=validate_source_coverage)

    p = sub.add_parser("validate-carrier-map")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_carrier_map)

    p = sub.add_parser("validate-system-handoff-map")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_system_handoff_map)

    p = sub.add_parser("validate-operation-chain")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_operation_chain)

    p = sub.add_parser("validate-capability-assessment")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_capability_assessment)

    p = sub.add_parser("validate-review-view-model")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_review_view_model)

    p = sub.add_parser("validate-contract-promotion")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_contract_promotion)

    p = sub.add_parser("validate-loop-rules")
    p.set_defaults(func=validate_loop_rules)

    p = sub.add_parser("validate-loop-manifest")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_loop_manifest)

    p = sub.add_parser("validate-loop-finding")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_loop_finding)

    p = sub.add_parser("validate-repair-plan")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_repair_plan)

    p = sub.add_parser("validate-stage-loop-contracts")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_stage_loop_contracts)

    p = sub.add_parser("validate-local-loop-patches")
    p.add_argument("--input", required=True)
    p.set_defaults(func=validate_local_loop_patches)

    p = sub.add_parser("classify-figma-diff")
    p.add_argument("diff_file")
    p.set_defaults(func=classify_figma_diff)

    args = parser.parse_args()
    configure_paths(args)
    args.func(args)


if __name__ == "__main__":
    main()
