"""Single orchestration entry point for backend consumers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .llm_client import call_llm
from .merge import merge_record
from .parser import extract_epicrisis
from .prompt_builder import build_llm_request
from .validator import validate_final_json
from .evidence import build_evidence


def process_epicrisis(text: str, *, llm_call: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None) -> dict[str, Any]:
    return process_epicrisis_bundle(text, llm_call=llm_call)["result"]


def process_epicrisis_bundle(
    text: str,
    *,
    llm_call: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    llm_evidence: Mapping[str, Any] | None = None,
    document: str = "document",
) -> dict[str, Any]:
    """Return the UI data model; the official result remains unchanged."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    redacted_text, record = extract_epicrisis(text)
    request = build_llm_request(redacted_text, record)
    print("TARGET_FIELDS:", request.get("target_fields"))
    response = dict(llm_call(request) if llm_call is not None else call_llm(request)) if request["llm_required"] else {}
    result = validate_final_json(merge_record(record, response, request["target_fields"]))
    return {
        "document": document,
        "text": redacted_text,
        "result": result,
        "evidence": build_evidence(
            document,
            redacted_text,
            result,
            record,
            llm_evidence=llm_evidence,
            llm_fields=request["target_fields"],
        ),
    }
