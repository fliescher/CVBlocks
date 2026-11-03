"""Dataset loading, validation, selection, and HTML rendering for CV Selector.

Pure Python: no Qt imports live here, so the CLI and the GUI share the same
code paths and the same output.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jsonschema import Draft202012Validator

MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

PROFILE = "profile.yaml"
SKILLS = "skills.yaml"
EDUCATION = "education.yaml"
EXTRAS = "extras.yaml"

DEFAULT_THEME = {
    "accent": "#1f4e5f",
    "highlight": "#b45309",
}

DEFAULT_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "cv.html.j2"


class CVDatasetError(Exception):
    """A problem the user can fix by editing a file or a manifest."""


# --------------------------------------------------------------------------
# Loading and validation
# --------------------------------------------------------------------------

def load_yaml(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise CVDatasetError(f"{path}: file not found") from exc
    except yaml.YAMLError as exc:
        raise CVDatasetError(f"{path}: invalid YAML\n{exc}") from exc


def validate(document: Any, schema_path: Path, label: str) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(document),
        key=lambda err: list(err.absolute_path),
    )
    if not errors:
        return
    lines = []
    for err in errors:
        location = "/".join(str(part) for part in err.absolute_path) or "<root>"
        lines.append(f"{label}: {location}: {err.message}")
    raise CVDatasetError("\n".join(lines))


def load_dataset(root: Path) -> dict[str, Any]:
    """Load and validate the whole dataset. Roles get a private _file key."""
    schema_dir = root / "schema"
    required = [root / name for name in (PROFILE, SKILLS, EDUCATION, EXTRAS)] + [schema_dir]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise CVDatasetError("dataset is incomplete, missing: " + ", ".join(missing))

    dataset: dict[str, Any] = {"root": root}
    for filename in (PROFILE, SKILLS, EDUCATION, EXTRAS):
        document = load_yaml(root / filename)
        if document is None:
            document = {}
        validate(document, schema_dir / f"{filename[:-5]}.schema.json", filename)
        dataset[filename[:-5]] = document

    role_schema = schema_dir / "role.schema.json"
    roles: list[dict[str, Any]] = []
    seen_roles: set[str] = set()
    for path in sorted((root / "roles").glob("*.yaml")):
        if path.name.startswith(("_", ".")):
            continue
        role = load_yaml(path)
        if role is None:
            role = {}
        validate(role, role_schema, path.name)

        role_id = role["id"]
        if role_id in seen_roles:
            raise CVDatasetError(f"{path.name}: duplicate role id '{role_id}'")
        seen_roles.add(role_id)

        seen_achievements: set[str] = set()
        for achievement in role["achievements"]:
            achievement_id = achievement["id"]
            if achievement_id in seen_achievements:
                raise CVDatasetError(
                    f"{path.name}: duplicate achievement id '{achievement_id}'"
                )
            seen_achievements.add(achievement_id)

        role["_file"] = path
        roles.append(role)

    dataset["roles"] = roles
    return dataset


def theme_from(profile: dict[str, Any]) -> dict[str, str]:
    theme = dict(DEFAULT_THEME)
    theme.update(profile.get("theme") or {})
    return theme


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------

def format_month(value: str | None) -> str:
    if not value:
        return "Present"
    year, month = value.split("-")
    return f"{MONTHS[int(month) - 1]} {year}"


def role_meta(role: dict[str, Any]) -> str:
    parts = [f"{format_month(role.get('start'))} – {format_month(role.get('end'))}"]
    if role.get("location"):
        parts.append(role["location"])
    return " · ".join(parts)


def contact_items(profile: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if profile.get("location"):
        items.append({"text": profile["location"], "href": ""})
    if profile.get("email"):
        items.append({"text": profile["email"], "href": f"mailto:{profile['email']}"})
    if profile.get("phone"):
        dial = re.sub(r"[^0-9+]", "", profile["phone"])
        items.append({"text": profile["phone"], "href": f"tel:{dial}"})
    for link in profile.get("links", []):
        items.append({
            "text": link.get("label") or link.get("url", ""),
            "href": link.get("url", ""),
        })
    return items


def _include(manifest: dict[str, Any] | None) -> dict[str, Any]:
    return (manifest or {}).get("include") or {}


def select_roles(roles: list[dict[str, Any]], manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    include = _include(manifest)

    if "roles" not in include:
        ordered = sorted(
            roles,
            key=lambda role: (role.get("end") or "9999-99", role["start"]),
            reverse=True,
        )
        return [deepcopy(role) for role in ordered]

    specs = include.get("roles") or []

    by_id = {role["id"]: role for role in roles}
    selected: list[dict[str, Any]] = []

    for spec in specs:
        if isinstance(spec, str):
            role_id, achievement_ids = spec, []
        elif isinstance(spec, dict):
            role_id = spec.get("id", "")
            achievement_ids = spec.get("achievements") or []
        else:
            raise CVDatasetError(
                f"manifest: each entry under include.roles must be an id or a "
                f"mapping, got {spec!r}"
            )

        if role_id not in by_id:
            raise CVDatasetError(f"manifest: unknown role id '{role_id}'")
        role = deepcopy(by_id[role_id])

        if achievement_ids:
            by_achievement = {item["id"]: item for item in role["achievements"]}
            unknown = [item for item in achievement_ids if item not in by_achievement]
            if unknown:
                raise CVDatasetError(
                    f"manifest: unknown achievement id(s) for '{role_id}': "
                    + ", ".join(unknown)
                )
            role["achievements"] = [by_achievement[item] for item in achievement_ids]

        selected.append(role)

    return selected


def select_skills(skills: dict[str, Any], manifest: dict[str, Any] | None) -> dict[str, Any]:
    include = _include(manifest)
    if "skills" not in include:
        return skills

    wanted = include.get("skills") or []
    if not wanted:
        return {"categories": []}

    by_name = {category["name"]: category for category in skills["categories"]}
    unknown = [name for name in wanted if name not in by_name]
    if unknown:
        raise CVDatasetError(f"manifest: unknown skill categor(y/ies): {', '.join(unknown)}")
    return {"categories": [by_name[name] for name in wanted]}


def extras_items(extras: dict[str, Any], manifest: dict[str, Any] | None) -> list[str]:
    include = _include(manifest)
    if include.get("extras") is False:
        return []
    items: list[str] = []
    for key in ("certifications", "open_source", "talks", "languages"):
        items.extend(extras.get(key, []))
    return items


def build_context(dataset: dict[str, Any], manifest: dict[str, Any] | None) -> dict[str, Any]:
    profile = dataset["profile"]
    include = _include(manifest)

    education = dataset["education"]
    if include.get("education") is False:
        education = {"entries": []}

    roles = select_roles(dataset["roles"], manifest)
    for role in roles:
        role["meta"] = role_meta(role)

    return {
        "profile": profile,
        "contact": contact_items(profile),
        "theme": theme_from(profile),
        "skills": select_skills(dataset["skills"], manifest),
        "roles": roles,
        "education": education,
        "extras_items": extras_items(dataset["extras"], manifest),
    }


def render_html(context: dict[str, Any], template_path: Path | None = None) -> str:
    template_path = template_path or DEFAULT_TEMPLATE
    if not template_path.exists():
        raise CVDatasetError(f"{template_path}: template not found")
    environment = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.filters["month"] = format_month
    template = environment.get_template(template_path.name)
    return template.render(**context)


def render_dataset(
    dataset: dict[str, Any],
    manifest: dict[str, Any] | None = None,
    template_path: Path | None = None,
) -> str:
    return render_html(build_context(dataset, manifest), template_path)


# --------------------------------------------------------------------------
# Writing back (round-trip, so comments and key order survive)
# --------------------------------------------------------------------------

def _ruamel() -> Any:
    from ruamel.yaml import YAML

    engine = YAML()
    engine.preserve_quotes = True
    engine.indent(mapping=2, sequence=4, offset=2)
    return engine


def _merge(target: Any, source: Any) -> None:
    """Merge source into target in place, keeping comments where possible."""
    if not isinstance(target, dict) or not isinstance(source, dict):
        return
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge(target[key], value)
        else:
            target[key] = value
    for key in list(target.keys()):
        if key not in source:
            del target[key]


def write_document(path: Path, document: dict[str, Any]) -> None:
    engine = _ruamel()
    target: Any = None
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            target = engine.load(handle)
    if target is None:
        target = document
    else:
        _merge(target, document)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        engine.dump(target, handle)


def achievement_mapping(achievement: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": achievement.get("id", ""),
        "themes": list(achievement.get("themes") or []),
        "text": achievement.get("text", ""),
    }
    if achievement.get("metrics"):
        data["metrics"] = deepcopy(achievement["metrics"])
    if achievement.get("highlight"):
        data["highlight"] = True
    return data


def role_mapping(role: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": role.get("id", ""),
        "company": role.get("company", ""),
        "title": role.get("title", ""),
        "start": role.get("start", ""),
        "end": role.get("end"),
        "location": role.get("location", ""),
        "scope": role.get("scope", ""),
        "achievements": [achievement_mapping(a) for a in role.get("achievements", [])],
    }


def profile_mapping(profile: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": profile.get("name", ""),
        "headline": profile.get("headline", ""),
        "location": profile.get("location", ""),
        "email": profile.get("email", ""),
        "phone": profile.get("phone", ""),
        "links": [
            {"label": link.get("label", ""), "url": link.get("url", "")}
            for link in profile.get("links", [])
        ],
        "summary": list(profile.get("summary") or []),
    }
    theme = profile.get("theme")
    if theme:
        data["theme"] = {
            "accent": theme.get("accent", DEFAULT_THEME["accent"]),
            "highlight": theme.get("highlight", DEFAULT_THEME["highlight"]),
        }
    return data


def save_profile(profile: dict[str, Any], path: Path) -> None:
    write_document(path, profile_mapping(profile))


def save_role(role: dict[str, Any], path: Path) -> None:
    write_document(path, role_mapping(role))


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest, handle, sort_keys=False, allow_unicode=True)


# --------------------------------------------------------------------------
# Small helpers used by the GUI
# --------------------------------------------------------------------------

def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "role"


def new_achievement() -> dict[str, Any]:
    return {"id": "", "themes": [], "text": "", "highlight": False}


def new_role() -> dict[str, Any]:
    return {
        "id": "",
        "company": "",
        "title": "",
        "start": "",
        "end": None,
        "location": "",
        "scope": "",
        "achievements": [],
    }


def role_path(root: Path, role: dict[str, Any]) -> Path:
    prefix = role.get("start") or "undated"
    name = slugify(role.get("company") or role.get("id") or "role")
    return root / "roles" / f"{prefix}-{name}.yaml"
