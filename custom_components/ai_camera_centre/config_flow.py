"""Config flow for AI Camera Centre.

Initial setup collects the global settings. After that the integration
page offers native "Add camera" and "Add alert target" buttons (config
subentries), and the Configure button opens the global settings — no YAML
required and no nested options menu.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
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
    CONF_CAMERA_ENTITY,
    CONF_CAMERA_ID,
    CONF_CAMERA_NAME,
    CONF_COOLDOWN_SECONDS,
    CONF_DASHBOARD_PATH,
    CONF_LOG_WINDOW_END,
    CONF_LOG_WINDOW_START,
    CONF_MIN_LOG_SCORE,
    CONF_MOTION_ENTITIES,
    CONF_REPEAT_CONTEXT_MINUTES,
    CONF_RETENTION_DAYS,
    CONF_SCENE_CONTEXT,
    CONF_SNAPSHOT_COUNT,
    CONF_SNAPSHOT_INTERVAL_MS,
    CONF_TARGET_CAMERAS,
    CONF_TARGET_CONDITION,
    CONF_TARGET_MIN_SCORE,
    CONF_TARGET_NAME,
    CONF_TARGET_SERVICE,
    CONF_VISITOR_DESCRIPTION,
    CONF_VISITOR_NAME,
    DEFAULT_ALARMO_TRIGGER_SCORE,
    DEFAULT_COOLDOWN_SECONDS,
    DEFAULT_DASHBOARD_PATH,
    DEFAULT_MIN_LOG_SCORE,
    DEFAULT_REPEAT_CONTEXT_MINUTES,
    DEFAULT_RETENTION_DAYS,
    DEFAULT_SNAPSHOT_COUNT,
    DEFAULT_SNAPSHOT_INTERVAL_MS,
    DEFAULT_TARGET_CONDITION,
    DOMAIN,
    NOTIFY_ALWAYS,
    NOTIFY_ARMED,
    NOTIFY_AWAY,
    NOTIFY_AWAY_OR_ARMED,
    SUBENTRY_CAMERA,
    SUBENTRY_KNOWN_VISITOR,
    SUBENTRY_TARGET,
)

MOTION_DOMAINS = ["binary_sensor", "input_boolean", "switch"]

INT_SETTINGS = (
    CONF_RETENTION_DAYS,
    CONF_SNAPSHOT_COUNT,
    CONF_SNAPSHOT_INTERVAL_MS,
    CONF_COOLDOWN_SECONDS,
    CONF_ALARMO_TRIGGER_SCORE,
    CONF_MIN_LOG_SCORE,
    CONF_REPEAT_CONTEXT_MINUTES,
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


# -- schema builders -----------------------------------------------------


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
                description={"suggested_value": _get(CONF_AI_TASK_ENTITY, None)},
            ): EntitySelector(EntitySelectorConfig(domain="ai_task")),
            vol.Optional(
                CONF_ALARM_PANEL_ENTITY,
                description={"suggested_value": _get(CONF_ALARM_PANEL_ENTITY, None)},
            ): EntitySelector(EntitySelectorConfig(domain="alarm_control_panel")),
            vol.Required(
                CONF_MIN_LOG_SCORE,
                default=_get(CONF_MIN_LOG_SCORE, DEFAULT_MIN_LOG_SCORE),
            ): NumberSelector(
                NumberSelectorConfig(min=1, max=10, mode=NumberSelectorMode.SLIDER)
            ),
            vol.Required(
                CONF_REPEAT_CONTEXT_MINUTES,
                default=_get(
                    CONF_REPEAT_CONTEXT_MINUTES, DEFAULT_REPEAT_CONTEXT_MINUTES
                ),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=120, mode=NumberSelectorMode.BOX)
            ),
            vol.Optional(
                CONF_LOG_WINDOW_START,
                description={"suggested_value": _get(CONF_LOG_WINDOW_START, None)},
            ): TimeSelector(),
            vol.Optional(
                CONF_LOG_WINDOW_END,
                description={"suggested_value": _get(CONF_LOG_WINDOW_END, None)},
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
    return vol.Schema(
        {
            vol.Required(
                CONF_CAMERA_NAME,
                default=camera.get(CONF_CAMERA_NAME, ""),
            ): TextSelector(),
            vol.Required(
                CONF_CAMERA_ENTITY,
                description={"suggested_value": camera.get(CONF_CAMERA_ENTITY)},
            ): EntitySelector(EntitySelectorConfig(domain="camera")),
            vol.Optional(
                CONF_MOTION_ENTITIES,
                description={"suggested_value": motion_entities},
            ): EntitySelector(
                EntitySelectorConfig(domain=MOTION_DOMAINS, multiple=True)
            ),
            vol.Optional(
                CONF_SCENE_CONTEXT,
                description={"suggested_value": camera.get(CONF_SCENE_CONTEXT, "")},
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


def _friendly_service_name(service: str) -> str:
    """Turn notify.mobile_app_ben_s_note15_pro into 'Ben S Note15 Pro'."""
    name = service.removeprefix("notify.").removeprefix("mobile_app_")
    return name.replace("_", " ").strip().title() or service


def _target_title(target: dict[str, Any]) -> str:
    return target.get(CONF_TARGET_NAME) or _friendly_service_name(
        target.get(CONF_TARGET_SERVICE, "")
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
            vol.Optional(
                CONF_TARGET_NAME,
                description={"suggested_value": target.get(CONF_TARGET_NAME)},
            ): TextSelector(),
            vol.Required(
                CONF_TARGET_SERVICE,
                description={"suggested_value": target.get(CONF_TARGET_SERVICE)},
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
                description={"suggested_value": target.get(CONF_TARGET_CAMERAS, [])},
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


# -- cleaners ------------------------------------------------------------


def _clean_settings(user_input: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(user_input)
    for key in INT_SETTINGS:
        if key in cleaned:
            cleaned[key] = int(cleaned[key])
    return cleaned


def _clean_camera(user_input: dict[str, Any], camera_id: str) -> dict[str, Any]:
    data: dict[str, Any] = {
        CONF_CAMERA_ID: camera_id,
        CONF_CAMERA_NAME: user_input[CONF_CAMERA_NAME],
        CONF_CAMERA_ENTITY: user_input[CONF_CAMERA_ENTITY],
        CONF_MOTION_ENTITIES: user_input.get(CONF_MOTION_ENTITIES, []),
    }
    if scene := user_input.get(CONF_SCENE_CONTEXT):
        data[CONF_SCENE_CONTEXT] = scene
    return data


def _clean_target(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_TARGET_NAME: (user_input.get(CONF_TARGET_NAME) or "").strip(),
        CONF_TARGET_SERVICE: str(user_input[CONF_TARGET_SERVICE]).strip(),
        CONF_TARGET_MIN_SCORE: int(user_input[CONF_TARGET_MIN_SCORE]),
        CONF_TARGET_CONDITION: user_input.get(
            CONF_TARGET_CONDITION, DEFAULT_TARGET_CONDITION
        ),
        CONF_TARGET_CAMERAS: user_input.get(CONF_TARGET_CAMERAS, []),
    }


def _visitor_schema(visitor: dict[str, Any] | None = None) -> vol.Schema:
    """Add/edit known-visitor form, prefilled when editing."""
    visitor = visitor or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_VISITOR_NAME,
                default=visitor.get(CONF_VISITOR_NAME, ""),
            ): TextSelector(),
            vol.Required(
                CONF_VISITOR_DESCRIPTION,
                description={
                    "suggested_value": visitor.get(CONF_VISITOR_DESCRIPTION, "")
                },
            ): TextSelector(TextSelectorConfig(multiline=True)),
        }
    )


def _clean_visitor(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_VISITOR_NAME: user_input[CONF_VISITOR_NAME].strip(),
        CONF_VISITOR_DESCRIPTION: user_input[CONF_VISITOR_DESCRIPTION].strip(),
    }


# -- flows ---------------------------------------------------------------


class AICameraCentreConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup and expose the camera/target subentries."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(
                title="AI Camera Centre",
                data={},
                options=_clean_settings(user_input),
            )
        return self.async_show_form(
            step_id="user", data_schema=_settings_schema({})
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AICameraCentreOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {
            SUBENTRY_CAMERA: CameraSubentryFlow,
            SUBENTRY_TARGET: AlertTargetSubentryFlow,
            SUBENTRY_KNOWN_VISITOR: KnownVisitorSubentryFlow,
        }


class AICameraCentreOptionsFlow(OptionsFlow):
    """Global settings only — cameras and targets are subentries now."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            options = dict(self.config_entry.options)
            options.update(_clean_settings(user_input))
            for key in OPTIONAL_SETTINGS:
                if key not in user_input:
                    options.pop(key, None)
            return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="init",
            data_schema=_settings_schema(dict(self.config_entry.options)),
        )


