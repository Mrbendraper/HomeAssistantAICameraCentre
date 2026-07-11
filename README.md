# Alert History

A Home Assistant custom integration (HACS-compatible) that turns one-off AI
camera alerts into a browsable, multi-camera alert history — with a bundled
Lovelace timeline card.

Point-in-time AI camera notifications are useful, but they vanish. This
integration persists each alert (image + full AI report), serves them to a
timeline card you can filter by camera and day, prunes old alerts
automatically, and exposes per-camera 24h sensors for use in other
automations.

## Features

- `alert_history.log_alert` service — one call archives the alert image and
  report. Returns the archived image URL for use in your notification.
- Bundled `alert-history-card` Lovelace card — rolling timeline grouped by
  day, camera filter chips, score badges, tap to expand full image + report.
  The card is served by the integration and auto-registered as a dashboard
  resource (manual fallback documented below).
- Automatic retention — records and images older than N days (default 7,
  configurable in the integration options) are pruned automatically.
- Dynamic sensors — `sensor.<camera>_alerts_24h` per camera with last alert
  details as attributes, created automatically the first time a camera logs.
- Storage in `<config>/alert_history/` (JSONL log + images), served
  authenticated-free at `/alert_history/images/...` for notifications.

## Installation

### HACS (custom repository)

1. HACS → ⋮ → Custom repositories
2. Repository: this repo's GitHub URL, type: **Integration**
3. Install **Alert History**, restart Home Assistant
4. Settings → Devices & Services → Add Integration → **Alert History**

### Manual

Copy `custom_components/alert_history/` into your `config/custom_components/`
folder, restart, then add the integration.

## Usage

Your camera automation/script does its snapshot burst and AI analysis as
before, then logs the alert with one service call:

```yaml
- action: alert_history.log_alert
  response_variable: logged
  data:
    camera_id: side_gate
    camera_label: Side Gate
    image_path: /config/www/snapshots/side_gate_3.jpg
    score: "{{ ai_suspicious | int }}"
    short: "{{ ai_short }}"
    detail: "{{ ai_detail }}"
    direction: "{{ ai_direction }}"
    carrying: "{{ ai_carrying }}"
    activity: "{{ ai_activity }}"
    gate_state: "{{ ai_gate_state }}"
    gate_risk: "{{ ai_gate_risk }}"

- action: notify.mobile_app_your_phone
  data:
    title: "Side Gate Motion [{{ ai_suspicious }}/10]"
    message: "{{ ai_short }}"
    data:
      image: "{{ logged.image_url }}"
      clickAction: /lovelace/alerts
```

A complete example script (5-shot burst, AI task, notification) covering
multiple cameras with one shared script is in
[`examples/camera_alert_script.yaml`](examples/camera_alert_script.yaml).

### Card

```yaml
type: custom:alert-history-card
title: Camera Alerts
days: 7
```

If auto-registration of the resource fails (e.g. YAML-mode dashboards), add
it manually: Settings → Dashboards → Resources → Add →
URL `/alert_history/alert-history-card.js`, type **JavaScript module**.

### Sensors

`sensor.<camera_label>_alerts_24h` — state is the alert count in the last
24 hours; attributes include `last_alert`, `last_score`, `last_short`,
`last_image`, and `max_score_24h`.

## Releasing (maintainers)

1. Bump `version` in `custom_components/alert_history/manifest.json` and
   `VERSION` in `const.py` (keep them in sync)
2. Commit, tag `vX.Y.Z`, push with tags
3. Create a GitHub release from the tag — HACS offers the new version

## Requirements

- Home Assistant 2024.7+
- An AI provider configured for `ai_task` (for the example script)
