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
    "color", "bg_color", "label", "strip",
)

# Effects that move the text across the panel, and so need the whole line as a
# picture of its own rather than just the first view of it.
SCROLL_EFFECTS = (1, 2, 3, 4)
# A line longer than this (as base64) is not sent along; the card then shows
# the still picture instead of a scroll.
MAX_STRIP_BYTES = 150_000


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


def _rgb(value: str | None, default: tuple[int, int, int]) -> tuple[int, int, int]:
    """A 6-digit hex colour (with or without #) as a tuple, or `default`."""
    try:
        raw = bytes.fromhex((value or "").lstrip("#"))
    except ValueError:
        return default
    return (raw[0], raw[1], raw[2]) if len(raw) == 3 else default


def render_text_strip(
    text: str,
    color: str,
    bg_color: str | None,
    font_config: Any,
    char_height: int,
):
    """Draw a line of text the way text mode lays it out, as one wide picture.

    Text mode sends the panel one bitmap per character, each in a cell of half
    or full width, so this repeats that rule instead of measuring the line as a
    whole. A font that declares variable width is laid out as one line.
    Inline colour tags colour single characters as they do on the panel.
    """
    import unicodedata

    from PIL import Image, ImageDraw, ImageFont
    from pypixelcolor.commands.send_text.color_utils import (
        has_color_tags, parse_colored_text, strip_color_tags,
    )
    from pypixelcolor.commands.send_text.image_processing import apply_pixel_threshold

    fg = _rgb(color, (255, 255, 255))
    bg = _rgb(bg_color, (0, 0, 0))
    font_size = font_config.font_size if font_config.font_size is not None else char_height
    font = ImageFont.truetype(font_config.path, font_size)
    offset = tuple(font_config.offset)
    threshold = font_config.pixel_threshold

    if font_config.var_width:
        clean = strip_color_tags(text) if has_color_tags(text) else text
        mask = Image.new("L", (max(1, len(clean)) * char_height, char_height), 0)
        ImageDraw.Draw(mask).text(offset, clean, fill=255, font=font)
        mask = apply_pixel_threshold(mask, threshold)
        bbox = mask.getbbox()
        width = (bbox[2] + 2) if bbox else 1
        cells = [(mask.crop((0, 0, width, char_height)), fg)]
    else:
        clean, char_colors = parse_colored_text(text, color)
        half = 16 if char_height >= 32 else 8
        full = 2 * half
        cells = []
        for index, char in enumerate(clean):
            probe = Image.new("L", (100, char_height), 0)
            box = ImageDraw.Draw(probe).textbbox((0, 0), char, font=font)
            wide = (
                unicodedata.east_asian_width(char) in ("W", "F")
                or (box[2] - box[0]) > int(half * 1.25)
            )
            cell = Image.new("L", (full if wide else half, char_height), 0)
            ImageDraw.Draw(cell).text(offset, char, fill=255, font=font)
            cell = apply_pixel_threshold(cell, threshold)
            char_color = fg
            if char_colors is not None and index < len(char_colors):
                char_color = _rgb(char_colors[index], fg)
            cells.append((cell, char_color))

    total = sum(cell.size[0] for cell, _ in cells) or 1
    strip = Image.new("RGB", (total, char_height), bg)
    x = 0
    for cell, cell_color in cells:
        strip.paste(Image.new("RGB", cell.size, cell_color), (x, 0), cell)
        x += cell.size[0]
    return strip


def build_text_preview(
    text: str,
    color: str,
    bg_color: str | None,
    font: str | None,
    char_height: int,
    width: int,
    height: int,
    animation: int,
) -> tuple[bytes, str | None]:
    """The text-mode preview: (first view as PNG, whole line as base64 PNG or None).

    The first view is what the panel shows when the content arrives, so a
    plain picture card (or the entity's thumbnail) is right for every effect.
    The whole line is only produced for the effects that move the text. Runs
    in the executor.
    """
    from PIL import Image
    from pypixelcolor.commands.send_text.font_utils import resolve_font_config

    from .device.text import resolve_text_font

    font_config = resolve_font_config(resolve_text_font(font, char_height))
    strip = render_text_strip(text, color, bg_color, font_config, char_height)

    first = Image.new("RGB", (width, height), _rgb(bg_color, (0, 0, 0)))
    first.paste(strip.crop((0, 0, min(strip.size[0], width), char_height)),
                (0, (height - char_height) // 2))
    out = io.BytesIO()
    first.save(out, format="PNG")

    line = None
    if animation in SCROLL_EFFECTS:
        buf = io.BytesIO()
        strip.save(buf, format="PNG")
        encoded = base64.b64encode(buf.getvalue()).decode()
        if len(encoded) <= MAX_STRIP_BYTES:
            line = encoded
    return out.getvalue(), line


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
