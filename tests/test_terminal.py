from __future__ import annotations

import http.client
import json
from collections.abc import Callable, Iterable

import pytest

import ai.ollama
from ai.service import AIService
from app import APP_NAME, __version__
from app.main import EXIT_CONFIG_ERROR, EXIT_INTERRUPTED, EXIT_OK, main
from app.terminal import CANCELLED_REPLY, USER_PROMPT, run_terminal
from core.command_handlers import build_default_registry
from core.conversation import UNKNOWN_COMMAND_REPLY, ConversationSession
from core.logging_config import get_logger
from core.state import ApplicationState, AppStatus
from tests.helpers import FakeOpener, FakeProvider, ScriptedInput

type MakeInput = Callable[[Iterable[str]], ScriptedInput]


@pytest.fixture
def session() -> ConversationSession:
    state = ApplicationState()
    state.transition_to(AppStatus.STARTING)
    state.transition_to(AppStatus.RUNNING)
    return ConversationSession(build_default_registry(), state, app_version="0.1.0")


def _run(session: ConversationSession, input_fn: Callable[[str], str]) -> list[str]:
    output: list[str] = []
    run_terminal(session, title="AEGIS vX", input_fn=input_fn, output_fn=output.append)
    return output


def test_loop_integrates_with_registered_commands(
    session: ConversationSession, scripted_input: MakeInput
) -> None:
    input_fn = scripted_input(["ajuda", "  ", "xyz", "STATUS", "sair", "hora"])

    output = _run(session, input_fn)

    assert output[:4] == [
        "AEGIS vX",
        "Sistema inicializado.",
        "Conversa inteligente: desativada (AEGIS_AI_ENABLED=false).",
        'Digite "ajuda" para conhecer os comandos disponíveis.',
    ]
    replies = output[4:]
    assert replies[0].startswith("\nAEGIS: Estes são os comandos disponíveis:")
    assert replies[1] == f"\nAEGIS: {UNKNOWN_COMMAND_REPLY}"
    assert replies[2].startswith("\nAEGIS: Estou funcionando normalmente.")
    assert replies[3] == "\nAEGIS: Encerrando a sessão. Até logo!"
    assert len(replies) == 4  # a entrada vazia não gera resposta
    assert input_fn.remaining == ["hora"]  # nada é lido depois de "sair"
    assert all(prompt.endswith(USER_PROMPT) for prompt in input_fn.prompts)
    assert not session.active


def test_eof_ends_session_cleanly(session: ConversationSession, scripted_input: MakeInput) -> None:
    output = _run(session, scripted_input(["hora"]))

    assert output[-1] == "\nAEGIS: Entrada encerrada. Até logo!"
    assert not session.active


def test_keyboard_interrupt_ends_session_cleanly(session: ConversationSession) -> None:
    def interrupt(prompt: str) -> str:
        raise KeyboardInterrupt

    output = _run(session, interrupt)

    assert output[-1] == "\nAEGIS: Sessão interrompida. Até logo!"
    assert not session.active


def _ai_terminal_session(provider: FakeProvider) -> tuple[ConversationSession, AIService]:
    state = ApplicationState()
    state.transition_to(AppStatus.STARTING)
    state.transition_to(AppStatus.RUNNING)
    service = AIService(provider, system_prompt="regras", max_history_messages=10)
    session = ConversationSession(build_default_registry(), state, app_version="0.1.0", ai=service)
    return session, service


def test_ctrl_c_during_ai_reply_cancels_only_that_reply(scripted_input: MakeInput) -> None:
    provider = FakeProvider("primeira", KeyboardInterrupt(), "terceira")
    session, service = _ai_terminal_session(provider)
    input_fn = scripted_input(["p1", "p2 demorada", "p3", "hora", "sair"])

    output = _run(session, input_fn)

    replies = output[4:]
    assert replies[0] == "\nAEGIS: primeira"
    assert replies[1] == f"\nAEGIS: {CANCELLED_REPLY}"
    assert replies[2] == "\nAEGIS: terceira"  # a sessão continuou
    assert replies[3].startswith("\nAEGIS: Agora são ")
    assert replies[-1] == "\nAEGIS: Encerrando a sessão. Até logo!"
    assert not any("Traceback" in line or "KeyboardInterrupt" in line for line in output)
    # A mensagem cancelada não entrou no histórico; a seguinte vê só p1/r1.
    assert [m.content for m in provider.calls[2]] == ["regras", "p1", "primeira", "p3"]
    assert input_fn.remaining == []


def test_ctrl_c_at_prompt_still_ends_session_with_ai_enabled() -> None:
    session, service = _ai_terminal_session(FakeProvider())

    def interrupt(prompt: str) -> str:
        raise KeyboardInterrupt

    output = _run(session, interrupt)

    assert output[-1] == "\nAEGIS: Sessão interrompida. Até logo!"
    assert not session.active
    assert len(service.history) == 0


