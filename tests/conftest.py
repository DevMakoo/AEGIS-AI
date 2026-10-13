from __future__ import annotations

from collections.abc import Iterator
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
