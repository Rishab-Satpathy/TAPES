"""LLM API wrapper for AITAPES v8.0.

Enforces a partitioned token budget:
    - 70% for generation (plan, build, check)
    - 30% for debate (Alpha, Omega, Judge)

API Interceptor halts with a user prompt on budget breach.
Embedding API support for text-embedding-3-small (or compatible).

Configuration via environment variables:
    AITAPES_API_BASE_URL - API base URL
    AITAPES_API_KEY - API key
    AITAPES_MODEL - Model name
    AITAPES_EMBED_MODEL - Embedding model name
    AITAPES_TOKEN_BUDGET - Total token budget per session
"""

from __future__ import annotations

import json
import os
import time
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .providers import (
    ProviderProfile,
    auth_headers,
    build_chat_payload,
    build_embedding_payload,
    build_url,
    get_provider_profile,
)


# ── Token budget partitioning ──────────────────────────────────────────────

class TokenPartition(StrEnum):
    GENERATION = "generation"
    DEBATE = "debate"


# Partition ratios
GENERATION_RATIO = 0.70
DEBATE_RATIO = 0.30

# Default total budget per session
DEFAULT_TOKEN_BUDGET = 100_000


@dataclass
class TokenBudget:
    """Partitioned token budget tracker.

    70% generation, 30% debate. API interceptor halts on breach.
    """
    total: int = DEFAULT_TOKEN_BUDGET
    generation_limit: int = 0
    debate_limit: int = 0
    generation_used: int = 0
    debate_used: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        if self.generation_limit == 0:
            self.generation_limit = int(self.total * GENERATION_RATIO)
        if self.debate_limit == 0:
            self.debate_limit = int(self.total * DEBATE_RATIO)

    def consume(self, tokens: int, partition: TokenPartition) -> None:
        """Record token usage. Checks limits BEFORE incrementing.

        Atomic math: if the proposed usage would breach the limit,
        raises BudgetBreachError without mutating the counter.
        """
        with self._lock:
            if partition == TokenPartition.GENERATION:
                projected = self.generation_used + tokens
                if projected > self.generation_limit:
                    raise BudgetBreachError(
                        partition=partition,
                        used=projected,
                        limit=self.generation_limit,
                    )
                self.generation_used = projected
            elif partition == TokenPartition.DEBATE:
                projected = self.debate_used + tokens
                if projected > self.debate_limit:
                    raise BudgetBreachError(
                        partition=partition,
                        used=projected,
                        limit=self.debate_limit,
                    )
                self.debate_used = projected

    def remaining(self, partition: TokenPartition) -> int:
        with self._lock:
            if partition == TokenPartition.GENERATION:
                return max(0, self.generation_limit - self.generation_used)
            return max(0, self.debate_limit - self.debate_used)

    def summary(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "generation": {"limit": self.generation_limit, "used": self.generation_used, "remaining": self.remaining(TokenPartition.GENERATION)},
            "debate": {"limit": self.debate_limit, "used": self.debate_used, "remaining": self.remaining(TokenPartition.DEBATE)},
        }


class BudgetBreachError(Exception):
    """Raised when a token partition budget would be exceeded."""
    def __init__(self, partition: TokenPartition, used: int, limit: int) -> None:
        self.partition = partition
        self.used = used
        self.limit = limit
        super().__init__(
            f"Token budget BREACHED for {partition.value}: "
            f"projected {used:,} / limit {limit:,} "
            f"({used/limit:.0%})"
        )


class InsufficientTokensError(Exception):
    """Raised when user denies a budget breach continuation.

    The orchestrator catches this to invoke why_ledger.rollback()
    and restore the working directory + AST state.
    """
    def __init__(self, partition: TokenPartition, used: int, limit: int) -> None:
        self.partition = partition
        self.used = used
        self.limit = limit
        super().__init__(
            f"Insufficient tokens DENIED for {partition.value}: "
            f"projected {used:,} / limit {limit:,}"
        )


# ── Session-level budget singleton ─────────────────────────────────────────

_session_budget: TokenBudget | None = None


def get_session_budget() -> TokenBudget:
    global _session_budget
    if _session_budget is None:
        total = int(os.environ.get("AITAPES_TOKEN_BUDGET", str(DEFAULT_TOKEN_BUDGET)))
        _session_budget = TokenBudget(total=total)
    return _session_budget


