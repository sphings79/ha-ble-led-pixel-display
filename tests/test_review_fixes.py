"""Points from the HACS review: event loop, file paths, admin password, logs."""
from __future__ import annotations

import asyncio
import threading
from functools import partial
from types import SimpleNamespace

import pytest

from tests import ha_stubs

ha_stubs.install()

from custom_components.ble_led_pixel import api as api_module  # noqa: E402
from custom_components.ble_led_pixel import services, text  # noqa: E402
from custom_components.ble_led_pixel.bluetooth.client import loggable_command  # noqa: E402
from custom_components.ble_led_pixel.const import DOMAIN  # noqa: E402
from custom_components.ble_led_pixel.device import composer  # noqa: E402
from custom_components.ble_led_pixel.device.commands import (  # noqa: E402
    make_set_password_command,
    make_verify_password_command,
)
from custom_components.ble_led_pixel.display import emoji_renderer  # noqa: E402


def run(coro):
    return asyncio.run(coro)


# --- the panel password stays out of the log ---------------------------------

def test_verify_frame_is_logged_without_its_payload():
    shown = loggable_command(make_verify_password_command("123456", 6))
    assert "0c2238" not in shown  # 12, 34, 56 in hex
    assert shown.startswith("07000502")


def test_set_and_clear_frames_are_logged_without_their_payload():
    for enable in (True, False):
        shown = loggable_command(make_set_password_command("123456", 6, enable))
        assert "0c2238" not in shown
        assert shown.startswith("08000402")


def test_other_frames_are_logged_in_full():
    frame = bytes([0x05, 0x00, 0x04, 0x01, 0x00])  # delete-all style frame, opcode 4/1
    assert loggable_command(frame) == frame.hex()
    firmware = bytes([0x04, 0x00, 0x05, 0x80])
    assert loggable_command(firmware) == firmware.hex()


# --- only allowed files are read ---------------------------------------------

class PathHass:
    def __init__(self, allowed):
        self.allowed = allowed
        self.config = SimpleNamespace(is_allowed_path=lambda path: self.allowed)

    async def async_add_executor_job(self, job, *args):
        return job(*args)


def test_a_path_outside_the_allowlist_is_refused():
    with pytest.raises(Exception) as err:
        run(text._require_allowed_path(PathHass(False), "/etc/passwd"))
    assert "allowlist_external_dirs" in str(err.value)


def test_an_allowed_path_passes():
    run(text._require_allowed_path(PathHass(True), "/config/www/a.png"))


def entity(allowed):
    entity = text.BleLedPixelTextDisplay.__new__(text.BleLedPixelTextDisplay)
    entity.hass = PathHass(allowed)
    sent = []

    async def send_image_file(**kwargs):
        sent.append(kwargs)
        return True

    async def send_layout(**kwargs):
        sent.append(kwargs)
        return True

    entity._api = SimpleNamespace(send_image_file=send_image_file, send_layout=send_layout)
    return entity, sent


def test_send_image_file_checks_the_path_before_reading():
    blocked, sent = entity(False)
    with pytest.raises(Exception):
        run(blocked.async_send_image_file("/etc/passwd"))
    assert sent == []
    allowed, sent = entity(True)
    run(allowed.async_send_image_file("/config/www/a.png"))
    assert len(sent) == 1


def test_send_layout_checks_the_image_path_before_reading():
    blocked, sent = entity(False)
    with pytest.raises(Exception):
        run(blocked.async_send_layout(image_path="/etc/passwd"))
    assert sent == []


# --- set_password is an administrator action ----------------------------------

def test_set_password_is_registered_as_an_admin_service():
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
    assert "set_password" in admin
    assert "set_password" not in platform


class PasswordApi:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    async def set_password(self, password, enabled):
        self.calls.append((password, enabled))
        return self.ok


@pytest.fixture
def wired(monkeypatch):
    async def extract(call):
        return {"text.p_display"}

    monkeypatch.setattr(services, "service", SimpleNamespace(
        async_extract_entity_ids=extract,
        remove_entity_service_fields=lambda call: dict(call.data),
    ))
    registry = SimpleNamespace(async_get=lambda entity_id: SimpleNamespace(
        platform=DOMAIN, config_entry_id="e1"))
    monkeypatch.setattr(services, "er", SimpleNamespace(async_get=lambda hass: registry))


def password_call(**data):
    return SimpleNamespace(data=data, service="set_password")


def test_set_password_reaches_the_targeted_panel(wired):
    api = PasswordApi()
    hass = SimpleNamespace(data={DOMAIN: {"e1": api}})
    run(services._async_set_password(
        hass, password_call(password="123456", enabled=True)))
    assert api.calls == [("123456", True)]


def test_a_refused_password_change_is_reported(wired):
    hass = SimpleNamespace(data={DOMAIN: {"e1": PasswordApi(ok=False)}})
    with pytest.raises(Exception):
        run(services._async_set_password(
            hass, password_call(password="123456", enabled=True)))


def test_set_password_refuses_all():
    from custom_components.ble_led_pixel.services import ATTR_ENTITY_ID  # noqa: F401

    hass = SimpleNamespace(data={DOMAIN: {}})
    with pytest.raises(Exception):
        run(services._async_set_password(
            hass, password_call(entity_id="all", password="123456", enabled=True)))


# --- blocking work runs off the event loop ------------------------------------

def test_composer_renders_in_a_worker_thread(monkeypatch):
    seen = {}

    def render(*args, **kwargs):
        seen["thread"] = threading.current_thread()
        return b"png", ".png"

    monkeypatch.setattr(composer, "_render_layout_media", render)
    result = run(composer.build_layout_media(64, 16, session=None, texts=[{"text": "x"}]))
    assert result == (b"png", ".png")
    assert seen["thread"] is not threading.main_thread()


def test_composer_fetches_each_icon_once_before_rendering(monkeypatch):
    fetched = []

    async def fetch(name, session):
        fetched.append(name)
        return f"<svg {name}/>"

    captured = {}

    def render(canvas_width, canvas_height, svgs, *args, **kwargs):
        captured["svgs"] = svgs
        return b"png", ".png"

    monkeypatch.setattr(composer, "fetch_mdi_svg", fetch)
    monkeypatch.setattr(composer, "_render_layout_media", render)
    icons = [{"icon": "a"}, {"icon": "a"}, {"icon": "b"}, {"x": 1}]
    run(composer.build_layout_media(64, 16, session=None, icons=icons))
    assert fetched == ["a", "b"]
    assert captured["svgs"] == {"a": "<svg a/>", "b": "<svg b/>"}


def test_emoji_cache_check_does_not_touch_the_disk_on_the_loop(tmp_path):
    missing = tmp_path / "none.png"
    assert emoji_renderer._read_cached(missing) is None
    present = tmp_path / "some.png"
    present.write_bytes(b"x")
    assert emoji_renderer._read_cached(present) == b"x"


def test_rendering_and_image_building_go_through_the_executor(monkeypatch):
    jobs = []

    class Hass:
        async def async_add_executor_job(self, job, *args):
            jobs.append(job.func if isinstance(job, partial) else job)
            return job(*args)

    monkeypatch.setattr(api_module, "render_text_to_png", lambda *a: b"png")
    monkeypatch.setattr(api_module, "make_image_command", lambda **kw: "plan")

    from tests.test_text_ordering import make_api

    api = make_api()
    api._hass = Hass()
    assert run(api.display_text("hi"))
    assert api_module.render_text_to_png in jobs
    assert api_module.make_image_command in jobs
