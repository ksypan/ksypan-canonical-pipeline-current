"""Small YandexGPT HTTP client. Secrets are read only from environment."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping

import requests
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional when environment is preloaded
    load_dotenv = None


class LLMClientError(RuntimeError):
    """Raised when YandexGPT cannot return a valid JSON object."""


class LLMTimeoutError(LLMClientError):
    """The upstream request exceeded its timeout."""


class LLMAuthenticationError(LLMClientError):
    """Yandex rejected the supplied credentials."""


class LLMResponseError(LLMClientError):
    """Yandex returned an unexpected or invalid response."""


@dataclass(frozen=True)
class YandexConfig:
    api_key: str
    model_uri: str
    api_url: str

    @classmethod
    def from_env(cls) -> "YandexConfig":
        if load_dotenv is not None:
            load_dotenv()
        values = {
            "api_key": os.getenv("YANDEX_API_KEY"),
            "model_uri": os.getenv("YANDEX_MODEL_URI"),
            "api_url": os.getenv("YANDEX_API_URL") or "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
        }
        missing = [name for name, value in values.items() if not value and name != "api_url"]
        if missing:
            raise LLMClientError("Missing environment variables: " + ", ".join(f"YANDEX_{name.upper()}" for name in missing))
        return cls(**values)  # type: ignore[arg-type]


def _response_json(response: requests.Response) -> dict[str, Any]:
    if response.status_code in {401, 403}:
        raise LLMAuthenticationError(f"YandexGPT authentication failed (HTTP {response.status_code})")
    if response.status_code >= 400:
        raise LLMClientError(f"YandexGPT API returned HTTP {response.status_code}")
    try:
        payload = response.json()
        text = payload["result"]["alternatives"][0]["message"]["text"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMResponseError("YandexGPT returned an unexpected response structure") from exc
    if not isinstance(text, str) or not text.strip():
        raise LLMResponseError("YandexGPT returned an empty response")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMResponseError("YandexGPT returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise LLMResponseError("YandexGPT response must be a JSON object")
    return parsed


def call_llm(request: Mapping[str, Any], config: YandexConfig | None = None, *, timeout: int = 60) -> dict[str, Any]:
    """Send a prompt-builder request and return the parsed JSON object."""
    if not request.get("llm_required"):
        return {}
    target_fields = request.get("target_fields")
    if not isinstance(target_fields, list) or not all(isinstance(name, str) for name in target_fields):
        raise LLMResponseError("LLM request must contain a target_fields list")
    config = config or YandexConfig.from_env()
    try:
        response = requests.post(
            config.api_url,
            headers={"Authorization": f"Api-Key {config.api_key}", "Content-Type": "application/json"},
            json={
                "modelUri": config.model_uri,
                "completionOptions": {"stream": False, "temperature": 0},
                "messages": [
                    {"role": "system", "text": request["system_prompt"]},
                    {"role": "user", "text": request["user_prompt"]},
                ],
            },
            timeout=timeout,
        )
    except requests.Timeout as exc:
        raise LLMTimeoutError(f"YandexGPT request timed out after {timeout}s") from exc
    except requests.RequestException as exc:
        raise LLMClientError(f"YandexGPT request failed: {exc.__class__.__name__}") from exc
    result = _response_json(response)
    unexpected = set(result) - set(target_fields)
    missing = set(target_fields) - set(result)
    if unexpected or missing:
        raise LLMResponseError(
            "YandexGPT fields do not match target_fields"
            + (f"; unexpected={sorted(unexpected)}" if unexpected else "")
            + (f"; missing={sorted(missing)}" if missing else "")
        )
    return result
