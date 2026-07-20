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
import secrets
import shutil
import time
from datetime import timedelta
from typing import Any

import voluptuous as vol

from aiohttp import web

from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    Event,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.http import KEY_HASS

from homeassistant.util import slugify

from .analyzer import CameraPipeline
from .const import (
    ACTION_SOUND_ALARM,
    CARD_URL,
    CONF_ALARM_PANEL_ENTITY,
    CONF_CAMERA_ENTITY,
    CONF_CAMERA_ID,
    CONF_CAMERA_NAME,
    CONF_MOTION_ENTITIES,
    CONF_RETENTION_DAYS,
    CONF_VISITOR_DESCRIPTION,
    CONF_VISITOR_ID,
    CONF_VISITOR_NAME,
    DEFAULT_RETENTION_DAYS,
    DOMAIN,
    IMAGES_URL,
    KNOWN_DIR_NAME,
    KNOWN_URL,
    MAX_UPLOAD_BYTES,
    SIGNAL_NEW_ALERT,
    SNAPSHOTS_URL,
    STORAGE_DIR,
    SUBENTRY_CAMERA,
    SUBENTRY_KNOWN_VISITOR,
    SUBENTRY_TARGET,
    UPLOAD_URL,
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
        vol.Optional("known_person", default="none"): cv.string,
    }
)

ANALYZE_SCHEMA = vol.Schema({vol.Required("camera_id"): cv.slug})


# longest edge (px) reference photos are downscaled to — bounds storage and
# the number of image tokens sent to the AI provider.
_MAX_PHOTO_EDGE = 1024


def _write_known_photo(raw: bytes, dest: str) -> None:
    """Normalise an uploaded image to a bounded JPEG on disk.

    Uses Pillow (ships with Home Assistant) to validate the bytes are a real
    image, strip metadata, downscale, and re-encode as JPEG. If Pillow is
    somehow unavailable, only genuine JPEG bytes are accepted as-is.
    """
    try:
        import io

        from PIL import Image  # noqa: PLC0415 - optional, imported lazily
    except ImportError:
        # No Pillow: accept only data that already looks like a JPEG.
        if not raw.startswith(b"\xff\xd8\xff"):
            raise HomeAssistantError(
                "Uploaded file is not a JPEG and Pillow is unavailable to "
                "convert it."
            )
        with open(dest, "wb") as fh:
            fh.write(raw)
        return

    try:
        with Image.open(io.BytesIO(raw)) as img:
            img = img.convert("RGB")
            img.thumbnail((_MAX_PHOTO_EDGE, _MAX_PHOTO_EDGE))
            img.save(dest, format="JPEG", quality=85)
    except Exception as err:  # noqa: BLE001 - not a decodable image
        raise HomeAssistantError(f"Invalid image upload: {err}") from err


