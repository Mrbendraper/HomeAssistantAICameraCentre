"""Config flow for AI Camera Centre.

Initial setup collects the global settings; the options flow then
manages cameras (add / edit / remove), alert targets (who gets notified,
at what score, for which cameras) and settings from the integration's
Configure button — no YAML required.
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
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
    TimeSelector,
)
from homeassistant.util import slugify

from .const import (
    CONF_AI_TASK_ENTITY,
    CONF_ALARM_PANEL_ENTITY,
    CONF_ALARMO_ENABLED,
    CONF_ALARMO_TRIGGER_SCORE,
    CONF_ALERT_TARGETS,
    CONF_CAMERA_ENTITY,
    CONF_CAMERA_NAME,
    CONF_CAMERAS,
    CONF_COOLDOWN_SECONDS,
    CONF_DASHBOARD_PATH,
    CONF_LOG_WINDOW_END,
    CONF_LOG_WINDOW_START,
    CONF_MIN_LOG_SCORE,
    CONF_MOTION_ENTITIES,
    CONF_MOTION_ENTITY,
    CONF_RETENTION_DAYS,
    CONF_SCENE_CONTEXT,
    CONF_SNAPSHOT_COUNT,
    CONF_SNAPSHOT_INTERVAL_MS,
    CONF_TARGET_CAMERAS,
    CONF_TARGET_CONDITION,
    CONF_TARGET_MIN_SCORE,
    CONF_TARGET_SERVICE,
    DEFAULT_ALARMO_TRIGGER_SCORE,
    DEFAULT_COOLDOWN_SECONDS,
    DEFAULT_DASHBOARD_PATH,
    DEFAULT_MIN_LOG_SCORE,
    DEFAULT_RETENTION_DAYS,
    DEFAULT_SNAPSHOT_COUNT,
    DEFAULT_SNAPSHOT_INTERVAL_MS,
    DEFAULT_TARGET_CONDITION,
    DOMAIN,
    NOTIFY_ALWAYS,
    NOTIFY_ARMED,
    NOTIFY_AWAY,
    NOTIFY_AWAY_OR_ARMED,
)

MOTION_DOMAINS = ["binary_sensor", "input_boolean", "switch"]

INT_SETTINGS = (
    CONF_RETENTION_DAYS,
    CONF_SNAPSHOT_COUNT,
    CONF_SNAPSHOT_INTERVAL_MS,
    CONF_COOLDOWN_SECONDS,
    CONF_ALARMO_TRIGGER_SCORE,
    CONF_MIN_LOG_SCORE,
)

# Optional settings that must be cleared when the user empties them.
OPTIONAL_SETTINGS = (
    CONF_AI_TASK_ENTITY,
    CONF_ALARM_PANEL_ENTITY,
    CONF_LOG_WINDOW_START,
    CONF_LOG_WINDOW_END,
)

NOTIFY_CONDITIONS = [
    {"value": NOTIFY_ALWAYS, "label": "Always"},
    {"value": NOTIFY_AWAY, "label": "Only when nobody is home"},
    {"value": NOTIFY_ARMED, "label": "Only when the alarm is armed"},
    {"value": NOTIFY_AWAY_OR_ARMED, "label": "When away or armed"},
]


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
                CONF_DASHBOARD_PATH,
                default=_get(CONF_DASHBOARD_PATH, DEFAULT_DASHBOARD_PATH),
            ): TextSelector(),
            vol.Optional(
                CONF_AI_TASK_ENTITY,
                description={
                    "suggested_value": _get(CONF_AI_TASK_ENTITY, None)
                },
            ): EntitySelector(EntitySelectorConfig(domain="ai_task")),
            vol.Optional(
                CONF_ALARM_PANEL_ENTITY,
                description={
                    "suggested_value": _get(CONF_ALARM_PANEL_ENTITY, None)
                },
            ): EntitySelector(
                EntitySelectorConfig(domain="alarm_control_panel")
            ),
            vol.Required(
                CONF_MIN_LOG_SCORE,
                default=_get(CONF_MIN_LOG_SCORE, DEFAULT_MIN_LOG_SCORE),
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=10, mode=NumberSelectorMode.SLIDER)
            ),
            vol.Optional(
                CONF_LOG_WINDOW_START,
                description={
                    "suggested_value": _get(CONF_LOG_WINDOW_START, None)
                },
            ): TimeSelector(),
            vol.Optional(
                CONF_LOG_WINDOW_END,
                description={
                    "suggested_value": _get(CONF_LOG_WINDOW_END, None)
                },
            ): TimeSelector(),
            vol.Required(
                CONF_ALARMO_ENABLED,
                default=_get(CONF_ALARMO_ENABLED, False),
            ): BooleanSelector(),
            vol.Required(
                CONF_ALARMO_TRIGGER_SCORE,
                default=_get(CONF_ALARMO_TRIGGER_SCORE, DEFAULT_ALARMO_TRIGGER_SCORE),
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=10, mode=NumberSelectorMode.SLIDER)
            ),
        }
    )


def _camera_schema(camera: dict[str, Any] | None = None) -> vol.Schema:
    """Add/edit camera form, prefilled when editing."""
    camera = camera or {}
    motion_entities = camera.get(CONF_MOTION_ENTITIES) or []
    if legacy_motion := camera.get(CONF_MOTION_ENTITY):
        if legacy_motion not in motion_entities:
            motion_entities = [*motion_entities, legacy_motion]
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
                CONF_MOTION_ENTITIES,
                description={"suggested_value": motion_entities},
            ): EntitySelector(
                EntitySelectorConfig(domain=MOTION_DOMAINS, multiple=True)
            ),
            vol.Optional(
                CONF_SCENE_CONTEXT,
                description={
                    "suggested_value": camera.get(CONF_SCENE_CONTEXT, "")
                },
            ): TextSelector(TextSelectorConfig(multiline=True)),
        }
    )


def _notify_service_selector(hass: HomeAssistant) -> SelectSelector:
    """Dropdown of the notify services registered right now."""
    services = sorted(
        f"notify.{name}" for name in hass.services.async_services().get("notify", {})
    )
    return SelectSelector(
        SelectSelectorConfig(
            options=services,
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _target_schema(
    hass: HomeAssistant,
    cameras: dict[str, Any],
    target: dict[str, Any] | None = None,
) -> vol.Schema:
    """Add/edit alert target form, prefilled when editing."""
    target = target or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_TARGET_SERVICE,
                description={
                    "suggested_value": target.get(CONF_TARGET_SERVICE)
                },
            ): _notify_service_selector(hass),
            vol.Required(
                CONF_TARGET_MIN_SCORE,
                default=target.get(CONF_TARGET_MIN_SCORE, 1),
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=10, mode=NumberSelectorMode.SLIDER)
            ),
            vol.Required(
                CONF_TARGET_CONDITION,
                default=target.get(CONF_TARGET_CONDITION, DEFAULT_TARGET_CONDITION),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=NOTIFY_CONDITIONS,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_TARGET_CAMERAS,
                description={
                    "suggested_value": target.get(CONF_TARGET_CAMERAS, [])
                },
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {
                            "value": camera_id,
                            "label": conf.get(CONF_CAMERA_NAME) or camera_id,
                        }
                        for camera_id, conf in cameras.items()
                    ],
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            ),
        }
    )


def _clean_settings(user_input: dict[str, Any]) -> dict[str, Any]:
    """Coerce number selector floats to ints."""
    cleaned = dict(user_input)
    for key in INT_SETTINGS:
        if key in cleaned:
            cleaned[key] = int(cleaned[key])
    return cleaned


def _clean_target(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_TARGET_SERVICE: str(user_input[CONF_TARGET_SERVICE]).strip(),
        CONF_TARGET_MIN_SCORE: int(user_input[CONF_TARGET_MIN_SCORE]),
        CONF_TARGET_CONDITION: user_input.get(
            CONF_TARGET_CONDITION, DEFAULT_TARGET_CONDITION
        ),
        CONF_TARGET_CAMERAS: user_input.get(CONF_TARGET_CAMERAS, []),
    }


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
            options[CONF_ALERT_TARGETS] = {}
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
    """Manage cameras, alert targets and settings after setup."""

    def __init__(self) -> None:
        self._edit_id: str | None = None

    @property
    def _options(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self.config_entry.options))

    @property
    def _cameras(self) -> dict[str, Any]:
        return dict(self.config_entry.options.get(CONF_CAMERAS, {}))

    @property
    def _targets(self) -> dict[str, Any]:
        return dict(self.config_entry.options.get(CONF_ALERT_TARGETS, {}))

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

    def _target_choices(self) -> SelectSelector:
        return SelectSelector(
            SelectSelectorConfig(
                options=[
                    {
                        "value": target_id,
                        "label": conf.get(CONF_TARGET_SERVICE) or target_id,
                    }
                    for target_id, conf in self._targets.items()
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
        menu.append("add_target")
        if self._targets:
            menu += ["edit_target", "remove_target"]
        menu.append("settings")
        return self.async_show_menu(step_id="init", menu_options=menu)

    # -- cameras ---------------------------------------------------------

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
            # Keep the original id (and its alert history) even if renamed;
            # dict(user_input) drops the legacy motion_entity key on save.
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

    # -- alert targets -----------------------------------------------------

    async def async_step_add_target(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            target = _clean_target(user_input)
            target_id = slugify(target[CONF_TARGET_SERVICE])
            if not target_id:
                errors[CONF_TARGET_SERVICE] = "invalid_service"
            elif target_id in self._targets:
                errors[CONF_TARGET_SERVICE] = "duplicate_target"
            else:
                options = self._options
                options.setdefault(CONF_ALERT_TARGETS, {})[target_id] = target
                return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="add_target",
            data_schema=_target_schema(self.hass, self._cameras),
            errors=errors,
        )

    async def async_step_edit_target(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._edit_id = user_input["target"]
            return await self.async_step_edit_target_details()
        return self.async_show_form(
            step_id="edit_target",
            data_schema=vol.Schema(
                {vol.Required("target"): self._target_choices()}
            ),
        )

    async def async_step_edit_target_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._edit_id is not None
        if user_input is not None:
            options = self._options
            options[CONF_ALERT_TARGETS][self._edit_id] = _clean_target(user_input)
            return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="edit_target_details",
            data_schema=_target_schema(
                self.hass, self._cameras, self._targets.get(self._edit_id)
            ),
        )

    async def async_step_remove_target(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            options = self._options
            options.get(CONF_ALERT_TARGETS, {}).pop(user_input["target"], None)
            return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="remove_target",
            data_schema=vol.Schema(
                {vol.Required("target"): self._target_choices()}
            ),
        )

    # -- settings ----------------------------------------------------------

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            options = self._options
            options.update(_clean_settings(user_input))
            for key in OPTIONAL_SETTINGS:
                if key not in user_input:
                    options.pop(key, None)
            return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="settings",
            data_schema=_settings_schema(dict(self.config_entry.options)),
        )
