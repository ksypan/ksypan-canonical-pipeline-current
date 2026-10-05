import json

from pipeline.evidence import build_evidence, validate_llm_evidence
from pipeline.field_contract import FIELD_CONTRACT
from pipeline.parser import extract_epicrisis_from_deidentified
from pipeline.processor import process_epicrisis_bundle


def _missing_llm(request):
    return {name: FIELD_CONTRACT[name]["missing_value"] for name in request["target_fields"]}


def test_parser_evidence_offsets_are_substrings():
    text = "Осмотр:\nИМТ 25,4\nАД 153/103"
    record = extract_epicrisis_from_deidentified(text)
    for meta in record["meta"].values():
        for span in meta.get("evidence_spans", []):
            assert text[span["start"]:span["end"]] == span["text"]


def test_explicit_negative_has_real_evidence():
    text = "Рентгенография ОГК:\nОтёка лёгких нет"
    bundle = process_epicrisis_bundle(text, llm_call=_missing_llm, document="negative")
    item = bundle["evidence"]["fields"]["rg_pc"]
    assert item["value"]["code"] == 0
    assert item["source"] == "parser"
    assert item["evidence"]
    span = item["evidence"][0]
    assert bundle["text"][span["start"]:span["end"]] == span["text"]


def test_not_mentioned_default_has_no_evidence():
    bundle = process_epicrisis_bundle("Без медицинских данных", llm_call=_missing_llm, document="missing")
    item = bundle["evidence"]["fields"]["rg_pc"]
    assert item["value"]["code"] == 0
    assert item["reason"] == "not_mentioned"
    assert item["evidence"] == []


def test_llm_exact_evidence_is_accepted_and_invented_quote_is_rejected():
    text = "Диагноз:\nХСН 2А, ФК 2"
    validated = validate_llm_evidence(text, {"evidence": [
        {"field": "hf", "value": 1, "evidence": "ХСН 2А, ФК 2"},
        {"field": "hf", "value": 1, "evidence": "выдуманная цитата"},
    ]})
    assert len(validated["hf"]) == 1
    assert text[validated["hf"][0]["start"]:validated["hf"][0]["end"]] == "ХСН 2А, ФК 2"


def test_multiple_llm_spans_are_supported():
    text = "Аспирин 100 мг утром. Клопидогрел 75 мг 1 раз в день."
    validated = validate_llm_evidence(text, {"evidence": [
        {"field": "antiplatelet", "evidence": "Аспирин 100 мг утром"},
        {"field": "antiplatelet", "evidence": "Клопидогрел 75 мг 1 раз в день"},
    ]})
    assert len(validated["antiplatelet"]) == 2


def test_evidence_does_not_change_submission_result():
    bundle = process_epicrisis_bundle("Осмотр:\nИМТ 25,4", llm_call=_missing_llm, document="stable")
    result_before = json.dumps(bundle["result"], ensure_ascii=False, sort_keys=True)
    evidence = build_evidence(bundle["document"], bundle["text"], bundle["result"], {"values": {}, "meta": {}}, llm_evidence={})
    assert json.dumps(bundle["result"], ensure_ascii=False, sort_keys=True) == result_before
    assert evidence["document"] == "stable"


def test_evidence_value_matches_canonical_value():
    bundle = process_epicrisis_bundle("Осмотр:\nИМТ 25,4", llm_call=_missing_llm, document="same")
    for name, item in bundle["evidence"]["fields"].items():
        assert item["value"] == bundle["result"][name]
