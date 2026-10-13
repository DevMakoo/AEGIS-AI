"""Comandos básicos do AEGIS e montagem do registro padrão."""

from __future__ import annotations

from datetime import date, timedelta

from core.command import Command, CommandContext
from core.command_registry import CommandRegistry
from core.state import AppStatus

_WEEKDAYS = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)
_MONTHS = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)
_STATUS_LABELS = {
    AppStatus.CREATED: "criado",
    AppStatus.STARTING: "inicializando",
    AppStatus.RUNNING: "em execução",
    AppStatus.STOPPING: "encerrando",
    AppStatus.STOPPED: "encerrado",
    AppStatus.FAILED: "com falha",
}


def format_date_pt_br(day: date) -> str:
    """Ex.: ``terça-feira, 13 de outubro de 2026`` (independe do locale do sistema)."""
    day_number = "1º" if day.day == 1 else str(day.day)
    return f"{_WEEKDAYS[day.weekday()]}, {day_number} de {_MONTHS[day.month - 1]} de {day.year}"


def format_duration(elapsed: timedelta) -> str:
    """Ex.: ``há menos de um minuto``, ``há 1 hora e 5 minutos``."""
    total_minutes = max(0, int(elapsed.total_seconds() // 60))
    if total_minutes == 0:
        return "há menos de um minuto"
    hours, minutes = divmod(total_minutes, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} hora" + ("s" if hours > 1 else ""))
    if minutes:
        parts.append(f"{minutes} minuto" + ("s" if minutes > 1 else ""))
    return "há " + " e ".join(parts)


def handle_help(context: CommandContext) -> str:
    lines = ["Estes são os comandos disponíveis:"]
    for command in context.available_commands:
        line = f"- {command.name}: {command.description}"
        if command.aliases:
            line += f" (também: {', '.join(command.aliases)})"
        lines.append(line)
    return "\n".join(lines)


def handle_status(context: CommandContext) -> str:
    label = _STATUS_LABELS.get(context.app_status, str(context.app_status))
    if context.app_status is AppStatus.RUNNING:
        headline = "Estou funcionando normalmente."
    else:
        headline = f"Atenção: meu estado atual é '{label}'."
    return "\n".join(
        [
            headline,
            f"- Versão: {context.app_version}",
            f"- Estado: {label}",
            f"- Sessão ativa {format_duration(context.now - context.session_started_at)}",
            f"- Comandos atendidos nesta sessão: {context.commands_handled}",
        ]
    )


def handle_time(context: CommandContext) -> str:
    return f"Agora são {context.now:%H:%M}."


def handle_date(context: CommandContext) -> str:
    return f"Hoje é {format_date_pt_br(context.now.date())}."


def handle_exit(context: CommandContext) -> str:
    return "Encerrando a sessão. Até logo!"


DEFAULT_COMMANDS: tuple[Command, ...] = (
    Command(
        name="ajuda",
        description="Lista os comandos disponíveis.",
        handler=handle_help,
        aliases=("comandos", "lista de comandos"),
    ),
    Command(
        name="status",
        description="Mostra o estado atual do AEGIS.",
        handler=handle_status,
        aliases=("estado", "como você está"),
    ),
    Command(
        name="hora",
        description="Informa a hora local.",
        handler=handle_time,
        aliases=("horas", "que horas são"),
    ),
    Command(
        name="data",
        description="Informa a data de hoje.",
        handler=handle_date,
        aliases=("dia", "que dia é hoje"),
    ),
    Command(
        name="sair",
        description="Encerra a sessão.",
        handler=handle_exit,
        aliases=("encerrar", "tchau", "até logo"),
        ends_session=True,
    ),
)


def build_default_registry() -> CommandRegistry:
    """Registro com os comandos básicos autorizados nesta fase."""
    registry = CommandRegistry()
    for command in DEFAULT_COMMANDS:
        registry.register(command)
    return registry
