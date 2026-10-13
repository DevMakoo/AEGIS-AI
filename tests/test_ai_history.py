from __future__ import annotations

import pytest

from ai.history import ConversationHistory
from ai.provider import ChatMessage


def test_starts_with_only_the_system_message() -> None:
    history = ConversationHistory("regras", max_messages=4)

    assert history.messages == (ChatMessage("system", "regras"),)
    assert len(history) == 0


def test_with_user_message_builds_context_without_mutating() -> None:
    history = ConversationHistory("regras", max_messages=4)
    history.append_exchange("p1", "r1")

    context = history.with_user_message("p2")

    assert context == (
        ChatMessage("system", "regras"),
        ChatMessage("user", "p1"),
        ChatMessage("assistant", "r1"),
        ChatMessage("user", "p2"),
    )
    assert len(history) == 2


def test_order_is_preserved() -> None:
    history = ConversationHistory("regras", max_messages=10)
    for i in range(3):
        history.append_exchange(f"p{i}", f"r{i}")

    assert [m.content for m in history.messages] == ["regras", "p0", "r0", "p1", "r1", "p2", "r2"]
    assert [m.role for m in history.messages[1:]] == ["user", "assistant"] * 3


def test_limit_drops_oldest_pairs_and_keeps_system_message() -> None:
    history = ConversationHistory("regras", max_messages=4)
    for i in range(5):
        history.append_exchange(f"p{i}", f"r{i}")

    assert len(history) == 4
    assert history.messages[0] == ChatMessage("system", "regras")
    assert [m.content for m in history.messages[1:]] == ["p3", "r3", "p4", "r4"]


def test_odd_limit_still_starts_with_user_message() -> None:
    history = ConversationHistory("regras", max_messages=3)
    for i in range(3):
        history.append_exchange(f"p{i}", f"r{i}")

    assert history.messages[1].role == "user"
    assert len(history) <= 3


def test_clear_keeps_system_message() -> None:
    history = ConversationHistory("regras", max_messages=4)
    history.append_exchange("p", "r")

    history.clear()

    assert history.messages == (ChatMessage("system", "regras"),)


def test_limit_below_two_is_rejected() -> None:
    with pytest.raises(ValueError):
        ConversationHistory("regras", max_messages=1)
