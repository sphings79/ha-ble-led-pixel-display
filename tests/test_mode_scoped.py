"""Settings grey out in modes that do not use them, and survive restarts."""
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import pytest

from tests import ha_stubs

ha_stubs.install()

from custom_components.ble_led_pixel import (  # noqa: E402
    button,
    entity,
    light,
    number,
    select,
    switch,
    text,
)
from custom_components.ble_led_pixel import api as api_module  # noqa: E402

BOTH = {"text", "textimage"}
SCOPES = {
    text.BleLedPixelTextDisplay: BOTH,
    select.BleLedPixelFontSelect: BOTH,
    light.BleLedPixelTextColorLight: BOTH,
    light.BleLedPixelBackgroundColorLight: BOTH,
    button.BleLedPixelSaveSlotButton: BOTH,
    select.BleLedPixelTextEffectSelect: {"text"},
    select.BleLedPixelTextGradientSelect: {"text"},
    select.BleLedPixelTextSizeSelect: {"text"},
    number.BleLedPixelTextSpeed: {"text"},
    number.BleLedPixelFontSize: {"textimage"},
    number.BleLedPixelLineSpacing: {"textimage"},
    switch.BleLedPixelAntialiasingSwitch: {"textimage"},
    select.BleLedPixelClockStyleSelect: {"clock"},
    switch.BleLedPixelClock24HSwitch: {"clock"},
    switch.BleLedPixelClockShowDateSwitch: {"clock"},
    button.BleLedPixelSyncTimeButton: {"clock"},
}
ALWAYS = [
    select.BleLedPixelModeSelect,
    switch.BleLedPixelAutoUpdateSwitch,
    number.BleLedPixelSlot,
    button.BleLedPixelShowSlotButton,
    button.BleLedPixelClearSlotButton,
    button.BleLedPixelUpdateButton,
]


def with_mode(cls, mode):
    obj = cls.__new__(cls)
    obj._api = SimpleNamespace(current_mode=mode)
    return obj


@pytest.mark.parametrize("cls", list(SCOPES))
@pytest.mark.parametrize("mode", ["text", "textimage", "clock"])
def test_available_only_in_its_modes(cls, mode):
    assert with_mode(cls, mode).available is (mode in SCOPES[cls])


@pytest.mark.parametrize("cls", list(SCOPES))
def test_everything_shows_before_the_mode_is_known(cls):
    assert with_mode(cls, None).available is True


@pytest.mark.parametrize("cls", ALWAYS)
def test_mode_neutral_entities_are_not_scoped(cls):
    assert not issubclass(cls, entity.ModeScopedEntity)


def test_mode_listeners_hear_each_change_once():
    api = api_module.BleLedPixelAPI.__new__(api_module.BleLedPixelAPI)
    api.current_mode = None
    api._mode_listeners = []
    heard = []
    remove = api.add_mode_listener(lambda: heard.append(api.current_mode))
    api.set_current_mode("text")
    api.set_current_mode("text")
    api.set_current_mode("clock")
    remove()
    api.set_current_mode("textimage")
    assert heard == ["text", "clock"]


def test_mode_select_switches_the_mode_before_updating(monkeypatch):
    order = []
    api = SimpleNamespace(set_current_mode=lambda mode: order.append(("mode", mode)))
    mode = select.BleLedPixelModeSelect.__new__(select.BleLedPixelModeSelect)
    mode._api = api
    mode._attr_options = ["textimage", "text", "clock"]

    async def trigger():
        order.append(("update",))

    mode._trigger_auto_update = trigger
    asyncio.run(mode.async_select_option("clock"))
    assert order == [("mode", "clock"), ("update",)]


class _Stored:
    def __init__(self, json_dict):
        self.json_dict = json_dict

    def as_dict(self):
        return self.json_dict


class _Base:
    """Stands in for RestoreEntity."""

    last = None
    extra = None

    async def async_get_last_state(self):
        return self.last

    async def async_get_last_extra_data(self):
        return self.extra


class _Scoped(entity.ModeScopedEntity, _Base):
    _modes = frozenset({"text"})
    state = "4"
    state_attributes = {"rgb_color": (255, 0, 0)}


@pytest.fixture
def stored(monkeypatch):
    module = sys.modules["homeassistant.helpers.restore_state"]
    monkeypatch.setattr(module, "RestoredExtraData", _Stored, raising=False)


def test_value_is_saved_even_while_greyed_out(stored):
    obj = _Scoped()
    obj._api = SimpleNamespace(current_mode="clock")
    assert obj.available is False
    assert obj.extra_restore_state_data.as_dict() == {
        "state": "4",
        "attributes": {"rgb_color": [255, 0, 0]},
    }


def test_restart_while_greyed_out_restores_the_saved_value():
    obj = _Scoped()
    obj.last = SimpleNamespace(state="unavailable", attributes={})
    obj.extra = _Stored({"state": "7", "attributes": {"rgb_color": [1, 2, 3]}})
    restored = asyncio.run(obj.async_get_last_state())
    assert restored.state == "7"
    assert restored.attributes["rgb_color"] == [1, 2, 3]


def test_a_normal_last_state_wins():
    obj = _Scoped()
    obj.last = SimpleNamespace(state="5", attributes={})
    obj.extra = _Stored({"state": "7"})
    assert asyncio.run(obj.async_get_last_state()).state == "5"


def test_update_uses_the_mode_just_chosen(monkeypatch):
    from custom_components.ble_led_pixel import common

    async def stale_state(*args, **kwargs):
        return "textimage"

    seen = []

    async def clock(hass, name, api):
        seen.append("clock")
        return True

    monkeypatch.setattr(common, "_get_entity_setting", stale_state)
    monkeypatch.setattr(common, "_update_clock_mode", clock)
    api = SimpleNamespace(current_mode="clock", _address="AA:BB")
    assert asyncio.run(common.update_panel_display(None, "Panel", api))
    assert seen == ["clock"]
