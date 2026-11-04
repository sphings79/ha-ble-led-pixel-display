"""Power-state restore, the one-shot connect hook, and the send lock."""
import asyncio
import contextlib
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
    api.connected = True
    run(api._run_on_connected())     # link comes up: runs before connect returns
    run(api._run_on_connected())     # a later reconnect: nothing left to run
    assert ran == [1]


def test_failing_hook_does_not_break_connect():
    api = FakeApi(connected=False)

    async def job():
        raise RuntimeError("boom")

    api.call_when_connected(job)
    api.connected = True
    run(api._run_on_connected())
    assert api._on_connected == []


def test_hook_kept_when_link_drops_before_it_runs():
    api = FakeApi(connected=True)
    ran = []

    async def job():
        ran.append(1)

    api.call_when_connected(job)     # scheduled while connected
    api.connected = False            # ...and the link drops first
    run(api._hass.tasks[0])
    assert ran == [] and api._on_connected == [job]
    api.connected = True             # the watcher reconnects
    run(api._run_on_connected())
    assert ran == [1]


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
    fake_api = SimpleNamespace(_address="AA:BB", restoring=contextlib.nullcontext)
    result = run(common.restore_panel_display(hass, "Panel", fake_api))
    assert result is sent
    assert calls == (["Panel"] if sent else [])


def _client():
    client = BluetoothClient.__new__(BluetoothClient)
    client._send_lock = asyncio.Lock()
    client._content_writes = 0
    client._address = "AA:BB"
    return client


def test_sends_never_overlap():
    client = _client()
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


def test_restore_gives_way_to_newer_content():
    client = _client()
    sent = []

    async def record(plan, *args):
        sent.append(plan)
        return True

    client._send_plan_unlocked = record

    async def restore():
        with client.restoring():
            await client.send_plan("restore-1")
            await asyncio.sleep(0.01)        # an automation sends meanwhile
            await client.send_plan("restore-2")

    async def automation():
        await asyncio.sleep(0.005)
        await client.send_plan("automation")

    async def main():
        await asyncio.gather(restore(), automation())

    asyncio.run(main())
    assert sent == ["restore-1", "automation"]


def test_restore_alone_sends_everything():
    client = _client()
    sent = []

    async def record(plan, *args):
        sent.append(plan)
        return True

    client._send_plan_unlocked = record

    async def restore():
        with client.restoring():
            await client.send_plan("a")
            await client.send_plan("b")

    asyncio.run(restore())
    assert sent == ["a", "b"]
    # Restore writes are not counted, so a later restore is not blocked.
    assert client._content_writes == 0
