# Changelog

All notable changes to AI Camera Centre. Versions follow the
`custom_components/ai_camera_centre/manifest.json` `version`.

## [2.5.0]

### Added
- **Known visitors** — add household members and regulars (name +
  description) as a new *Known visitor* entry on the integration page. Their
  descriptions are added to every camera's AI prompt so recognised people
  are scored low; the recognised name is stored on the alert (`known_person`),
  the `ai_camera_centre_alert` event, and the card.
- **Repeat-visitor context** — a *Recent-activity context window* setting
  (default 15 min, 0 disables). The camera's recent alerts are summarised
  into the prompt so the AI can flag the same subject returning or loitering
  and raise the score.

## [2.4.0]

### Added
- **Card lightbox** — tap the expanded alert image for a full-screen view.
- **Notification channels** — alerts scoring 7+ use a separate
  high-importance Android channel (can ring through Do Not Disturb) and the
  iOS time-sensitive level; a **Sound alarm** action button (when an alarm
  panel is set) trips Alarmo.
- **Camera area auto-inherit** — camera devices are placed in their source
  camera entity's area on setup (only when unset).
- **`ai_camera_centre_alert` event** — fired for every alert for use in
  automations.
- **Diagnostics** — downloadable config-entry diagnostics.
- **Structured AI output** — `ai_task` is called with a schema; falls back
  to prompt-and-parse JSON where structured output isn't supported.
- **CI** — hassfest + HACS validation on push/PR.

## [2.3.1]

### Changed
- Each camera is now a config **subentry** and its own **device** with six
  entities (24h count, last score, recent-alert binary sensor, latest-alert
  image, analysis switch, analyze button). Cameras and alert targets are
  added from the integration page.
- Alert targets show a friendly name.

### Fixed
- `DeviceInfo` import path (broke platform setup on 2.3.0).

## [2.2.0]

### Added
- Per-target **notify condition** (always / away / armed / away-or-armed).
- Optional **Alarmo** trigger on high-risk alerts while armed.
- **Selective logging** — minimum score and time-window filters.

## [2.1.x]

### Added
- **Alert targets** and multiple **motion triggers** per camera.
- Brand images bundled in the integration (HA 2026.3 brands proxy).

## [2.0.0]

### Changed
- Renamed from *Alert History* to **AI Camera Centre** with a self-contained
  analysis pipeline (snapshot burst → AI → log → notify) and bundled
  timeline card.
