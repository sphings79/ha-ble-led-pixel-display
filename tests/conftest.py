"""Test setup.

The integration's package ``__init__`` imports Home Assistant, which these
tests do not install. The modules under test here are plain Python, so the
package is registered without running its ``__init__``: submodules then
import normally and their relative imports resolve.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = ROOT / "custom_components" / "ble_led_pixel"


def _register_package(name: str, path: Path) -> None:
    if name in sys.modules:
        return
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module


_register_package("custom_components", ROOT / "custom_components")
_register_package("custom_components.ble_led_pixel", PACKAGE_DIR)
