"""Constants for the BLE LED Pixel Display integration."""

DOMAIN = "ble_led_pixel"
DEFAULT_NAME = "LED Pixel Display"

# Bluetooth UUIDs from protocol documentation
WRITE_UUID = "0000fa02-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fa03-0000-1000-8000-00805f9b34fb"
CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"

# Device discovery
DEVICE_NAME_PREFIX = "LED_BLE_"

# Configuration keys
CONF_ADDRESS = "address"
CONF_NAME = "name"

# Options keys (configurable via the integration's options flow)
# Override the dimensions reported by firmware. Some panels (notably the
# B.K. Light 32x32 sold at Action) advertise wrong dimensions (64x16) and
# only render correctly when the host sends frames at the actual size.
# 0 means "use firmware-reported value".
OPT_OVERRIDE_DIMENSIONS = "override_dimensions"
OPT_PANEL_WIDTH = "panel_width"
OPT_PANEL_HEIGHT = "panel_height"
# Turns on the presets, scoreboard, countdown and stopwatch actions for a
# panel the feature table does not know. See capabilities.py.
OPT_FORCE_FEATURES = "force_features"
# Password for a panel that was locked from the vendor app. Sent after
# every connect, because the panel forgets it when the link drops.
OPT_PASSWORD = "password"

# Update interval
SCAN_INTERVAL = 30

# Connection settings
CONNECTION_TIMEOUT = 10
RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 1  # seconds between retry attempts

# Display modes (based on pypixelcolor capabilities)
MODE_TEXT_IMAGE = "textimage"
MODE_TEXT = "text"
MODE_CLOCK = "clock"

AVAILABLE_MODES = [
    MODE_TEXT_IMAGE,
    MODE_TEXT,
    MODE_CLOCK,
]

DEFAULT_MODE = MODE_TEXT_IMAGE

# Reconnect behaviour after the BLE link drops
REDISCOVERY_ATTEMPTS = 3      # lookups after asking HA to re-scan the address
REDISCOVERY_DELAY = 2.0       # seconds between those lookups
RECONNECT_BACKOFF_START = 5   # seconds before the first retry
RECONNECT_BACKOFF_MAX = 30    # seconds; the backoff doubles up to this cap


# Text effects, by the names the vendor's own tooling uses.
#
# Codes 3 and 4 are deliberately absent. pypixelcolor refuses them on anything
# but a 32x32 panel because they can put a device into a boot loop, and no
# source names them -- offering an unnamed option that bricks some panels is
# not worth the two extra entries.
#
# The range runs to 8, not 7: every table reconstructed from captured traffic
# stopped one short, so the Laser effect was unreachable until it turned up in
# Bk-Light-AppBypass and was confirmed against the vendor app.
TEXT_EFFECTS: dict[str, int] = {
    "Fixed": 0,
    "Scroll left": 1,
    "Scroll right": 2,
    "Blinking": 5,
    "Breathing": 6,
    "Snowflake": 7,
    "Laser": 8,
}

TEXT_EFFECT_CODES: dict[int, str] = {code: name for name, code in TEXT_EFFECTS.items()}

DEFAULT_TEXT_EFFECT = "Fixed"
