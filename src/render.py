#!/usr/bin/env python3
"""Validate the YAML CV dataset and render it to a single HTML file.

Usage:
    python src/render.py                          # everything -> out/cv.html
    python src/render.py --check                  # validate only
    python src/render.py --manifest app.yaml      # filtered variant
    python src/render.py --out out/acme.html
"""

from __future__ import annotations

import argparse
import json
import re
import sys
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


def die(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def load_yaml(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except FileNotFoundError:
        die(f"{path}: file not found")
    except yaml.YAMLError as exc:
        die(f"{path}: invalid YAML\n{exc}")


def validate(document: Any, schema_path: Path, label: str) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(document),
        key=lambda err: list(err.absolute_path),
    )
    if not errors:
        return
    for err in errors:
        location = "/".join(str(part) for part in err.absolute_path) or "<root>"
        print(f"{label}: {location}: {err.message}", file=sys.stderr)
    raise SystemExit(1)


def load_dataset(root: Path) -> dict[str, Any]:
    schema_dir = root / "schema"
    required = [root / name for name in (PROFILE, SKILLS, EDUCATION, EXTRAS)] + [schema_dir]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        die("dataset is incomplete, missing: " + ", ".join(missing))

    dataset: dict[str, Any] = {}
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
            die(f"{path.name}: duplicate role id '{role_id}'")
        seen_roles.add(role_id)

        seen_achievements: set[str] = set()
        for achievement in role["achievements"]:
            achievement_id = achievement["id"]
            if achievement_id in seen_achievements:
                die(f"{path.name}: duplicate achievement id '{achievement_id}'")
            seen_achievements.add(achievement_id)

        roles.append(role)

    dataset["roles"] = roles
    return dataset


def format_month(value: str | None) -> str:
    if not value:
        return "Present"
    year, month = value.split("-")
    return f"{MONTHS[int(month) - 1]} {year}"


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


def role_meta(role: dict[str, Any]) -> str:
    parts = [f"{format_month(role.get('start'))} – {format_month(role.get('end'))}"]
    if role.get("location"):
        parts.append(role["location"])
    return " · ".join(parts)


def select_roles(roles: list[dict[str, Any]], manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    include = (manifest or {}).get("include", {})
    specs = include.get("roles") or []

    if not specs:
        ordered = sorted(
            roles,
            key=lambda role: (role.get("end") or "9999-99", role["start"]),
            reverse=True,
        )
        return deepcopy(ordered)

    by_id = {role["id"]: role for role in roles}
    selected: list[dict[str, Any]] = []

    for spec in specs:
        if isinstance(spec, str):
            role_id, achievement_ids = spec, []
        elif isinstance(spec, dict):
            role_id = spec.get("id", "")
            achievement_ids = spec.get("achievements") or []
        else:
            die(f"manifest: each entry under include.roles must be an id or a mapping, got {spec!r}")

        if role_id not in by_id:
            die(f"manifest: unknown role id '{role_id}'")
        role = deepcopy(by_id[role_id])

        if achievement_ids:
            by_achievement = {item["id"]: item for item in role["achievements"]}
            unknown = [item for item in achievement_ids if item not in by_achievement]
            if unknown:
                die(f"manifest: unknown achievement id(s) for '{role_id}': {', '.join(unknown)}")
            role["achievements"] = [by_achievement[item] for item in achievement_ids]

        selected.append(role)

    return selected


def select_skills(skills: dict[str, Any], manifest: dict[str, Any] | None) -> dict[str, Any]:
    include = (manifest or {}).get("include", {})
    wanted = include.get("skills") or []
    if not wanted:
        return skills

    by_name = {category["name"]: category for category in skills["categories"]}
    unknown = [name for name in wanted if name not in by_name]
    if unknown:
        die(f"manifest: unknown skill categor(y/ies): {', '.join(unknown)}")
    return {"categories": [by_name[name] for name in wanted]}


def extras_items(extras: dict[str, Any], manifest: dict[str, Any] | None) -> list[str]:
    include = (manifest or {}).get("include", {})
    if include.get("extras") is False:
        return []
    items: list[str] = []
    for key in ("certifications", "open_source", "talks", "languages"):
        items.extend(extras.get(key, []))
    return items


def build_context(dataset: dict[str, Any], manifest: dict[str, Any] | None) -> dict[str, Any]:
    profile = dataset["profile"]
    include = (manifest or {}).get("include", {})

    education = dataset["education"]
    if include.get("education") is False:
        education = {"entries": []}

    roles = select_roles(dataset["roles"], manifest)
    for role in roles:
        role["meta"] = role_meta(role)

    return {
        "profile": profile,
        "contact": contact_items(profile),
        "skills": select_skills(dataset["skills"], manifest),
        "roles": roles,
        "education": education,
        "extras_items": extras_items(dataset["extras"], manifest),
    }


def render(context: dict[str, Any], template_path: Path) -> str:
    if not template_path.exists():
        die(f"{template_path}: template not found")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the YAML CV dataset to HTML.")
    parser.add_argument("--data", type=Path, default=Path("cv-data"), help="dataset directory")
    parser.add_argument("--manifest", type=Path, help="selection manifest for a tailored CV")
    parser.add_argument("--template", type=Path, default=Path("templates/cv.html.j2"))
    parser.add_argument("--out", type=Path, default=Path("out/cv.html"))
    parser.add_argument("--check", action="store_true", help="validate the dataset and exit")
    args = parser.parse_args(argv)

    dataset = load_dataset(args.data)

    manifest = None
    if args.manifest:
        manifest = load_yaml(args.manifest)
        if manifest is None:
            manifest = {}

    achievements = sum(len(role["achievements"]) for role in dataset["roles"])
    if args.check:
        print(f"OK: {len(dataset['roles'])} role(s), {achievements} achievement(s)")
        return 0

    context = build_context(dataset, manifest)
    html = render(context, args.template)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")

    rendered_roles = len(context["roles"])
    rendered_achievements = sum(len(role["achievements"]) for role in context["roles"])
    print(
        f"wrote {args.out} "
        f"({rendered_roles} role(s), {rendered_achievements} achievement(s))"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
