"""Interface textual interativa. Só lê e escreve; a lógica fica em ``ConversationSession``."""

from __future__ import annotations

from collections.abc import Callable

from core.conversation import ConversationSession

type InputFn = Callable[[str], str]
type OutputFn = Callable[[str], None]

USER_PROMPT = "Você: "
SPEAKER = "AEGIS"


def run_terminal(
    session: ConversationSession,
    *,
    title: str,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
) -> None:
    """Executa o loop de conversa até a sessão terminar, EOF ou Ctrl+C."""
    output_fn(title)
    output_fn("Sistema inicializado.")
    output_fn('Digite "ajuda" para conhecer os comandos disponíveis.')

    while session.active:
        try:
            message = input_fn(f"\n{USER_PROMPT}")
            reply = session.handle(message)
        except EOFError:
            session.close("fim da entrada (EOF)")
            _say(output_fn, "Entrada encerrada. Até logo!")
            return
        except KeyboardInterrupt:
            session.close("interrupção pelo teclado")
            _say(output_fn, "Sessão interrompida. Até logo!")
            return
        if reply is not None:
            _say(output_fn, reply)


def _say(output_fn: OutputFn, message: str) -> None:
    output_fn(f"\n{SPEAKER}: {message}")
