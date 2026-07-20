"""Tests for adding a known visitor from the people card."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ai_camera_centre.const import (
    CONF_VISITOR_DESCRIPTION,
    CONF_VISITOR_ID,
    CONF_VISITOR_NAME,
    DOMAIN,
    SUBENTRY_KNOWN_VISITOR,
)

STUB_COMPONENTS = ("camera", "ai_task", "conversation", "media_source")


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    for comp in STUB_COMPONENTS:
        hass.config.components.add(comp)
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={"retention_days": 7})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _visitors(entry: MockConfigEntry) -> list[dict]:
    return [
        dict(sub.data)
        for sub in entry.subentries.values()
        if sub.subentry_type == SUBENTRY_KNOWN_VISITOR
    ]


async def test_add_visitor_creates_subentry(hass, hass_ws_client) -> None:
    entry = await _setup(hass)
    ws = await hass_ws_client(hass)

    await ws.send_json(
        {
            "id": 1,
            "type": "ai_camera_centre/add_visitor",
            "name": "Ben Draper",
            "description": "Tall, usually in a blue coat",
        }
    )
    resp = await ws.receive_json()
    assert resp["success"]
    assert resp["result"]["visitor_id"] == "ben_draper"

    visitors = _visitors(entry)
    assert len(visitors) == 1
    assert visitors[0][CONF_VISITOR_NAME] == "Ben Draper"
    assert visitors[0][CONF_VISITOR_ID] == "ben_draper"
    assert visitors[0][CONF_VISITOR_DESCRIPTION] == "Tall, usually in a blue coat"
    # Adding a subentry schedules a reload; let it settle before teardown.
    await hass.async_block_till_done()


async def test_duplicate_visitor_is_rejected(hass, hass_ws_client) -> None:
    entry = await _setup(hass)
    ws = await hass_ws_client(hass)

    for msg_id in (1, 2):
        await ws.send_json(
            {"id": msg_id, "type": "ai_camera_centre/add_visitor", "name": "Ben"}
        )
        resp = await ws.receive_json()
        if msg_id == 1:
            assert resp["success"]
        else:
            assert not resp["success"]
            assert resp["error"]["code"] == "duplicate_visitor"

    assert len(_visitors(entry)) == 1
    await hass.async_block_till_done()


async def test_blank_name_is_rejected(hass, hass_ws_client) -> None:
    entry = await _setup(hass)
    ws = await hass_ws_client(hass)

    # Whitespace slugifies to nothing, so there is no usable visitor_id.
    await ws.send_json(
        {"id": 1, "type": "ai_camera_centre/add_visitor", "name": "   "}
    )
    resp = await ws.receive_json()
    assert not resp["success"]
    assert resp["error"]["code"] == "invalid_name"
    assert _visitors(entry) == []
    await hass.async_block_till_done()
