"""Constants for the Alert History integration."""

DOMAIN = "alert_history"
VERSION = "1.0.0"

CONF_RETENTION_DAYS = "retention_days"
DEFAULT_RETENTION_DAYS = 7

STORAGE_DIR = "alert_history"  # created under the HA config directory

IMAGES_URL = f"/{DOMAIN}/images"
CARD_URL = f"/{DOMAIN}/alert-history-card.js"

SIGNAL_NEW_ALERT = f"{DOMAIN}_new_alert"
