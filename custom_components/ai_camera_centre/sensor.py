"""Sensor platform for AI Camera Centre.

One sensor per camera: alert count in the last 24 hours, with details of
the most recent alert as attributes. Sensors are created dynamically as
new cameras log their first alert.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, SIGNAL_NEW_ALERT


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for cameras present in the log; add new ones on the fly."""
    store = hass.data[DOMAIN]["store"]
    known: set[str] = set()

    def _make(camera_id: str, label: str) -> "CameraAlertsSensor":
        known.add(camera_id)
        return CameraAlertsSensor(store, camera_id, label)

    entities = [_make(cid, label) for cid, label in store.cameras().items()]
    if entities:
        async_add_entities(entities)

    @callback
    def _on_new_alert(record: dict[str, Any]) -> None:
        if record["camera"] not in known:
            async_add_entities(
                [
                    _make(
                        record["camera"],
                        record.get("camera_label") or record["camera"],
                    )
                ]
            )

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEW_ALERT, _on_new_alert)
    )


class CameraAlertsSensor(SensorEntity):
    """Alerts in the last 24h for one camera."""

    _attr_should_poll = False
    _attr_icon = "mdi:cctv"
    _attr_native_unit_of_measurement = "alerts"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, store, camera_id: str, label: str) -> None:
        self._store = store
        self._camera_id = camera_id
        self._attr_unique_id = f"{DOMAIN}_{camera_id}_alerts_24h"
        self._attr_name = f"{label} Alerts (24h)"

    def _recent(self) -> list[dict[str, Any]]:
        cutoff = time.time() - 86400
        return [
            r
            for r in self._store.alerts()  # newest first
            if r["camera"] == self._camera_id and float(r.get("ts", 0)) >= cutoff
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
        @callback
        def _on_new_alert(record: dict[str, Any]) -> None:
            if record["camera"] == self._camera_id:
                self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_NEW_ALERT, _on_new_alert)
        )
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_refresh, timedelta(minutes=15)
            )
        )

    async def _async_refresh(self, _now) -> None:
        self.async_write_ha_state()
