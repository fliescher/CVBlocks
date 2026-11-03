# cv-data

This folder is the source of truth for the CV. Every file here is plain YAML
and is validated against `schema/` on load.

See the top-level [`README.md`](../README.md) for the full field reference,
examples, and the render commands.

Quick reminders:

- One role per file in `roles/`; copy `roles/_TEMPLATE.yaml` to start.
- Quote dates (`"2021-03"`) and anything YAML might reinterpret (`"NO"`, `"1.10"`).
- Role IDs are unique across the dataset; achievement IDs are unique per role.
- `applications/<slug>/manifest.yaml` selects what goes into one CV variant.
