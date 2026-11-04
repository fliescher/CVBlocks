# Bundled example layouts

Ten complete CV layouts. They all use the same fictional dataset, so you can
compare the markup and CSS without maintaining ten copies of the content.
Jordan Avery is not a real person; every employer, metric, and link is made up.

Each directory contains:

```
examples/
  data/                       shared fictional dataset (profile, roles, all categories, schemas)
  01-classic/
    example.yaml              display name and description for the GUI
    template.html.j2          standalone Jinja2 template
  02-sidebar/
  ...
  10-elegant/
```

| Directory | Name | Layout and style |
| --- | --- | --- |
| `01-classic` | Classic | Traditional single column, serif type, ruled headings, centred header. |
| `02-sidebar` | Sidebar | Light left rail for contact, skills, and education; experience in the main column. |
| `03-timeline` | Timeline | Vertical timeline, dates in the margin, dot markers for each role. |
| `04-compact` | Compact | Dense two-column one-pager with small type and narrow margins. |
| `05-editorial` | Editorial | Large display type, pull-quote summary, serif body, numbered sections. |
| `06-minimal` | Minimal | Airy monochrome layout with hairline rules and generous whitespace. |
| `07-header-band` | Header band | Full-width colour band, two-column body, pill-shaped skill groups. |
| `08-cards` | Cards | Each role in a bordered card, with skill chips and a light grey canvas. |
| `09-technical` | Technical | Monospace labels, key/value skills, terminal-inspired section markers. |
| `10-elegant` | Elegant | Centred serif name, narrow right rail, small caps, and dotted leaders. |

## Load an example in the GUI

1. Start the app from the repository root:
   `.venv/bin/python src/gui.py`
2. Choose `File → Load example…` and pick a layout.
3. Select roles and their items, plus category items in the Experience and
   Library tabs, then use `Export HTML…` to try the layout.

Example mode is read-only: the app loads `examples/data` so you can explore
the selection, the Library checkboxes, layouts, theme presets, and colours, but
`Save`, `Save selection as…`, `Add item`, `Mark important`, and the editing
actions are disabled. Use `File → Open dataset…` to return to your own dataset
and the default template.

The example templates also support the cover-letter preview: switch the preview
to `Cover letter` to see the same layout with only the letter body. Editing the
letter is disabled while an example is loaded.

## Render an example from the command line

```sh
.venv/bin/python src/render.py \
  --data examples/data \
  --template examples/02-sidebar/template.html.j2 \
  --out out/examples/sidebar.html
```

Swap the template path for any other example. To validate the shared dataset:

```sh
.venv/bin/python src/render.py --data examples/data --check
```

The `examples/data/schema/` files are copies of `cv-data/schema/`; the dataset
is self-contained so the examples work when the repository is copied without
the rest of `cv-data`.
