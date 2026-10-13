from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

import pytest

from core.logging_config import shutdown_logging


@pytest.fixture(autouse=True)
def _reset_logging() -> Iterator[None]:
    """Garante que nenhum handler (e arquivo de log) vaze entre testes."""
    yield
    shutdown_logging()


@pytest.fixture
def test_environ(tmp_path: Path) -> dict[str, str]:
    """Ambiente isolado: logs em diretório temporário, sem ler o .env real."""
    return {"AEGIS_ENV": "test", "AEGIS_LOG_DIR": str(tmp_path / "logs")}


class ScriptedInput:
    """Simula ``input()``: devolve as linhas em ordem e gera EOF ao final."""

    def __init__(self, lines: Iterable[str]) -> None:
        self._lines = list(lines)
        self.prompts: list[str] = []

    @property
    def remaining(self) -> list[str]:
        return list(self._lines)

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self._lines:
            raise EOFError
        return self._lines.pop(0)


@pytest.fixture
def scripted_input() -> Callable[[Iterable[str]], ScriptedInput]:
    return ScriptedInput