def reset_session_budget(total: int | None = None) -> TokenBudget:
    global _session_budget
    _session_budget = TokenBudget(total=total or DEFAULT_TOKEN_BUDGET)
    return _session_budget


# ── API interceptor ────────────────────────────────────────────────────────

def _check_budget_preflight(tokens: int, partition: TokenPartition) -> None:
    """Pre-flight check: verify we have enough budget BEFORE API call."""
    budget = get_session_budget()
    remaining = budget.remaining(partition)
    if tokens > remaining:
        limit = budget.generation_limit if partition == TokenPartition.GENERATION else budget.debate_limit
        used = budget.generation_used if partition == TokenPartition.GENERATION else budget.debate_used
        raise InsufficientTokensError(
            partition=partition,
            used=used + tokens,
            limit=limit,
        )

def _intercept_budget(tokens: int, partition: TokenPartition) -> None:
    """Post-call budget reconciliation.

    This runs AFTER the API call returns to record actual spend.
    Budget breach here means we overran our pre-flight estimate —
    user is prompted to confirm or abort.
    """
    budget = get_session_budget()
    try:
        budget.consume(tokens, partition)
    except BudgetBreachError as e:
        print(f"\n{'!'*60}")
        print(f"  TAPES BUDGET BREACH — {e.partition.value.upper()}")
        print(f"  Projected: {e.used:,} / Limit: {e.limit:,}")
        print(f"{'!'*60}")
        from forest_tapes.tapes_core.interaction import ask_user
        if ask_user("  Continue anyway? (y/N): ", default=False):
            with budget._lock:
                if partition == TokenPartition.GENERATION:
                    budget.generation_used += tokens
                else:
                    budget.debate_used += tokens
        else:
            raise InsufficientTokensError(
                partition=e.partition,
                used=e.used,
                limit=e.limit,
            ) from e


# ── Configuration ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LLMConfig:
    """LLM configuration."""
    provider: str = "watsonx"
    base_url: str = "https://us-south.ml.cloud.ibm.com"
    api_key: str = ""
    model: str = "ibm/granite-13b-chat-v2"
    embed_model: str = ""
    temperature: float = 0.3
    max_tokens: int = 4096
    api_version: str = "2024-08-01-preview"
    profile: ProviderProfile | None = None

    @classmethod
    def from_env(cls) -> LLMConfig:
        provider_name = os.environ.get("AITAPES_PROVIDER", "watsonx").strip().lower()
        profile = get_provider_profile(provider_name)
        api_key = (
            os.environ.get("AITAPES_API_KEY")
            or os.environ.get(profile.api_key_env, "")
        )
        base_url = (
            os.environ.get("AITAPES_API_BASE_URL")
            or os.environ.get(profile.base_url_env, "")
            or profile.default_base_url
        )
        model = (
            os.environ.get("AITAPES_MODEL")
            or os.environ.get(profile.model_env, "")
            or profile.default_model
        )
        embed_model = (
            os.environ.get("AITAPES_EMBED_MODEL")
            or os.environ.get(profile.embed_model_env, "")
            or profile.default_embed_model
        )
        return cls(
            provider=provider_name,
            base_url=base_url,
            api_key=api_key,
            model=model,
            embed_model=embed_model,
            temperature=float(os.environ.get("AITAPES_TEMPERATURE", "0.3")),
            max_tokens=int(os.environ.get("AITAPES_MAX_TOKENS", "4096")),
            api_version=os.environ.get("AITAPES_API_VERSION", "2024-08-01-preview"),
            profile=profile,
        )


@dataclass(frozen=True)
class LLMResponse:
    """LLM API response."""
    content: str
    model: str
    tokens_used: int
    finish_reason: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class EmbeddingResponse:
    """Embedding API response."""
    embedding: list[float]
    model: str
    tokens_used: int
    raw: dict[str, Any]


# ── Generation call ────────────────────────────────────────────────────────

