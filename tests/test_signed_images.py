"""Tests for signed, authenticated alert-image serving."""
from __future__ import annotations

import io
import os

from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ai_camera_centre.const import DOMAIN, IMAGES_URL, SNAPSHOTS_URL

# ai_task -> conversation -> hassil isn't installed in CI; mark present.
STUB_COMPONENTS = ("camera", "ai_task", "conversation", "media_source")


def _png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


async def _setup(hass: HomeAssistant) -> None:
    for comp in STUB_COMPONENTS:
        hass.config.components.add(comp)
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={"retention_days": 7})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _log_alert(hass: HomeAssistant) -> dict:
    store = hass.data[DOMAIN]["store"]
    src = os.path.join(store.snapshots_dir, "side_gate_x.jpg")
    with open(src, "wb") as fh:
        fh.write(_png())
    return await store.async_log(
        {
            "camera_id": "side_gate",
            "camera_label": "Side Gate",
            "image_path": src,
            "score": 5,
            "short": "s",
            "detail": "d",
            "direction": "unknown",
            "carrying": "nothing",
            "activity": "walking",
            "gate_state": "n/a",
            "gate_risk": "n/a",
            "known_person": "none",
        }
    )


async def _first_alert_image(hass, hass_ws_client) -> str:
    ws = await hass_ws_client(hass)
    await ws.send_json({"id": 1, "type": "ai_camera_centre/alerts"})
    msg = await ws.receive_json()
    assert msg["success"]
    alerts = msg["result"]["alerts"]
    assert len(alerts) == 1
    return alerts[0]["image"]


async def test_alerts_ws_returns_signed_image(hass, hass_ws_client):
    await _setup(hass)
    await _log_alert(hass)
    img = await _first_alert_image(hass, hass_ws_client)
    assert img.startswith(IMAGES_URL + "/")
    assert "authSig=" in img


async def test_signed_url_served_and_unsigned_rejected(
    hass, hass_ws_client, hass_client_no_auth
):
    await _setup(hass)
    await _log_alert(hass)
    signed = await _first_alert_image(hass, hass_ws_client)
    client = await hass_client_no_auth()

    # a valid signed URL is served without any bearer token
    resp = await client.get(signed)
    assert resp.status == 200

    # the same path without its signature is rejected
    resp = await client.get(signed.split("?", 1)[0])
    assert resp.status == 401


async def test_snapshot_static_path_still_unauthenticated(hass, hass_client_no_auth):
    await _setup(hass)
    store = hass.data[DOMAIN]["store"]
    fname = "cam_tok_1.jpg"
    with open(os.path.join(store.snapshots_dir, fname), "wb") as fh:
        fh.write(_png())
    client = await hass_client_no_auth()
    resp = await client.get(f"{SNAPSHOTS_URL}/{fname}")
    assert resp.status == 200
