"""Binary sensor platform for AI Camera Centre.

One "recent alert" sensor per camera: on when that camera has logged an
alert within the last RECENT_ALERT_MINUTES minutes.
"""
from __future__ import annotations

import time
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_CAMERA_ID, DOMAIN, RECENT_ALERT_MINUTES, SUBENTRY_CAMERA
from .entity import CameraEntityMixin


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    pipelines = hass.data[DOMAIN]["pipelines"]
    for subentry_id, sub in entry.subentries.items():
        if sub.subentry_type != SUBENTRY_CAMERA:
            continue
        camera_id = sub.data.get(CONF_CAMERA_ID) or subentry_id
        pipeline = pipelines.get(camera_id)
        if pipeline is None:
            continue
        async_add_entities(
            [CameraRecentAlert(pipeline)], config_subentry_id=subentry_id
        )


class CameraRecentAlert(CameraEntityMixin, BinarySensorEntity):
    """On while the camera has a very recent alert."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, pipeline) -> None:
        self._init_camera(pipeline, "recent_alert")
        self._attr_name = "Recent alert"

    @property
    def is_on(self) -> bool:
        last = self._store.latest_for(self._camera_id)
        if not last:
            return False
        cutoff = time.time() - RECENT_ALERT_MINUTES * 60
        return float(last.get("ts", 0)) >= cutoff

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._connect_alert_signal())
        # A new alert flips it on; a timer is what flips it back off again.
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_refresh, timedelta(minutes=1)
            )
        )

    @callback
    def _async_refresh(self, _now) -> None:
        self.async_write_ha_state()
