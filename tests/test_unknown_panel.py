"""The unknown-panel notice is raised only when there is something to ask."""
from __future__ import annotations

import asyncio

from tests import ha_stubs

ha_stubs.install()

from custom_components.ble_led_pixel import unknown_panel  # noqa: E402


class Registry:
    def __init__(self):
        self.created = []
        self.deleted = []

    def async_create_issue(self, hass, domain, issue_id, **kwargs):
        self.created.append(issue_id)

    def async_delete_issue(self, hass, domain, issue_id):
        self.deleted.append(issue_id)


def run(monkeypatch, device_info):
    registry = Registry()
    monkeypatch.setattr(unknown_panel, "ir", type("ir", (), {
        "async_create_issue": staticmethod(registry.async_create_issue),
        "async_delete_issue": staticmethod(registry.async_delete_issue),
        "IssueSeverity": type("S", (), {"WARNING": "warning"}),
    }))

    async def integration(hass, domain):
        return type("I", (), {"version": "2.4.1"})()

    monkeypatch.setattr(unknown_panel, "async_get_integration", integration)
    asyncio.run(unknown_panel.async_report_unknown_panel(None, "AA:BB", device_info))
    return registry


def test_unknown_product_raises_the_notice(monkeypatch):
    registry = run(monkeypatch, {"cidpid": "009999", "brand": None})
    assert registry.created == ["unknown_panel_AA:BB"]


def test_unbranded_64x20_panel_is_listed_as_generic():
    from custom_components.ble_led_pixel.advertisement import PanelIdentity

    assert PanelIdentity("0001", "05", None).brand == "Generic"


def test_branded_product_clears_the_notice(monkeypatch):
    registry = run(monkeypatch, {"cidpid": "000702", "brand": "B.K. Light"})
    assert registry.created == []
    assert registry.deleted == ["unknown_panel_AA:BB"]


def test_offline_panel_is_checked_from_its_stored_identity():
    from custom_components.ble_led_pixel.advertisement import PanelIdentity

    api = type("Api", (), {"device_info": None, "identity": PanelIdentity("0001", "05", None)})()
    assert unknown_panel.report_info_for(api) == {"cidpid": "000105", "brand": "Generic"}


def test_defaults_only_device_info_falls_back_to_stored_identity():
    from custom_components.ble_led_pixel.advertisement import PanelIdentity

    info = {"width": 64, "height": 16, "cidpid": None, "brand": None}
    api = type("Api", (), {"device_info": info, "identity": PanelIdentity("0001", "05", None)})()
    result = unknown_panel.report_info_for(api)
    assert result["cidpid"] == "000105"
    assert result["brand"] == "Generic"
    assert result["width"] == 64
