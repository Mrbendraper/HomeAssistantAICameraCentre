"""Tests for the missing motion-trigger-entity warning."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.ai_camera_centre import _warn_unknown_motion_entities


async def test_warns_only_for_unknown_entities(
    hass: HomeAssistant, caplog
) -> None:
    ent_reg = er.async_get(hass)
    # A real, present entity should never be reported.
    hass.states.async_set("binary_sensor.real_motion", "off")

    with caplog.at_level(logging.WARNING):
        _warn_unknown_motion_entities(
            hass,
            ent_reg,
            "Side Gate",
            ["binary_sensor.real_motion", "binary_sensor.ghost_motion"],
        )

    assert "binary_sensor.ghost_motion" in caplog.text
    assert "binary_sensor.real_motion" not in caplog.text
    # The camera is named so the user knows which one to fix.
    assert "Side Gate" in caplog.text


async def test_no_warning_when_all_present(
    hass: HomeAssistant, caplog
) -> None:
    ent_reg = er.async_get(hass)
    hass.states.async_set("binary_sensor.driveway_person", "off")

    with caplog.at_level(logging.WARNING):
        _warn_unknown_motion_entities(
            hass, ent_reg, "Driveway", ["binary_sensor.driveway_person"]
        )

    assert "not found" not in caplog.text
