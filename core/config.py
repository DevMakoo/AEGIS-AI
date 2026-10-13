"""Carregamento centralizado das configurações do AEGIS.

Ordem de precedência (da menor para a maior):
1. Valores padrão definidos em ``AppConfig``.
2. Arquivo ``.env`` na raiz do projeto (opcional).
3. Variáveis de ambiente do processo.

Uma variável presente no ambiente do processo prevalece sobre o ``.env`` mesmo
quando está vazia — a mesma regra de ``python-dotenv`` (``override=False``). Valores
vazios ou só com espaços, venham de onde vierem, equivalem a "não definido" e usam
o padrão. Exemplo: ``.env`` com ``AEGIS_AI_ENABLED=true`` e processo com
``AEGIS_AI_ENABLED=`` (vazio) resulta em ``false`` (padrão).

Todas as variáveis usam o prefixo ``AEGIS_``.
"""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import dotenv_values

from core.exceptions import ConfigError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"

VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
SUPPORTED_LANGUAGES = frozenset({"pt-BR"})

DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
AI_TIMEOUT_RANGE = (1.0, 600.0)
AI_HISTORY_RANGE = (2, 200)

_TRUE_VALUES = frozenset({"1", "true", "yes", "on", "sim"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", "nao", "não"})


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class AIProviderName(StrEnum):
    """Provedores de IA suportados. Novos provedores (ex.: online) entram aqui e em
    ``ai/factory.py``; valores desconhecidos são rejeitados, nunca substituídos."""

    OLLAMA = "ollama"


@dataclass(frozen=True, slots=True)
class AIConfig:
    enabled: bool = False
    provider: AIProviderName = AIProviderName.OLLAMA
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL
    # Sem padrão: não presumimos que algum modelo esteja instalado.
    ollama_model: str | None = None
    # Hosts fora do loopback exigem autorização explícita.
    ollama_allow_remote: bool = False
    timeout_seconds: float = 60.0
    # Mensagens de usuário/assistente mantidas (a mensagem de sistema não conta).
    max_history_messages: int = 20
    # ``None`` usa a mensagem de sistema padrão de ``ai/prompts.py``.
    system_prompt: str | None = None


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
    ai: AIConfig = field(default_factory=AIConfig)
    # Reservado para um provedor online (fase futura); não é usado nesta fase.
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
        ai=_parse_ai(get, defaults.ai),
        ai_api_key=SecretStr(key) if (key := get("AI_API_KEY")) else None,
    )


def _parse_ai(get: Callable[[str], str | None], defaults: AIConfig) -> AIConfig:
    allow_remote = _parse_bool(
        "AEGIS_OLLAMA_ALLOW_REMOTE", get("OLLAMA_ALLOW_REMOTE"), defaults.ollama_allow_remote
    )
    return AIConfig(
        enabled=_parse_bool("AEGIS_AI_ENABLED", get("AI_ENABLED"), defaults.enabled),
        provider=_parse_provider(get("AI_PROVIDER"), defaults.provider),
        ollama_base_url=_parse_ollama_url(
            get("OLLAMA_BASE_URL"), defaults.ollama_base_url, allow_remote=allow_remote
        ),
        ollama_model=_parse_model(get("OLLAMA_MODEL")),
        ollama_allow_remote=allow_remote,
        timeout_seconds=_parse_float_in_range(
            "AEGIS_AI_TIMEOUT_SECONDS",
            get("AI_TIMEOUT_SECONDS"),
            defaults.timeout_seconds,
            AI_TIMEOUT_RANGE,
        ),
        max_history_messages=_parse_int_in_range(
            "AEGIS_AI_MAX_HISTORY_MESSAGES",
            get("AI_MAX_HISTORY_MESSAGES"),
            defaults.max_history_messages,
            AI_HISTORY_RANGE,
        ),
        system_prompt=get("AI_SYSTEM_PROMPT"),
    )


def _parse_provider(raw: str | None, default: AIProviderName) -> AIProviderName:
    if raw is None:
        return default
    try:
        return AIProviderName(raw.lower())
    except ValueError:
        options = ", ".join(p.value for p in AIProviderName)
        raise ConfigError(
            f"AEGIS_AI_PROVIDER não suportado: '{raw}'. Valores aceitos: {options}."
        ) from None


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _parse_ollama_url(raw: str | None, default: str, *, allow_remote: bool) -> str:
    value = default if raw is None else raw
    name = "AEGIS_OLLAMA_BASE_URL"
    try:
        parts = urlsplit(value)
        _ = parts.port  # levanta ValueError se a porta for inválida
    except ValueError:
        raise ConfigError(f"{name} inválido: '{value}'.") from None
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ConfigError(f"{name} inválido: '{value}'. Use http(s)://host:porta.")
    if "@" in parts.netloc:
        raise ConfigError(f"{name} não pode conter usuário ou senha.")
    if parts.query or parts.fragment:
        raise ConfigError(f"{name} não pode conter parâmetros (?...) ou fragmentos (#...).")
    if not allow_remote and not _is_loopback(parts.hostname.lower()):
        raise ConfigError(
            f"{name} aponta para um host não local ('{parts.hostname}'). As mensagens sairiam "
            "deste computador; para permitir isso de forma explícita, defina "
            "AEGIS_OLLAMA_ALLOW_REMOTE=true."
        )
    # Normalização feita só sobre o caminho, depois das validações de host: não altera
    # esquema, host ou porta. Aceita a raiz, um prefixo (proxy reverso) ou URLs que já
    # terminam em /api ou /api/chat, evitando /api/api/chat.
    path = parts.path.rstrip("/")
    for suffix in ("/api/chat", "/api"):
        if path.endswith(suffix):
            path = path.removesuffix(suffix)
            break
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _parse_model(raw: str | None) -> str | None:
    if raw is None:
        return None
    if any(c.isspace() for c in raw):
        raise ConfigError(f"AEGIS_OLLAMA_MODEL inválido: '{raw}'. Não use espaços.")
    return raw


def _parse_float_in_range(
    name: str, raw: str | None, default: float, bounds: tuple[float, float]
) -> float:
    if raw is None:
        return default
    try:
        value = float(raw.replace(",", "."))
    except ValueError:
        raise ConfigError(f"{name} inválido: '{raw}'. Use um número.") from None
    low, high = bounds
    if not low <= value <= high:  # também rejeita nan
        raise ConfigError(f"{name} fora do intervalo: '{raw}'. Use entre {low:g} e {high:g}.")
    return value


def _parse_int_in_range(name: str, raw: str | None, default: int, bounds: tuple[int, int]) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} inválido: '{raw}'. Use um número inteiro.") from None
    low, high = bounds
    if not low <= value <= high:
        raise ConfigError(f"{name} fora do intervalo: '{raw}'. Use entre {low} e {high}.")
    return value


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
