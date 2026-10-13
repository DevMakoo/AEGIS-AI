"""Inicialização da aplicação: logging, estado e registro do ciclo de vida."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app import APP_NAME, __version__
from core.config import AppConfig
from core.exceptions import StartupError
from core.logging_config import configure_logging, shutdown_logging
from core.state import ApplicationState, AppStatus


@dataclass(slots=True)
class Application:
    config: AppConfig
    state: ApplicationState
    logger: logging.Logger

    def shutdown(self) -> None:
        """Encerra a aplicação de forma ordenada. Chamadas repetidas são ignoradas."""
        if self.state.status is not AppStatus.RUNNING:
            return
        self.state.transition_to(AppStatus.STOPPING)
        self.logger.info("Encerrando %s.", APP_NAME)
        self.state.transition_to(AppStatus.STOPPED)
        shutdown_logging()


def bootstrap(config: AppConfig) -> Application:
    """Prepara a aplicação para uso e retorna-a no estado ``RUNNING``."""
    state = ApplicationState()
    state.transition_to(AppStatus.STARTING)

    try:
        logger = configure_logging(config)
    except StartupError:
        state.transition_to(AppStatus.FAILED)
        raise

    logger.info(
        "Iniciando %s v%s (ambiente=%s, idioma=%s).",
        APP_NAME,
        __version__,
        config.environment,
        config.language,
    )
    state.transition_to(AppStatus.RUNNING)
    logger.info("Aplicação inicializada.")
    return Application(config=config, state=state, logger=logger)
