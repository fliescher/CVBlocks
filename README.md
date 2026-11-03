# CV Selector

A CV that lives in plain YAML files: one file per role, one manifest per job
application. Validate the dataset, pick the roles and bullets you want, render
a tailored HTML CV, print it to PDF.

No database, no lock-in. Every fact is a text file you can read, diff, and
edit by hand — and later through a GUI that writes the same files.

## Requirements

- Python 3.10 or newer
- No Node, Rust, or LaTeX toolchain

## Quick start

Linux / macOS:

```sh
cd ~/gitea_repos/CV_selector
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python src/render.py --check    # validate the dataset
.venv/bin/python src/render.py            # render everything to out/cv.html
```

Windows (PowerShell):

```powershell
cd $HOME\gitea_repos\CV_selector
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

.venv\Scripts\python src\render.py --check
.venv\Scripts\python src\render.py
```

The repository ships empty, so the first render is a blank page. Fill in
`cv-data/profile.yaml`, add a role, and run it again.

## Layout

```
cv-data/                       the dataset — source of truth
  profile.yaml                 name, contact, summary paragraphs
  skills.yaml                  grouped skill categories
  education.yaml               degrees
  extras.yaml                  certifications, open source, talks, languages
  roles/<year>-<company>.yaml  one file per role, achievements nested inside
  roles/_TEMPLATE.yaml         copy this; files starting with "_" are ignored
  schema/*.schema.json         JSON Schema per file, enforced on every load
  applications/<slug>/         manifest + generated output per application
  notes/                       free-form Markdown, never parsed
src/render.py                  loader, validator, HTML renderer
templates/cv.html.j2           single-column A4 template (Jinja2)
out/                           generated CVs (git-ignored)
```

## Dataset conventions

- **IDs are slugs.** Role IDs are unique across `roles/`; achievement IDs are
  unique within their role. Manifests reference these IDs.
- **Dates are quoted** `YYYY-MM`, and `null` means the current role.
- **One role per file** keeps diffs small and merge conflicts rare.
- **Bullets** read action → technology → measurable result.
- **Themes** are free-form tags (`performance`, `reliability`, `migration`,
  `mentoring`, `cost`, `security`). They exist so a job description can be
  matched against your achievements later.
- **Unknown fields are rejected.** If you add a field, add it to the matching
  schema file too.

## Examples

### A profile

`cv-data/profile.yaml`:

```yaml
name: "Alex Beispiel"
headline: "Senior Software Engineer"
location: "Berlin, Germany · Remote (EU)"
email: "alex@example.com"
phone: "+49 30 1234567"

links:
  - label: "github.com/abeispiel"
    url: "https://github.com/abeispiel"
  - label: "linkedin.com/in/abeispiel"
    url: "https://linkedin.com/in/abeispiel"

summary:
  - >
    Senior software engineer with 9 years building and operating payment
    systems at scale. Deep in Go, PostgreSQL, and Kubernetes, with a track
    record of turning unreliable legacy services into observable ones.
  - >
    Comfortable owning a problem from design doc through on-call, and
    mentoring engineers into their next level.
```

The second summary paragraph is optional; delete the whole `summary` list if
you prefer to write it per application.

### A role

`cv-data/roles/2021-acme-senior.yaml`:

```yaml
id: acme-senior
company: Acme Payments
title: Senior Software Engineer
start: "2021-03"
end: null                    # null = current role
location: Remote (EU)
scope: >
  B2B payments platform, 40k daily active users, 1.2k req/s peak. Owned
  the billing domain on a team of six engineers.

achievements:
  - id: checkout-latency
    themes: [performance, delivery]
    text: >
      Cut p95 checkout latency from 900 ms to 180 ms by replacing N+1
      queries with batched reads, lifting checkout conversion 2.1%.
    metrics:
      - { label: p95 latency, before: 900, after: 180, unit: ms }

  - id: on-call-reliability
    themes: [reliability]
    text: >
      Raised availability from 99.5% to 99.95% and cut pages 60% by
      introducing SLOs, runbooks, and alert tuning.
```

`metrics` is optional and currently informational — it keeps the numbers
structured so a future ranking step can use them.

### Skills, education, extras

