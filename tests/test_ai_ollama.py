from __future__ import annotations

import http.client
import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from ai.ollama import MAX_RESPONSE_BYTES, OllamaProvider, build_direct_opener
from ai.provider import ChatMessage
from core.config import load_config
from core.exceptions import (
    AIEndpointNotFoundError,
    AIModelNotFoundError,
    AIResponseError,
    AITimeoutError,
    AIUnavailableError,
)
from core.logging_config import LOG_FILE_NAME, configure_logging
from tests.helpers import FakeOpener, NetworkAccessBlocked

BASE_URL = "http://127.0.0.1:11434"
MESSAGES = (ChatMessage("system", "regras"), ChatMessage("user", "olá"))


def _provider(outcome: bytes | BaseException) -> tuple[OllamaProvider, FakeOpener]:
    opener = FakeOpener(outcome)
    provider = OllamaProvider(
        base_url=BASE_URL + "/", model="llama3.2", timeout_seconds=12.5, opener=opener
    )
    return provider, opener


def _ok_body(content: str = "Olá! Como posso ajudar?", role: str = "assistant") -> bytes:
    return json.dumps(
        {
            "model": "llama3.2",
            "created_at": "2026-10-13T12:00:00Z",
            "message": {"role": role, "content": content},
            "done": True,
            "done_reason": "stop",
        }
    ).encode("utf-8")


def _http_error(code: int, body: bytes = b"") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        BASE_URL + "/api/chat", code, "erro", http.client.HTTPMessage(), io.BytesIO(body)
    )


def test_valid_response_returns_content_and_sends_expected_request() -> None:
    provider, opener = _provider(_ok_body())

    assert provider.chat(MESSAGES) == "Olá! Como posso ajudar?"

    request, timeout = opener.requests[0]
    assert request.full_url == "http://127.0.0.1:11434/api/chat"
    assert request.get_method() == "POST"
    assert request.get_header("Content-type") == "application/json"
    assert timeout == 12.5
    assert request.data is not None
    assert json.loads(request.data) == {
        "model": "llama3.2",
        "messages": [
            {"role": "system", "content": "regras"},
            {"role": "user", "content": "olá"},
        ],
        "stream": False,
    }


def test_provider_identity() -> None:
    provider, _ = _provider(_ok_body())

    assert provider.name == "Ollama"
    assert provider.model == "llama3.2"


@pytest.mark.parametrize(
    "body",
    [
        b"isto nao e json",
        b"\xff\xfe\x00",
        b"[1, 2, 3]",
        b'{"done": true}',
        b'{"message": "texto"}',
        b'{"message": {"role": "assistant"}}',
        b'{"message": {"role": "assistant", "content": 42}}',
        b'{"message": {"role": "assistant", "content": "   "}}',
        b'{"message": {"role": "user", "content": "oi"}}',
        b'{"error": "the model failed to generate a response"}',
    ],
)
def test_malformed_responses_raise_response_error(body: bytes) -> None:
    provider, _ = _provider(body)

    with pytest.raises(AIResponseError):
        provider.chat(MESSAGES)


def test_oversized_response_is_rejected() -> None:
    provider, _ = _provider(b"x" * (MAX_RESPONSE_BYTES + 10))

    with pytest.raises(AIResponseError, match="maior"):
        provider.chat(MESSAGES)


@pytest.mark.parametrize(
    "body",
    [
        b'{"error": "model \\"llama3.2\\" not found, try pulling it first"}',
        b'{"error": "model \'llama3.2\' not found"}',
        b'{"error": "Model llama3.2 Not Found"}',
    ],
)
def test_http_404_with_model_message_means_model_not_found(body: bytes) -> None:
    provider, _ = _provider(_http_error(404, body))

    with pytest.raises(AIModelNotFoundError, match="llama3.2"):
        provider.chat(MESSAGES)


@pytest.mark.parametrize(
    "body",
    [
        b"404 page not found",
        b"<html><body>Not Found</body></html>",
        b'{"error": "not found"}',
        b'{"detail": "model not found"}',
        b"",
    ],
)
def test_other_http_404_means_endpoint_not_found(body: bytes) -> None:
    provider, _ = _provider(_http_error(404, body))

    with pytest.raises(AIEndpointNotFoundError):
        provider.chat(MESSAGES)


