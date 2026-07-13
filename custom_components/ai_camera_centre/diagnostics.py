"""Diagnostics for AI Camera Centre.

Downloadable from the integration's ⋮ menu — handy to attach to a bug
report. No credentials are stored by this integration, so nothing needs
redacting.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, SUBENTRY_CAMERA, SUBENTRY_TARGET, VERSION


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data.get(DOMAIN, {})
    store = data.get("store")
    pipelines = data.get("pipelines", {})

    cameras = [
        {"subentry_id": sub.subentry_id, **dict(sub.data)}
        for sub in entry.subentries.values()
        if sub.subentry_type == SUBENTRY_CAMERA
    ]
    targets = [
        dict(sub.data)
        for sub in entry.subentries.values()
        if sub.subentry_type == SUBENTRY_TARGET
    ]

    return {
        "version": VERSION,
        "options": dict(entry.options),
        "camera_count": len(cameras),
        "cameras": cameras,
        "target_count": len(targets),
        "targets": targets,
        "runtime": {
            "pipeline_ids": list(pipelines),
            "paused": {cid: p.paused for cid, p in pipelines.items()},
            "stored_alert_count": len(store.records) if store else None,
            "retention_days": store.retention_days if store else None,
        },
    }
