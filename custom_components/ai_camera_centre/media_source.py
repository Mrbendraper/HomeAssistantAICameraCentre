"""Media source exposing AI Camera Centre files.

Lets the built-in pipeline hand local snapshot files to the ai_task
service as attachments (media-source://ai_camera_centre/snapshots/...),
and makes archived alert images browsable in the media browser.
"""
from __future__ import annotations

import os
from pathlib import Path

from homeassistant.components.media_player import MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN, IMAGES_URL, KNOWN_URL, SNAPSHOTS_URL, STORAGE_DIR


async def async_get_media_source(hass: HomeAssistant) -> "CameraCentreMediaSource":
    """Set up the AI Camera Centre media source."""
    return CameraCentreMediaSource(hass)


class CameraCentreMediaSource(MediaSource):
    """Serve files from the integration's storage directory."""

    name = "AI Camera Centre"

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(DOMAIN)
        self.hass = hass
        self._base = Path(hass.config.path(STORAGE_DIR))

    def _resolve_path(self, identifier: str) -> Path:
        path = (self._base / identifier).resolve()
        if not str(path).startswith(str(self._base.resolve()) + os.sep):
            raise Unresolvable(f"Invalid path: {identifier}")
        return path

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        if not item.identifier:
            raise Unresolvable("No file specified")
        path = self._resolve_path(item.identifier)
        if not await self.hass.async_add_executor_job(path.is_file):
            raise Unresolvable(f"File not found: {item.identifier}")
        if item.identifier.startswith("snapshots/"):
            url = f"{SNAPSHOTS_URL}/{item.identifier.removeprefix('snapshots/')}"
        elif item.identifier.startswith("known/"):
            url = f"{KNOWN_URL}/{item.identifier.removeprefix('known/')}"
        else:
            url = f"{IMAGES_URL}/{item.identifier.removeprefix('images/')}"
        return PlayMedia(url=url, mime_type="image/jpeg", path=path)

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        identifier = item.identifier or ""
        base = self._resolve_path(identifier) if identifier else self._base

        def _list_dir() -> list[tuple[str, bool]]:
            if not base.is_dir():
                return []
            entries = []
            for child in sorted(base.iterdir()):
                if child.is_dir() or child.suffix == ".jpg":
                    entries.append((child.name, child.is_dir()))
            return entries

        children = []
        for name, is_dir in await self.hass.async_add_executor_job(_list_dir):
            child_id = f"{identifier}/{name}" if identifier else name
            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=child_id,
                    media_class=MediaClass.DIRECTORY if is_dir else MediaClass.IMAGE,
                    media_content_type="" if is_dir else "image/jpeg",
                    title=name,
                    can_play=not is_dir,
                    can_expand=is_dir,
                )
            )
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=identifier,
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title=self.name if not identifier else identifier,
            can_play=False,
            can_expand=True,
            children=children,
        )
