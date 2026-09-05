"""Font location utilities for BLE LED Pixel Display integration."""
from __future__ import annotations

import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

# Font lookups touch the filesystem, including a recursive walk of the system
# font directories. That must not happen on the event loop - Home Assistant
# flags it as a blocking call. build_font_index() does the scanning once from
# an executor thread during setup; every lookup afterwards is served from here.
_FONT_INDEX: dict[str, Path] | None = None
_FONT_NAMES: list[str] | None = None


def build_font_index() -> None:
    """Scan every font location and cache the result.

    Blocking - call from an executor thread, not from the event loop.
    """
    global _FONT_INDEX, _FONT_NAMES

    index: dict[str, Path] = {}
    for location in get_font_locations():
        try:
            for pattern in ("*.ttf", "*.otf"):
                # Top level first so it wins over anything nested, then
                # subdirectories, which is where system fonts usually live.
                for font_file in list(location.glob(pattern)) + list(location.rglob(pattern)):
                    if not font_file.is_file():
                        continue
                    # Reachable both as "VCR_OSD_MONO" and "VCR_OSD_MONO.ttf"
                    index.setdefault(font_file.name.lower(), font_file)
                    index.setdefault(font_file.stem.lower(), font_file)
        except (OSError, PermissionError) as err:
            _LOGGER.debug("Could not scan directory %s: %s", location, err)

    _FONT_INDEX = index
    _FONT_NAMES = sorted({path.name for path in index.values()}) or ["OpenSans-Light.ttf"]
    _LOGGER.debug("Font index built: %d fonts from %d keys", len(_FONT_NAMES), len(index))


def get_font_locations() -> list[Path]:
    """Get list of font directories sorted by priority.

    Priority order:
    1. Custom fonts from this integration's fonts/ folder
    2. Fonts from pypixelcolor package
    3. System fonts (Linux standard locations)

    Returns:
        List of Path objects for font directories that exist
    """
    locations = []

    # 1st priority: Custom fonts from this integration
    custom_fonts_dir = Path(__file__).parent / "fonts"
    if custom_fonts_dir.exists() and custom_fonts_dir.is_dir():
        locations.append(custom_fonts_dir)
        _LOGGER.debug("Added custom fonts directory: %s", custom_fonts_dir)

    # 2nd priority: pypixelcolor package fonts
    try:
        import pypixelcolor
        pypixelcolor_fonts_dir = Path(pypixelcolor.__file__).parent / "fonts"
        if pypixelcolor_fonts_dir.exists() and pypixelcolor_fonts_dir.is_dir():
            locations.append(pypixelcolor_fonts_dir)
            _LOGGER.debug("Added pypixelcolor fonts directory: %s", pypixelcolor_fonts_dir)
    except (ImportError, AttributeError) as e:
        _LOGGER.debug("Could not locate pypixelcolor fonts: %s", e)

    # 3rd priority: System fonts (Linux standard locations)
    system_font_paths = [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".fonts",
        Path.home() / "fonts",
        Path.home() / "homeassistant/fonts",
        Path.home() / ".local/share/fonts",
    ]

    for font_path in system_font_paths:
        if font_path.exists() and font_path.is_dir():
            locations.append(font_path)
            _LOGGER.debug("Added system fonts directory: %s", font_path)

    if not locations:
        _LOGGER.warning("No font directories found!")

    return locations


def get_font_path(font_name: str, locations: list[Path] | None = None) -> Path | None:
    """Find font file in available font locations.

    Args:
        font_name: Font filename (with or without extension)
        locations: Optional list of font directories to search (uses get_font_locations() if None)

    Returns:
        Path to font file if found, None otherwise
    """
    # Serve from the prebuilt index whenever the caller did not ask for
    # specific locations. Keeps the lookup off the filesystem.
    if locations is None and _FONT_INDEX is not None:
        hit = _FONT_INDEX.get(font_name.lower())
        if hit is None and not any(
            font_name.lower().endswith(ext) for ext in ('.ttf', '.otf', '.woff', '.woff2')
        ):
            hit = _FONT_INDEX.get(f"{font_name.lower()}.ttf")
        if hit is None:
            _LOGGER.warning("Font %s not found in any location", font_name)
        return hit

    # Add common font extensions if not present
    if not any(font_name.lower().endswith(ext) for ext in ['.ttf', '.otf', '.woff', '.woff2']):
        font_name += '.ttf'

    # Get font locations if not provided
    if locations is None:
        locations = get_font_locations()

    # Search each location in priority order
    for location in locations:
        font_path = location / font_name
        if font_path.exists() and font_path.is_file():
            _LOGGER.debug("Found font %s in %s", font_name, location)
            return font_path

        # Also search subdirectories (common for system fonts)
        for subfont_path in location.rglob(font_name):
            if subfont_path.is_file():
                _LOGGER.debug("Found font %s in %s", font_name, subfont_path.parent)
                return subfont_path

    _LOGGER.warning("Font %s not found in any location", font_name)
    return None


def get_available_fonts(locations: list[Path] | None = None) -> list[str]:
    """Get list of available font filenames from all locations.

    Args:
        locations: Optional list of font directories to search (uses get_font_locations() if None)

    Returns:
        Sorted list of unique font filenames
    """
    if locations is None and _FONT_NAMES is not None:
        return list(_FONT_NAMES)

    if locations is None:
        locations = get_font_locations()

    fonts = set()

    # Scan each location for fonts
    for location in locations:
        try:
            # Scan for TTF fonts
            for font_file in location.glob("*.ttf"):
                fonts.add(font_file.name)

            # Scan for OTF fonts
            for font_file in location.glob("*.otf"):
                fonts.add(font_file.name)

            # Also check subdirectories (for system fonts)
            for font_file in location.rglob("*.ttf"):
                if font_file.is_file():
                    fonts.add(font_file.name)

            for font_file in location.rglob("*.otf"):
                if font_file.is_file():
                    fonts.add(font_file.name)

        except (OSError, PermissionError) as e:
            _LOGGER.debug("Could not scan directory %s: %s", location, e)

    # Ensure we have at least a default font
    if not fonts:
        fonts.add("OpenSans-Light.ttf")

    _LOGGER.debug("Found %d unique fonts across all locations", len(fonts))
    return sorted(list(fonts))

# Shipped with the integration, so it is available regardless of which
# pypixelcolor version is installed.
FALLBACK_FONT = "VCR_OSD_MONO.ttf"


def resolve_font_for_library(font_name: str | None) -> str:
    """Resolve a font name to an absolute path for pypixelcolor.

    pypixelcolor accepts either one of its built-in font names or a path to a
    font file. The set of built-in names is not stable: 0.4 shipped CUSONG,
    SIMSUN and VCR_OSD_MONO, while later versions replaced all three with a
    single UNIFONT. Handing over an absolute path keeps this integration
    working across both, and lets users drop their own fonts into the
    integration's fonts/ folder.

    Args:
        font_name: Font filename or name, with or without extension.

    Returns:
        An absolute path when the font was found anywhere in the search
        locations, otherwise the name unchanged so the library can still try
        to resolve it as one of its own.
    """
    for candidate in (font_name, FALLBACK_FONT):
        if not candidate:
            continue
        path = get_font_path(candidate)
        if path is not None:
            return str(path)

    _LOGGER.warning(
        "Font %s not found and fallback %s missing; passing the name to the "
        "library unchanged", font_name, FALLBACK_FONT
    )
    return font_name or FALLBACK_FONT
