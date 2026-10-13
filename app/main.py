"""Ponto de entrada da aplicação AEGIS."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

from app import APP_NAME, __version__
from app.bootstrap import bootstrap
from core.config import DEFAULT_ENV_FILE, load_config
from core.exceptions import ConfigError, StartupError

EXIT_OK = 0
EXIT_STARTUP_ERROR = 1
EXIT_CONFIG_ERROR = 2


def main(
    environ: Mapping[str, str] | None = None,
    env_file: Path | None = DEFAULT_ENV_FILE,
) -> int:
    """Inicializa o AEGIS e retorna o código de saída do processo."""
    try:
        config = load_config(environ=environ, env_file=env_file)
    except ConfigError as exc:
        print(f"[{APP_NAME}] Erro de configuração: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    try:
        app = bootstrap(config)
    except StartupError as exc:
        print(f"[{APP_NAME}] Falha na inicialização: {exc}", file=sys.stderr)
        return EXIT_STARTUP_ERROR

    print(f"{APP_NAME} v{__version__}")
    print("Assistente pessoal inteligente — aplicação inicializada.")
    print("Nenhum módulo interativo disponível nesta fase. Encerrando.")
    app.shutdown()
    return EXIT_OK
