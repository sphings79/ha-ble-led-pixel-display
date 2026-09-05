"""Which extra features a panel actually has.

Not every panel can do everything. The vendor app decides what to offer by
looking at the LED type and, for a long list of models, at the exact product
id -- two panels of the same resolution can differ. Sending a command a panel
does not implement is not obviously harmful, but it does nothing useful and
leaves a Home Assistant action that silently has no effect, so the features
below are only offered where the app offers them too.

The table is transcribed from `ChooseActivity.showMenuType` in iPixel Color
3.7.7, which picks a list of reachable screens per device, cross-checked
against `Constants.getCategoryData`, which builds the matching menu. Where the
two disagreed the dispatcher won, because that is what actually gates access.

Two more features exist in the same table and are not implemented here:
scheduled content (`TimingActivity`) and the alarm clock (`AlarmClockActivity`).

A panel the table does not know gets nothing, which would be the wrong answer
for hardware that is simply newer than this list. The options flow can turn
the features on by hand for that case -- see `OPT_FORCE_FEATURES`.
"""
from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

FEATURE_PRESETS = "presets"
FEATURE_SCOREBOARD = "scoreboard"
FEATURE_COUNTDOWN = "countdown"
FEATURE_STOPWATCH = "stopwatch"

ALL_FEATURES: frozenset[str] = frozenset(
    {FEATURE_PRESETS, FEATURE_SCOREBOARD, FEATURE_COUNTDOWN, FEATURE_STOPWATCH}
)

# Shorthands for the combinations the app's own screen lists produce.
_NONE: frozenset[str] = frozenset()
_P = frozenset({FEATURE_PRESETS})
_PS = frozenset({FEATURE_PRESETS, FEATURE_SCOREBOARD})
_PSS = frozenset({FEATURE_PRESETS, FEATURE_SCOREBOARD, FEATURE_STOPWATCH})
# The "mecha" family is the odd one out: it is the only one with a countdown,
# and the only one with no presets.
_MECHA = frozenset({FEATURE_SCOREBOARD, FEATURE_STOPWATCH, FEATURE_COUNTDOWN})

# LED type -> (features for that type, per product id exceptions).
# Keys of the exception dict are (cid, pid) exactly as advertised.
_TABLE: dict[int, tuple[frozenset[str], dict[tuple[str, str], frozenset[str]]]] = {
    0: (_NONE, {}),
    1: (_P, {
        ("0001", "07"): _PSS, ("0001", "08"): _PSS, ("0036", "01"): _PSS,
        ("0025", "01"): _PS, ("0025", "09"): _PS, ("0025", "10"): _PS,
        ("0001", "131"): _NONE,
        ("0015", "02"): _P, ("0017", "01"): _P,
        ("0001", "63"): _P, ("0001", "64"): _P,
    }),
    # 32x32 panels, including the B.K. Light board sold at Action. The app
    # offers none of these features here.
    2: (_NONE, {}),
    3: (_P, {("0001", "04"): _PSS, ("0001", "05"): _PSS, ("0001", "28"): _PSS}),
    4: (_P, {
        ("0001", "06"): _PSS,
        ("0025", "13"): _PS,
        ("0001", "10"): _NONE, ("0008", "01"): _NONE,
        ("0018", "01"): _NONE, ("0035", "01"): _NONE,
    }),
    5: (_P, {("0001", "04"): _PSS, ("0001", "05"): _PSS, ("0001", "28"): _PSS}),
    6: (_NONE, {}),
    7: (_P, {
        ("0025", "02"): _PS, ("0025", "14"): _PS,
        ("0001", "13"): _PSS, ("0001", "14"): _PSS,
    }),
    8: (_P, {
        ("0025", "02"): _PS, ("0025", "14"): _PS,
        ("0001", "13"): _PSS, ("0001", "14"): _PSS,
    }),
    13: (_NONE, {}),
    16: (_PSS, {("0025", "05"): _PS, ("0025", "12"): _PS}),
    24: (_PSS, {}),
}

# Multi-zone panels share one rule set.
_ZONE_EXCEPTIONS: dict[tuple[str, str], frozenset[str]] = {
    ("0025", "03"): _PS, ("0025", "04"): _PS, ("0025", "11"): _PS,
    **{("0001", pid): _PSS
       for pid in ("15", "16", "17", "18", "21", "22", "29", "30", "129")},
}
for _led_type in (9, 10, 11, 12, 14, 15):
    _TABLE[_led_type] = (_P, _ZONE_EXCEPTIONS)

# Single-colour panels.
_BASE_COLOR_EXCEPTIONS: dict[tuple[str, str], frozenset[str]] = {
    ("0025", "06"): _PS, ("0025", "07"): _PS, ("0025", "08"): _PS,
    ("0015", "09"): _P,
}
for _led_type in (17, 18, 19, 34, 35):
    _TABLE[_led_type] = (_PSS, _BASE_COLOR_EXCEPTIONS)

# The "mecha" family, the only one with a countdown.
for _led_type in (20, 21, 22, 23):
    _TABLE[_led_type] = (_MECHA, {})

# Large panels, all with the same set.
for _led_type in range(25, 34):
    _TABLE[_led_type] = (_PSS, {})


def resolve_features(
    led_type: int | None,
    cid: str | None = None,
    pid: str | None = None,
) -> frozenset[str]:
    """Return the extra features a panel supports.

    Args:
        led_type: Resolved LED type, as produced by `resolve_panel`.
        cid: Component id from the advertisement, where known.
        pid: Product id from the advertisement, where known.

    Returns:
        The supported features. Empty when the panel is not in the table,
        which for a genuinely new model means "unknown" rather than "none" --
        the options flow exists for exactly that case.
    """
    if led_type is None:
        return _NONE

    entry = _TABLE.get(led_type)
    if entry is None:
        _LOGGER.debug(
            "LED type %s is not in the feature table; offering no extra "
            "features. Enable them in the options if your panel has them.",
            led_type,
        )
        return _NONE

    default, exceptions = entry
    if cid is not None and pid is not None:
        specific = exceptions.get((str(cid), str(pid)))
        if specific is not None:
            return specific
    return default
