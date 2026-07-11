"""Config flow for AI Camera Centre.

Initial setup collects the global settings; the options flow then
manages the camera list (add / edit / remove) and settings from the
integration's Configure button — no YAML required.
"""
from __future__ import annotations

import copy
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)
from homeassistant.util import slugify

from .const import (
    CONF_AI_TASK_ENTITY,
    CONF_CAMERA_ENTITY,
    CONF_CAMERA_NAME,
    CONF_CAMERAS,
    CONF_COOLDOWN_SECONDS,
    CONF_DASHBOARD_PATH,
    CONF_MIN_NOTIFY_SCORE,
    CONF_MOTION_ENTITY,
    CONF_NOTIFY_SERVICES,
    CONF_RETENTION_DAYS,
    CONF_SCENE_CONTEXT,
    CONF_SNAPSHOT_COUNT,
    CONF_SNAPSHOT_INTERVAL_MS,
    DEFAULT_COOLDOWN_SECONDS,
    DEFAULT_DASHBOARD_PATH,
    DEFAULT_MIN_NOTIFY_SCORE,
    DEFAULT_RETENTION_DAYS,
    DEFAULT_SNAPSHOT_COUNT,
    DEFAULT_SNAPSHOT_INTERVAL_MS,
    DOMAIN,
)


def _settings_schema(options: dict[str, Any]) -> vol.Schema:
    """Global settings form, prefilled from current options."""

    def _get(key: str, default: Any) -> Any:
        return options.get(key, default)

    return vol.Schema(
        {
            vol.Required(
                CONF_RETENTION_DAYS,
                default=_get(CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS),
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=90, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_SNAPSHOT_COUNT,
                default=_get(CONF_SNAPSHOT_COUNT, DEFAULT_SNAPSHOT_COUNT),
            ): NumberSelector(
                NumberSelectorConfig(min=2, max=10, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_SNAPSHOT_INTERVAL_MS,
                default=_get(CONF_SNAPSHOT_INTERVAL_MS, DEFAULT_SNAPSHOT_INTERVAL_MS),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=100, max=5000, step=100, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_COOLDOWN_SECONDS,
                default=_get(CONF_COOLDOWN_SECONDS, DEFAULT_COOLDOWN_SECONDS),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=3600, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_MIN_NOTIFY_SCORE,
                default=_get(CONF_MIN_NOTIFY_SCORE, DEFAULT_MIN_NOTIFY_SCORE),
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=10, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_NOTIFY_SERVICES,
                description={
                    "suggested_value": _get(CONF_NOTIFY_SERVICES, "")
                },
            ): TextSelector(),
            vol.Required(
                CONF_DASHBOARD_PATH,
                default=_get(CONF_DASHBOARD_PATH, DEFAULT_DASHBOARD_PATH),
            ): TextSelector(),
            vol.Optional(
                CONF_AI_TASK_ENTITY,
                description={
                    "suggested_value": _get(CONF_AI_TASK_ENTITY, None)
                },
            ): EntitySelector(EntitySelectorConfig(domain="ai_task")),
        }
    )


def _camera_schema(camera: dict[str, Any] | None = None) -> vol.Schema:
    """Add/edit camera form, prefilled when editing."""
    camera = camera or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_CAMERA_NAME,
                default=camera.get(CONF_CAMERA_NAME, ""),
            ): TextSelector(),
            vol.Required(
                CONF_CAMERA_ENTITY,
                description={
                    "suggested_value": camera.get(CONF_CAMERA_ENTITY)
                },
            ): EntitySelector(EntitySelectorConfig(domain="camera")),
            vol.Optional(
                CONF_MOTION_ENTITY,
                description={
                    "suggested_value": camera.get(CONF_MOTION_ENTITY)
                },
            ): EntitySelector(EntitySelectorConfig(domain="binary_sensor")),
            vol.Optional(
                CONF_SCENE_CONTEXT,
                description={
                    "suggested_value": camera.get(CONF_SCENE_CONTEXT, "")
                },
            ): TextSelector(TextSelectorConfig(multiline=True)),
        }
    )


def _clean_settings(user_input: dict[str, Any]) -> dict[str, Any]:
    """Coerce number selector floats to ints."""
    cleaned = dict(user_input)
    for key in (
        CONF_RETENTION_DAYS,
        CONF_SNAPSHOT_COUNT,
        CONF_SNAPSHOT_INTERVAL_MS,
        CONF_COOLDOWN_SECONDS,
        CONF_MIN_NOTIFY_SCORE,
    ):
        if key in cleaned:
            cleaned[key] = int(cleaned[key])
    return cleaned


class AICameraCentreConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            options = _clean_settings(user_input)
            options[CONF_CAMERAS] = {}
            return self.async_create_entry(
                title="AI Camera Centre", data={}, options=options
            )
        return self.async_show_form(
            step_id="user", data_schema=_settings_schema({})
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AICameraCentreOptionsFlow()


class AICameraCentreOptionsFlow(OptionsFlow):
    """Manage cameras and settings after setup."""

    def __init__(self) -> None:
        self._edit_id: str | None = None

    @property
    def _options(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self.config_entry.options))

    @property
    def _cameras(self) -> dict[str, Any]:
        return dict(self.config_entry.options.get(CONF_CAMERAS, {}))

    def _camera_choices(self) -> SelectSelector:
        return SelectSelector(
            SelectSelectorConfig(
                options=[
                    {
                        "value": camera_id,
                        "label": conf.get(CONF_CAMERA_NAME) or camera_id,
                    }
                    for camera_id, conf in self._cameras.items()
                ],
                mode=SelectSelectorMode.LIST,
            )
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        menu = ["add_camera"]
        if self._cameras:
            menu += ["edit_camera", "remove_camera"]
        menu.append("settings")
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_add_camera(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            camera_id = slugify(user_input[CONF_CAMERA_NAME])
            if not camera_id:
                errors[CONF_CAMERA_NAME] = "invalid_name"
            elif camera_id in self._cameras:
                errors[CONF_CAMERA_NAME] = "duplicate_camera"
            else:
                options = self._options
                options.setdefault(CONF_CAMERAS, {})[camera_id] = dict(user_input)
                return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="add_camera", data_schema=_camera_schema(), errors=errors
        )

    async def async_step_edit_camera(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._edit_id = user_input["camera"]
            return await self.async_step_edit_camera_details()
        return self.async_show_form(
            step_id="edit_camera",
            data_schema=vol.Schema(
                {vol.Required("camera"): self._camera_choices()}
            ),
        )

    async def async_step_edit_camera_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._edit_id is not None
        if user_input is not None:
            options = self._options
            # Keep the original id (and its alert history) even if renamed.
            options[CONF_CAMERAS][self._edit_id] = dict(user_input)
            return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="edit_camera_details",
            data_schema=_camera_schema(self._cameras.get(self._edit_id)),
        )

    async def async_step_remove_camera(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            options = self._options
            options.get(CONF_CAMERAS, {}).pop(user_input["camera"], None)
            return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="remove_camera",
            data_schema=vol.Schema(
                {vol.Required("camera"): self._camera_choices()}
            ),
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            options = self._options
            cleaned = _clean_settings(user_input)
            # Optional fields left empty must clear the stored value.
            cleaned.setdefault(CONF_NOTIFY_SERVICES, "")
            options.update(cleaned)
            if CONF_AI_TASK_ENTITY not in user_input:
                options.pop(CONF_AI_TASK_ENTITY, None)
            return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="settings",
            data_schema=_settings_schema(dict(self.config_entry.options)),
        )
