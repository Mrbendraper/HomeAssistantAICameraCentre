"""Shared base for AI Camera Centre per-camera entities.

A mixin (rather than a common base class) so it composes cleanly with the
different Home Assistant entity bases (SensorEntity, ImageEntity, ...)
without multiple-inheritance ordering headaches.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_NEW_ALERT, VERSION

if TYPE_CHECKING:
    from . import AlertStore
    from .analyzer import CameraPipeline


class CameraEntityMixin:
    """Wires an entity to one camera's device, store and alert signal."""

    _attr_has_entity_name = True

    def _init_camera(self, pipeline: "CameraPipeline", key: str) -> None:
        self._pipeline = pipeline
        self._camera_id = pipeline.camera_id
        self._attr_unique_id = f"{self._camera_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._camera_id)},
            name=pipeline.label,
            manufacturer="AI Camera Centre",
            model="AI camera",
            sw_version=VERSION,
        )

    @property
    def _store(self) -> "AlertStore":
        return self.hass.data[DOMAIN]["store"]

    def _connect_alert_signal(self):
        """Return an unsubscribe callback for new-alert dispatches."""
        return async_dispatcher_connect(
            self.hass, SIGNAL_NEW_ALERT, self._handle_alert
        )

    @callback
    def _handle_alert(self, record: dict[str, Any]) -> None:
        if record.get("camera") == self._camera_id:
            self.async_write_ha_state()