def _estimate_tokens(prompt: str, system: str | None, max_tokens: int) -> int:
    """Rough token estimate: ~4 chars per token for mixed English code."""
    raw = (system or "") + prompt
    return (len(raw) // 4) + max_tokens


def call_llm(
    prompt: str,
    config: LLMConfig | None = None,
    system: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    partition: TokenPartition = TokenPartition.GENERATION,
) -> LLMResponse:
    """Call the configured LLM API with budget enforcement and retry."""
    if config is None:
        config = LLMConfig.from_env()

    profile = config.profile or get_provider_profile(config.provider)
    mt = max_tokens if max_tokens is not None else config.max_tokens

    payload = build_chat_payload(
        profile,
        model=config.model,
        prompt=prompt,
        system=system,
        temperature=temperature if temperature is not None else config.temperature,
        max_tokens=mt,
    )
    url = build_url(
        profile,
        config.base_url,
        endpoint="chat",
        model=config.model,
        api_key=config.api_key,
        api_version=config.api_version,
    )
    headers = auth_headers(profile, config.api_key)

    data = json.dumps(payload).encode("utf-8")

    estimated = _estimate_tokens(prompt, system, mt)
    _check_budget_preflight(estimated, partition)

    retries, delay = 3, 1.0
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(f"LLM API error {e.code}: {error_body}") from e
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"LLM API connection error: {e.reason}") from e

    content, finish_reason, tokens = _parse_chat_response(body, profile, config)
    _intercept_budget(tokens, partition)

    return LLMResponse(
        content=content,
        model=body.get("model", config.model),
        tokens_used=tokens,
        finish_reason=finish_reason,
        raw=body,
    )


def call_llm_json(
    prompt: str,
    config: LLMConfig | None = None,
    system: str | None = None,
    partition: TokenPartition = TokenPartition.GENERATION,
) -> dict[str, Any]:
    """Call LLM and parse response as JSON."""
    if system is None:
        system = "You must respond with valid JSON only. No markdown, no explanation, just JSON."

    response = call_llm(prompt, config=config, system=system, partition=partition)

    # Try to extract JSON from the response
    content = response.content.strip()

    # Remove markdown code fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        # Remove first and last lines (```json and ```)
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM returned invalid JSON: {content[:200]}") from e


# ── Embedding call ─────────────────────────────────────────────────────────

def call_embedding(
    text: str,
    config: LLMConfig | None = None,
    model: str | None = None,
) -> EmbeddingResponse:
    """Call an embedding API (text-embedding-3-small or compatible).

    This is the second call mode alongside generation.
    Embedding calls draw from the GENERATION partition budget.
    """
    if config is None:
        config = LLMConfig.from_env()

    profile = config.profile or get_provider_profile(config.provider)
    if not profile.supports_embeddings:
        raise RuntimeError(f"Provider {profile.name} does not support embeddings in TAPES")

    embed_model = model or config.embed_model
    payload = build_embedding_payload(profile, model=embed_model, text=text)
    url = build_url(
        profile,
        config.base_url,
        endpoint="embedding",
        model=embed_model,
        api_key=config.api_key,
        api_version=config.api_version,
    )
    headers = auth_headers(profile, config.api_key)

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    estimated = len(text) // 4
    _check_budget_preflight(estimated, TokenPartition.GENERATION)

    retries, delay = 3, 1.0
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                break
        except urllib.error.HTTPError as e:
            if attempt < retries - 1 and e.code in (429, 500, 502, 503, 504):
                time.sleep(delay)
                delay *= 2
                continue
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(f"Embedding API error {e.code}: {error_body}") from e
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"Embedding API connection error: {e.reason}") from e

    embedding, tokens = _parse_embedding_response(body, profile)

    # Budget enforcement — embedding calls count against generation partition
    _intercept_budget(tokens, TokenPartition.GENERATION)

    return EmbeddingResponse(
        embedding=embedding,
        model=body.get("model", embed_model),
        tokens_used=tokens,
        raw=body,
    )


def embed_text(text: str, config: LLMConfig | None = None) -> list[float]:
    """Convenience: embed text and return just the vector."""
    return call_embedding(text, config=config).embedding


def _parse_chat_response(body: dict[str, Any], profile: ProviderProfile, config: LLMConfig) -> tuple[str, str, int]:
    choice = body["choices"][0]
    usage = body.get("usage", {})
    return (
        choice["message"]["content"],
        choice.get("finish_reason", "unknown"),
        usage.get("total_tokens", 0),
    )


def _parse_embedding_response(body: dict[str, Any], profile: ProviderProfile) -> tuple[list[float], int]:
    usage = body.get("usage", {})
    return body["data"][0]["embedding"], usage.get("total_tokens", 0)
