"""Button entity for BLE LED Pixel Display manual controls."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import BleLedPixelAPI
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME
from .entity import panel_device_info
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
        BleLedPixelSaveSlotButton(hass, api, address, name),
        BleLedPixelShowSlotButton(hass, api, address, name),
        BleLedPixelClearSlotButton(hass, api, address, name),
    ])


class _BleLedPixelSlotButton(ButtonEntity):
    """A button acting on the slot chosen in the Slot number entity."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    _label = ""
    _key = ""

    def __init__(
        self, hass: HomeAssistant, api: BleLedPixelAPI, address: str, name: str
    ) -> None:
        self.hass = hass
        self._api = api
        self._name = name
        self._attr_name = self._label
        self._attr_unique_id = f"{address}_{self._key}_button"
        self._attr_device_info = panel_device_info(api, address, name)

    async def async_press(self) -> None:
        slot = self._api.selected_slot
        if not await self._act(slot):
            raise HomeAssistantError(self._failure(slot))

    async def _act(self, slot: int) -> bool:
        raise NotImplementedError

    def _failure(self, slot: int) -> str:
        return f"{self._label} failed for slot {slot}; see the log"


class BleLedPixelSaveSlotButton(_BleLedPixelSlotButton):
    """Store what the current settings show in the chosen slot.

    Re-sends the current text with the current mode's settings, so the panel
    shows it and keeps a copy. Clock mode is drawn by the panel itself and
    cannot be stored.
    """

    _label = "Save to Slot"
    _key = "save_slot"
    _attr_icon = "mdi:content-save"

    async def _act(self, slot: int) -> bool:
        return await update_panel_display(
            self.hass, self._name, self._api, save_slot=slot
        )

    def _failure(self, slot: int) -> str:
        return (
            f"Could not save to slot {slot}. Clock mode cannot be saved, "
            "and text needs a value; see the log for details"
        )


class BleLedPixelShowSlotButton(_BleLedPixelSlotButton):
    """Show what the chosen slot holds.

    An empty slot makes the panel cycle through the slots that hold
    something, since it cannot report which ones are empty.
    """

    _label = "Show Slot"
    _key = "show_slot"
    _attr_icon = "mdi:play-box-outline"

    async def _act(self, slot: int) -> bool:
        return await self._api.show_slot(slot)


class BleLedPixelClearSlotButton(_BleLedPixelSlotButton):
    """Erase the chosen slot."""

    _label = "Clear Slot"
    _key = "clear_slot"
    _attr_icon = "mdi:delete-outline"

    async def _act(self, slot: int) -> bool:
        return await self._api.delete_slot(slot)


class BleLedPixelUpdateButton(ButtonEntity):
    """Representation of an BLE LED Pixel Display update button."""

    _attr_has_entity_name = True

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
        
        # Device info for grouping in device registry
        self._attr_device_info = panel_device_info(api, address, name)

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

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

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
        self._attr_name = "Clock Sync Time"
        self._attr_unique_id = f"{address}_sync_time_button"

        # Device info for grouping in device registry
        self._attr_device_info = panel_device_info(api, address, name)

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