"""Processamento de mensagens e controle da sessão de conversa.

Independe da interface: terminal hoje, interface gráfica ou voz no futuro.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from core.command import CommandContext, normalize_text
from core.command_registry import CommandRegistry
from core.exceptions import CommandError, SessionClosedError
from core.logging_config import get_logger
from core.state import ApplicationState

UNKNOWN_COMMAND_REPLY = 'Não reconheci esse comando. Digite "ajuda" para ver as opções.'

_logger = get_logger("conversation")


class ConversationSession:
    """Recebe uma mensagem por vez e responde usando apenas comandos registrados."""

    def __init__(
        self,
        registry: CommandRegistry,
        app_state: ApplicationState,
        *,
        app_version: str,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._registry = registry
        self._app_state = app_state
        self._app_version = app_version
        self._clock = clock
        self._started_at = clock()
        self._commands_handled = 0
        self._active = True
        _logger.info("Sessão de conversa iniciada (%d comandos autorizados).", len(registry))

    @property
    def active(self) -> bool:
        return self._active

    @property
    def commands_handled(self) -> int:
        return self._commands_handled

    def handle(self, message: str) -> str | None:
        """Processa a mensagem e retorna a resposta, ou ``None`` para entrada vazia."""
        if not self._active:
            raise SessionClosedError("A sessão de conversa já foi encerrada.")
        if not normalize_text(message):
            return None

        command = self._registry.resolve(message)
        if command is None:
            # O conteúdo digitado não é registrado; apenas o tamanho, para diagnóstico.
            _logger.info("Entrada não reconhecida (%d caracteres).", len(message.strip()))
            return UNKNOWN_COMMAND_REPLY

        _logger.info("Comando reconhecido: %s.", command.name)
        context = CommandContext(
            now=self._clock(),
            app_version=self._app_version,
            app_status=self._app_state.status,
            session_started_at=self._started_at,
            commands_handled=self._commands_handled,
            available_commands=self._registry.commands,
        )
        try:
            reply = command.handler(context)
        except CommandError as exc:
            _logger.warning("Falha no comando %s: %s", command.name, exc)
            reply = f"Não consegui concluir o comando '{command.name}': {exc}"

        self._commands_handled += 1
        if command.ends_session:
            self.close(f"comando '{command.name}'")
        return reply

    def close(self, reason: str) -> None:
        """Encerra a sessão. Chamadas repetidas são ignoradas."""
        if not self._active:
            return
        self._active = False
        _logger.info(
            "Sessão de conversa encerrada (motivo: %s; comandos atendidos: %d).",
            reason,
            self._commands_handled,
        )
