from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from core.command import CommandContext
from core.command_handlers import (
    DEFAULT_COMMANDS,
    build_default_registry,
    format_date_pt_br,
    format_duration,
    handle_date,
    handle_exit,
    handle_help,
    handle_status,
    handle_time,
)
from core.state import AppStatus

FIXED_NOW = datetime(2026, 10, 13, 14, 5, 30)


def _context(
    *,
    now: datetime = FIXED_NOW,
    status: AppStatus = AppStatus.RUNNING,
    started_at: datetime | None = None,
    handled: int = 0,
) -> CommandContext:
    return CommandContext(
        now=now,
        app_version="9.9.9",
        app_status=status,
        session_started_at=now if started_at is None else started_at,
        commands_handled=handled,
        available_commands=DEFAULT_COMMANDS,
    )


def test_default_registry_has_the_five_basic_commands() -> None:
    registry = build_default_registry()

    assert [c.name for c in registry.commands] == ["ajuda", "status", "hora", "data", "sair"]
    assert [c.name for c in registry.commands if c.ends_session] == ["sair"]


def test_help_lists_every_command_with_description_and_aliases() -> None:
    reply = handle_help(_context())

    assert reply.startswith("Estes são os comandos disponíveis:")
    for command in DEFAULT_COMMANDS:
        assert f"- {command.name}: {command.description}" in reply
        for alias in command.aliases:
            assert alias in reply


def test_status_when_running() -> None:
    reply = handle_status(
        _context(started_at=FIXED_NOW - timedelta(minutes=3), handled=2),
    )

    assert reply.startswith("Estou funcionando normalmente.")
    assert "Versão: 9.9.9" in reply
    assert "Estado: em execução" in reply
    assert "Sessão ativa há 3 minutos" in reply
    assert "Comandos atendidos nesta sessão: 2" in reply


def test_status_does_not_claim_normal_operation_when_not_running() -> None:
    reply = handle_status(_context(status=AppStatus.STOPPING))

    assert "funcionando normalmente" not in reply
    assert "encerrando" in reply


def test_time_uses_injected_clock() -> None:
    assert handle_time(_context()) == "Agora são 14:05."
    assert handle_time(_context(now=datetime(2026, 1, 2, 7, 9))) == "Agora são 07:09."


def test_date_in_brazilian_portuguese() -> None:
    assert handle_date(_context()) == "Hoje é terça-feira, 13 de outubro de 2026."


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 3, 1), "domingo, 1º de março de 2026"),
        (date(2026, 12, 31), "quinta-feira, 31 de dezembro de 2026"),
        (date(2024, 2, 29), "quinta-feira, 29 de fevereiro de 2024"),
    ],
)
def test_format_date_pt_br(day: date, expected: str) -> None:
    assert format_date_pt_br(day) == expected


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        (timedelta(seconds=59), "há menos de um minuto"),
        (timedelta(seconds=-5), "há menos de um minuto"),
        (timedelta(minutes=1), "há 1 minuto"),
        (timedelta(minutes=60), "há 1 hora"),
        (timedelta(hours=2, minutes=5), "há 2 horas e 5 minutos"),
    ],
)
def test_format_duration(elapsed: timedelta, expected: str) -> None:
    assert format_duration(elapsed) == expected


def test_exit_message() -> None:
    assert handle_exit(_context()) == "Encerrando a sessão. Até logo!"
