"""Serve the dashboard card and load it on every dashboard.

The card is a single JS file shipped inside the integration, so there is
nothing to install through HACS' frontend section or to add as a resource by
hand.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_FILE = Path(__file__).parent / "www" / "ble-led-pixel-card.js"
CARD_URL = f"/{DOMAIN}/ble-led-pixel-card.js"


def _version() -> str:
    try:
        manifest = Path(__file__).parent / "manifest.json"
        return str(json.loads(manifest.read_text(encoding="utf-8")).get("version", "0"))
    except Exception:  # noqa: BLE001 - only used to bust the browser cache
        return "0"


async def async_register_card(hass: HomeAssistant) -> None:
    """Make the card available. Never raises: the card is optional."""
    if hass.data.get(f"{DOMAIN}_card_registered"):
        return
    try:
        version = await hass.async_add_executor_job(_version)
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(CARD_FILE), False)]
        )
        # The version in the URL makes browsers fetch the new file after an
        # update instead of running the cached old one.
        add_extra_js_url(hass, f"{CARD_URL}?v={version}")
        hass.data[f"{DOMAIN}_card_registered"] = True
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not register the dashboard card: %s", err)
