"""The setup picker lists panels only, with a way out to every device."""
from __future__ import annotations

import asyncio

import pytest

from tests import ha_stubs

ha_stubs.install()

from custom_components.ble_led_pixel import config_flow  # noqa: E402
from custom_components.ble_led_pixel.bluetooth import scanner  # noqa: E402

PANEL = {"address": "59:31:7E:9E:1E:82", "name": "LED_BLE_7E9E1E82", "rssi": -60, "is_compatible": True}
SET_UP = {"address": "AA:AA:AA:AA:AA:01", "name": "LED_BLE_AAAA0001", "rssi": -70, "is_compatible": True}
DESK = {"address": "BB:BB:BB:BB:BB:02", "name": "Desk", "rssi": -66, "is_compatible": False}
SPEAKER = {"address": "CC:CC:CC:CC:CC:03", "name": "Speaker", "rssi": -80, "is_compatible": False}


class Flow(config_flow.ConfigFlow):
    def __init__(self, configured=(), ignored=()):
        super().__init__()
        self._ignored = set(ignored)
        self.hass = object()
        self._configured = set(configured)
        self.created = None

    def _async_current_ids(self, include_ignore=True):
        # Home Assistant counts ignored entries unless told not to.
        return self._configured | (self._ignored if include_ignore else set())

    def async_show_form(self, step_id, data_schema=None, errors=None, description_placeholders=None):
        options = dict(data_schema.schema[next(iter(data_schema.schema))].container) if data_schema else {}
        return {"type": "form", "step_id": step_id, "options": options, "errors": errors or {}}

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        pass

    def async_create_entry(self, title, data):
        self.created = data
        return {"type": "create_entry", "data": data}

    def async_abort(self, reason):
        return {"type": "abort", "reason": reason}


@pytest.fixture
def nearby(monkeypatch):
    devices = [DESK, SET_UP, PANEL, SPEAKER]
    monkeypatch.setattr(config_flow, "discover_panels", lambda hass, return_all=False: list(devices))
    return devices


def run(coro):
    return asyncio.run(coro)


def test_lists_only_panels_not_yet_set_up(nearby):
    form = run(Flow(configured={SET_UP["address"]}).async_step_user())
    assert form["step_id"] == "user"
    assert list(form["options"]) == [PANEL["address"], "all", "manual"]
    assert form["options"]["all"] == "Show all Bluetooth devices (2 more)"
    assert form["errors"] == {}


def test_no_panels_still_offers_all_and_manual(nearby):
    nearby[:] = [DESK]
    form = run(Flow().async_step_user())
    assert form["errors"] == {"base": "no_devices_found"}
    assert list(form["options"]) == ["all", "manual"]


def test_show_all_lists_everything_with_panels_starred_first(nearby):
    flow = Flow(configured={SET_UP["address"]})
    run(flow.async_step_user())
    form = run(flow.async_step_user({"device": "all"}))
    assert form["step_id"] == "pick_any"
    assert list(form["options"]) == [PANEL["address"], DESK["address"], SPEAKER["address"], "manual"]
    assert form["options"][PANEL["address"]].startswith("⭐ ")
    assert not form["options"][DESK["address"]].startswith("⭐")


def test_connect_failure_keeps_the_error_on_the_same_step(nearby, monkeypatch):
    async def fail(hass, data):
        raise config_flow.CannotConnect

    monkeypatch.setattr(config_flow, "validate_input", fail)
    flow = Flow()
    run(flow.async_step_user())
    form = run(flow.async_step_user({"device": PANEL["address"]}))
    assert form["step_id"] == "user"
    assert form["errors"] == {"base": "cannot_connect"}

    run(flow.async_step_user({"device": "all"}))
    form = run(flow.async_step_pick_any({"device": DESK["address"]}))
    assert form["step_id"] == "pick_any"
    assert form["errors"] == {"base": "cannot_connect"}


def test_picking_a_panel_creates_the_entry(nearby, monkeypatch):
    async def ok(hass, data):
        return {"title": "LED panel 9E:1E:82", "address": data["address"]}

    monkeypatch.setattr(config_flow, "validate_input", ok)
    flow = Flow()
    run(flow.async_step_user())
    result = run(flow.async_step_user({"device": PANEL["address"]}))
    assert result["type"] == "create_entry"
    assert flow.created["address"] == PANEL["address"]


class Info:
    def __init__(self, name, uuids=(), mfr=None):
        self.address = "DD:DD:DD:DD:DD:04"
        self.name = name
        self.rssi = -50
        self.service_uuids = list(uuids)
        self.manufacturer_data = mfr or {}


def test_scanner_recognises_the_panel_service_uuid(monkeypatch):
    infos = [Info("Rebranded", uuids=["0000FA01-0000-1000-8000-00805F9B34FB"]), Info("Desk")]
    monkeypatch.setattr(
        scanner.bluetooth, "async_discovered_service_info", lambda hass, connectable=True: infos, raising=False
    )
    found = scanner.discover_panels(object(), return_all=True)
    assert [d["is_compatible"] for d in found] == [True, False]


def test_ignored_panel_can_still_be_set_up_by_hand(nearby):
    form = run(Flow(ignored={PANEL["address"]}).async_step_user())
    assert PANEL["address"] in form["options"]
