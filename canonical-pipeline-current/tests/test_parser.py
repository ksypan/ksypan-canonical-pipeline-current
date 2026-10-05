from pipeline.field_contract import FIELD_CONTRACT
from pipeline.parser import extract_epicrisis_from_deidentified


def test_parser_returns_contract_shape():
    record = extract_epicrisis_from_deidentified("Диагноз:\nАртериальная гипертензия")
    assert set(record["values"]) == set(FIELD_CONTRACT)
    assert set(record["values"]) == set(record["meta"])
