from __future__ import annotations

from pathlib import Path

import pytest

from core.config import (
    DEFAULT_LOG_DIR,
    PROJECT_ROOT,
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
