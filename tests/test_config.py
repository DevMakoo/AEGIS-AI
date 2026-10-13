from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.config import (
    DEFAULT_LOG_DIR,
    PROJECT_ROOT,
    AIConfig,
    AIProviderName,
    AppConfig,
    Environment,
    SecretStr,
    load_config,
)
from core.exceptions import ConfigError


def test_defaults_without_env() -> None:
    config = load_config(environ={}, env_file=None)

    assert config == AppConfig()
    assert config.environment is Environment.DEVELOPMENT
    assert config.log_level == "INFO"
    assert config.log_dir == DEFAULT_LOG_DIR
    assert config.log_to_file is True
    assert config.language == "pt-BR"
    assert config.ai_api_key is None


def test_environment_variables_override_defaults(tmp_path: Path) -> None:
    config = load_config(
        environ={
            "AEGIS_ENV": "Production",
            "AEGIS_LOG_LEVEL": "debug",
            "AEGIS_LOG_DIR": str(tmp_path),
            "AEGIS_LOG_TO_FILE": "false",
        },
        env_file=None,
    )

    assert config.environment is Environment.PRODUCTION
    assert config.log_level == "DEBUG"
    assert config.log_dir == tmp_path
    assert config.log_to_file is False


def test_blank_values_fall_back_to_defaults() -> None:
    config = load_config(environ={"AEGIS_LOG_LEVEL": "  ", "AEGIS_AI_API_KEY": ""}, env_file=None)

    assert config.log_level == "INFO"
    assert config.ai_api_key is None


def test_relative_log_dir_is_resolved_from_project_root() -> None:
    config = load_config(environ={"AEGIS_LOG_DIR": "var/logs"}, env_file=None)

    assert config.log_dir == PROJECT_ROOT / "var" / "logs"


def test_env_file_is_loaded_and_process_env_wins(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("AEGIS_LOG_LEVEL=WARNING\nAEGIS_ENV=production\n", encoding="utf-8")

    config = load_config(environ={"AEGIS_ENV": "test"}, env_file=env_file)

    assert config.log_level == "WARNING"
    assert config.environment is Environment.TEST


def test_missing_env_file_is_ignored(tmp_path: Path) -> None:
    config = load_config(environ={}, env_file=tmp_path / "inexistente.env")

    assert config == AppConfig()


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("AEGIS_ENV", "staging"),
        ("AEGIS_LOG_LEVEL", "VERBOSE"),
        ("AEGIS_LOG_TO_FILE", "talvez"),
        ("AEGIS_LANGUAGE", "en-US"),
    ],
)
def test_invalid_values_raise_config_error(variable: str, value: str) -> None:
    with pytest.raises(ConfigError, match=variable):
        load_config(environ={variable: value}, env_file=None)


def test_api_key_is_never_exposed_in_repr() -> None:
    secret = "sk-test-0123456789"
    config = load_config(environ={"AEGIS_AI_API_KEY": secret}, env_file=None)

    assert isinstance(config.ai_api_key, SecretStr)
    assert config.ai_api_key.get_secret_value() == secret
    assert secret not in repr(config)
    assert secret not in repr(config.ai_api_key)
    assert secret not in str(config.ai_api_key)
    assert config.secret_values() == (secret,)


def test_ai_defaults_are_safe() -> None:
    ai = load_config(environ={}, env_file=None).ai

    assert ai == AIConfig()
    assert ai.enabled is False
    assert ai.provider is AIProviderName.OLLAMA
    assert ai.ollama_base_url == "http://127.0.0.1:11434"
    assert ai.ollama_model is None
    assert ai.ollama_allow_remote is False
    assert ai.timeout_seconds == 60.0
    assert ai.max_history_messages == 20
    assert ai.system_prompt is None


