"""Tests for the CameraPipeline motion-ignore processing gate."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.ai_camera_centre import AlertStore
from custom_components.ai_camera_centre.analyzer import CameraPipeline
from custom_components.ai_camera_centre.const import (
    ARMED_ONLY_ARMED,
    ARMED_ONLY_DISARMED,
    CONF_ALARM_PANEL_ENTITY,
    CONF_CAMERA_ENTITY,
    CONF_CAMERA_MOTION_POLICY,
    CONF_PROCESS_ARMED,
    CONF_PROCESS_PRESENCE,
    CONF_PROCESS_TIME_MODE,
    CONF_SUN_ENTITY,
    POLICY_CUSTOM,
    PRESENCE_ONLY_AWAY,
    PRESENCE_ONLY_HOME,
    TIME_DAY,
    TIME_NIGHT,
)

ALARM = "alarm_control_panel.home"


def _pipeline(hass, tmp_path, global_options=None, camera_conf=None):
    store = AlertStore(hass, str(tmp_path / "acc"), 7)
    camera_conf = {CONF_CAMERA_ENTITY: "camera.side", **(camera_conf or {})}
    return CameraPipeline(
        hass, store, global_options or {}, "side_gate", camera_conf, targets=[]
    )


# -- presence gate -------------------------------------------------------


@pytest.mark.parametrize(
    ("person_state", "expected"),
    [("home", False), ("not_home", True)],
)
async def test_presence_only_away(hass, tmp_path, person_state, expected):
    hass.states.async_set("person.ben", person_state)
    p = _pipeline(hass, tmp_path, {CONF_PROCESS_PRESENCE: PRESENCE_ONLY_AWAY})
    assert p._should_process() is expected


async def test_presence_only_home(hass, tmp_path):
    hass.states.async_set("person.ben", "home")
    p = _pipeline(hass, tmp_path, {CONF_PROCESS_PRESENCE: PRESENCE_ONLY_HOME})
    assert p._should_process() is True
    hass.states.async_set("person.ben", "not_home")
    assert p._should_process() is False


async def test_presence_no_person_entities_treated_as_away(hass, tmp_path):
    p = _pipeline(hass, tmp_path, {CONF_PROCESS_PRESENCE: PRESENCE_ONLY_AWAY})
    assert p._should_process() is True


# -- alarm gate ----------------------------------------------------------


async def test_armed_only_armed(hass, tmp_path):
    opts = {CONF_PROCESS_ARMED: ARMED_ONLY_ARMED, CONF_ALARM_PANEL_ENTITY: ALARM}
    p = _pipeline(hass, tmp_path, opts)
    hass.states.async_set(ALARM, "armed_away")
    assert p._should_process() is True
    hass.states.async_set(ALARM, "disarmed")
    assert p._should_process() is False


async def test_armed_only_disarmed(hass, tmp_path):
    opts = {CONF_PROCESS_ARMED: ARMED_ONLY_DISARMED, CONF_ALARM_PANEL_ENTITY: ALARM}
    p = _pipeline(hass, tmp_path, opts)
    hass.states.async_set(ALARM, "disarmed")
    assert p._should_process() is True
    hass.states.async_set(ALARM, "armed_home")
    assert p._should_process() is False


async def test_armed_gate_fails_open_without_panel(hass, tmp_path):
    # only_armed but no alarm panel configured -> process anyway (fail open)
    p = _pipeline(hass, tmp_path, {CONF_PROCESS_ARMED: ARMED_ONLY_ARMED})
    assert p._should_process() is True


# -- time gate (sun-based) ----------------------------------------------


@pytest.mark.parametrize(
    ("mode", "sun", "expected"),
    [
        (TIME_DAY, "above_horizon", True),
        (TIME_DAY, "below_horizon", False),
        (TIME_NIGHT, "below_horizon", True),
        (TIME_NIGHT, "above_horizon", False),
    ],
)
async def test_time_day_night(hass, tmp_path, mode, sun, expected):
    hass.states.async_set("sun.sun", sun)
    p = _pipeline(
        hass, tmp_path, {CONF_PROCESS_TIME_MODE: mode, CONF_SUN_ENTITY: "sun.sun"}
    )
    assert p._should_process() is expected


async def test_time_gate_fails_open_when_sun_unknown(hass, tmp_path):
    hass.states.async_set("sun.sun", "unavailable")
    for mode in (TIME_DAY, TIME_NIGHT):
        p = _pipeline(hass, tmp_path, {CONF_PROCESS_TIME_MODE: mode})
        assert p._should_process() is True
    assert p._is_daytime() is None


# -- factors combine with AND -------------------------------------------


async def test_factors_combine_with_and(hass, tmp_path):
    hass.states.async_set("person.ben", "home")
    hass.states.async_set("sun.sun", "below_horizon")
    opts = {
        CONF_PROCESS_PRESENCE: PRESENCE_ONLY_AWAY,
        CONF_PROCESS_TIME_MODE: TIME_NIGHT,
    }
    p = _pipeline(hass, tmp_path, opts)
    # night passes but presence fails -> overall skip
    assert p._should_process() is False
    hass.states.async_set("person.ben", "not_home")
    assert p._should_process() is True


# -- per-camera custom policy overrides the house -----------------------


async def test_camera_custom_policy_overrides_house(hass, tmp_path):
    hass.states.async_set("person.ben", "home")
    global_opts = {CONF_PROCESS_PRESENCE: PRESENCE_ONLY_AWAY}
    camera_conf = {
        CONF_CAMERA_MOTION_POLICY: POLICY_CUSTOM,
        CONF_PROCESS_PRESENCE: PRESENCE_ONLY_HOME,
    }
    p = _pipeline(hass, tmp_path, global_opts, camera_conf)
    # house would skip (someone home), but camera custom = only_home -> process
    assert p._should_process() is True


# -- async_analyze honours the gate and the force bypass ----------------


async def test_async_analyze_skips_when_gate_blocks(hass, tmp_path):
    hass.states.async_set("person.ben", "home")
    p = _pipeline(hass, tmp_path, {CONF_PROCESS_PRESENCE: PRESENCE_ONLY_AWAY})
    p._run = AsyncMock()
    await p.async_analyze(force=False)
    p._run.assert_not_awaited()
    # a manual/forced run bypasses the gate
    await p.async_analyze(force=True)
    p._run.assert_awaited_once()


async def test_async_analyze_runs_when_gate_allows(hass, tmp_path):
    hass.states.async_set("person.ben", "not_home")
    p = _pipeline(hass, tmp_path, {CONF_PROCESS_PRESENCE: PRESENCE_ONLY_AWAY})
    p._run = AsyncMock()
    await p.async_analyze(force=False)
    p._run.assert_awaited_once()
