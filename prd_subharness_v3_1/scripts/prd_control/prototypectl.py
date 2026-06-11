#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
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
HARNESS_ROOT = ROOT
INSTANCE_ROOT = ROOT
RUN_ID = "manual"
RUN_ROOT = ROOT / "runs" / RUN_ID
INSTANCE_ROOT_PROVIDED = False
ALLOW_HARNESS_WRITES = False

WRITE_COMMANDS = {
    "classify-figma-diff",
}


def configure_paths(args):
    global INSTANCE_ROOT, RUN_ID, RUN_ROOT, INSTANCE_ROOT_PROVIDED, ALLOW_HARNESS_WRITES
    INSTANCE_ROOT_PROVIDED = bool(getattr(args, "instance_root", None))
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
        "BLOCKED: classify-figma-diff writes candidates and requires --instance-root outside the harness package. "
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
                "fact_stores_are_not_written_by_prototypectl": True,
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
        "sub_harnesses/prototype_projection_harness/drd_v3_1/libs/deductive_method_library.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/libs/obligation_primitive_library.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/libs/sidecar_card_template_library.yaml",
        "sub_harnesses/prototype_projection_harness/adapters/design_systems/sds_monochrome_adapter.yaml",
        "sub_harnesses/prototype_projection_harness/adapters/design_systems/figma-sds.SOURCE.md",
        "sub_harnesses/prototype_projection_harness/adapters/design_systems/figma-sds/figma.config.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/screen_role_obligations.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/design_kernel.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/logic_sidecar_card_map.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/schemas/local_materialization_patch.schema.json",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/examples/image_upload_3_5_walkthrough.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/examples/screen_role_obligations.sample.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/examples/design_kernel.sample.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/examples/logic_sidecar_card_map.sample.yaml",
        "sub_harnesses/prototype_projection_harness/drd_v3_1/examples/local_materialization_patch.sample.yaml",
    ]


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
        ]:
            exists = command in source
            print(f"- {'OK' if exists else 'MISSING'} command:{command}")
            if not exists:
                missing.append(f"command:{command}")
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
        for item in data.get("obligations", []) or []:
            oid = item.get("obligation_id", "<unknown>")
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
        if kernel.get("mode") != "DRD_MODE":
            errors.append("design_kernel.mode must be DRD_MODE")
        if not kernel.get("forbidden_realizations"):
            errors.append("design_kernel.forbidden_realizations must not be empty")
        surface_forbidden = (kernel.get("surface_contract", {}) or {}).get("forbidden_realizations")
        if not surface_forbidden:
            errors.append("surface_contract.forbidden_realizations must not be empty")
        for constraint in kernel.get("constraint_contracts", []) or []:
            cid = constraint.get("constraint_id", "<unknown>")
            if not constraint.get("earliest_fix_surface"):
                errors.append(f"{cid}: missing earliest_fix_surface")
            if not constraint.get("feedback_timing"):
                errors.append(f"{cid}: missing feedback_timing")
    print_result("validate-design-kernel", errors, warnings)


def validate_sidecar_cards(args):
    path = resolve_path(args.input)
    errors = validate_schema(path, DRD_ROOT / "schemas" / "logic_sidecar_card_map.schema.json")
    warnings = []
    if not errors:
        card_map = yload(path).get("logic_sidecar_card_map", {})
        card_ids = {card.get("card_id") for card in card_map.get("cards", []) or []}
        for card in card_map.get("cards", []) or []:
            cid = card.get("card_id", "<unknown>")
            if not card.get("anchor_badge_id"):
                errors.append(f"{cid}: missing anchor_badge_id")
            if not card.get("source_refs"):
                errors.append(f"{cid}: missing source_refs")
        for stub in card_map.get("annotation_stubs", []) or []:
            sid = stub.get("annotation_id", "<unknown>")
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
        for patch in patch_doc.get("patches", []) or []:
            pid = patch.get("patch_id", "<unknown>")
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
        if not screen.get("source_refs"):
            errors.append(f"{sid}: missing source_refs")
        for state in screen.get("states", []) or []:
            stid = state.get("state_id", "UNKNOWN_STATE")
            dims = state.get("dimensions", {}) or {}
            missing = [dimension for dimension in required_state_dimensions if dimension not in dims]
            if missing:
                errors.append(f"{sid}/{stid}: missing state dimensions {missing}")
            if not state.get("source_refs"):
                errors.append(f"{sid}/{stid}: missing source_refs")

    for edge in rt.get("interaction_graph", {}).get("edges", []) or []:
        eid = edge.get("edge_id", "UNKNOWN_EDGE")
        for field in ["edge_id", "interaction_id", "source", "trigger", "source_refs"]:
            if not edge.get(field):
                errors.append(f"{eid}: missing {field}")
        actions = edge.get("actions", []) or []
        else_actions = edge.get("else_actions", []) or []
        if not actions and not else_actions:
            errors.append(f"{eid}: missing actions or else_actions")
        for action in actions + else_actions:
            if "order" not in action:
                errors.append(f"{eid}: action without explicit order")
            if not action.get("type") and not action.get("action_type"):
                errors.append(f"{eid}: action missing type")
            if not any(action.get(key) for key in ["destination", "state_effect", "gap_ref", "sets_variable"]):
                warnings.append(f"{eid}: action has no destination/state_effect/gap_ref/sets_variable")
        if not str(eid).startswith("EDGE-"):
            warnings.append(f"{eid}: edge_id should start with EDGE-")

    print_result("validate-runtime", errors, warnings)


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
    parser.add_argument("--run-id", default="manual", help="Run id under <instance-root>/runs")
    parser.add_argument("--allow-harness-writes", action="store_true", help=argparse.SUPPRESS)
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("status")
    p.add_argument("--mode", choices=["default", "drd"], default="default")
    p.set_defaults(func=status)

    p = sub.add_parser("validate-runtime")
    p.add_argument("--runtime")
    p.add_argument("--base-runtime")
    p.set_defaults(func=validate_runtime)

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

    p = sub.add_parser("classify-figma-diff")
    p.add_argument("diff_file")
    p.set_defaults(func=classify_figma_diff)

    args = parser.parse_args()
    configure_paths(args)
    args.func(args)


if __name__ == "__main__":
    main()
