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

import appearance
import categories
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from jsonschema import Draft202012Validator

MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

PROFILE = "profile.yaml"
PROFILE_EXAMPLE = "profile.example.yaml"

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


def _load_category(root: Path, category: str, schema_dir: Path) -> list[dict[str, Any]]:
    """Load one directory of one-item-per-file category entries."""
    spec = categories.SPECS[category]
    schema = schema_dir / spec["schema"]
    directory = root / spec["directory"]
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    for path in sorted(directory.glob("*.yaml")):
        if path.name.startswith(("_", ".")):
            continue
        item = load_yaml(path)
        if item is None:
            item = {}
        validate(item, schema, f"{spec['directory']}/{path.name}")

        item_id = item["id"]
        if item_id in seen:
            raise CVDatasetError(
                f"{spec['directory']}/{path.name}: duplicate id '{item_id}'"
            )
        seen.add(item_id)
        item["_file"] = path
        item["_category"] = category
        items.append(item)

    return items


def load_dataset(root: Path) -> dict[str, Any]:
    """Load and validate the whole dataset.

    Roles and every non-role category get a private `_file` key. The loader
    deliberately requires the category directories to exist, so a typo in a
    directory name is an error rather than a silently empty CV section.
    """
    schema_dir = root / "schema"
    category_dirs = [
        root / categories.SPECS[key]["directory"] for key in categories.CATEGORY_ORDER
    ]
    schemas = [schema_dir / "profile.schema.json", schema_dir / "role.schema.json"] + [
        schema_dir / categories.SPECS[key]["schema"] for key in categories.CATEGORY_ORDER
    ]
    # The personal profile is intentionally untracked. Fresh checkouts load the
    # tracked example until the GUI or the user creates profile.yaml.
    profile_path = root / PROFILE
    if not profile_path.exists():
        profile_path = root / PROFILE_EXAMPLE
    required = [profile_path, root / "roles", schema_dir] + category_dirs + schemas
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise CVDatasetError("dataset is incomplete, missing: " + ", ".join(missing))

    profile = load_yaml(profile_path)
    if profile is None:
        profile = {}
    validate(profile, schema_dir / "profile.schema.json", profile_path.name)

    dataset: dict[str, Any] = {"root": root, "profile": profile}

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
    for category in categories.CATEGORY_ORDER:
        dataset[category] = _load_category(root, category, schema_dir)
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


def _selected_items(
    items: list[dict[str, Any]],
    value: Any,
    label: str,
) -> list[dict[str, Any]]:
    """Apply one manifest include value to a category.

    Missing or `true` selects everything, `false` selects nothing, and a list
    selects item ids in the order written in the manifest. Unknown ids are a
    hard error so a typo never silently drops a section.
    """
    if value is None or value is True:
        return [deepcopy(item) for item in items]
    if value is False:
        return []
    if not isinstance(value, list):
        raise CVDatasetError(
            f"manifest: include.{label} must be true, false, or a list of ids"
        )
    if not value:
        return []

    by_id = {item["id"]: item for item in items}
    unknown = [item for item in value if item not in by_id]
    if unknown:
        raise CVDatasetError(
            f"manifest: unknown {label} id(s): {', '.join(str(item) for item in unknown)}"
        )
    return [deepcopy(by_id[item]) for item in value]


def _public_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in item.items() if not key.startswith("_")}


