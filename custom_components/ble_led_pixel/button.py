"""Button entity for BLE LED Pixel Display manual controls."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .api import BleLedPixelAPI
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME
from .common import update_panel_display

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BLE LED Pixel Display button entities."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    api = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([
        BleLedPixelUpdateButton(hass, api, entry, address, name),
        BleLedPixelSyncTimeButton(hass, api, entry, address, name),
    ])


class BleLedPixelUpdateButton(ButtonEntity):
    """Representation of an BLE LED Pixel Display update button."""

    _attr_icon = "mdi:refresh"

    def __init__(
        self, 
        hass: HomeAssistant,
        api: BleLedPixelAPI, 
        entry: ConfigEntry, 
        address: str, 
        name: str
    ) -> None:
        """Initialize the update button."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Update Display"
        self._attr_unique_id = f"{address}_update_button"
        self._attr_entity_description = "Manually update display with current text and settings"
        
        # Device info for grouping in device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=name,
            model="LED Pixel Panel",
            sw_version="1.0",
        )

    async def async_press(self) -> None:
        """Handle button press to update display."""
        _LOGGER.debug("Manual display update triggered")
        await update_panel_display(self.hass, self._name, self._api)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True


class BleLedPixelSyncTimeButton(ButtonEntity):
    """Representation of an BLE LED Pixel Display time sync button."""

    _attr_icon = "mdi:clock-sync"

    def __init__(
        self,
        hass: HomeAssistant,
        api: BleLedPixelAPI,
        entry: ConfigEntry,
        address: str,
        name: str
    ) -> None:
        """Initialize the sync time button."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Sync Time"
        self._attr_unique_id = f"{address}_sync_time_button"
        self._attr_entity_description = "Sync current time to device clock"

        # Device info for grouping in device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=name,
            model="LED Pixel Panel",
            sw_version="1.0",
        )

    async def async_press(self) -> None:
        """Handle button press to sync time."""
        _LOGGER.debug("Manual time sync triggered")
        try:
            # Connect if needed
            if not self._api.is_connected:
                _LOGGER.debug("Reconnecting to device for time sync")
                await self._api.connect()

            # Sync time
            success = await self._api.sync_time()

            if success:
                _LOGGER.info("Time synchronized successfully")
            else:
                _LOGGER.error("Failed to sync time")

        except Exception as err:
            _LOGGER.error("Error during time sync: %s", err)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True