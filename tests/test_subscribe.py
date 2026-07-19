"""Tests for the live-update websocket subscription."""
from __future__ import annotations

import io
import os

from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ai_camera_centre.const import DOMAIN

STUB_COMPONENTS = ("camera", "ai_task", "conversation", "media_source")


def _png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (4, 5, 6)).save(buf, format="PNG")
    return buf.getvalue()


async def _setup(hass: HomeAssistant) -> None:
    for comp in STUB_COMPONENTS:
        hass.config.components.add(comp)
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={"retention_days": 7})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_subscribe_pushes_new_alert(hass, hass_ws_client):
    await _setup(hass)
    ws = await hass_ws_client(hass)

    await ws.send_json({"id": 5, "type": "ai_camera_centre/subscribe"})
    ack = await ws.receive_json()
    assert ack["success"]

    # log an alert -> the subscription should push it as an event on id 5
    store = hass.data[DOMAIN]["store"]
    src = os.path.join(store.snapshots_dir, "side_gate_y.jpg")
    with open(src, "wb") as fh:
        fh.write(_png())
    await hass.services.async_call(
        DOMAIN,
        "log_alert",
        {"camera_id": "side_gate", "image_path": src, "score": 6, "short": "hi"},
        blocking=True,
    )

    msg = await ws.receive_json()
    assert msg["type"] == "event"
    assert msg["id"] == 5
    alert = msg["event"]["alert"]
    assert alert["score"] == 6
    assert alert["short"] == "hi"
    assert "authSig=" in alert["image"]
