from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from app import APP_NAME, __version__
from app.bootstrap import bootstrap
from app.main import EXIT_CONFIG_ERROR, EXIT_OK, EXIT_STARTUP_ERROR, main
from core.config import load_config
from core.exceptions import StartupError
from core.logging_config import LOG_FILE_NAME, REDACTED, get_logger
from core.state import AppStatus


@pytest.mark.parametrize(
    "module",
    [
        "ai.provider",
        "ai.ollama",
        "ai.history",
        "ai.prompts",
        "ai.service",
        "ai.factory",
        "app",
        "app.main",
        "app.bootstrap",
        "app.terminal",
        "core",
        "core.command",
        "core.command_registry",
        "core.command_handlers",
        "core.conversation",
        "core.config",
        "core.logging_config",
        "core.exceptions",
        "core.state",
        "ai",
        "voice",
        "interface",
        "automation",
        "memory",
        "main",
    ],
)
def test_main_modules_import(module: str) -> None:
    importlib.import_module(module)


def test_bootstrap_reaches_running_and_writes_log(test_environ: dict[str, str]) -> None:
    config = load_config(environ=test_environ, env_file=None)

    app = bootstrap(config)

    assert app.state.status is AppStatus.RUNNING
    log_file = config.log_dir / LOG_FILE_NAME
    assert log_file.is_file()
    assert "Aplicação inicializada." in log_file.read_text(encoding="utf-8")


def test_shutdown_reaches_stopped_and_is_idempotent(test_environ: dict[str, str]) -> None:
    app = bootstrap(load_config(environ=test_environ, env_file=None))

    app.shutdown()
    app.shutdown()

    assert app.state.status is AppStatus.STOPPED
    assert not get_logger().handlers


def test_bootstrap_fails_when_log_dir_is_unusable(tmp_path: Path) -> None:
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x", encoding="utf-8")
    config = load_config(environ={"AEGIS_LOG_DIR": str(blocker)}, env_file=None)

    with pytest.raises(StartupError, match="arquivo de log"):
        bootstrap(config)


def test_secrets_are_redacted_from_logs(test_environ: dict[str, str]) -> None:
    secret = "sk-test-0123456789"
    config = load_config(environ={**test_environ, "AEGIS_AI_API_KEY": secret}, env_file=None)
    app = bootstrap(config)

    app.logger.info("Chave carregada: %s", secret)
    app.shutdown()

    content = (config.log_dir / LOG_FILE_NAME).read_text(encoding="utf-8")
    assert secret not in content
    assert REDACTED in content


def test_console_shows_only_warnings_and_errors(
    test_environ: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    app = bootstrap(load_config(environ=test_environ, env_file=None))

    app.logger.warning("Aviso visível.")
    app.shutdown()

    err = capsys.readouterr().err
    assert "Aviso visível." in err
    assert "Aplicação inicializada." not in err


def test_main_prints_name_and_version(test_environ: dict[str, str]) -> None:
    output: list[str] = []

    exit_code = main(
        environ=test_environ,
        env_file=None,
        input_fn=lambda prompt: "sair",
        output_fn=output.append,
    )

    assert exit_code == EXIT_OK
    assert output[0] == f"{APP_NAME} v{__version__}"
    assert "Sistema inicializado." in output


def test_main_reports_invalid_config(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(environ={"AEGIS_LOG_LEVEL": "VERBOSE"}, env_file=None)

    assert exit_code == EXIT_CONFIG_ERROR
    assert "Erro de configuração" in capsys.readouterr().err


def test_main_reports_startup_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x", encoding="utf-8")

    exit_code = main(environ={"AEGIS_LOG_DIR": str(blocker)}, env_file=None)

    assert exit_code == EXIT_STARTUP_ERROR
    assert "Falha na inicialização" in capsys.readouterr().err
