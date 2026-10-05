import pytest

from pipeline.field_contract import FIELD_CONTRACT
from pipeline.merge import merge_record
from pipeline.parser import create_empty_template


def test_confirmed_parser_value_is_not_overwritten():
    record = create_empty_template()
    record["values"]["bmi"] = 25.4
    record["meta"]["bmi"] = {"status": "confirmed", "source": "parser", "evidence": "ИМТ 25,4"}
    targets = [name for name, field in FIELD_CONTRACT.items() if field["extractor"] != "parser"]
    response = {name: FIELD_CONTRACT[name]["missing_value"] for name in targets}
    assert merge_record(record, response, targets)["bmi"] == 25.4


def test_llm_extra_field_is_rejected():
    record = create_empty_template()
    with pytest.raises(ValueError):
        merge_record(record, {"unexpected": 1}, ["bmi"])
