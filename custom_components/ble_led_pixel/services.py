"""Service (action) registration for BLE LED Pixel Display.

Registered in async_setup() (integration-level), NOT in a platform's
async_setup_entry, per Home Assistant's own guidance:
https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-setup/

Actions registered per-config-entry/platform only exist in Home Assistant's
service registry once that specific device's config entry has finished
loading - if automations are validated before that (e.g. during startup),
they're briefly flagged as referencing an "unknown action" even though the
action becomes available moments later. Registering here instead means the
action exists immediately, regardless of whether any device has loaded yet.

Uses homeassistant.helpers.service.async_register_platform_entity_service,
which still dispatches to a named method on each entity targeted by the
service call (same func-by-name mechanism as the older
platform.async_register_entity_service), so the entity methods in text.py
are unchanged - only where and how they get registered.
"""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service

from .const import DOMAIN

ICON_ITEM_SCHEMA = vol.Schema({
    vol.Required("icon"): cv.string,
    vol.Optional("x", default=0): vol.Coerce(int),
    vol.Optional("y", default=0): vol.Coerce(int),
    vol.Optional("size"): vol.Coerce(int),
    vol.Optional("color_hex", default="ffffff"): cv.string,
    vol.Optional("blink", default=False): cv.boolean,
    vol.Optional("blink_interval_ms", default=500): vol.All(
        vol.Coerce(int), vol.Range(min=50, max=5000)
    ),
})

TEXT_ITEM_SCHEMA = vol.Schema({
    vol.Required("text"): cv.string,
    vol.Optional("x", default=0): vol.Coerce(int),
    vol.Optional("y", default=0): vol.Coerce(int),
    vol.Optional("size", default=6): vol.Coerce(float),
    vol.Optional("font"): vol.In(
        ["3x5-de", "5x5", "7x5", "Lepidos", "OpenSans-Light", "WP7xn"]
    ),
    vol.Optional("color_hex", default="ffffff"): cv.string,
    vol.Optional("wrap", default=True): cv.boolean,
    vol.Optional("align", default="left"): vol.In(["left", "right", "center"]),
    vol.Optional("scroll", default=False): cv.boolean,
    vol.Optional("line_spacing", default=1): vol.Coerce(int),
    vol.Optional("blink", default=False): cv.boolean,
    vol.Optional("blink_interval_ms", default=500): vol.All(
        vol.Coerce(int), vol.Range(min=50, max=5000)
    ),
})


