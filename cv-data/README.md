# cv-data

This folder is the source of truth for the CV. Every file here is plain YAML
and is validated against `schema/` on load.

See the top-level [`README.md`](../README.md) for the full field reference,
examples, and the render commands.

Quick reminders:

- One role per file in `roles/`; copy `roles/_TEMPLATE.yaml` to start.
- Every other category is also one item per file: `core-skills/`,
  `education/`, `certifications/`, `open-source/`, `hobbies/`, `languages/`,
  and `projects/`. Copy the `_TEMPLATE.yaml` in the folder you need.
- The GUI **Library** tab and the **Add item** action write these files for
  you; files starting with `_` are ignored by the loader.
- Quote dates (`"2021-03"`) and anything YAML might reinterpret (`"NO"`, `"1.10"`).
- IDs are unique within each category; achievement IDs are unique per role.
- `applications/<slug>/manifest.yaml` selects what goes into one CV variant.