class AlertStore:
    """In-memory + on-disk (JSONL) store for alert records."""

    def __init__(self, hass: HomeAssistant, base_dir: str, retention_days: int) -> None:
        self.hass = hass
        self.base_dir = base_dir
        self.images_dir = os.path.join(base_dir, "images")
        self.snapshots_dir = os.path.join(base_dir, "snapshots")
        self.known_dir = os.path.join(base_dir, KNOWN_DIR_NAME)
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
        os.makedirs(self.known_dir, exist_ok=True)
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
        # Archived images are served on an unauthenticated static path, so
        # (a) never copy files from outside the allowed dirs (a malicious
        # log_alert call could otherwise publish e.g. secrets.yaml), and
        # (b) use an unguessable filename (capability URL).
        if not (
            src.startswith(self.base_dir + os.sep)
            or self.hass.config.is_allowed_path(src)
        ):
            raise HomeAssistantError(
                f"Path not allowed: {src} (add it to allowlist_external_dirs)"
            )
        if not await self.hass.async_add_executor_job(os.path.isfile, src):
            raise HomeAssistantError(f"Snapshot not found: {src}")
        ts = time.time()
        camera_id = data["camera_id"]
        fname = f"{int(ts * 1000)}_{secrets.token_hex(8)}.jpg"
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
            "known_person": data.get("known_person", "none"),
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

    # -- known-visitor reference photos ---------------------------------

    def _visitor_dir(self, visitor_id: str) -> str:
        """Directory for a visitor's photos, guarded against path escapes."""
        if not visitor_id or visitor_id != slugify(visitor_id):
            raise HomeAssistantError(f"Invalid visitor id: {visitor_id!r}")
        return os.path.join(self.known_dir, visitor_id)

    def known_photos_map(self) -> dict[str, list[str]]:
        """{visitor_id: [filename, ...]} for every visitor with photos (sync)."""
        result: dict[str, list[str]] = {}
        if not os.path.isdir(self.known_dir):
            return result
        for vid in os.listdir(self.known_dir):
            vdir = os.path.join(self.known_dir, vid)
            if not os.path.isdir(vdir):
                continue
            files = sorted(
                n for n in os.listdir(vdir) if n.lower().endswith(".jpg")
            )
            if files:
                result[vid] = files
        return result

    def list_known_photos(self, visitor_id: str) -> list[str]:
        """Photo filenames for one visitor, newest last (sync)."""
        return self.known_photos_map().get(visitor_id, [])

    def save_known_photo_sync(self, visitor_id: str, raw: bytes) -> str:
        """Validate/normalise an uploaded image to JPEG and store it (sync)."""
        vdir = self._visitor_dir(visitor_id)
        os.makedirs(vdir, exist_ok=True)
        fname = f"{int(time.time() * 1000)}_{secrets.token_hex(6)}.jpg"
        dest = os.path.join(vdir, fname)
        _write_known_photo(raw, dest)
        return fname

    def delete_known_photo_sync(self, visitor_id: str, filename: str) -> bool:
        """Delete one of a visitor's photos (basename-scoped). Returns success."""
        if os.path.basename(filename) != filename or not filename.endswith(".jpg"):
            raise HomeAssistantError(f"Invalid filename: {filename!r}")
        path = os.path.join(self._visitor_dir(visitor_id), filename)
        try:
            os.remove(path)
            return True
        except OSError:
            return False


@callback
def _sign_image(hass: HomeAssistant, url: str, retention_days: int) -> str:
    """Sign an archived alert-image URL so it can be fetched without a bearer.

    Only IMAGES_URL paths are signed (snapshots/known photos stay as capability
    URLs). The signature is tied to HA's stable content-user token and expires
    with the retention window — the image is pruned by then anyway.
    """
    if not url.startswith(IMAGES_URL + "/"):
        return url
    return async_sign_path(
        hass,
        url,
        timedelta(days=max(1, int(retention_days))),
        use_content_user=True,
    )


@callback
def _signed_alert(hass: HomeAssistant, record: dict[str, Any], days: int) -> dict[str, Any]:
    """A copy of an alert record with its image URL signed."""
    signed = dict(record)
    signed["image"] = _sign_image(hass, record.get("image", ""), days)
    return signed


@callback
def _signed_alerts(hass: HomeAssistant, store: "AlertStore") -> list[dict[str, Any]]:
    days = store.retention_days
    return [_signed_alert(hass, rec, days) for rec in store.alerts()]


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/alerts"})
@websocket_api.async_response
async def ws_list_alerts(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return alert records (with signed image URLs) to the frontend card."""
    store: AlertStore = hass.data[DOMAIN]["store"]
    connection.send_result(msg["id"], {"alerts": _signed_alerts(hass, store)})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@callback
def ws_subscribe_alerts(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Push each new alert to the card live, so it needn't poll."""
    store: AlertStore | None = hass.data.get(DOMAIN, {}).get("store")
    if store is None:
        connection.send_error(msg["id"], "not_ready", "Integration not ready")
        return

    @callback
    def _forward(record: dict[str, Any]) -> None:
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {"alert": _signed_alert(hass, record, store.retention_days)},
            )
        )

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(
        hass, SIGNAL_NEW_ALERT, _forward
    )
    connection.send_result(msg["id"])


