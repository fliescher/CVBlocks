"""Bundled CV layouts. No Qt here.

Every layout is one standalone Jinja2 template in layouts/, listed in
layouts/index.yaml. To add a layout, drop `NN-name.html.j2` into that folder
and add an entry to the index.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

LAYOUTS_DIR = Path(__file__).resolve().parents[1] / "layouts"


def discover(directory: Path | None = None) -> list[dict[str, Any]]:
    """Return the layouts from index.yaml, in order. Broken entries are skipped."""
    directory = directory or LAYOUTS_DIR
    index = directory / "index.yaml"
    try:
        document = yaml.safe_load(index.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []

    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in document.get("layouts") or []:
        if not isinstance(entry, dict):
            continue
        slug = str(entry.get("slug") or "").strip()
        template = directory / str(entry.get("template") or f"{slug}.html.j2")
        if not slug or slug in seen or not template.is_file():
            continue
        seen.add(slug)
        found.append({
            "slug": slug,
            "name": str(entry.get("name") or slug),
            "description": str(entry.get("description") or ""),
            "template": template,
        })
    return found


def find(key: str, directory: Path | None = None) -> dict[str, Any] | None:
    """Look a layout up by slug, by display name, or by the number prefix."""
    wanted = key.strip().lower()
    items = discover(directory)
    for item in items:
        if wanted in (item["slug"].lower(), item["name"].lower()):
            return item
    for item in items:
        if item["slug"].lower().startswith(wanted + "-"):
            return item
    return None
