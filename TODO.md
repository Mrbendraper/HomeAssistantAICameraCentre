# Roadmap

## Done

- **1. Conditional notifications — presence / alarm state** (v2.2.0).
  Per-target `notify_condition` (always / away / armed / away_or_armed);
  "away" = no `person.*` in the `home` zone; "armed" uses an
  `alarm_control_panel` picked in Settings. Evaluated in
  `analyzer.CameraPipeline._notify`.
- **2. Trigger Alarmo on high-risk alerts** (v2.2.0). Settings
  `alarmo_enabled` + `alarmo_trigger_score`; calls `alarmo.trigger` with
  `entity_id` when the score meets the threshold **and** the panel is
  armed. ⚠️ Still to verify against a live Alarmo instance that
  `alarmo.trigger` accepts `entity_id` (vs `area_id`) on the user's
  version.
- **3. Selective logging — risk level and time window** (v2.2.0). Settings
  `min_log_score` and optional `log_window_start`/`log_window_end`
  (wraps past midnight). Gates only `store.async_log` / the card in
  `analyzer._run`; notifications and Alarmo stay independent (an unlogged
  alert still notifies, using the transient snapshot image), so a real
  threat outside the logging window is never silently dropped. A forced
  `analyze` service call always archives. Global, not per-camera.

## Planned

## 4. UI overhaul — each camera as its own device

Everything currently lives on one integration card with a single "1 service"
entry and all configuration buried in the options-flow menu. Restructure so
the integration page reads like a proper multi-device hub:

- **Config subentries** (HA 2025.3+, `ConfigSubentryFlow`): make each camera
  a subentry of the main config entry. The integration page then gets a
  native **"Add camera"** button, and every camera is listed with its own
  rename / configure / delete controls — no more add/edit/remove menu inside
  the options flow. Alert targets could be a second subentry type
  (`async_get_supported_subentry_types` returns both).
- **Device registry**: register one device per camera subentry
  (`device_registry.async_get_or_create` with the subentry id), so each
  camera gets a device page. Attach all of that camera's entities to it.
- **More per-camera entities** hanging off each device:
  - `image` entity showing the latest alert snapshot
  - `sensor` for last alert score (plus existing 24h-count sensor)
  - `binary_sensor` "alert in the last N minutes"
  - `switch` to pause/resume analysis for that camera (holiday mode,
    gardener day, etc.)
  - `button` to run `analyze` for that camera from the device page
- Migration: on upgrade, convert the `cameras` dict in options into
  subentries (config entry `async_migrate_entry` bumping the entry VERSION)
  so existing setups carry over without reconfiguring.
- The options flow shrinks to just the global settings.
- Touches: `config_flow.py` (subentry flows), `__init__.py` (setup loops
  over subentries instead of options; migration), `sensor.py` (+ new
  platform files `image.py`, `binary_sensor.py`, `switch.py`, `button.py`),
  `strings.json`/`translations`.

## Backlog — further ideas (unscoped)

- **Live card updates** — push new alerts to the Lovelace card over a
  websocket subscription instead of the current 5-minute poll, so an alert
  appears on the dashboard the moment it's logged.
- **HA event on every alert** — fire `ai_camera_centre_alert` on the event
  bus with the full report, so users can build their own automations
  without touching our services.
- **Structured AI output** — use `ai_task.generate_data`'s `structure`
  parameter (schema-enforced fields) instead of prompt-and-parse JSON;
  falls back to text parsing for providers that don't support it.
- **Repeat-visitor context** — include the previous alert's report (if
  recent) in the prompt so the AI can say "same person as 3 minutes ago,
  still loitering" and score escalating behaviour higher; optionally
  suppress duplicate notifications for the same ongoing event.
- **Video clips** — record a short clip (`camera.record`) alongside the
  snapshot burst and attach it to the notification / detail view.
- **Notification polish** — Android notification channels by score band
  (so high scores can ring through Do Not Disturb), iOS critical alerts,
  actionable buttons on the notification ("Sound alarm", "Dismiss").
- **Card polish** — full-screen lightbox for images, mark-as-reviewed
  state, unreviewed-count badge.
- **Diagnostics + repairs** — implement the diagnostics platform (download
  redacted config/state for bug reports) and repair issues for common
  misconfigurations (no AI Task provider, camera entity missing).
- **CI** — GitHub Actions running hassfest validation and the HACS action
  on every push/PR, so releases can't ship a broken manifest.
- **Tests** — pytest-homeassistant-custom-component coverage for the
  store, pipeline (mocked ai_task), and config flow.
- **Translations** — the strings are translation-ready; add other
  languages once text stabilises.
- **HACS default repository** — after the brands PR is merged and CI is in
  place, submit to the HACS default list so users can install without
  adding a custom repository.
