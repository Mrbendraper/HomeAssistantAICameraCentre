"""Config flow for Alert History."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS, DOMAIN

RETENTION_SCHEMA = vol.All(vol.Coerce(int), vol.Range(min=1, max=90))


class AlertHistoryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(
                title="Alert History",
                data={},
                options={
                    CONF_RETENTION_DAYS: user_input[CONF_RETENTION_DAYS],
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_RETENTION_DAYS, default=DEFAULT_RETENTION_DAYS
                    ): RETENTION_SCHEMA,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AlertHistoryOptionsFlow()


class AlertHistoryOptionsFlow(OptionsFlow):
    """Allow changing retention after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_RETENTION_DAYS,
                        default=self.config_entry.options.get(
                            CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS
                        ),
                    ): RETENTION_SCHEMA,
                }
            ),
        )
