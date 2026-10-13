from __future__ import annotations

import pytest

from core.exceptions import InvalidStateTransitionError
from core.state import ApplicationState, AppStatus


def test_full_lifecycle_is_recorded() -> None:
    state = ApplicationState()

    for status in (AppStatus.STARTING, AppStatus.RUNNING, AppStatus.STOPPING, AppStatus.STOPPED):
        state.transition_to(status)

    assert state.status is AppStatus.STOPPED
    assert state.history == (
        AppStatus.CREATED,
        AppStatus.STARTING,
        AppStatus.RUNNING,
        AppStatus.STOPPING,
        AppStatus.STOPPED,
    )


def test_invalid_transition_is_rejected() -> None:
    state = ApplicationState()

    with pytest.raises(InvalidStateTransitionError):
        state.transition_to(AppStatus.RUNNING)
    assert state.status is AppStatus.CREATED


def test_failed_is_terminal() -> None:
    state = ApplicationState()
    state.transition_to(AppStatus.STARTING)
    state.transition_to(AppStatus.FAILED)

    assert not state.can_transition_to(AppStatus.STARTING)
