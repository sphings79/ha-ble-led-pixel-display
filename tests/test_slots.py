"""Erasing all stored content, and saving text to a slot."""
from __future__ import annotations

import asyncio

from tests import ha_stubs

ha_stubs.install()

from custom_components.ble_led_pixel import api as api_module  # noqa: E402
from tests.test_text_ordering import make_api  # noqa: E402


def test_delete_all_slots_sends_the_erase_command():
    api = make_api()
    sent = []

    async def send_command(command, content=False, still_current=None):
        sent.append((command, content))
        return True

    api._bluetooth.send_command = send_command
    assert asyncio.run(api.delete_all_slots())
    # Not a content write: erasing must not be dropped by a restore guard.
    assert sent == [(bytes([0x04, 0x00, 0x03, 0x80]), False)]


def test_text_saved_to_a_slot_is_never_dropped():
    async def scenario():
        api = make_api()
        saved = asyncio.create_task(api.display_text_pypixelcolor("keep", save_slot=1))
        await asyncio.sleep(0)
        new = asyncio.create_task(api.display_text_pypixelcolor("new"))
        await asyncio.sleep(0)
        api._hass.pending["new"].set()
        assert await new
        api._hass.pending["keep"].set()
        assert await saved
        return api._bluetooth.sent

    assert asyncio.run(scenario()) == ["new", "keep"]


def test_save_slot_reaches_the_text_command():
    async def scenario():
        api = make_api()
        seen = {}
        original = api._hass.async_add_executor_job

        async def job(func):
            seen.update(func.keywords)
            return await original(func)

        api._hass.async_add_executor_job = job
        task = asyncio.create_task(api.display_text_pypixelcolor("x", save_slot=3))
        await asyncio.sleep(0)
        api._hass.pending["x"].set()
        assert await task
        return seen["save_slot"]

    assert asyncio.run(scenario()) == 3


def test_slot_save_requested_before_an_erase_is_dropped():
    async def scenario():
        api = make_api()

        async def send_command(command, content=False, still_current=None):
            api._bluetooth.sent.append("erase")
            return True

        api._bluetooth.send_command = send_command
        saved = asyncio.create_task(api.display_text_pypixelcolor("old", save_slot=1))
        await asyncio.sleep(0)
        assert await api.delete_all_slots()
        api._hass.pending["old"].set()
        assert await saved
        return api._bluetooth.sent

    assert asyncio.run(scenario()) == ["erase"]


def test_slot_save_requested_before_deleting_that_slot_is_dropped():
    async def scenario():
        api = make_api()
        saved = asyncio.create_task(api.display_text_pypixelcolor("old", save_slot=2))
        other = asyncio.create_task(api.display_text_pypixelcolor("other", save_slot=3))
        await asyncio.sleep(0)
        assert await api.delete_slot(2)
        api._hass.pending["old"].set()
        api._hass.pending["other"].set()
        assert await saved
        assert await other
        return api._bluetooth.sent

    sent = asyncio.run(scenario())
    assert "old" not in sent
    assert "other" in sent
