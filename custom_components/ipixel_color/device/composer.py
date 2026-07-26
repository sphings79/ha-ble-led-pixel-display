"""Compose an MDI icon and/or text at arbitrary positions on a single canvas.

Unlike send_mdi_icon (which centers one icon on the whole panel) or the
native send_text (device-rendered, no positioning control), this lets you
place an icon and a text label independently, each at its own top-left
(x, y) position - then sends the whole composed canvas as a single image,
reusing the same pipeline as send_mdi_icon.
"""
from __future__ import annotations

import io
import logging

import aiohttp
from PIL import Image, ImageDraw, ImageFont

from ..color import hex_to_rgb
from ..fonts import get_font_locations, get_font_path
from .mdi_icon import build_mdi_icon_png, fetch_mdi_svg, render_mdi_icon

_LOGGER = logging.getLogger(__name__)

# Smallest bundled bitmap font - use this when no explicit font is requested
DEFAULT_SMALL_FONT = "3x5-de"
DEFAULT_SMALL_FONT_SIZE = 6


def _wrap_line(line: str, font_obj: ImageFont.FreeTypeFont, draw: ImageDraw.ImageDraw, max_width: int) -> list[str]:
    """Greedily word-wrap a single line to fit within max_width pixels.

    Args:
        line: A single line of text (no '\\n').
        font_obj: The font to measure with.
        draw: An ImageDraw instance used for measurement only.
        max_width: Maximum line width in pixels.

    Returns:
        List of wrapped sub-lines. A single word wider than max_width is
        kept on its own line rather than being split mid-word.
    """
    words = line.split(" ")
    wrapped: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        width = draw.textbbox((0, 0), candidate, font=font_obj)[2]
        if width <= max_width or not current:
            current = candidate
        else:
            wrapped.append(current)
            current = word
    if current:
        wrapped.append(current)
    return wrapped