def test_ai_values_are_loaded() -> None:
    ai = load_config(
        environ={
            "AEGIS_AI_ENABLED": "sim",
            "AEGIS_AI_PROVIDER": "OLLAMA",
            "AEGIS_OLLAMA_BASE_URL": "http://localhost:11500/",
            "AEGIS_OLLAMA_MODEL": "qwen2.5:7b",
            "AEGIS_AI_TIMEOUT_SECONDS": "2,5",
            "AEGIS_AI_MAX_HISTORY_MESSAGES": "8",
            "AEGIS_AI_SYSTEM_PROMPT": "Responda curto.",
        },
        env_file=None,
    ).ai

    assert ai.enabled is True
    assert ai.provider is AIProviderName.OLLAMA
    assert ai.ollama_base_url == "http://localhost:11500"
    assert ai.ollama_model == "qwen2.5:7b"
    assert ai.timeout_seconds == 2.5
    assert ai.max_history_messages == 8
    assert ai.system_prompt == "Responda curto."


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:11434", "http://localhost:11434", "http://[::1]:11434", "https://127.0.0.2"],
)
def test_loopback_urls_are_accepted(url: str) -> None:
    config = load_config(environ={"AEGIS_OLLAMA_BASE_URL": url}, env_file=None)

    assert config.ai.ollama_base_url == url


@pytest.mark.parametrize(
    ("url", "fragment"),
    [
        ("ftp://127.0.0.1:11434", "http(s)"),
        ("127.0.0.1:11434", "http(s)"),
        ("http://", "http(s)"),
        ("http://127.0.0.1:porta", "inválido"),
        ("http://user:senha@127.0.0.1:11434", "usuário ou senha"),
        ("http://127.0.0.1:11434/?x=1", "parâmetros"),
        ("http://192.168.0.10:11434", "AEGIS_OLLAMA_ALLOW_REMOTE"),
        ("https://api.exemplo.com", "AEGIS_OLLAMA_ALLOW_REMOTE"),
        ("http://localhost.exemplo.com", "AEGIS_OLLAMA_ALLOW_REMOTE"),
    ],
)
def test_invalid_or_remote_ollama_urls_are_rejected(url: str, fragment: str) -> None:
    with pytest.raises(ConfigError, match="AEGIS_OLLAMA_BASE_URL") as info:
        load_config(environ={"AEGIS_OLLAMA_BASE_URL": url}, env_file=None)

    assert fragment in str(info.value)


def test_remote_ollama_requires_explicit_opt_in() -> None:
    config = load_config(
        environ={
            "AEGIS_OLLAMA_BASE_URL": "http://192.168.0.10:11434",
            "AEGIS_OLLAMA_ALLOW_REMOTE": "true",
        },
        env_file=None,
    )

    assert config.ai.ollama_base_url == "http://192.168.0.10:11434"
    assert config.ai.ollama_allow_remote is True


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("AEGIS_AI_ENABLED", "talvez"),
        ("AEGIS_AI_PROVIDER", "openai"),
        ("AEGIS_OLLAMA_MODEL", "modelo com espaco"),
        ("AEGIS_OLLAMA_ALLOW_REMOTE", "x"),
        ("AEGIS_AI_TIMEOUT_SECONDS", "rápido"),
        ("AEGIS_AI_TIMEOUT_SECONDS", "0"),
        ("AEGIS_AI_TIMEOUT_SECONDS", "601"),
        ("AEGIS_AI_TIMEOUT_SECONDS", "nan"),
        ("AEGIS_AI_MAX_HISTORY_MESSAGES", "1"),
        ("AEGIS_AI_MAX_HISTORY_MESSAGES", "201"),
        ("AEGIS_AI_MAX_HISTORY_MESSAGES", "dez"),
    ],
)
def test_invalid_ai_values_raise_config_error(variable: str, value: str) -> None:
    with pytest.raises(ConfigError, match=variable):
        load_config(environ={variable: value}, env_file=None)


