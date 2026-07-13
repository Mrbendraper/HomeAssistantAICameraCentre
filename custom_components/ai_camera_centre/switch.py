"""Switch platform for AI Camera Centre.

One switch per camera to pause/resume its AI analysis (e.g. while the
gardener is round, or on holiday). Off = motion triggers are ignored;
the analyze button and service still work with force.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

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
            [AnalysisSwitch(pipeline)], config_subentry_id=subentry_id
        )


class AnalysisSwitch(CameraEntityMixin, SwitchEntity, RestoreEntity):
    """Enable/disable automatic analysis for one camera."""

    _attr_icon = "mdi:motion-sensor"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, pipeline) -> None:
        self._init_camera(pipeline, "analysis_enabled")
        self._attr_name = "Analysis"
        self._attr_is_on = True

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        if last is not None:
            self._attr_is_on = last.state == "on"
        # Apply the restored state to the (freshly built) pipeline.
        self._pipeline.paused = not self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        self._pipeline.paused = False
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        self._pipeline.paused = True
        self.async_write_ha_state()
