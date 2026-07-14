# Roadmap

## Shipped

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
- **Live card updates** — push new alerts to the Lovelace card over a
  websocket subscription instead of the current 5-minute poll.
- **Tests** — pytest-homeassistant-custom-component coverage for the store,
  pipeline (mocked `ai_task`), and config/subentry flows. Would catch the
  import/logic errors that currently only surface on a live HA.
- **Translations** — strings are translation-ready; add other languages
  once the text stabilises.
- **Signed image URLs** — replace the capability-URL scheme (random
  filenames on unauthenticated static paths) with signed, expiring URLs
  (`http.async_sign_path`) for alert images; the card would fetch signed
  URLs over the websocket, and notifications would embed a signed URL.
  See SECURITY.md "Network surface".
- **HACS default store** — after the repo description/topics are set,
  releases are published, and brand handling is confirmed, submit to the
  HACS default list (see README "Releasing").
- **Auto-inherit refinements / notification actions** — e.g. an
  acknowledge/dismiss action; per-camera notify overrides — as requested.
