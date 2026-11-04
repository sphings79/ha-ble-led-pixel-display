"""Power-state restore, the one-shot connect hook, and the send lock."""
import asyncio
from types import SimpleNamespace

import pytest

from tests import ha_stubs

ha_stubs.install()

from custom_components.ble_led_pixel import api as api_module  # noqa: E402
from custom_components.ble_led_pixel import common, switch  # noqa: E402
from custom_components.ble_led_pixel.bluetooth.client import (  # noqa: E402
    BluetoothClient,
)


def run(coro):
    return asyncio.run(coro)


class FakeApi:
    """The slice of BleLedPixelAPI the hook and the switch use."""

    def __init__(self, connected: bool) -> None:
        self._hass = ha_stubs.FakeHass()
        self._address = "AA:BB"
        self._on_connected = []
        self.connected = connected
        self._power_state = True

    is_connected = property(lambda self: self.connected)
    power_state = api_module.BleLedPixelAPI.power_state
    restore_power_state = api_module.BleLedPixelAPI.restore_power_state
    call_when_connected = api_module.BleLedPixelAPI.call_when_connected
    _run_on_connected = api_module.BleLedPixelAPI._run_on_connected


def test_hook_runs_now_when_connected():
    api = FakeApi(connected=True)
    ran = []

    async def job():
        ran.append(1)

    api.call_when_connected(job)
    assert len(api._hass.tasks) == 1
    run(api._hass.tasks[0])
    assert ran == [1] and api._on_connected == []


def test_hook_waits_for_the_link_and_runs_once():
    api = FakeApi(connected=False)
    ran = []

    async def job():
        ran.append(1)

    api.call_when_connected(job)
    assert api._hass.tasks == [] and ran == []
    run(api._run_on_connected())     # link comes up: runs before connect returns
    run(api._run_on_connected())     # a later reconnect: nothing left to run
    assert ran == [1]


def test_failing_hook_does_not_break_connect():
    api = FakeApi(connected=False)

    async def job():
        raise RuntimeError("boom")

    api.call_when_connected(job)
    run(api._run_on_connected())
    assert api._on_connected == []


def _restored_switch(last_state):
    api = FakeApi(connected=True)
    entity = switch.BleLedPixelSwitch.__new__(switch.BleLedPixelSwitch)
    entity._api = api
    entity._commanded = False
    entity._is_on = api.power_state

    async def get_last_state():
        return last_state

    entity.async_get_last_state = get_last_state
    run(switch.BleLedPixelSwitch.async_added_to_hass(entity))
    return entity, api


def test_switch_starts_on_with_no_history():
    entity, api = _restored_switch(None)
    assert entity.is_on is True and api.power_state is True
    assert entity.extra_state_attributes == {"commanded": False}


def test_switch_restores_commanded_off():
    state = SimpleNamespace(state="off", attributes={"commanded": True})
    entity, api = _restored_switch(state)
    assert entity.is_on is False and api.power_state is False
    assert entity.extra_state_attributes == {"commanded": True}


def test_switch_ignores_old_uncommanded_off():
    # Versions before this always saved "off" without the attribute.
    entity, _ = _restored_switch(SimpleNamespace(state="off", attributes={}))
    assert entity.is_on is True


class FakeStates:
    def __init__(self, states):
        self._states = states

    def get(self, entity_id):
        value = self._states.get(entity_id)
        return SimpleNamespace(state=value) if value else None


@pytest.mark.parametrize(
    ("auto", "power", "sent"),
    [("on", "on", True), ("on", None, True), ("off", "on", False), ("on", "off", False)],
)
def test_restore_display_respects_auto_update_and_power(monkeypatch, auto, power, sent):
    ids = {"auto_update": "switch.auto", "power": "switch.power"}
    monkeypatch.setattr(
        common, "get_entity_id_by_unique_id",
        lambda hass, address, suffix, platform=None: ids[suffix],
    )
    calls = []

    async def fake_update(hass, name, api, text=None):
        calls.append(name)
        return True

    monkeypatch.setattr(common, "update_panel_display", fake_update)
    hass = SimpleNamespace(states=FakeStates({"switch.auto": auto, "switch.power": power}))
    result = run(common.restore_panel_display(hass, "Panel", SimpleNamespace(_address="AA:BB")))
    assert result is sent
    assert calls == (["Panel"] if sent else [])


def test_sends_never_overlap():
    client = BluetoothClient.__new__(BluetoothClient)
    client._send_lock = asyncio.Lock()
    active = []
    overlaps = []

    async def slow_send(*args):
        if active:
            overlaps.append(args)
        active.append(args)
        await asyncio.sleep(0.01)
        active.pop()
        return True

    client._send_plan_unlocked = slow_send
    client._send_command_unlocked = slow_send

    async def main():
        await asyncio.gather(
            client.send_plan("plan-a"),
            client.send_command(b"\x01"),
            client.send_plan("plan-b"),
        )

    asyncio.run(main())
    assert overlaps == []
