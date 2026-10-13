from __future__ import annotations

from pathlib import Path

import pytest

from ai.prompts import DEFAULT_SYSTEM_PROMPT
from ai.service import SECRET_PLACEHOLDER, AIService, sanitize_model_output, user_message_for
from core.config import load_config
from core.exceptions import (
    AIConfigurationError,
    AIEndpointNotFoundError,
    AIError,
    AIModelNotFoundError,
    AIProviderError,
    AIResponseError,
    AITimeoutError,
    AIUnavailableError,
)
from core.logging_config import LOG_FILE_NAME, configure_logging
from tests.helpers import FakeProvider


def _service(provider: FakeProvider, *, max_history: int = 10, secrets=()) -> AIService:
    return AIService(
        provider, system_prompt="regras", max_history_messages=max_history, secrets=secrets
    )


def test_valid_reply_is_returned_and_stored_in_history() -> None:
    provider = FakeProvider("Olá!")
    service = _service(provider)

    assert service.reply("  oi  ") == "Olá!"

    sent = provider.calls[0]
    assert [(m.role, m.content) for m in sent] == [("system", "regras"), ("user", "oi")]
    assert [(m.role, m.content) for m in service.history.messages] == [
        ("system", "regras"),
        ("user", "oi"),
        ("assistant", "Olá!"),
    ]


def test_context_accumulates_in_order() -> None:
    provider = FakeProvider("r1", "r2")
    service = _service(provider)

    service.reply("p1")
    service.reply("p2")

    assert [m.content for m in provider.calls[1]] == ["regras", "p1", "r1", "p2"]


def test_history_limit_is_applied() -> None:
    provider = FakeProvider("r1", "r2", "r3")
    service = _service(provider, max_history=2)

    for i in range(1, 4):
        service.reply(f"p{i}")

    assert [m.content for m in service.history.messages] == ["regras", "p3", "r3"]


@pytest.mark.parametrize(
    ("error", "label"),
    [
        (AIUnavailableError("x"), "Falso inacessível"),
        (AIModelNotFoundError("x"), "modelo não encontrado"),
        (AIEndpointNotFoundError("x"), "endereço do Falso não encontrado"),
        (AITimeoutError("x"), "tempo limite excedido"),
        (AIResponseError("x"), "resposta inválida do Falso"),
    ],
)
def test_failures_propagate_and_are_not_stored(error: AIError, label: str) -> None:
    service = _service(FakeProvider(error))

    with pytest.raises(type(error)):
        service.reply("pergunta")

    assert len(service.history) == 0
    assert service.describe().endswith(f"última tentativa falhou: {label}")


@pytest.mark.parametrize(
    "error",
    [
        AIUnavailableError("x"),
        AIModelNotFoundError("x"),
        AIEndpointNotFoundError("x"),
        AITimeoutError("x"),
        AIResponseError("x"),
        ZeroDivisionError("x"),
    ],
)
def test_status_never_exposes_internal_class_names(error: BaseException) -> None:
    service = _service(FakeProvider(error))

    with pytest.raises(AIError):
        service.reply("pergunta")

    description = service.describe()
    assert "Error" not in description
    assert type(error).__name__ not in description


def test_unknown_failure_has_generic_status() -> None:
    service = _service(FakeProvider(ZeroDivisionError("x")))

    with pytest.raises(AIProviderError):
        service.reply("pergunta")

    assert service.describe().endswith("última tentativa falhou: falha inesperada")


def test_unexpected_provider_exception_becomes_provider_error() -> None:
    service = _service(FakeProvider(ZeroDivisionError("bug")))

    with pytest.raises(AIProviderError) as info:
        service.reply("pergunta")

    assert isinstance(info.value.__cause__, ZeroDivisionError)
    assert len(service.history) == 0


@pytest.mark.parametrize("raw", ["", "  \n ", "\x1b[31m\x1b[0m"])
def test_empty_reply_after_sanitizing_is_an_error(raw: str) -> None:
    service = _service(FakeProvider(raw))

    with pytest.raises(AIResponseError):
        service.reply("pergunta")
    assert len(service.history) == 0


def test_success_after_failure_clears_last_error() -> None:
    service = _service(FakeProvider(AITimeoutError("x"), "ok"))

    with pytest.raises(AITimeoutError):
        service.reply("p")
    service.reply("p")

    assert service.describe() == "habilitada (Falso, modelo modelo-teste)"