def test_main_runs_session_and_shuts_down(
    test_environ: dict[str, str], scripted_input: MakeInput
) -> None:
    output: list[str] = []

    exit_code = main(
        environ=test_environ,
        env_file=None,
        input_fn=scripted_input(["data", "sair"]),
        output_fn=output.append,
    )

    assert exit_code == EXIT_OK
    assert output[0] == f"{APP_NAME} v{__version__}"
    assert any(line.startswith("\nAEGIS: Hoje é ") for line in output)
    assert output[-1] == "\nAEGIS: Encerrando a sessão. Até logo!"
    assert not get_logger().handlers  # app.shutdown() foi executado


def test_main_handles_interrupt_outside_input(
    test_environ: dict[str, str], scripted_input: MakeInput
) -> None:
    def interrupt_on_reply(text: str) -> None:
        if text.startswith("\nAEGIS:"):
            raise KeyboardInterrupt

    exit_code = main(
        environ=test_environ,
        env_file=None,
        input_fn=scripted_input(["hora"]),
        output_fn=interrupt_on_reply,
    )

    assert exit_code == EXIT_INTERRUPTED
    assert not get_logger().handlers


def _ai_environ(test_environ: dict[str, str], **extra: str) -> dict[str, str]:
    return {**test_environ, "AEGIS_AI_ENABLED": "true", "AEGIS_OLLAMA_MODEL": "llama3.2", **extra}


def test_main_with_ollama_stopped_keeps_commands_working(
    test_environ: dict[str, str], scripted_input: MakeInput, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refused(self: http.client.HTTPConnection) -> None:
        raise ConnectionRefusedError(10061, "conexão recusada")

    monkeypatch.setattr(http.client.HTTPConnection, "connect", refused)
    output: list[str] = []

    exit_code = main(
        environ=_ai_environ(test_environ),
        env_file=None,
        input_fn=scripted_input(["olá, tudo bem?", "hora", "sair"]),
        output_fn=output.append,
    )

    assert exit_code == EXIT_OK
    assert "Conversa inteligente: habilitada (Ollama, modelo llama3.2)." in output
    assert any("Não consegui falar com o Ollama" in line for line in output)
    assert any(line.startswith("\nAEGIS: Agora são ") for line in output)
    assert not any("Traceback" in line for line in output)
    assert output[-1] == "\nAEGIS: Encerrando a sessão. Até logo!"


def test_main_hybrid_flow_with_simulated_ollama(
    test_environ: dict[str, str], scripted_input: MakeInput, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = json.dumps({"message": {"role": "assistant", "content": "Oi! Sou o AEGIS."}})
    opener = FakeOpener(body.encode("utf-8"))
    monkeypatch.setattr(ai.ollama, "build_direct_opener", lambda: opener)
    output: list[str] = []

    exit_code = main(
        environ=_ai_environ(test_environ),
        env_file=None,
        input_fn=scripted_input(["oi", "data", "sair"]),
        output_fn=output.append,
    )

    assert exit_code == EXIT_OK
    assert "\nAEGIS: Oi! Sou o AEGIS." in output
    assert any(line.startswith("\nAEGIS: Hoje é ") for line in output)
    assert len(opener.requests) == 1  # "data" e "sair" não foram para a IA


def test_main_with_ai_enabled_but_no_model_runs_in_command_mode(
    test_environ: dict[str, str], scripted_input: MakeInput
) -> None:
    output: list[str] = []
    environ = {**test_environ, "AEGIS_AI_ENABLED": "true"}

    exit_code = main(
        environ=environ,
        env_file=None,
        input_fn=scripted_input(["olá", "sair"]),
        output_fn=output.append,
    )

    assert exit_code == EXIT_OK
    assert "Conversa inteligente: indisponível (defina AEGIS_OLLAMA_MODEL)." in output
    assert f"\nAEGIS: {UNKNOWN_COMMAND_REPLY}" in output


@pytest.mark.parametrize(
    "extra",
    [
        {"AEGIS_AI_PROVIDER": "openai"},
        {"AEGIS_OLLAMA_BASE_URL": "https://ollama.exemplo.com"},
        {"AEGIS_AI_TIMEOUT_SECONDS": "abc"},
    ],
)
def test_main_rejects_invalid_ai_config_with_exit_code_2(
    test_environ: dict[str, str], capsys: pytest.CaptureFixture[str], extra: dict[str, str]
) -> None:
    exit_code = main(environ={**test_environ, **extra}, env_file=None)

    assert exit_code == EXIT_CONFIG_ERROR
    assert "Erro de configuração" in capsys.readouterr().err
