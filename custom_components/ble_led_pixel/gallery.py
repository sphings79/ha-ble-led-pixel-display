"""The bundled picture gallery.

The pictures live next to this module as 32x32 PNGs and GIFs, described by
index.json. They are drawn by tools/build_gallery.py in the repository, so the
artwork is generated from reviewable source rather than checked in blind.

Reading the index touches the disk, so it happens once per Home Assistant run
in the executor and is cached from then on.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import NamedTuple

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

GALLERY_DIR = Path(__file__).parent / "gallery"
INDEX_FILE = GALLERY_DIR / "index.json"

# The separator between category and name in the select entity's options. A
# middle dot sorts the list into visible groups without needing a real grouped
# selector, which Home Assistant's select entities do not have.
LABEL_SEPARATOR = " · "


class Motif(NamedTuple):
    """One bundled picture."""

    motif_id: str
    name: str
    category: str
    path: Path
    animated: bool

    @property
    def label(self) -> str:
        """The human-facing name, as shown in the select entity."""
        return f"{self.category}{LABEL_SEPARATOR}{self.name}"


_CACHE: list[Motif] | None = None


def _load_from_disk() -> list[Motif]:
    """Read index.json. Blocking -- call through async_load_gallery."""
    try:
        raw = json.loads(INDEX_FILE.read_text())
    except FileNotFoundError:
        _LOGGER.error("Gallery index missing at %s", INDEX_FILE)
        return []
    except json.JSONDecodeError as err:
        _LOGGER.error("Gallery index at %s is not valid JSON: %s", INDEX_FILE, err)
        return []

    motifs: list[Motif] = []
    for entry in raw:
        path = GALLERY_DIR / entry["file"]
        if not path.is_file():
            _LOGGER.warning("Gallery lists %s but the file is missing", entry["file"])
            continue
        motifs.append(
            Motif(
                motif_id=entry["id"],
                name=entry["name"],
                category=entry["category"],
                path=path,
                animated=bool(entry.get("animated")),
            )
        )
    motifs.sort(key=lambda m: (m.category, m.name))
    return motifs


async def async_load_gallery(hass: HomeAssistant) -> list[Motif]:
    """Return every bundled motif, reading the index at most once per run."""
    global _CACHE
    if _CACHE is None:
        _CACHE = await hass.async_add_executor_job(_load_from_disk)
        _LOGGER.debug("Gallery loaded: %d motifs", len(_CACHE))
    return _CACHE


def find(motifs: list[Motif], wanted: str) -> Motif | None:
    """Look a motif up by id, by name or by the label the select entity shows.

    Automations written against any of the three keep working, which matters
    because the select stores labels while the service takes ids.
    """
    wanted = wanted.strip()
    lowered = wanted.casefold()
    for motif in motifs:
        if wanted in (motif.motif_id, motif.label) or lowered == motif.name.casefold():
            return motif
    return None