def _known_visitors(entry: ConfigEntry) -> list[dict[str, str]]:
    """Known-visitor subentries as {visitor_id, name, description}."""
    out: list[dict[str, str]] = []
    for sub in entry.subentries.values():
        if sub.subentry_type != SUBENTRY_KNOWN_VISITOR:
            continue
        data = dict(sub.data)
        vid = (
            data.get(CONF_VISITOR_ID)
            or slugify(data.get(CONF_VISITOR_NAME, ""))
            or sub.subentry_id
        )
        out.append(
            {
                CONF_VISITOR_ID: vid,
                CONF_VISITOR_NAME: data.get(CONF_VISITOR_NAME, ""),
                CONF_VISITOR_DESCRIPTION: data.get(CONF_VISITOR_DESCRIPTION, ""),
            }
        )
    return out


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/visitors"})
@websocket_api.async_response
async def ws_list_visitors(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return known visitors and their reference-photo URLs for the card."""
    data = hass.data.get(DOMAIN, {})
    store: AlertStore | None = data.get("store")
    entry: ConfigEntry | None = data.get("entry")
    if store is None or entry is None:
        connection.send_result(msg["id"], {"visitors": []})
        return
    photo_map = await hass.async_add_executor_job(store.known_photos_map)
    visitors = [
        {
            **v,
            "photos": [
                {"filename": f, "url": f"{KNOWN_URL}/{v[CONF_VISITOR_ID]}/{f}"}
                for f in photo_map.get(v[CONF_VISITOR_ID], [])
            ],
        }
        for v in _known_visitors(entry)
    ]
    connection.send_result(msg["id"], {"visitors": visitors})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/delete_visitor_photo",
        vol.Required("visitor_id"): str,
        vol.Required("filename"): str,
    }
)
@websocket_api.async_response
async def ws_delete_visitor_photo(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete one of a visitor's reference photos (admin only)."""
    data = hass.data.get(DOMAIN, {})
    store: AlertStore | None = data.get("store")
    entry: ConfigEntry | None = data.get("entry")
    if store is None or entry is None:
        connection.send_error(msg["id"], "not_ready", "Integration not ready")
        return
    valid_ids = {v[CONF_VISITOR_ID] for v in _known_visitors(entry)}
    if msg["visitor_id"] not in valid_ids:
        connection.send_error(msg["id"], "unknown_visitor", "Unknown visitor")
        return
    try:
        deleted = await hass.async_add_executor_job(
            store.delete_known_photo_sync, msg["visitor_id"], msg["filename"]
        )
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "invalid_filename", str(err))
        return
    connection.send_result(msg["id"], {"deleted": deleted})


class KnownPhotoUploadView(HomeAssistantView):
    """Authenticated endpoint the people card posts reference photos to."""

    url = UPLOAD_URL
    name = f"api:{DOMAIN}:known_photo"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        user = request["hass_user"]
        if user is None or not user.is_admin:
            return web.Response(status=403, text="Admin privileges required")
        data = hass.data.get(DOMAIN, {})
        store: AlertStore | None = data.get("store")
        entry: ConfigEntry | None = data.get("entry")
        if store is None or entry is None:
            return web.Response(status=503, text="Integration not ready")
        # Cheap up-front guard on the declared size (multipart adds overhead).
        if request.content_length and request.content_length > MAX_UPLOAD_BYTES * 2:
            return web.Response(status=413, text="File too large")
        try:
            post = await request.post()
        except Exception:  # noqa: BLE001 - malformed multipart
            return web.Response(status=400, text="Invalid form data")
        visitor_id = str(post.get("visitor_id", ""))
        valid_ids = {v[CONF_VISITOR_ID] for v in _known_visitors(entry)}
        if visitor_id not in valid_ids:
            return web.Response(status=400, text="Unknown visitor")
        field = post.get("file")
        if field is None or not hasattr(field, "file"):
            return web.Response(status=400, text="No file uploaded")
        ctype = (getattr(field, "content_type", "") or "").lower()
        if ctype and not ctype.startswith("image/"):
            return web.Response(status=400, text="Uploaded file is not an image")
        raw = await hass.async_add_executor_job(field.file.read)
        if not raw:
            return web.Response(status=400, text="Empty file")
        if len(raw) > MAX_UPLOAD_BYTES:
            return web.Response(status=413, text="File too large")
        try:
            fname = await hass.async_add_executor_job(
                store.save_known_photo_sync, visitor_id, raw
            )
        except HomeAssistantError as err:
            _LOGGER.warning(
                "Known photo upload failed for visitor_id=%s: %s", visitor_id, err
            )
            return web.Response(status=400, text="Unable to save uploaded photo")
        return web.json_response(
            {"filename": fname, "url": f"{KNOWN_URL}/{visitor_id}/{fname}"}
        )


