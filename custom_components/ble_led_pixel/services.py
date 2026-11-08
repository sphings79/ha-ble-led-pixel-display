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

from typing import Any

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import service

from .const import DOMAIN, MAX_WRITABLE_SLOT, MIN_WRITABLE_SLOT
from .exceptions import BleLedPixelConnectionError

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
        [
            "3x5-de",
            "Jersey10",
            "Lepidos",
            "Micro5",
            "OpenSans-Light",
            "PixelifySans",
            "PressStart2P",
            "Silkscreen",
            "Tiny5",
            "VT323",
            "WP7xn",
        ]
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


def _hex_frame(value: Any) -> bytes:
    """One frame as hex, spaces allowed: '05 00 08 80 01'."""
    text = "".join(str(value).split())
    if text.lower().startswith("0x"):
        text = text[2:]
    try:
        frame = bytes.fromhex(text)
    except ValueError as err:
        raise vol.Invalid(f"'{value}' is not hex bytes, e.g. '05 00 08 80 01'") from err
    if not 1 <= len(frame) <= 512:
        raise vol.Invalid("A frame is 1 to 512 bytes")
    return frame


SEND_RAW_COMMAND_SCHEMA = cv.make_entity_service_schema({
    vol.Required("frames"): vol.All(
        cv.ensure_list, [_hex_frame], vol.Length(min=1, max=10)
    ),
    vol.Optional("gap", default=0.5): vol.All(
        vol.Coerce(float), vol.Range(min=0, max=10)
    ),
    vol.Optional("listen", default=2.0): vol.All(
        vol.Coerce(float), vol.Range(min=0, max=30)
    ),
})


async def _async_send_raw_command(
    hass: HomeAssistant, call: ServiceCall
) -> dict[str, Any] | None:
    """Send frames to the targeted panels exactly as given (administrators only).

    Registered as an admin service, so Home Assistant refuses any caller that
    is not an administrator before this runs. Nothing is checked on the way to
    the panel -- the frames can set or clear its password or erase its storage
    -- which is why this is not an ordinary entity action.
    """
    if call.data.get(ATTR_ENTITY_ID) in (ENTITY_MATCH_ALL, [ENTITY_MATCH_ALL]):
        raise ServiceValidationError(
            f"{DOMAIN}.send_raw_command needs an explicit target, not 'all'."
        )
    data = service.remove_entity_service_fields(call)
    registry = er.async_get(hass)
    apis: dict[str, tuple[str, Any]] = {}
    for entity_id in sorted(await service.async_extract_entity_ids(call)):
        entry = registry.async_get(entity_id)
        if entry is None or entry.platform != DOMAIN or entry.config_entry_id is None:
            continue
        api = hass.data.get(DOMAIN, {}).get(entry.config_entry_id)
        if api is not None and hasattr(api, "send_raw_frames"):
            # One send per panel, however many of its entities were targeted.
            apis.setdefault(entry.config_entry_id, (entity_id, api))
    if not apis:
        raise ServiceValidationError(
            f"{DOMAIN}.send_raw_command needs a BLE LED Pixel panel as its "
            "target: pick the panel's device or one of its entities."
        )
    results: dict[str, Any] = {}
    for entity_id, api in apis.values():
        try:
            log = await api.send_raw_frames(
                data["frames"], gap=data["gap"], listen=data["listen"]
            )
        except BleLedPixelConnectionError as err:
            raise HomeAssistantError(f"Could not reach the panel: {err}") from err
        results[entity_id] = {"log": log}
    return results if call.return_response else None


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
        "delete_all_slots",
        entity_domain=Platform.TEXT,
        schema={},
        func="async_delete_all_slots",
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
            # 6 breathing, 7 snowflake. 3 and 4 are rejected by the library on
            # non-32x32 panels because they can bootloop a device. The panel's
            # code 8 (laser) is rejected by pypixelcolor 0.5, so not offered.
            vol.Optional("animation", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=7)
            ),
            vol.Optional("speed", default=80): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Optional("save_slot", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=MAX_WRITABLE_SLOT)
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
                [
            "3x5-de",
            "Jersey10",
            "Lepidos",
            "Micro5",
            "OpenSans-Light",
            "PixelifySans",
            "PressStart2P",
            "Silkscreen",
            "Tiny5",
            "VT323",
            "WP7xn",
        ]
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
        "show_gallery_image",
        entity_domain=Platform.TEXT,
        schema={
            vol.Required("motif"): cv.string,
            vol.Optional("save_slot", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=MAX_WRITABLE_SLOT)
            ),
            vol.Optional("resize_method", default="fit"): vol.In(["fit", "crop"]),
        },
        func="async_show_gallery_image",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "preload_gallery",
        entity_domain=Platform.TEXT,
        schema={
            vol.Required("motifs"): vol.All(
                cv.ensure_list, [cv.string], vol.Length(min=1, max=MAX_WRITABLE_SLOT)
            ),
            vol.Optional("first_slot", default=MIN_WRITABLE_SLOT): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_WRITABLE_SLOT, max=MAX_WRITABLE_SLOT)
            ),
        },
        func="async_preload_gallery",
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

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_password",
        entity_domain=Platform.TEXT,
        schema={
            # Digits only; the length is checked against the model, because
            # two known models use four digits and everything else six.
            vol.Required("password"): vol.All(cv.string, vol.Match(r"^\d{4}$|^\d{6}$")),
            vol.Optional("enabled", default=True): cv.boolean,
        },
        func="async_set_password",
    )

    async def send_raw_command(call: ServiceCall) -> dict[str, Any] | None:
        return await _async_send_raw_command(hass, call)

    service.async_register_admin_service(
        hass,
        DOMAIN,
        "send_raw_command",
        send_raw_command,
        schema=SEND_RAW_COMMAND_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
