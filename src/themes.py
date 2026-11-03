"""Visual styles (colour + font presets) for CV Selector.

Pure Python, no Qt. Not to be confused with the free-form achievement tags
("themes" in the YAML data): these are *styles* that change how the CV looks.

A style has five keys:

    accent     headings, rules, links          (template variable theme.accent)
    highlight  bullets marked important        (template variable theme.highlight)
    text       body text colour
    desk       screen backdrop behind the page (screen only, never printed)
    font       CSS font-family stack, system fonts only

`accent` and `highlight` reach every template through the Jinja `theme`
variable. `text`, `desk` and `font` are applied by a small <style> block that
is injected into the rendered HTML, so they work with any template.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

STYLE_KEYS = ("accent", "highlight", "text", "desk", "font")
COLOR_KEYS = ("accent", "highlight", "text", "desk")

COLOR_LABELS = {
    "accent": "Accent",
    "highlight": "Highlight",
    "text": "Body text",
    "desk": "Backdrop",
}

COLOR_HINTS = {
    "accent": "Headings, rules, and links",
    "highlight": "Bullets marked as important",
    "text": "Body text colour",
    "desk": "Screen backdrop behind the page (not printed)",
}

SANS = "'Helvetica Neue', Helvetica, Arial, sans-serif"
HUMANIST = "'Segoe UI', Calibri, 'Gill Sans', 'Trebuchet MS', sans-serif"
SERIF = "Georgia, 'Times New Roman', Times, serif"
BOOK = "'Palatino Linotype', Palatino, 'Book Antiqua', Georgia, serif"
MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace"

FONT_CHOICES: list[tuple[str, str]] = [
    ("Sans (Helvetica / Arial)", SANS),
    ("Humanist sans (Segoe UI / Calibri)", HUMANIST),
    ("Serif (Georgia)", SERIF),
    ("Book serif (Palatino)", BOOK),
    ("Monospace", MONO),
]


def _style(sid: str, name: str, accent: str, highlight: str, text: str, desk: str, font: str) -> dict[str, str]:
    return {
        "id": sid, "name": name, "accent": accent, "highlight": highlight,
        "text": text, "desk": desk, "font": font,
    }


BUILTIN_STYLES: list[dict[str, str]] = [
    _style("teal",       "Teal (default)",   "#1f4e5f", "#b45309", "#1f2933", "#e1e6e6", SANS),
    _style("ocean",      "Ocean Blue",       "#1d4ed8", "#ea580c", "#1e293b", "#e2e8f0", SANS),
    _style("navy",       "Navy Classic",     "#1e3a5f", "#b91c1c", "#1f2937", "#dfe5ec", SERIF),
    _style("forest",     "Forest",           "#166534", "#b45309", "#1c2b22", "#e0e8e2", HUMANIST),
    _style("burgundy",   "Burgundy",         "#7f1d1d", "#0f766e", "#2b1f1f", "#ece1e1", BOOK),
    _style("purple",     "Royal Purple",     "#5b21b6", "#d97706", "#251f33", "#e8e3f1", SANS),
    _style("slate",      "Slate",            "#334155", "#0891b2", "#1e293b", "#e2e5e9", HUMANIST),
    _style("charcoal",   "Charcoal & Amber", "#1f2937", "#ea580c", "#111827", "#e5e7eb", SANS),
    _style("crimson",    "Crimson",          "#b91c1c", "#1d4ed8", "#27272a", "#efe3e3", SANS),
    _style("coral",      "Teal & Coral",     "#0f766e", "#e11d48", "#1f2a2a", "#dcebea", HUMANIST),
    _style("sunset",     "Sunset",           "#c2410c", "#7c3aed", "#2a211c", "#f1e5dc", SANS),
    _style("rose",       "Rose",             "#be185d", "#0e7490", "#2d1f27", "#f1e2ea", HUMANIST),
    _style("olive",      "Olive",            "#4d5a1f", "#9a3412", "#262a1c", "#e6e8dc", BOOK),
    _style("indigo",     "Midnight Indigo",  "#312e81", "#be123c", "#1e1b3a", "#e0e0ef", SANS),
    _style("copper",     "Copper",           "#92400e", "#115e59", "#2b2118", "#efe4d8", SERIF),
    _style("graphite",   "Graphite",         "#111827", "#b91c1c", "#111827", "#e7e8ea", SANS),
    _style("sky",        "Sky",              "#0369a1", "#c026d3", "#1b2a36", "#dbeaf3", HUMANIST),
    _style("mint",       "Mint",             "#047857", "#be185d", "#17302a", "#dcefe8", SANS),
    _style("sand",       "Warm Sand",        "#78350f", "#1d4ed8", "#2a2118", "#eee6d8", SERIF),
    _style("terminal",   "Terminal",         "#166534", "#c2410c", "#14231a", "#dfe7e1", MONO),
]

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_FONT_FORBIDDEN = re.compile(r"[;{}<>\\\n\r]")


class StyleError(ValueError):
    pass


# --------------------------------------------------------------------------
# Lookup and validation
# --------------------------------------------------------------------------

def builtin_ids() -> list[str]:
    return [style["id"] for style in BUILTIN_STYLES]


def find_builtin(style_id: str) -> dict[str, str] | None:
    for style in BUILTIN_STYLES:
        if style["id"] == style_id or style["name"].lower() == style_id.lower():
            return dict(style)
    return None


def find_style(style_id: str, custom: dict[str, dict[str, str]] | None = None) -> dict[str, str] | None:
    if custom and style_id in custom:
        return {"id": style_id, **custom[style_id]}
    return find_builtin(style_id)


def is_color(value: Any) -> bool:
    return isinstance(value, str) and bool(_HEX.match(value))


def is_font(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not _FONT_FORBIDDEN.search(value)


def sanitize(style: dict[str, Any], base: dict[str, str] | None = None) -> dict[str, str]:
    """Return a clean style with all five keys; bad values fall back to base."""
    base = base or BUILTIN_STYLES[0]
    clean: dict[str, str] = {}
    for key in COLOR_KEYS:
        value = style.get(key)
        clean[key] = value.lower() if is_color(value) else base[key]
    font = style.get("font")
    clean["font"] = font.strip() if is_font(font) else base["font"]
    return clean


def resolve(
    style_id: str,
    overrides: dict[str, str] | None = None,
    custom: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    """Style by id, with unsaved colour tweaks applied on top."""
    base = find_style(style_id, custom) or BUILTIN_STYLES[0]
    merged = {key: base[key] for key in STYLE_KEYS}
    if overrides:
        merged.update({k: v for k, v in overrides.items() if k in STYLE_KEYS})
    return sanitize(merged, base)


# --------------------------------------------------------------------------
# HTML injection
# --------------------------------------------------------------------------

def css_for(style: dict[str, str]) -> str:
    clean = sanitize(style)
    return (
        "@media screen{html,body{background:%(desk)s !important}}\n"
        "body{color:%(text)s !important;font-family:%(font)s !important}\n"
    ) % clean


def inject(html: str, style: dict[str, Any]) -> str:
    """Add the override block to rendered HTML. Idempotent per render."""
    block = f'<style id="cv-style">\n{css_for(style)}</style>\n'
    match = re.search(r"</head\s*>", html, flags=re.IGNORECASE)
    if match:
        return html[: match.start()] + block + html[match.start():]
    return block + html


def has_style_keys(theme: dict[str, Any]) -> bool:
    return all(key in theme for key in ("text", "desk", "font"))


# --------------------------------------------------------------------------
# Custom style storage (JSON file chosen by the caller)
# --------------------------------------------------------------------------

def load_custom(path: Path) -> dict[str, dict[str, str]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, str]] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, dict) and isinstance(value.get("name"), str):
            style = sanitize(value)
            style["name"] = value["name"].strip() or key
            result[key] = style
    return result


def save_custom(path: Path, custom: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(custom, indent=2, ensure_ascii=False), encoding="utf-8")


def new_custom_id(name: str, existing: set[str]) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "custom"
    candidate = f"custom-{slug}"
    counter = 2
    while candidate in existing or find_builtin(candidate):
        candidate = f"custom-{slug}-{counter}"
        counter += 1
    return candidate
