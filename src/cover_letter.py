"""Cover-letter storage and rendering. No Qt here.

A cover letter is deliberately small: a list of paragraphs, and each paragraph
is a list of styled text runs. The GUI's QTextEdit turns its document into this
structure, so the stored file stays readable and independent of Qt's HTML
dialect.

Rendering reuses the selected CV layout. Every bundled layout includes the
cover-letter body in place of its CV sections, while keeping its own header,
page frame, colours, and typography.
"""

from __future__ import annotations

import re
from html import escape
from pathlib import Path
from typing import Any

import cvlib
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COVER_LETTER_DIR = PROJECT_ROOT / "cover_letter"
DEFAULT_PATH = COVER_LETTER_DIR / "cover_letter.yaml"

DEFAULT_SIZE = 10.5
MIN_SIZE = 6.0
MAX_SIZE = 72.0

_CSS = """
.cover-letter { margin-top: 0; }
.cover-letter p {
  margin: 0 0 0.65em;
  white-space: pre-wrap;
}
.cover-letter p:last-child { margin-bottom: 0; }
.cover-letter strong { font-weight: 700; }
.cover-letter em { font-style: italic; }
"""


class CoverLetterError(Exception):
    """A problem the user can fix by editing the cover-letter file."""


def empty_document() -> dict[str, Any]:
    return {"paragraphs": []}


def normalize(document: Any) -> dict[str, Any]:
    """Return a clean paragraph/run document, rejecting malformed values."""
    if document is None:
        return empty_document()

    if isinstance(document, dict):
        raw_paragraphs = document.get("paragraphs", [])
    elif isinstance(document, list):
        raw_paragraphs = document
    else:
        raise CoverLetterError("cover letter must contain a paragraphs list")

    if raw_paragraphs is None:
        raw_paragraphs = []
    if not isinstance(raw_paragraphs, list):
        raise CoverLetterError("cover letter paragraphs must be a list")

    paragraphs: list[dict[str, Any]] = []
    for block in raw_paragraphs:
        if isinstance(block, str):
            raw_runs: Any = [block]
        elif isinstance(block, list):
            raw_runs = block
        elif isinstance(block, dict):
            raw_runs = block.get("runs", [])
        else:
            raise CoverLetterError("each cover-letter paragraph must be a list or mapping")
        if raw_runs is None:
            raw_runs = []
        if not isinstance(raw_runs, list):
            raise CoverLetterError("cover-letter paragraph runs must be a list")

        runs: list[dict[str, Any]] = []
        for raw_run in raw_runs:
            if isinstance(raw_run, str):
                raw_run = {"text": raw_run}
            if not isinstance(raw_run, dict):
                raise CoverLetterError("each cover-letter run must be a mapping")

            text = raw_run.get("text", "")
            if text is None:
                text = ""
            if not isinstance(text, str):
                text = str(text)
            if not text:
                continue

            run: dict[str, Any] = {"text": text}
            if bool(raw_run.get("bold")):
                run["bold"] = True
            if bool(raw_run.get("italic")):
                run["italic"] = True
            if raw_run.get("size") is not None:
                try:
                    size = float(raw_run["size"])
                except (TypeError, ValueError) as exc:
                    raise CoverLetterError(f"invalid font size: {raw_run['size']!r}") from exc
                if not MIN_SIZE <= size <= MAX_SIZE:
                    raise CoverLetterError(
                        f"font size must be between {MIN_SIZE:g} and {MAX_SIZE:g} pt"
                    )
                run["size"] = round(size, 1)
            runs.append(run)

        paragraphs.append({"runs": runs})

    # A trailing empty paragraph is just an artifact of QTextEdit. Keep empty
    # paragraphs between text because the writer may have used them as spacing.
    while paragraphs and not paragraphs[-1]["runs"]:
        paragraphs.pop()
    return {"paragraphs": paragraphs}


def load(path: Path | None = None) -> dict[str, Any]:
    path = Path(path) if path is not None else DEFAULT_PATH
    if not path.exists():
        return empty_document()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CoverLetterError(f"{path}: invalid cover letter\n{exc}") from exc
    try:
        return normalize(raw)
    except CoverLetterError as exc:
        raise CoverLetterError(f"{path}: {exc}") from exc


def save(path: Path | None, document: dict[str, Any]) -> dict[str, Any]:
    path = Path(path) if path is not None else DEFAULT_PATH
    clean = normalize(document)
    try:
        cvlib.write_document(path, clean)
    except OSError as exc:
        raise CoverLetterError(f"{path}: could not save cover letter\n{exc}") from exc
    return clean


def supports_template(template_path: Path) -> bool:
    """True when a template can replace its CV sections with a cover letter."""
    try:
        return "cover_letter_html" in Path(template_path).read_text(encoding="utf-8")
    except OSError:
        return False


def document_html(document: dict[str, Any]) -> str:
    """Build the trusted HTML fragment inserted by the layouts."""
    parts = ['<article class="cover-letter">']
    for block in document.get("paragraphs", []):
        runs = block.get("runs", [])
        if not runs:
            parts.append("<p><br></p>")
            continue
        parts.append("<p>")
        for run in runs:
            text = escape(str(run.get("text", "")), quote=False)
            size = run.get("size")
            if size:
                text = f'<span style="font-size: {size:g}pt">{text}</span>'
            if run.get("italic"):
                text = f"<em>{text}</em>"
            if run.get("bold"):
                text = f"<strong>{text}</strong>"
            parts.append(text)
        parts.append("</p>")
    parts.append("</article>")
    return "".join(parts)


def _inject_css(html: str) -> str:
    block = f'<style id="cover-letter-style">\n{_CSS}</style>\n'
    match = re.search(r"</head\s*>", html, flags=re.IGNORECASE)
    if match:
        return html[: match.start()] + block + html[match.start():]
    return block + html


def render(
    dataset: dict[str, Any],
    document: dict[str, Any],
    template_path: Path | None = None,
    overrides: dict[str, str] | None = None,
) -> str:
    """Render a cover letter with the chosen CV layout.

    Layouts that do not yet know about cover letters (for example a custom
    dataset template) fall back to the default template instead of silently
    showing CV sections on the letter.
    """
    clean = normalize(document)
    template = Path(template_path) if template_path is not None else cvlib.DEFAULT_TEMPLATE
    if not supports_template(template):
        template = cvlib.DEFAULT_TEMPLATE

    context = cvlib.build_context(dataset, None, overrides)
    context["cover_letter"] = clean
    context["cover_letter_html"] = document_html(clean)
    html = cvlib.render_html(context, template)
    return _inject_css(html)
