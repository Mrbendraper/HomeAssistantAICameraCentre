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

- **4. UI overhaul — each camera as its own device** (v2.3.0). Cameras and
  alert targets are now config *subentries* (`ConfigSubentryFlow`), so the
  integration page has native Add camera / Add alert target buttons and
  per-item edit/delete; the options flow is global settings only. Each
  camera registers a device with six entities (`sensor` alerts-24h +
  last-score, `binary_sensor` recent-alert, `image` latest-alert, `switch`
  analysis on/off, `button` analyze-now). `camera_id` slugs stay stable so
  the alert store/history is keyed consistently. New files: `entity.py`,
  `image.py`, `binary_sensor.py`, `switch.py`, `button.py`. No config
  migration: 2.3 is a fresh-config release (all back-compat/migration code
  was removed — see below), so an existing dev install is removed and
  re-added.
  ⚠️ **Needs live-HA verification** (drafted without a running HA):
  - `ConfigSubentryFlow._get_entry()` / `_get_reconfigure_subentry()` and
    `async_update_and_abort` signatures on the installed HA version.
  - That adding/removing a camera subentry via the UI reloads the entry so
    its pipeline + entities appear/disappear (relies on the update listener
    firing on subentry changes).

- **Removed all migration / back-compat code** (v2.3.0). Dropped the v1→v2
  options→subentry migration, the `alert_history`→`ai_camera_centre` storage
  dir move, the legacy image-URL rewrite, the pre-2.1 single
  `motion_entity` key, and the `notify_services`/`min_notify_score` legacy
  options — the project is pre-release so there are no old installs to
  support.

## Backlog — further ideas (unscoped)

_Done since 2.3.1 (unreleased, next tag):_
- **HA event on every alert** ✅ — `ai_camera_centre_alert` fired on the bus
  for every alert (logged or not) with the full report + `logged` flag.
- **CI** ✅ — `.github/workflows/validate.yml` runs hassfest + the HACS
  action (brands check skipped, since brands ship bundled) on push/PR/weekly.
- **Diagnostics** ✅ — `diagnostics.py` dumps options, cameras, targets and
  runtime state (no secrets to redact).
- **Structured AI output** ✅ — `ai_task.generate_data` is called with a
  `structure` (ALERT_STRUCTURE) so the provider returns validated fields
  directly. Falls back to prompt-and-parse JSON for providers/entities
  without structured support, and remembers the failure per session
  (`_structured_ok`) so it doesn't re-bill a doomed structured call each
  analysis. `_parse_ai_result` already handled both dict and str inputs.

_Still open:_

- **Auto-inherit camera area** — when a camera device is created, look up
  the source camera entity's area (entity registry → its device/area) and
  set the AI Camera Centre device to the same area, so it doesn't need
  manual placement. Users can still override. Registry lookup at setup in
  `__init__.async_setup_entry` (or via `DeviceInfo`); make it best-effort
  (skip if the source entity has no area). Cameras are already assignable to
  areas manually today (they're devices) — this is just convenience.
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
