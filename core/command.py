"""Modelos e contratos dos comandos autorizados do AEGIS."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from core.state import AppStatus

_TRAILING_PUNCTUATION = ".!?…"


def normalize_text(text: str) -> str:
    """Forma canônica usada para comparar entradas com nomes e aliases.

    Ignora maiúsculas/minúsculas, acentos, espaços excedentes e pontuação final
    (``"  Que HORAS são? "`` -> ``"que horas sao"``). Não há correspondência
    aproximada: depois de normalizada, a entrada precisa ser idêntica.
    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    collapsed = " ".join(without_accents.split())
    return collapsed.rstrip(_TRAILING_PUNCTUATION).rstrip()


@dataclass(frozen=True, slots=True)
class CommandContext:
    """Informações somente leitura disponíveis para um comando."""

    now: datetime
    app_version: str
    app_status: AppStatus
    session_started_at: datetime
    commands_handled: int
    available_commands: tuple[Command, ...]
    ai_status: str = "desativada"


type CommandHandler = Callable[[CommandContext], str]


@dataclass(frozen=True, slots=True)
class Command:
    """Comando autorizado: só é executável depois de entrar no ``CommandRegistry``."""

    name: str
    description: str
    handler: CommandHandler
    aliases: tuple[str, ...] = ()
    ends_session: bool = False
