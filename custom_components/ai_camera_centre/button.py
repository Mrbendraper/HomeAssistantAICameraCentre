"""Button platform for AI Camera Centre.

One button per camera to run an analysis on demand from its device page
(equivalent to calling ai_camera_centre.analyze for that camera).
"""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
            [AnalyzeButton(pipeline)], config_subentry_id=subentry_id
        )


class AnalyzeButton(CameraEntityMixin, ButtonEntity):
    """Trigger an on-demand analysis for one camera."""

    _attr_icon = "mdi:camera-iris"

    def __init__(self, pipeline) -> None:
        self._init_camera(pipeline, "analyze_now")
        self._attr_name = "Analyze now"

    async def async_press(self) -> None:
        await self._pipeline.async_analyze(force=True)
