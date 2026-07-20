"""Tests for recording analysis activity to the Home Assistant logbook.

Sub-threshold and failed analyses never reach the alert history, so the
pipeline writes a logbook line for every outcome — otherwise a working but
quiet camera looks dead in its Activity timeline.
"""
from __future__ import annotations

from types import SimpleNamespace

from homeassistant.components.logbook import EVENT_LOGBOOK_ENTRY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.ai_camera_centre.analyzer import CameraPipeline
from custom_components.ai_camera_centre.const import DOMAIN


def _pipeline(hass: HomeAssistant, enabled: bool) -> SimpleNamespace:
    """A stand-in carrying just the attributes _record_activity touches."""
    return SimpleNamespace(
        log_activity=enabled,
        hass=hass,
        camera_id="back_garden",
        label="Back Garden",
    )


def _register_recent_alert(hass: HomeAssistant) -> str:
    return er.async_get(hass).async_get_or_create(
        "binary_sensor", DOMAIN, "back_garden_recent_alert"
    ).entity_id


async def test_activity_is_logged_against_the_camera_entity(
    hass: HomeAssistant,
) -> None:
    entity_id = _register_recent_alert(hass)
    events = async_capture_events(hass, EVENT_LOGBOOK_ENTRY)

    CameraPipeline._record_activity(
        _pipeline(hass, True),
        "Analysed (score 1) — below the log threshold (min 2), not logged",
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["message"].startswith("Analysed (score 1)")
    assert events[0].data["entity_id"] == entity_id
    assert events[0].data["domain"] == DOMAIN


async def test_disabled_records_nothing(hass: HomeAssistant) -> None:
    _register_recent_alert(hass)
    events = async_capture_events(hass, EVENT_LOGBOOK_ENTRY)

    CameraPipeline._record_activity(_pipeline(hass, False), "Analysed (score 1)")
    await hass.async_block_till_done()

    assert events == []


async def test_no_entry_when_camera_entity_missing(hass: HomeAssistant) -> None:
    # No recent_alert entity registered -> nothing to anchor to, no crash.
    events = async_capture_events(hass, EVENT_LOGBOOK_ENTRY)

    CameraPipeline._record_activity(_pipeline(hass, True), "Analysis failed: boom")
    await hass.async_block_till_done()

    assert events == []
