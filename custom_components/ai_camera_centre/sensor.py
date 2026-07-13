"""Sensor platform for AI Camera Centre.

Two sensors per configured camera, attached to that camera's device:
- Alerts (24h): count of alerts in the last 24 hours, with last-alert
  details as attributes.
- Last score: the suspicion score of the most recent alert.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_CAMERA_ID, DOMAIN, SUBENTRY_CAMERA
from .entity import CameraEntityMixin


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the per-camera sensors, one set per camera subentry."""
    pipelines = hass.data[DOMAIN]["pipelines"]
    for subentry_id, sub in entry.subentries.items():
        if sub.subentry_type != SUBENTRY_CAMERA:
            continue
        camera_id = sub.data.get(CONF_CAMERA_ID) or subentry_id
        pipeline = pipelines.get(camera_id)
        if pipeline is None:
            continue
        async_add_entities(
            [CameraAlerts24h(pipeline), CameraLastScore(pipeline)],
            config_subentry_id=subentry_id,
        )


class CameraAlerts24h(CameraEntityMixin, SensorEntity):
    """Count of alerts for one camera in the last 24 hours."""

    _attr_icon = "mdi:cctv"
    _attr_native_unit_of_measurement = "alerts"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, pipeline) -> None:
        self._init_camera(pipeline, "alerts_24h")
        # Preserve the pre-2.3 unique_id so history/statistics carry over.
        self._attr_unique_id = f"{DOMAIN}_{self._camera_id}_alerts_24h"
        self._attr_name = "Alerts (24h)"

    def _recent(self) -> list[dict[str, Any]]:
        cutoff = time.time() - 86400
        return [
            r
            for r in self._store.camera_alerts(self._camera_id)
            if float(r.get("ts", 0)) >= cutoff
        ]

    @property
    def native_value(self) -> int:
        return len(self._recent())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        recent = self._recent()
        if not recent:
            return {"last_alert": None}
        last = recent[0]
        return {
            "last_alert": datetime.fromtimestamp(
                float(last["ts"]), tz=timezone.utc
            ).isoformat(),
            "last_score": last.get("score"),
            "last_short": last.get("short"),
            "last_image": last.get("image"),
            "max_score_24h": max(int(r.get("score", 0)) for r in recent),
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._connect_alert_signal())
        # Refresh periodically so the rolling 24h window stays accurate.
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_refresh, timedelta(minutes=15)
            )
        )

    @callback
    def _async_refresh(self, _now) -> None:
        self.async_write_ha_state()


class CameraLastScore(CameraEntityMixin, SensorEntity):
    """Suspicion score of the most recent alert for one camera."""

    _attr_icon = "mdi:alert-decagram"
    _attr_native_unit_of_measurement = "/10"

    def __init__(self, pipeline) -> None:
        self._init_camera(pipeline, "last_score")
        self._attr_name = "Last score"

    @property
    def native_value(self) -> int | None:
        last = self._store.latest_for(self._camera_id)
        return int(last["score"]) if last else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        last = self._store.latest_for(self._camera_id)
        if not last:
            return {}
        return {
            "short": last.get("short"),
            "detail": last.get("detail"),
            "image": last.get("image"),
            "when": datetime.fromtimestamp(
                float(last["ts"]), tz=timezone.utc
            ).isoformat(),
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._connect_alert_signal())
