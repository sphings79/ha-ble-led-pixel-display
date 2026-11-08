"""Compare brands.json with the brand table built into the integration.

brands.json is what installed integrations fetch; BRANDS in advertisement.py
is what a release ships. Before a release, run this to see which models were
added to brands.json only, and paste them into BRANDS:

    python3 tools/sync_brands.py

Exits 1 when the two disagree about an entry or when BRANDS holds something
brands.json lacks (installed integrations would not learn it), 0 otherwise.
Entries only in brands.json are reported but are not an error: that is the
state between adding a model and releasing it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "custom_components" / "ble_led_pixel"


def load_builtin() -> dict[str, str]:
    """BRANDS from advertisement.py, without importing Home Assistant.

    The module imports ``.brands`` (which needs Home Assistant), so its source
    is read for the BRANDS literal instead of being imported.
    """
    import ast

    tree = ast.parse((PACKAGE / "advertisement.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "BRANDS":
            code = compile(ast.Expression(node.value), "BRANDS", "eval")
            return eval(code, {})  # noqa: S307 - a literal from our own file
    raise SystemExit("BRANDS not found in advertisement.py")


def load_published() -> dict[str, str]:
    data = json.loads((ROOT / "data" / "brands.json").read_text(encoding="utf-8"))
    return data["brands"]


def compare(builtin: dict[str, str], published: dict[str, str]) -> tuple[list[str], list[str]]:
    """Return (problems, release_candidates)."""
    problems = []
    for cidpid, brand in builtin.items():
        if cidpid not in published:
            problems.append(f"{cidpid}: in BRANDS but not in brands.json")
        elif published[cidpid] != brand:
            problems.append(
                f"{cidpid}: BRANDS says {brand!r}, brands.json says {published[cidpid]!r}"
            )
    candidates = [
        f'    "{cidpid}": "{brand}",'
        for cidpid, brand in sorted(published.items())
        if cidpid not in builtin
    ]
    return problems, candidates


def main() -> int:
    problems, candidates = compare(load_builtin(), load_published())
    for problem in problems:
        print("MISMATCH", problem)
    if candidates:
        print("Only in brands.json -- add to BRANDS for the next release:")
        print("\n".join(candidates))
    if not problems and not candidates:
        print("brands.json and BRANDS agree.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
