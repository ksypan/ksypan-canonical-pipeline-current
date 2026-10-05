"""Combine deterministic parser values with an LLM response."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .field_contract import FIELD_CONTRACT


def merge_record(record: Mapping[str, Any], llm_response: Mapping[str, Any], target_fields: list[str]) -> dict[str, Any]:
    values = record.get("values")
    meta = record.get("meta")
    if not isinstance(values, Mapping) or not isinstance(meta, Mapping) or set(values) != set(meta):
        raise ValueError("record must contain matching values and meta mappings")
    targets = set(target_fields)
    if any(name not in FIELD_CONTRACT for name in targets):
        raise ValueError("target_fields contains unknown fields")
    if any(FIELD_CONTRACT[name].get("extractor") == "parser" for name in targets):
        raise ValueError("parser-only fields cannot be LLM targets")
    if set(llm_response) != targets:
        raise ValueError("LLM response keys must match target_fields exactly")

    result: dict[str, Any] = {}
    for name, field in FIELD_CONTRACT.items():
        if name not in values:
            raise ValueError(f"Unknown or missing parser field: {name}")
        if meta[name].get("status") == "confirmed":
            result[name] = values[name]
        elif name in targets:
            result[name] = llm_response[name]
        else:
            result[name] = field.get("missing_value", "не указано")
    return result
