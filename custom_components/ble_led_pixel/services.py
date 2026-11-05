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

Each action dispatches to a named method on every panel's Message entity
that the call targets, like Home Assistant's own entity actions, but without
skipping entities that are unavailable: the Message is greyed out in clock
mode, and the actions must keep working then.
"""
from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError, Unauthorized, UnknownUser
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service

from .const import DATA_PANEL_ENTITIES, DOMAIN

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


def _panel_entities(hass: HomeAssistant) -> set:
    """The Message entities of every loaded panel, which carry the actions."""
    return hass.data.setdefault(DATA_PANEL_ENTITIES, set())


def _excluded_entity_ids(hass: HomeAssistant, call: ServiceCall) -> set[str]:
    """Entities an `entity_id: all` call excludes, on versions that support it.

    Targeted calls get their exclusions applied by async_extract_entity_ids.
    Home Assistant releases without an exclude block have nothing to exclude.
    """
    try:
        from homeassistant.helpers import target as target_helpers
    except ImportError:
        return set()
    extract = getattr(target_helpers, "async_extract_excluded_entity_ids", None)
    selection = getattr(target_helpers, "TargetSelection", None)
    if extract is None or selection is None:
        return set()
    return set(extract(hass, selection(call.data)))


async def _resolve_targets(hass: HomeAssistant, call: ServiceCall) -> list:
    """Find the panels an action call targets, whether available or not.

    Home Assistant's own entity-action dispatch skips unavailable entities.
    The Message entity is greyed out (unavailable) while the panel is in
    clock mode, but the actions it carries act on the panel, not on the
    Message, so they must still run then.
    """
    entities = _panel_entities(hass)
    target_all = call.data.get(ATTR_ENTITY_ID) in (ENTITY_MATCH_ALL, [ENTITY_MATCH_ALL])
    if target_all:
        excluded = _excluded_entity_ids(hass, call)
        targets = [entity for entity in entities if entity.entity_id not in excluded]
    else:
        wanted = await service.async_extract_entity_ids(call)
        targets = [entity for entity in entities if entity.entity_id in wanted]
    targets.sort(key=lambda entity: entity.entity_id)

    if call.context.user_id:
        user = await hass.auth.async_get_user(call.context.user_id)
        if user is None:
            raise UnknownUser(context=call.context)
        if not user.is_admin:
            allowed = user.permissions.check_entity
            if target_all:
                # As Home Assistant does: "all" means all the user controls.
                targets = [
                    entity for entity in targets
                    if allowed(entity.entity_id, POLICY_CONTROL)
                ]
            else:
                for entity in targets:
                    if not allowed(entity.entity_id, POLICY_CONTROL):
                        raise Unauthorized(
                            context=call.context,
                            entity_id=entity.entity_id,
                            permission=POLICY_CONTROL,
                        )

    if not targets:
        raise ServiceValidationError(
            f"{DOMAIN}.{call.service} needs a BLE LED Pixel panel as its target: "
            "pick the panel's Message entity, the device, or its area."
        )
    return targets


def _register_panel_action(
    hass: HomeAssistant,
    name: str,
    *,
    schema: dict,
    func: str,
    supports_response: SupportsResponse = SupportsResponse.NONE,
) -> None:
    """Register one action that runs a method on each targeted panel."""

    async def handle(call: ServiceCall) -> dict[str, Any] | None:
        data = service.remove_entity_service_fields(call)
        targets = await _resolve_targets(hass, call)
        for entity in targets:
            entity.async_set_context(call.context)
        # Every panel is tried, as Home Assistant does: one that is offline
        # must not keep the others from updating. The first failure is
        # raised once all have finished.
        outcomes = await asyncio.gather(
            *(getattr(entity, func)(**data) for entity in targets),
            return_exceptions=True,
        )
        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                raise outcome
        results = {
            entity.entity_id: outcome for entity, outcome in zip(targets, outcomes)
        }
        return results if call.return_response else None

    hass.services.async_register(
        DOMAIN,
        name,
        handle,
        schema=cv.make_entity_service_schema(schema),
        supports_response=supports_response,
    )


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


def async_setup_services(hass: HomeAssistant) -> None:
    """Register all ble_led_pixel.* actions once, at integration setup."""

    _register_panel_action(
        hass,
        "show_slot",
        schema={
            vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        },
        func="async_show_slot",
    )

    _register_panel_action(
        hass,
        "delete_slot",
        schema={
            vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        },
        func="async_delete_slot",
    )

    _register_panel_action(
        hass,
        "delete_all_slots",
        schema={},
        func="async_delete_all_slots",
    )

    _register_panel_action(
        hass,
        "show_emoji",
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

    _register_panel_action(
        hass,
        "send_mdi_icon",
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

    _register_panel_action(
        hass,
        "send_text",
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
            vol.Optional("save_slot", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=10)
            ),
            vol.Optional("rainbow_mode", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=9)
            ),
        },
        func="async_send_text",
    )

    _register_panel_action(
        hass,
        "send_test_pattern",
        schema={},
        func="async_send_test_pattern",
    )

    _register_panel_action(
        hass,
        "send_layout",
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

    _register_panel_action(
        hass,
        "send_image_file",
        schema={
            vol.Required("file_path"): cv.string,
            vol.Optional("resize_method", default="crop"): vol.In(["crop", "fit"]),
            vol.Optional("save_slot", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=10)
            ),
        },
        func="async_send_image_file",
    )

    _register_panel_action(
        hass,
        "show_preset",
        schema={
            vol.Required("preset"): vol.All(vol.Coerce(int), vol.Range(min=1, max=20)),
            vol.Optional("language", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
        },
        func="async_show_preset",
    )

    _register_panel_action(
        hass,
        "set_scoreboard",
        schema={
            vol.Required("home"): vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
            vol.Required("away"): vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
        },
        func="async_set_scoreboard",
    )

    _register_panel_action(
        hass,
        "set_countdown",
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

    _register_panel_action(
        hass,
        "set_stopwatch",
        schema={vol.Required("running"): cv.boolean},
        func="async_set_stopwatch",
    )

    _register_panel_action(
        hass,
        "set_password",
        schema={
            # Digits only; the length is checked against the model, because
            # two known models use four digits and everything else six.
            vol.Required("password"): vol.All(cv.string, vol.Match(r"^\d{4}$|^\d{6}$")),
            vol.Optional("enabled", default=True): cv.boolean,
        },
        func="async_set_password",
    )

    _register_panel_action(
        hass,
        "send_raw_command",
        schema={
            vol.Required("frames"): vol.All(
                cv.ensure_list, [_hex_frame], vol.Length(min=1, max=10)
            ),
            vol.Optional("gap", default=0.5): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=10)
            ),
            vol.Optional("listen", default=2.0): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=30)
            ),
        },
        func="async_send_raw_command",
        supports_response=SupportsResponse.OPTIONAL,
    )
