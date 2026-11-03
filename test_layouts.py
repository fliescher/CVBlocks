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
    "skills": {"categories": [{"name": "Languages", "items": ["Go", "Python"]},
                               {"name": "Platform", "items": ["Kubernetes"]}]},
    "education": {"entries": [{"degree": "BSc", "institution": "Utrecht", "year": 2012}]},
    "extras": {"certifications": ["CKA"], "open_source": ["pgqueue"], "talks": ["KubeCon"], "languages": ["English"]},
    "roles": [
        {"id": "a", "company": "Lumen", "title": "Staff Engineer", "start": "2022-04", "end": None,
         "location": "Rotterdam", "scope": "Scope text.",
         "achievements": [{"id": "x", "themes": [], "text": "Plain bullet."},
                          {"id": "y", "themes": [], "text": "Highlighted bullet.", "highlight": True}]},
        {"id": "b", "company": "Northwind", "title": "Backend Engineer", "start": "2018-08", "end": "2022-03",
         "location": "Berlin", "scope": "", "achievements": [{"id": "z", "themes": [], "text": "Another."}]},
    ],
}

for item in items:
    html = cvlib.render_dataset(dataset, None, item["template"])
    slug = item["slug"]
    assert "#123456" in html and "#654321" in html, f"{slug}: colours not applied"
    assert "Jordan Avery" in html and "Highlighted bullet." in html and "Lumen" in html, slug
    assert "is-highlight" in html, f"{slug}: highlight class missing"
    assert "cv-appearance" not in html, slug
    assert "{{" not in html and "{%" not in html, f"{slug}: unrendered Jinja"
print("all 20 layouts render with the profile colours")

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

# Two layouts must not collapse into the same markup.
bodies = {re.sub(r"\s+", " ", i["template"].read_text()) for i in items}
assert len(bodies) == 20
print("layouts are distinct")
