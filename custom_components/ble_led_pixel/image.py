"""Image platform: what the panel is showing, for the dashboard card."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ADDRESS, CONF_NAME, DOMAIN
from .entity import panel_device_info
from .preview import upscale


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the preview image of a panel."""
    api = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [BleLedPixelPreviewImage(hass, api, entry.data[CONF_ADDRESS], entry.data[CONF_NAME])]
    )


class BleLedPixelPreviewImage(ImageEntity):
    """The last content sent to the panel, as a picture plus how to animate it."""

    _attr_has_entity_name = True
    _attr_name = "Preview"
    _attr_icon = "mdi:monitor-eye"
    _attr_should_poll = False

    # The attributes change with every send and are only of use to the card,
    # so they stay out of the recorder database.
    _unrecorded_attributes = frozenset(
        {
            "kind", "mode", "text", "effect", "effect_code", "speed",
            "rainbow_mode", "color", "bg_color", "label", "width", "height",
            "connected", "scale",
        }
    )

    def __init__(self, hass: HomeAssistant, api, address: str, name: str) -> None:
        super().__init__(hass)
        self._api = api
        self._preview = api.preview
        self._attr_unique_id = f"{address}_preview"
        self._attr_device_info = panel_device_info(api, address, name)
        self._remove_listener = None
        # The enlarged picture, kept until the content changes.
        self._enlarged: tuple[object, bytes] | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._remove_listener = self._preview.add_listener(self._preview_changed)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        await super().async_will_remove_from_hass()

    def _preview_changed(self) -> None:
        self.async_write_ha_state()

    @property
    def content_type(self) -> str:
        return self._preview.content_type

    @property
    def image_last_updated(self) -> datetime | None:
        return self._preview.updated

    async def async_image(self) -> bytes | None:
        """The picture, enlarged so it is readable outside the card.

        The panel's own picture is 32x32 or so. The card reads the exact
        pixels back out of this one using the `scale` attribute.
        """
        image = self._preview.image
        factor = self._preview.scale
        if image is None or factor <= 1:
            return image
        key = (self._preview.updated, factor, len(image))
        if self._enlarged is not None and self._enlarged[0] == key:
            return self._enlarged[1]
        try:
            enlarged = await self.hass.async_add_executor_job(upscale, image, factor)
        except Exception:  # noqa: BLE001 - the small picture is better than none
            return image
        self._enlarged = (key, enlarged)
        return enlarged

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._api.device_info
        width = height = None
        if info:
            width, height = self._api._resolved_dimensions(info)
        attrs: dict[str, Any] = {
            "kind": self._preview.kind,
            "connected": self._preview.connected,
            "scale": self._preview.scale,
            "width": width,
            "height": height,
        }
        attrs.update(self._preview.meta)
        return attrs
