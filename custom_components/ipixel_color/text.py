"""Text entity for iPIXEL Color."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback, async_get_current_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .api import iPIXELAPI, iPIXELConnectionError
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME
from .common import get_entity_id_by_unique_id
from .common import resolve_template_variables, update_ipixel_display

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iPIXEL Color text input."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    api = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([
        iPIXELTextDisplay(hass, api, entry, address, name),
    ])

    platform = async_get_current_platform()
    platform.async_register_entity_service(
        "send_mdi_icon",
        {
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
        "async_send_mdi_icon",
    )
    platform.async_register_entity_service(
        "send_text",
        {
            vol.Required("text"): cv.string,
            vol.Optional("color", default=[255, 255, 255]): vol.All(
                vol.ExactSequence([cv.byte, cv.byte, cv.byte]), vol.Coerce(tuple)
            ),
            vol.Optional("bg_color", default=None): vol.Any(
                None,
                vol.All(vol.ExactSequence([cv.byte, cv.byte, cv.byte]), vol.Coerce(tuple)),
            ),
            vol.Optional("font", default="CUSONG"): vol.In(
                ["CUSONG", "SIMSUN", "VCR_OSD_MONO"]
            ),
            vol.Optional("animation", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=7)
            ),
            vol.Optional("speed", default=80): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Optional("rainbow_mode", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=9)
            ),
        },
        "async_send_text",
    )
    platform.async_register_entity_service(
        "send_test_pattern",
        {},
        "async_send_test_pattern",
    )
    platform.async_register_entity_service(
        "send_layout",
        {
            vol.Optional("icon"): cv.string,
            vol.Optional("icon_x", default=0): vol.Coerce(int),
            vol.Optional("icon_y", default=0): vol.Coerce(int),
            vol.Optional("icon_size"): vol.Coerce(int),
            vol.Optional("icon_color", default=[255, 255, 255]): vol.All(
                vol.ExactSequence([cv.byte, cv.byte, cv.byte]), vol.Coerce(tuple)
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
                ["3x5-de", "5x5", "7x5", "OpenSans-Light", "WP7xn"]
            ),
            vol.Optional("text_color", default=[255, 255, 255]): vol.All(
                vol.ExactSequence([cv.byte, cv.byte, cv.byte]), vol.Coerce(tuple)
            ),
            vol.Optional("text_wrap", default=True): cv.boolean,
            vol.Optional("text_line_spacing", default=1): vol.Coerce(int),
            vol.Optional("text_scroll", default=False): cv.boolean,
            vol.Optional("text_scroll_step", default=2): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=20)
            ),
            vol.Optional("text_scroll_frame_ms", default=80): vol.All(
                vol.Coerce(int), vol.Range(min=20, max=1000)
            ),
            vol.Optional("text_scroll_gap", default=16): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=200)
            ),
            vol.Optional("bg_color", default=[0, 0, 0]): vol.All(
                vol.ExactSequence([cv.byte, cv.byte, cv.byte]), vol.Coerce(tuple)
            ),
            vol.Optional("save_slot", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=10)
            ),
        },
        "async_send_layout",
    )
    platform.async_register_entity_service(
        "send_image_file",
        {
            vol.Required("file_path"): cv.string,
            vol.Optional("resize_method", default="crop"): vol.In(["crop", "fit"]),
            vol.Optional("save_slot", default=0): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=10)
            ),
        },
        "async_send_image_file",
    )


class iPIXELTextDisplay(TextEntity, RestoreEntity):
    """Representation of an iPIXEL Color text display."""

    _attr_mode = TextMode.TEXT
    _attr_native_max = 500  # Maximum 500 characters per protocol

    def __init__(
        self, 
        hass: HomeAssistant,
        api: iPIXELAPI, 
        entry: ConfigEntry, 
        address: str, 
        name: str
    ) -> None:
        """Initialize the text display."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Display"
        self._attr_unique_id = f"{address}_text_display"
        self._current_text = ""
        self._available = True
        
        # Store current settings (could be exposed as additional entities later)
        self._effect = "scroll_ltr"  # Default to left-to-right scrolling
        self._speed = 50
        self._color_fg = (255, 255, 255)  # White text
        self._color_bg = (0, 0, 0)  # Black background

        # Device info for grouping in device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=name,
            manufacturer="iPIXEL",
            model="LED Matrix Display",
            sw_version="1.0",
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        # Restore last state if available
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state:
            self._current_text = last_state.state
            _LOGGER.debug("Restored text state: %s", self._current_text)

    @property
    def native_value(self) -> str | None:
        """Return the current text value."""
        return self._current_text

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Always return True to allow reconnection attempts
        # The actual connection state will be handled in the async_set_value method
        return True

    async def async_set_value(self, value: str) -> None:
        """Set the text to display."""
        try:
            # Store the original text value (preserving \n as typed)
            self._current_text = value
            
            # Check if auto-update is enabled
            auto_update = await self._get_auto_update_setting()
            if not auto_update:
                _LOGGER.debug("Auto-update disabled - text stored but not sent to display. Use update button to refresh.")
                return
            
            # Resolve templates and process escape sequences when sending to display
            template_resolved = await resolve_template_variables(self.hass, value)
            processed_text = template_resolved.replace('\\n', '\n').replace('\\t', '\t')
            
            # Auto-update is enabled, proceed with display update
            await self._update_display(processed_text)
                
        except iPIXELConnectionError as err:
            _LOGGER.error("Connection error while displaying text: %s", err)
            # Don't set unavailable to allow retry
        except Exception as err:
            _LOGGER.error("Unexpected error while displaying text: %s", err)

    async def _update_display(self, text: str | None = None) -> None:
        """Update the physical display with text and current settings.
        
        Args:
            text: Pre-processed text to display, or None to use stored text
        """
        # Use the common update function
        await update_ipixel_display(self.hass, self._name, self._api, text)

    async def _get_auto_update_setting(self) -> bool:
        """Get the current auto-update setting from the switch entity."""
        try:
            # Get the auto-update switch entity
            entity_id = get_entity_id_by_unique_id(self.hass, self._address, "auto_update", "switch")
            state = self.hass.states.get(entity_id)
            if state:
                return state.state == "on"
        except Exception as err:
            _LOGGER.debug("Could not get auto-update setting: %s", err)
        return False  # Default to manual updates only

    async def async_send_mdi_icon(
        self,
        icon: str,
        color: tuple[int, int, int] = (255, 255, 255),
        bg_color: tuple[int, int, int] = (0, 0, 0),
        scale: int = 100,
        save_slot: int = 0,
    ) -> None:
        """Render and display a Home Assistant MDI icon (service: send_mdi_icon).

        Args:
            icon: MDI icon name, e.g. 'mdi:battery-outline' or 'battery-outline'.
            color: Icon fill color as an (R, G, B) tuple.
            bg_color: Canvas background color as an (R, G, B) tuple.
            scale: Icon size as a percentage of the panel's smaller dimension (1-100).
            save_slot: If >= 1, saves the icon to that device memory slot.
        """
        color_hex = "".join(f"{c:02x}" for c in color)
        bg_color_hex = "".join(f"{c:02x}" for c in bg_color)

        success = await self._api.send_mdi_icon(
            icon=icon,
            color=color_hex,
            bg_color=bg_color_hex,
            scale=scale,
            save_slot=save_slot,
        )
        if not success:
            _LOGGER.error("Failed to send MDI icon '%s'", icon)
            raise HomeAssistantError(f"Failed to send MDI icon '{icon}' - check the logs for details")

    async def async_send_text(
        self,
        text: str,
        color: tuple[int, int, int] = (255, 255, 255),
        bg_color: tuple[int, int, int] | None = None,
        font: str = "CUSONG",
        animation: int = 0,
        speed: int = 80,
        rainbow_mode: int = 0,
    ) -> None:
        """Send text using pypixelcolor's native renderer (service: send_text).

        Independent of the entity's stored text/effect/speed/colors (used by
        the 'Display' text box + auto-update flow) - meant for direct calls
        from automations/scripts with their own parameters each time.

        Args:
            text: Text to display (supports emojis).
            color: Text color as an (R, G, B) tuple.
            bg_color: Background color as an (R, G, B) tuple, or None for transparent.
            font: Built-in font name ('CUSONG', 'SIMSUN', 'VCR_OSD_MONO').
            animation: Animation type (0-7). Note: pypixelcolor itself rejects
                3 and 4 on panels that aren't 32x32, to avoid a device bootloop.
            speed: Animation speed (0-100).
            rainbow_mode: Rainbow color-cycling mode (0-9).
        """
        color_hex = "".join(f"{c:02x}" for c in color)
        bg_color_hex = "".join(f"{c:02x}" for c in bg_color) if bg_color is not None else None

        success = await self._api.display_text_pypixelcolor(
            text=text,
            color=color_hex,
            bg_color=bg_color_hex,
            font=font,
            animation=animation,
            speed=speed,
            rainbow_mode=rainbow_mode,
        )
        if not success:
            _LOGGER.error("Failed to send text '%s'", text)
            raise HomeAssistantError(f"Failed to send text '{text}' - check the logs for details")

    async def async_send_test_pattern(self) -> None:
        """DIAGNOSTIC ONLY: send a 4-quadrant colored test pattern (service: send_test_pattern).

        Used to empirically determine the logical-buffer-to-physical-panel
        mapping when the device's reported width/height doesn't match the
        panel's real physical shape.
        """
        success = await self._api.send_test_pattern()
        if not success:
            _LOGGER.error("Failed to send test pattern")
            raise HomeAssistantError("Failed to send test pattern - check the logs for details")

    async def async_send_layout(
        self,
        icon: str | None = None,
        icon_x: int = 0,
        icon_y: int = 0,
        icon_size: int | None = None,
        icon_color: tuple[int, int, int] = (255, 255, 255),
        image_path: str | None = None,
        image_x: int = 0,
        image_y: int = 0,
        image_width: int | None = None,
        image_height: int | None = None,
        text: str | None = None,
        text_x: int = 0,
        text_y: int = 0,
        text_size: float = 6,
        text_font: str | None = None,
        text_color: tuple[int, int, int] = (255, 255, 255),
        text_wrap: bool = True,
        text_line_spacing: int = 1,
        text_scroll: bool = False,
        text_scroll_step: int = 2,
        text_scroll_frame_ms: int = 80,
        text_scroll_gap: int = 16,
        bg_color: tuple[int, int, int] = (0, 0, 0),
        save_slot: int = 0,
    ) -> None:
        """Compose an icon and/or text at independent positions (service: send_layout).

        Both are optional; give at least one. Positions are the element's
        top-left corner in device pixels. '\\n' in text always forces a
        line break; text_wrap additionally auto-wraps at the panel edge;
        text_scroll makes text too wide to fit scroll continuously instead.
        """
        icon_color_hex = "".join(f"{c:02x}" for c in icon_color)
        text_color_hex = "".join(f"{c:02x}" for c in text_color)
        bg_color_hex = "".join(f"{c:02x}" for c in bg_color)

        success = await self._api.send_layout(
            icon=icon,
            icon_x=icon_x,
            icon_y=icon_y,
            icon_size=icon_size,
            icon_color=icon_color_hex,
            image_path=image_path,
            image_x=image_x,
            image_y=image_y,
            image_width=image_width,
            image_height=image_height,
            text=text,
            text_x=text_x,
            text_y=text_y,
            text_size=text_size,
            text_font=text_font,
            text_color=text_color_hex,
            text_wrap=text_wrap,
            text_line_spacing=text_line_spacing,
            text_scroll=text_scroll,
            text_scroll_step=text_scroll_step,
            text_scroll_frame_ms=text_scroll_frame_ms,
            text_scroll_gap=text_scroll_gap,
            bg_color=bg_color_hex,
            save_slot=save_slot,
        )
        if not success:
            _LOGGER.error("Failed to send layout")
            raise HomeAssistantError("Failed to send layout - check the logs for details")

    async def async_send_image_file(
        self,
        file_path: str,
        resize_method: str = "crop",
        save_slot: int = 0,
    ) -> None:
        """Send an existing image or GIF file from disk (service: send_image_file).

        The file must be readable by Home Assistant (e.g. under /config/www/).
        """
        success = await self._api.send_image_file(
            file_path=file_path,
            resize_method=resize_method,
            save_slot=save_slot,
        )
        if not success:
            _LOGGER.error("Failed to send image file '%s'", file_path)
            raise HomeAssistantError(f"Failed to send image file '{file_path}' - check the logs for details")

    async def async_update(self) -> None:
        """Update the entity state."""
        try:
            # Check connection status
            if self._api.is_connected:
                self._available = True
            else:
                self._available = False
                _LOGGER.debug("Device not connected, marking as unavailable")
                
        except Exception as err:
            _LOGGER.error("Error updating entity state: %s", err)
            self._available = False