def render_text_element(
    text: str,
    font_size: float = DEFAULT_SMALL_FONT_SIZE,
    font_name: str | None = None,
    color_hex: str = "ffffff",
    max_width: int | None = None,
    line_spacing: int = 1,
) -> Image.Image:
    """Render text tightly cropped to its own bounding box (no fixed canvas).

    Explicit '\\n' in the text always forces a line break, regardless of
    max_width. If max_width is given, each resulting line is additionally
    word-wrapped to fit within it (e.g. to avoid running off the edge of
    the panel).

    Args:
        text: Text to render. '\\n' forces a line break.
        font_size: Font size in pixels (can be fractional).
        font_name: Bundled font name (e.g. '3x5-de', '5x5', '7x5',
            'OpenSans-Light', 'WP7xn'), or None for the smallest bundled font.
        color_hex: Text color in hex, with or without '#'.
        max_width: If given, word-wrap each line to fit within this many
            pixels. None disables automatic wrapping (only '\\n' breaks lines).
        line_spacing: Extra vertical gap between lines, in pixels.

    Returns:
        RGBA PIL Image sized exactly to the rendered (possibly multi-line) text.
    """
    locations = get_font_locations()
    font_path = get_font_path(font_name or DEFAULT_SMALL_FONT, locations)

    # Accept both a real newline character and a literal '\n' (two chars,
    # backslash + n) as a forced line break - the latter is what arrives
    # when someone types \n into a plain GUI text field (no YAML escape
    # processing happens there), rather than an actual newline.
    text = text.replace("\\n", "\n")

    if font_path is not None:
        font_obj = ImageFont.truetype(str(font_path), size=max(1, round(font_size)))
    else:
        _LOGGER.warning("Font '%s' not found, falling back to PIL default", font_name)
        font_obj = ImageFont.load_default()

    probe = Image.new("RGBA", (1, 1))
    probe_draw = ImageDraw.Draw(probe)

    # Explicit '\n' always breaks; max_width additionally wraps each of those lines
    raw_lines = text.split("\n")
    if max_width is not None:
        lines: list[str] = []
        for raw_line in raw_lines:
            lines.extend(_wrap_line(raw_line, font_obj, probe_draw, max_width) or [""])
    else:
        lines = raw_lines

    # Measure each line
    line_boxes = [probe_draw.textbbox((0, 0), line, font=font_obj) for line in lines]
    line_heights = [max(1, box[3] - box[1]) for box in line_boxes]
    line_widths = [max(1, box[2] - box[0]) for box in line_boxes]

    text_w = max(line_widths)
    text_h = sum(line_heights) + line_spacing * (len(lines) - 1)

    img = Image.new("RGBA", (text_w, text_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    rgb = hex_to_rgb(color_hex)

    y_offset = 0
    for line, box, height in zip(lines, line_boxes, line_heights):
        draw.text((-box[0], y_offset - box[1]), line, font=font_obj, fill=rgb + (255,))
        y_offset += height + line_spacing

    return img


async def _build_base_canvas(
    canvas_width: int,
    canvas_height: int,
    session: aiohttp.ClientSession,
    bg_color_hex: str,
    icon: str | None,
    icon_x: int,
    icon_y: int,
    icon_size: int | None,
    icon_color_hex: str,
    image_bytes: bytes | None = None,
    image_x: int = 0,
    image_y: int = 0,
    image_width: int | None = None,
    image_height: int | None = None,
) -> Image.Image:
    """Build the background+icon+image canvas shared by both static and scrolling output."""
    bg_rgb = hex_to_rgb(bg_color_hex)
    canvas = Image.new("RGB", (canvas_width, canvas_height), bg_rgb)

    if icon:
        size_px = icon_size or min(canvas_width, canvas_height)
        svg_markup = await fetch_mdi_svg(icon, session)
        icon_img = render_mdi_icon(svg_markup, size_px, icon_color_hex)
        canvas.paste(icon_img, (icon_x, icon_y), mask=icon_img)

    if image_bytes is not None:
        img = Image.open(io.BytesIO(image_bytes))
        if getattr(img, "is_animated", False):
            img.seek(0)  # static insertion: first frame only
        img = img.convert("RGBA")
        if image_width or image_height:
            target_w = image_width or img.width
            target_h = image_height or img.height
            img = img.resize((target_w, target_h))
        canvas.paste(img, (image_x, image_y), mask=img)

    return canvas


def build_scrolling_text_gif(
    base_canvas: Image.Image,
    text: str,
    text_x: int,
    text_y: int,
    text_size: float,
    text_font: str | None,
    text_color_hex: str,
    text_line_spacing: int,
    scroll_step: int = 2,
    frame_ms: int = 80,
    gap_px: int = 16,
) -> bytes:
    """Build a looping horizontal-scroll (marquee) GIF of text over a static base canvas.

    The text is rendered at its natural (unwrapped) width, then a window of
    the panel's available width is scrolled across it, looping continuously:
    once the text has fully scrolled past, a blank gap of gap_px plays before
    it restarts from the right edge, for a clean, non-jarring loop.

    Args:
        base_canvas: The static background (already composed with bg/icon),
            reused unchanged as every frame's backdrop.
        text: Text to scroll. '\\n' still forces separate lines, each
            scrolling together as one block.
        text_x: Left edge of the scroll window, in pixels.
        text_y: Top of the text block, in pixels.
        text_size: Font size in pixels (can be fractional).
        text_font: Bundled font name, or None for the smallest bundled font.
        text_color_hex: Text color, hex without '#'.
        text_line_spacing: Extra vertical gap between forced lines, in pixels.
        scroll_step: Pixels moved per frame (higher = faster, choppier).
        frame_ms: Duration of each frame in milliseconds.
        gap_px: Blank pixels between the end of one pass and the next.

    Returns:
        GIF-encoded bytes, looping forever (loop=0).
    """
    canvas_width, canvas_height = base_canvas.size
    visible_width = max(1, canvas_width - text_x)

    # Render at full natural width - no wrapping, scrolling makes it moot
    text_img = render_text_element(
        text, text_size, text_font, text_color_hex,
        max_width=None, line_spacing=text_line_spacing,
    )

    # Build a seamless loop strip: text, then a blank gap, then the text
    # again - so cropping a sliding window never shows a hard cut.
    strip_w = text_img.width + gap_px
    strip = Image.new("RGBA", (strip_w * 2, text_img.height), (0, 0, 0, 0))
    strip.paste(text_img, (0, 0), mask=text_img)
    strip.paste(text_img, (strip_w, 0), mask=text_img)

    frames = []
    offset = 0
    while offset < strip_w:
        frame = base_canvas.copy()
        window = strip.crop((offset, 0, offset + visible_width, text_img.height))
        frame.paste(window, (text_x, text_y), mask=window)
        frames.append(frame)
        offset += scroll_step

    if not frames:
        frames = [base_canvas.copy()]

    buf = io.BytesIO()
    frames[0].save(
        buf, format="GIF", save_all=True, append_images=frames[1:],
        duration=frame_ms, loop=0, disposal=2, optimize=False,
    )
    return buf.getvalue()


async def build_layout_media(
    canvas_width: int,
    canvas_height: int,
    session: aiohttp.ClientSession,
    bg_color_hex: str = "000000",
    icon: str | None = None,
    icon_x: int = 0,
    icon_y: int = 0,
    icon_size: int | None = None,
    icon_color_hex: str = "ffffff",
    image_bytes: bytes | None = None,
    image_x: int = 0,
    image_y: int = 0,
    image_width: int | None = None,
    image_height: int | None = None,
    text: str | None = None,
    text_x: int = 0,
    text_y: int = 0,
    text_size: float = DEFAULT_SMALL_FONT_SIZE,
    text_font: str | None = None,
    text_color_hex: str = "ffffff",
    text_wrap: bool = True,
    text_line_spacing: int = 1,
    text_scroll: bool = False,
    text_scroll_step: int = 2,
    text_scroll_frame_ms: int = 80,
    text_scroll_gap: int = 16,
) -> tuple[bytes, str]:
    """Compose an icon, a static image/GIF-first-frame, and/or text, and return (data, file_extension).

    Returns a static PNG unless text_scroll is True AND the text is
    actually wider than the available space (in which case a looping
    scroll GIF is built instead - a short static text still returns PNG,
    since there'd be nothing to usefully scroll).

    See build_layout_png's docstring for the shared icon/text parameters. Additional:
        image_bytes: Raw bytes of an image/GIF file to insert (only its
            first frame, if animated) at (image_x, image_y). None to skip.
        image_x: Image top-left X position in pixels.
        image_y: Image top-left Y position in pixels.
        image_width: If given, resize the image to this width.
        image_height: If given, resize the image to this height.
        text_scroll: If True, scroll text too wide to fit instead of
            clipping it. Ignored if the text already fits.
        text_scroll_step: Pixels moved per animation frame.
        text_scroll_frame_ms: Duration of each frame in milliseconds.
        text_scroll_gap: Blank pixels between loop passes.

    Returns:
        Tuple of (encoded bytes, ".png" or ".gif").
    """
    base_canvas = await _build_base_canvas(
        canvas_width, canvas_height, session, bg_color_hex,
        icon, icon_x, icon_y, icon_size, icon_color_hex,
        image_bytes, image_x, image_y, image_width, image_height,
    )

    if text and text_scroll:
        # Only actually scroll if it doesn't already fit - measure first
        probe_img = render_text_element(
            text, text_size, text_font, text_color_hex, max_width=None,
        )
        if probe_img.width > max(1, canvas_width - text_x):
            gif_bytes = build_scrolling_text_gif(
                base_canvas, text, text_x, text_y, text_size, text_font,
                text_color_hex, text_line_spacing,
                scroll_step=text_scroll_step, frame_ms=text_scroll_frame_ms,
                gap_px=text_scroll_gap,
            )
            return gif_bytes, ".gif"

    canvas = base_canvas.copy()
    if text:
        max_width = max(1, canvas_width - text_x) if text_wrap else None
        text_img = render_text_element(
            text, text_size, text_font, text_color_hex,
            max_width=max_width, line_spacing=text_line_spacing,
        )
        canvas.paste(text_img, (text_x, text_y), mask=text_img)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue(), ".png"


async def build_layout_png(
    canvas_width: int,
    canvas_height: int,
    session: aiohttp.ClientSession,
    bg_color_hex: str = "000000",
    icon: str | None = None,
    icon_x: int = 0,
    icon_y: int = 0,
    icon_size: int | None = None,
    icon_color_hex: str = "ffffff",
    text: str | None = None,
    text_x: int = 0,
    text_y: int = 0,
    text_size: float = DEFAULT_SMALL_FONT_SIZE,
    text_font: str | None = None,
    text_color_hex: str = "ffffff",
    text_wrap: bool = True,
    text_line_spacing: int = 1,
) -> bytes:
    """Compose an icon and/or text at their own positions onto one canvas.

    Args:
        canvas_width: Device width in pixels.
        canvas_height: Device height in pixels.
        session: aiohttp session for fetching the MDI icon (if any).
        bg_color_hex: Canvas background color, hex without '#'.
        icon: MDI icon name (with or without 'mdi:'), or None to skip.
        icon_x: Icon top-left X position in pixels.
        icon_y: Icon top-left Y position in pixels.
        icon_size: Icon size in pixels (square). Defaults to the canvas's
            smaller dimension if not given.
        icon_color_hex: Icon fill color, hex without '#'.
        text: Text to render, or None to skip. '\\n' always forces a line
            break regardless of text_wrap.
        text_x: Text top-left X position in pixels.
        text_y: Text top-left Y position in pixels.
        text_size: Font size in pixels (can be fractional).
        text_font: Bundled font name, or None for the smallest bundled font.
        text_color_hex: Text color, hex without '#'.
        text_wrap: If True (default), automatically word-wrap text that
            would run past the panel's right edge given text_x. If False,
            only explicit '\\n' breaks lines.
        text_line_spacing: Extra vertical gap between wrapped/forced lines, in pixels.

    Returns:
        PNG-encoded bytes of the composed canvas.
    """
    data, _ext = await build_layout_media(
        canvas_width=canvas_width, canvas_height=canvas_height, session=session,
        bg_color_hex=bg_color_hex,
        icon=icon, icon_x=icon_x, icon_y=icon_y, icon_size=icon_size, icon_color_hex=icon_color_hex,
        text=text, text_x=text_x, text_y=text_y, text_size=text_size,
        text_font=text_font, text_color_hex=text_color_hex,
        text_wrap=text_wrap, text_line_spacing=text_line_spacing, text_scroll=False,
    )
    return data
