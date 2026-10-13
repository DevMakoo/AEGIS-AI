"""Provedor Ollama via API local ``POST /api/chat`` (https://docs.ollama.com/api/chat).

- Não baixa modelos nem inicia/encerra o Ollama.
- Não faz nenhuma chamada de rede na importação nem na construção.
- Conexão direta: ignora proxies do ambiente (HTTP_PROXY etc.) e não segue
  redirecionamentos, para que as mensagens não saiam do destino configurado.
"""

from __future__ import annotations

import http.client
import json
import re
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any, Protocol

from ai.provider import ChatMessage
from core.exceptions import (
    AIEndpointNotFoundError,
    AIModelNotFoundError,
    AIResponseError,
    AITimeoutError,
    AIUnavailableError,
)
from core.logging_config import get_logger

CHAT_PATH = "/api/chat"
MAX_RESPONSE_BYTES = 1_000_000
_MAX_ERROR_BODY_BYTES = 4_096
_MAX_LOGGED_ERROR_CHARS = 200
_MODEL_NOT_FOUND = re.compile(r"\bmodel\b.*\bnot found\b", re.IGNORECASE)

_logger = get_logger("ai.ollama")


class HttpOpener(Protocol):
    """Subconjunto de ``urllib.request.OpenerDirector`` usado pelo provedor."""

    def open(self, fullurl: urllib.request.Request, *, timeout: float) -> Any: ...


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Transforma qualquer redirecionamento em erro HTTP, em vez de segui-lo."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def build_direct_opener() -> urllib.request.OpenerDirector:
    """Opener sem proxies (``ProxyHandler({})``) e sem seguir redirecionamentos."""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _RejectRedirects())


class OllamaProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        opener: HttpOpener | None = None,
    ) -> None:
        self._chat_url = base_url.rstrip("/") + CHAT_PATH
        self._model = model
        self._timeout = timeout_seconds
        self._opener: HttpOpener = build_direct_opener() if opener is None else opener

    @property
    def name(self) -> str:
        return "Ollama"

    @property
    def model(self) -> str:
        return self._model

    def chat(self, messages: Sequence[ChatMessage]) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
        }
        request = urllib.request.Request(
            self._chat_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        body = self._send(request)
        return self._parse(body)

    def _send(self, request: urllib.request.Request) -> bytes:
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc) from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise AITimeoutError(f"Tempo limite de {self._timeout:g}s excedido.") from None
            raise AIUnavailableError(
                f"Ollama inacessível em {self._chat_url}: {type(exc.reason).__name__}."
            ) from None
        except TimeoutError:
            raise AITimeoutError(f"Tempo limite de {self._timeout:g}s excedido.") from None
        except (ConnectionError, http.client.RemoteDisconnected):
            raise AIUnavailableError("Conexão com o Ollama interrompida.") from None
        except (OSError, http.client.HTTPException) as exc:
            raise AIResponseError(f"Falha de comunicação: {type(exc).__name__}.") from None

        if len(body) > MAX_RESPONSE_BYTES:
            raise AIResponseError(f"Resposta maior que {MAX_RESPONSE_BYTES} bytes.")
        return body

    def _http_error(self, exc: urllib.error.HTTPError) -> Exception:
        detail = _error_detail(exc)
        # INFO: o usuário já recebe uma mensagem amigável; o console só mostra WARNING+.
        _logger.info("Ollama retornou HTTP %d: %s", exc.code, detail or "(sem detalhes)")
        if exc.code == 404:
            # O Ollama responde 404 com {"error": "model '...' not found"} para modelo
            # ausente. Outro 404 (URL errada, outro serviço na porta) não é "modelo".
            if detail is not None and _MODEL_NOT_FOUND.search(detail):
                return AIModelNotFoundError(f"Modelo '{self._model}' não encontrado no Ollama.")
            return AIEndpointNotFoundError(f"Endereço não encontrado: {self._chat_url}.")
        return AIResponseError(f"Ollama retornou HTTP {exc.code}.")

    @staticmethod
    def _parse(body: bytes) -> str:
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise AIResponseError("Resposta do Ollama não é JSON válido.") from None
        if not isinstance(data, dict):
            raise AIResponseError("Resposta do Ollama não é um objeto JSON.")
        if "error" in data:
            raise AIResponseError("Ollama retornou um erro no corpo da resposta.")
        message = data.get("message")
        if not isinstance(message, dict):
            raise AIResponseError("Resposta do Ollama sem o campo 'message'.")
        if message.get("role") != "assistant":
            raise AIResponseError("Resposta do Ollama com papel inesperado.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise AIResponseError("Resposta do Ollama sem conteúdo de texto.")
        return content


def _error_detail(exc: urllib.error.HTTPError) -> str | None:
    """Campo ``error`` do corpo JSON do Ollama, sanitizado e truncado para log.

    É texto remoto: só caracteres imprimíveis são mantidos, em uma única linha, e
    corpos que não sejam o JSON de erro do Ollama (ex.: páginas HTML) são ignorados.
    """
    try:
        raw = exc.read(_MAX_ERROR_BODY_BYTES)
        data = json.loads(raw.decode("utf-8"))
        detail = data.get("error") if isinstance(data, dict) else None
    except (OSError, http.client.HTTPException, UnicodeDecodeError, ValueError):
        detail = None
    if not isinstance(detail, str):
        return None
    printable = "".join(c if c.isprintable() else " " for c in detail)
    return " ".join(printable.split())[:_MAX_LOGGED_ERROR_CHARS] or None
