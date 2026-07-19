"""Tests for AlertStore and the known-photo helpers."""
from __future__ import annotations

import io
import os
import time

import pytest

from homeassistant.exceptions import HomeAssistantError

from custom_components.ai_camera_centre import AlertStore, _write_known_photo


def _png_bytes(size=(32, 24), color=(10, 20, 30)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


async def _make_store(hass, tmp_path) -> AlertStore:
    store = AlertStore(hass, str(tmp_path / "acc"), retention_days=7)
    await store.async_load()  # creates images/snapshots/known dirs
    return store


def _alert_data(store: AlertStore, camera_id="side_gate") -> dict:
    src = os.path.join(store.snapshots_dir, f"{camera_id}_x.jpg")
    with open(src, "wb") as fh:
        fh.write(_png_bytes())
    return {
        "camera_id": camera_id,
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


# -- _write_known_photo --------------------------------------------------


def test_write_known_photo_normalises_png_to_jpeg(tmp_path):
    dest = str(tmp_path / "out.jpg")
    _write_known_photo(_png_bytes(size=(4000, 3000)), dest)
    assert os.path.isfile(dest)
    with open(dest, "rb") as fh:
        head = fh.read(3)
    assert head == b"\xff\xd8\xff"  # JPEG magic
    from PIL import Image

    with Image.open(dest) as img:
        assert max(img.size) <= 1024  # downscaled


def test_write_known_photo_rejects_non_image(tmp_path):
    with pytest.raises(HomeAssistantError):
        _write_known_photo(b"not an image", str(tmp_path / "x.jpg"))


# -- known-photo store methods ------------------------------------------


async def test_save_list_delete_known_photo(hass, tmp_path):
    store = await _make_store(hass, tmp_path)
    fname = store.save_known_photo_sync("ben", _png_bytes())
    assert fname.endswith(".jpg")
    assert store.known_photos_map() == {"ben": [fname]}
    assert store.list_known_photos("ben") == [fname]

    assert store.delete_known_photo_sync("ben", fname) is True
    assert store.known_photos_map() == {}
    # deleting again is a no-op, not an error
    assert store.delete_known_photo_sync("ben", fname) is False


def test_visitor_dir_rejects_bad_id(hass, tmp_path):
    store = AlertStore(hass, str(tmp_path / "acc"), 7)
    for bad in ("../evil", "a/b", "Ben Draper"):
        with pytest.raises(HomeAssistantError):
            store._visitor_dir(bad)


def test_delete_known_photo_rejects_traversal(hass, tmp_path):
    store = AlertStore(hass, str(tmp_path / "acc"), 7)
    with pytest.raises(HomeAssistantError):
        store.delete_known_photo_sync("ben", "../../secrets.jpg")


# -- async_log path guards + prune --------------------------------------


async def test_async_log_writes_record(hass, tmp_path):
    store = await _make_store(hass, tmp_path)
    record = await store.async_log(_alert_data(store))
    assert record["camera"] == "side_gate"
    assert record["image"].endswith(".jpg")
    assert len(store.alerts()) == 1


async def test_async_log_rejects_outside_path(hass, tmp_path):
    store = await _make_store(hass, tmp_path)
    outside = str(tmp_path / "outside.jpg")
    with open(outside, "wb") as fh:
        fh.write(_png_bytes())
    data = _alert_data(store)
    data["image_path"] = outside  # not under base_dir, not allow-listed
    with pytest.raises(HomeAssistantError):
        await store.async_log(data)


async def test_async_prune_drops_old_records(hass, tmp_path):
    store = await _make_store(hass, tmp_path)
    await store.async_log(_alert_data(store))
    # age the record past retention
    store.records[0]["ts"] = time.time() - 8 * 86400
    await store.async_prune()
    assert store.records == []
