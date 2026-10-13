from __future__ import annotations

import http.client
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

import pytest

from core.logging_config import shutdown_logging
from tests.helpers import NetworkAccessBlocked, ScriptedInput


@pytest.fixture(autouse=True)
def _reset_logging() -> Iterator[None]:
    """Garante que nenhum handler (e arquivo de log) vaze entre testes."""
    yield
    shutdown_logging()


@pytest.fixture(autouse=True)
def _block_http(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Impede conexões HTTP/HTTPS reais feitas via ``http.client``.

    Cobre ``http.client.HTTPConnection`` e ``HTTPSConnection`` (cujo ``connect`` chama
    o da classe base) — o transporte de ``urllib.request`` e, portanto, do
    ``OllamaProvider``. Ambos os casos são verificados em ``tests/test_ai_ollama.py``.
    NÃO cobre sockets diretos nem bibliotecas com transporte próprio (ex.: httpx,
    urllib3/requests); um provedor futuro que as use precisará de proteção própria.

    Restrito de propósito: não altera ``socket`` em geral, então não interfere no
    pytest nem em asyncio. Desfeito ao fim de cada teste. Testes de integração
    manuais podem desativá-lo com ``@pytest.mark.network``.
    """
    if request.node.get_closest_marker("network") is not None:
        return

    def blocked(self: http.client.HTTPConnection) -> None:
        raise NetworkAccessBlocked(f"Conexão HTTP bloqueada nos testes: {self.host}:{self.port}")

    monkeypatch.setattr(http.client.HTTPConnection, "connect", blocked)


@pytest.fixture
def test_environ(tmp_path: Path) -> dict[str, str]:
    """Ambiente isolado: logs em diretório temporário, sem ler o .env real."""
    return {"AEGIS_ENV": "test", "AEGIS_LOG_DIR": str(tmp_path / "logs")}


@pytest.fixture
def scripted_input() -> Callable[[Iterable[str]], ScriptedInput]:
    return ScriptedInput
