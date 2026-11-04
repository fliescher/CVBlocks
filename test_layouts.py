"""Checks for the layout registry, the appearance overrides, and all 20 layouts.

Run from the repository root:  python test_layouts.py
Needs no Qt. jsonschema is only needed to load a real dataset, so it is stubbed
when missing.
"""
import pathlib
import re
import sys
import tempfile

try:
    import jsonschema  # noqa: F401
except ImportError:
    import types
    _stub = types.ModuleType("jsonschema")
    _stub.Draft202012Validator = object
    sys.modules["jsonschema"] = _stub

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
import appearance  # noqa: E402
import categories  # noqa: E402
import cvlib  # noqa: E402
import layouts  # noqa: E402

items = layouts.discover()
assert len(items) == 20, len(items)
assert len({i["slug"] for i in items}) == 20
assert len({i["name"] for i in items}) == 20
assert all(i["template"].is_file() and i["description"] for i in items)
assert layouts.find("13")["slug"] == "13-swiss"
assert layouts.find("Swiss")["slug"] == "13-swiss"
assert layouts.find("19-ledger")["name"] == "Ledger"
assert layouts.find("nope") is None and layouts.find("") is None
orphans = {p.name for p in (ROOT / "layouts").glob("*.html.j2")} - {i["template"].name for i in items}
assert not orphans, f"templates missing from index.yaml: {orphans}"
print("registry ok:", len(items), "layouts")

dataset = {
    "root": ROOT,
    "profile": {
        "name": "Jordan Avery", "headline": "Staff Platform Engineer",
        "location": "Rotterdam, NL", "email": "j@example.com", "phone": "+31 6 1234 5678",
        "links": [{"label": "github.com/j", "url": "https://github.com/j"}],
        "summary": ["First paragraph.", "Second paragraph."],
        "theme": {"accent": "#123456", "highlight": "#654321"},
    },
    "core_skills": [
        {"id": "go", "group": "Languages", "text": "Go"},
        {"id": "python", "group": "Languages", "text": "Python"},
        {"id": "kubernetes", "group": "Platform", "text": "Kubernetes"},
    ],
    "education": [
        {"id": "bsc", "degree": "BSc", "institution": "Utrecht", "year": "2012"},
    ],
    "certifications": [
        {"id": "cka", "title": "CKA", "issuer": "CNCF", "year": "2023", "kind": "certification"},
    ],
    "open_source": [
        {"id": "pgqueue", "name": "pgqueue", "role": "Maintainer", "text": "Queue", "url": ""},
    ],
    "hobbies": [
        {"id": "cycling", "name": "Cycling", "text": "Weekend rides"},
    ],
    "languages": [
        {"id": "english", "language": "English", "level": "C2"},
    ],
    "projects": [
        {"id": "billing", "name": "Billing rewrite", "role": "Lead", "year": "2025", "text": "Project text.", "url": ""},
    ],
    "roles": [
        {"id": "a", "company": "Lumen", "title": "Staff Engineer", "start": "2022-04", "end": None,
         "location": "Rotterdam", "scope": "Scope text.",
         "achievements": [{"id": "x", "themes": [], "text": "Plain item."},
                          {"id": "y", "themes": [], "text": "Highlighted item.", "highlight": True}]},
        {"id": "b", "company": "Northwind", "title": "Backend Engineer", "start": "2018-08", "end": "2022-03",
         "location": "Berlin", "scope": "", "achievements": [{"id": "z", "themes": [], "text": "Another."}]},
    ],
}

for item in items:
    html = cvlib.render_dataset(dataset, None, item["template"])
    slug = item["slug"]
    assert "#123456" in html and "#654321" in html, f"{slug}: colours not applied"
    assert "Jordan Avery" in html and "Highlighted item." in html and "Lumen" in html, slug
    assert "is-highlight" in html, f"{slug}: highlight class missing"
    assert "Cycling" in html and "Billing rewrite" in html, (
        f"{slug}: hobbies or selected projects missing"
    )
    assert "cv-appearance" not in html, slug
    assert "{{" not in html and "{%" not in html, f"{slug}: unrendered Jinja"
print("all 20 layouts render with the profile colours")

