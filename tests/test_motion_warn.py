"""Tests for the motion-trigger entity warnings."""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ai_camera_centre import (
    _warn_trigger_device_mismatch,
    _warn_unknown_motion_entities,
)


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


def _camera_with_trigger(hass: HomeAssistant, same_device: bool):
    """Register a camera entity and one trigger, on the same or another device."""
    entry = MockConfigEntry(domain="reolink")
    entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    cam_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("reolink", "front_garden")},
        name="Front Garden",
    )
    other_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("reolink", "back_garden")},
        name="Back Garden",
    )
    camera = ent_reg.async_get_or_create(
        "camera", "reolink", "fg_cam", device_id=cam_device.id
    )
    trigger = ent_reg.async_get_or_create(
        "binary_sensor",
        "reolink",
        "trigger",
        device_id=cam_device.id if same_device else other_device.id,
    )
    return ent_reg, dev_reg, camera.entity_id, trigger.entity_id


async def test_warns_when_trigger_is_on_another_device(
    hass: HomeAssistant, caplog
) -> None:
    ent_reg, dev_reg, camera_entity, trigger = _camera_with_trigger(
        hass, same_device=False
    )

    with caplog.at_level(logging.WARNING):
        _warn_trigger_device_mismatch(
            hass, ent_reg, dev_reg, "Front Garden", camera_entity, [trigger]
        )

    assert trigger in caplog.text
    # Names the offending device so the mis-pick is obvious.
    assert "Back Garden" in caplog.text


async def test_no_warning_when_trigger_shares_the_camera_device(
    hass: HomeAssistant, caplog
) -> None:
    ent_reg, dev_reg, camera_entity, trigger = _camera_with_trigger(
        hass, same_device=True
    )

    with caplog.at_level(logging.WARNING):
        _warn_trigger_device_mismatch(
            hass, ent_reg, dev_reg, "Front Garden", camera_entity, [trigger]
        )

    assert "different device" not in caplog.text


async def test_helper_without_device_is_not_flagged(
    hass: HomeAssistant, caplog
) -> None:
    """input_boolean/switch helpers have no device; they must not warn."""
    ent_reg, dev_reg, camera_entity, _ = _camera_with_trigger(hass, same_device=True)

    with caplog.at_level(logging.WARNING):
        _warn_trigger_device_mismatch(
            hass,
            ent_reg,
            dev_reg,
            "Front Garden",
            camera_entity,
            ["input_boolean.test_motion"],
        )

    assert "different device" not in caplog.text