class CameraSubentryFlow(ConfigSubentryFlow):
    """Add or edit a camera."""

    def _camera_ids(self) -> set[str]:
        return {
            sub.data.get(CONF_CAMERA_ID)
            for sub in self._get_entry().subentries.values()
            if sub.subentry_type == SUBENTRY_CAMERA
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            camera_id = slugify(user_input[CONF_CAMERA_NAME])
            if not camera_id:
                errors[CONF_CAMERA_NAME] = "invalid_name"
            elif camera_id in self._camera_ids():
                errors[CONF_CAMERA_NAME] = "duplicate_camera"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_CAMERA_NAME],
                    data=_clean_camera(user_input, camera_id),
                    unique_id=camera_id,
                )
        return self.async_show_form(
            step_id="user", data_schema=_camera_schema(), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            # Keep the original camera_id (and its alert history) on rename.
            camera_id = subentry.data.get(CONF_CAMERA_ID) or subentry.subentry_id
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=user_input[CONF_CAMERA_NAME],
                data=_clean_camera(user_input, camera_id),
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_camera_schema(dict(subentry.data)),
        )


class AlertTargetSubentryFlow(ConfigSubentryFlow):
    """Add or edit an alert target."""

    def _cameras(self) -> dict[str, Any]:
        return {
            sub.data.get(CONF_CAMERA_ID): sub.data
            for sub in self._get_entry().subentries.values()
            if sub.subentry_type == SUBENTRY_CAMERA
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            target = _clean_target(user_input)
            if not target[CONF_TARGET_SERVICE]:
                errors[CONF_TARGET_SERVICE] = "invalid_service"
            else:
                return self.async_create_entry(
                    title=_target_title(target), data=target
                )
        return self.async_show_form(
            step_id="user",
            data_schema=_target_schema(self.hass, self._cameras()),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            target = _clean_target(user_input)
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=_target_title(target),
                data=target,
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_target_schema(
                self.hass, self._cameras(), dict(subentry.data)
            ),
        )


class KnownVisitorSubentryFlow(ConfigSubentryFlow):
    """Add or edit a known visitor (household member / regular)."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            visitor = _clean_visitor(user_input)
            if not visitor[CONF_VISITOR_NAME]:
                errors[CONF_VISITOR_NAME] = "invalid_name"
            else:
                return self.async_create_entry(
                    title=visitor[CONF_VISITOR_NAME], data=visitor
                )
        return self.async_show_form(
            step_id="user", data_schema=_visitor_schema(), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            visitor = _clean_visitor(user_input)
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=visitor[CONF_VISITOR_NAME],
                data=visitor,
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_visitor_schema(dict(subentry.data)),
        )
