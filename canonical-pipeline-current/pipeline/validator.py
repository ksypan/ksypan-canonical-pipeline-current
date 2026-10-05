"""Final validation and normalization of the flat 50-field result."""

from __future__ import annotations

import re
import json
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from .field_contract import FIELD_CONTRACT


DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_TEMPLATE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = next(
    (candidate for candidate in (_TEMPLATE_ROOT / "participant-output-template-v2.json", _TEMPLATE_ROOT / "participant-output-template-v2 (2).json") if candidate.exists()),
    _TEMPLATE_ROOT / "participant-output-template-v2.json",
)


def _official_fields() -> tuple[str, ...]:
    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8-sig"))
    if not isinstance(template, dict) or len(template) != 50:
        raise ValueError("Official template must contain exactly 50 fields")
    return tuple(template)


def validate_final_json(values: Mapping[str, Any]) -> dict[str, Any]:
    official_fields = _official_fields()
    if official_fields != tuple(FIELD_CONTRACT):
        raise ValueError("FIELD_CONTRACT and official template are out of sync")
    if not isinstance(values, Mapping) or tuple(values) != official_fields:
        raise ValueError(f"Final result must contain exactly {len(FIELD_CONTRACT)} official fields")
    normalized = dict(values)
    for name, value in normalized.items():
        field = FIELD_CONTRACT[name]
        if value is None:
            normalized[name] = field.get("missing_value", "не указано")
            value = normalized[name]
        kind = field.get("value_type")
        if kind == "date" and value != "не указано" and (not isinstance(value, str) or not DATE_RE.fullmatch(value)):
            raise ValueError(f"{name} must be DD/MM/YYYY or 'не указано'")
        if kind == "number" and value != "не указано" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise ValueError(f"{name} must be numeric or 'не указано'")
        if kind == "string" and not isinstance(value, str):
            raise ValueError(f"{name} must be a string")
        if kind == "enum" and value != "не указано" and value not in field.get("allowed_values", []):
            raise ValueError(f"{name} has a value outside the contract")
        if kind == "binary_code" and (not isinstance(value, Mapping) or set(value) != {"code", "text"} or value["code"] not in {0, 1} or not isinstance(value["text"], str)):
            raise ValueError(f"{name} must be {{code, text}}")
        if kind == "medication_list_or_zero" and value != 0 and (not isinstance(value, list) or any(not isinstance(item, Mapping) or set(item) != {"name", "prescription"} or not all(isinstance(item[key], str) for key in ("name", "prescription")) for item in value)):
            raise ValueError(f"{name} must be 0 or a medication list")
    if normalized.get("ca_fact") != "Y":
        for name in ("ca_lad", "rca"):
            if normalized.get(name) != "не указано":
                raise ValueError(f"{name} is only allowed when ca_fact is Y")
    return {name: normalized[name] for name in FIELD_CONTRACT}


def validate(values: Mapping[str, Any]) -> dict[str, Any]:
    """Short alias used by the orchestration layer."""
    return validate_final_json(values)
