from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderProfile:
    name: str
    family: str
    default_base_url: str
    default_model: str
    default_embed_model: str
    api_key_env: str
    model_env: str
    embed_model_env: str
    base_url_env: str
    auth_scheme: str = "bearer"
    chat_path: str = "/chat/completions"
    embeddings_path: str = "/embeddings"
    extra_headers: dict[str, str] = field(default_factory=dict)
    notes: str = ""
    supports_embeddings: bool = True


PROVIDERS: dict[str, ProviderProfile] = {
    "watsonx": ProviderProfile(
        name="watsonx",
        family="openai_compatible",
        default_base_url="https://us-south.ml.cloud.ibm.com",
        default_model="ibm/granite-13b-chat-v2",
        default_embed_model="",
        api_key_env="IBM_BOB_API_KEY",
        model_env="IBM_BOB_MODEL_ID",
        embed_model_env="",
        base_url_env="IBM_BOB_BASE_URL",
        supports_embeddings=False,
        notes="IBM watsonx.ai with IAM token exchange.",
    ),
}

PROVIDER_MODELS: dict[str, list[str]] = {
    "watsonx": ["ibm/granite-13b-chat-v2", "ibm/granite-13b-instruct-v2"],
}


def get_provider_profile(name: str) -> ProviderProfile:
    normalized = name.strip().lower()
    if normalized not in PROVIDERS:
        raise ValueError(f"Unsupported provider: {name}")
    return PROVIDERS[normalized]


def list_provider_profiles() -> list[ProviderProfile]:
    return [PROVIDERS[key] for key in sorted(PROVIDERS)]


def list_models(provider_name: str) -> list[str]:
    normalized = provider_name.strip().lower()
    return list(PROVIDER_MODELS.get(normalized, []))


def auth_headers(profile: ProviderProfile, api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json", **profile.extra_headers}
    if not api_key:
        return headers
    headers["Authorization"] = f"Bearer {api_key}"
    return headers


def build_url(
    profile: ProviderProfile,
    base_url: str,
    *,
    endpoint: str,
    model: str,
    api_key: str,
    api_version: str | None = None,
) -> str:
    root = base_url.rstrip("/")
    path = profile.chat_path if endpoint == "chat" else profile.embeddings_path
    return f"{root}{path}"


def build_chat_payload(
    profile: ProviderProfile,
    *,
    model: str,
    prompt: str,
    system: str | None,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def build_embedding_payload(profile: ProviderProfile, *, model: str, text: str) -> dict[str, Any]:
    raise ValueError(f"Provider {profile.name} does not support embeddings")
