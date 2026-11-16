"""The panel preview: what was last sent, for the dashboard card."""
from __future__ import annotations

import asyncio
import io

import pytest
from PIL import Image

from tests import ha_stubs

ha_stubs.install()

from custom_components.ble_led_pixel import api as api_module  # noqa: E402
from custom_components.ble_led_pixel import image as image_module  # noqa: E402
from custom_components.ble_led_pixel import preview as preview_module  # noqa: E402
from custom_components.ble_led_pixel.preview import (  # noqa: E402
    KIND_PLACEHOLDER,
    PanelPreview,
    fit_image,
)


class FakeStore:
    def __init__(self):
        self.saved = None
        self.loaded = None

    def async_delay_save(self, getter, delay):
        self.saved = getter()

    async def async_load(self):
        return self.loaded

    async def async_save(self, data):
        self.saved = data


def make_preview(connected=True):
    prev = PanelPreview.__new__(PanelPreview)
    prev._hass = None
    prev._is_connected = lambda: connected
    prev._store = FakeStore()
    prev.image = None
    prev.content_type = "image/png"
    prev.kind = "none"
    prev.meta = {}
    prev.updated = None
    prev._listeners = []
    return prev


def png(width, height, color=(255, 0, 0)):
    out = io.BytesIO()
    Image.new("RGB", (width, height), color).save(out, format="PNG")
    return out.getvalue()


def test_set_image_notifies_and_keeps_only_known_meta():
    prev = make_preview()
    calls = []
    prev.add_listener(lambda: calls.append(1))
    prev.set_image(b"x", "image/png", kind="text", text="hi", junk="no", speed=None)
    assert prev.kind == "text"
    assert prev.meta == {"text": "hi"}
    assert prev.updated is not None
    assert calls == [1]


def test_removed_listener_is_not_called():
    prev = make_preview()
    calls = []
    remove = prev.add_listener(lambda: calls.append(1))
    remove()
    prev.notify()
    assert calls == []


def test_failing_listener_does_not_break_the_send():
    prev = make_preview()
    prev.add_listener(lambda: 1 / 0)
    prev.set_image(b"x")  # must not raise


def test_placeholder_keeps_the_old_picture_but_says_so():
    prev = make_preview()
    prev.set_image(b"pic", "image/png", mode="textimage")
    prev.set_placeholder("clock", mode="clock")
    assert prev.kind == KIND_PLACEHOLDER
    assert prev.image == b"pic"
    assert prev.meta["label"] == "clock"


def test_survives_a_restart():
    prev = make_preview()
    prev.set_image(b"pic", "image/gif", kind="text", text="hi", speed=40)
    stored = prev._store.saved

    again = make_preview()
    again._store.loaded = stored
    asyncio.run(again.async_load())
    assert again.image == b"pic"
    assert again.content_type == "image/gif"
    assert again.kind == "text"
    assert again.meta == {"text": "hi", "speed": 40}
    assert again.updated == prev.updated


def test_load_with_nothing_or_garbage_is_harmless():
    prev = make_preview()
    asyncio.run(prev.async_load())
    assert prev.kind == "none"
    prev._store.loaded = {"image": "!!not base64!!"}
    asyncio.run(prev.async_load())  # must not raise


def test_save_on_unload_only_when_there_is_something():
    prev = make_preview()
    asyncio.run(prev.async_save_now())
    assert prev._store.saved is None
    prev.set_image(b"pic")
    prev._store.saved = None
    asyncio.run(prev.async_save_now())
    assert prev._store.saved["kind"] == "image"


@pytest.mark.parametrize("method, corner", [("crop", (255, 0, 0)), ("fit", (0, 0, 0))])
def test_fit_image_matches_the_panel_size(method, corner):
    data, content_type = fit_image(png(64, 16), 32, 32, method)
    img = Image.open(io.BytesIO(data))
    assert content_type == "image/png"
    assert img.size == (32, 32)
    # "fit" keeps the whole picture, so the top-left stays black padding;
    # "crop" fills the panel.
    assert img.getpixel((0, 0)) == corner


def test_fit_image_keeps_a_gif_animated():
    frames = [Image.new("RGB", (8, 8), c) for c in ((255, 0, 0), (0, 255, 0), (0, 0, 255))]
    out = io.BytesIO()
    frames[0].save(out, format="GIF", save_all=True, append_images=frames[1:], duration=70, loop=0)
    data, content_type = fit_image(out.getvalue(), 16, 16, "crop")
    img = Image.open(io.BytesIO(data))
    assert content_type == "image/gif"
    assert img.size == (16, 16)
    assert img.n_frames == 3


class FakeApi:
    _record_image = api_module.BleLedPixelAPI._record_image
    _record_placeholder = api_module.BleLedPixelAPI._record_placeholder
    _resolved_dimensions = api_module.BleLedPixelAPI._resolved_dimensions

    def __init__(self):
        self.preview = make_preview()
        self._entry = None
        self.device_info = {"width": 64, "height": 16}


