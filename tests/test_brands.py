"""The fetched brand table: validation, merge order, failure handling."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from tests import ha_stubs

ha_stubs.install()

from custom_components.ble_led_pixel import brands  # noqa: E402
from custom_components.ble_led_pixel.advertisement import BRANDS, PanelIdentity  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sync_brands  # noqa: E402


@pytest.fixture(autouse=True)
def clean_remote():
    brands.set_remote({})
    yield
    brands.set_remote({})


def doc(**entries):
    return {"schema": 1, "brands": entries}


def test_valid_entries_are_kept():
    assert brands.parse_brands(doc(**{"000999": "Acme"})) == {"000999": "Acme"}


@pytest.mark.parametrize("data", [None, [], "x", {"brands": {}}, {"schema": 2, "brands": {}},
                                  {"schema": 1}, {"schema": 1, "brands": []}])
def test_unusable_documents_are_rejected(data):
    assert brands.parse_brands(data) is None


def test_bad_entries_are_dropped_but_good_ones_stay():
    parsed = brands.parse_brands(doc(**{
        "000999": "Acme",
        "99": "short id",
        "abcdef": "not digits",
        "000998": "",
        "000997": "x" * 41,
        "000996": "line\nbreak",
        "000995": 5,
    }))
    assert parsed == {"000999": "Acme"}


def test_built_in_table_wins_over_the_fetched_one():
    brands.set_remote({"000702": "Somebody Else", "000999": "Acme"})
    assert PanelIdentity("0007", "02", None).brand == BRANDS["000702"]
    assert PanelIdentity("0009", "99", None).brand == "Acme"


def test_unknown_panel_stays_unknown_without_remote_entry():
    assert PanelIdentity("0009", "99", None).brand is None


def test_set_remote_reports_changes():
    assert brands.set_remote({"000999": "Acme"}) is True
    assert brands.set_remote({"000999": "Acme"}) is False


class FakeContent:
    def __init__(self, body):
        self.body = body

    async def read(self, n):
        return self.body[:n]


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self.content = FakeContent(body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    def get(self, url):
        if self.error:
            raise self.error
        return self.response


def fetch(session):
    return asyncio.run(brands.async_fetch(session))


def test_fetch_returns_validated_entries():
    body = json.dumps(doc(**{"000999": "Acme"})).encode()
    assert fetch(FakeSession(FakeResponse(200, body))) == {"000999": "Acme"}


@pytest.mark.parametrize("session", [
    FakeSession(FakeResponse(404, b"{}")),
    FakeSession(FakeResponse(200, b"not json")),
    FakeSession(FakeResponse(200, b'{"schema": 9}')),
    FakeSession(FakeResponse(200, b" " * (brands.MAX_RESPONSE_BYTES + 1))),
    FakeSession(error=ConnectionError("down")),
    FakeSession(error=TimeoutError()),
])
def test_fetch_failures_return_none(session):
    assert fetch(session) is None


def test_published_file_agrees_with_the_built_in_table():
    problems, _pending = sync_brands.compare(
        sync_brands.load_builtin(), sync_brands.load_published()
    )
    assert problems == []


def test_published_file_passes_its_own_validation():
    published = sync_brands.load_published()
    data = json.loads((ROOT / "brands.json").read_text(encoding="utf-8"))
    assert brands.parse_brands(data) == published
