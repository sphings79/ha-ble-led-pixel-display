"""Text Size select: whole 16px rows that fit the panel."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from tests import ha_stubs

ha_stubs.install()

from custom_components.ble_led_pixel import api as api_module  # noqa: E402
from custom_components.ble_led_pixel import select  # noqa: E402
from custom_components.ble_led_pixel.const import (  # noqa: E402
    OPT_OVERRIDE_DIMENSIONS,
    OPT_PANEL_HEIGHT,
    text_size_from_font_size,
    text_sizes_for_height,
)


@pytest.mark.parametrize(
    "height, sizes",
    [(None, [16, 32, 48, 64]), (20, [16]), (16, [16]), (12, [16]), (32, [16, 32]), (64, [16, 32, 48, 64])],
)
def test_sizes_fit_the_panel(height, sizes):
    assert text_sizes_for_height(height) == sizes


@pytest.mark.parametrize(
    "font_size, size", [(None, 16), (0, 16), (10.5, 16), (16, 16), (31.5, 16), (32, 32), (50, 48), (200, 64)]
)
def test_old_font_size_maps_to_what_text_mode_drew(font_size, size):
    assert text_size_from_font_size(font_size) == size


class FakeAPI:
    _resolved_dimensions = api_module.BleLedPixelAPI._resolved_dimensions
    text_sizes = api_module.BleLedPixelAPI.text_sizes

    def __init__(self, height=None, options=None):
        self._device_info = None if height is None else {"width": 64, "height": height}
        self._entry = SimpleNamespace(options=options or {})


def test_api_honours_the_height_override():
    api = FakeAPI(height=20, options={OPT_OVERRIDE_DIMENSIONS: True, OPT_PANEL_HEIGHT: 32})
    assert api.text_sizes == [16, 32]
    assert FakeAPI(height=20).text_sizes == [16]
    assert FakeAPI().text_sizes == [16, 32, 48, 64]
    # Panel not queried yet: the override alone decides.
    assert FakeAPI(options={OPT_OVERRIDE_DIMENSIONS: True, OPT_PANEL_HEIGHT: 16}).text_sizes == [16]
    assert FakeAPI(options={OPT_PANEL_HEIGHT: 16}).text_sizes == [16, 32, 48, 64]  # override off


def make_select(monkeypatch, api, number_state=None, last_state=None):
    monkeypatch.setattr(
        select, "get_entity_id_by_unique_id",
        lambda hass, address, setting, platform: f"{platform}.panel_{setting}",
    )
    stored = {}
    if number_state is not None:
        stored["number.panel_font_size"] = SimpleNamespace(state=SimpleNamespace(state=number_state))
    monkeypatch.setattr(select, "restore_state_data", lambda hass: SimpleNamespace(last_states=stored))
    entity = select.BleLedPixelTextSizeSelect.__new__(select.BleLedPixelTextSizeSelect)
    entity.hass = SimpleNamespace()
    entity._api = api
    entity._address = "AA"
    entity._name = "Panel"
    entity._chosen = None
    entity.async_write_ha_state = lambda: None

    async def get_last_state():
        return None if last_state is None else SimpleNamespace(state=last_state)

    entity.async_get_last_state = get_last_state
    asyncio.run(entity.async_added_to_hass())
    return entity


def test_first_start_takes_the_size_from_the_old_font_size(monkeypatch):
    entity = make_select(monkeypatch, FakeAPI(height=64), number_state="40")
    assert entity.options == ["16", "32", "48", "64"]
    assert entity.current_option == "32"

    async def no_refresh(*args):
        return None

    monkeypatch.setattr(select, "_refresh_if_showing_text", no_refresh)
    asyncio.run(entity.async_select_option("48"))
    assert entity.current_option == "48"


def test_restored_size_wins_and_is_clamped_to_the_panel(monkeypatch):
    entity = make_select(monkeypatch, FakeAPI(height=64), number_state="16", last_state="64")
    assert entity.current_option == "64"
    entity._api = FakeAPI(height=32)  # panel turned out shorter, or override changed
    assert entity.current_option == "32"
    assert entity.options == ["16", "32"]


def test_first_start_without_an_old_font_size_is_16(monkeypatch):
    assert make_select(monkeypatch, FakeAPI(height=64)).current_option == "16"
    assert make_select(monkeypatch, FakeAPI(height=64), number_state="0").current_option == "16"


def test_size_that_does_not_fit_is_refused(monkeypatch):
    entity = make_select(monkeypatch, FakeAPI(height=20))
    assert entity.options == ["16"]
    asyncio.run(entity.async_select_option("32"))
    assert entity.current_option == "16"
    assert entity._chosen == 16


def test_saved_state_found_by_registry_id_on_newer_home_assistant(monkeypatch):
    stored = SimpleNamespace(state=SimpleNamespace(state="48"))
    data = SimpleNamespace(last_states_by_entity_id={}, last_states_by_entity_registry_id={"reg1": stored})
    monkeypatch.setattr(select, "restore_state_data", lambda hass: data)
    registry = SimpleNamespace(async_get=lambda entity_id: SimpleNamespace(id="reg1"))
    monkeypatch.setattr(select.er, "async_get", lambda hass: registry, raising=False)
    assert select._stored_state(None, "number.panel_font_size") is stored
