from __future__ import annotations

import pytest

from ai import factory
from ai.factory import build_ai, create_provider
from ai.ollama import OllamaProvider
from ai.prompts import DEFAULT_SYSTEM_PROMPT
from ai.service import AI_DISABLED_DESCRIPTION
from core.config import AIConfig, AIProviderName, load_config
from core.exceptions import AIConfigurationError


def test_ai_disabled_by_default_builds_no_service() -> None:
    setup = build_ai(load_config(environ={}, env_file=None))

    assert setup.service is None
    assert setup.description == AI_DISABLED_DESCRIPTION


def test_enabled_without_model_degrades_to_commands_only() -> None:
    setup = build_ai(load_config(environ={"AEGIS_AI_ENABLED": "true"}, env_file=None))

    assert setup.service is None
    assert "AEGIS_OLLAMA_MODEL" in setup.description


def test_ollama_is_selected_and_configured() -> None:
    config = load_config(
        environ={
            "AEGIS_AI_ENABLED": "true",
            "AEGIS_AI_PROVIDER": "ollama",
            "AEGIS_OLLAMA_MODEL": "llama3.2:3b",
            "AEGIS_AI_MAX_HISTORY_MESSAGES": "6",
        },
        env_file=None,
    )

    setup = build_ai(config)

    assert setup.service is not None
    assert setup.description == "habilitada (Ollama, modelo llama3.2:3b)"
    assert setup.service.history.messages[0].content == DEFAULT_SYSTEM_PROMPT


def test_custom_system_prompt_is_used() -> None:
    config = load_config(
        environ={
            "AEGIS_AI_ENABLED": "true",
            "AEGIS_OLLAMA_MODEL": "m",
            "AEGIS_AI_SYSTEM_PROMPT": "Seja breve.",
        },
        env_file=None,
    )

    setup = build_ai(config)

    assert setup.service is not None
    assert setup.service.history.messages[0].content == "Seja breve."


def test_create_provider_returns_ollama_provider() -> None:
    provider = create_provider(AIConfig(enabled=True, ollama_model="m", timeout_seconds=5))

    assert isinstance(provider, OllamaProvider)
    assert provider.model == "m"


def test_every_supported_provider_has_an_implementation() -> None:
    assert set(factory._PROVIDER_FACTORIES) == set(AIProviderName)


def test_provider_without_implementation_is_explicit_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(factory, "_PROVIDER_FACTORIES", {})

    with pytest.raises(AIConfigurationError, match="sem implementação"):
        create_provider(AIConfig(enabled=True, ollama_model="m"))
