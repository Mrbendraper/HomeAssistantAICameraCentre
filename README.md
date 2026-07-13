<img src="assets/logo-wide.png" alt="AI Camera Centre" width="490">

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

- **A device per camera** — each camera you add appears as its own device
  in Home Assistant with its own entities (see below), added straight from
  the integration page with a native **Add camera** button.
- **Built-in analysis pipeline** — configure cameras entirely in the UI:
  camera entity, one or more motion triggers, and an optional per-camera
  scene description that is injected into the AI prompt (e.g. "a gate is
  visible; subjects behind the gate are likely arriving").
- **Alert targets** — add notify services the same way you add cameras
  (their own **Add alert target** button). Each target has its own minimum
  suspicion score, an optional camera filter, and a **notify condition**
  (always / only when nobody's home / only when the alarm is armed /
  away-or-armed), so one phone can get every event while another is only
  woken for high-risk alerts when you're out.
- **Alarmo integration** — optionally trip
  [Alarmo](https://github.com/nielsfaber/alarmo) when a high-risk alert
  lands while the alarm is already armed, so the AI can sound the siren,
  not just ping a phone.
- **Selective logging** — keep the history clean: only archive alerts at or
  above a minimum score, and/or only during a chosen time window (e.g.
  nighttime only).
- **AI-powered reports** via Home Assistant's `ai_task` — works with any
  configured AI provider (Google Generative AI, OpenAI, Ollama, ...).
  Each alert includes a short notification line, detailed description,
  direction of travel, activity, carried items, gate state/risk, and a
  1–10 suspicion score.
- **Mobile notifications** with the alert image and a tap-through to your
  dashboard.
- **Bundled timeline card** — rolling history grouped by day, camera filter
  chips, score badges, tap to expand the full image and report. Served by
  the integration and auto-registered as a dashboard resource.
- **Automatic retention** — alerts and images older than N days (default 7)
  are pruned automatically.
- **Per-camera entities** — every camera device carries: an *Alerts (24h)*
  count sensor, a *Last score* sensor, a *Recent alert* binary sensor, a
  *Latest alert* image, an *Analysis* switch to pause/resume that camera,
  and an *Analyze now* button. Use them on dashboards and in your own
  automations.
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
2. Repository: `https://github.com/simpleaddins/HomeAssistantAICameraCentre`,
   type: **Integration**
3. Install **AI Camera Centre**, restart Home Assistant

### Manual

Copy `custom_components/ai_camera_centre/` into your
`config/custom_components/` folder and restart.

## Setup

1. Settings → Devices & Services → Add Integration → **AI Camera Centre**
   and fill in the global settings.
2. On the integration page, click **Add camera** (a native "+" button, not
   the Configure menu):
   - **Camera name** — e.g. "Side Gate"
   - **Camera stream entity** — the `camera.*` entity to snapshot
   - **Motion triggers** — one or more entities (`binary_sensor`,
     `input_boolean` or `switch`); any of them turning on starts the
     analysis (optional; leave blank to trigger only via the `analyze`
     service or the camera's *Analyze now* button)
   - **Scene context** — optional but recommended: describe what the camera
     sees and state explicitly whether a gate is visible

   Each camera you add becomes its own **device** with its entities.
3. On the same page, click **Add alert target**:
   - **Notify service** — pick from the dropdown
     (e.g. `notify.mobile_app_your_phone`)
   - **Minimum suspicion score** — 1 sends every alert; 6+ only wakes this
     target for genuinely suspicious events
   - **When to notify** — always, or only when nobody's home / the alarm is
     armed / either (the armed options need an alarm panel set in Settings)
   - **Cameras** — optionally restrict this target to specific cameras
4. Optional, in the integration's **Configure** button (global **Settings**):
   - **Alarm panel** — pick your `alarm_control_panel.*` to enable the armed
     notify conditions and Alarmo triggering
   - **Minimum score to log** / **log time window** — keep low-risk or
     daytime noise out of the history
   - **Trigger Alarmo** — sound Alarmo on high-risk alerts while armed
5. Repeat for each camera and target. That's it — walk in front of a camera
   to test, use its *Analyze now* button, or call the service manually:

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

### Entities per camera

Each camera device exposes:

| Entity | What it does |
| --- | --- |
| `sensor.<camera>_alerts_24h` | Alert count in the last 24 h; attributes `last_alert`, `last_score`, `last_short`, `last_image`, `max_score_24h` |
| `sensor.<camera>_last_score` | Suspicion score (1–10) of the most recent alert |
| `binary_sensor.<camera>_recent_alert` | On for a few minutes after each alert |
| `image.<camera>_latest_alert` | The latest alert snapshot (drop onto a dashboard) |
| `switch.<camera>_analysis` | Turn a camera's automatic analysis off/on (holiday mode, gardener day). The *Analyze now* button and service still work while off |
| `button.<camera>_analyze` | Run an analysis on demand |

## How the pipeline works

1. Any of the camera's motion triggers turns `on` (per-camera cooldown
   prevents alert storms)
2. A burst of snapshots is captured from the camera stream (count and
   interval configurable; default 5 shots, 500 ms apart)
3. The frames go to `ai_task.generate_data` with a structured prompt plus
   your per-camera scene context; the AI compares frames to determine what
   moved, in which direction, and how suspicious it looks (1–10)
4. "No obvious motion" results are dropped. Remaining alerts are checked
   against the logging rules (minimum score + optional time window); alerts
   that pass are archived (image + full report) and shown on the card
5. If Alarmo triggering is enabled and the score meets the threshold while
   the panel is armed, Alarmo is tripped
6. Every alert target whose minimum score, camera filter and notify
   condition (presence / armed state) all match gets the summary, the
   image, and a tap-through to your dashboard

Notes on the filters — the logging rules and the notification rules are
independent, by design:

- The **logging rules** (minimum score to log, time window) decide only
  what enters the **history and the card**. An alert filtered out here is
  *not* archived, but it can still notify and trigger Alarmo — so a genuine
  threat is never silently dropped just because it fell outside your
  "nighttime only" logging window. Its notification simply uses the
  temporary snapshot image rather than an archived one.
- The **notification rules** (each target's minimum score, camera filter
  and notify condition) decide who gets pushed. So you can, for example,
  keep your history to nighttime events only while still being notified of
  daytime threats when you're away.
- "Nobody home" is true when no `person.*` entity is in the `home` zone; if
  you have no person entities at all it is treated as away (fail open).

Storage lives in `<config>/ai_camera_centre/` (a JSONL log plus images).

## Advanced: bring your own pipeline

If you want full control of the prompt or flow, you can keep running your
own script/automation and log results into the same history and card with
`ai_camera_centre.log_alert` — see
[`examples/camera_alert_script.yaml`](examples/camera_alert_script.yaml).

## Troubleshooting

**"Custom element doesn't exist: ai-camera-centre-card"** — the card's
JavaScript isn't reaching your browser. Check, in order:

1. *Is the integration serving it?* Open
   `http://<ha-address>:8123/ai_camera_centre/ai-camera-centre-card.js` —
   you should see JavaScript. A 404 means the integration isn't set up or
   an old version is installed (HACS → Redownload, restart, and make sure
   the integration entry exists under Devices & Services).
2. *Is the resource registered?* Settings → Dashboards → ⋮ → Resources
   (requires "Advanced mode" on your profile). There should be an entry for
   `/ai_camera_centre/ai-camera-centre-card.js`; add it manually as a
   **JavaScript module** if missing, and delete any stale
   `/alert_history/...` entry.
3. *Clear the frontend cache* — this is the usual culprit. Hard-refresh the
   browser (Ctrl+F5); in the companion app: Settings → Companion App →
   Debugging → **Reset frontend cache**.

**No alerts are generated** — check Settings → System → Logs for
`ai_camera_centre` errors. The most common cause is no AI Task provider:
you need one configured (e.g. Google Generative AI or OpenAI) and either
set as the default AI Task entity or selected in this integration's
Settings.

**Notifications don't arrive** — verify the alert target's minimum score
isn't filtering the alert out, and that its camera filter (if any) includes
the camera. Each delivery failure is logged.

**No integration icon** — the icon ships inside the integration
(`custom_components/ai_camera_centre/brand/`) and is picked up
automatically on Home Assistant **2026.3 or newer**; older versions show
the default placeholder. If you're on 2026.3+ and still see the
placeholder, hard-refresh the browser / reset the companion app's
frontend cache. Details in [docs/BRANDING.md](docs/BRANDING.md).

## Upgrading

Update via HACS and restart. **2.3 is a fresh-config release**: cameras and
alert targets are now config *subentries* (each its own device / native add
button), and there is no automatic migration from the earlier development
layout — if you are coming from a pre-2.3 build, remove and re-add the
integration, then add your cameras and targets again. Stored alert history
in `<config>/ai_camera_centre/` is unaffected. Dashboards using
`custom:alert-history-card` (the pre-2.0 card name) keep working via an
alias, but new dashboards should use `custom:ai-camera-centre-card`.

## Releasing (maintainers)

1. Bump `version` in `custom_components/ai_camera_centre/manifest.json` and
   `VERSION` in `const.py` (keep them in sync)
2. Commit, tag `vX.Y.Z`, push with tags
3. Create a GitHub release from the tag — HACS offers the new version

Brand assets (integration icon/logo) are documented in
[docs/BRANDING.md](docs/BRANDING.md).

## Roadmap

Planned features not yet built are tracked in [TODO.md](TODO.md).
