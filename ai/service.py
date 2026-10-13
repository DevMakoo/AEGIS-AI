"""Serviço de IA: monta o contexto, chama o provedor e mantém o histórico da sessão.

Não conhece a interface (terminal, GUI ou voz). A resposta é sempre devolvida como
texto puro: nunca é avaliada, executada nem reprocessada como comando.
"""

from __future__ import annotations

import re
import time
import traceback
from collections.abc import Iterable
from pathlib import Path

from ai.history import ConversationHistory
from ai.provider import AIProvider
from core.exceptions import (
    AIConfigurationError,
    AIEndpointNotFoundError,
    AIError,
    AIModelNotFoundError,
    AIProviderError,
    AIResponseError,
    AITimeoutError,
    AIUnavailableError,
)
from core.logging_config import FILE_ONLY, get_logger

SECRET_PLACEHOLDER = "[segredo removido]"
AI_DISABLED_DESCRIPTION = "desativada (AEGIS_AI_ENABLED=false)"

_ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-Z\\-_])")
_ALLOWED_CONTROL = frozenset("\n\t")

_USER_MESSAGES: tuple[tuple[type[AIError], str], ...] = (
    (
        AIUnavailableError,
        "Não consegui falar com o Ollama. Verifique se ele está em execução e tente "
        "novamente. Os comandos continuam disponíveis.",
    ),
    (
        AIModelNotFoundError,
        "O modelo configurado não foi encontrado no Ollama. Confira AEGIS_OLLAMA_MODEL "
        '(os modelos instalados aparecem em "ollama list").',
    ),
    (
        AIEndpointNotFoundError,
        "O endereço configurado não respondeu como um servidor Ollama. Confira "
        "AEGIS_OLLAMA_BASE_URL.",
    ),
    (
        AITimeoutError,
        "A IA demorou demais para responder. Tente novamente ou aumente AEGIS_AI_TIMEOUT_SECONDS.",
    ),
    (AIResponseError, "Recebi uma resposta inválida da IA. Tente novamente."),
    (AIConfigurationError, "A conversa inteligente não está configurada corretamente."),
)
_FALLBACK_USER_MESSAGE = "Ocorreu uma falha inesperada na IA. Os comandos continuam disponíveis."

# Estado da última tentativa, para ``status``/cabeçalho (``{provider}`` = nome do provedor).
_STATUS_LABELS: tuple[tuple[type[AIError], str], ...] = (
    (AIUnavailableError, "{provider} inacessível"),
    (AIModelNotFoundError, "modelo não encontrado"),
    (AIEndpointNotFoundError, "endereço do {provider} não encontrado"),
    (AITimeoutError, "tempo limite excedido"),
    (AIResponseError, "resposta inválida do {provider}"),
)
_FALLBACK_STATUS_LABEL = "falha inesperada"
_MAX_LOGGED_FRAMES = 6

_logger = get_logger("ai")


def user_message_for(error: AIError) -> str:
    """Mensagem curta, em português e sem detalhes técnicos, para a interface."""
    for error_type, message in _USER_MESSAGES:
        if isinstance(error, error_type):
            return message
    return _FALLBACK_USER_MESSAGE


def _stack_locations(exc: BaseException) -> str:
    """Ex.: ``service.py:120 reply > ollama.py:93 _send`` (só arquivo, linha e função)."""
    frames = traceback.extract_tb(exc.__traceback__)[-_MAX_LOGGED_FRAMES:]
    if not frames:
        return "(local desconhecido)"
    return " > ".join(f"{Path(f.filename).name}:{f.lineno} {f.name}" for f in frames)


def sanitize_model_output(text: str) -> str:
    """Remove sequências ANSI e caracteres de controle que poderiam manipular o terminal."""
    text = _ANSI_ESCAPE.sub("", text.replace("\r\n", "\n"))
    kept: list[str] = []
    for char in text:
        if char in _ALLOWED_CONTROL or char.isprintable():
            kept.append(char)
        elif char.isspace():  # ex.: \r, espaço não separável
            kept.append(" ")
        # demais controles (ESC, BEL, bidi U+202E etc.) são descartados
    return "".join(kept).strip()


class AIService:
    def __init__(
        self,
        provider: AIProvider,
        *,
        system_prompt: str,
        max_history_messages: int,
        secrets: Iterable[str] = (),
    ) -> None:
        self._provider = provider
        # Segredos conhecidos da configuração nunca são enviados ao provedor.
        # Isso NÃO detecta dados sensíveis arbitrários digitados pelo usuário.
        self._secrets = tuple(s for s in secrets if s)
        self._history = ConversationHistory(self._redact(system_prompt), max_history_messages)
        self._last_error: AIError | None = None

    @property
    def history(self) -> ConversationHistory:
        return self._history

    def describe(self) -> str:
        """Descrição do estado real da IA, para o comando ``status`` e o cabeçalho."""
        description = f"habilitada ({self._provider.name}, modelo {self._provider.model})"
        if self._last_error is not None:
            description += f"; última tentativa falhou: {self._status_label(self._last_error)}"
        return description

    def _status_label(self, error: AIError) -> str:
        for error_type, label in _STATUS_LABELS:
            if isinstance(error, error_type):
                return label.format(provider=self._provider.name)
        return _FALLBACK_STATUS_LABEL

    def reply(self, message: str) -> str:
        """Retorna a resposta da IA ou levanta ``AIError``. Só sucessos entram no histórico."""
        user_content = self._redact(message.strip())
        context = self._history.with_user_message(user_content)
        started = time.monotonic()
        try:
            raw = self._provider.chat(context)
            if not isinstance(raw, str):
                raise AIResponseError("O provedor não retornou texto.")
            text = sanitize_model_output(raw)
            if not text:
                raise AIResponseError("Resposta vazia após sanitização.")
        except AIError as exc:
            self._last_error = exc
            _logger.info("Falha da IA: %s - %s", type(exc).__name__, exc)
            raise
        except Exception as exc:
            # Falha imprevista do provedor: a sessão continua. O diagnóstico vai só para
            # o arquivo de log (FILE_ONLY) e contém o tipo e os locais da pilha, mas não
            # a mensagem da exceção nem variáveis, que poderiam conter dados da conversa.
            self._last_error = AIProviderError(type(exc).__name__)
            _logger.error(
                "Falha inesperada no provedor %s: %s em %s.",
                self._provider.name,
                type(exc).__name__,
                _stack_locations(exc),
                extra=FILE_ONLY,
            )
            raise self._last_error from exc

        self._last_error = None
        self._history.append_exchange(user_content, text)
        _logger.info(
            "Resposta da IA recebida (%s, modelo %s, %.1fs; entrada %d e resposta %d caracteres).",
            self._provider.name,
            self._provider.model,
            time.monotonic() - started,
            len(user_content),
            len(text),
        )
        return text

    def reset(self) -> None:
        """Descarta o histórico da sessão (a mensagem de sistema é mantida)."""
        self._history.clear()
        self._last_error = None

    def _redact(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, SECRET_PLACEHOLDER)
        return text