def test_known_secrets_are_never_sent_to_provider() -> None:
    secret = "sk-test-0123456789"
    provider = FakeProvider("ok")
    service = AIService(
        provider,
        system_prompt=f"regras {secret}",
        max_history_messages=4,
        secrets=(secret, ""),
    )

    service.reply(f"minha chave é {secret}")

    sent_text = " ".join(m.content for m in provider.calls[0])
    assert secret not in sent_text
    assert SECRET_PLACEHOLDER in sent_text


def test_reset_discards_history() -> None:
    service = _service(FakeProvider("r"))
    service.reply("p")

    service.reset()

    assert len(service.history) == 0
    assert service.history.messages[0].content == "regras"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Olá!\nTudo bem?", "Olá!\nTudo bem?"),
        ("\x1b[31mvermelho\x1b[0m", "vermelho"),
        ("\x1b]0;titulo falso\x07texto", "texto"),
        ("linha\r\noutra", "linha\noutra"),
        ("a\x07b\x00c", "abc"),
        ("abc‮def", "abcdef"),
        ("col1\tcol2", "col1\tcol2"),
        ("1 000", "1 000"),
    ],
)
def test_sanitize_model_output(raw: str, expected: str) -> None:
    assert sanitize_model_output(raw) == expected


@pytest.mark.parametrize(
    ("error", "fragment"),
    [
        (AIUnavailableError("detalhe técnico"), "Ollama"),
        (AIModelNotFoundError("detalhe técnico"), "ollama list"),
        (AIEndpointNotFoundError("detalhe técnico"), "AEGIS_OLLAMA_BASE_URL"),
        (AITimeoutError("detalhe técnico"), "AEGIS_AI_TIMEOUT_SECONDS"),
        (AIResponseError("detalhe técnico"), "resposta inválida"),
        (AIConfigurationError("detalhe técnico"), "configurada"),
        (AIProviderError("detalhe técnico"), "falha inesperada"),
    ],
)
def test_user_messages_are_friendly_and_hide_details(error: AIError, fragment: str) -> None:
    message = user_message_for(error)

    assert fragment in message
    assert "detalhe técnico" not in message
    assert "Traceback" not in message
    assert "Error" not in message
    assert type(error).__name__ not in message


def test_unexpected_failure_is_logged_to_file_only_without_sensitive_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = "sk-test-0123456789"
    config = load_config(
        environ={"AEGIS_LOG_DIR": str(tmp_path), "AEGIS_AI_API_KEY": secret}, env_file=None
    )
    configure_logging(config)
    leaky = ZeroDivisionError(f"bug com MENSAGEM-SIGILOSA e {secret}")
    service = AIService(
        FakeProvider(leaky),
        system_prompt="regras",
        max_history_messages=4,
        secrets=config.secret_values(),
    )

    with pytest.raises(AIProviderError):
        service.reply(f"MENSAGEM-SIGILOSA com {secret}")

    console = capsys.readouterr().err
    content = (tmp_path / LOG_FILE_NAME).read_text(encoding="utf-8")
    assert console == ""  # nada técnico no terminal
    assert "ERROR" in content
    assert "Falha inesperada no provedor Falso: ZeroDivisionError em" in content
    assert "service.py:" in content  # locais da pilha preservados para diagnóstico
    assert "helpers.py:" in content
    assert "SIGILOSA" not in content
    assert secret not in content


def test_regular_warnings_still_reach_the_console(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    logger = configure_logging(load_config(environ={"AEGIS_LOG_DIR": str(tmp_path)}, env_file=None))

    logger.error("Erro comum visível.")

    assert "Erro comum visível." in capsys.readouterr().err


def test_logs_do_not_contain_message_contents(tmp_path: Path) -> None:
    config = load_config(environ={"AEGIS_LOG_DIR": str(tmp_path)}, env_file=None)
    configure_logging(config)
    service = _service(FakeProvider("RESPOSTA-SIGILOSA", AIUnavailableError("off")))

    service.reply("PERGUNTA-SIGILOSA")
    with pytest.raises(AIUnavailableError):
        service.reply("OUTRA-PERGUNTA-SIGILOSA")

    content = (tmp_path / LOG_FILE_NAME).read_text(encoding="utf-8")
    assert "Resposta da IA recebida" in content
    assert "AIUnavailableError" in content
    assert "SIGILOSA" not in content


def test_default_system_prompt_covers_identity_and_limits() -> None:
    prompt = DEFAULT_SYSTEM_PROMPT

    for fragment in ("AEGIS", "português brasileiro", "cometer erros", "Nunca afirme"):
        assert fragment in prompt
    assert "senhas" in prompt
