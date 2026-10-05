import pytest

from pipeline.field_contract import FIELD_CONTRACT
from pipeline.validator import validate_final_json


def test_validator_rejects_wrong_field_count():
    with pytest.raises(ValueError):
        validate_final_json({})


def test_validator_returns_contract_order():
    values = {name: field["missing_value"] for name, field in FIELD_CONTRACT.items()}
    assert list(validate_final_json(values)) == list(FIELD_CONTRACT)
