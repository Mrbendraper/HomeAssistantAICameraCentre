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

- **Archived alert images use signed, expiring URLs.** They are served
  behind an authenticated endpoint (`/ai_camera_centre/images/…`,
  `requires_auth`); the card `<img>`, mobile notifications and the
  `ai_camera_centre_alert` event are handed **signed URLs** (`?authSig=…`,
  via `async_sign_path` with Home Assistant's content-user token) so they
  load without a bearer token, while an unsigned request is rejected (401).
  The signature expires with the retention window and is revocable by
  rotating Home Assistant's sign secret, so a leaked link is bounded in time
  rather than usable forever.
- **Burst snapshots and known-visitor photos are still served on
  unauthenticated static paths** (`/ai_camera_centre/snapshots/…`,
  `/ai_camera_centre/known/…`, like Home Assistant's own `/local/`).
  Mitigation: filenames carry a cryptographically random token (capability
  URLs), so they cannot be enumerated or guessed — but anyone who obtains a
  full URL can fetch that file without logging in. Snapshots are transient
  (overwritten on the next capture); treat known-photo URLs as sensitive, and
  don't expose your Home Assistant port to the internet without additional
  protection. (Signing these too is on the roadmap.)
- The card's data feed (the `ai_camera_centre/alerts` and
  `ai_camera_centre/subscribe` websocket commands) and all services require
  Home Assistant **authentication**. Any authenticated user can view alert
  history and call `analyze`/`log_alert`.
- **Managing known people requires an admin.** Uploading a reference photo
  (`POST /api/ai_camera_centre/known_photo`), adding a visitor
  (`ai_camera_centre/add_visitor`) and deleting a visitor's photo
  (`ai_camera_centre/delete_visitor_photo`) all require authentication **and
  admin privileges** — a non-admin is rejected. Uploads are additionally
  hardened: the declared size is capped (8 MB, checked before and after
  reading), the part must declare an `image/*` content type, the target must
  be an existing visitor (no arbitrary directory creation — the `visitor_id`
  is slug-validated), and the bytes are re-encoded through Pillow to a bounded
  JPEG. That re-encode both proves the upload is a real image and **strips all
  metadata (including any EXIF GPS)** before it is stored or sent to the AI
  provider. Stored photo/visitor-photo filenames are basename-scoped and must
  end in `.jpg`, so a crafted `filename` cannot escape the visitor directory.
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

- Extend signed, expiring URLs (shipped for alert images in 2.7.0) to the
  burst snapshots and known-visitor photos, retiring the remaining
  capability-URL surfaces.
