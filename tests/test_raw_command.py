"""send_raw_command: administrators only, one send per panel, no wildcard."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
import voluptuous as vol

from tests import ha_stubs

ha_stubs.install()

from custom_components.ble_led_pixel import services  # noqa: E402
from custom_components.ble_led_pixel.const import DOMAIN  # noqa: E402
from custom_components.ble_led_pixel.exceptions import BleLedPixelConnectionError  # noqa: E402


def run(coro):
    return asyncio.run(coro)


class FakeApi:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    async def send_raw_frames(self, frames, gap, listen):
        self.calls.append((frames, gap, listen))
        if self.error:
            raise self.error
        return [{"sent": frames[0].hex(" ")}]


class FakeRegistry:
    def __init__(self, entries):
        self.entries = entries

    def async_get(self, entity_id):
        return self.entries.get(entity_id)


def entry(platform=DOMAIN, entry_id="e1"):
    return SimpleNamespace(platform=platform, config_entry_id=entry_id)


@pytest.fixture
def wired(monkeypatch):
    """Patch the Home Assistant helpers services.py leans on."""
    state = SimpleNamespace(ids=set(), entries={})

    async def extract(call):
        return state.ids

    monkeypatch.setattr(
        services,
        "service",
        SimpleNamespace(
            async_extract_entity_ids=extract,
            remove_entity_service_fields=lambda call: dict(call.data),
        ),
    )
    monkeypatch.setattr(
        services, "er", SimpleNamespace(async_get=lambda hass: FakeRegistry(state.entries))
    )
    return state


def call(**data):
    return SimpleNamespace(data=data, return_response=True, service="send_raw_command")


def hass_with(**apis):
    return SimpleNamespace(data={DOMAIN: apis})


FRAMES = [bytes.fromhex("0400 0101")]


def test_hex_frames_accept_spaces_and_prefix():
    assert services._hex_frame("05 00 08 80 01") == bytes.fromhex("0500088001")
    assert services._hex_frame("0x0400 0101") == bytes.fromhex("04000101")


@pytest.mark.parametrize("bad", ["", "zz", "0", "00" * 513])
def test_hex_frames_reject_junk(bad):
    with pytest.raises(vol.Invalid):
        services._hex_frame(bad)


def test_registered_as_an_admin_service_only():
    platform, admin = [], []
    fake = SimpleNamespace(
        async_register_platform_entity_service=lambda hass, domain, name, **kw: platform.append(name),
        async_register_admin_service=lambda hass, domain, name, *a, **kw: admin.append(name),
    )
    original = services.service
    services.service = fake
    try:
        services.async_setup_services(SimpleNamespace())
    finally:
        services.service = original
    assert "send_raw_command" in admin
    assert "send_raw_command" not in platform


def test_one_send_per_panel_however_many_entities_are_targeted(wired):
    api = FakeApi()
    wired.ids = {"text.p_display", "number.p_slot"}
    wired.entries = {"text.p_display": entry(), "number.p_slot": entry()}
    result = run(services._async_send_raw_command(
        hass_with(e1=api), call(frames=FRAMES, gap=0.5, listen=2.0)
    ))
    assert len(api.calls) == 1
    assert list(result) == ["number.p_slot"]
    assert result["number.p_slot"]["log"] == [{"sent": "04 00 01 01"}]


def test_other_integrations_entities_are_ignored(wired):
    api = FakeApi()
    wired.ids = {"light.kitchen"}
    wired.entries = {"light.kitchen": entry(platform="hue")}
    with pytest.raises(Exception, match="needs a BLE LED Pixel panel"):
        run(services._async_send_raw_command(
            hass_with(e1=api), call(frames=FRAMES, gap=0.5, listen=2.0)
        ))
    assert api.calls == []


def test_all_is_refused(wired):
    api = FakeApi()
    wired.ids = {"text.p_display"}
    wired.entries = {"text.p_display": entry()}
    with pytest.raises(Exception, match="explicit target"):
        run(services._async_send_raw_command(
            hass_with(e1=api),
            call(entity_id="all", frames=FRAMES, gap=0.5, listen=2.0),
        ))
    assert api.calls == []


def test_an_unreachable_panel_is_reported(wired):
    api = FakeApi(error=BleLedPixelConnectionError("down"))
    wired.ids = {"text.p_display"}
    wired.entries = {"text.p_display": entry()}
    with pytest.raises(Exception, match="Could not reach the panel"):
        run(services._async_send_raw_command(
            hass_with(e1=api), call(frames=FRAMES, gap=0.5, listen=2.0)
        ))
