"""Tests for the per-camera Analysis switch restore behaviour.

A reload or unclean shutdown can leave the saved state as "unavailable" or
"unknown". Treating those as "off" silently pauses the camera's analysis
indefinitely, so they must fall back to the default (on) instead.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import State

from custom_components.ai_camera_centre.switch import AnalysisSwitch


def _switch() -> tuple[AnalysisSwitch, SimpleNamespace]:
    pipeline = SimpleNamespace(camera_id="side_gate", label="Side Gate", paused=False)
    return AnalysisSwitch(pipeline), pipeline


@pytest.mark.parametrize("restored", ["unavailable", "unknown"])
async def test_unusable_restore_state_does_not_pause(restored: str) -> None:
    """unavailable/unknown must not be read as "off"."""
    switch, pipeline = _switch()
    switch.async_get_last_state = AsyncMock(
        return_value=State("switch.side_gate_analysis", restored)
    )

    await switch.async_added_to_hass()

    assert switch.is_on is True
    assert pipeline.paused is False


async def test_no_previous_state_defaults_to_on() -> None:
    switch, pipeline = _switch()
    switch.async_get_last_state = AsyncMock(return_value=None)

    await switch.async_added_to_hass()

    assert switch.is_on is True
    assert pipeline.paused is False


async def test_restores_a_real_off() -> None:
    """A deliberate "off" is still honoured across restarts."""
    switch, pipeline = _switch()
    switch.async_get_last_state = AsyncMock(
        return_value=State("switch.side_gate_analysis", "off")
    )

    await switch.async_added_to_hass()

    assert switch.is_on is False
    assert pipeline.paused is True


async def test_restores_a_real_on() -> None:
    switch, pipeline = _switch()
    pipeline.paused = True
    switch.async_get_last_state = AsyncMock(
        return_value=State("switch.side_gate_analysis", "on")
    )

    await switch.async_added_to_hass()

    assert switch.is_on is True
    assert pipeline.paused is False
