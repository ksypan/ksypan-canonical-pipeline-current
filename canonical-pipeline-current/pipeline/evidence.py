"""Evidence-layer records kept separate from the official submission JSON.

The displayed text is the deidentified text that deterministic parsing and the
LLM receive. All offsets in this module are offsets into that exact string.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any


def _span(text: str, start: int, end: int) -> dict[str, Any] | None:
    if not isinstance(start, int) or not isinstance(end, int):
        return None
    if start < 0 or end < start or end > len(text):
        return None
    return {"text": text[start:end], "start": start, "end": end}


def verify_evidence_text(text: str, evidence_text: str) -> dict[str, Any] | None:
    """Accept an LLM fragment only when it is an exact source substring."""
    if not isinstance(text, str) or not isinstance(evidence_text, str) or not evidence_text:
        return None
    start = text.find(evidence_text)
    if start < 0:
        return None
    return {"text": evidence_text, "start": start, "end": start + len(evidence_text)}


def validate_llm_evidence(text: str, response: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Validate the optional future LLM evidence__test protocol.

    Supported protocol: ``{"field": "hf", "value": ..., "evidence__test": "..."}``
    records, supplied either as a list or as a field->record mapping. Invalid
    or invented quotes are deliberately omitted, never repaired or searched
    approximately.
    """
    raw = response.get("evidence__test", []) if isinstance(response, Mapping) else []
    records: list[Mapping[str, Any]] = []
    if isinstance(raw, Mapping):
        records = [dict(value, field=field) for field, value in raw.items() if isinstance(value, Mapping)]
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        records = [item for item in raw if isinstance(item, Mapping)]
    validated: dict[str, list[dict[str, Any]]] = {}
    for item in records:
        field = item.get("field")
        fragment = item.get("evidence__test")
        span = verify_evidence_text(text, fragment)
        if isinstance(field, str) and span is not None:
            validated.setdefault(field, []).append(span)
    return validated


def _parser_spans(text: str, meta: Mapping[str, Any]) -> list[dict[str, Any]]:
    spans = meta.get("evidence_spans", [])
    if not isinstance(spans, list):
        return []
    result = []
    for item in spans:
        if not isinstance(item, Mapping):
            continue
        span = _span(text, item.get("start"), item.get("end"))
        if span is not None and span["text"] == item.get("text"):
            result.append(span)
    return result


def build_evidence(
    document: str,
    text: str,
    result: Mapping[str, Any],
    record: Mapping[str, Any],
    *,
    llm_evidence: Mapping[str, Any] | None = None,
    llm_fields: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a machine-readable evidence__test object without touching ``result__test``."""
    values = record.get("values", {})
    meta = record.get("meta", {})
    if not isinstance(values, Mapping) or not isinstance(meta, Mapping):
        raise ValueError("record must contain values and meta mappings")
    validated_llm = validate_llm_evidence(text, llm_evidence or {})
    fields: dict[str, Any] = {}
    for field, value in result.items():
        item_meta = meta.get(field, {})
        source = item_meta.get("source")
        reason = item_meta.get("reason")
        spans = _parser_spans(text, item_meta) if source == "parser" else []
        if field in llm_fields:
            source = "llm"
        elif source is None:
            source = "finalizer"
        if field in validated_llm:
            source = "llm"
            spans = validated_llm[field]
            reason = None
        elif source in {"finalizer", "llm"} and reason is None and not spans:
            reason = "not_mentioned"
        fields[field] = {
            "value": deepcopy(value),
            "source": source,
            "reason": reason,
            "evidence__test": spans,
        }
    return {"document": document, "fields": fields}


def write_evidence(path: str | Path, evidence: Mapping[str, Any]) -> None:
    import json

    Path(path).write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
