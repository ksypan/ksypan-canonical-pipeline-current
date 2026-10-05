#!/usr/bin/env python3
"""Validate field_registry.yaml against participant-output-template-50.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


ALLOWED_PRIMARY = {"deterministic_rule", "regex", "llm", "hybrid"}
REQUIRED_FIELD_KEYS = {
    "field_name",
    "field_path",
    "description",
    "data_type",
    "missing_value",
    "extraction_strategy",
    "evidence_policy",
    "needs_dataset_validation",
}


def json_pointer_get(document: Any, pointer: str) -> tuple[bool, Any]:
    """Resolve a JSON Pointer, including keys that look numeric (for example 2_aag)."""
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        return False, None
    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            return False, None
        current = current[token]
    return True, current


def validate_registry(registry_path: Path, template_path: Path) -> tuple[list[str], list[str], int, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    needs_validation: list[str] = []

    try:
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [f"YAML error: {exc}"], warnings, 0, needs_validation

    try:
        template = json.loads(template_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"JSON template error: {exc}"], warnings, 0, needs_validation

    if not isinstance(registry, dict):
        return ["Registry root must be a mapping"], warnings, 0, needs_validation
    fields = registry.get("fields")
    if not isinstance(fields, list):
        return ["fields must be a list"], warnings, 0, needs_validation

    names: set[str] = set()
    paths: set[str] = set()
    for index, field in enumerate(fields, start=1):
        prefix = f"fields[{index}]"
        if not isinstance(field, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        missing = REQUIRED_FIELD_KEYS - field.keys()
        if missing:
            errors.append(f"{prefix} missing required keys: {', '.join(sorted(missing))}")
        name = field.get("field_name")
        if name in names:
            errors.append(f"duplicate field_name: {name}")
        elif isinstance(name, str):
            names.add(name)
        else:
            errors.append(f"{prefix}.field_name must be a string")

        path = field.get("field_path")
        if path:
            if path in paths:
                errors.append(f"duplicate field_path: {path}")
            elif isinstance(path, str):
                paths.add(path)
        strategy = field.get("extraction_strategy")
        primary = strategy.get("primary") if isinstance(strategy, dict) else None
        if primary not in ALLOWED_PRIMARY:
            errors.append(f"{prefix}.extraction_strategy.primary is invalid: {primary!r}")
        evidence = field.get("evidence_policy")
        if not isinstance(evidence, dict) or evidence.get("required_when_value_found") is not True:
            errors.append(f"{prefix}.evidence_policy.required_when_value_found must be true")
        if field.get("needs_dataset_validation") is True and isinstance(name, str):
            needs_validation.append(name)
        if path is not None and path != "":
            exists, _ = json_pointer_get(template, path)
            if not exists:
                errors.append(f"{prefix}.field_path not found in template: {path}")

    actual_template_fields = sum(
        1 for section in template.values() if isinstance(section, dict) for key in section
        if key not in {"value", "evidence__test", "confidence", "source"}
    ) if isinstance(template, dict) else None
    if actual_template_fields is None:
        warnings.append("Cannot determine domain field count from template")
    elif len(fields) != actual_template_fields:
        warnings.append(
            f"Registry contains {len(fields)} fields; template contains {actual_template_fields} domain fields"
        )

    return errors, warnings, len(fields), needs_validation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=Path("field_registry.yaml"))
    parser.add_argument("--template", type=Path, default=Path("participant-output-template-50.json"))
    args = parser.parse_args()
    errors, warnings, count, needs_validation = validate_registry(args.registry, args.template)
    try:
        template = json.loads(args.template.read_text(encoding="utf-8"))
        template_count = sum(
            1 for section in template.values() if isinstance(section, dict) for key in section
            if key not in {"value", "evidence__test", "confidence", "source"}
        ) if isinstance(template, dict) else None
    except (OSError, json.JSONDecodeError):
        template_count = None
    print(f"Registry fields: {count}")
    print(f"Template domain fields: {template_count if template_count is not None else 'unknown'}")
    print("needs_dataset_validation: " + (", ".join(needs_validation) if needs_validation else "none"))
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print("Validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