```yaml
# cv-data/skills.yaml
categories:
  - name: Languages
    items: [Go, Python, TypeScript, SQL]
  - name: Reliability
    items: [SLOs, OpenTelemetry, Prometheus, incident command]
```

```yaml
# cv-data/education.yaml
entries:
  - degree: BSc Computer Science
    institution: Example University
    year: "2016"
```

```yaml
# cv-data/extras.yaml
certifications:
  - AWS Certified Solutions Architect – Associate (2024)
open_source:
  - Maintainer, example-queue (1.2k stars)
talks:
  - "Boring reliability: SLOs that engineers actually use — PyCon DE 2023"
languages:
  - English (C2)
  - German (B2)
```

### A selection manifest

Copy `cv-data/applications/_manifest.example.yaml` to
`cv-data/applications/2026-11-acme/manifest.yaml`:

```yaml
application:
  company: Acme Corp
  role_title: Senior Backend Engineer
  date: 2026-11-03
  job_description: ""        # paste the posting; it records why this variant exists

include:
  roles:
    - id: acme-senior
      achievements: [checkout-latency, on-call-reliability]
    - id: globex-engineer    # bare id = every achievement in that role
  skills: [Languages]        # category names, in the order you want them
  education: false           # drop the section entirely
  extras: true
```

Rules:

- An empty `roles`, `skills`, or `include` block means **include everything**.
- Roles render in the order you list them; without a manifest they sort
  newest-first by end date.
- Listing `achievements` selects and orders those bullets only.
- `education: false` / `extras: false` remove those sections.

## Commands

```sh
# validate only; prints counts, exits non-zero on any schema error
.venv/bin/python src/render.py --check

# full CV (all roles, all skills, education, extras)
.venv/bin/python src/render.py

# tailored CV from a manifest
.venv/bin/python src/render.py \
  --manifest cv-data/applications/2026-11-acme/manifest.yaml \
  --out out/acme.html
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--data` | `cv-data` | dataset directory |
| `--manifest` | none | selection manifest; omit for everything |
| `--template` | `templates/cv.html.j2` | Jinja2 template |
| `--out` | `out/cv.html` | output HTML file |
| `--check` | off | validate the dataset and exit |

## Workflow

**Add a role**

1. `cp cv-data/roles/_TEMPLATE.yaml cv-data/roles/2024-initech-engineer.yaml`
2. Fill in the fields and achievements. Keep IDs stable once a manifest uses them.
3. `.venv/bin/python src/render.py --check`
4. `.venv/bin/python src/render.py`

**Tailor for an application**

1. Create `cv-data/applications/2026-11-acme/manifest.yaml` from the example.
2. Paste the job description, list the roles and bullets that answer it.
3. Render to `out/acme.html`.
4. Keep the manifest and the generated HTML together so the variant can be
   reproduced or compared later.

**Export to PDF**

Open the generated HTML in a browser → `Ctrl/Cmd + P` → *Save as PDF*, A4,
margins **Default**, **Background graphics on**. The filename convention
`Firstname_Lastname_CV.pdf` still applies.

## Troubleshooting

- `invalid YAML`: check indentation (spaces, never tabs) and quote strings
  that YAML would reinterpret: `"NO"`, `"on"`, `"1.10"`, dates, phone numbers.
- `does not match '^[a-z0-9]+...'`: IDs must be lowercase slugs.
- `unknown role id` / `unknown achievement id`: the manifest references an ID
  that does not exist in `roles/`. IDs are case-sensitive.
- `unknown skill categor(y/ies)`: use the exact `name` from `skills.yaml`.
- Tinkering with a schema is fine — just keep it in sync with your files.

## Why files instead of a database

The dataset is meant to be reviewed in a pull request, grepped, and backed up
by copying a folder. At CV scale (hundreds of bullets) an in-memory list is
plenty; a database would add a binary blob that cannot be diffed.

If search ever gets slow, build a throwaway index at startup — never make it
the thing you edit.

## Roadmap

The planned GUI is PySide6 + SQLite-free: it reads and writes these YAML files
(using `ruamel.yaml` so comments and key order survive), shows a filterable
table of achievements by theme, and renders the current selection with the
same Jinja2 template. Windows and Linux builds via PyInstaller.
