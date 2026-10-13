"""Seleção do provedor de IA a partir da configuração.

Ponto de extensão: um provedor futuro (ex.: online) precisa de um valor em
``AIProviderName`` e de uma entrada em ``_PROVIDER_FACTORIES``. Nada é trocado
silenciosamente: provedor sem implementação é um erro explícito.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ai.ollama import OllamaProvider
from ai.prompts import DEFAULT_SYSTEM_PROMPT
from ai.provider import AIProvider
from ai.service import AI_DISABLED_DESCRIPTION, AIService
from core.config import AIConfig, AIProviderName, AppConfig
from core.exceptions import AIConfigurationError
from core.logging_config import get_logger

_logger = get_logger("ai")


def _create_ollama(config: AIConfig) -> AIProvider:
    if config.ollama_model is None:
        raise AIConfigurationError("defina AEGIS_OLLAMA_MODEL")
    return OllamaProvider(
        base_url=config.ollama_base_url,
        model=config.ollama_model,
        timeout_seconds=config.timeout_seconds,
    )


_PROVIDER_FACTORIES: dict[AIProviderName, Callable[[AIConfig], AIProvider]] = {
    AIProviderName.OLLAMA: _create_ollama,
}


def create_provider(config: AIConfig) -> AIProvider:
    """Instancia o provedor configurado (sem nenhuma chamada de rede)."""
    factory = _PROVIDER_FACTORIES.get(config.provider)
    if factory is None:
        raise AIConfigurationError(f"provedor '{config.provider}' sem implementação")
    return factory(config)


@dataclass(frozen=True, slots=True)
class AISetup:
    """Resultado da preparação da IA: o serviço, ou o motivo de não haver um."""

    service: AIService | None
    description: str


def build_ai(config: AppConfig) -> AISetup:
    """Prepara a IA. Configuração incompleta não impede o modo de comandos."""
    if not config.ai.enabled:
        return AISetup(service=None, description=AI_DISABLED_DESCRIPTION)
    try:
        provider = create_provider(config.ai)
    except AIConfigurationError as exc:
        _logger.info("IA habilitada, mas indisponível: %s.", exc)
        return AISetup(service=None, description=f"indisponível ({exc})")

    service = AIService(
        provider,
        system_prompt=config.ai.system_prompt or DEFAULT_SYSTEM_PROMPT,
        max_history_messages=config.ai.max_history_messages,
        secrets=config.secret_values(),
    )
    _logger.info("IA habilitada: %s, modelo %s.", provider.name, provider.model)
    return AISetup(service=service, description=service.describe())
