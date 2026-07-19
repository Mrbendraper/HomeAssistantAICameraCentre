# Changelog

All notable changes to AI Camera Centre. Versions follow the
`custom_components/ai_camera_centre/manifest.json` `version`.

## [2.6.0]

### Added
- **Motion-ignore processing rules** — skip AI analysis entirely (no snapshot
  burst, no AI call, no notification) based on three factors that must all
  agree: **presence** (process always / only when nobody home / only when
  someone home), **alarm state** (always / only armed / only disarmed) and
  **time** (any time / between two times / daytime only / nighttime only,
  where day/night follows a sun entity, default `sun.sun`). Configured as a
  house-wide default in Settings, with a per-camera **motion processing
  policy** that either follows the house or sets its own rules. The manual
  *Analyze now* button and the `analyze` service always bypass these rules.
  This is separate from the existing notify conditions (who gets pushed) and
  log window (what gets archived); it gates whether the pipeline runs at all,
  to save AI cost.
- **Reference photos for known people** — upload one or more photos per known
  visitor via the new **AI Camera Centre People** card
  (`custom:ai-camera-centre-people-card`). Photos are attached to the AI
  prompt so the model can visually recognise household members and regulars
  (in addition to the existing text description) and record the matched name.
  Uploads go through an authenticated, admin-only endpoint and are normalised
  to a bounded JPEG; they are stored under
  `<config>/ai_camera_centre/known/<visitor_id>/` and are not age-pruned.
- **AI response style / personality** — an optional global free-text override
  (e.g. "in the style of Samuel L. Jackson") that shapes the wording of the
  short and detailed alert text. It is explicitly constrained to wording only
  and never changes the suspicion score or any factual field.

### Security
- The known-photo upload endpoint no longer echoes internal exception detail
  in its HTTP error response; failures return a generic message and the detail
  is logged server-side instead (CodeQL: information exposure through an
  exception).
- The `validate` GitHub workflow now declares an explicit least-privilege
  `permissions: contents: read` (CodeQL: workflow does not contain
  permissions).

## [2.5.1]

### Security
- Burst snapshots used fixed, predictable filenames on an unauthenticated
  static path, allowing anyone who could reach the Home Assistant port to
  poll near-live camera frames without logging in. Snapshot and archived
  image filenames now carry a cryptographically random token (capability
  URLs), and each run's snapshots replace the previous run's.
- `log_alert`'s `image_path` is now restricted to the integration's storage
  directory or `allowlist_external_dirs`, so arbitrary host files can no
  longer be copied into the publicly served images directory.

### Added
- A real [SECURITY.md](SECURITY.md): private vulnerability reporting,
  supported versions, and the integration's security model.

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
