"""Constants for the AI Camera Centre integration."""

DOMAIN = "ai_camera_centre"
VERSION = "2.1.0"

# -- global options ------------------------------------------------------
CONF_RETENTION_DAYS = "retention_days"
CONF_SNAPSHOT_COUNT = "snapshot_count"
CONF_SNAPSHOT_INTERVAL_MS = "snapshot_interval_ms"
CONF_COOLDOWN_SECONDS = "cooldown_seconds"
CONF_DASHBOARD_PATH = "dashboard_path"
CONF_AI_TASK_ENTITY = "ai_task_entity"
# legacy (pre-2.1, migrated to alert targets on setup)
CONF_MIN_NOTIFY_SCORE = "min_notify_score"
CONF_NOTIFY_SERVICES = "notify_services"

DEFAULT_RETENTION_DAYS = 7
DEFAULT_SNAPSHOT_COUNT = 5
DEFAULT_SNAPSHOT_INTERVAL_MS = 500
DEFAULT_COOLDOWN_SECONDS = 30
DEFAULT_MIN_NOTIFY_SCORE = 1
DEFAULT_DASHBOARD_PATH = "/lovelace/alerts"

# -- per-camera options --------------------------------------------------
CONF_CAMERAS = "cameras"
CONF_CAMERA_NAME = "name"
CONF_CAMERA_ENTITY = "camera_entity"
CONF_MOTION_ENTITIES = "motion_entities"
CONF_MOTION_ENTITY = "motion_entity"  # legacy single-entity key (pre-2.1)
CONF_SCENE_CONTEXT = "scene_context"

# -- alert target options --------------------------------------------------
CONF_ALERT_TARGETS = "alert_targets"
CONF_TARGET_SERVICE = "service"
CONF_TARGET_MIN_SCORE = "min_score"
CONF_TARGET_CAMERAS = "cameras"  # camera ids; empty list = all cameras

# -- storage / urls ------------------------------------------------------
STORAGE_DIR = "ai_camera_centre"  # created under the HA config directory
LEGACY_STORAGE_DIR = "alert_history"  # migrated on first start
LEGACY_IMAGES_URL = "/alert_history/images"

IMAGES_URL = f"/{DOMAIN}/images"
SNAPSHOTS_URL = f"/{DOMAIN}/snapshots"
CARD_URL = f"/{DOMAIN}/ai-camera-centre-card.js"

SIGNAL_NEW_ALERT = f"{DOMAIN}_new_alert"
