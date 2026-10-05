from pipeline.field_contract import FIELD_CONTRACT
from pipeline.merge import merge_record
from pipeline.parser import create_empty_template
from pipeline.prompt_builder import build_llm_request
from pipeline.validator import validate_final_json


def test_contract_has_50_fields():
    assert len(FIELD_CONTRACT) == 50


def test_prompt_and_merge_smoke():
    record = create_empty_template()
    request = build_llm_request("Без идентификаторов", record)
    result = merge_record(record, {name: FIELD_CONTRACT[name]["missing_value"] for name in request["target_fields"]}, request["target_fields"])
    assert len(validate_final_json(result)) == 50
