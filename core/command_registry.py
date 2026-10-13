"""Registro central e única fonte de comandos autorizados."""

from __future__ import annotations

from core.command import Command, normalize_text
from core.exceptions import CommandRegistrationError


class CommandRegistry:
    """Associa nomes e aliases normalizados a comandos autorizados.

    A resolução é por igualdade exata após ``normalize_text``: não há
    correspondência aproximada, avaliação de código nem execução de entradas
    que não estejam registradas.
    """

    def __init__(self) -> None:
        self._commands: list[Command] = []
        self._index: dict[str, Command] = {}

    @property
    def commands(self) -> tuple[Command, ...]:
        """Comandos na ordem de registro."""
        return tuple(self._commands)

    def __len__(self) -> int:
        return len(self._commands)

    def register(self, command: Command) -> None:
        """Registra o comando; nada é alterado se houver qualquer conflito."""
        name_key = normalize_text(command.name)
        if not name_key:
            raise CommandRegistrationError("O nome do comando não pode ser vazio.")
        if not command.description.strip():
            raise CommandRegistrationError(f"O comando '{command.name}' precisa de uma descrição.")
        if not callable(command.handler):
            raise CommandRegistrationError(f"O comando '{command.name}' não possui handler válido.")

        keys: dict[str, str] = {name_key: command.name}
        for alias in command.aliases:
            alias_key = normalize_text(alias)
            if not alias_key:
                raise CommandRegistrationError(f"O comando '{command.name}' possui um alias vazio.")
            if alias_key in keys:
                raise CommandRegistrationError(
                    f"O comando '{command.name}' repete o nome ou alias '{alias}'."
                )
            keys[alias_key] = alias

        for key, label in keys.items():
            existing = self._index.get(key)
            if existing is None:
                continue
            if key == name_key and normalize_text(existing.name) == name_key:
                raise CommandRegistrationError(f"Já existe um comando chamado '{existing.name}'.")
            raise CommandRegistrationError(
                f"'{label}' (do comando '{command.name}') conflita com o comando '{existing.name}'."
            )

        self._commands.append(command)
        for key in keys:
            self._index[key] = command

    def resolve(self, text: str) -> Command | None:
        """Retorna o comando correspondente à entrada, ou ``None`` se não houver."""
        return self._index.get(normalize_text(text))
