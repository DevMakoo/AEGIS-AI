"""Dublês de teste compartilhados (importados pelos testes e pelo ``conftest.py``)."""

from __future__ import annotations

import io
import urllib.request
from collections.abc import Iterable, Sequence
from typing import Any

from ai.provider import ChatMessage


class NetworkAccessBlocked(RuntimeError):
    """Um teste tentou abrir uma conexão HTTP real."""


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


class FakeProvider:
    """Provedor de IA falso: devolve respostas ou levanta erros em sequência."""

    def __init__(self, *outcomes: str | BaseException, model: str = "modelo-teste") -> None:
        self._outcomes = list(outcomes)
        self.calls: list[tuple[ChatMessage, ...]] = []
        self._model = model

    @property
    def name(self) -> str:
        return "Falso"

    @property
    def model(self) -> str:
        return self._model

    def chat(self, messages: Sequence[ChatMessage]) -> str:
        self.calls.append(tuple(messages))
        outcome = self._outcomes.pop(0) if self._outcomes else "resposta padrão"
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._buffer = io.BytesIO(body)

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class FakeOpener:
    """Substitui a rede no ``OllamaProvider``: registra a requisição e devolve um corpo
    ou levanta um erro."""

    def __init__(self, outcome: bytes | BaseException) -> None:
        self._outcome = outcome
        self.requests: list[tuple[urllib.request.Request, float]] = []

    def open(self, fullurl: urllib.request.Request, *, timeout: float) -> Any:
        self.requests.append((fullurl, timeout))
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return FakeResponse(self._outcome)
