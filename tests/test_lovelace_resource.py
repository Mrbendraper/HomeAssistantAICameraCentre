"""Tests for auto-registration of the bundled Lovelace card resource.

The resource URL carries a ?v=<version> cache-buster and the card is served
with long-lived cache headers, so a stale version pins browsers to the JS
from whichever release first registered it — cards added later never appear.
"""
from __future__ import annotations

from types import SimpleNamespace

from homeassistant.core import HomeAssistant

from custom_components.ai_camera_centre import _async_register_lovelace_resource
from custom_components.ai_camera_centre.const import CARD_URL, VERSION

CURRENT = f"{CARD_URL}?v={VERSION}"


class _Resources:
    """Minimal stand-in for Lovelace's resource storage collection."""

    def __init__(self, items: list[dict]) -> None:
        self._items = items
        self.loaded = True
        self.created: list[dict] = []
        self.updated: list[tuple[str, dict]] = []

    def async_items(self) -> list[dict]:
        return self._items

    async def async_create_item(self, data: dict) -> None:
        self.created.append(data)

    async def async_update_item(self, item_id: str, updates: dict) -> None:
        self.updated.append((item_id, updates))


def _install(hass: HomeAssistant, items: list[dict]) -> _Resources:
    resources = _Resources(items)
    hass.data["lovelace"] = SimpleNamespace(resources=resources)
    return resources


async def test_stale_version_is_updated(hass: HomeAssistant) -> None:
    """A resource left on an old version must be rewritten, not ignored."""
    resources = _install(
        hass, [{"id": "abc", "url": f"{CARD_URL}?v=2.0.0", "res_type": "module"}]
    )

    await _async_register_lovelace_resource(hass)

    assert resources.updated == [("abc", {"url": CURRENT})]
    assert resources.created == []


async def test_current_version_is_left_alone(hass: HomeAssistant) -> None:
    resources = _install(
        hass, [{"id": "abc", "url": CURRENT, "res_type": "module"}]
    )

    await _async_register_lovelace_resource(hass)

    assert resources.updated == []
    assert resources.created == []


async def test_missing_resource_is_created(hass: HomeAssistant) -> None:
    resources = _install(hass, [])

    await _async_register_lovelace_resource(hass)

    assert resources.created == [{"res_type": "module", "url": CURRENT}]
    assert resources.updated == []


async def test_unrelated_resources_are_ignored(hass: HomeAssistant) -> None:
    """Someone else's card must not be touched, and ours still registered."""
    resources = _install(
        hass, [{"id": "other", "url": "/local/some-other-card.js", "res_type": "module"}]
    )

    await _async_register_lovelace_resource(hass)

    assert resources.updated == []
    assert resources.created == [{"res_type": "module", "url": CURRENT}]
