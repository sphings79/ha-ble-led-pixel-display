"""A text that finishes rendering after a newer one started is not sent."""
from __future__ import annotations

import asyncio

from tests import ha_stubs

ha_stubs.install()

from custom_components.ble_led_pixel import api as api_module  # noqa: E402


class Plan:
    def __init__(self, text):
        self.text = text
        self.windows = [b"x"]


class Hass:
    """Runs executor jobs on demand, in an order the test picks."""

    def __init__(self):
        self.pending = {}

    async def async_add_executor_job(self, job):
        text = job.keywords["text"]
        gate = asyncio.Event()
        self.pending[text] = gate
        await gate.wait()
        return Plan(text)


class Bluetooth:
    def __init__(self):
        self.sent = []

    async def send_plan(self, plan, ack_timeout=None, still_current=None):
        # Like the real client: asked once the send lock is held.
        if still_current is not None and not still_current():
            return True
        self.sent.append(getattr(plan, "text", "other content"))
        return True


def make_api():
    api = api_module.BleLedPixelAPI.__new__(api_module.BleLedPixelAPI)
    api._hass = Hass()
    api._bluetooth = Bluetooth()
    api._entry = None
    api._font_size_note = None
    api._content_generation = 0

    async def device_info():
        return {"width": 64, "height": 20}

    async def connected():
        return True

    api.get_device_info = device_info
    api.ensure_connected = connected
    return api


def test_older_render_finishing_last_is_dropped():
    async def scenario():
        api = make_api()
        old = asyncio.create_task(api.display_text_pypixelcolor("a long old message"))
        await asyncio.sleep(0)
        new = asyncio.create_task(api.display_text_pypixelcolor("new"))
        await asyncio.sleep(0)
        api._hass.pending["new"].set()
        assert await new
        api._hass.pending["a long old message"].set()
        assert await old
        return api._bluetooth.sent

    assert asyncio.run(scenario()) == ["new"]


def test_texts_in_order_are_all_sent():
    async def scenario():
        api = make_api()
        for text in ("one", "two"):
            task = asyncio.create_task(api.display_text_pypixelcolor(text))
            await asyncio.sleep(0)
            api._hass.pending[text].set()
            assert await task
        return api._bluetooth.sent

    assert asyncio.run(scenario()) == ["one", "two"]


def test_older_text_stuck_reconnecting_does_not_overwrite_a_newer_one():
    async def scenario():
        api = make_api()
        link_up = asyncio.Event()

        async def slow_reconnect():
            await link_up.wait()  # e.g. running the queued restore
            return True

        api.ensure_connected = slow_reconnect
        old = asyncio.create_task(api.display_text_pypixelcolor("old"))
        await asyncio.sleep(0)
        api._hass.pending["old"].set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)  # old is now waiting in ensure_connected

        async def connected():
            return True

        api.ensure_connected = connected
        new = asyncio.create_task(api.display_text_pypixelcolor("new"))
        await asyncio.sleep(0)
        api._hass.pending["new"].set()
        assert await new
        link_up.set()
        assert await old
        return api._bluetooth.sent

    assert asyncio.run(scenario()) == ["new"]


def test_older_text_does_not_overwrite_newer_non_text_content():
    async def scenario():
        api = make_api()
        old = asyncio.create_task(api.display_text_pypixelcolor("old"))
        await asyncio.sleep(0)
        # An image, slot, emoji or clock request arrives while the text renders.
        assert await api.show_slot(1)
        api._hass.pending["old"].set()
        assert await old
        return api._bluetooth.sent

    assert asyncio.run(scenario()) == ["other content"]


def test_any_display_request_supersedes_earlier_ones():
    api = make_api()
    first = api._claim_content()
    assert first()
    second = api._claim_content()
    assert not first()
    assert second()


def test_restore_does_not_supersede_a_live_request():
    from custom_components.ble_led_pixel.bluetooth.client import BluetoothClient

    api = make_api()
    live = api._claim_content()
    client = BluetoothClient.__new__(BluetoothClient)
    client._content_writes = 0
    with client.restoring():
        restore = api._claim_content()
        assert live()
        assert restore()
    newer = api._claim_content()
    assert newer()
    assert not live()
    assert not restore()


def test_clock_stuck_reconnecting_does_not_overwrite_newer_text():
    from custom_components.ble_led_pixel.api import BleLedPixelConnectionError

    async def scenario():
        api = make_api()
        link_up = asyncio.Event()
        first = [True]

        async def send_command(command, content=False, still_current=None):
            if first[0]:
                first[0] = False
                raise BleLedPixelConnectionError("link dropped")
            if still_current is not None and not still_current():
                return True
            api._bluetooth.sent.append("clock")
            return True

        api._bluetooth.send_command = send_command

        async def slow_reconnect():
            await link_up.wait()
            return True

        api.ensure_connected = slow_reconnect
        clock = asyncio.create_task(api.set_clock_mode())
        await asyncio.sleep(0)
        await asyncio.sleep(0)  # clock is now waiting in ensure_connected

        async def connected():
            return True

        api.ensure_connected = connected
        new = asyncio.create_task(api.display_text_pypixelcolor("new"))
        await asyncio.sleep(0)
        api._hass.pending["new"].set()
        assert await new
        link_up.set()
        assert await clock
        return api._bluetooth.sent

    assert asyncio.run(scenario()) == ["new"]
