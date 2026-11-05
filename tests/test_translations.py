"""strings.json is the source; every translation has the same keys and placeholders."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parent.parent / "custom_components" / "ble_led_pixel"
LANGUAGES = ["en", "de", "fr"]


def _flatten(data: dict, prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{prefix}{key}."))
        else:
            flat[f"{prefix}{key}"] = value
    return flat


SOURCE = _flatten(json.loads((PACKAGE / "strings.json").read_text(encoding="utf-8")))


def _load(language: str) -> dict[str, str]:
    path = PACKAGE / "translations" / f"{language}.json"
    return _flatten(json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("language", LANGUAGES)
def test_same_keys_as_the_source(language):
    translated = _load(language)
    assert sorted(set(SOURCE) - set(translated)) == []
    assert sorted(set(translated) - set(SOURCE)) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_same_placeholders_as_the_source(language):
    translated = _load(language)
    for key, text in SOURCE.items():
        assert sorted(re.findall(r"\{\w+\}", translated[key])) == sorted(
            re.findall(r"\{\w+\}", text)
        ), key


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_empty_values(language):
    assert [key for key, text in _load(language).items() if not text.strip()] == []
