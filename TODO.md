# Roadmap

## Shipped

- **2.8.0** — Grouped settings UI (global and per-camera forms organised into
  collapsible sections with headings, section descriptions and per-field help
  text). Startup warning when a camera's configured motion-trigger entity id no
  longer exists, so a stale/renamed trigger no longer fails silently.
- **2.7.0** — Live card updates (new alerts push to the timeline card over a
  websocket subscription instead of the 5-minute poll). Signed, expiring URLs
  for archived alert images (served behind auth via `async_sign_path` with the
  content-user token, retention-length expiry; snapshots/known photos still use
  capability URLs).
- **2.6.0** — Motion-ignore processing rules (skip the whole pipeline based on
  presence + alarm state + time, where time can be absolute or day/night from a
  sun entity; house-wide default with a per-camera follow/custom policy).
  Reference photos for known people (upload via the new **AI Camera Centre
  People** card; attached to the AI prompt for visual recognition). Global AI
  response style / personality override (wording only).
- **2.5.0** — Known visitors (household members / regulars as a
  `known_visitor` subentry, injected into the prompt; recognised name
  recorded as `known_person`). Repeat-visitor context (recent alerts fed
  back into the prompt for loitering / return detection).
- **2.4.0** — Card image lightbox. Score-banded notification channels +
  iOS interruption level + a "Sound alarm" action button. Camera devices
  auto-inherit their source camera's area. `ai_camera_centre_alert` event.
  Diagnostics. CI (hassfest + HACS). Structured AI output with text
  fallback.
- **2.3.x** — Each camera is a config subentry / device with six entities
  (24h count, last score, recent-alert binary sensor, latest-alert image,
  analysis switch, analyze button). Friendly alert-target names.
- **2.2.0** — Conditional notifications (presence / alarm state). Alarmo
  trigger on high-risk alerts. Selective logging (min score + time window).
- **2.1.x** — Alert targets and multiple motion triggers per camera.
  Brand images bundled in the integration (HA 2026.3 brands proxy).
- **2.0.0** — Renamed to AI Camera Centre; self-contained analysis pipeline
  (snapshot burst → AI → log → notify), bundled timeline card.

## Backlog

- **Video clips** — record a short clip (`camera.record`) alongside the
  snapshot burst; store under `<config>/ai_camera_centre/clips/`, serve it,
  prune on the retention schedule, offer playback on the card (reuse the
  lightbox) and attach the clip URL to the notification. Add a toggle +
  clip-length setting (recording adds load/storage). Needs live testing.
- **Tests** — _initial suite landed_: `tests/` covers the store, the
  motion-ignore processing gate, the config/options flows, and the
  known-photo upload endpoint + websocket commands, run in CI on every push
  (`validate.yml` pytest job, Python 3.13). Still to expand: the full
  analyze pipeline with a mocked `ai_task`, and the camera/visitor subentry
  flows.
- **Translations** — strings are translation-ready; add other languages
  once the text stabilises.
- **Signed image URLs for snapshots + known photos** — extend the 2.7.0
  signed-URL scheme (currently alert images only) to the burst snapshots and
  known-visitor reference photos, removing the remaining capability-URL
  surfaces. See SECURITY.md "Network surface".
- **HACS default store** — after the repo description/topics are set,
  releases are published, and brand handling is confirmed, submit to the
  HACS default list (see README "Releasing").
- **Auto-inherit refinements / notification actions** — e.g. an
  acknowledge/dismiss action; per-camera notify overrides — as requested.
