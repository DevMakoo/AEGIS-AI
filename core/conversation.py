"""Processamento de mensagens e controle da sessão de conversa.

Independe da interface: terminal hoje, interface gráfica ou voz no futuro.

Ordem de decisão para cada mensagem:
1. Entrada vazia: ignorada.
2. Comando registrado (correspondência exata após normalização): executa o handler.
3. Caso contrário, se a IA estiver disponível: a mensagem vai para a IA, cuja
   resposta é devolvida apenas como texto — nunca reprocessada como comando.
4. Sem IA: informa que o comando não foi reconhecido.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from ai.service import AI_DISABLED_DESCRIPTION, AIService, user_message_for
from core.command import CommandContext, normalize_text
from core.command_registry import CommandRegistry
from core.exceptions import AIError, CommandError, SessionClosedError
from core.logging_config import get_logger
from core.state import ApplicationState

UNKNOWN_COMMAND_REPLY = (
    "Não reconheci esse comando, e a conversa inteligente não está disponível. "
    'Digite "ajuda" para ver as opções.'
)

_logger = get_logger("conversation")


class ConversationSession:
    """Recebe uma mensagem por vez; comandos registrados têm prioridade sobre a IA."""

    def __init__(
        self,
        registry: CommandRegistry,
        app_state: ApplicationState,
        *,
        app_version: str,
        clock: Callable[[], datetime] = datetime.now,
        ai: AIService | None = None,
        ai_unavailable_description: str = AI_DISABLED_DESCRIPTION,
    ) -> None:
        self._registry = registry
        self._app_state = app_state
        self._app_version = app_version
        self._clock = clock
        self._ai = ai
        self._ai_unavailable_description = ai_unavailable_description
        self._started_at = clock()
        self._commands_handled = 0
        self._active = True
        _logger.info(
            "Sessão de conversa iniciada (%d comandos autorizados; IA %s).",
            len(registry),
            "habilitada" if ai is not None else "indisponível",
        )

    @property
    def active(self) -> bool:
        return self._active

    @property
    def commands_handled(self) -> int:
        return self._commands_handled

    @property
    def ai_status(self) -> str:
        return self._ai.describe() if self._ai is not None else self._ai_unavailable_description

    def handle(self, message: str) -> str | None:
        """Processa a mensagem e retorna a resposta, ou ``None`` para entrada vazia."""
        if not self._active:
            raise SessionClosedError("A sessão de conversa já foi encerrada.")
        if not normalize_text(message):
            return None

        command = self._registry.resolve(message)
        if command is None:
            return self._handle_free_text(message)

        _logger.info("Comando reconhecido: %s.", command.name)
        context = CommandContext(
            now=self._clock(),
            app_version=self._app_version,
            app_status=self._app_state.status,
            session_started_at=self._started_at,
            commands_handled=self._commands_handled,
            available_commands=self._registry.commands,
            ai_status=self.ai_status,
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

    def _handle_free_text(self, message: str) -> str:
        # O conteúdo digitado não é registrado; apenas o tamanho, para diagnóstico.
        size = len(message.strip())
        if self._ai is None:
            _logger.info("Entrada não reconhecida (%d caracteres); IA indisponível.", size)
            return UNKNOWN_COMMAND_REPLY
        _logger.info("Entrada encaminhada à IA (%d caracteres).", size)
        try:
            return self._ai.reply(message)
        except AIError as exc:
            return user_message_for(exc)

    def close(self, reason: str) -> None:
        """Encerra a sessão e descarta o histórico da IA. Chamadas repetidas são ignoradas."""
        if not self._active:
            return
        self._active = False
        if self._ai is not None:
            self._ai.reset()
        _logger.info(
            "Sessão de conversa encerrada (motivo: %s; comandos atendidos: %d).",
            reason,
            self._commands_handled,
        )
