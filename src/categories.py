"""Content categories shared by the loader, renderer, CLI, and GUI.

The dataset has one directory per category. Every item lives in its own YAML
file, which keeps diffs small and lets the GUI add, edit, and delete a single
entry without rewriting a list. Roles are special: they already have their own
directory and a richer schema, including nested achievement items.

This module is pure Python and has no Qt imports, so the GUI and the command
line enforce the same rules.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

CATEGORY_ORDER = (
    "core_skills",
    "education",
    "certifications",
    "open_source",
    "hobbies",
    "languages",
    "projects",
)


def _field(
    key: str,
    label: str,
    *,
    required: bool = False,
    multiline: bool = False,
    slug: bool = False,
    choices: tuple[str, ...] = (),
    placeholder: str = "",
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "required": required,
        "multiline": multiline,
        "slug": slug,
        "choices": choices,
        "placeholder": placeholder,
    }


SPECS: dict[str, dict[str, Any]] = {
    "core_skills": {
        "label": "Core skills",
        "directory": "core-skills",
        "schema": "core_skill.schema.json",
        "description": "Individual skills, grouped into rows such as Languages or Platform.",
        "fields": (
            _field("id", "ID", required=True, slug=True, placeholder="go"),
            _field("group", "Group", required=True, placeholder="Languages"),
            _field("text", "Skill", required=True, placeholder="Go"),
        ),
    },
    "education": {
        "label": "Education",
        "directory": "education",
        "schema": "education.schema.json",
        "description": "Degrees and formal education, one entry per file.",
        "fields": (
            _field("id", "ID", required=True, slug=True, placeholder="bsc-computer-science"),
            _field("degree", "Degree", required=True, placeholder="BSc Computer Science"),
            _field("institution", "Institution", required=True, placeholder="Utrecht University"),
            _field("year", "Year", placeholder="2012"),
            _field("location", "Location", placeholder="Utrecht, Netherlands"),
        ),
    },
    "certifications": {
        "label": "Certifications & trainings",
        "directory": "certifications",
        "schema": "certification.schema.json",
        "description": "Certifications, courses, and other completed training.",
        "fields": (
            _field("id", "ID", required=True, slug=True, placeholder="cka"),
            _field("title", "Title", required=True, placeholder="Certified Kubernetes Administrator"),
            _field("issuer", "Issuer", placeholder="CNCF"),
            _field("year", "Year", placeholder="2023"),
            _field(
                "kind",
                "Kind",
                choices=("certification", "training"),
                placeholder="certification",
            ),
            _field("url", "URL", placeholder="https://example.com/credential"),
        ),
    },
    "open_source": {
        "label": "Open source",
        "directory": "open-source",
        "schema": "open_source.schema.json",
        "description": "Projects you maintain or contribute to.",
        "fields": (
            _field("id", "ID", required=True, slug=True, placeholder="pgqueue"),
            _field("name", "Project", required=True, placeholder="pgqueue"),
            _field("role", "Role", placeholder="Maintainer"),
            _field("url", "URL", placeholder="https://github.com/example/pgqueue"),
            _field("text", "Description", multiline=True, placeholder="Postgres job queue; 2.1k stars"),
        ),
    },
    "hobbies": {
        "label": "Hobbies",
        "directory": "hobbies",
        "schema": "hobby.schema.json",
        "description": "Personal interests and activities, one per file.",
        "fields": (
            _field("id", "ID", required=True, slug=True, placeholder="cycling"),
            _field("name", "Hobby", required=True, placeholder="Cycling"),
            _field("text", "Description", multiline=True, placeholder="Weekend rides, 4,000 km a year"),
        ),
    },
    "languages": {
        "label": "Languages",
        "directory": "languages",
        "schema": "language.schema.json",
        "description": "Spoken and written languages with an optional level.",
        "fields": (
            _field("id", "ID", required=True, slug=True, placeholder="english"),
            _field("language", "Language", required=True, placeholder="English"),
            _field("level", "Level", placeholder="C2"),
        ),
    },
    "projects": {
        "label": "Selected projects",
        "directory": "projects",
        "schema": "project.schema.json",
        "description": "Projects worth calling out separately from employment.",
        "fields": (
            _field("id", "ID", required=True, slug=True, placeholder="billing-rewrite"),
            _field("name", "Project", required=True, placeholder="Billing rewrite"),
            _field("role", "Role", placeholder="Technical lead"),
            _field("year", "Year", placeholder="2025"),
            _field("url", "URL", placeholder="https://example.com/project"),
            _field("text", "Description", multiline=True, placeholder="Replaced a batch billing job with an event-driven service."),
        ),
    },
}

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def spec(category: str) -> dict[str, Any]:
    try:
        return SPECS[category]
    except KeyError as exc:
        raise ValueError(f"unknown category '{category}'") from exc


def fields(category: str) -> tuple[dict[str, Any], ...]:
    return tuple(spec(category)["fields"])


def new_item(category: str) -> dict[str, str]:
    item: dict[str, str] = {}
    for field in fields(category):
        choices = field["choices"]
        item[field["key"]] = choices[0] if choices else ""
    return item


def item_mapping(category: str, item: dict[str, Any]) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for field in fields(category):
        value = item.get(field["key"], "")
        mapping[field["key"]] = str(value).strip() if isinstance(value, str) else value
    return mapping


def item_path(root: Path, category: str, item: dict[str, Any]) -> Path:
    slug = str(item.get("id") or "").strip()
    if not slug:
        slug = slugify(str(item.get("text") or item.get("title") or item.get("name") or "item"))
    return root / spec(category)["directory"] / f"{slug}.yaml"


def item_title(category: str, item: dict[str, Any]) -> str:
    if category == "core_skills":
        return str(item.get("text") or item.get("group") or item.get("id") or "")
    if category == "education":
        return str(item.get("degree") or item.get("institution") or item.get("id") or "")
    if category in ("certifications", "open_source", "projects"):
        return str(item.get("title") or item.get("name") or item.get("id") or "")
    if category in ("hobbies", "languages"):
        return str(item.get("name") or item.get("language") or item.get("id") or "")
    return str(item.get("id") or "")


def item_detail(category: str, item: dict[str, Any]) -> str:
    if category == "core_skills":
        return str(item.get("group") or "")
    if category == "education":
        parts = [str(item.get("institution") or ""), str(item.get("year") or "")]
        if item.get("location"):
            parts.append(str(item["location"]))
        return " · ".join(part for part in parts if part)
    if category == "certifications":
        parts = [str(item.get("issuer") or ""), str(item.get("year") or "")]
        return " · ".join(part for part in parts if part)
    if category == "open_source":
        return str(item.get("role") or item.get("url") or "")
    if category == "hobbies":
        return str(item.get("text") or "")
    if category == "languages":
        return str(item.get("level") or "")
    if category == "projects":
        parts = [str(item.get("role") or ""), str(item.get("year") or "")]
        return " · ".join(part for part in parts if part)
    return ""


def extra_text(category: str, item: dict[str, Any]) -> str:
    """One-line text for the compact `extras_*` template lists."""
    if category == "certifications":
        title = str(item.get("title") or item.get("id") or "")
        issuer = str(item.get("issuer") or "")
        year = str(item.get("year") or "")
        detail = " — ".join(part for part in (title, issuer) if part)
        return f"{detail} ({year})" if year else detail
    if category == "open_source":
        name = str(item.get("name") or item.get("url") or item.get("id") or "")
        detail = str(item.get("text") or item.get("role") or "")
        return f"{name} — {detail}" if detail else name
    if category == "hobbies":
        name = str(item.get("name") or item.get("id") or "")
        detail = str(item.get("text") or "")
        return f"{name} — {detail}" if detail else name
    if category == "languages":
        language = str(item.get("language") or item.get("id") or "")
        level = str(item.get("level") or "")
        return f"{language} ({level})" if level else language
    if category == "projects":
        name = str(item.get("name") or item.get("id") or "")
        detail = str(item.get("text") or item.get("role") or "")
        return f"{name} — {detail}" if detail else name
    return item_title(category, item)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def validate_item(category: str, item: dict[str, Any]) -> str | None:
    """Return a human-readable problem, or None when the item can be saved."""
    for field in fields(category):
        value = str(item.get(field["key"], "")).strip()
        if field["required"] and not value:
            return f"{field['label']} is required."
        if field["slug"] and value and not SLUG_PATTERN.fullmatch(value):
            return f"{field['label']} must be a lowercase slug such as 'example-id'."
        if field["choices"] and value and value not in field["choices"]:
            return f"{field['label']} must be one of: {', '.join(field['choices'])}."
    return None
