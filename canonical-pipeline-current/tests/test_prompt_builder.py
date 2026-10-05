from pipeline.parser import create_empty_template
from pipeline.prompt_builder import build_llm_request


def test_prompt_builder_selects_target_fields():
    request = build_llm_request("Без идентификаторов", create_empty_template())
    assert request["llm_required"] is True
    assert request["target_fields"]
