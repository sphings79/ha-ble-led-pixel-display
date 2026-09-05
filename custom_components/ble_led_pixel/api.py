"""BLE LED Pixel Display Bluetooth API client - Refactored version."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING
from math import floor

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.config_entries import ConfigEntry

from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .bluetooth.client import BluetoothClient
from .device.commands import (
    make_power_command,
    make_brightness_command,
)
from .device.clock import make_clock_mode_command, make_time_command
from .device.commands import (
    make_countdown_command,
    make_verify_password_command,
    password_length,
    make_preset_command,
    make_scoreboard_command,
    make_stopwatch_command,
)
from .capabilities import (
    ALL_FEATURES,
    FEATURE_COUNTDOWN,
    FEATURE_PRESETS,
    FEATURE_SCOREBOARD,
    FEATURE_STOPWATCH,
    resolve_features,
)
from .device.text import make_text_command
from .device.image import make_image_command
from homeassistant.components import bluetooth

from .advertisement import PanelIdentity, parse_identity
from .fonts import resolve_font_for_library
from .unknown_panel import async_report_unknown_panel
from .device.info import (
    build_device_info_command,
    build_firmware_command,
    parse_device_response,
    parse_firmware_response,
)
from .device.mdi_icon import build_mdi_icon_png
from .device.composer import build_layout_media
from .display.text_renderer import render_text_to_png
from .display.emoji_renderer import render_emoji_to_png
from .const import RECONNECT_BACKOFF_START, RECONNECT_BACKOFF_MAX
from .exceptions import BleLedPixelConnectionError, BleLedPixelFeatureUnsupported
from .const import (
    OPT_FORCE_FEATURES,
    OPT_PASSWORD,
    OPT_OVERRIDE_DIMENSIONS,
    OPT_PANEL_HEIGHT,
    OPT_PANEL_WIDTH,
)

try:
    from pypixelcolor.commands.show_slot import show_slot as pypixelcolor_show_slot
    from pypixelcolor.commands.delete import delete as pypixelcolor_delete
except ImportError:
    pypixelcolor_show_slot = None
    pypixelcolor_delete = None

_LOGGER = logging.getLogger(__name__)


class BleLedPixelAPI:
    """BLE LED pixel panel API client - simplified facade."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        entry: "ConfigEntry | None" = None,
    ) -> None:
        """Initialize the API client.

        Args:
            hass: Home Assistant instance
            address: Bluetooth MAC address
            entry: Config entry holding integration options (dimension overrides, etc.)
        """
        self._hass = hass
        self._address = address
        self._entry = entry
        self._bluetooth = BluetoothClient(hass, address)
        # Reconnect watcher state
        self._reconnect_task: asyncio.Task | None = None
        self._reconnect_lock = asyncio.Lock()
        self._watcher_started = False
        self._unsubscribe_bluetooth = None
        self._unsubscribe_identity = None
        self._power_state = False
        # Options this instance was set up with; __init__ compares against it
        # so an entry.data change does not trigger a reload.
        self.setup_options: dict[str, Any] = {}
        self._device_info: dict[str, Any] | None = None
        self._device_response: bytes | None = None

    def _resolved_dimensions(self, base_info: dict[str, Any]) -> tuple[int, int]:
        """Return (width, height) honoring options-flow overrides if set."""
        if self._entry is None:
            return base_info["width"], base_info["height"]
        options = self._entry.options
        if not options.get(OPT_OVERRIDE_DIMENSIONS):
            return base_info["width"], base_info["height"]
        width = options.get(OPT_PANEL_WIDTH) or base_info["width"]
        height = options.get(OPT_PANEL_HEIGHT) or base_info["height"]
        return width, height
        
    async def connect(self) -> bool:
        """Connect to the LED panel."""
        connected = await self._bluetooth.connect(self._notification_handler)
        if connected:
            await self._unlock_if_needed()
        return connected
    
    async def disconnect(self) -> None:
        """Disconnect from the device."""
        await self._bluetooth.disconnect()
    
    async def ensure_connected(self) -> bool:
        """Reconnect if the link dropped. Never raises."""
        connected = await self._bluetooth.ensure_connected()
        if connected:
            await self._unlock_if_needed()
        return connected

    @property
    def password(self) -> str | None:
        """The configured password, if the panel is locked."""
        if self._entry is None:
            return None
        password = self._entry.options.get(OPT_PASSWORD)
        return password or None

    @property
    def is_locked(self) -> bool | None:
        """Whether the panel is password protected.

        None until the device info has been read once. The flag is byte 10 of
        that response; the vendor app treats 1 as protected.
        """
        if self._device_info is None:
            return None
        flag = self._device_info.get("password_flag")
        if flag is None:
            return None
        return flag == 1

    async def _unlock_if_needed(self) -> None:
        """Send the password after connecting, when one is configured.

        A panel forgets the unlock when the link drops, so this has to happen
        on every connect rather than once at setup. It runs before anything
        else is sent, because a locked panel silently discards content.

        Never raises: a failure here should leave the entry loaded with a log
        line, not break setup.
        """
        password = self.password
        if password is None:
            return
        # is_locked is None before the first device-info read. Send anyway in
        # that case - the user configured a password, which is a stronger
        # signal than a flag we have not read yet.
        if self.is_locked is False:
            return
        try:
            identity = self.identity
            command = make_verify_password_command(
                password, password_length(identity.cid, identity.pid)
            )
        except ValueError as err:
            _LOGGER.error("Cannot unlock %s: %s", self._address, err)
            return
        try:
            # Deliberately not _send_with_reconnect: that calls back into
            # ensure_connected, which calls this method.
            if await self._bluetooth.send_command(command):
                _LOGGER.debug("Sent the password to %s", self._address)
            else:
                _LOGGER.warning(
                    "Could not send the password to %s; the panel will "
                    "ignore anything sent to it", self._address,
                )
        except Exception as err:  # noqa: BLE001 - unlocking must not break setup
            _LOGGER.warning("Error sending the password to %s: %s", self._address, err)

    async def unlock(self) -> bool:
        """Send the configured password now.

        Returns:
            True when a password was configured and the command went out.
        """
        if self.password is None:
            return False
        await self._unlock_if_needed()
        return True

    def _schedule_reconnect(self) -> None:
        """Start the reconnect loop, unless one is already running."""
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        # Background task: async_create_task() would make Home Assistant wait
        # for this loop before finishing its start-up phase, and the loop is
        # meant to run indefinitely.
        self._reconnect_task = self._hass.async_create_background_task(
            self._reconnect_loop(), name=f"ble_led_pixel reconnect {self._address}"
        )

    async def _reconnect_loop(self) -> None:
        """Reconnect with a growing backoff until the link is up again."""
        try:
            async with self._reconnect_lock:
                if self.is_connected:
                    return
                delay = RECONNECT_BACKOFF_START
                _LOGGER.warning(
                    "Link to LED panel %s lost; reconnecting (first retry in %.0fs)",
                    self._address, delay,
                )
                while not self.is_connected:
                    await asyncio.sleep(delay)
                    if not self._watcher_started:   # integration unloaded meanwhile
                        return
                    if await self.ensure_connected():
                        _LOGGER.info("Reconnected to LED panel %s", self._address)
                        return
                    delay = min(delay * 2, RECONNECT_BACKOFF_MAX)
                    _LOGGER.warning(
                        "Reconnect to %s failed; next attempt in %.0fs", self._address, delay,
                    )
        finally:
            if self._reconnect_task is asyncio.current_task():
                self._reconnect_task = None

    async def start_watcher(self) -> None:
        """Watch for the panel advertising again and reconnect when it does.

        Home Assistant's Bluetooth manager tells us whenever the panel is seen.
        If we are not connected at that moment, the link is restored right away
        rather than waiting out the backoff - which is what makes a panel that
        was out of range at startup come back on its own.
        """
        if self._watcher_started:
            return
        self._watcher_started = True

        def _advertisement_callback(service_info, change) -> None:
            if not self.is_connected:
                self._schedule_reconnect()

        self._unsubscribe_bluetooth = bluetooth.async_register_callback(
            self._hass,
            _advertisement_callback,
            {"address": self._address},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
        # The panel may already be advertising, and no callback fires for what
        # happened before we subscribed - so make one attempt right away.
        if not self.is_connected:
            self._schedule_reconnect()

    async def stop_watcher(self) -> None:
        """Stop watching and cancel a pending reconnect."""
        self._watcher_started = False
        if self._unsubscribe_bluetooth is not None:
            try:
                self._unsubscribe_bluetooth()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error unsubscribing bluetooth callback: %s", err)
            self._unsubscribe_bluetooth = None
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Reconnect task ended with: %s", err)
            self._reconnect_task = None

    async def _send_with_reconnect(self, command: bytes) -> bool:
        """Send a command, reconnecting once when the link turns out to be dead.

        A connection can die between the availability check and the write. In
        that case reconnect and retry once, instead of failing the action and
        leaving the panel stale until someone reloads the integration.
        """
        try:
            if await self._bluetooth.send_command(command):
                return True
        except BleLedPixelConnectionError:
            pass
        if await self.ensure_connected():
            return await self._bluetooth.send_command(command)
        return False

    async def set_power(self, on: bool) -> bool:
        """Set device power state."""
        command = make_power_command(on)
        success = await self._send_with_reconnect(command)
        
        if success:
            self._power_state = on
            _LOGGER.debug("Power set to %s", "ON" if on else "OFF")
        return success
    
    async def set_brightness(self, brightness: int) -> bool:
        """Set device brightness level.
        
        Args:
            brightness: Brightness level from 1 to 100
            
        Returns:
            True if command was sent successfully
        """
        try:
            command = make_brightness_command(brightness)
            success = await self._send_with_reconnect(command)
            
            if success:
                _LOGGER.debug("Brightness set to %d", brightness)
            else:
                _LOGGER.error("Failed to set brightness to %d", brightness)
            return success
            
        except ValueError as err:
            _LOGGER.error("Invalid brightness value: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Error setting brightness: %s", err)
            return False

    async def sync_time(self) -> bool:
        """Sync current time to the device.

        This is useful for keeping the clock display accurate,
        especially after the device has been running for a while.

        Returns:
            True if time was synced successfully
        """
        try:
            time_command = make_time_command()
            success = await self._send_with_reconnect(time_command)

            if success:
                _LOGGER.debug("Time synchronized to device")
            else:
                _LOGGER.error("Failed to sync time")
            return success

        except Exception as err:
            _LOGGER.error("Error syncing time: %s", err)
            return False

    async def set_clock_mode(
        self,
        style: int = 1,
        date: str = "",
        show_date: bool = True,
        format_24: bool = True
    ) -> bool:
        """Set device to clock display mode.

        Args:
            style: Clock style (0-8)
            date: Date in DD/MM/YYYY format (defaults to today)
            show_date: Whether to show the date
            format_24: Whether to use 24-hour format

        Returns:
            True if command was sent successfully
        """
        try:
            # Set clock mode
            command = make_clock_mode_command(style, date, show_date, format_24)
            success = await self._send_with_reconnect(command)

            if not success:
                _LOGGER.error("Failed to set clock mode")
                return False

            _LOGGER.info("Clock mode set: style=%d, 24h=%s, show_date=%s",
                       style, format_24, show_date)

            # Sync current time to the device
            time_success = await self.sync_time()
            if not time_success:
                _LOGGER.warning("Clock mode set but time sync failed")

            return success

        except ValueError as err:
            _LOGGER.error("Invalid clock mode parameters: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Error setting clock mode: %s", err)
            return False
    
    def _cached_identity(self) -> PanelIdentity:
        """Identity stored on the config entry, if one was ever seen."""
        entry = self._entry
        if entry is None:
            return PanelIdentity(None, None, None, None)
        return PanelIdentity(
            cid=entry.data.get("cid"),
            pid=entry.data.get("pid"),
            around=entry.data.get("around"),
            device_type=entry.data.get("adv_device_type"),
        )

    def _store_identity(self, identity: PanelIdentity) -> None:
        """Persist the identity so it survives the panel going quiet."""
        entry = self._entry
        if entry is None or identity.cid is None:
            return
        if entry.data.get("cid") == identity.cid and entry.data.get("pid") == identity.pid:
            return

        # Logged once, when an identity is first seen or changes. The panel
        # works either way -- dimensions come from the device type, not the
        # brand -- but the manufacturer field stays blank until the id is known.
        if identity.brand is None and identity.cidpid is not None:
            _LOGGER.warning(
                "Panel %s reports product id %s, which is not in the brand "
                "table. Everything works, only the manufacturer stays unset. "
                "Please open an issue with this id and the brand printed on "
                "the packaging so it can be added: "
                "https://github.com/sphings79/ha-ble-led-pixel-display/issues",
                self._address, identity.cidpid,
            )

        try:
            self._hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    "cid": identity.cid,
                    "pid": identity.pid,
                    "around": identity.around,
                    "adv_device_type": identity.device_type,
                },
            )
            _LOGGER.debug("Stored identity for %s: cid=%s pid=%s",
                          self._address, identity.cid, identity.pid)
        except Exception as err:  # noqa: BLE001 - diagnostics must not break setup
            _LOGGER.debug("Could not store identity: %s", err)

        # Device info is queried once and cached, so an identity that arrives
        # afterwards has to be patched in or the sensors keep showing nothing.
        if self._device_info is not None:
            self._device_info["cid"] = identity.cid
            self._device_info["pid"] = identity.pid
            self._device_info["cidpid"] = identity.cidpid
            self._device_info["brand"] = identity.brand

        # The identity can arrive long after setup, once the panel advertises.
        # Re-check then, so the notice about an unknown panel appears - or
        # disappears again - without waiting for the next restart.
        self._hass.async_create_task(
            async_report_unknown_panel(self._hass, self._address, self._device_info)
        )

    @property
    def device_info(self) -> dict[str, Any] | None:
        """Everything known about the panel, or None before it was queried."""
        return self._device_info

    @property
    def identity(self) -> PanelIdentity:
        """Product identity, from the live advertisement or the stored one.

        Does not need a connection: cid and pid are advertised, not queried.
        """
        live = self._read_identity()
        return live if live.cid is not None else self._cached_identity()

    def start_identity_watch(self) -> None:
        """Cache the product identity whenever the panel advertises.

        A panel stops advertising the moment it is connected, and the
        device-info query only runs once a link is up -- so by the time
        anything asks for cid and pid there is usually nothing on air to read,
        and the entry had nothing stored to fall back on. Listening for
        advertisements catches the identity in the window where it is actually
        being broadcast, which is exactly when the panel is disconnected.
        """
        if self._unsubscribe_identity is not None:
            return

        # Whatever the Bluetooth manager already has cached, before waiting for
        # the next advertisement.
        self._store_identity(self._read_identity())

        @callback
        def _advertisement_seen(service_info, change) -> None:
            self._store_identity(parse_identity(service_info.manufacturer_data))

        try:
            self._unsubscribe_identity = bluetooth.async_register_callback(
                self._hass,
                _advertisement_seen,
                {"address": self._address},
                bluetooth.BluetoothScanningMode.PASSIVE,
            )
        except Exception as err:  # noqa: BLE001 - diagnostics must not break setup
            _LOGGER.debug("Could not watch advertisements for %s: %s",
                          self._address, err)

    def stop_identity_watch(self) -> None:
        """Stop listening for advertisements."""
        if self._unsubscribe_identity is None:
            return
        try:
            self._unsubscribe_identity()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Could not stop the identity watch: %s", err)
        self._unsubscribe_identity = None

    def _read_identity(self) -> PanelIdentity:
        """Read cid and pid from the panel's last seen advertisement.

        Never raises: an identity is a nice-to-have, and a panel that has not
        advertised recently should not stop the rest of the device info from
        being used.
        """
        try:
            service_info = bluetooth.async_last_service_info(
                self._hass, self._address, connectable=True
            )
            if service_info is None:
                return PanelIdentity(None, None, None, None)
            return parse_identity(service_info.manufacturer_data)
        except Exception as err:  # noqa: BLE001 - diagnostics must not break setup
            _LOGGER.debug("Could not read product identity: %s", err)
            return PanelIdentity(None, None, None, None)

    async def _read_firmware(self) -> None:
        """Query the firmware versions and fold them into the device info.

        The device-info response carries no version numbers -- pypixelcolor
        reports "unknown" for both. They come from a second read, opcode
        0x8005, which no traffic-derived implementation had: it looks inert
        because nothing on the panel changes, so it was taken for a no-op.

        Never raises. A panel that does not answer keeps the placeholder
        values rather than failing the whole device-info read.
        """
        try:
            response = await self._bluetooth.send_command_wait_response(
                build_firmware_command(), timeout=5.0
            )
        except Exception as err:  # noqa: BLE001 - versions are a nice-to-have
            _LOGGER.debug("Firmware query failed for %s: %s", self._address, err)
            return

        if not response:
            _LOGGER.debug("No firmware reply from %s", self._address)
            return

        versions = parse_firmware_response(response)
        if versions is None:
            _LOGGER.debug(
                "Unexpected firmware reply from %s: %s", self._address, response.hex()
            )
            return

        if self._device_info is not None:
            self._device_info.update(versions)
        _LOGGER.debug(
            "Firmware of %s: MCU %s (build %s), WiFi %s",
            self._address, versions["mcu_version"],
            versions["mcu_build"], versions["wifi_version"],
        )

    async def get_device_info(self) -> dict[str, Any] | None:
        """Query device information and store it (with retry logic)."""
        if self._device_info is not None:
            return self._device_info
            
        max_retries = 3

        for attempt in range(max_retries):
            try:
                command = build_device_info_command()

                # Uses the persistent notification subscription instead of a
                # start_notify/stop_notify cycle per call, which is what caused
                # the "Notify acquired" errors PR #30 worked around.
                response = await self._bluetooth.send_command_wait_response(command, timeout=10.0)

                if response:
                    # cid/pid ride in the advertisement, not in this response,
                    # and they decide which hardware generation a device type
                    # refers to -- so read them first and pass the pid in.
                    identity = self.identity
                    self._store_identity(identity)
                    self._device_info = parse_device_response(response, identity.pid)
                    self._device_info["cid"] = identity.cid
                    self._device_info["pid"] = identity.pid
                    self._device_info["cidpid"] = identity.cidpid
                    self._device_info["brand"] = identity.brand
                    await self._read_firmware()
                    _LOGGER.info("Device info retrieved on attempt %d: %s", attempt + 1, self._device_info)
                    return self._device_info

                raise Exception("No response received")
            
            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout waiting for device info (attempt %d/%d)", attempt + 1, max_retries)
            except Exception as err:
                _LOGGER.warning("Attempt %d/%d failed to get device info: %s", attempt + 1, max_retries, err)
                
            # Short delay before next attempt
            if attempt < max_retries - 1:
                await asyncio.sleep(1.0)
                
        # If we reach here, all retries failed. Return default values.
        _LOGGER.error("All %d attempts failed to get device info. Using defaults.", max_retries)
        self._device_info = {
            "width": 64,
            "height": 16,
            "device_type": 0,
            "device_type_str": "Unknown",
            "led_type": 0,
            "mcu_version": "Unknown",
            "wifi_version": "Unknown",
            "has_wifi": False,
            "password_flag": 255,
            "cid": None,
            "pid": None,
            "cidpid": None,
            "brand": None,
        }
        return self._device_info
    
    async def display_text(self, text: str, antialias: bool = True, font_size: float | None = None, font: str | None = None, line_spacing: int = 0, text_color: str = "ffffff", bg_color: str = "000000") -> bool:
        """Display text as image using PIL and pypixelcolor with color gradient mapping.

        Args:
            text: Text to display (supports multiline with \n)
            antialias: Enable text antialiasing for smoother rendering
            font_size: Fixed font size in pixels (can be fractional), or None for auto-sizing
            font: Font name from fonts/ folder, or None for default
            line_spacing: Additional spacing between lines in pixels
            text_color: Foreground/text color in hex format (e.g., 'ffffff')
            bg_color: Background color in hex format (e.g., '000000')
        """
        try:
            # Get device dimensions (honors options-flow override if set)
            base_info = await self.get_device_info()
            width, height = self._resolved_dimensions(base_info)
            device_info = {**base_info, "width": width, "height": height}

            # Render text to PNG with color gradient
            png_data = render_text_to_png(text, width, height, antialias, font_size, font, line_spacing, text_color, bg_color)

            # Generate image commands using pypixelcolor
            commands = make_image_command(
                image_bytes=png_data,
                file_extension=".png",
                resize_method="crop",
                device_info_dict=device_info
            )

            # Send all command frames
            for i, command in enumerate(commands):
                _LOGGER.debug(
                    "Sending pypixelcolor image frame %d/%d: %d bytes",
                    i + 1,
                    len(commands),
                    len(command)
                )
                success = await self._send_with_reconnect(command)
                if not success:
                    _LOGGER.error("Failed to send image frame %d/%d", i + 1, len(commands))
                    return False

            _LOGGER.info(
                "Text rendered as image: '%s' (%dx%d, %d bytes PNG, %d frames)",
                text,
                width,
                height,
                len(png_data),
                len(commands)
            )
            return True

        except Exception as err:
            _LOGGER.error("Error displaying text: %s", err)
            return False

    async def send_mdi_icon(
        self,
        icon: str,
        color: str = "ffffff",
        bg_color: str = "000000",
        scale: int = 100,
        save_slot: int = 0,
    ) -> bool:
        """Render a Home Assistant MDI icon and display it on the device.

        The icon is downloaded from the jsDelivr CDN mirror of @mdi/svg,
        recolored, rasterized and centered on a canvas matching the
        device's own reported width/height (same convention already used
        by display_text), then sent via pypixelcolor's send_image_hex.

        Args:
            icon: MDI icon name, e.g. 'mdi:battery-outline' or 'battery-outline'.
            color: Icon fill color in hex (with or without '#'), e.g. 'ffffff'.
            bg_color: Canvas background color in hex (with or without '#').
            scale: Icon size as a percentage of the panel's smaller
                dimension (1-100). 100 fills edge to edge on the short side.
            save_slot: If >= 1, saves the image to that device memory slot.
        """
        try:
            device_info = await self.get_device_info()
            width = device_info["width"]
            height = device_info["height"]

            session = async_get_clientsession(self._hass)
            png_data = await build_mdi_icon_png(
                icon=icon,
                session=session,
                canvas_width=width,
                canvas_height=height,
                color_hex=color,
                bg_color_hex=bg_color,
                scale_percent=scale,
            )

            plan = make_image_command(
                image_bytes=png_data,
                file_extension=".png",
                resize_method="crop",
                device_info_dict=device_info,
                save_slot=save_slot,
            )

            success = await self._bluetooth.send_plan(plan, ack_timeout=25.0)
            if not success:
                _LOGGER.error("Failed to send MDI icon '%s'", icon)
                return False

            _LOGGER.info(
                "MDI icon '%s' sent (%dx%d, %d bytes PNG)",
                icon, width, height, len(png_data),
            )
            return True

        except Exception as err:
            _LOGGER.error("Error sending MDI icon '%s': %s", icon, err)
            return False

    async def send_layout(
        self,
        icon: str | None = None,
        icon_x: int = 0,
        icon_y: int = 0,
        icon_size: int | None = None,
        icon_color: str = "ffffff",
        icon_blink: bool = False,
        icon_blink_interval_ms: int = 500,
        icons: list[dict] | None = None,
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
        text_color: str = "ffffff",
        text_wrap: bool = True,
        text_line_spacing: int = 1,
        text_align: str = "left",
        text_scroll: bool = False,
        text_blink: bool = False,
        text_blink_interval_ms: int = 500,
        texts: list[dict] | None = None,
        scroll_step: int = 2,
        scroll_frame_ms: int = 80,
        scroll_gap: int = 16,
        bg_color: str = "000000",
        save_slot: int = 0,
    ) -> bool:
        """Compose up to 4 MDI icons, an image, and up to 4 text elements, and display it.

        All elements are optional but at least one should be given.
        Positions are the top-left corner of each element, in device pixels.

        For a single icon, use the flat icon/icon_x/... parameters (kept
        for backward compatibility). For more than one icon (up to 4), use
        `icons` instead - a list of dicts, each with the same shape as the
        flat parameters (icon, x, y, size, color_hex), e.g.:
            icons=[
                {"icon": "mdi:weather-sunny", "x": 0, "y": 0, "size": 16},
                {"icon": "mdi:water-percent", "x": 20, "y": 0, "size": 16},
            ]
        If `icons` is given, the flat icon/icon_x/... parameters are ignored.

        For a single text, use the flat text/text_x/... parameters (kept for
        backward compatibility). For more than one text (up to 4), use
        `texts` instead - a list of dicts, each with the same shape as the
        flat parameters (text, x, y, size, font, color_hex, wrap, scroll,
        line_spacing). If `texts` is given, the flat text/text_x/...
        parameters are ignored.

        Args:
            icon: Single MDI icon name, e.g. 'mdi:battery-outline'.
                Ignored if `icons` is given. None to skip.
            icon_x: Icon top-left X position in pixels.
            icon_y: Icon top-left Y position in pixels.
            icon_size: Icon size in pixels (square). Defaults to the panel's
                smaller dimension if not given.
            icon_color: Icon fill color in hex (with or without '#').
            icon_blink: If True, the icon blinks on/off (ignored if
                `icons` is given - set 'blink' per item there instead).
            icon_blink_interval_ms: Milliseconds each blink state (on or
                off) lasts.
            icons: List of up to 4 icon dicts - see above. Takes priority
                over icon/icon_x/... if given. Icons are always static (no
                scrolling).
            image_path: Absolute path to an image/GIF file to insert (only
                its first frame, if animated), readable by Home Assistant
                (e.g. under /config/www/). None to skip.
            image_x: Image top-left X position in pixels.
            image_y: Image top-left Y position in pixels.
            image_width: If given, resize the image to this width.
            image_height: If given, resize the image to this height.
            text: Single text to display (ignored if `texts` is given).
                None to skip. '\n' always forces a line break regardless
                of text_wrap.
            text_x: Text top-left X position in pixels.
            text_y: Text top-left Y position in pixels.
            text_size: Font size in pixels (can be fractional) - scales the
                text dynamically.
            text_font: Bundled font name ('3x5-de', '5x5', '7x5',
                'OpenSans-Light', 'WP7xn'), or None for the smallest bundled font.
            text_color: Text color in hex (with or without '#').
            text_wrap: If True (default), automatically word-wrap text that
                would run past the panel's right edge. If False, only
                explicit '\n' breaks lines.
            text_line_spacing: Extra vertical gap between lines, in pixels.
            text_align: Horizontal alignment within the text's own block:
                'left' (default), 'right', or 'center'. Mainly matters with
                multiple '\\n'-separated lines of different widths.
            text_blink: If True, the text blinks on/off (ignored if
                `texts` is given - set 'blink' per item there instead).
            text_blink_interval_ms: Milliseconds each blink state (on or
                off) lasts.
            text_scroll: If True, text too wide to fit scrolls continuously
                (looping GIF) instead of being clipped. No effect if the
                text already fits. Ignored together with text_wrap - wrap
                takes priority when both would apply to fitting text.
            texts: List of up to 4 text element dicts - see above. Takes
                priority over text/text_x/... if given.
            scroll_step: Pixels moved per animation frame, shared by every
                scrolling text so their loops can stay in sync.
            scroll_frame_ms: Duration of each animation frame, in ms.
            scroll_gap: Blank pixels between consecutive loop passes.
            bg_color: Canvas background color in hex (with or without '#').
            save_slot: If >= 1, saves the image to that device memory slot.
        """
        try:
            device_info = await self.get_device_info()
            width = device_info["width"]
            height = device_info["height"]

            image_bytes = None
            if image_path:
                image_bytes = await self._hass.async_add_executor_job(Path(image_path).read_bytes)

            if icons is None and icon:
                icons = [{
                    "icon": icon, "x": icon_x, "y": icon_y,
                    "size": icon_size, "color_hex": icon_color,
                    "blink": icon_blink, "blink_interval_ms": icon_blink_interval_ms,
                }]

            if texts is None and text:
                texts = [{
                    "text": text, "x": text_x, "y": text_y, "size": text_size,
                    "font": text_font, "color_hex": text_color, "wrap": text_wrap,
                    "align": text_align, "scroll": text_scroll,
                    "line_spacing": text_line_spacing,
                    "blink": text_blink, "blink_interval_ms": text_blink_interval_ms,
                }]

            session = async_get_clientsession(self._hass)
            png_data, file_ext = await build_layout_media(
                canvas_width=width,
                canvas_height=height,
                session=session,
                bg_color_hex=bg_color,
                icons=icons,
                image_bytes=image_bytes,
                image_x=image_x,
                image_y=image_y,
                image_width=image_width,
                image_height=image_height,
                texts=texts,
                scroll_step=scroll_step,
                scroll_frame_ms=scroll_frame_ms,
                scroll_gap=scroll_gap,
            )

            plan = make_image_command(
                image_bytes=png_data,
                file_extension=file_ext,
                resize_method="crop",
                device_info_dict=device_info,
                save_slot=save_slot,
            )

            success = await self._bluetooth.send_plan(plan, ack_timeout=25.0)
            if not success:
                _LOGGER.error("Failed to send layout (icons=%s, texts=%s)", icons, texts)
                return False

            _LOGGER.info(
                "Layout sent (%dx%d, n_icons=%d, n_texts=%d)",
                width, height, len(icons or []), len(texts or []),
            )
            return True

        except Exception as err:
            _LOGGER.error("Error sending layout: %s", err)
            return False

    async def send_image_file(
        self,
        file_path: str,
        resize_method: str = "crop",
        save_slot: int = 0,
    ) -> bool:
        """Send an existing image or GIF file (read from disk) to the panel.

        The file must be readable by Home Assistant (e.g. under
        /config/www/), and can be any format pypixelcolor's send_image_hex
        supports (PNG, GIF, JPEG, BMP, TIFF, WEBP, HEIC/HEIF). Animated
        GIFs are sent as-is (frame-by-frame, with their own durations).

        Args:
            file_path: Absolute path to the image/GIF file.
            resize_method: 'crop' (default, fills the panel and crops
                excess) or 'fit' (fits the whole image with black padding).
            save_slot: If >= 1, saves the image to that device memory slot.
        """
        try:
            path = Path(file_path)
            file_bytes = await self._hass.async_add_executor_job(path.read_bytes)

            device_info = await self.get_device_info()

            plan = make_image_command(
                image_bytes=file_bytes,
                file_extension=path.suffix or ".png",
                resize_method=resize_method,
                device_info_dict=device_info,
                save_slot=save_slot,
            )

            success = await self._bluetooth.send_plan(plan, ack_timeout=25.0)
            if not success:
                _LOGGER.error("Failed to send image file '%s'", file_path)
                return False

            _LOGGER.info("Image file '%s' sent (%d bytes)", file_path, len(file_bytes))
            return True

        except Exception as err:
            _LOGGER.error("Error sending image file '%s': %s", file_path, err)
            return False

    async def send_test_pattern(self) -> bool:
        """DIAGNOSTIC ONLY: send a 4-quadrant colored test pattern.

        Sized to the device's own reported (width, height). Used to
        empirically determine how the logical buffer maps onto the
        physical panel when the two don't match (e.g. device reports
        64x16 but the panel is physically a 32x32 square). Remove once
        the mapping is confirmed and no longer needed.

        Quadrants (in logical buffer space, left/right = width split,
        top/bottom = height split): TL=red, TR=green, BL=blue, BR=yellow.
        """
        try:
            device_info = await self.get_device_info()
            width = device_info["width"]
            height = device_info["height"]

            from PIL import Image
            import io

            img = Image.new("RGB", (width, height))
            px = img.load()
            for y in range(height):
                for x in range(width):
                    left = x < width / 2
                    top = y < height / 2
                    if left and top:
                        px[x, y] = (255, 0, 0)
                    elif not left and top:
                        px[x, y] = (0, 255, 0)
                    elif left and not top:
                        px[x, y] = (0, 0, 255)
                    else:
                        px[x, y] = (255, 255, 0)

            buf = io.BytesIO()
            img.save(buf, format="PNG")

            plan = make_image_command(
                image_bytes=buf.getvalue(),
                file_extension=".png",
                resize_method="crop",
                device_info_dict=device_info,
                save_slot=0,
            )
            success = await self._bluetooth.send_plan(plan, ack_timeout=25.0)
            if not success:
                _LOGGER.error("Failed to send test pattern")
                return False

            if pypixelcolor_show_slot is not None:
                show_plan = pypixelcolor_show_slot(0)
                shown = await self._bluetooth.send_plan(show_plan)
                if not shown:
                    _LOGGER.error("Failed to show_slot(0) after sending test pattern")
                    return False

            _LOGGER.info("Test pattern sent (%dx%d), save_slot=0, shown via slot 0", width, height)
            return True
        except Exception as err:
            _LOGGER.error("Error sending test pattern: %s", err)
            return False

    async def show_slot(self, slot: int) -> bool:
        """Display a picture already stored on the panel.

        Sends seven bytes instead of re-transmitting the image, which on a
        32x32 panel means 7 bytes rather than 12288. Store pictures first with
        the save_slot argument of send_image_file or send_mdi_icon.

        Args:
            slot: Slot number. An empty slot makes the panel cycle through the
                slots that do hold something, rather than showing nothing.

        Returns:
            True when the command was sent.
        """
        if pypixelcolor_show_slot is None:
            _LOGGER.error("pypixelcolor is not available")
            return False
        try:
            success = await self._bluetooth.send_plan(pypixelcolor_show_slot(slot))
            if success:
                _LOGGER.debug("Showing slot %d", slot)
            else:
                _LOGGER.error("Failed to show slot %d", slot)
            return success
        except Exception as err:
            _LOGGER.error("Error showing slot %d: %s", slot, err)
            return False

    async def delete_slot(self, slot: int) -> bool:
        """Erase one stored picture from the panel.

        Args:
            slot: Slot number, 0-255.

        Returns:
            True when the command was sent.
        """
        if pypixelcolor_delete is None:
            _LOGGER.error("pypixelcolor is not available")
            return False
        try:
            success = await self._bluetooth.send_plan(pypixelcolor_delete(slot))
            if success:
                _LOGGER.debug("Deleted slot %d", slot)
            else:
                _LOGGER.error("Failed to delete slot %d", slot)
            return success
        except Exception as err:
            _LOGGER.error("Error deleting slot %d: %s", slot, err)
            return False

    @property
    def features(self) -> frozenset[str]:
        """Extra features this panel supports.

        Resolved from the LED type and the advertised product id, because two
        panels of the same resolution can differ. The options flow can force
        the full set on for hardware newer than the table.
        """
        entry = self._entry
        if entry is not None and entry.options.get(OPT_FORCE_FEATURES):
            return ALL_FEATURES

        led_type = None
        if self._device_info is not None:
            led_type = self._device_info.get("led_type")
        identity = self.identity
        return resolve_features(led_type, identity.cid, identity.pid)

    def supports(self, feature: str) -> bool:
        """Whether this panel supports one feature."""
        return feature in self.features

    async def _send_feature_command(
        self, feature: str, command: bytes, description: str
    ) -> bool:
        """Send a command that only some panels implement.

        Refuses rather than sending into the void: a command a panel does not
        implement produces no error and no effect, which is the most confusing
        possible outcome for an automation.
        """
        if not self.supports(feature):
            raise BleLedPixelFeatureUnsupported(
                f"This panel does not support {feature}. The vendor app does "
                f"not offer it for this model either. If yours does have it, "
                f"turn on the feature override in the integration options."
            )
        success = await self._send_with_reconnect(command)
        if success:
            _LOGGER.debug("%s", description)
        else:
            _LOGGER.error("Failed: %s", description)
        return success

    async def show_preset(self, preset: int, language: int = 0) -> bool:
        """Show one of the presets stored in the panel's firmware.

        Args:
            preset: Preset number, 1-20.
            language: Language byte for presets that contain wording.
        """
        return await self._send_feature_command(
            FEATURE_PRESETS,
            make_preset_command(preset, language),
            f"Showing preset {preset}",
        )

    async def set_scoreboard(self, home: int, away: int) -> bool:
        """Put two scores on the panel.

        Args:
            home: First score, 0-65535.
            away: Second score, 0-65535.
        """
        return await self._send_feature_command(
            FEATURE_SCOREBOARD,
            make_scoreboard_command(home, away),
            f"Scoreboard set to {home}:{away}",
        )

    async def set_countdown(
        self, running: bool, minutes: int = 0, seconds: int = 0
    ) -> bool:
        """Start or stop the countdown timer.

        Args:
            running: True starts counting down, False stops.
            minutes: Minutes to start from, 0-99.
            seconds: Seconds to start from, 0-59.
        """
        return await self._send_feature_command(
            FEATURE_COUNTDOWN,
            make_countdown_command(running, minutes, seconds),
            f"Countdown {'started' if running else 'stopped'} "
            f"at {minutes:02d}:{seconds:02d}",
        )

    async def set_stopwatch(self, running: bool) -> bool:
        """Start or stop the stopwatch.

        The panel counts on its own; the elapsed time cannot be read back.
        """
        return await self._send_feature_command(
            FEATURE_STOPWATCH,
            make_stopwatch_command(running),
            f"Stopwatch {'started' if running else 'stopped'}",
        )

    async def display_text_pypixelcolor(
        self,
        text: str,
        color: str = "ffffff",
        bg_color: str | None = None,
        font: str | None = None,
        animation: int = 0,
        speed: int = 80,
        rainbow_mode: int = 0,
        font_size: int = 16
    ) -> bool:
        """Display text using pypixelcolor.

        Args:
            text: Text to display (supports emojis)
            color: Text color in hex format (e.g., 'ffffff')
            bg_color: Background color in hex format (e.g., '000000'), or None for transparent
            font: Font name or file path. Resolved through fonts.py, so the
                library never sees one of its own volatile built-in names.
            animation: Effect code. See TEXT_EFFECTS in const.py for the
                names; 3 and 4 are omitted because pypixelcolor rejects
                them on anything but a 32x32 panel.
            speed: Animation speed (0-100)
            rainbow_mode: Rainbow mode (0-9)
            font_size: Font size (16, 32, 48, 64) defaults to 16

        Returns:
            True if text was sent successfully
        """
        try:
            # Get device info for height (honors options-flow override if set)
            base_info = await self.get_device_info()
            _, device_height = self._resolved_dimensions(base_info)

            if font_size > device_height:
                font_size = device_height
            if font_size < 16:
                font_size = 16
            char_height = floor(font_size / 16) * 16

            # Generate text commands using pypixelcolor
            commands = make_text_command(
                text=text,
                color=color,
                bg_color=bg_color,
                font=resolve_font_for_library(font),
                animation=animation,
                speed=speed,
                rainbow_mode=rainbow_mode,
                save_slot=0,
                char_height=char_height
            )

            # Send all command frames
            for i, command in enumerate(commands):
                _LOGGER.debug(
                    "Sending pypixelcolor text frame %d/%d: %d bytes",
                    i + 1,
                    len(commands),
                    len(command)
                )
                success = await self._send_with_reconnect(command)
                if not success:
                    _LOGGER.error("Failed to send text frame %d/%d", i + 1, len(commands))
                    return False

            _LOGGER.info(
                "Pypixelcolor text sent: '%s' (color=%s, bg=%s, font=%s, anim=%d, speed=%d, frames=%d)",
                text,
                color,
                bg_color or "none",
                font,
                animation,
                speed,
                len(commands)
            )
            return True

        except Exception as err:
            _LOGGER.error("Error displaying pypixelcolor text: %s", err)
            return False

    async def display_emoji(
        self,
        emoji: str,
        bg_color: str = "000000",
        width_override: int | None = None,
        height_override: int | None = None,
    ) -> bool:
        """Display an emoji as a Twemoji image, downloaded async and cached locally.

        Unlike display_text_pypixelcolor (which delegates emoji handling to
        pypixelcolor and currently triggers a blocking HTTP call inside the
        event loop), this method downloads the Twemoji PNG asynchronously,
        caches it under hass.config.path(".storage/ble_led_pixel_emoji_cache"), and
        composes it onto a canvas matching the device dimensions.

        Args:
            emoji: Unicode emoji character (e.g. '🔔', '🚨', '⚠️')
            bg_color: Background color in hex (default '000000')
            width_override: Optional canvas width override. Useful when the
                firmware reports incorrect dimensions for the physical panel.
                Defaults to device_info width.
            height_override: Optional canvas height override.

        Returns:
            True if the emoji was rendered and sent successfully.
        """
        try:
            base_info = await self.get_device_info()
            width = width_override or base_info["width"]
            height = height_override or base_info["height"]
            device_info = {**base_info, "width": width, "height": height}

            png_data = await render_emoji_to_png(self._hass, emoji, width, height, bg_color)
            if png_data is None:
                _LOGGER.error("Could not render emoji %r (download or cache miss)", emoji)
                return False

            commands = make_image_command(
                image_bytes=png_data,
                file_extension=".png",
                resize_method="crop",
                device_info_dict=device_info,
            )

            if not self.is_connected:
                await self.connect()

            for i, command in enumerate(commands):
                success = await self._send_with_reconnect(command)
                if not success:
                    _LOGGER.error("Failed to send emoji frame %d/%d", i + 1, len(commands))
                    return False

            _LOGGER.info(
                "Emoji %r displayed (%dx%d, %d frames)",
                emoji, width, height, len(commands),
            )
            return True

        except Exception as err:
            _LOGGER.exception("Error displaying emoji %r: %s", emoji, err)
            return False

    def _notification_handler(self, sender: Any, data: bytearray) -> None:
        """Handle notifications from the device."""
        _LOGGER.debug("Notification from %s: %s", sender, data.hex())
    
    @property
    def is_connected(self) -> bool:
        """Return True if connected to device."""
        return self._bluetooth.is_connected
    
    @property
    def power_state(self) -> bool:
        """Return current power state."""
        return self._power_state
    
    @property
    def address(self) -> str:
        """Return device address."""
        return self._address


# Export at module level for convenience
__all__ = [
    "BleLedPixelAPI",
    "BleLedPixelError",
    "BleLedPixelConnectionError",
    "BleLedPixelFeatureUnsupported",
    "BleLedPixelTimeoutError",
]
from .exceptions import (
    BleLedPixelConnectionError,
    BleLedPixelError,
    BleLedPixelFeatureUnsupported,
    BleLedPixelTimeoutError,
)
