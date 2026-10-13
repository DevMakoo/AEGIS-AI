from __future__ import annotations

from collections.abc import Callable, Iterable

import pytest

from app import APP_NAME, __version__
from app.main import EXIT_INTERRUPTED, EXIT_OK, main
from app.terminal import USER_PROMPT, run_terminal
from core.command_handlers import build_default_registry
from core.conversation import UNKNOWN_COMMAND_REPLY, ConversationSession
from core.logging_config import get_logger
from core.state import ApplicationState, AppStatus
from tests.conftest import ScriptedInput

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

    assert output[:3] == [
        "AEGIS vX",
        "Sistema inicializado.",
        'Digite "ajuda" para conhecer os comandos disponíveis.',
    ]
    replies = output[3:]
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
