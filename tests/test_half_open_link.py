"""A link whose notifications cannot be enabled must not count as connected."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from bleak.exc import BleakError

from tests import ha_stubs

ha_stubs.install()

from custom_components.ble_led_pixel.bluetooth import client as client_module  # noqa: E402
from custom_components.ble_led_pixel.bluetooth.client import BluetoothClient  # noqa: E402
from custom_components.ble_led_pixel.exceptions import BleLedPixelConnectionError  # noqa: E402


class FakeBleakClient:
    """Minimal stand-in for a connected BleakClient."""

    def __init__(self, start_error=None, stop_error=None, disconnect_error=None):
        self.is_connected = True
        self.start_error = start_error
        self.stop_error = stop_error
        self.disconnect_error = disconnect_error
        self.disconnect_calls = 0
        self.stop_calls = 0

    async def start_notify(self, uuid, handler):
        if self.start_error:
            raise self.start_error

    async def stop_notify(self, uuid):
        self.stop_calls += 1
        if self.stop_error:
            raise self.stop_error

    async def disconnect(self):
        self.disconnect_calls += 1
        if self.disconnect_error:
            raise self.disconnect_error
        self.is_connected = False


def make_client(monkeypatch, fake):
    async def fake_establish(*args, **kwargs):
        return fake

    async def fake_get_ble_device(self):
        return SimpleNamespace(name="panel")

    monkeypatch.setattr(client_module, "establish_connection", fake_establish)
    monkeypatch.setattr(BluetoothClient, "_get_ble_device", fake_get_ble_device)
    return BluetoothClient(SimpleNamespace(), "AA:BB:CC:DD:EE:FF")


def test_failed_start_notify_drops_the_link(monkeypatch):
    fake = FakeBleakClient(start_error=BleakError("StartNotify doesn't exist"))
    client = make_client(monkeypatch, fake)

    with pytest.raises(BleLedPixelConnectionError):
        asyncio.run(client.connect(lambda sender, data: None))

    assert not client.is_connected
    assert client._connected is False
    assert client._client is None
    assert client._ack_mgr is None
    assert fake.disconnect_calls == 1


def test_a_failing_disconnect_while_dropping_does_not_mask_the_error(monkeypatch):
    fake = FakeBleakClient(
        start_error=BleakError("Unlikely Error"),
        disconnect_error=BleakError("Not connected"),
    )
    client = make_client(monkeypatch, fake)

    with pytest.raises(BleLedPixelConnectionError, match="Unlikely Error"):
        asyncio.run(client.connect(lambda sender, data: None))

    assert not client.is_connected
    assert client._client is None


def test_cancelled_start_notify_also_drops_the_link(monkeypatch):
    fake = FakeBleakClient(start_error=asyncio.CancelledError())
    client = make_client(monkeypatch, fake)

    async def run():
        await client._connect_locked(lambda sender, data: None)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())

    assert client._connected is False
    assert client._client is None
    assert fake.disconnect_calls == 1


def test_successful_connect_keeps_the_link(monkeypatch):
    fake = FakeBleakClient()
    client = make_client(monkeypatch, fake)

    assert asyncio.run(client.connect(lambda sender, data: None)) is True

    assert client.is_connected
    assert fake.disconnect_calls == 0


def test_disconnect_still_disconnects_when_stop_notify_fails(monkeypatch):
    fake = FakeBleakClient(stop_error=BleakError("No notify session started"))
    client = make_client(monkeypatch, fake)
    asyncio.run(client.connect(lambda sender, data: None))

    asyncio.run(client.disconnect())

    assert fake.stop_calls == 1
    assert fake.disconnect_calls == 1
    assert client._connected is False
