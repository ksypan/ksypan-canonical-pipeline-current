import json
from pathlib import Path

import yaml

from scripts.validate_field_registry import validate_registry


REQUIRED = {
    "field_name": "2_aag",
    "field_path": "/section/2_aag",
    "description": "test",
    "data_type": "string",
    "missing_value": "не указано",
    "extraction_strategy": {"primary": "regex"},
    "evidence_policy": {"required_when_value_found": True},
    "needs_dataset_validation": False,
}


def write_case(tmp_path: Path, field: dict) -> tuple[Path, Path]:
    registry = tmp_path / "registry.yaml"
    template = tmp_path / "template.json"
    registry.write_text(yaml.safe_dump({"fields": [field]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    template.write_text(json.dumps({"section": {"2_aag": "не указано"}}), encoding="utf-8")
    return registry, template


def test_valid_minimal_registry_and_numeric_looking_key(tmp_path):
    registry, template = write_case(tmp_path, REQUIRED)
    assert validate_registry(registry, template) == ([], [], 1, [])


def test_duplicate_field_name(tmp_path):
    registry = tmp_path / "registry.yaml"
    template = tmp_path / "template.json"
    fields = [REQUIRED, {**REQUIRED, "field_path": "/section/other"}]
    registry.write_text(yaml.safe_dump({"fields": fields}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    template.write_text(json.dumps({"section": {"2_aag": 1, "other": 1}}), encoding="utf-8")
    errors, *_ = validate_registry(registry, template)
    assert any("duplicate field_name" in error for error in errors)


def test_duplicate_field_path(tmp_path):
    registry, template = write_case(tmp_path, {**REQUIRED, "field_name": "other"})
    errors, *_ = validate_registry(registry, template)
    assert errors == []
    registry.write_text(yaml.safe_dump({"fields": [REQUIRED, {**REQUIRED, "field_name": "other"}]}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    errors, *_ = validate_registry(registry, template)
    assert any("duplicate field_path" in error for error in errors)


def test_invalid_strategy_and_missing_required_key(tmp_path):
    field = {**REQUIRED, "extraction_strategy": {"primary": "magic"}}
    del field["description"]
    registry, template = write_case(tmp_path, field)
    errors, *_ = validate_registry(registry, template)
    assert any("missing required keys" in error for error in errors)
    assert any("is invalid" in error for error in errors)


def test_missing_template_path(tmp_path):
    registry, template = write_case(tmp_path, {**REQUIRED, "field_path": "/section/missing"})
    errors, *_ = validate_registry(registry, template)
    assert any("not found in template" in error for error in errors)


def test_null_path_with_dataset_validation_is_allowed(tmp_path):
    field = {**REQUIRED, "field_path": None, "needs_dataset_validation": True}
    registry, template = write_case(tmp_path, field)
    errors, warnings, count, pending = validate_registry(registry, template)
    assert errors == []
    assert count == 1
    assert pending == ["2_aag"]
