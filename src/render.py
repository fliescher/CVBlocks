#!/usr/bin/env python3
"""Validate the YAML CV dataset and render it to a single HTML file.

Usage:
    python src/render.py                          # everything -> out/cv.html
    python src/render.py --check                  # validate only
    python src/render.py --manifest app.yaml      # filtered variant
    python src/render.py --out out/acme.html
    python src/render.py --list-layouts           # show the bundled layouts
    python src/render.py --layout swiss           # slug, name, or number (13)
    python src/render.py --accent "#1d4ed8" --highlight "#ea580c"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import cvlib
import layouts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the YAML CV dataset to HTML.")
    parser.add_argument("--data", type=Path, default=Path("cv-data"), help="dataset directory")
    parser.add_argument("--manifest", type=Path, help="selection manifest for a tailored CV")
    parser.add_argument("--template", type=Path, default=cvlib.DEFAULT_TEMPLATE)
    parser.add_argument("--out", type=Path, default=Path("out/cv.html"))
    parser.add_argument("--check", action="store_true", help="validate the dataset and exit")
    parser.add_argument("--layout", help="bundled layout: slug, name, or number (see --list-layouts)")
    parser.add_argument("--list-layouts", action="store_true", help="list bundled layouts and exit")
    parser.add_argument("--accent", help="accent colour as #rrggbb, overrides profile.yaml")
    parser.add_argument("--highlight", help="highlight colour as #rrggbb, overrides profile.yaml")
    args = parser.parse_args(argv)

    if args.list_layouts:
        for item in layouts.discover():
            print(f"{item['slug']:<18} {item['name']:<14} {item['description']}")
        return 0

    template = args.template
    if args.layout:
        item = layouts.find(args.layout)
        if item is None:
            print(f"unknown layout '{args.layout}'; try --list-layouts", file=sys.stderr)
            return 2
        template = item["template"]

    colours = {"accent": args.accent, "highlight": args.highlight}
    for key, value in colours.items():
        if value is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            print(f"--{key} must look like #1f4e5f, got '{value}'", file=sys.stderr)
            return 2

    try:
        dataset = cvlib.load_dataset(args.data)

        manifest = None
        if args.manifest:
            manifest = cvlib.load_yaml(args.manifest) or {}

        chosen = {key: value for key, value in colours.items() if value}
        if chosen:
            dataset["profile"].setdefault("theme", {}).update(chosen)

        achievements = sum(len(role["achievements"]) for role in dataset["roles"])
        if args.check:
            print(f"OK: {len(dataset['roles'])} role(s), {achievements} achievement(s)")
            return 0

        html = cvlib.render_dataset(dataset, manifest, template)
    except cvlib.CVDatasetError as exc:
        print(exc, file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")

    context_roles = cvlib.select_roles(dataset["roles"], manifest)
    rendered_achievements = sum(len(role["achievements"]) for role in context_roles)
    print(
        f"wrote {args.out} "
        f"({len(context_roles)} role(s), {rendered_achievements} achievement(s))"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
