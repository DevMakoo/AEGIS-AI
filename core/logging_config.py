"""Configuração de logging do AEGIS, com mascaramento de segredos."""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterable
from logging.handlers import RotatingFileHandler

from core.config import AppConfig
from core.exceptions import StartupError

LOGGER_NAME = "aegis"
LOG_FILE_NAME = "aegis.log"
REDACTED = "***REDACTED***"

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_MAX_LOG_BYTES = 1_000_000
_LOG_BACKUP_COUNT = 3


class SecretRedactingFilter(logging.Filter):
    """Substitui valores secretos conhecidos na mensagem final do log."""

    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        self._secrets = tuple(s for s in secrets if s)

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True
        message = record.getMessage()
        redacted = message
        for secret in self._secrets:
            redacted = redacted.replace(secret, REDACTED)
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True


def get_logger(name: str | None = None) -> logging.Logger:
    """Retorna o logger raiz do AEGIS ou um logger filho (ex.: ``aegis.voice``)."""
    return logging.getLogger(LOGGER_NAME if name is None else f"{LOGGER_NAME}.{name}")


def configure_logging(config: AppConfig) -> logging.Logger:
    """Configura o logger ``aegis``. Pode ser chamada novamente com segurança."""
    shutdown_logging()

    logger = get_logger()
    logger.setLevel(config.log_level)
    logger.propagate = False

    redactor = SecretRedactingFilter(config.secret_values())
    formatter = logging.Formatter(_LOG_FORMAT)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    console.addFilter(redactor)
    logger.addHandler(console)

    if config.log_to_file:
        try:
            config.log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                config.log_dir / LOG_FILE_NAME,
                maxBytes=_MAX_LOG_BYTES,
                backupCount=_LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
        except OSError as exc:
            shutdown_logging()
            raise StartupError(
                f"Não foi possível preparar o arquivo de log em '{config.log_dir}': {exc}"
            ) from exc
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redactor)
        logger.addHandler(file_handler)

    return logger


def shutdown_logging() -> None:
    """Remove e fecha os handlers do logger ``aegis`` (libera arquivos de log)."""
    logger = get_logger()
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
