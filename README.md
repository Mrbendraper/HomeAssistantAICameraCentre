# AI Camera Centre

A self-contained Home Assistant custom integration (HACS-compatible) that
turns your cameras into an AI-powered alerting system — no YAML scripts or
automations required.

Point it at a camera stream and a motion sensor, and AI Camera Centre does
the rest: on motion it captures a burst of snapshots, sends them to your AI
provider for analysis (what caused the motion, direction of travel, what
they're carrying, a 1–10 suspicion score), archives the alert with its image,
notifies your phone, and shows everything on a bundled Lovelace timeline
card.

## Features

- **Built-in analysis pipeline** — configure cameras entirely in the UI:
  camera entity, motion sensor, and an optional per-camera scene description
  that is injected into the AI prompt (e.g. "a gate is visible; subjects
  behind the gate are likely arriving").
- **AI-powered reports** via Home Assistant's `ai_task` — works with any
  configured AI provider (Google Generative AI, OpenAI, Ollama, ...).
  Each alert includes a short notification line, detailed description,
  direction of travel, activity, carried items, gate state/risk, and a
  1–10 suspicion score.
- **Mobile notifications** with the alert image and a tap-through to your
  dashboard; a configurable minimum score filters out benign events.
- **Bundled timeline card** — rolling history grouped by day, camera filter
  chips, score badges, tap to expand the full image and report. Served by
  the integration and auto-registered as a dashboard resource.
- **Automatic retention** — alerts and images older than N days (default 7)
  are pruned automatically.
- **Per-camera sensors** — `sensor.<camera>_alerts_24h` with last-alert
  details as attributes, for use in your own automations.
- **Services** — `ai_camera_centre.analyze` triggers the pipeline on demand;
  `ai_camera_centre.log_alert` lets advanced users log alerts from their own
  scripts into the same history.

## Requirements

- Home Assistant 2025.8 or newer
- An AI provider configured for **AI Tasks** (Settings → Devices & Services,
  e.g. Google Generative AI or OpenAI, then set it as the default AI Task
  entity or pick one in this integration's settings)
- A camera entity per camera, and ideally a motion `binary_sensor` per
  camera to trigger analysis

## Installation

### HACS (custom repository)

1. HACS → ⋮ → Custom repositories
2. Repository: `https://github.com/Mrbendraper/HomeAssistantAICameraCentre`,
   type: **Integration**
3. Install **AI Camera Centre**, restart Home Assistant

### Manual

Copy `custom_components/ai_camera_centre/` into your
`config/custom_components/` folder and restart.

## Setup

1. Settings → Devices & Services → Add Integration → **AI Camera Centre**
2. Fill in the global settings — most importantly **Notify services**
   (e.g. `notify.mobile_app_your_phone`; comma-separate several).
3. Open the integration's **Configure** button → **Add a camera**:
   - **Camera name** — e.g. "Side Gate"
   - **Camera stream entity** — the `camera.*` entity to snapshot
   - **Motion sensor** — the `binary_sensor.*` that should trigger analysis
     (optional; leave blank to trigger only via the `analyze` service)
   - **Scene context** — optional but recommended: describe what the camera
     sees and state explicitly whether a gate is visible
4. Repeat for each camera. That's it — walk in front of a camera to test, or
   call the service manually:

```yaml
action: ai_camera_centre.analyze
data:
  camera_id: side_gate
```

### Card

```yaml
type: custom:ai-camera-centre-card
title: Camera Alerts
days: 7
```

If auto-registration of the resource fails (e.g. YAML-mode dashboards), add
it manually: Settings → Dashboards → Resources → Add →
URL `/ai_camera_centre/ai-camera-centre-card.js`, type **JavaScript module**.

### Sensors

`sensor.<camera_label>_alerts_24h` — state is the alert count in the last
24 hours; attributes include `last_alert`, `last_score`, `last_short`,
`last_image`, and `max_score_24h`.

## How the pipeline works

1. Motion sensor turns `on` (per-camera cooldown prevents alert storms)
2. A burst of snapshots is captured from the camera stream (count and
   interval configurable; default 5 shots, 500 ms apart)
3. The frames go to `ai_task.generate_data` with a structured prompt plus
   your per-camera scene context; the AI compares frames to determine what
   moved, in which direction, and how suspicious it looks (1–10)
4. "No obvious motion" results are dropped; real alerts are archived
   (image + full report) and shown on the card
5. If the score meets your notification threshold, every configured notify
   service gets the summary, the image, and a tap-through to your dashboard

Storage lives in `<config>/ai_camera_centre/` (JSONL log + images). Data
from the previous *Alert History* version of this integration is migrated
automatically on first start.

## Advanced: bring your own pipeline

If you want full control of the prompt or flow, you can keep running your
own script/automation and log results into the same history and card with
`ai_camera_centre.log_alert` — see
[`examples/camera_alert_script.yaml`](examples/camera_alert_script.yaml).

## Upgrading from Alert History (v1.x)

The integration was renamed (`alert_history` → `ai_camera_centre`) in v2.0:

1. Remove the old *Alert History* integration entry and the
   `custom_components/alert_history/` folder
2. Install AI Camera Centre and add the integration
3. Stored alerts/images are migrated automatically; dashboards using
   `custom:alert-history-card` keep working (the old card name is aliased),
   but new dashboards should use `custom:ai-camera-centre-card`

## Releasing (maintainers)

1. Bump `version` in `custom_components/ai_camera_centre/manifest.json` and
   `VERSION` in `const.py` (keep them in sync)
2. Commit, tag `vX.Y.Z`, push with tags
3. Create a GitHub release from the tag — HACS offers the new version
