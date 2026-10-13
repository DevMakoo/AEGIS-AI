from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta

import pytest

from core.command import Command, CommandContext
from core.command_handlers import build_default_registry
from core.command_registry import CommandRegistry
from core.config import load_config
from core.conversation import UNKNOWN_COMMAND_REPLY, ConversationSession
from core.exceptions import CommandError, SessionClosedError
from core.logging_config import LOG_FILE_NAME, configure_logging
from core.state import ApplicationState, AppStatus


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 10, 13, 14, 5))


@pytest.fixture
def running_state() -> ApplicationState:
    state = ApplicationState()
    state.transition_to(AppStatus.STARTING)
    state.transition_to(AppStatus.RUNNING)
    return state


@pytest.fixture
def session(running_state: ApplicationState, clock: FakeClock) -> ConversationSession:
    return ConversationSession(
        build_default_registry(), running_state, app_version="0.1.0", clock=clock
    )


@pytest.mark.parametrize("message", ["", "   ", "\t\n", "..."])
def test_empty_input_is_ignored(session: ConversationSession, message: str) -> None:
    assert session.handle(message) is None
    assert session.active
    assert session.commands_handled == 0


def test_unknown_command_keeps_session_running(session: ConversationSession) -> None:
    assert session.handle("abrir o navegador") == UNKNOWN_COMMAND_REPLY
    assert session.active
    assert session.handle("hora") == "Agora são 14:05."


def test_commands_resolved_by_alias_and_normalized_input(session: ConversationSession) -> None:
    assert session.handle("  QUE horas   SÃO? ") == "Agora são 14:05."
    assert session.handle("Dia") == "Hoje é terça-feira, 13 de outubro de 2026."


def test_status_reflects_real_session_data(session: ConversationSession, clock: FakeClock) -> None:
    session.handle("hora")
    clock.now += timedelta(minutes=2)

    reply = session.handle("status")

    assert reply is not None
    assert "Estou funcionando normalmente." in reply
    assert "Versão: 0.1.0" in reply
    assert "há 2 minutos" in reply
    assert "Comandos atendidos nesta sessão: 1" in reply


def test_exit_closes_session(session: ConversationSession) -> None:
    assert session.handle("sair") == "Encerrando a sessão. Até logo!"
    assert not session.active

    with pytest.raises(SessionClosedError):
        session.handle("hora")


def test_close_is_idempotent(session: ConversationSession) -> None:
    session.close("teste")
    session.close("teste")

    assert not session.active


def _session_with(handler_error: Exception, running_state: ApplicationState) -> ConversationSession:
    def failing(context: CommandContext) -> str:
        raise handler_error

    registry = CommandRegistry()
    registry.register(Command(name="falhar", description="Sempre falha.", handler=failing))
    return ConversationSession(registry, running_state, app_version="0.1.0")


def test_expected_command_error_becomes_friendly_reply(running_state: ApplicationState) -> None:
    session = _session_with(CommandError("recurso indisponível"), running_state)

    reply = session.handle("falhar")

    assert reply == "Não consegui concluir o comando 'falhar': recurso indisponível"
    assert session.active


def test_programming_errors_are_not_hidden(running_state: ApplicationState) -> None:
    session = _session_with(ValueError("bug"), running_state)

    with pytest.raises(ValueError, match="bug"):
        session.handle("falhar")


# Strings de ataque usadas apenas como DADOS de entrada: o teste garante que nunca
# são avaliadas nem executadas (os sinks de execução são substituídos por falhas).
@pytest.mark.parametrize(
    "message",
    [
        "__import__('os').system('calc')",
        "eval('1+1')",
        "import os; os.system('notepad')",
        "exec(\"print('x')\")",
        "rm -rf /",
        "del /s /q C:\\",
        "Start-Process notepad",
        "powershell -Command Get-Process",
        "cmd /c dir",
        "C:\\Windows\\System32\\calc.exe",
        "notepad.exe",
        "ajuda; sair",
        "ajuda && calc",
        "hora | calc",
        "$(sair)",
        "`hora`",
    ],
)
def test_arbitrary_input_is_never_executed(
    session: ConversationSession, monkeypatch: pytest.MonkeyPatch, message: str
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Tentativa de execução externa")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(os, "startfile", forbidden, raising=False)

    assert session.handle(message) == UNKNOWN_COMMAND_REPLY
    assert session.active
    assert session.commands_handled == 0


def test_logs_record_commands_but_not_user_text(
    test_environ: dict[str, str], running_state: ApplicationState
) -> None:
    config = load_config(environ=test_environ, env_file=None)
    configure_logging(config)
    session = ConversationSession(build_default_registry(), running_state, app_version="0.1.0")

    session.handle("minha senha é hunter2")
    session.handle("hora")
    session.handle("sair")

    content = (config.log_dir / LOG_FILE_NAME).read_text(encoding="utf-8")
    assert "Sessão de conversa iniciada" in content
    assert "Comando reconhecido: hora." in content
    assert "Sessão de conversa encerrada" in content
    assert "hunter2" not in content
    assert "senha" not in content
