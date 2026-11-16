"""What a panel is showing, kept for the dashboard card.

The panel cannot report its content, so the preview is what Home Assistant
last sent to it successfully -- a picture, plus enough detail (effect, speed,
colours) for the card to animate it. Modes the panel draws itself (the clock,
stored slots, presets, scoreboard...) have no picture; they are recorded as a
placeholder so the card can say so instead of showing stale content.
"""
from __future__ import annotations

import base64
import io
import logging
import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
# Writes are collapsed: an automation may send every few seconds, and the file
# only has to survive a restart.
SAVE_DELAY = 30

KIND_NONE = "none"
KIND_IMAGE = "image"
KIND_TEXT = "text"
KIND_PLACEHOLDER = "placeholder"

# Meta keys the card reads. Everything else passed in is dropped, so a caller
# cannot grow the entity attributes without bound.
META_KEYS = (
    "mode", "text", "effect", "effect_code", "speed", "rainbow_mode",
    "color", "bg_color", "label",
)


def fit_image(data: bytes, width: int, height: int, method: str) -> tuple[bytes, str]:
    """Scale a picture the way the panel would, returning (bytes, content type).

    "crop" fills the panel and cuts the excess, "fit" keeps the whole picture
    on black. An animated GIF stays animated. Runs in the executor.
    """
    from PIL import Image, ImageSequence

    def place(frame: "Image.Image") -> "Image.Image":
        frame = frame.convert("RGB")
        src_w, src_h = frame.size
        if (src_w, src_h) == (width, height):
            return frame
        if method == "fit":
            scale = min(width / src_w, height / src_h)
        else:
            scale = max(width / src_w, height / src_h)
        new_w = max(1, round(src_w * scale))
        new_h = max(1, round(src_h * scale))
        frame = frame.resize((new_w, new_h), Image.LANCZOS)
        canvas = Image.new("RGB", (width, height), (0, 0, 0))
        canvas.paste(frame, ((width - new_w) // 2, (height - new_h) // 2))
        return canvas

    with Image.open(io.BytesIO(data)) as img:
        if getattr(img, "is_animated", False) and img.format == "GIF":
            frames, durations = [], []
            for frame in ImageSequence.Iterator(img):
                durations.append(frame.info.get("duration", 100))
                frames.append(place(frame))
            out = io.BytesIO()
            frames[0].save(
                out, format="GIF", save_all=True, append_images=frames[1:],
                duration=durations, loop=0, disposal=2,
            )
            return out.getvalue(), "image/gif"
        out = io.BytesIO()
        place(img).save(out, format="PNG")
        return out.getvalue(), "image/png"


class PanelPreview:
    """The last successfully sent content of one panel."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        is_connected: Callable[[], bool],
    ) -> None:
        self._hass = hass
        self._is_connected = is_connected
        slug = re.sub(r"[^a-z0-9]", "", address.lower())
        self._store: Store = Store(hass, STORAGE_VERSION, f"ble_led_pixel.preview_{slug}")
        self.image: bytes | None = None
        self.content_type = "image/png"
        self.kind = KIND_NONE
        self.meta: dict[str, Any] = {}
        self.updated: datetime | None = None
        self._listeners: list[Callable[[], None]] = []

    @property
    def connected(self) -> bool:
        return bool(self._is_connected())

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Call `listener` whenever the preview or the link state changes."""
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    @callback
    def notify(self) -> None:
        """Tell listeners something changed (also used for link up/down)."""
        for listener in list(self._listeners):
            try:
                listener()
            except Exception as err:  # noqa: BLE001 - a listener must not break a send
                _LOGGER.debug("Preview listener failed: %s", err)

    def _clean(self, meta: dict[str, Any]) -> dict[str, Any]:
        return {k: meta[k] for k in META_KEYS if meta.get(k) is not None}

    @callback
    def set_image(
        self,
        data: bytes,
        content_type: str = "image/png",
        kind: str = KIND_IMAGE,
        **meta: Any,
    ) -> None:
        """Record a picture that was just sent to the panel."""
        self.image = data
        self.content_type = content_type
        self.kind = kind
        self.meta = self._clean(meta)
        self._changed()

    @callback
    def set_placeholder(self, label: str, **meta: Any) -> None:
        """Record content the panel draws itself (clock, slot, preset...)."""
        self.kind = KIND_PLACEHOLDER
        self.meta = self._clean({**meta, "label": label})
        self._changed()

    def _changed(self) -> None:
        self.updated = datetime.now(timezone.utc)
        self._store.async_delay_save(self._as_dict, SAVE_DELAY)
        self.notify()

    def _as_dict(self) -> dict[str, Any]:
        return {
            "image": base64.b64encode(self.image).decode() if self.image else None,
            "content_type": self.content_type,
            "kind": self.kind,
            "meta": self.meta,
            "updated": self.updated.isoformat() if self.updated else None,
        }

    async def async_load(self) -> None:
        """Pick up what was stored before the last restart."""
        try:
            data = await self._store.async_load()
            if not data:
                return
            if data.get("image"):
                self.image = base64.b64decode(data["image"])
            self.content_type = data.get("content_type") or "image/png"
            self.kind = data.get("kind") or KIND_NONE
            self.meta = self._clean(data.get("meta") or {})
            self.updated = datetime.fromisoformat(data["updated"]) if data.get("updated") else None
        except Exception as err:  # noqa: BLE001 - cosmetic, never block setup
            _LOGGER.debug("Could not load the stored preview: %s", err)

    async def async_save_now(self) -> None:
        """Write the preview immediately (on unload), if there is one."""
        if self.kind != KIND_NONE:
            await self._store.async_save(self._as_dict())