def select_core_skills(
    items: list[dict[str, Any]], manifest: dict[str, Any] | None
) -> dict[str, Any]:
    """Group selected skill files into the categories used by all templates."""
    include = _include(manifest)

    if "core_skills" in include:
        selected = _selected_items(items, include.get("core_skills"), "core_skills")
    elif "skills" in include:
        # Compatibility with manifests written before core skills became files.
        wanted = include.get("skills") or []
        if not wanted:
            selected = []
        else:
            available = {item.get("group") or "Core skills" for item in items}
            unknown = [name for name in wanted if name not in available]
            if unknown:
                raise CVDatasetError(
                    f"manifest: unknown skill categor(y/ies): {', '.join(unknown)}"
                )
            selected = [
                deepcopy(item)
                for item in items
                if (item.get("group") or "Core skills") in wanted
            ]
    else:
        selected = [deepcopy(item) for item in items]

    groups: dict[str, list[str]] = {}
    for item in selected:
        group = str(item.get("group") or "Core skills")
        groups.setdefault(group, []).append(str(item.get("text", "")))

    return {
        "categories": [
            {"name": name, "items": texts} for name, texts in groups.items()
        ]
    }


def select_education(
    items: list[dict[str, Any]], manifest: dict[str, Any] | None
) -> dict[str, Any]:
    include = _include(manifest)
    if "education" not in include:
        selected = [deepcopy(item) for item in items]
    else:
        selected = _selected_items(items, include.get("education"), "education")
    return {"entries": selected}


def _extra_selection(
    dataset: dict[str, Any],
    manifest: dict[str, Any] | None,
    category: str,
) -> list[dict[str, Any]]:
    include = _include(manifest)
    if include.get("extras") is False:
        return []
    if category not in include:
        return [deepcopy(item) for item in dataset.get(category, [])]
    return _selected_items(dataset.get(category, []), include.get(category), category)


def extras_sections(
    dataset: dict[str, Any], manifest: dict[str, Any] | None
) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    for category in categories.CATEGORY_ORDER:
        if category == "core_skills" or category == "education":
            continue
        sections[category] = [
            categories.extra_text(category, item)
            for item in _extra_selection(dataset, manifest, category)
        ]
    # Kept for old templates and old manifests. The new category set has no
    # talks folder, so this is normally empty.
    sections["talks"] = []
    return sections


def extras_items(
    dataset: dict[str, Any], manifest: dict[str, Any] | None
) -> list[str]:
    sections = extras_sections(dataset, manifest)
    items: list[str] = []
    for category in ("certifications", "open_source", "projects", "hobbies", "languages", "talks"):
        items.extend(sections.get(category, []))
    return items


def selected_projects(
    dataset: dict[str, Any], manifest: dict[str, Any] | None
) -> list[dict[str, Any]]:
    return [
        _public_item(item)
        for item in _extra_selection(dataset, manifest, "projects")
    ]


def build_context(
    dataset: dict[str, Any],
    manifest: dict[str, Any] | None,
    overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the template context.

    `overrides` are optional text/desk/font values from appearance.py. They are
    added to the Jinja `theme` variable and applied to the page after rendering.
    """
    profile = dataset["profile"]

    roles = select_roles(dataset["roles"], manifest)
    for role in roles:
        role["meta"] = role_meta(role)

    return {
        "profile": profile,
        "contact": contact_items(profile),
        "theme": {**theme_from(profile), **appearance.clean(overrides)},
        # Layouts use this to replace their CV sections with a cover letter.
        # None keeps every existing template on the normal CV path.
        "cover_letter": None,
        "skills": select_core_skills(dataset.get("core_skills", []), manifest),
        "roles": roles,
        "education": select_education(dataset.get("education", []), manifest),
        "extras": extras_sections(dataset, manifest),
        "extras_items": extras_items(dataset, manifest),
        "projects": selected_projects(dataset, manifest),
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
    html = template.render(**context)
    if appearance.has_overrides(context["theme"]):
        html = appearance.inject(html, context["theme"])
    return html


def render_dataset(
    dataset: dict[str, Any],
    manifest: dict[str, Any] | None = None,
    template_path: Path | None = None,
    overrides: dict[str, str] | None = None,
) -> str:
    return render_html(build_context(dataset, manifest, overrides), template_path)


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


def save_item(category: str, item: dict[str, Any], path: Path) -> None:
    """Save one non-role category item, stripping GUI-only private keys."""
    write_document(path, categories.item_mapping(category, item))


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
