# Roadmap

Planned features, not yet implemented. Each item below is scoped enough to
pick up and build directly.

## 1. Conditional notifications — presence / alarm state

Add an optional **notify condition** to each alert target (alongside the
existing minimum score and camera filter), so targets can stay quiet while
someone's home and the house isn't armed.

- New per-target field `notify_condition`, one of:
  - `always` (current/default behaviour)
  - `away` — only notify when nobody is home
  - `armed` — only notify when the alarm panel is armed (any armed state)
  - `away_or_armed` — either condition satisfied
- "Nobody home" — use the built-in `zone.home` entity's `persons` attribute
  (or count `person.*` entities in state `home`); no dependency on a
  specific presence integration.
- "Armed" — needs an alarm panel entity selector in **Settings** (a single
  `alarm_control_panel.*` picked once, reused by every target), condition
  true when its state is any of `armed_home` / `armed_away` /
  `armed_night` / `armed_vacation` / `armed_custom_bypass`.
- Touches: `const.py` (new keys), `config_flow.py` (`_target_schema` +
  a new `alarm_panel_entity` field in `_settings_schema`), `analyzer.py`
  (`_notify` gains the condition check before the score/camera check).

## 2. Trigger Alarmo on high-risk alerts

Optional: when an alert's score crosses a threshold, trigger the
[Alarmo](https://github.com/nielsfaber/alarmo) integration instead of (or
as well as) sending a notification — e.g. a suspicion score of 9+ while
armed_away should sound the siren, not just ping a phone.

- New global (or per-camera?) settings: `alarmo_enabled` (bool),
  `alarmo_trigger_score` (1–10, default e.g. 9).
- Call `alarmo.trigger` (Alarmo's service for tripping the alarm as if a
  sensor fired) when `report["score"] >= alarmo_trigger_score` — likely
  restricted to when the panel is already armed, so a benign high score
  while everyone's home and disarmed doesn't set it off. Reuse the same
  alarm panel entity from item 1 for the armed check.
- Needs testing against a real Alarmo instance to confirm the exact
  service name/payload (`area_id` vs `entity_id`) — check the current
  Alarmo docs before implementing, the service surface has changed
  between versions.
- Touches: `const.py`, `config_flow.py` (settings step), `analyzer.py`
  (`_run`, after logging the record and before/alongside `_notify`).

## 3. Selective logging — risk level and time window

Right now every alert that isn't "no obvious motion" gets archived
(image + report) regardless of score or time of day. Add filters so
low-risk daytime noise (e.g. the cat, a delivery van) doesn't fill the
history:

- **(a) Minimum score to log** — a new setting `min_log_score` (default 1
  = log everything, current behaviour). Alerts below this are discarded
  after analysis rather than archived — still evaluated by the AI (so
  cooldown logic and testing still work) but skipped in `AlertStore.async_log`.
- **(b) Time-window logging** — an optional "only log during these hours"
  range (e.g. 22:00–06:00 for nighttime-only history), or the inverse
  ("skip logging during these hours"). Needs a from/to time selector in
  **Settings**; compare against `homeassistant.util.dt.now()` local time
  at the point the alert would be logged.
- Both filters should be independent of the notify-target filters above —
  e.g. you might want notifications only when armed (item 1) but logging
  of every real alert regardless, or vice versa. Consider whether these
  filters are global or per-camera; per-camera is more flexible but adds
  UI surface — start global, revisit if requested.
- Touches: `const.py`, `config_flow.py` (`_settings_schema`), `analyzer.py`
  (`_run` — gate the `store.async_log` call), `sensor.py` (24h counts
  will reflect only logged alerts, which is probably the desired
  behaviour, but worth calling out in the changelog since it's a
  behaviour change from "every real alert is logged").

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