def test_a_superseded_send_is_not_recorded():
    api = FakeApi()
    api._record_image(lambda: False, b"old")
    assert api.preview.image is None
    api._record_image(lambda: True, b"new", "image/png", kind="image")
    assert api.preview.image == b"new"


def test_a_broken_preview_never_fails_the_send():
    api = FakeApi()
    api.preview.set_image = lambda *a, **k: 1 / 0
    api._record_image(None, b"x")  # must not raise
    api.preview.set_placeholder = lambda *a, **k: 1 / 0
    api._record_placeholder(None, "clock")  # must not raise


def test_entity_reports_picture_and_attributes():
    api = FakeApi()
    api.preview.set_image(b"pic", "image/gif", kind="text", effect="Marquee", speed=60)
    entity = image_module.BleLedPixelPreviewImage.__new__(image_module.BleLedPixelPreviewImage)
    entity._api = api
    entity._preview = api.preview
    assert asyncio.run(entity.async_image()) == b"pic"
    assert entity.content_type == "image/gif"
    assert entity.image_last_updated == api.preview.updated
    attrs = entity.extra_state_attributes
    assert attrs["kind"] == "text"
    assert attrs["effect"] == "Marquee"
    assert (attrs["width"], attrs["height"]) == (64, 16)
    assert attrs["connected"] is True


def test_entity_keeps_its_attributes_out_of_the_recorder():
    unrecorded = image_module.BleLedPixelPreviewImage._unrecorded_attributes
    assert {"text", "effect", "speed", "connected"} <= unrecorded


def test_preview_module_exports_what_the_api_uses():
    assert preview_module.fit_image is api_module.fit_image


class Hass:
    async def async_add_executor_job(self, job, *args):
        return job(*args)


class Bluetooth:
    def __init__(self, ok=True):
        self.ok = ok

    async def send_plan(self, plan, ack_timeout=None, still_current=None):
        return self.ok


def make_real_api(ok=True):
    api = api_module.BleLedPixelAPI.__new__(api_module.BleLedPixelAPI)
    api._hass = Hass()
    api._bluetooth = Bluetooth(ok)
    api._entry = None
    api._address = "AA:BB"
    api._font_size_note = None
    api._content_generation = 0
    api._slot_epoch = 0
    api._slot_epochs = {}
    api.preview = make_preview()

    async def device_info():
        return {"width": 64, "height": 16}

    async def connected():
        return True

    async def plan(**kwargs):
        return object()

    api.get_device_info = device_info
    api.ensure_connected = connected
    api._make_image_plan = plan
    return api


def test_display_text_records_what_it_sent():
    api = make_real_api()
    assert asyncio.run(api.display_text("PV 3200W", text_color="00ff00"))
    assert api.preview.kind == "image"
    assert api.preview.meta["text"] == "PV 3200W"
    assert api.preview.meta["color"] == "00ff00"
    assert Image.open(io.BytesIO(api.preview.image)).size == (64, 16)


def test_display_text_records_nothing_when_the_send_failed():
    api = make_real_api(ok=False)
    assert not asyncio.run(api.display_text("PV 3200W"))
    assert api.preview.image is None
    assert api.preview.kind == "none"


def test_text_mode_records_the_effect():
    api = make_real_api()

    class Plan:
        windows = [b"x"]

    api._hass.async_add_executor_job = _text_mode_executor

    assert asyncio.run(
        api.display_text_pypixelcolor("Hello", animation=1, speed=40, color="ff0000")
    )
    assert api.preview.kind == "text"
    assert api.preview.meta["effect_code"] == 1
    assert api.preview.meta["speed"] == 40
    assert api.preview.meta["color"] == "ff0000"


async def _text_mode_executor(job, *args):
    keywords = getattr(job, "keywords", {})
    if "text" in keywords and "animation" in keywords:
        class Plan:
            windows = [b"x"]

        return Plan()
    return job(*args)


def test_clock_mode_leaves_a_placeholder():
    api = make_real_api()
    api.preview.set_image(b"pic")
    api._record_placeholder(None, "clock", mode="clock")
    assert api.preview.kind == KIND_PLACEHOLDER


def test_card_is_registered_once_and_never_raises():
    from custom_components.ble_led_pixel import card

    registered = []
    loaded = []
    card.add_extra_js_url = lambda hass, url: loaded.append(url)
    card.StaticPathConfig = lambda *args: args

    class Http:
        async def async_register_static_paths(self, paths):
            registered.extend(paths)

    class CardHass:
        data = {}
        http = Http()

        async def async_add_executor_job(self, job, *args):
            return job(*args)

    hass = CardHass()
    asyncio.run(card.async_register_card(hass))
    asyncio.run(card.async_register_card(hass))
    assert len(registered) == 1 and len(loaded) == 1
    assert loaded[0].startswith("/ble_led_pixel/ble-led-pixel-card.js?v=")
    assert card.CARD_FILE.is_file()

    class Broken(CardHass):
        data = {}
        http = None  # no http component: must only be logged

    asyncio.run(card.async_register_card(Broken()))
