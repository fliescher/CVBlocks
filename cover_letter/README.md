# Cover letter

`cover_letter.yaml` in this directory is written by the desktop app through
`Edit → Edit cover letter…` (or the toolbar's **Cover letter** button). It is
personal data and is ignored by git, just like the files in `cv-data/`.

The letter uses the currently selected CV layout, theme, accent/highlight
colours, and font. The CV body is replaced with the letter text; the profile
header and page frame stay the same.

The storage format is deliberately small: one list item per paragraph, and each
paragraph contains one or more text runs.

```yaml
paragraphs:
  - runs:
      - text: "Dear Hiring Manager,"
  - runs:
      - text: "I am applying for the "
      - text: "Staff Platform Engineer"
        bold: true
      - text: " role."
  - runs:
      - text: "The parts I would bring to the team are "
      - text: "reliability"
        italic: true
      - text: " and clear communication."
```

`bold` and `italic` are optional booleans. `size` is an optional point size and
must be between 6 and 72. Empty paragraphs become blank lines in the rendered
letter.

Copy `_TEMPLATE.yaml` if you prefer to write the file by hand. The GUI writes
`cover_letter.yaml`; it never edits `_TEMPLATE.yaml`.
