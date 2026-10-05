"""Backend-facing access to the single pipeline configuration loader."""

from pipeline.llm_client import YandexConfig

Settings = YandexConfig


def get_settings() -> Settings:
    return Settings.from_env()
