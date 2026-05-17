from __future__ import annotations

from aitapes.llm import LLMConfig
from aitapes.providers import build_url, get_provider_profile


def test_llm_config_defaults_to_watsonx() -> None:
    config = LLMConfig.from_env()

    assert config.provider == "watsonx"
    assert config.model == "ibm/granite-13b-chat-v2"
    assert config.base_url == "https://us-south.ml.cloud.ibm.com"


def test_llm_config_uses_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("AITAPES_PROVIDER", "watsonx")
    monkeypatch.setenv("IBM_BOB_API_KEY", "test-key-123")
    monkeypatch.setenv("IBM_BOB_MODEL_ID", "ibm/granite-13b-instruct-v2")

    config = LLMConfig.from_env()

    assert config.provider == "watsonx"
    assert config.api_key == "test-key-123"
    assert config.model == "ibm/granite-13b-instruct-v2"


def test_watsonx_chat_url_uses_base() -> None:
    profile = get_provider_profile("watsonx")

    chat_url = build_url(
        profile,
        profile.default_base_url,
        endpoint="chat",
        model="ibm/granite-13b-chat-v2",
        api_key="abc123",
        api_version=None,
    )

    assert "/chat/completions" in chat_url
    assert chat_url.startswith("https://us-south.ml.cloud.ibm.com")
