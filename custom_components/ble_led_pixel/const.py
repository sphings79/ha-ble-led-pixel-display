"""Constants for the BLE LED Pixel Display integration."""

DOMAIN = "ble_led_pixel"

# Every loaded panel's Message entity, which carries the panel actions.
DATA_PANEL_ENTITIES = f"{DOMAIN}_panel_entities"
DEFAULT_NAME = "LED Pixel Display"

# Bluetooth UUIDs from protocol documentation
WRITE_UUID = "0000fa02-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fa03-0000-1000-8000-00805f9b34fb"
CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"

# Device discovery
# The vendor app looks for this anywhere in the name, not as a prefix and
# without a trailing underscore -- so a panel called LED_BLE1234, or one
# carrying a brand prefix, is found by the app. Matching the app rather
# than being stricter than it.
DEVICE_NAME_MARKER = "LED_BLE"

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
# Offer the vertical scroll effects (codes 3 and 4) on panels that are not
# 32x32. Off by default -- see VERTICAL_TEXT_EFFECTS.
OPT_VERTICAL_SCROLL = "vertical_scroll"
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
# Codes 3 and 4 (scroll up/down) are kept apart in VERTICAL_TEXT_EFFECTS below
# and only offered where they are known or chosen to be safe.
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

# Codes 3 and 4 scroll the text up and down. pypixelcolor refuses them on
# anything but a 32x32 panel, warning that they can boot-loop a device, but
# that check only runs when it is handed the panel's dimensions, which this
# integration does not do. They work on at least a 64x20 panel (Type 133), so
# they are offered on 32x32 panels and, as an opt-in in the options, on others.
VERTICAL_TEXT_EFFECTS: dict[str, int] = {
    "Scroll up": 3,
    "Scroll down": 4,
}

ALL_TEXT_EFFECTS: dict[str, int] = dict(
    sorted({**TEXT_EFFECTS, **VERTICAL_TEXT_EFFECTS}.items(), key=lambda item: item[1])
)


def text_effects(vertical: bool) -> dict[str, int]:
    """The effects to offer, in code order, with or without vertical scroll."""
    return dict(ALL_TEXT_EFFECTS) if vertical else dict(TEXT_EFFECTS)


TEXT_EFFECT_CODES: dict[int, str] = {code: name for name, code in ALL_TEXT_EFFECTS.items()}

DEFAULT_TEXT_EFFECT = "Fixed"


# Text gradients ("rainbow mode"), by code.
#
# The vendor app names these only GRADIENT_COLOR_01 to _08, so the wording
# here is ours -- but not invented: each label describes the actual colour
# ramp, read out of GradientColor.kt and measured. The gradient number is kept
# in the label so nobody has to trust our adjectives.
#
# Codes 0 and 1 both mean off. The app's gradient switch has no case for
# either, so they fall through and the text keeps its solid colour.
#
# One caveat worth knowing: the ramps were read from the app's own rendering
# path, which it uses for image-mode text. The code sent here is rendered by
# the panel's firmware instead. The numbering lines up exactly -- eight
# gradients at codes 2 to 9 in both -- so they are almost certainly the same
# set, but that correspondence is inferred, not proven.
TEXT_GRADIENTS: dict[str, int] = {
    "Off": 0,
    "1 - Spectrum": 2,
    "2 - Navy to blush": 3,
    "3 - Cyan to gold": 4,
    "4 - Blue to cyan": 5,
    "5 - Spectrum, vivid": 6,
    "6 - Colour wheel, 16 steps": 7,
    "7 - Warm wheel, 16 steps": 8,
    "8 - Warm wheel, wide": 9,
}

DEFAULT_TEXT_GRADIENT = "Off"

# Text mode is drawn by the panel's firmware in whole 16px rows, so these are
# the only character heights that differ. Taller than the panel is useless.
TEXT_SIZES: tuple[int, ...] = (16, 32, 48, 64)
DEFAULT_TEXT_SIZE = 16


def text_sizes_for_height(height: int | None) -> list[int]:
    """Text sizes that fit a panel of this height; all of them if unknown."""
    if not height:
        return list(TEXT_SIZES)
    return [size for size in TEXT_SIZES if size <= height] or [DEFAULT_TEXT_SIZE]


def text_size_from_font_size(font_size: float | None) -> int:
    """The text size the old Font Size number amounted to in text mode."""
    if not font_size or font_size < DEFAULT_TEXT_SIZE:
        return DEFAULT_TEXT_SIZE
    return min(int(font_size // 16) * 16, TEXT_SIZES[-1])
