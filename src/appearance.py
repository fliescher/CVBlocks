"""Optional look overrides applied on top of any layout. No Qt here.

A layout (see layouts.py) decides the structure and typography of the CV.
Accent and highlight colours come from `theme` in profile.yaml and reach every
layout through the Jinja `theme` variable. On top of that the GUI can override
three more things for any layout:

    text   body text colour
    desk   screen backdrop behind the page (screen only, never printed)
    font   CSS font-family stack, system fonts only

They are applied as a small <style> block injected into the rendered HTML, so
they work with every layout, including ones you add yourself.
"""

from __future__ import annotations

import json
import re
from typing import Any

KEYS = ("text", "desk", "font")
COLOR_KEYS = ("text", "desk")

LABELS = {"text": "Body text", "desk": "Backdrop", "font": "Font"}
HINTS = {
    "text": "Body text colour",
    "desk": "Screen backdrop behind the page (not printed)",
    "font": "Font family for the whole page",
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

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_FONT_FORBIDDEN = re.compile(r"[;{}<>\\\n\r]")


def is_color(value: Any) -> bool:
    return isinstance(value, str) and bool(_HEX.match(value))


def is_font(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not _FONT_FORBIDDEN.search(value)


def clean(overrides: dict[str, Any] | None) -> dict[str, str]:
    """Keep only valid overrides. Anything else is dropped, never repaired."""
    result: dict[str, str] = {}
    for key, value in (overrides or {}).items():
        if key in COLOR_KEYS and is_color(value):
            result[key] = value.lower()
        elif key == "font" and is_font(value):
            result[key] = value.strip()
    return result


def has_overrides(theme: dict[str, Any]) -> bool:
    return any(key in theme for key in KEYS)


def css_for(overrides: dict[str, Any]) -> str:
    values = clean(overrides)
    lines = []
    if "desk" in values:
        lines.append("@media screen{html,body{background:%s !important}}" % values["desk"])
    body = []
    if "text" in values:
        body.append("color:%s !important" % values["text"])
    if "font" in values:
        body.append("font-family:%s !important" % values["font"])
    if body:
        lines.append("body{%s}" % ";".join(body))
    return "\n".join(lines) + ("\n" if lines else "")


def inject(html: str, overrides: dict[str, Any]) -> str:
    css = css_for(overrides)
    if not css:
        return html
    block = f'<style id="cv-appearance">\n{css}</style>\n'
    match = re.search(r"</head\s*>", html, flags=re.IGNORECASE)
    if match:
        return html[: match.start()] + block + html[match.start():]
    return block + html


def dumps(overrides: dict[str, Any]) -> str:
    return json.dumps(clean(overrides))


def loads(text: str | None) -> dict[str, str]:
    try:
        raw = json.loads(text or "{}")
    except ValueError:
        return {}
    return clean(raw if isinstance(raw, dict) else {})
