from pipeline.field_contract import FIELD_CONTRACT
from pipeline.processor import process_epicrisis


def test_processor_can_finish_with_injected_llm():
    def fake_llm(request):
        return {name: FIELD_CONTRACT[name]["missing_value"] for name in request["target_fields"]}

    result = process_epicrisis("Без идентификаторов", llm_call=fake_llm)
    assert len(result) == 50
