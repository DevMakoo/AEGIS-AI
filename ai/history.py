"""Histórico conversacional temporário, somente em memória."""

from __future__ import annotations

from ai.provider import ChatMessage


class ConversationHistory:
    """Mensagem de sistema fixa + trocas usuário/assistente, com limite de tamanho.

    ``max_messages`` conta apenas mensagens de usuário e assistente. Ao exceder o
    limite, as trocas mais antigas saem em pares (pergunta e resposta juntas), e
    a mensagem de sistema é sempre preservada. Nada é gravado em disco.
    """

    def __init__(self, system_prompt: str, max_messages: int) -> None:
        if max_messages < 2:
            raise ValueError("O histórico precisa comportar ao menos 2 mensagens.")
        self._system = ChatMessage("system", system_prompt)
        self._max_messages = max_messages
        self._turns: list[ChatMessage] = []

    def __len__(self) -> int:
        """Quantidade de mensagens de usuário/assistente (sem a de sistema)."""
        return len(self._turns)

    @property
    def messages(self) -> tuple[ChatMessage, ...]:
        return (self._system, *self._turns)

    def with_user_message(self, content: str) -> tuple[ChatMessage, ...]:
        """Contexto a enviar ao provedor, sem alterar o histórico."""
        return (*self.messages, ChatMessage("user", content))

    def append_exchange(self, user_content: str, assistant_content: str) -> None:
        """Registra uma troca bem-sucedida e aplica o limite.

        A lista nova é montada à parte e trocada de uma vez: uma interrupção (Ctrl+C)
        no meio da operação não deixa uma pergunta sem resposta no histórico.
        """
        turns = [
            *self._turns,
            ChatMessage("user", user_content),
            ChatMessage("assistant", assistant_content),
        ]
        while len(turns) > self._max_messages:
            del turns[:2]
        self._turns = turns

    def clear(self) -> None:
        """Descarta as trocas, mantendo a mensagem de sistema."""
        self._turns.clear()
