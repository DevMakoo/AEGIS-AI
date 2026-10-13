"""Ponto de entrada da aplicação AEGIS."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

from app import APP_NAME, __version__
from app.bootstrap import bootstrap
from app.terminal import InputFn, OutputFn, run_terminal
from core.command_handlers import build_default_registry
from core.config import DEFAULT_ENV_FILE, load_config
from core.conversation import ConversationSession
from core.exceptions import ConfigError, StartupError

EXIT_OK = 0
EXIT_STARTUP_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_INTERRUPTED = 130


def main(
    environ: Mapping[str, str] | None = None,
    env_file: Path | None = DEFAULT_ENV_FILE,
    *,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
) -> int:
    """Inicializa o AEGIS, executa a sessão no terminal e retorna o código de saída."""
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

    try:
        session = ConversationSession(build_default_registry(), app.state, app_version=__version__)
        try:
            run_terminal(
                session,
                title=f"{APP_NAME} v{__version__}",
                input_fn=input_fn,
                output_fn=output_fn,
            )
        except KeyboardInterrupt:
            # Ctrl+C fora da leitura de entrada (ex.: durante a escrita da resposta).
            session.close("interrupção pelo teclado")
            return EXIT_INTERRUPTED
    finally:
        app.shutdown()
    return EXIT_OK
