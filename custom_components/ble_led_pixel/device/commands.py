"""Command building for BLE LED pixel panels."""
from __future__ import annotations


def make_power_command(on: bool) -> bytes:
    """Build power control command.
    
    Command format from protocol documentation:
    [5, 0, 7, 1, on_byte] where on_byte = 1 for on, 0 for off
    """
    on_byte = 1 if on else 0
    return bytes([5, 0, 7, 1, on_byte])


def make_brightness_command(brightness: int) -> bytes:
    """Build brightness control command.

    Command 0x8004 from ipixel-ctrl set_brightness.py

    Args:
        brightness: Brightness level from 1 to 100

    Returns:
        Command bytes for brightness control

    Raises:
        ValueError: If brightness is not in valid range (1-100)
    """
    if brightness < 1 or brightness > 100:
        raise ValueError("Brightness must be between 1 and 100")

    return make_command_payload(0x8004, bytes([brightness]))


def make_command_payload(opcode: int, payload: bytes) -> bytes:
    """Create command with header (following ipixel-ctrl/common.py format)."""
    total_length = len(payload) + 4  # +4 for length and opcode
    
    command = bytearray()
    command.extend(total_length.to_bytes(2, 'little'))  # Length (little-endian)
    command.extend(opcode.to_bytes(2, 'little'))        # Opcode (little-endian)
    command.extend(payload)                             # Payload data
    
    return bytes(command)

def make_preset_command(preset: int, language: int = 0) -> bytes:
    """Build the command that shows a preset stored in the panel's firmware.

    Costs six bytes against a full frame buffer, because nothing is
    transferred -- the animation already lives on the panel. Which twenty
    presets these are depends on the model: some ship a road-sign set
    (emergency, turn left, baby on board), others a set of moods.

    Frame: [6, 0, 7, 0x80, preset, language]

    Args:
        preset: Preset number, 1-20.
        language: UI language byte the app sends alongside. Panels that show
            text in a preset use it to pick the wording.
    """
    return bytes([6, 0, 7, 0x80, preset & 0xFF, language & 0xFF])


def make_scoreboard_command(home: int, away: int) -> bytes:
    """Build the scoreboard command.

    Both scores are 16-bit and big-endian, which is the one place this
    protocol departs from little-endian.

    Frame: [8, 0, 0x0A, 0x80, home_hi, home_lo, away_hi, away_lo]
    """
    return bytes([
        8, 0, 0x0A, 0x80,
        (home >> 8) & 0xFF, home & 0xFF,
        (away >> 8) & 0xFF, away & 0xFF,
    ])


def make_countdown_command(running: bool, minutes: int, seconds: int) -> bytes:
    """Build the countdown timer command.

    Frame: [7, 0, 0x0D, 0x80, flag, minutes, seconds]

    Args:
        running: True starts the countdown, False stops it.
        minutes: Minutes to count down from, 0-99.
        seconds: Seconds to count down from, 0-59.
    """
    return bytes([
        7, 0, 0x0D, 0x80,
        1 if running else 0,
        minutes & 0xFF,
        seconds & 0xFF,
    ])


def make_stopwatch_command(running: bool) -> bytes:
    """Build the stopwatch command.

    Frame: [5, 0, 9, 0x80, flag]

    The panel counts on its own once started; there is no way to read the
    elapsed time back.
    """
    return bytes([5, 0, 9, 0x80, 1 if running else 0])
