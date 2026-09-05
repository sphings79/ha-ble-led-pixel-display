"""Offer a prefilled bug report for panels the brand table does not know.

An unrecognised panel works fine - geometry comes from the device type, not
the brand - so this is not an error condition. It is an invitation: everything
technical is already known here, only the name on the box is not, and that is
the one thing the user can see and we cannot.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ISSUE_FORM_URL = "https://github.com/sphings79/ha-ble-led-pixel-display/issues/new"
ISSUE_TEMPLATE = "unknown-panel.yml"


def build_report_url(device_info: dict[str, Any], integration_version: str) -> str:
    """Build a GitHub issue URL with the technical fields already filled in.

    The parameter names match the field ids in
    .github/ISSUE_TEMPLATE/unknown-panel.yml - GitHub prefills a form field
    from a query parameter of the same name.
    """
    cidpid = device_info.get("cidpid") or "unknown"
    width = device_info.get("width")
    height = device_info.get("height")
    mcu = device_info.get("mcu_version") or "unknown"
    wifi = device_info.get("wifi_version") or "unknown"

    params = {
        "template": ISSUE_TEMPLATE,
        "title": f"Unknown panel: {cidpid}",
        "labels": "unknown-panel",
        "product_id": cidpid,
        "device_type": str(device_info.get("device_type", "unknown")),
        "reported_size": f"{width}x{height}" if width and height else "unknown",
        "versions": f"MCU {mcu}, WiFi {wifi}",
        "integration_version": integration_version,
    }
    return f"{ISSUE_FORM_URL}?{urlencode(params)}"


async def async_report_unknown_panel(
    hass: HomeAssistant, address: str, device_info: dict[str, Any] | None
) -> None:
    """Raise a repair notice for an unrecognised panel, with a prefilled link.

    Does nothing when the brand is already known, when no product id has been
    seen yet, or when the panel is recognised later - the notice is cleared in
    that case.
    """
    issue_id = f"unknown_panel_{address}"

    if not device_info:
        return

    cidpid = device_info.get("cidpid")
    if cidpid is None:
        # No advertisement seen yet; nothing to report and nothing to clear.
        return

    if device_info.get("brand"):
        # Recognised after all - drop a notice from an earlier run.
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    try:
        integration = await async_get_integration(hass, DOMAIN)
        version = str(integration.version or "unknown")
    except Exception:  # noqa: BLE001 - a missing version must not stop the notice
        version = "unknown"

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="unknown_panel",
        translation_placeholders={
            "product_id": cidpid,
            "address": address,
        },
        learn_more_url=build_report_url(device_info, version),
    )
    _LOGGER.debug("Raised unknown-panel notice for %s (%s)", address, cidpid)
