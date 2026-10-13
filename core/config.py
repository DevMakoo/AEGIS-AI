"""Carregamento centralizado das configurações do AEGIS.

Ordem de precedência (da menor para a maior):
1. Valores padrão definidos em ``AppConfig``.
2. Arquivo ``.env`` na raiz do projeto (opcional).
3. Variáveis de ambiente do processo.

Todas as variáveis usam o prefixo ``AEGIS_``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from dotenv import dotenv_values

from core.exceptions import ConfigError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"

VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
SUPPORTED_LANGUAGES = frozenset({"pt-BR"})

_TRUE_VALUES = frozenset({"1", "true", "yes", "on", "sim"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", "nao", "não"})


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class SecretStr:
    """Envolve um valor sensível para que ele nunca apareça em repr/str/logs."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "SecretStr('**********')"

    def __str__(self) -> str:
        return "**********"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SecretStr) and other._value == self._value

    def __hash__(self) -> int:
        return hash(self._value)


@dataclass(frozen=True, slots=True)
class AppConfig:
    environment: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    log_dir: Path = DEFAULT_LOG_DIR
    log_to_file: bool = True
    language: str = "pt-BR"
    # Reservado para a integração com IA (fase futura); não é usado nesta fase.
    ai_api_key: SecretStr | None = field(default=None, repr=False)

    def secret_values(self) -> tuple[str, ...]:
        """Valores que nunca devem aparecer em logs."""
        if self.ai_api_key is None:
            return ()
        return (self.ai_api_key.get_secret_value(),)


def load_config(
    environ: Mapping[str, str] | None = None,
    env_file: Path | None = DEFAULT_ENV_FILE,
) -> AppConfig:
    """Monta a configuração a partir do ``.env`` e das variáveis de ambiente.

    ``environ`` e ``env_file`` existem para permitir testes isolados; em uso
    normal, os valores padrão leem ``os.environ`` e o ``.env`` da raiz.
    """
    values: dict[str, str] = {}
    if env_file is not None and env_file.is_file():
        values.update({k: v for k, v in dotenv_values(env_file).items() if v is not None})
    values.update(os.environ if environ is None else environ)

    def get(name: str) -> str | None:
        raw = values.get(f"AEGIS_{name}")
        if raw is None or not raw.strip():
            return None
        return raw.strip()

    defaults = AppConfig()
    return AppConfig(
        environment=_parse_environment(get("ENV"), defaults.environment),
        log_level=_parse_log_level(get("LOG_LEVEL"), defaults.log_level),
        log_dir=_parse_path(get("LOG_DIR"), defaults.log_dir),
        log_to_file=_parse_bool("AEGIS_LOG_TO_FILE", get("LOG_TO_FILE"), defaults.log_to_file),
        language=_parse_language(get("LANGUAGE"), defaults.language),
        ai_api_key=SecretStr(key) if (key := get("AI_API_KEY")) else None,
    )


def _parse_environment(raw: str | None, default: Environment) -> Environment:
    if raw is None:
        return default
    try:
        return Environment(raw.lower())
    except ValueError:
        options = ", ".join(e.value for e in Environment)
        raise ConfigError(f"AEGIS_ENV inválido: '{raw}'. Valores aceitos: {options}.") from None


def _parse_log_level(raw: str | None, default: str) -> str:
    if raw is None:
        return default
    level = raw.upper()
    if level not in VALID_LOG_LEVELS:
        options = ", ".join(sorted(VALID_LOG_LEVELS))
        raise ConfigError(f"AEGIS_LOG_LEVEL inválido: '{raw}'. Valores aceitos: {options}.")
    return level


def _parse_path(raw: str | None, default: Path) -> Path:
    if raw is None:
        return default
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _parse_bool(name: str, raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ConfigError(f"{name} inválido: '{raw}'. Use true/false.")


def _parse_language(raw: str | None, default: str) -> str:
    if raw is None:
        return default
    if raw not in SUPPORTED_LANGUAGES:
        options = ", ".join(sorted(SUPPORTED_LANGUAGES))
        raise ConfigError(f"AEGIS_LANGUAGE não suportado: '{raw}'. Valores aceitos: {options}.")
    return raw
