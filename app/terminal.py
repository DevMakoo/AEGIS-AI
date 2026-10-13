"""Interface textual interativa. Só lê e escreve; a lógica fica em ``ConversationSession``."""

from __future__ import annotations

from collections.abc import Callable

from core.conversation import ConversationSession
from core.logging_config import get_logger

type InputFn = Callable[[str], str]
type OutputFn = Callable[[str], None]

USER_PROMPT = "Você: "
SPEAKER = "AEGIS"
CANCELLED_REPLY = 'Resposta cancelada. A sessão continua: digite outra mensagem ou "sair".'

_logger = get_logger("terminal")


def run_terminal(
    session: ConversationSession,
    *,
    title: str,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
) -> None:
    """Executa o loop de conversa até a sessão terminar, EOF ou Ctrl+C no prompt.

    Ctrl+C no prompt encerra a sessão. Ctrl+C durante o processamento de uma
    mensagem (ex.: aguardando a IA) cancela só aquela resposta e a sessão continua.
    """
    output_fn(title)
    output_fn("Sistema inicializado.")
    output_fn(f"Conversa inteligente: {session.ai_status}.")
    output_fn('Digite "ajuda" para conhecer os comandos disponíveis.')

    while session.active:
        try:
            message = input_fn(f"\n{USER_PROMPT}")
        except EOFError:
            session.close("fim da entrada (EOF)")
            _say(output_fn, "Entrada encerrada. Até logo!")
            return
        except KeyboardInterrupt:
            session.close("interrupção pelo teclado")
            _say(output_fn, "Sessão interrompida. Até logo!")
            return

        try:
            reply = session.handle(message)
        except KeyboardInterrupt:
            # A exceção já desfez a operação em andamento (o urllib fecha a conexão
            # HTTP); nada foi gravado no histórico da IA.
            _logger.info("Processamento de mensagem cancelado pelo usuário (Ctrl+C).")
            _say(output_fn, CANCELLED_REPLY)
            continue
        if reply is not None:
            _say(output_fn, reply)


def _say(output_fn: OutputFn, message: str) -> None:
    output_fn(f"\n{SPEAKER}: {message}")
