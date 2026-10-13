"""Ciclo de vida da aplicação, com transições de estado validadas."""

from __future__ import annotations

from enum import StrEnum

from core.exceptions import InvalidStateTransitionError


class AppStatus(StrEnum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


_ALLOWED_TRANSITIONS: dict[AppStatus, frozenset[AppStatus]] = {
    AppStatus.CREATED: frozenset({AppStatus.STARTING}),
    AppStatus.STARTING: frozenset({AppStatus.RUNNING, AppStatus.FAILED}),
    AppStatus.RUNNING: frozenset({AppStatus.STOPPING, AppStatus.FAILED}),
    AppStatus.STOPPING: frozenset({AppStatus.STOPPED, AppStatus.FAILED}),
    AppStatus.STOPPED: frozenset(),
    AppStatus.FAILED: frozenset(),
}


class ApplicationState:
    """Mantém o status atual da aplicação e o histórico de transições."""

    def __init__(self) -> None:
        self._history: list[AppStatus] = [AppStatus.CREATED]

    @property
    def status(self) -> AppStatus:
        return self._history[-1]

    @property
    def history(self) -> tuple[AppStatus, ...]:
        return tuple(self._history)

    def can_transition_to(self, target: AppStatus) -> bool:
        return target in _ALLOWED_TRANSITIONS[self.status]

    def transition_to(self, target: AppStatus) -> None:
        if not self.can_transition_to(target):
            raise InvalidStateTransitionError(
                f"Transição de estado inválida: {self.status} -> {target}."
            )
        self._history.append(target)
