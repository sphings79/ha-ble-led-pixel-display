"""Bluetooth client management for BLE LED pixel panels."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextvars import ContextVar
from typing import Any, Callable, TYPE_CHECKING

from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from homeassistant.components import bluetooth

from ..const import WRITE_UUID, NOTIFY_UUID, REDISCOVERY_ATTEMPTS, REDISCOVERY_DELAY
from ..exceptions import BleLedPixelConnectionError

# Set while a restore is running in the current task: the number of content
# writes from elsewhere at the moment it began. See BluetoothClient.restoring().
_RESTORE_SINCE: ContextVar[int | None] = ContextVar("ble_led_pixel_restore_since", default=None)

try:
    from pypixelcolor.lib.transport.send_plan import send_plan as pypixelcolor_send_plan
    from pypixelcolor.lib.transport.ack_manager import AckManager
except ImportError:
    pypixelcolor_send_plan = None
    AckManager = None

_LOGGER = logging.getLogger(__name__)


class BluetoothClient:
    """Manages Bluetooth connection and communication.

    Notification handling: a SINGLE notify subscription is enabled once in
    connect() and stays active for the whole connection lifetime, exactly
    matching pypixelcolor's own reference client (DeviceSession), which
    creates one AckManager at connect() and reuses it for every command
    without ever stopping/restarting notifications in between.

    An earlier version of this file stopped and restarted notifications
    around every single send_command()/send_plan() call. That repeated
    stop/start churn is a likely source of dropped ACKs on real hardware
    (a notification arriving in the brief window between stop and start
    would be silently lost) - especially for images, whose multi-chunk
    transfer depends on ACKs arriving reliably window by window.
    """

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialize Bluetooth client.

        Args:
            hass: Home Assistant instance
            address: Bluetooth MAC address
        """
        self._hass = hass
        self._address = address
        self._client: BleakClientWithServiceCache | None = None
        self._connected = False
        self._notification_handler: Callable | None = None
        self._ack_mgr = None
        self._extra_listeners: list[Callable[[Any, bytearray], None]] = []
        # Serializes connection attempts. Several entities updating at once
        # would otherwise each start their own connect and stampede the radio.
        self._connect_lock = asyncio.Lock()
        # Serializes writes. A multi-window plan shares the AckManager's
        # acknowledgement events with everything else on the link, so two
        # sends at once interleave their chunks and steal each other's ACKs.
        self._send_lock = asyncio.Lock()
        # Writes that changed what the panel shows, not counting restores.
        self._content_writes = 0

    def _disconnected_callback(self, client: BleakClientWithServiceCache) -> None:
        """Called when device disconnects."""
        _LOGGER.warning("LED panel %s disconnected", self._address)
        self._connected = False

    def _dispatch_notification(self, sender: Any, data: bytearray) -> None:
        """Single persistent notify callback: fan out to all consumers.

        Called for every notification for the whole connection lifetime.
        Forwards to: the AckManager (for send_plan's per-window ACKs), any
        temporary listeners registered by send_command(), and the original
        handler passed to connect() (currently just debug logging).
        """
        if self._ack_mgr is not None:
            try:
                self._ack_mgr.make_notify_handler()(sender, data)
            except Exception as err:
                _LOGGER.debug("AckManager handler error: %s", err)

        for listener in list(self._extra_listeners):
            try:
                listener(sender, data)
            except Exception as err:
                _LOGGER.debug("Extra notification listener error: %s", err)

        if self._notification_handler:
            try:
                self._notification_handler(sender, data)
            except Exception as err:
                _LOGGER.debug("Notification handler error: %s", err)

    async def _get_ble_device(self):
        """Return the BLEDevice, asking for a re-scan when the cache is stale.

        After a dropped link Home Assistant's Bluetooth manager may have lost
        track of the panel even though it is still advertising perfectly well.
        Without this, a reconnect fails with "Device not found" and nothing
        ever recovers until the config entry is reloaded by hand.
        """
        ble_device = bluetooth.async_ble_device_from_address(
            self._hass, self._address, connectable=True
        )
        if ble_device:
            return ble_device

        _LOGGER.debug(
            "Device %s not in the Bluetooth cache, asking for rediscovery",
            self._address,
        )
        bluetooth.async_rediscover_address(self._hass, self._address)
        for _ in range(REDISCOVERY_ATTEMPTS):
            await asyncio.sleep(REDISCOVERY_DELAY)
            ble_device = bluetooth.async_ble_device_from_address(
                self._hass, self._address, connectable=True
            )
            if ble_device:
                _LOGGER.debug("Device %s reappeared after rediscovery", self._address)
                return ble_device
        return None

    async def connect(self, notification_handler: Callable[[Any, bytearray], None]) -> bool:
        """Connect to the LED panel.

        Args:
            notification_handler: Callback for device notifications

        Returns:
            True if connected successfully

        Raises:
            BleLedPixelConnectionError: If connection fails
        """
        async with self._connect_lock:
            return await self._connect_locked(notification_handler)

    async def ensure_connected(self) -> bool:
        """Return True if connected, reconnecting when the link was lost.

        Unlike connect() this never raises - it is the entry point for command
        paths that want to recover quietly. Returns False when no connection
        was ever established (nothing to restore) or the attempt failed.
        """
        if self.is_connected:
            return True
        if self._notification_handler is None:
            return False

        async with self._connect_lock:
            # Another caller may have reconnected while we waited for the lock.
            if self.is_connected:
                return True
            try:
                return await self._connect_locked(self._notification_handler)
            except BleLedPixelConnectionError as err:
                _LOGGER.warning("Reconnect to %s failed: %s", self._address, err)
                return False

    async def _connect_locked(self, notification_handler: Callable[[Any, bytearray], None]) -> bool:
        """Establish the link. Caller must hold the connect lock."""
        _LOGGER.debug("Connecting to LED panel at %s", self._address)

        try:
            ble_device = await self._get_ble_device()

            if not ble_device:
                raise BleLedPixelConnectionError(
                    f"Device {self._address} not found. "
                    "Ensure the device is powered on and in range."
                )

            # Use establish_connection with service caching for reliable connection
            # This handles retries, timeouts, and works with Bluetooth proxies
            _LOGGER.debug("Establishing connection to %s using bleak-retry-connector", self._address)
            self._client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                ble_device.name or "LED panel Display",
                disconnected_callback=self._disconnected_callback,
                max_attempts=3,
            )

            self._connected = True
            self._notification_handler = notification_handler

            # Create ONE persistent AckManager for the whole connection, and
            # enable notifications ONCE via the dispatcher above. Never
            # stopped/restarted again until disconnect().
            if AckManager is not None:
                self._ack_mgr = AckManager()

            await self._client.start_notify(NOTIFY_UUID, self._dispatch_notification)
            _LOGGER.info("Successfully connected to LED panel")
            return True

        except BleakError as err:
            _LOGGER.error("Failed to connect to %s: %s", self._address, err)
            raise BleLedPixelConnectionError(f"Connection failed: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected error connecting to %s: %s", self._address, err)
            raise BleLedPixelConnectionError(f"Connection failed: {err}") from err

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._client and self._connected:
            try:
                await self._client.stop_notify(NOTIFY_UUID)
                await self._client.disconnect()
                _LOGGER.debug("Disconnected from LED panel")
            except BleakError as err:
                _LOGGER.error("Error during disconnect: %s", err)
            finally:
                self._connected = False
                self._client = None  # Don't reuse client - create fresh for next connection
                self._ack_mgr = None
                self._extra_listeners = []

    async def _send_command_unlocked(self, command: bytes) -> bool:
        """Send a small, single-packet command and log any response.

        Uses the persistent notification subscription (no stop/start
        churn): registers a temporary listener in self._extra_listeners
        for the duration of this call only.

        Args:
            command: Command bytes to send

        Returns:
            True if command was sent successfully

        Raises:
            BleLedPixelConnectionError: If not connected
        """
        if not self._connected or not self._client:
            raise BleLedPixelConnectionError("Device not connected")

        response_data = []
        response_received = asyncio.Event()

        def response_handler(sender: Any, data: bytearray) -> None:
            response_data.append(bytes(data))
            response_received.set()
            _LOGGER.info("Device response: %s", data.hex())

        self._extra_listeners.append(response_handler)
        try:
            _LOGGER.debug("Sending command: %s", command.hex())
            await self._client.write_gatt_char(WRITE_UUID, command)

            try:
                await asyncio.wait_for(response_received.wait(), timeout=2.0)
                if response_data:
                    _LOGGER.info("Command response received: %s", response_data[-1].hex())
                else:
                    _LOGGER.debug("No response received within timeout")
            except asyncio.TimeoutError:
                _LOGGER.debug("No response received within 2 seconds")

            return True
        except BleakError as err:
            _LOGGER.error("Failed to send command: %s", err)
            return False
        finally:
            if response_handler in self._extra_listeners:
                self._extra_listeners.remove(response_handler)

    async def _send_command_wait_response_unlocked(self, command: bytes, timeout: float = 5.0) -> bytes | None:
        """Send a command and return the raw response bytes, if any arrive.

        Same persistent-notification mechanism as send_command(), but
        returns the response payload instead of a bool - for callers that
        need to parse it (e.g. device info queries).

        Args:
            command: Command bytes to send.
            timeout: How long to wait for a response, in seconds.

        Returns:
            The response bytes, or None if no response arrived in time.

        Raises:
            BleLedPixelConnectionError: If not connected.
        """
        if not self._connected or not self._client:
            raise BleLedPixelConnectionError("Device not connected")

        response_data = []
        response_received = asyncio.Event()

        def response_handler(sender: Any, data: bytearray) -> None:
            response_data.append(bytes(data))
            response_received.set()

        self._extra_listeners.append(response_handler)
        try:
            await self._client.write_gatt_char(WRITE_UUID, command)
            try:
                await asyncio.wait_for(response_received.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                _LOGGER.debug("No response received within %.1f seconds", timeout)
                return None
            return response_data[-1] if response_data else None
        finally:
            if response_handler in self._extra_listeners:
                self._extra_listeners.remove(response_handler)

    async def _send_plan_unlocked(self, plan, ack_timeout: float = 8.0) -> bool:
        """Send a pypixelcolor SendPlan using the library's own transport.

        Uses the persistent AckManager created in connect() (no stop/start
        of notifications): each window is split into plan.chunk_size (244)
        byte chunks, and a per-window ACK is awaited via the AckManager
        before continuing. Needed for any multi-byte payload (currently:
        images).

        Args:
            plan: A pypixelcolor SendPlan object (e.g. from send_image_hex).
            ack_timeout: How long to wait for each window's ACK, in
                seconds. pypixelcolor's own default (8s) is tuned for small
                payloads; a complex GIF may need noticeably longer for the
                device to process before it acks - callers sending images/
                GIFs should pass a higher value (e.g. 20-30s).

        Returns:
            True if the plan was sent and acknowledged successfully.

        Raises:
            BleLedPixelConnectionError: If not connected.
            ImportError: If pypixelcolor is not available.
        """
        if pypixelcolor_send_plan is None:
            raise ImportError("pypixelcolor library is not installed")
        if not self._connected or not self._client:
            raise BleLedPixelConnectionError("Device not connected")
        if self._ack_mgr is None:
            raise BleLedPixelConnectionError("AckManager not initialized - not connected?")

        try:
            result = await pypixelcolor_send_plan(
                self._client, plan, self._ack_mgr, ack_timeout=ack_timeout,
            )
            if not result.success:
                _LOGGER.error("send_plan '%s' failed: %s", plan.id, result.message)
            return result.success
        except Exception as err:
            _LOGGER.error("Error sending plan '%s': %s", plan.id, err)
            return False

    @contextlib.contextmanager
    def restoring(self):
        """Mark the sends made inside this block as a restore of saved state.

        A restore must never replace content that was sent after it was
        started. Its writes are therefore dropped, under the send lock, once
        anything else has changed the panel's content since the block began.
        """
        token = _RESTORE_SINCE.set(self._content_writes)
        try:
            yield
        finally:
            _RESTORE_SINCE.reset(token)

    @staticmethod
    def in_restore() -> bool:
        """Whether the current task is inside a restoring() block."""
        return _RESTORE_SINCE.get() is not None

    def _claim_content_write(self) -> bool:
        """Account for a content write; False when a restore is superseded.

        Called with the send lock held, so the check and the write that
        follows cannot be separated by another sender.
        """
        since = _RESTORE_SINCE.get()
        if since is None:
            self._content_writes += 1
            return True
        if self._content_writes != since:
            _LOGGER.debug(
                "Skipping restore write to %s: newer content was sent", self._address
            )
            return False
        return True

    async def send_command(
        self,
        command: bytes,
        content: bool = False,
        still_current: Callable[[], bool] | None = None,
    ) -> bool:
        """Send a small, single-packet command and log any response.

        Args:
            command: Command bytes to send.
            content: True for commands that change what the panel shows
                (clock mode, presets, scoreboard), as opposed to settings
                such as power, brightness or the password.
            still_current: As for send_plan: asked once the link is ours,
                and the command is dropped if newer content was requested.

        Raises:
            BleLedPixelConnectionError: If not connected
        """
        async with self._send_lock:
            if still_current is not None and not still_current():
                _LOGGER.debug("Dropping a superseded command")
                return True
            if content and not self._claim_content_write():
                return True
            return await self._send_command_unlocked(command)

    async def send_raw_frames(
        self, frames: list[bytes], gap: float = 0.5, listen: float = 2.0
    ) -> list[dict[str, Any]]:
        """Write frames as given and collect every notification (debug only).

        For trying commands on hardware. Frames go out one after another on
        this link, gap seconds apart, and the panel is listened to for listen
        seconds after the last one. Nothing is checked or retried.

        Returns:
            One entry per write and per notification, in the order they
            happened: {"sent": hex} or {"received": hex}.

        Raises:
            BleLedPixelConnectionError: If not connected.
        """
        async with self._send_lock:
            if not self._connected or not self._client:
                raise BleLedPixelConnectionError("Device not connected")
            self._claim_content_write()
            log: list[dict[str, Any]] = []

            def listener(sender: Any, data: bytearray) -> None:
                log.append({"received": bytes(data).hex(" ")})

            self._extra_listeners.append(listener)
            try:
                for index, frame in enumerate(frames):
                    if index:
                        await asyncio.sleep(gap)
                    log.append({"sent": frame.hex(" ")})
                    await self._client.write_gatt_char(WRITE_UUID, frame)
                await asyncio.sleep(listen)
            finally:
                if listener in self._extra_listeners:
                    self._extra_listeners.remove(listener)
            return log

    async def send_command_wait_response(self, command: bytes, timeout: float = 5.0) -> bytes | None:
        """Send a command and return the raw response bytes, if any arrive.

        Raises:
            BleLedPixelConnectionError: If not connected.
        """
        async with self._send_lock:
            return await self._send_command_wait_response_unlocked(command, timeout)

    async def send_plan(
        self, plan, ack_timeout: float = 8.0, still_current: Callable[[], bool] | None = None
    ) -> bool:
        """Send a pypixelcolor SendPlan, one at a time on this link.

        still_current, if given, is asked once the link is ours: a plan that
        was overtaken while it waited (rendering, reconnecting, or queued
        behind another send) is dropped there rather than sent over the newer
        content.

        Raises:
            BleLedPixelConnectionError: If not connected.
            ImportError: If pypixelcolor is not available.
        """
        async with self._send_lock:
            if still_current is not None and not still_current():
                _LOGGER.debug("Dropping a superseded plan")
                return True
            if not self._claim_content_write():
                return True
            return await self._send_plan_unlocked(plan, ack_timeout)

    @property
    def is_connected(self) -> bool:
        """Return True if connected to device."""
        return self._connected and self._client and self._client.is_connected

    @property
    def address(self) -> str:
        """Return device address."""
        return self._address
