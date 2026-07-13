"""Image platform for AI Camera Centre.

One image entity per camera showing that camera's most recent alert
snapshot, so it can be dropped straight onto a dashboard.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_CAMERA_ID, DOMAIN, SUBENTRY_CAMERA
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
            [LatestAlertImage(hass, pipeline)], config_subentry_id=subentry_id
        )


class LatestAlertImage(CameraEntityMixin, ImageEntity):
    """The most recent alert snapshot for one camera."""

    _attr_content_type = "image/jpeg"

    def __init__(self, hass: HomeAssistant, pipeline) -> None:
        ImageEntity.__init__(self, hass)
        self._init_camera(pipeline, "latest_alert")
        self._attr_name = "Latest alert"
        last = pipeline.store.latest_for(pipeline.camera_id)
        if last:
            self._attr_image_last_updated = dt_util.utc_from_timestamp(
                float(last["ts"])
            )

    @staticmethod
    def _read(path: str) -> bytes:
        with open(path, "rb") as fh:
            return fh.read()

    async def async_image(self) -> bytes | None:
        record = self._store.latest_for(self._camera_id)
        if not record:
            return None
        path = self._store.image_path_for(record)
        if not path:
            return None
        try:
            return await self.hass.async_add_executor_job(self._read, path)
        except OSError:
            return None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._connect_alert_signal())

    @callback
    def _handle_alert(self, record: dict[str, Any]) -> None:
        if record.get("camera") != self._camera_id:
            return
        # Bump the timestamp so the frontend refetches the new image.
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()