@pytest.mark.parametrize(
    ("dotenv_value", "process_env", "expected"),
    [
        ("true", {}, True),  # só .env: vale o .env
        ("true", {"AEGIS_AI_ENABLED": "false"}, False),  # processo prevalece
        ("false", {"AEGIS_AI_ENABLED": "true"}, True),  # processo prevalece
        ("true", {"AEGIS_AI_ENABLED": ""}, False),  # vazio no processo = padrão
        ("true", {"AEGIS_AI_ENABLED": "   "}, False),  # só espaços = vazio
        ("", {}, False),  # vazio no .env = padrão
        (None, {}, False),  # ausente nos dois = padrão
    ],
)
def test_precedence_between_process_environment_and_dotenv(
    tmp_path: Path, dotenv_value: str | None, process_env: dict[str, str], expected: bool
) -> None:
    env_file = tmp_path / ".env"
    lines = "AEGIS_LOG_LEVEL=WARNING\n"
    if dotenv_value is not None:
        lines += f"AEGIS_AI_ENABLED={dotenv_value}\n"
    env_file.write_text(lines, encoding="utf-8")

    config = load_config(environ=process_env, env_file=env_file)

    assert config.ai.enabled is expected
    assert config.log_level == "WARNING"  # demais variáveis do .env continuam valendo


def test_empty_process_variable_matches_python_dotenv_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dotenv import load_dotenv

    env_file = tmp_path / ".env"
    env_file.write_text("AEGIS_AI_ENABLED=true\n", encoding="utf-8")
    monkeypatch.setenv("AEGIS_AI_ENABLED", "")

    load_dotenv(env_file, override=False)  # referência: python-dotenv mantém o vazio

    assert os.environ["AEGIS_AI_ENABLED"] == ""
    assert load_config(environ=dict(os.environ), env_file=env_file).ai.enabled is False


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://127.0.0.1:11434", "http://127.0.0.1:11434"),
        ("http://127.0.0.1:11434/", "http://127.0.0.1:11434"),
        ("http://127.0.0.1:11434/api", "http://127.0.0.1:11434"),
        ("http://127.0.0.1:11434/api/", "http://127.0.0.1:11434"),
        ("http://127.0.0.1:11434/api/chat", "http://127.0.0.1:11434"),
        ("http://localhost:11434/ollama/api", "http://localhost:11434/ollama"),
        ("http://localhost:11434/ollama", "http://localhost:11434/ollama"),
        ("http://localhost:11434/myapi", "http://localhost:11434/myapi"),
        ("http://[::1]:11434/api", "http://[::1]:11434"),
    ],
)
def test_ollama_base_url_is_normalized(url: str, expected: str) -> None:
    config = load_config(environ={"AEGIS_OLLAMA_BASE_URL": url}, env_file=None)

    assert config.ai.ollama_base_url == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://api.exemplo.com/api",
        "http://192.168.0.10:11434/api/chat",
        "http://127.0.0.1:11434@exemplo.com/api",
        "http://@127.0.0.1:11434/api",
        "http://127.0.0.1:11434/api?redirect=http://exemplo.com",
    ],
)
def test_normalization_does_not_bypass_url_validation(url: str) -> None:
    with pytest.raises(ConfigError, match="AEGIS_OLLAMA_BASE_URL"):
        load_config(environ={"AEGIS_OLLAMA_BASE_URL": url}, env_file=None)


def test_normalized_url_produces_single_api_chat_path() -> None:
    from ai.ollama import OllamaProvider
    from tests.helpers import FakeOpener

    base = load_config(
        environ={"AEGIS_OLLAMA_BASE_URL": "http://127.0.0.1:11434/api/"}, env_file=None
    ).ai.ollama_base_url
    opener = FakeOpener(b'{"message": {"role": "assistant", "content": "ok"}}')

    OllamaProvider(base_url=base, model="m", timeout_seconds=1, opener=opener).chat([])

    assert opener.requests[0][0].full_url == "http://127.0.0.1:11434/api/chat"
