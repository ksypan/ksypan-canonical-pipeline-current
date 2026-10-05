import json
from unittest.mock import Mock, patch

import pytest
import requests

from pipeline.llm_client import (
    LLMAuthenticationError,
    LLMResponseError,
    LLMTimeoutError,
    YandexConfig,
    call_llm,
)


CONFIG = YandexConfig("secret", "gpt://folder/model", "https://example.test")
REQUEST = {"llm_required": True, "target_fields": ["bmi"], "system_prompt": "s", "user_prompt": "u"}


def response(text, status=200):
    result = Mock(status_code=status, text="safe")
    result.json.return_value = {"result": {"alternatives": [{"message": {"text": text}}]}}
    return result


def test_valid_response_and_target_validation():
    with patch("pipeline.llm_client.requests.post", return_value=response('```json\n{"bmi": 25.4}\n```')):
        assert call_llm(REQUEST, CONFIG) == {"bmi": 25.4}


def test_invalid_json():
    with patch("pipeline.llm_client.requests.post", return_value=response("not json")):
        with pytest.raises(LLMResponseError):
            call_llm(REQUEST, CONFIG)


def test_http_auth_error():
    with patch("pipeline.llm_client.requests.post", return_value=response("{}", 401)):
        with pytest.raises(LLMAuthenticationError):
            call_llm(REQUEST, CONFIG)


def test_timeout():
    with patch("pipeline.llm_client.requests.post", side_effect=requests.Timeout()):
        with pytest.raises(LLMTimeoutError):
            call_llm(REQUEST, CONFIG)


def test_extra_field_is_rejected():
    with patch("pipeline.llm_client.requests.post", return_value=response(json.dumps({"bmi": 1, "extra": 2}))):
        with pytest.raises(LLMResponseError):
            call_llm(REQUEST, CONFIG)
