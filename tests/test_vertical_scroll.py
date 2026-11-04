"""Scroll up/down: offered on 32x32 panels, elsewhere only when opted in."""
from types import SimpleNamespace

from tests import ha_stubs

ha_stubs.install()

from custom_components.ble_led_pixel import api as api_module  # noqa: E402
from custom_components.ble_led_pixel.const import (  # noqa: E402
    ALL_TEXT_EFFECTS,
    OPT_VERTICAL_SCROLL,
    TEXT_EFFECTS,
    text_effects,
)


def test_effect_lists():
    assert "Scroll up" not in text_effects(False)
    assert list(text_effects(True).values()) == sorted(ALL_TEXT_EFFECTS.values())
    assert text_effects(True)["Scroll up"] == 3
    assert text_effects(True)["Scroll down"] == 4
    assert text_effects(False) == TEXT_EFFECTS


class FakeApi:
    vertical_scroll_allowed = api_module.BleLedPixelAPI.vertical_scroll_allowed
    _known_dimensions = api_module.BleLedPixelAPI._known_dimensions
    _resolved_dimensions = api_module.BleLedPixelAPI._resolved_dimensions
    device_info = api_module.BleLedPixelAPI.device_info
    add_device_info_listener = api_module.BleLedPixelAPI.add_device_info_listener

    def __init__(self, options, info):
        self._entry = SimpleNamespace(options=options)
        self._device_info = info
        self._device_info_listeners = []

    def learn(self, info):
        """What get_device_info does once the panel answers."""
        self._device_info = info
        for listener in list(self._device_info_listeners):
            listener()


def test_off_by_default_on_other_panels():
    assert not FakeApi({}, {"width": 64, "height": 20}).vertical_scroll_allowed
    assert not FakeApi({}, None).vertical_scroll_allowed


def test_32x32_override_counts_before_the_panel_answers():
    from custom_components.ble_led_pixel.const import (
        OPT_OVERRIDE_DIMENSIONS,
        OPT_PANEL_HEIGHT,
        OPT_PANEL_WIDTH,
    )

    override = {OPT_OVERRIDE_DIMENSIONS: True, OPT_PANEL_WIDTH: 32, OPT_PANEL_HEIGHT: 32}
    assert FakeApi(override, None).vertical_scroll_allowed
    assert not FakeApi({**override, OPT_OVERRIDE_DIMENSIONS: False}, None).vertical_scroll_allowed
    assert not FakeApi({**override, OPT_PANEL_WIDTH: 64}, None).vertical_scroll_allowed


def test_opt_in_enables_it():
    assert FakeApi({OPT_VERTICAL_SCROLL: True}, {"width": 64, "height": 20}).vertical_scroll_allowed
    assert FakeApi({OPT_VERTICAL_SCROLL: True}, None).vertical_scroll_allowed


def test_always_on_for_32x32():
    assert FakeApi({}, {"width": 32, "height": 32}).vertical_scroll_allowed


class AsyncFakeApi(FakeApi):
    async_vertical_scroll_allowed = api_module.BleLedPixelAPI.async_vertical_scroll_allowed

    def __init__(self, options, info, reported=None, reachable=True):
        super().__init__(options, info)
        self.reported = reported
        self.reachable = reachable
        self.queries = 0

    async def ensure_connected(self):
        return self.reachable

    async def get_device_info(self):
        self.queries += 1
        self._device_info = self.reported
        return self.reported


def run(coro):
    import asyncio

    return asyncio.run(coro)


def test_unknown_size_is_read_from_the_panel_before_refusing():
    api = AsyncFakeApi({}, None, reported={"width": 32, "height": 32})
    assert run(api.async_vertical_scroll_allowed())
    assert api.queries == 1
    assert run(api.async_vertical_scroll_allowed())
    assert api.queries == 1  # known now, not asked again


def test_known_or_opted_in_does_not_query():
    api = AsyncFakeApi({}, {"width": 64, "height": 20})
    assert not run(api.async_vertical_scroll_allowed())
    api = AsyncFakeApi({OPT_VERTICAL_SCROLL: True}, None)
    assert run(api.async_vertical_scroll_allowed())
    assert api.queries == 0


def test_unreachable_panel_is_refused_quietly():
    api = AsyncFakeApi({}, None, reachable=False)
    assert not run(api.async_vertical_scroll_allowed())
    assert api.queries == 0


def test_select_options_follow_the_panel_size():
    from custom_components.ble_led_pixel import select

    entity = select.BleLedPixelTextEffectSelect.__new__(select.BleLedPixelTextEffectSelect)
    entity._api = FakeApi({}, None)
    assert "Scroll up" not in entity.options
    entity._api._device_info = {"width": 32, "height": 32}
    assert "Scroll up" in entity.options


def restored_select(api, saved):
    from custom_components.ble_led_pixel import select

    entity = select.BleLedPixelTextEffectSelect.__new__(select.BleLedPixelTextEffectSelect)
    entity._api = api
    entity._attr_current_option = "Fixed"
    entity.hass = object()
    entity.writes = 0
    entity.removers = []

    def write():
        entity.writes += 1

    entity.async_write_ha_state = write
    entity.async_on_remove = entity.removers.append

    async def last_state():
        return SimpleNamespace(state=saved)

    entity.async_get_last_state = last_state
    run(entity.async_added_to_hass())
    return entity


def test_saved_scroll_effect_survives_a_restart_before_the_size_is_known():
    entity = restored_select(FakeApi({}, None), "Scroll up")
    assert entity.current_option == "Scroll up"
    entity._api.learn({"width": 32, "height": 32})
    assert entity.current_option == "Scroll up"
    assert "Scroll up" in entity.options
    assert entity.writes == 1  # options published once the size is known


def test_saved_scroll_effect_dropped_when_the_panel_turns_out_not_to_allow_it():
    entity = restored_select(FakeApi({}, None), "Scroll down")
    entity._api.learn({"width": 64, "height": 20})
    assert entity.current_option == "Fixed"
    assert entity.writes == 1


def test_saved_scroll_effect_rejected_after_turning_the_option_off():
    entity = restored_select(FakeApi({}, {"width": 64, "height": 20}), "Scroll up")
    assert entity.current_option == "Fixed"


def test_listener_is_removed_with_the_entity():
    entity = restored_select(FakeApi({}, None), "Fixed")
    assert len(entity._api._device_info_listeners) == 1
    entity.removers[0]()
    assert entity._api._device_info_listeners == []


def test_listeners_hear_about_the_fallback_size_too(monkeypatch):
    api = api_module.BleLedPixelAPI.__new__(api_module.BleLedPixelAPI)
    api._device_info = None
    api._device_info_listeners = []
    heard = []
    api.add_device_info_listener(lambda: heard.append(api._device_info["height"]))

    class Silent:
        async def send_command_wait_response(self, command, timeout=None):
            return None

    api._bluetooth = Silent()

    async def no_sleep(_):
        return None

    monkeypatch.setattr(api_module.asyncio, "sleep", no_sleep)
    run(api.get_device_info())
    assert heard == [16]
