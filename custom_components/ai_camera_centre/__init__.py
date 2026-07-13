"""The AI Camera Centre integration.

Self-contained AI camera alerting: configure cameras (stream + motion
trigger + scene context) in the UI and the integration captures snapshot
bursts, runs AI analysis via ai_task, persists alert reports and images,
notifies your devices, and serves a bundled Lovelace timeline card.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

from .analyzer import CameraPipeline
from .const import (
    CARD_URL,
    CONF_CAMERA_ID,
    CONF_MOTION_ENTITIES,
    CONF_RETENTION_DAYS,
    DEFAULT_RETENTION_DAYS,
    DOMAIN,
    IMAGES_URL,
    SIGNAL_NEW_ALERT,
    SNAPSHOTS_URL,
    STORAGE_DIR,
    SUBENTRY_CAMERA,
    SUBENTRY_TARGET,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.IMAGE,
    Platform.SWITCH,
    Platform.BUTTON,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_LOG_ALERT = "log_alert"
SERVICE_ANALYZE = "analyze"

LOG_ALERT_SCHEMA = vol.Schema(
    {
        vol.Required("camera_id"): cv.slug,
        vol.Optional("camera_label"): cv.string,
        vol.Required("image_path"): cv.string,
        vol.Required("score"): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
        vol.Optional("short", default=""): cv.string,
        vol.Optional("detail", default=""): cv.string,
        vol.Optional("direction", default="unknown"): cv.string,
        vol.Optional("carrying", default="unknown"): cv.string,
        vol.Optional("activity", default="unknown"): cv.string,
        vol.Optional("gate_state", default="n/a"): cv.string,
        vol.Optional("gate_risk", default="n/a"): cv.string,
    }
)

ANALYZE_SCHEMA = vol.Schema({vol.Required("camera_id"): cv.slug})


class AlertStore:
    """In-memory + on-disk (JSONL) store for alert records."""

    def __init__(self, hass: HomeAssistant, base_dir: str, retention_days: int) -> None:
        self.hass = hass
        self.base_dir = base_dir
        self.images_dir = os.path.join(base_dir, "images")
        self.snapshots_dir = os.path.join(base_dir, "snapshots")
        self.log_path = os.path.join(base_dir, "alerts.jsonl")
        self.retention_days = retention_days
        self.records: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    @property
    def _cutoff(self) -> float:
        return time.time() - self.retention_days * 86400

    # -- sync helpers (run in executor) --------------------------------

    def _load_sync(self) -> list[dict[str, Any]]:
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.snapshots_dir, exist_ok=True)
        records: list[dict[str, Any]] = []
        if os.path.exists(self.log_path):
            with open(self.log_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return records

    def _append_sync(self, record: dict[str, Any], src: str, dest: str) -> None:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(src, dest)
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _prune_sync(self, cutoff: float, kept: list[dict[str, Any]]) -> None:
        for root, _dirs, files in os.walk(self.images_dir):
            for name in files:
                if not name.endswith(".jpg"):
                    continue
                path = os.path.join(root, name)
                try:
                    if os.path.getmtime(path) < cutoff:
                        os.remove(path)
                except OSError:
                    continue
        tmp = self.log_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for rec in kept:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        os.replace(tmp, self.log_path)

    # -- async API ------------------------------------------------------

    async def async_load(self) -> None:
        async with self._lock:
            self.records = await self.hass.async_add_executor_job(self._load_sync)

    async def async_log(self, data: dict[str, Any]) -> dict[str, Any]:
        src = data["image_path"]
        if not await self.hass.async_add_executor_job(os.path.isfile, src):
            raise HomeAssistantError(f"Snapshot not found: {src}")
        ts = time.time()
        camera_id = data["camera_id"]
        fname = f"{int(ts * 1000)}.jpg"
        dest = os.path.join(self.images_dir, camera_id, fname)
        record = {
            "ts": round(ts, 3),
            "camera": camera_id,
            "camera_label": data.get("camera_label")
            or camera_id.replace("_", " ").title(),
            "score": data["score"],
            "short": data["short"],
            "detail": data["detail"],
            "direction": data["direction"],
            "carrying": data["carrying"],
            "activity": data["activity"],
            "gate_state": data["gate_state"],
            "gate_risk": data["gate_risk"],
            "image": f"{IMAGES_URL}/{camera_id}/{fname}",
        }
        async with self._lock:
            await self.hass.async_add_executor_job(
                self._append_sync, record, src, dest
            )
            self.records.append(record)
        return record

    async def async_prune(self, *_args: Any) -> None:
        cutoff = self._cutoff
        async with self._lock:
            kept = [r for r in self.records if float(r.get("ts", 0)) >= cutoff]
            await self.hass.async_add_executor_job(self._prune_sync, cutoff, kept)
            self.records = kept

    def alerts(self) -> list[dict[str, Any]]:
        """Records within retention, newest first (no disk access)."""
        cutoff = self._cutoff
        return sorted(
            (r for r in self.records if float(r.get("ts", 0)) >= cutoff),
            key=lambda r: r["ts"],
            reverse=True,
        )

    def cameras(self) -> dict[str, str]:
        cams: dict[str, str] = {}
        for rec in self.alerts():
            cams.setdefault(rec["camera"], rec.get("camera_label") or rec["camera"])
        return cams

    # -- per-camera queries (used by the entity platforms) --------------

    def camera_alerts(self, camera_id: str) -> list[dict[str, Any]]:
        """All in-retention alerts for one camera, newest first."""
        return [r for r in self.alerts() if r.get("camera") == camera_id]

    def latest_for(self, camera_id: str) -> dict[str, Any] | None:
        alerts = self.camera_alerts(camera_id)
        return alerts[0] if alerts else None

    def count_since(self, camera_id: str, cutoff: float) -> int:
        return sum(
            1
            for r in self.camera_alerts(camera_id)
            if float(r.get("ts", 0)) >= cutoff
        )

    def image_path_for(self, record: dict[str, Any]) -> str | None:
        """Map an alert record's image URL back to its file on disk."""
        image = record.get("image", "")
        if not image:
            return None
        fname = os.path.basename(image)
        return os.path.join(self.images_dir, record.get("camera", ""), fname)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/alerts"})