def async_setup_services(hass: HomeAssistant) -> None:
    """Register all ble_led_pixel.* actions once, at integration setup."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "show_slot",
        entity_domain=Platform.TEXT,
        schema={
            vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        },
        func="async_show_slot",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "delete_slot",
        entity_domain=Platform.TEXT,
        schema={
            vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        },
        func="async_delete_slot",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "show_emoji",
        entity_domain=Platform.TEXT,
        schema={
            vol.Required("emoji"): vol.All(cv.string, vol.Length(min=1)),
            vol.Optional("bg_color", default=[0, 0, 0]): vol.All(
                vol.ExactSequence([cv.byte, cv.byte, cv.byte]), vol.Coerce(tuple)
            ),
            vol.Optional("width", default=None): vol.Any(
                None, vol.All(vol.Coerce(int), vol.Range(min=1, max=512))
            ),
            vol.Optional("height", default=None): vol.Any(
                None, vol.All(vol.Coerce(int), vol.Range(min=1, max=512))
            ),
        },
        func="async_show_emoji",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "send_mdi_icon",
        entity_domain=Platform.TEXT,
        schema={
            vol.Required("icon"): cv.string,
            vol.Optional("color", default=[255, 255, 255]): vol.All(
                vol.ExactSequence([cv.byte, cv.byte, cv.byte]), vol.Coerce(tuple)
            ),
            vol.Optional("bg_color", default=[0, 0, 0]): vol.All(
                vol.ExactSequence([cv.byte, cv.byte, cv.byte]), vol.Coerce(tuple)
            ),
            vol.Optional("scale", default=100): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=100)
            ),
            vol.Optional("save_slot", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=10)
            ),
        },
        func="async_send_mdi_icon",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "send_text",
        entity_domain=Platform.TEXT,
        schema={
            vol.Required("text"): cv.string,
            vol.Optional("color", default=[255, 255, 255]): vol.All(
                vol.ExactSequence([cv.byte, cv.byte, cv.byte]), vol.Coerce(tuple)
            ),
            vol.Optional("bg_color", default=None): vol.Any(
                None,
                vol.All(vol.ExactSequence([cv.byte, cv.byte, cv.byte]), vol.Coerce(tuple)),
            ),
            # Any font the integration can resolve: its own fonts/ folder,
            # the pypixelcolor package, or a system font path. Not a fixed
            # list, because the library's built-in font names change between
            # versions and users may add their own.
            vol.Optional("font", default="VCR_OSD_MONO"): cv.string,
            # Effect codes as documented by Pupariaa/Bk-Light-AppBypass:
            # 0 fixed, 1 scroll left, 2 scroll right, 5 blinking,
            # 6 breathing, 7 snowflake, 8 laser. 3 and 4 are rejected by the
            # library on non-32x32 panels because they can bootloop a device.
            vol.Optional("animation", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=8)
            ),
            vol.Optional("speed", default=80): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Optional("rainbow_mode", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=9)
            ),
        },
        func="async_send_text",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "send_test_pattern",
        entity_domain=Platform.TEXT,
        schema={},
        func="async_send_test_pattern",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "send_layout",
        entity_domain=Platform.TEXT,
        schema={
            vol.Optional("icon"): cv.string,
            vol.Optional("icon_x", default=0): vol.Coerce(int),
            vol.Optional("icon_y", default=0): vol.Coerce(int),
            vol.Optional("icon_size"): vol.Coerce(int),
            vol.Optional("icon_color", default=[255, 255, 255]): vol.All(
                vol.ExactSequence([cv.byte, cv.byte, cv.byte]), vol.Coerce(tuple)
            ),
            vol.Optional("icon_blink", default=False): cv.boolean,
            vol.Optional("icon_blink_interval_ms", default=500): vol.All(
                vol.Coerce(int), vol.Range(min=50, max=5000)
            ),
            vol.Optional("icons"): vol.All(
                cv.ensure_list, [ICON_ITEM_SCHEMA], vol.Length(max=4)
            ),
            vol.Optional("image_path"): cv.string,
            vol.Optional("image_x", default=0): vol.Coerce(int),
            vol.Optional("image_y", default=0): vol.Coerce(int),
            vol.Optional("image_width"): vol.Coerce(int),
            vol.Optional("image_height"): vol.Coerce(int),
            vol.Optional("text"): cv.string,
            vol.Optional("text_x", default=0): vol.Coerce(int),
            vol.Optional("text_y", default=0): vol.Coerce(int),
            vol.Optional("text_size", default=6): vol.Coerce(float),
            vol.Optional("text_font"): vol.In(
                ["3x5-de", "5x5", "7x5", "Lepidos", "OpenSans-Light", "WP7xn"]
            ),
            vol.Optional("text_color", default=[255, 255, 255]): vol.All(
                vol.ExactSequence([cv.byte, cv.byte, cv.byte]), vol.Coerce(tuple)
            ),
            vol.Optional("text_wrap", default=True): cv.boolean,
            vol.Optional("text_line_spacing", default=1): vol.Coerce(int),
            vol.Optional("text_align", default="left"): vol.In(["left", "right", "center"]),
            vol.Optional("text_scroll", default=False): cv.boolean,
            vol.Optional("text_blink", default=False): cv.boolean,
            vol.Optional("text_blink_interval_ms", default=500): vol.All(
                vol.Coerce(int), vol.Range(min=50, max=5000)
            ),
            vol.Optional("texts"): vol.All(
                cv.ensure_list, [TEXT_ITEM_SCHEMA], vol.Length(max=4)
            ),
            vol.Optional("scroll_step", default=2): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=20)
            ),
            vol.Optional("scroll_frame_ms", default=80): vol.All(
                vol.Coerce(int), vol.Range(min=20, max=1000)
            ),
            vol.Optional("scroll_gap", default=16): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=200)
            ),
            vol.Optional("bg_color", default=[0, 0, 0]): vol.All(
                vol.ExactSequence([cv.byte, cv.byte, cv.byte]), vol.Coerce(tuple)
            ),
            vol.Optional("save_slot", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=10)
            ),
        },
        func="async_send_layout",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "send_image_file",
        entity_domain=Platform.TEXT,
        schema={
            vol.Required("file_path"): cv.string,
            vol.Optional("resize_method", default="crop"): vol.In(["crop", "fit"]),
            vol.Optional("save_slot", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=10)
            ),
        },
        func="async_send_image_file",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "show_preset",
        entity_domain=Platform.TEXT,
        schema={
            vol.Required("preset"): vol.All(vol.Coerce(int), vol.Range(min=1, max=20)),
            vol.Optional("language", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
        },
        func="async_show_preset",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_scoreboard",
        entity_domain=Platform.TEXT,
        schema={
            vol.Required("home"): vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
            vol.Required("away"): vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
        },
        func="async_set_scoreboard",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_countdown",
        entity_domain=Platform.TEXT,
        schema={
            vol.Required("running"): cv.boolean,
            vol.Optional("minutes", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=99)
            ),
            vol.Optional("seconds", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=59)
            ),
        },
        func="async_set_countdown",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_stopwatch",
        entity_domain=Platform.TEXT,
        schema={vol.Required("running"): cv.boolean},
        func="async_set_stopwatch",
    )
