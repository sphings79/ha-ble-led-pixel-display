"""Text display commands using pypixelcolor."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional, Union

try:
    from pypixelcolor.commands.send_text import send_text
    from pypixelcolor.lib.font_config import FontConfig
    from pypixelcolor.lib.transport.send_plan import SendPlan
except ImportError:
    send_text = None
    FontConfig = None
    SendPlan = None

_LOGGER = logging.getLogger(__name__)

# pypixelcolor's built-in font since 0.5.0 (GNU Unifont, OFL 1.1).
BUILTIN_FONT = "UNIFONT"

# Threshold for a font file without a sidecar JSON. pypixelcolor 0.4 used
# this, so such fonts render as they did before 0.5.
_DEFAULT_PIXEL_THRESHOLD = 70


def _sidecar_metrics(font_path: Path, char_height: int) -> dict[str, Any] | None:
    """Return the sidecar JSON metrics closest to char_height, if any.

    The fonts shipped in fonts/ carry a ``<font>.json`` with metrics per
    character height (font_size, offset, pixel_threshold, var_width).
    pypixelcolor 0.4 read these itself; 0.5 dropped that, so without this the
    files were bundled but ignored and every font rendered with defaults.
    """
    json_path = font_path.with_suffix(".json")
    if not json_path.is_file():
        return None
    try:
        config = json.loads(json_path.read_text(encoding="utf-8"))
        metrics = {int(h): m for h, m in config["metrics"].items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as err:
        _LOGGER.warning("Ignoring invalid font metrics %s: %s", json_path, err)
        return None
    if not metrics:
        return None
    closest = min(metrics, key=lambda h: abs(h - char_height))
    chosen = metrics[closest]
    if not isinstance(chosen, dict):
        _LOGGER.warning(
            "Ignoring invalid font metrics for height %s in %s", closest, json_path
        )
        return None
    return chosen


def _is_builtin_font_file(path: Path) -> bool:
    """True for pypixelcolor's own Unifont file, which it tunes itself."""
    try:
        from pypixelcolor.lib.font_config import UNIFONT_PATH
    except ImportError:
        return False
    return path.resolve() == Path(UNIFONT_PATH).resolve()


def resolve_text_font(font: str | None, char_height: int) -> Union[str, Any]:
    """Turn a font path into what pypixelcolor 0.5 expects.

    Returns the built-in font name for anything that is not an existing file,
    otherwise a FontConfig carrying the font's sidecar metrics. Does file I/O,
    so call it from an executor.
    """
    if not font or FontConfig is None:
        return BUILTIN_FONT
    path = Path(font)
    if not path.is_file() or _is_builtin_font_file(path):
        return BUILTIN_FONT
    settings = _font_settings(_sidecar_metrics(path, char_height) or {}, char_height, path)
    try:
        return FontConfig.from_file(path, **settings)
    except (OSError, ValueError, TypeError) as err:
        _LOGGER.warning("Could not load font %s, using %s: %s", font, BUILTIN_FONT, err)
        return BUILTIN_FONT


def _font_settings(metrics: dict, char_height: int, path: Path) -> dict[str, Any]:
    """FontConfig keywords from sidecar metrics; defaults if any are malformed.

    A user's sidecar can be valid JSON and still hold nonsense (an offset of
    {} or [1]), which must not stop the text from being sent.
    """
    defaults = {
        "font_size": char_height,
        "offset": (0, 0),
        "pixel_threshold": _DEFAULT_PIXEL_THRESHOLD,
        "var_width": False,
    }
    try:
        offset = metrics.get("offset", (0, 0))
        if not isinstance(offset, (list, tuple)) or len(offset) != 2:
            raise ValueError(f"offset must be two numbers, got {offset!r}")
        var_width = metrics.get("var_width", False)
        if not isinstance(var_width, bool):
            raise ValueError(f"var_width must be true or false, got {var_width!r}")
        font_size = int(metrics.get("font_size", char_height))
        if font_size < 1:
            raise ValueError(f"font_size must be positive, got {font_size}")
        pixel_threshold = int(metrics.get("pixel_threshold", _DEFAULT_PIXEL_THRESHOLD))
        if not 0 <= pixel_threshold <= 255:
            raise ValueError(f"pixel_threshold must be 0-255, got {pixel_threshold}")
        return {
            "font_size": font_size,
            "offset": (int(offset[0]), int(offset[1])),
            "pixel_threshold": pixel_threshold,
            "var_width": var_width,
        }
    except (ValueError, TypeError, OverflowError) as err:
        _LOGGER.warning("Ignoring invalid font metrics in %s: %s", path.with_suffix(".json"), err)
        return defaults


def make_text_command(
    text: str,
    font: str,
    color: str = "ffffff",
    bg_color: Optional[str] = None,
    animation: int = 0,
    speed: int = 80,
    rainbow_mode: int = 0,
    save_slot: int = 0,
    char_height: Optional[int] = None
) -> SendPlan:
    """Build text display command using pypixelcolor.

    Args:
        text: The text to display
        font: Absolute path to a font file, as returned by
            fonts.resolve_font_for_library(). Required rather than defaulted:
            the built-in font names are not stable across pypixelcolor
            releases -- 0.4 shipped CUSONG, SIMSUN and VCR_OSD_MONO, 0.5
            replaced all three with UNIFONT -- so a default here would name a
            font that quietly stops existing.
        color: Text color in hex format (e.g., 'ffffff')
        bg_color: Background color in hex format (e.g., '000000'), or None for transparent
        animation: Animation type (0-7, excluding 3&4 on non-32x32 devices)
        speed: Animation speed (0-100)
        rainbow_mode: Rainbow mode (0-9)
        save_slot: Save slot (0-255)
        char_height: Character height in pixels (auto-detected if None)

    Reads the font and its sidecar metrics from disk, so call it from an
    executor.

    Returns:
        The pypixelcolor SendPlan. Pass it to BluetoothClient.send_plan(),
        which chunks each window and waits for the per-window ACK; writing
        the raw window data as single packets fails for longer texts.

    Raises:
        ImportError: If pypixelcolor is not available
        ValueError: If parameters are out of valid ranges
    """
    if send_text is None:
        raise ImportError("pypixelcolor library is not installed")

    # Call pypixelcolor's send_text function
    send_plan = send_text(
        text=text,
        color=color,
        bg_color=bg_color,
        font=resolve_text_font(font, char_height or 16),
        animation=animation,
        speed=speed,
        rainbow_mode=rainbow_mode,
        save_slot=save_slot,
        char_height=char_height
    )

    return send_plan
