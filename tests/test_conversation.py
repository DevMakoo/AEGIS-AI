from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta

import pytest

from ai.service import AIService
from core.command import Command, CommandContext
from core.command_handlers import build_default_registry
from core.command_registry import CommandRegistry
from core.config import load_config
from core.conversation import UNKNOWN_COMMAND_REPLY, ConversationSession
from core.exceptions import (
    AIModelNotFoundError,
    AIResponseError,
    AITimeoutError,
    AIUnavailableError,
    CommandError,
    SessionClosedError,
)
from core.logging_config import LOG_FILE_NAME, configure_logging
from core.state import ApplicationState, AppStatus
from tests.helpers import FakeProvider


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


def _ai_session(running_state: ApplicationState, provider: FakeProvider) -> ConversationSession:
    service = AIService(provider, system_prompt="regras", max_history_messages=10)
    return ConversationSession(
        build_default_registry(), running_state, app_version="0.1.0", ai=service
    )


def test_commands_keep_priority_over_ai(running_state: ApplicationState) -> None:
    provider = FakeProvider()
    session = _ai_session(running_state, provider)

    for message in ("ajuda", "  STATUS ", "que horas são?", "Dia", "comandos"):
        session.handle(message)

    assert provider.calls == []
    assert session.commands_handled == 5


def test_unknown_input_goes_to_ai_only_when_enabled(running_state: ApplicationState) -> None:
    provider = FakeProvider("Olá! Sou o AEGIS.")
    with_ai = _ai_session(running_state, provider)
    without_ai = ConversationSession(build_default_registry(), running_state, app_version="0.1.0")

    assert with_ai.handle("Bom dia, tudo bem?") == "Olá! Sou o AEGIS."
    assert without_ai.handle("Bom dia, tudo bem?") == UNKNOWN_COMMAND_REPLY
    assert [m.content for m in provider.calls[0]][-1] == "Bom dia, tudo bem?"
    assert with_ai.commands_handled == 0


@pytest.mark.parametrize(
    "error",
    [
        AIUnavailableError("off"),
        AIModelNotFoundError("x"),
        AITimeoutError("t"),
        AIResponseError("r"),
        ZeroDivisionError("bug no provedor"),
    ],
)
def test_ai_failures_keep_session_and_commands_working(
    running_state: ApplicationState, error: BaseException
) -> None:
    session = _ai_session(running_state, FakeProvider(error))

    reply = session.handle("conte uma piada")

    assert reply is not None
    assert "Traceback" not in reply
    assert session.active
    assert (session.handle("hora") or "").startswith("Agora são ")
    assert session.handle("sair") == "Encerrando a sessão. Até logo!"


@pytest.mark.parametrize(
    "model_reply",
    [
        "sair",
        "ajuda",
        "__import__('os').system('calc')",
        "Start-Process notepad",
        r"C:\Windows\System32\calc.exe",
    ],
)
def test_model_reply_is_never_executed_nor_treated_as_command(
    running_state: ApplicationState, monkeypatch: pytest.MonkeyPatch, model_reply: str
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Tentativa de execução externa")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(os, "startfile", forbidden, raising=False)
    session = _ai_session(running_state, FakeProvider(model_reply))

    reply = session.handle("diga algo")

    assert reply == model_reply  # devolvido apenas como texto
    assert session.active  # "sair" vindo do modelo não encerra a sessão
    assert session.commands_handled == 0


def test_status_reports_real_ai_state(running_state: ApplicationState) -> None:
    session = _ai_session(running_state, FakeProvider(AIUnavailableError("off")))
    disabled = ConversationSession(build_default_registry(), running_state, app_version="0.1.0")

    session.handle("olá")
    status = session.handle("status")

    assert status is not None
    assert "Conversa inteligente: habilitada (Falso, modelo modelo-teste)" in status
    assert "última tentativa falhou: Falso inacessível" in status
    assert "Error" not in status
    assert "Conversa inteligente: desativada" in (disabled.handle("status") or "")


@pytest.mark.parametrize("phrase", ["como você está", "Como você está?", "tchau", "Até logo!"])
def test_removed_aliases_now_reach_the_ai(running_state: ApplicationState, phrase: str) -> None:
    provider = FakeProvider("resposta da IA")
    session = _ai_session(running_state, provider)

    assert session.handle(phrase) == "resposta da IA"
    assert session.active
    assert provider.calls[0][-1].content == phrase.strip()
    assert session.commands_handled == 0


@pytest.mark.parametrize("phrase", ["tchau", "até logo", "como você está"])
def test_removed_aliases_are_unknown_without_ai(session: ConversationSession, phrase: str) -> None:
    assert session.handle(phrase) == UNKNOWN_COMMAND_REPLY
    assert session.active


@pytest.mark.parametrize("command", ["sair", "  SAIR ", "Sair!", "encerrar"])
def test_explicit_exit_still_ends_session_with_ai(
    running_state: ApplicationState, command: str
) -> None:
    provider = FakeProvider()
    session = _ai_session(running_state, provider)

    assert session.handle(command) == "Encerrando a sessão. Até logo!"
    assert not session.active
    assert provider.calls == []


def test_status_alias_estado_still_works(running_state: ApplicationState) -> None:
    session = _ai_session(running_state, FakeProvider())

    assert (session.handle("estado") or "").startswith("Estou funcionando normalmente.")


def test_closing_session_discards_ai_history(running_state: ApplicationState) -> None:
    service = AIService(FakeProvider("r"), system_prompt="regras", max_history_messages=10)
    session = ConversationSession(
        build_default_registry(), running_state, app_version="0.1.0", ai=service
    )
    session.handle("pergunta")
    assert len(service.history) == 2

    session.handle("sair")

    assert len(service.history) == 0


def test_ai_flow_logs_sizes_but_not_contents(
    test_environ: dict[str, str], running_state: ApplicationState
) -> None:
    config = load_config(environ=test_environ, env_file=None)
    configure_logging(config)
    session = _ai_session(running_state, FakeProvider("RESPOSTA-PRIVADA"))

    session.handle("MENSAGEM-PRIVADA do usuário")
    session.handle("sair")

    content = (config.log_dir / LOG_FILE_NAME).read_text(encoding="utf-8")
    assert "Entrada encaminhada à IA (27 caracteres)." in content
    assert "PRIVADA" not in content
