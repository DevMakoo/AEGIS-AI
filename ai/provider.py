"""Contrato comum dos provedores de IA conversacional."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

type ChatRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: ChatRole
    content: str


class AIProvider(Protocol):
    """Provedor que recebe a conversa estruturada e devolve apenas texto.

    Implementações devem levantar subclasses de ``core.exceptions.AIError`` para
    falhas de comunicação ou respostas inválidas, e nunca executar nada com base
    no conteúdo da resposta.
    """

    @property
    def name(self) -> str:
        """Nome legível do provedor (ex.: ``Ollama``)."""
        ...

    @property
    def model(self) -> str: ...

    def chat(self, messages: Sequence[ChatMessage]) -> str:
        """Envia as mensagens em ordem e retorna o texto da resposta do assistente."""
        ...