class AlertImageView(HomeAssistantView):
    """Serve archived alert images behind auth so signed URLs are required.

    Replaces the old unauthenticated static path: a request with a valid
    signed URL (`?authSig=…`) or a bearer token succeeds; anything else 401s.
    """

    url = IMAGES_URL + "/{tail:.+}"
    name = f"api:{DOMAIN}:image"
    requires_auth = True

    async def get(self, request: web.Request, tail: str) -> web.StreamResponse:
        hass: HomeAssistant = request.app[KEY_HASS]
        store: AlertStore | None = hass.data.get(DOMAIN, {}).get("store")
        if store is None:
            return web.Response(status=503, text="Integration not ready")
        base = os.path.realpath(store.images_dir)
        path = os.path.realpath(os.path.join(base, tail))
        # Never serve outside the images directory (path-traversal guard).
        if not (path == base or path.startswith(base + os.sep)):
            return web.Response(status=404)
        if not await hass.async_add_executor_job(os.path.isfile, path):
            return web.Response(status=404)
        return web.FileResponse(path)


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
    # Kept current across reloads so the websocket/upload handlers can read the
    # known-visitor subentries of the (single) config entry.
    hass.data[DOMAIN]["entry"] = entry

    # Static paths, websocket commands and the upload view survive reloads;
    # register once.
    if not hass.data[DOMAIN].get("http_registered"):
        card_path = os.path.join(
            os.path.dirname(__file__), "www", "ai-camera-centre-card.js"
        )
        # Archived alert images are served behind auth (signed URLs); burst
        # snapshots and known-visitor photos remain capability URLs.
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(SNAPSHOTS_URL, store.snapshots_dir, False),
                StaticPathConfig(KNOWN_URL, store.known_dir, False),
                StaticPathConfig(CARD_URL, card_path, True),
            ]
        )
        websocket_api.async_register_command(hass, ws_list_alerts)
        websocket_api.async_register_command(hass, ws_subscribe_alerts)
        websocket_api.async_register_command(hass, ws_list_visitors)
        websocket_api.async_register_command(hass, ws_delete_visitor_photo)
        hass.http.register_view(KnownPhotoUploadView())
        hass.http.register_view(AlertImageView())
        hass.data[DOMAIN]["http_registered"] = True

    # -- built-in analysis pipelines (one per camera subentry) ---------
    targets = [
        dict(sub.data)
        for sub in entry.subentries.values()
        if sub.subentry_type == SUBENTRY_TARGET
    ]
    # Normalised so every visitor carries a stable visitor_id (legacy visitors
    # predating the id get a computed fallback) matching the photo dir keys.
    known_visitors = _known_visitors(entry)

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    pipelines: dict[str, CameraPipeline] = {}
    for sub in entry.subentries.values():
        if sub.subentry_type != SUBENTRY_CAMERA:
            continue
        camera_conf = dict(sub.data)
        camera_id = camera_conf.get(CONF_CAMERA_ID) or sub.subentry_id
        pipeline = CameraPipeline(
            hass,
            store,
            dict(entry.options),
            camera_id,
            camera_conf,
            targets,
            known_visitors,
        )
        pipelines[camera_id] = pipeline
        motion_entities = camera_conf.get(CONF_MOTION_ENTITIES) or []
        if motion_entities:
            camera_label = camera_conf.get(CONF_CAMERA_NAME) or camera_id
            _warn_unknown_motion_entities(
                hass, ent_reg, camera_label, motion_entities
            )
            _warn_trigger_device_mismatch(
                hass,
                ent_reg,
                dev_reg,
                camera_label,
                camera_conf.get(CONF_CAMERA_ENTITY),
                motion_entities,
            )
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

    async def handle_notification_action(event: Event) -> None:
        """'Sound alarm' button on a notification -> trigger Alarmo."""
        if event.data.get("action") != ACTION_SOUND_ALARM:
            return
        panel = entry.options.get(CONF_ALARM_PANEL_ENTITY)
        if not panel:
            return
        try:
            await hass.services.async_call(
                "alarmo", "trigger", {"entity_id": panel}, blocking=False
            )
        except Exception:  # noqa: BLE001 - alarmo missing / API change
            _LOGGER.exception("Failed to trigger alarm from notification action")

    entry.async_on_unload(
        hass.bus.async_listen(
            "mobile_app_notification_action", handle_notification_action
        )
    )

    entry.async_on_unload(
        async_track_time_interval(hass, store.async_prune, timedelta(hours=6))
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _inherit_camera_areas(hass, entry)
    hass.async_create_task(_async_register_lovelace_resource(hass))
    return True


@callback
def _warn_unknown_motion_entities(
    hass: HomeAssistant,
    ent_reg: er.EntityRegistry,
    camera_label: str,
    motion_entities: list[str],
) -> None:
    """Warn about configured motion triggers that don't exist.

    A camera silently stops triggering when a configured motion entity id no
    longer resolves — e.g. the source integration renamed it, the device was
    re-added, or it was mistyped. ``async_track_state_change_event`` matches on
    the exact id and never fires for a missing one, so without this the failure
    is invisible: the source integration shows motion, but our pipeline never
    runs. We check both the live state machine and the (persistent) entity
    registry so a source integration that simply hasn't finished loading yet
    isn't falsely reported as missing.
    """
    missing = [
        entity_id
        for entity_id in motion_entities
        if hass.states.get(entity_id) is None
        and ent_reg.async_get(entity_id) is None
    ]
    if missing:
        _LOGGER.warning(
            "Camera '%s': motion trigger %s not found in Home Assistant — "
            "motion from this camera will be ignored until the entity id is "
            "corrected in the camera's settings. Trigger entity ids can change "
            "when the source integration is updated or the device is renamed.",
            camera_label,
            ", ".join(missing),
        )


@callback
def _warn_trigger_device_mismatch(
    hass: HomeAssistant,
    ent_reg: er.EntityRegistry,
    dev_reg: dr.DeviceRegistry,
    camera_label: str,
    camera_entity: str | None,
    motion_entities: list[str],
) -> None:
    """Warn when a motion trigger belongs to a different device than the camera.

    Cameras of the same model usually share a device name, so Home Assistant
    disambiguates their entity ids with numeric suffixes (``..._motion_2``,
    ``..._person_3``). Picking the wrong one is easy and completely silent:
    every entity resolves, nothing errors, and the camera simply never fires
    for the events you expected — it only wakes for whatever the mis-picked
    sensor reports.

    Cross-device triggers are legitimate (a separate PIR covering the same
    view), so this is advisory. Helpers (input_boolean/switch) have no device
    and are skipped.
    """
    if not camera_entity:
        return
    source = ent_reg.async_get(camera_entity)
    if source is None or source.device_id is None:
        return

    def _device_name(device_id: str) -> str:
        device = dev_reg.async_get(device_id)
        if device is None:
            return "unknown device"
        return device.name_by_user or device.name or "unnamed device"

    mismatched = [
        f"{entity_id} (device: {_device_name(entry.device_id)})"
        for entity_id in motion_entities
        if (entry := ent_reg.async_get(entity_id)) is not None
        and entry.device_id is not None
        and entry.device_id != source.device_id
    ]
    if mismatched:
        _LOGGER.warning(
            "Camera '%s': motion trigger(s) %s belong to a different device "
            "than its camera entity %s (device: %s). That is supported — e.g. "
            "a separate motion sensor covering the same view — but it is also "
            "what a mis-picked trigger looks like when several cameras share a "
            "device name. If this camera isn't firing when you expect, check "
            "its Motion triggers.",
            camera_label,
            ", ".join(mismatched),
            camera_entity,
            _device_name(source.device_id),
        )


def _source_area_id(
    ent_reg: er.EntityRegistry, dev_reg: dr.DeviceRegistry, entity_id: str
) -> str | None:
    """The area of a camera entity (its own, else its device's)."""
    source = ent_reg.async_get(entity_id)
    if source is None:
        return None
    if source.area_id:
        return source.area_id
    if source.device_id and (device := dev_reg.async_get(source.device_id)):
        return device.area_id
    return None


@callback
def _inherit_camera_areas(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Place each camera device in its source camera's area, if unset.

    Runs after the platforms create the devices. Only fills an empty area,
    so a user's manual placement is never overridden.
    """
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    for sub in entry.subentries.values():
        if sub.subentry_type != SUBENTRY_CAMERA:
            continue
        camera_id = sub.data.get(CONF_CAMERA_ID)
        camera_entity = sub.data.get(CONF_CAMERA_ENTITY)
        if not camera_id or not camera_entity:
            continue
        device = dev_reg.async_get_device(identifiers={(DOMAIN, camera_id)})
        if device is None or device.area_id is not None:
            continue
        if area_id := _source_area_id(ent_reg, dev_reg, camera_entity):
            dev_reg.async_update_device(device.id, area_id=area_id)


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
        hass.data[DOMAIN].pop("entry", None)
    return unload_ok
