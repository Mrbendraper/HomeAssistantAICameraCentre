"""End-to-end tests for the known-photo upload endpoint and WS commands.

These exercise the live Home Assistant HTTP/websocket stack, so they also
verify the framework touch-points that static checks can't: KEY_HASS,
request["hass_user"], HomeAssistantView registration and the websocket
command handlers.
"""
from __future__ import annotations

import io

import aiohttp

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ai_camera_centre.const import (
    CONF_VISITOR_DESCRIPTION,
    CONF_VISITOR_ID,
    CONF_VISITOR_NAME,
    DOMAIN,
    SUBENTRY_KNOWN_VISITOR,
    UPLOAD_URL,
)


def _png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={"retention_days": 7},
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_KNOWN_VISITOR,
                title="Ben",
                unique_id="ben",
                data={
                    CONF_VISITOR_ID: "ben",
                    CONF_VISITOR_NAME: "Ben",
                    CONF_VISITOR_DESCRIPTION: "tall",
                },
            )
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _upload_form(visitor_id: str, data: bytes, content_type="image/png") -> aiohttp.FormData:
    form = aiohttp.FormData()
    form.add_field("visitor_id", visitor_id)
    form.add_field("file", data, filename="p.png", content_type=content_type)
    return form


async def test_upload_then_list_then_delete(hass, hass_client, hass_ws_client):
    await _setup(hass)
    client = await hass_client()

    # upload
    resp = await client.post(UPLOAD_URL, data=_upload_form("ben", _png()))
    assert resp.status == 200
    payload = await resp.json()
    assert payload["url"].startswith("/ai_camera_centre/known/ben/")
    fname = payload["filename"]

    # WS visitors reflects the new photo
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "ai_camera_centre/visitors"})
    msg = await ws.receive_json()
    assert msg["success"]
    visitors = msg["result"]["visitors"]
    assert len(visitors) == 1
    assert visitors[0]["visitor_id"] == "ben"
    assert [p["filename"] for p in visitors[0]["photos"]] == [fname]

    # WS delete
    await ws.send_json(
        {
            "id": 2,
            "type": "ai_camera_centre/delete_visitor_photo",
            "visitor_id": "ben",
            "filename": fname,
        }
    )
    msg = await ws.receive_json()
    assert msg["success"] and msg["result"]["deleted"] is True


async def test_upload_unknown_visitor_rejected(hass, hass_client):
    await _setup(hass)
    client = await hass_client()
    resp = await client.post(UPLOAD_URL, data=_upload_form("nobody", _png()))
    assert resp.status == 400
    assert "Unknown visitor" in await resp.text()


async def test_upload_invalid_image_does_not_leak_detail(hass, hass_client):
    """Regression for the CodeQL fix: no exception detail in the response."""
    await _setup(hass)
    client = await hass_client()
    resp = await client.post(
        UPLOAD_URL, data=_upload_form("ben", b"not really an image")
    )
    assert resp.status == 400
    body = await resp.text()
    assert body == "Unable to save uploaded photo"
    # underlying Pillow/exception text must not be exposed
    assert "cannot identify" not in body.lower()
    assert "Invalid image" not in body


async def test_upload_requires_authentication(hass, hass_client_no_auth):
    await _setup(hass)
    client = await hass_client_no_auth()
    resp = await client.post(UPLOAD_URL, data=_upload_form("ben", _png()))
    assert resp.status == 401