@websocket_api.async_response
async def ws_list_alerts(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return alert records to the frontend card."""
    store: AlertStore = hass.data[DOMAIN]["store"]
    connection.send_result(msg["id"], {"alerts": store.alerts()})


async def _async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Best-effort auto-registration of the bundled card."""
    try:
        lovelace = hass.data.get("lovelace")
        resources = getattr(lovelace, "resources", None)
        if resources is None and isinstance(lovelace, dict):
            resources = lovelace.get("resources")
        if resources is None or not hasattr(resources, "async_create_item"):
            raise RuntimeError("Lovelace resource collection unavailable")
        if hasattr(resources, "loaded") and not resources.loaded:
            await resources.async_load()
        for item in resources.async_items():
            if str(item.get("url", "")).split("?")[0] == CARD_URL:
                return
        await resources.async_create_item(
            {"res_type": "module", "url": f"{CARD_URL}?v={VERSION}"}
        )
        _LOGGER.info("Registered Lovelace resource %s", CARD_URL)
    except Exception:  # noqa: BLE001 - YAML-mode dashboards, API changes
        _LOGGER.warning(
            "Could not auto-register the AI Camera Centre card. Add it manually: "
            "Settings > Dashboards > Resources > Add > URL: %s, type: module",
            CARD_URL,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AI Camera Centre from a config entry."""
    retention = entry.options.get(CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS)
    base_dir = hass.config.path(STORAGE_DIR)
    store = AlertStore(hass, base_dir, retention)
    await store.async_load()
    await store.async_prune()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["store"] = store

    # Static paths and websocket command survive reloads; register once.
    if not hass.data[DOMAIN].get("http_registered"):
        card_path = os.path.join(
            os.path.dirname(__file__), "www", "ai-camera-centre-card.js"
        )
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(IMAGES_URL, store.images_dir, False),
                StaticPathConfig(SNAPSHOTS_URL, store.snapshots_dir, False),
                StaticPathConfig(CARD_URL, card_path, True),
            ]
        )
        websocket_api.async_register_command(hass, ws_list_alerts)
        hass.data[DOMAIN]["http_registered"] = True

    # -- built-in analysis pipelines (one per camera subentry) ---------
    targets = [
        dict(sub.data)
        for sub in entry.subentries.values()
        if sub.subentry_type == SUBENTRY_TARGET
    ]

    pipelines: dict[str, CameraPipeline] = {}
    for sub in entry.subentries.values():
        if sub.subentry_type != SUBENTRY_CAMERA:
            continue
        camera_conf = dict(sub.data)
        camera_id = camera_conf.get(CONF_CAMERA_ID) or sub.subentry_id
        pipeline = CameraPipeline(
            hass, store, dict(entry.options), camera_id, camera_conf, targets
        )
        pipelines[camera_id] = pipeline
        motion_entities = camera_conf.get(CONF_MOTION_ENTITIES) or []
        if motion_entities:
            entry.async_on_unload(
                async_track_state_change_event(
                    hass, motion_entities, pipeline.handle_motion_event
                )
            )
    hass.data[DOMAIN]["pipelines"] = pipelines

    async def handle_log_alert(call: ServiceCall) -> ServiceResponse:
        record = await store.async_log(dict(call.data))
        async_dispatcher_send(hass, SIGNAL_NEW_ALERT, record)
        if call.return_response:
            return {"image_url": record["image"], "ts": record["ts"]}
        return None

    async def handle_analyze(call: ServiceCall) -> None:
        camera_id = call.data["camera_id"]
        pipeline = hass.data[DOMAIN]["pipelines"].get(camera_id)
        if pipeline is None:
            raise HomeAssistantError(
                f"No camera '{camera_id}' is configured in AI Camera Centre "
                f"(configured: {', '.join(hass.data[DOMAIN]['pipelines']) or 'none'})"
            )
        await pipeline.async_analyze(force=True)

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOG_ALERT,
        handle_log_alert,
        schema=LOG_ALERT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ANALYZE, handle_analyze, schema=ANALYZE_SCHEMA
    )

    entry.async_on_unload(
        async_track_time_interval(hass, store.async_prune, timedelta(hours=6))
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hass.async_create_task(_async_register_lovelace_resource(hass))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.services.async_remove(DOMAIN, SERVICE_LOG_ALERT)
        hass.services.async_remove(DOMAIN, SERVICE_ANALYZE)
        hass.data[DOMAIN].pop("store", None)
        hass.data[DOMAIN].pop("pipelines", None)
    return unload_ok
