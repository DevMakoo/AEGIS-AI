from __future__ import annotations

import pytest

from core.command import Command, CommandContext, normalize_text
from core.command_registry import CommandRegistry
from core.exceptions import CommandRegistrationError


def _noop(context: CommandContext) -> str:
    return "ok"


def _command(name: str, *aliases: str, description: str = "Descrição.") -> Command:
    return Command(name=name, description=description, handler=_noop, aliases=aliases)


@pytest.fixture
def registry() -> CommandRegistry:
    registry = CommandRegistry()
    registry.register(_command("ajuda", "comandos"))
    registry.register(_command("hora", "que horas são"))
    return registry


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ajuda", "ajuda"),
        ("  AJUDA  ", "ajuda"),
        ("\tStatus\n", "status"),
        ("Que   Horas  São?", "que horas sao"),
        ("ajuda!!!", "ajuda"),
        ("", ""),
        ("   ", ""),
        (" ...? ", ""),
    ],
)
def test_normalize_text(raw: str, expected: str) -> None:
    assert normalize_text(raw) == expected


def test_register_keeps_order_and_size(registry: CommandRegistry) -> None:
    assert [c.name for c in registry.commands] == ["ajuda", "hora"]
    assert len(registry) == 2


@pytest.mark.parametrize("text", ["ajuda", "comandos", "hora", "que horas são"])
def test_resolve_name_and_aliases(registry: CommandRegistry, text: str) -> None:
    command = registry.resolve(text)

    assert command is not None
    assert text in (command.name, *command.aliases)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("  AJUDA ", "ajuda"),
        ("Comandos", "comandos"),
        ("  QUE   horas   sao?  ", "hora"),
        ("Hora.", "hora"),
    ],
)
def test_resolve_normalizes_spaces_case_and_accents(
    registry: CommandRegistry, text: str, expected: str
) -> None:
    command = registry.resolve(text)

    assert command is not None
    assert expected in (command.name, *command.aliases)


def test_resolution_is_deterministic(registry: CommandRegistry) -> None:
    results = {id(registry.resolve(" Que horas são ")) for _ in range(10)}

    assert len(results) == 1


@pytest.mark.parametrize("text", ["ajud", "ajudaa", "ajuda agora", "a juda", "horas?!x", "help"])
def test_no_approximate_matching(registry: CommandRegistry, text: str) -> None:
    assert registry.resolve(text) is None


def test_duplicate_name_is_rejected(registry: CommandRegistry) -> None:
    with pytest.raises(CommandRegistrationError, match="Já existe"):
        registry.register(_command("  AJUDA "))


def test_alias_conflicting_with_existing_name_is_rejected(registry: CommandRegistry) -> None:
    with pytest.raises(CommandRegistrationError, match="conflita"):
        registry.register(_command("socorro", "Ajuda"))


def test_alias_conflicting_with_existing_alias_is_rejected(registry: CommandRegistry) -> None:
    with pytest.raises(CommandRegistrationError, match="conflita"):
        registry.register(_command("relogio", "que horas sao"))


def test_name_conflicting_with_existing_alias_is_rejected(registry: CommandRegistry) -> None:
    with pytest.raises(CommandRegistrationError, match="conflita"):
        registry.register(_command("comandos"))


def test_alias_repeated_within_command_is_rejected() -> None:
    with pytest.raises(CommandRegistrationError, match="repete"):
        CommandRegistry().register(_command("data", "dia", "DIA"))


def test_failed_registration_leaves_registry_unchanged(registry: CommandRegistry) -> None:
    with pytest.raises(CommandRegistrationError):
        registry.register(_command("novo", "livre", "comandos"))

    assert len(registry) == 2
    assert registry.resolve("novo") is None
    assert registry.resolve("livre") is None


@pytest.mark.parametrize(
    "command",
    [
        _command("   "),
        _command("vazio", "  "),
        _command("sem descricao", description="  "),
    ],
)
def test_invalid_commands_are_rejected(command: Command) -> None:
    with pytest.raises(CommandRegistrationError):
        CommandRegistry().register(command)
