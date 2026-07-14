# Security Policy

## Supported Versions

Only the latest release receives security fixes. There is no long-term
support for older versions — update via HACS.

| Version        | Supported |
| -------------- | --------- |
| latest release | ✅        |
| anything older | ❌        |

## Reporting a Vulnerability

Please **do not** open a public issue for security problems.

- Preferred: GitHub **private vulnerability reporting** — this repository's
  *Security* tab → *Report a vulnerability*.
- You should get an initial response within a few days. Confirmed issues
  are fixed in the next release and credited in the changelog unless you
  ask otherwise.

## Security model

What this integration touches, and the choices behind it:

### Data & privacy

- Alert reports and images are stored **locally** in
  `<config>/ai_camera_centre/` (JSONL log + JPEGs). Nothing is sent to any
  service run by this project — there is no telemetry.
- **Camera snapshots are sent to the AI provider you configure** for
  `ai_task` (e.g. Google, OpenAI, or a local Ollama). If that matters for
  your privacy posture, use a local provider. Known-visitor descriptions
  and per-camera scene context are included in those prompts.
- Diagnostics downloads contain configuration and runtime state only — no
  credentials (the integration stores none).

### Network surface

- **Alert images, burst snapshots and the Lovelace card are served on
  unauthenticated static paths** (`/ai_camera_centre/images/…`,
  `/ai_camera_centre/snapshots/…`, like Home Assistant's own `/local/`).
  This is required so dashboard `<img>` tags and mobile notifications can
  load them (neither can attach auth tokens). Mitigation: filenames carry
  a cryptographically random token (capability URLs), so images cannot be
  enumerated or guessed — but anyone who obtains a full URL can fetch that
  image without logging in. Treat alert-image URLs as sensitive, and don't
  expose your Home Assistant port to the internet without additional
  protection.
- The card's data feed (`ai_camera_centre/alerts` websocket command) and
  all services require Home Assistant **authentication**. Any authenticated
  user can view alert history and call `analyze`/`log_alert`.
- `log_alert`'s `image_path` is restricted to the integration's own storage
  directory or paths in `allowlist_external_dirs` — arbitrary files on the
  host cannot be published.
- The media source (`media-source://ai_camera_centre/…`) validates resolved
  paths stay inside the storage directory (no path traversal).

### Actions

- The **"Sound alarm"** notification button (and the automatic Alarmo
  trigger) can only *trip* the alarm — nothing in this integration can
  disarm it. The underlying `mobile_app_notification_action` event could be
  fired by any authenticated user; the worst outcome is a false alarm
  ("fail loud").

### Accepted / low risks

- AI output (alert summaries, `known_person`) is fed back into later
  prompts as recent-activity context. A subject visible on camera cannot
  meaningfully inject instructions this way, but AI-generated text is
  treated as data, not trusted input, everywhere else (escaped in the card,
  never executed).
- Alert content is rendered in the bundled card with HTML escaping on every
  field.

## Hardening roadmap

- Signed, expiring URLs for alert images (would replace the
  capability-URL scheme; needs frontend/notification support).
