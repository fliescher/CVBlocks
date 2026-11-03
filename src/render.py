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
import sys
from pathlib import Path

import cvlib


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the YAML CV dataset to HTML.")
    parser.add_argument("--data", type=Path, default=Path("cv-data"), help="dataset directory")
    parser.add_argument("--manifest", type=Path, help="selection manifest for a tailored CV")
    parser.add_argument("--template", type=Path, default=cvlib.DEFAULT_TEMPLATE)
    parser.add_argument("--out", type=Path, default=Path("out/cv.html"))
    parser.add_argument("--check", action="store_true", help="validate the dataset and exit")
    args = parser.parse_args(argv)

    try:
        dataset = cvlib.load_dataset(args.data)

        manifest = None
        if args.manifest:
            manifest = cvlib.load_yaml(args.manifest) or {}

        achievements = sum(len(role["achievements"]) for role in dataset["roles"])
        if args.check:
            print(f"OK: {len(dataset['roles'])} role(s), {achievements} achievement(s)")
            return 0

        html = cvlib.render_dataset(dataset, manifest, args.template)
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