def test_remote_error_text_is_sanitized_in_logs(tmp_path: Path) -> None:
    configure_logging(load_config(environ={"AEGIS_LOG_DIR": str(tmp_path)}, env_file=None))
    body = json.dumps({"error": "falha\x1b[31m\nlinha falsa | ERROR | x" + "y" * 500}).encode()
    provider, _ = _provider(_http_error(500, body))

    with pytest.raises(AIResponseError):
        provider.chat(MESSAGES)

    logged = (tmp_path / LOG_FILE_NAME).read_text(encoding="utf-8")
    line = next(line for line in logged.splitlines() if "HTTP 500" in line)
    assert "\x1b" not in logged
    assert "linha falsa" in line  # quebra de linha removida: não forja nova linha de log
    assert "y" * 201 not in line  # truncado


@pytest.mark.parametrize("code", [400, 429, 500, 502])
def test_other_http_errors_raise_response_error(code: int) -> None:
    provider, _ = _provider(_http_error(code, b"corpo qualquer"))

    with pytest.raises(AIResponseError, match=str(code)):
        provider.chat(MESSAGES)


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError(ConnectionRefusedError(10061, "recusada")),
        urllib.error.URLError(OSError("host inacessível")),
        ConnectionResetError(),
        http.client.RemoteDisconnected("fechou"),
    ],
)
def test_connection_failures_raise_unavailable(error: BaseException) -> None:
    provider, _ = _provider(error)

    with pytest.raises(AIUnavailableError):
        provider.chat(MESSAGES)


@pytest.mark.parametrize(
    "error", [TimeoutError("timed out"), urllib.error.URLError(TimeoutError("timed out"))]
)
def test_timeouts_raise_timeout_error(error: BaseException) -> None:
    provider, _ = _provider(error)

    with pytest.raises(AITimeoutError):
        provider.chat(MESSAGES)


def test_unexpected_http_protocol_error_raises_response_error() -> None:
    provider, _ = _provider(http.client.IncompleteRead(b""))

    with pytest.raises(AIResponseError):
        provider.chat(MESSAGES)


def test_constructor_makes_no_network_call() -> None:
    # Com o opener real: construir não conecta (a proteção de rede falharia aqui).
    OllamaProvider(base_url=BASE_URL, model="x", timeout_seconds=1)


@pytest.mark.parametrize(
    "connection",
    [
        http.client.HTTPConnection("127.0.0.1", 11434),
        http.client.HTTPSConnection("127.0.0.1", 11434),
    ],
)
def test_http_and_https_connections_are_blocked(connection: http.client.HTTPConnection) -> None:
    with pytest.raises(NetworkAccessBlocked):
        connection.connect()


def test_real_opener_is_blocked_during_tests() -> None:
    provider = OllamaProvider(base_url=BASE_URL, model="x", timeout_seconds=1)

    with pytest.raises(NetworkAccessBlocked):
        provider.chat(MESSAGES)


def test_direct_opener_ignores_environment_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:8080")

    def env_proxies(opener: urllib.request.OpenerDirector) -> list[dict[str, str]]:
        return [
            h.proxies
            for h in opener.handlers
            if isinstance(h, urllib.request.ProxyHandler) and h.proxies
        ]

    # Controle: o opener padrão do urllib usaria o proxy do ambiente...
    assert env_proxies(urllib.request.build_opener())
    # ...o opener do provedor não (ProxyHandler({}) substitui o padrão).
    assert env_proxies(build_direct_opener()) == []


def test_direct_opener_does_not_follow_redirects() -> None:
    opener = build_direct_opener()
    handler = next(h for h in opener.handlers if isinstance(h, urllib.request.HTTPRedirectHandler))
    request = urllib.request.Request(BASE_URL + "/api/chat", data=b"{}", method="POST")

    redirected = handler.redirect_request(
        request, io.BytesIO(), 307, "redirect", http.client.HTTPMessage(), "https://externo.example"
    )

    assert redirected is None
