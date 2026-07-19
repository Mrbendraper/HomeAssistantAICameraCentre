"""Tests for the config and options flows."""
from __future__ import annotations

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ai_camera_centre.const import (
    CONF_PROCESS_PRESENCE,
    CONF_RESPONSE_STYLE,
    CONF_RETENTION_DAYS,
    DEFAULT_PROCESS_PRESENCE,
    DOMAIN,
)

MINIMAL_SETTINGS = {
    "retention_days": 7,
    "snapshot_count": 5,
    "snapshot_interval_ms": 500,
    "cooldown_seconds": 30,
    "dashboard_path": "/lovelace/alerts",
    "min_log_score": 1,
    "repeat_context_minutes": 15,
    "alarmo_enabled": False,
    "alarmo_trigger_score": 9,
    # gate selects carry their own defaults via the schema, but supply them
    # explicitly here since we bypass the form rendering:
    "process_presence": DEFAULT_PROCESS_PRESENCE,
    "process_armed": "always",
    "process_time_mode": "always",
}


async def test_user_flow_creates_entry(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**MINIMAL_SETTINGS, CONF_RESPONSE_STYLE: "like a noir detective"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    opts = result["options"]
    assert opts[CONF_RETENTION_DAYS] == 7
    assert opts[CONF_PROCESS_PRESENCE] == DEFAULT_PROCESS_PRESENCE
    assert opts[CONF_RESPONSE_STYLE] == "like a noir detective"


async def test_single_instance_only(hass: HomeAssistant):
    MockConfigEntry(domain=DOMAIN, data={}, options=MINIMAL_SETTINGS).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_clears_blanked_style(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={**MINIMAL_SETTINGS, CONF_RESPONSE_STYLE: "old style"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    # resubmit without a style -> it should be cleared from options
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], MINIMAL_SETTINGS
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert CONF_RESPONSE_STYLE not in result["data"]