context = cvlib.build_context(dataset, None)
assert [category["name"] for category in context["skills"]["categories"]] == [
    "Languages", "Platform"
]
assert context["education"]["entries"][0]["degree"] == "BSc"
assert context["extras"]["certifications"] == ["CKA — CNCF (2023)"]
assert context["extras"]["hobbies"] == ["Cycling — Weekend rides"]
assert context["extras"]["languages"] == ["English (C2)"]
assert context["projects"][0]["name"] == "Billing rewrite"
assert "Billing rewrite" in cvlib.render_dataset(dataset)
print("category context ok")

filtered = {
    "include": {
        "core_skills": ["go"],
        "education": [],
        "certifications": [],
        "open_source": [],
        "hobbies": [],
        "languages": ["english"],
        "projects": ["billing"],
    }
}
filtered_context = cvlib.build_context(dataset, filtered)
assert filtered_context["skills"]["categories"] == [
    {"name": "Languages", "items": ["Go"]}
]
assert filtered_context["education"]["entries"] == []
assert filtered_context["extras"]["certifications"] == []
assert filtered_context["extras"]["open_source"] == []
assert filtered_context["extras"]["hobbies"] == []
assert filtered_context["extras"]["languages"] == ["English (C2)"]
assert [p["id"] for p in filtered_context["projects"]] == ["billing"]
print("category selection manifests ok")

item = categories.new_item("projects")
assert categories.validate_item("projects", item) is not None
item.update({"id": "demo", "name": "Demo project"})
assert categories.validate_item("projects", item) is None
assert categories.item_path(ROOT, "projects", item).name == "demo.yaml"
print("category item helpers ok")

look = {"text": "#101010", "desk": "#d0d0d0", "font": appearance.SERIF}
for item in items:
    html = cvlib.render_dataset(dataset, None, item["template"], look)
    assert html.index("cv-appearance") < html.lower().index("</head>"), item["slug"]
    assert "#101010" in html and "#d0d0d0" in html and "Georgia" in html
print("appearance overrides apply to every layout")

hostile = appearance.clean({"text": "red; }</style><script>", "font": "x;}</style>", "desk": "#ABCDEF", "junk": "1"})
assert hostile == {"desk": "#abcdef"}, hostile
assert appearance.css_for({}) == "" and appearance.inject("<html></html>", {}) == "<html></html>"
assert appearance.loads("not json") == {} and appearance.loads(appearance.dumps(look)) == look
print("appearance validation ok")

import cover_letter  # noqa: E402

letter = {
    "paragraphs": [
        {"runs": [{"text": "Dear Hiring Manager,"}]},
        {"runs": [
            {"text": "I build "},
            {"text": "reliable", "bold": True},
            {"text": " and "},
            {"text": "fast", "italic": True},
            {"text": " systems."},
            {"text": " Big", "size": 14},
        ]},
        {"runs": []},
    ]
}
for item in items:
    html = cover_letter.render(dataset, letter, item["template"])
    assert "cover-letter" in html, item["slug"]
    assert "Dear Hiring Manager," in html, item["slug"]
    assert "<strong>reliable</strong>" in html, item["slug"]
    assert "<em>fast</em>" in html, item["slug"]
    assert "font-size: 14pt" in html, item["slug"]
    assert "Jordan Avery" in html, item["slug"]
    assert "Lumen" not in html and "Kubernetes" not in html, (
        f"{item['slug']}: cover letter leaked CV sections"
    )
    assert "{{" not in html and "{%" not in html, f"{item['slug']}: unrendered Jinja"
print("cover letter renders with all 20 layouts")

default_letter = cover_letter.render(dataset, letter)
assert "cover-letter" in default_letter and "Lumen" not in default_letter
for example in sorted((ROOT / "examples").glob("*/template.html.j2")):
    assert cover_letter.supports_template(example), example
    html = cover_letter.render(dataset, letter, example)
    assert "cover-letter" in html and "Lumen" not in html, example
print("cover letter renders with the default and example templates")

with tempfile.TemporaryDirectory() as tmp:
    saved_path = pathlib.Path(tmp) / "cover_letter" / "cover_letter.yaml"
    saved = cover_letter.save(saved_path, letter)
    assert saved_path.is_file()
    assert cover_letter.load(saved_path) == saved
    assert saved["paragraphs"][1]["runs"][1]["bold"] is True
    assert saved["paragraphs"][1]["runs"][3]["italic"] is True
    assert saved["paragraphs"][1]["runs"][5]["size"] == 14
print("cover letter save/load round-trip ok")

# Two layouts must not collapse into the same markup.
bodies = {re.sub(r"\s+", " ", i["template"].read_text()) for i in items}
assert len(bodies) == 20
print("layouts are distinct")
