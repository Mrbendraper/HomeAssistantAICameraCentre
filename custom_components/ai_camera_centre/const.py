"""Constants for the AI Camera Centre integration."""

DOMAIN = "ai_camera_centre"
VERSION = "2.5.1"

# subentry types
SUBENTRY_CAMERA = "camera"
SUBENTRY_TARGET = "alert_target"
SUBENTRY_KNOWN_VISITOR = "known_visitor"

# how recent an alert must be for the per-camera binary sensor to read "on"
RECENT_ALERT_MINUTES = 5

# -- global options ------------------------------------------------------
CONF_RETENTION_DAYS = "retention_days"
CONF_SNAPSHOT_COUNT = "snapshot_count"
CONF_SNAPSHOT_INTERVAL_MS = "snapshot_interval_ms"
CONF_COOLDOWN_SECONDS = "cooldown_seconds"
CONF_DASHBOARD_PATH = "dashboard_path"
CONF_AI_TASK_ENTITY = "ai_task_entity"
CONF_ALARM_PANEL_ENTITY = "alarm_panel_entity"
# alarmo integration
CONF_ALARMO_ENABLED = "alarmo_enabled"
CONF_ALARMO_TRIGGER_SCORE = "alarmo_trigger_score"
# selective logging
CONF_MIN_LOG_SCORE = "min_log_score"
CONF_LOG_WINDOW_START = "log_window_start"
CONF_LOG_WINDOW_END = "log_window_end"
# repeat-visitor context
CONF_REPEAT_CONTEXT_MINUTES = "repeat_context_minutes"

DEFAULT_RETENTION_DAYS = 7
DEFAULT_SNAPSHOT_COUNT = 5
DEFAULT_SNAPSHOT_INTERVAL_MS = 500
DEFAULT_COOLDOWN_SECONDS = 30
DEFAULT_DASHBOARD_PATH = "/lovelace/alerts"
DEFAULT_REPEAT_CONTEXT_MINUTES = 15  # 0 = disabled
DEFAULT_ALARMO_TRIGGER_SCORE = 9
DEFAULT_MIN_LOG_SCORE = 1

# score at/above which notifications use the high-priority channel
NOTIFY_HIGH_SCORE = 7

# mobile_app notification action id for the "Sound alarm" button
ACTION_SOUND_ALARM = "ACC_SOUND_ALARM"

# alarm_control_panel states treated as "armed"
ARMED_STATES = frozenset(
    {
        "armed_home",
        "armed_away",
        "armed_night",
        "armed_vacation",
        "armed_custom_bypass",
    }
)

# notify_condition values (per alert target)
NOTIFY_ALWAYS = "always"
NOTIFY_AWAY = "away"
NOTIFY_ARMED = "armed"
NOTIFY_AWAY_OR_ARMED = "away_or_armed"
DEFAULT_TARGET_CONDITION = NOTIFY_ALWAYS

# -- per-camera subentry data --------------------------------------------
CONF_CAMERA_ID = "camera_id"  # stable slug; storage/record identity
CONF_CAMERA_NAME = "name"
CONF_CAMERA_ENTITY = "camera_entity"
CONF_MOTION_ENTITIES = "motion_entities"
CONF_SCENE_CONTEXT = "scene_context"

# -- known visitor subentry data -----------------------------------------
CONF_VISITOR_NAME = "name"
CONF_VISITOR_DESCRIPTION = "description"

# -- alert target subentry data ------------------------------------------
CONF_TARGET_NAME = "name"  # optional friendly name; derived if blank
CONF_TARGET_SERVICE = "service"
CONF_TARGET_MIN_SCORE = "min_score"
CONF_TARGET_CAMERAS = "cameras"  # camera ids; empty list = all cameras
CONF_TARGET_CONDITION = "notify_condition"

# -- storage / urls ------------------------------------------------------
STORAGE_DIR = "ai_camera_centre"  # created under the HA config directory

IMAGES_URL = f"/{DOMAIN}/images"
SNAPSHOTS_URL = f"/{DOMAIN}/snapshots"
CARD_URL = f"/{DOMAIN}/ai-camera-centre-card.js"

SIGNAL_NEW_ALERT = f"{DOMAIN}_new_alert"

# fired on the HA event bus for every alert (logged or not) so users can
# build their own automations
EVENT_ALERT = f"{DOMAIN}_alert"
