#!/usr/bin/env python3
"""CV Selector — a small desktop GUI over the YAML dataset.

PySide6 on Windows and Linux. The preview uses QtWebEngine when the system
provides it; otherwise the app still edits, saves, and exports, and offers
"Open preview in browser".

Run:
    .venv/bin/python src/gui.py
    .venv/bin/python src/gui.py --data path/to/cv-data
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

import appearance
import cvlib
import layouts

from PySide6.QtCore import QCoreApplication, QSettings, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

WEBENGINE_AVAILABLE = False
if os.environ.get("CV_NO_WEBENGINE") != "1":
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView

        WEBENGINE_AVAILABLE = True
    except Exception:
        QWebEngineView = None  # type: ignore[assignment]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_ROOT = PROJECT_ROOT / "examples"
EXAMPLES_DATA = EXAMPLES_ROOT / "data"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def swatch_icon(color: str) -> QIcon:
    pixmap = QPixmap(18, 18)
    pixmap.fill(QColor(color))
    return QIcon(pixmap)


def elide(text: str, limit: int = 120) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def populate_theme_combo(combo: QComboBox, roles: list[dict[str, Any]]) -> None:
    current = combo.currentText()
    combo.blockSignals(True)
    combo.clear()
    combo.addItem("All themes")
    themes = sorted({theme for role in roles for a in role["achievements"] for theme in a.get("themes", [])})
    combo.addItems(themes)
    index = combo.findText(current)
    combo.setCurrentIndex(max(index, 0))
    combo.blockSignals(False)


def discover_examples() -> list[dict[str, Any]]:
    """Return the bundled layouts, sorted by directory name."""
    examples: list[dict[str, Any]] = []
    if not EXAMPLES_ROOT.exists():
        return examples

    for meta_path in sorted(EXAMPLES_ROOT.glob("*/example.yaml")):
        try:
            meta = cvlib.load_yaml(meta_path) or {}
        except cvlib.CVDatasetError:
            continue
        if not isinstance(meta, dict):
            continue
        template = meta_path.parent / (meta.get("template") or "template.html.j2")
        if not template.exists():
            continue
        examples.append({
            "slug": meta_path.parent.name,
            "name": meta.get("name") or meta_path.parent.name.replace("-", " ").title(),
            "description": meta.get("description", ""),
            "template": template,
        })
    return examples


# --------------------------------------------------------------------------
# Dialogs
# --------------------------------------------------------------------------

class ProfileDialog(QDialog):
    def __init__(self, profile: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit profile")
        self.resize(620, 640)
        self.profile = deepcopy(profile)

        self.name = QLineEdit(self.profile.get("name", ""))
        self.headline = QLineEdit(self.profile.get("headline", ""))
        self.location = QLineEdit(self.profile.get("location", ""))
        self.email = QLineEdit(self.profile.get("email", ""))
        self.phone = QLineEdit(self.profile.get("phone", ""))

        self.links = QTableWidget(0, 2)
        self.links.setHorizontalHeaderLabels(["Label", "URL"])
        self.links.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.links.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.links.verticalHeader().setVisible(False)
        self.links.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for link in self.profile.get("links", []):
            self._add_link(link.get("label", ""), link.get("url", ""))

        add_link = QPushButton("Add link")
        remove_link = QPushButton("Remove link")
        add_link.clicked.connect(lambda: self._add_link("", ""))
        remove_link.clicked.connect(self._remove_link)
        link_buttons = QHBoxLayout()
        link_buttons.addWidget(add_link)
        link_buttons.addWidget(remove_link)
        link_buttons.addStretch(1)

        self.summary = QPlainTextEdit("\n\n".join(self.profile.get("summary", [])))
        self.summary.setPlaceholderText("One paragraph per block, separated by a blank line.")

        form = QFormLayout()
        form.addRow("Name", self.name)
        form.addRow("Headline", self.headline)
        form.addRow("Location", self.location)
        form.addRow("Email", self.email)
        form.addRow("Phone", self.phone)

        links_box = QGroupBox("Links")
        links_layout = QVBoxLayout(links_box)
        links_layout.addWidget(self.links)
        links_layout.addLayout(link_buttons)

        summary_box = QGroupBox("Summary")
        summary_layout = QVBoxLayout(summary_box)
        summary_layout.addWidget(self.summary)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(links_box, 1)
        layout.addWidget(summary_box, 1)
        layout.addWidget(buttons)

    def _add_link(self, label: str, url: str) -> None:
        row = self.links.rowCount()
        self.links.insertRow(row)
        self.links.setItem(row, 0, QTableWidgetItem(label))
        self.links.setItem(row, 1, QTableWidgetItem(url))

    def _remove_link(self) -> None:
        rows = sorted({index.row() for index in self.links.selectedIndexes()}, reverse=True)
        for row in rows:
            self.links.removeRow(row)

    def result_profile(self) -> dict[str, Any]:
        links = []
        for row in range(self.links.rowCount()):
            label = self.links.item(row, 0)
            url = self.links.item(row, 1)
            label_text = label.text().strip() if label else ""
            url_text = url.text().strip() if url else ""
            if label_text or url_text:
                links.append({"label": label_text or url_text, "url": url_text})

        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", self.summary.toPlainText()) if part.strip()]

        profile = deepcopy(self.profile)
        profile.update({
            "name": self.name.text().strip(),
            "headline": self.headline.text().strip(),
            "location": self.location.text().strip(),
            "email": self.email.text().strip(),
            "phone": self.phone.text().strip(),
            "links": links,
            "summary": paragraphs,
        })
        return profile


class RoleDialog(QDialog):
    def __init__(self, role: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Role")
        self.resize(900, 680)
        self.role = deepcopy(role)
        self.achievements: list[dict[str, Any]] = deepcopy(self.role.get("achievements", []))
        self.current_index = -1
        self._loading = False

        self.id = QLineEdit(self.role.get("id", ""))
        self.id.setPlaceholderText("acme-senior")
        self.company = QLineEdit(self.role.get("company", ""))
        self.title = QLineEdit(self.role.get("title", ""))
        self.start = QLineEdit(self.role.get("start", ""))
        self.start.setPlaceholderText("2021-03")
        self.end = QLineEdit(self.role.get("end") or "")
        self.end.setPlaceholderText("2024-08, or leave empty")
        self.current = QCheckBox("Current role")
        self.current.setChecked(not self.role.get("end"))
        self.current.toggled.connect(lambda checked: self.end.setDisabled(checked))
        self.end.setDisabled(self.current.isChecked())
        self.location = QLineEdit(self.role.get("location", ""))
        self.scope = QPlainTextEdit(self.role.get("scope", ""))
        self.scope.setFixedHeight(80)

        form = QFormLayout()
        form.addRow("ID", self.id)
        form.addRow("Company", self.company)
        form.addRow("Title", self.title)
        dates = QHBoxLayout()
        dates.addWidget(self.start, 1)
        dates.addWidget(QLabel("to"))
        dates.addWidget(self.end, 1)
        dates.addWidget(self.current)
        form.addRow("Dates (YYYY-MM)", dates)
        form.addRow("Location", self.location)
        form.addRow("Scope", self.scope)

        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.load_achievement)
        self.list.setMinimumWidth(320)

        add = QPushButton("Add")
        remove = QPushButton("Remove")
        up = QPushButton("Up")
        down = QPushButton("Down")
        add.clicked.connect(self.add_achievement)
        remove.clicked.connect(self.remove_achievement)
        up.clicked.connect(lambda: self.move_achievement(-1))
        down.clicked.connect(lambda: self.move_achievement(1))
        list_buttons = QHBoxLayout()
        for button in (add, remove, up, down):
            list_buttons.addWidget(button)

        list_panel = QWidget()
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.addWidget(QLabel("Achievements"))
        list_layout.addWidget(self.list, 1)
        list_layout.addLayout(list_buttons)

        self.ach_id = QLineEdit()
        self.ach_id.setPlaceholderText("checkout-latency")
        self.ach_themes = QLineEdit()
        self.ach_themes.setPlaceholderText("performance, delivery")
        self.ach_text = QPlainTextEdit()
        self.ach_text.setPlaceholderText("Action → technology → measurable result.")
        self.ach_highlight = QCheckBox("Highlight this bullet")
        self.ach_fields = QWidget()
        ach_form = QFormLayout(self.ach_fields)
        ach_form.setContentsMargins(0, 0, 0, 0)
        ach_form.addRow("ID", self.ach_id)
        ach_form.addRow("Themes", self.ach_themes)
        ach_form.addRow("Text", self.ach_text)
        ach_form.addRow("", self.ach_highlight)

        self.ach_id.textEdited.connect(self.store_achievement)
        self.ach_themes.textEdited.connect(self.store_achievement)
        self.ach_text.textChanged.connect(self.store_achievement)
        self.ach_highlight.toggled.connect(self.store_achievement)

        editor = QGroupBox("Selected achievement")
        editor_layout = QVBoxLayout(editor)
        editor_layout.addWidget(self.ach_fields)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(list_panel)
        split.addWidget(editor)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(split, 1)
        layout.addWidget(buttons)

        self.refresh_list()
        if self.achievements:
            self.list.setCurrentRow(0)
        else:
            self.set_fields_enabled(False)

    def set_fields_enabled(self, enabled: bool) -> None:
        self.ach_fields.setEnabled(enabled)

    def refresh_list(self) -> None:
        self._loading = True
        self.list.clear()
        for achievement in self.achievements:
            label = ("★ " if achievement.get("highlight") else "") + elide(
                achievement.get("text") or achievement.get("id") or "Untitled", 70
            )
            item = QListWidgetItem(label)
            item.setToolTip(achievement.get("text", ""))
            self.list.addItem(item)
        self._loading = False
        if 0 <= self.current_index < self.list.count():
            self.list.setCurrentRow(self.current_index)

    def load_achievement(self, row: int) -> None:
        if self._loading:
            return
        if 0 <= self.current_index < len(self.achievements):
            self.store_achievement()
        self.current_index = row
        self._loading = True
        if 0 <= row < len(self.achievements):
            achievement = self.achievements[row]
            self.ach_id.setText(achievement.get("id", ""))
            self.ach_themes.setText(", ".join(achievement.get("themes", [])))
            self.ach_text.setPlainText(achievement.get("text", ""))
            self.ach_highlight.setChecked(bool(achievement.get("highlight")))
            self.set_fields_enabled(True)
        self._loading = False

    def store_achievement(self) -> None:
        if self._loading or not (0 <= self.current_index < len(self.achievements)):
            return
        achievement = self.achievements[self.current_index]
        achievement["id"] = self.ach_id.text().strip()
        achievement["themes"] = [part.strip() for part in self.ach_themes.text().split(",") if part.strip()]
        achievement["text"] = self.ach_text.toPlainText().strip()
        achievement["highlight"] = self.ach_highlight.isChecked()

        item = self.list.item(self.current_index)
        if item is not None:
            label = ("★ " if achievement["highlight"] else "") + elide(
                achievement["text"] or achievement["id"] or "Untitled", 70
            )
            item.setText(label)
            item.setToolTip(achievement["text"])

    def add_achievement(self) -> None:
        self.store_achievement()
        self.achievements.append(cvlib.new_achievement())
        self.current_index = len(self.achievements) - 1
        self.refresh_list()
        self.list.setCurrentRow(self.current_index)
        self.ach_id.setFocus()

    def remove_achievement(self) -> None:
        if not (0 <= self.current_index < len(self.achievements)):
            return
        del self.achievements[self.current_index]
        self.current_index = min(self.current_index, len(self.achievements) - 1)
        self.refresh_list()
        if self.achievements:
            self.list.setCurrentRow(self.current_index)
        else:
            self.current_index = -1
            self.ach_id.clear()
            self.ach_themes.clear()
            self.ach_text.clear()
            self.ach_highlight.setChecked(False)
            self.set_fields_enabled(False)

    def move_achievement(self, delta: int) -> None:
        target = self.current_index + delta
        if not (0 <= self.current_index < len(self.achievements)):
            return
        if not (0 <= target < len(self.achievements)):
            return
        self.store_achievement()
        self.achievements[self.current_index], self.achievements[target] = (
            self.achievements[target],
            self.achievements[self.current_index],
        )
        self.current_index = target
        self.refresh_list()
        self.list.setCurrentRow(target)

    def accept(self) -> None:
        self.store_achievement()
        error = self.validate_role()
        if error:
            QMessageBox.warning(self, "Cannot save role", error)
            return
        super().accept()

    def validate_role(self) -> str | None:
        slug = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        month = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")

        if not self.id.text().strip():
            return "The role needs an ID."
        if not slug.match(self.id.text().strip()):
            return "The role ID must be a lowercase slug, e.g. acme-senior."
        if not self.company.text().strip():
            return "The role needs a company."
        if not self.title.text().strip():
            return "The role needs a title."
        if not month.match(self.start.text().strip()):
            return "Start date must be YYYY-MM."
        if not self.current.isChecked() and not month.match(self.end.text().strip()):
            return "End date must be YYYY-MM, or tick 'Current role'."

        seen = set()
        for achievement in self.achievements:
            if not achievement["id"] or not slug.match(achievement["id"]):
                return "Every achievement needs a lowercase slug ID."
            if achievement["id"] in seen:
                return f"Duplicate achievement ID: {achievement['id']}"
            seen.add(achievement["id"])
            if not achievement["text"]:
                return f"Achievement '{achievement['id']}' has no text."
        return None

    def result_role(self) -> dict[str, Any]:
        role = deepcopy(self.role)
        role.update({
            "id": self.id.text().strip(),
            "company": self.company.text().strip(),
            "title": self.title.text().strip(),
            "start": self.start.text().strip(),
            "end": None if self.current.isChecked() else self.end.text().strip(),
            "location": self.location.text().strip(),
            "scope": self.scope.toPlainText().strip(),
            "achievements": deepcopy(self.achievements),
        })
        role["_file"] = self.role.get("_file")
        return role


# --------------------------------------------------------------------------
# Preview
# --------------------------------------------------------------------------

class AppearanceDialog(QDialog):
    """Accent and highlight colours, plus optional text, backdrop and font."""

    changed = Signal(dict)

    FALLBACK = {"text": "#1f2428", "desk": "#e5e7ea"}

    def __init__(self, theme: dict[str, str], overrides: dict[str, str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Customize style")
        self.values: dict[str, str] = {"accent": theme["accent"], "highlight": theme["highlight"]}
        for key in appearance.KEYS:
            if overrides.get(key):
                self.values[key] = overrides[key]
        self.start = dict(self.values)
        self.memory = {key: overrides.get(key) or self.FALLBACK[key] for key in appearance.COLOR_KEYS}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Changes show in the preview straight away. They apply to every layout."))
        form = QFormLayout()

        self.buttons: dict[str, QPushButton] = {}
        self.default_checks: dict[str, QCheckBox] = {}

        for key, label, hint in (
            ("accent", "Accent", "Headings, rules, and links"),
            ("highlight", "Highlight", "Bullets marked as important"),
        ):
            self.buttons[key] = self._color_button(key, hint)
            form.addRow(label, self.buttons[key])

        for key in appearance.COLOR_KEYS:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            self.buttons[key] = self._color_button(key, appearance.HINTS[key])
            check = QCheckBox("Layout default")
            check.setChecked(key not in self.values)
            check.toggled.connect(lambda on, k=key: self.toggle_default(k, on))
            self.default_checks[key] = check
            row_layout.addWidget(self.buttons[key], 1)
            row_layout.addWidget(check)
            form.addRow(appearance.LABELS[key], row)

        self.font_combo = QComboBox()
        self.font_combo.addItem("Layout default", "")
        for label, stack in appearance.FONT_CHOICES:
            self.font_combo.addItem(label, stack)
        current_font = self.values.get("font", "")
        if current_font and self.font_combo.findData(current_font) < 0:
            self.font_combo.addItem("Current font", current_font)
        self.font_combo.setCurrentIndex(max(self.font_combo.findData(current_font), 0))
        self.font_combo.currentIndexChanged.connect(self.pick_font)
        form.addRow(appearance.LABELS["font"], self.font_combo)
        layout.addLayout(form)

        row = QHBoxLayout()
        reset = QPushButton("Reset text, backdrop, font")
        reset.setToolTip("Go back to what the layout itself defines")
        reset.clicked.connect(self.reset_extras)
        row.addWidget(reset)
        row.addStretch(1)
        layout.addLayout(row)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)
        self.refresh()

    def _color_button(self, key: str, hint: str) -> QPushButton:
        button = QPushButton()
        button.setToolTip(hint)
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet("text-align: left; padding: 4px 10px;")
        button.clicked.connect(lambda _checked=False, k=key: self.pick(k))
        return button

    def refresh(self) -> None:
        for key, button in self.buttons.items():
            color = self.values.get(key) or self.memory.get(key, "#000000")
            button.setIcon(swatch_icon(color))
            button.setText("  " + color)
            if key in self.default_checks:
                button.setEnabled(not self.default_checks[key].isChecked())

    def pick(self, key: str) -> None:
        initial = self.values.get(key) or self.memory.get(key, "#000000")
        color = QColorDialog.getColor(QColor(initial), self, self.windowTitle())
        if not color.isValid():
            return
        self.values[key] = color.name()
        if key in self.memory:
            self.memory[key] = color.name()
        self.refresh()
        self.changed.emit(dict(self.values))

    def toggle_default(self, key: str, on: bool) -> None:
        if on:
            self.values.pop(key, None)
        else:
            self.values[key] = self.memory[key]
        self.refresh()
        self.changed.emit(dict(self.values))

    def pick_font(self, index: int) -> None:
        stack = self.font_combo.itemData(index)
        if stack:
            self.values["font"] = stack
        else:
            self.values.pop("font", None)
        self.changed.emit(dict(self.values))

    def reset_extras(self) -> None:
        for key in appearance.KEYS:
            self.values.pop(key, None)
        for check in self.default_checks.values():
            check.blockSignals(True)
            check.setChecked(True)
            check.blockSignals(False)
        self.font_combo.blockSignals(True)
        self.font_combo.setCurrentIndex(0)
        self.font_combo.blockSignals(False)
        self.refresh()
        self.changed.emit(dict(self.values))

    def reject(self) -> None:
        self.changed.emit(dict(self.start))
        super().reject()


class PreviewPane(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if WEBENGINE_AVAILABLE:
            self.view = QWebEngineView(self)
        else:
            self.view = QTextBrowser(self)
            self.view.setOpenExternalLinks(True)
        layout.addWidget(self.view)

    def set_html(self, html: str, base_url: QUrl) -> None:
        if WEBENGINE_AVAILABLE:
            self.view.setHtml(html, base_url)
        else:
            self.view.setHtml(
                "<h2>Live preview needs QtWebEngine</h2>"
                "<p>The QtWebEngine system libraries are missing on this machine.</p>"
                "<p>Use <b>View → Open preview in browser</b> to see the real layout. "
                "On Fedora, <code>sudo dnf install krb5-libs</code> usually fixes it.</p>"
            )

    def set_message(self, message: str) -> None:
        if WEBENGINE_AVAILABLE:
            self.view.setHtml(f"<p style='font-family:sans-serif;color:#8a4b08'>{message}</p>")
        else:
            self.view.setHtml(f"<p>{message}</p>")


class ExampleDialog(QDialog):
    def __init__(self, examples: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Load example")
        self.resize(680, 430)
        self.examples = examples

        self.list = QListWidget()
        for example in examples:
            self.list.addItem(example["name"])
        self.list.currentRowChanged.connect(self.show_description)
        self.list.itemDoubleClicked.connect(lambda _item: self.accept())

        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setMinimumHeight(52)
        self.description.setStyleSheet("color: #5f6b73;")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Load")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose a bundled layout. The sample dataset is read-only."))
        layout.addWidget(self.list, 1)
        layout.addWidget(self.description)
        layout.addWidget(buttons)

        self.list.setCurrentRow(0)

    def show_description(self, row: int) -> None:
        if 0 <= row < len(self.examples):
            example = self.examples[row]
            self.description.setText(
                f"<b>{example['name']}</b><br>{example['description']}"
            )
        else:
            self.description.clear()

    def selected_example(self) -> dict[str, Any] | None:
        row = self.list.currentRow()
        if 0 <= row < len(self.examples):
            return self.examples[row]
        return None


# --------------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self, data_root: Path) -> None:
        super().__init__()
        self.root = data_root
        self.dataset: dict[str, Any] = {}
        self.dirty_roles: set[Path] = set()
        self.profile_dirty = False
        self._updating = False
        self.template_path = cvlib.DEFAULT_TEMPLATE
        self.example: dict[str, Any] | None = None

        # Layout and look are view settings kept per user, not written to the dataset.
        self.settings = QSettings("CVBlocks", "CVSelector")
        self.layout_slug = self.saved_layout()
        self.appearance = appearance.loads(str(self.settings.value("appearance/json", "") or ""))

        self.setWindowTitle("CV Selector")
        self.resize(1360, 900)
        self._build_ui()
        self.load_dataset(data_root)

    # ---------------- UI ----------------

    def _build_ui(self) -> None:
        self.setStatusBar(QStatusBar(self))

        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        toolbar.addWidget(QLabel(" Style "))
        self.layout_combo = QComboBox()
        self.layout_combo.setMinimumWidth(170)
        self.layout_combo.setToolTip("Layout of the CV in the preview and the export")
        self.populate_layout_combo()
        self.layout_combo.currentIndexChanged.connect(self.on_layout_selected)
        toolbar.addWidget(self.layout_combo)

        self.customize_button = QToolButton()
        self.customize_button.setText("Customize…")
        self.customize_button.setToolTip("Accent, highlight, text colour, backdrop, and font")
        self.customize_button.clicked.connect(self.customize_style)
        toolbar.addWidget(self.customize_button)
        toolbar.addSeparator()

        self.accent_button = QToolButton()
        self.accent_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.accent_button.setText("Accent")
        self.accent_button.setToolTip("Colour for headings, rules, and links")
        self.accent_button.clicked.connect(lambda: self.pick_color("accent"))

        self.highlight_button = QToolButton()
        self.highlight_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.highlight_button.setText("Highlight")
        self.highlight_button.setToolTip("Colour for bullets marked as important")
        self.highlight_button.clicked.connect(lambda: self.pick_color("highlight"))

        toolbar.addWidget(self.accent_button)
        toolbar.addWidget(self.highlight_button)
        toolbar.addSeparator()

        self.mark_action = QAction("Mark important", self)
        self.mark_action.setToolTip("Toggle the highlight colour on checked bullets")
        self.mark_action.triggered.connect(self.toggle_highlight)
        toolbar.addAction(self.mark_action)

        select_all = QAction("Select all", self)
        select_all.triggered.connect(lambda: self.set_all_checked(True))
        clear_all = QAction("Clear", self)
        clear_all.triggered.connect(lambda: self.set_all_checked(False))
        toolbar.addAction(select_all)
        toolbar.addAction(clear_all)
        toolbar.addSeparator()

        self.save_action = QAction("Save", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save)
        self.export_action = QAction("Export HTML…", self)
        self.export_action.setShortcut("Ctrl+E")
        self.export_action.triggered.connect(self.export_html)
        toolbar.addAction(self.save_action)
        toolbar.addAction(self.export_action)

        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        file_menu.addAction("Open dataset…", self.open_dataset)
        file_menu.addAction("Load example…", self.load_example)
        file_menu.addSeparator()
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.export_action)
        self.save_selection_action = file_menu.addAction(
            "Save selection as…", self.save_manifest
        )
        file_menu.addSeparator()
        file_menu.addAction("Quit", self.close)

        edit_menu = menu.addMenu("&Edit")
        self.profile_action = edit_menu.addAction("Edit profile…", self.edit_profile)
        self.add_role_action = edit_menu.addAction("Add role…", self.add_role)
        self.edit_role_action = edit_menu.addAction("Edit role…", self.edit_role)
        self.delete_role_action = edit_menu.addAction("Delete role…", self.delete_role)

        self.example_locked_actions = [
            self.save_action,
            self.save_selection_action,
            self.mark_action,
            self.profile_action,
            self.add_role_action,
            self.edit_role_action,
            self.delete_role_action,
        ]
        self.example_locked_widgets: list[QWidget] = []

        view_menu = menu.addMenu("&View")
        view_menu.addAction("Refresh preview", self.update_preview, "F5")
        view_menu.addAction("Open preview in browser", self.open_in_browser)
        view_menu.addSeparator()
        view_menu.addAction("Customize style…", self.customize_style)

        help_menu = menu.addMenu("&Help")
        help_menu.addAction("About", self.about)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left: filters + tabs
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search achievements…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filters)

        self.theme_filter = QComboBox()
        self.theme_filter.currentTextChanged.connect(self.apply_filters)

        self.tabs = QTabWidget()

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Content", "Themes"])
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tree.header().resizeSection(1, 96)
        self.tree.setAlternatingRowColors(True)
        self.tree.setWordWrap(False)
        self.tree.itemChanged.connect(self.on_item_changed)
        self.tree.itemDoubleClicked.connect(self.on_tree_double_click)

        self.tabs.addTab(self.tree, "Experience")
        self.tabs.addTab(self._build_sections_tab(), "Sections")

        left_layout.addWidget(self.search)
        left_layout.addWidget(self.theme_filter)
        left_layout.addWidget(self.tabs, 1)

        # Right: preview
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        bar = QHBoxLayout()
        bar.setContentsMargins(10, 8, 10, 0)
        self.preview_label = QLabel("Preview")
        self.preview_label.setStyleSheet("font-weight: 600;")
        self.counts_label = QLabel("")
        self.counts_label.setStyleSheet("color: #6b7280;")
        open_button = QPushButton("Open in browser")
        open_button.clicked.connect(self.open_in_browser)
        bar.addWidget(self.preview_label)
        bar.addWidget(self.counts_label)
        bar.addStretch(1)
        bar.addWidget(open_button)
        right_layout.addLayout(bar)
        self.preview = PreviewPane()
        right_layout.addWidget(self.preview, 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 940])
        self.setCentralWidget(splitter)

    def _build_sections_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(4, 8, 4, 8)

        self.skill_boxes: list[QCheckBox] = []
        self.skills_box = QGroupBox("Skill categories")
        self.skills_layout = QVBoxLayout(self.skills_box)
        self.skills_layout.setSpacing(4)

        self.education_check = QCheckBox("Education")
        self.education_check.setChecked(True)
        self.education_check.toggled.connect(self.update_preview)
        self.extras_check = QCheckBox("Certifications, open source, talks, languages")
        self.extras_check.setChecked(True)
        self.extras_check.toggled.connect(self.update_preview)

        layout.addWidget(self.skills_box)
        layout.addWidget(self.education_check)
        layout.addWidget(self.extras_check)
        layout.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    # ---------------- Dataset ----------------

    def load_dataset(
        self,
        root: Path,
        template: Path | None = None,
        example: dict[str, Any] | None = None,
    ) -> None:
        try:
            dataset = cvlib.load_dataset(root)
        except cvlib.CVDatasetError as exc:
            QMessageBox.critical(self, "Cannot open dataset", str(exc))
            return
        self.root = root
        self.dataset = dataset
        self.template_path = template or cvlib.DEFAULT_TEMPLATE
        self.example = example
        self.dirty_roles.clear()
        self.profile_dirty = False
        if example:
            self.setWindowTitle(f"CV Selector — Example: {example['name']}")
        else:
            self.setWindowTitle(f"CV Selector — {root}")
        self.update_example_state()
        # An example brings its own layout; your own dataset uses the saved choice.
        self.layout_slug = "" if example else self.saved_layout()
        self.sync_layout_combo()
        self.refresh_theme_buttons()
        self.rebuild_sections()
        self.rebuild_tree()
        self.update_preview()
        if example:
            self.statusBar().showMessage(
                f"Example '{example['name']}' is read-only. Use File → Open dataset… to return.",
                8000,
            )

    def update_example_state(self) -> None:
        locked = self.example is not None
        for action in self.example_locked_actions:
            action.setEnabled(not locked)
        for widget in self.example_locked_widgets:
            widget.setEnabled(not locked)

    def output_root(self) -> Path:
        if self.example:
            return PROJECT_ROOT / "out"
        return self.root.parent / "out"

    def refresh_theme_buttons(self) -> None:
        theme = cvlib.theme_from(self.dataset["profile"])
        self.accent_button.setIcon(swatch_icon(theme["accent"]))
        self.highlight_button.setIcon(swatch_icon(theme["highlight"]))

    def rebuild_sections(self) -> None:
        while self.skills_layout.count():
            item = self.skills_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.skill_boxes.clear()

        categories = self.dataset["skills"]["categories"]
        if not categories:
            label = QLabel("No skill categories yet.")
            label.setStyleSheet("color: #6b7280;")
            self.skills_layout.addWidget(label)
            return

        for category in categories:
            box = QCheckBox(category["name"])
            box.setChecked(True)
            box.toggled.connect(self.update_preview)
            self.skills_layout.addWidget(box)
            self.skill_boxes.append(box)

    def rebuild_tree(self, preserved: set[tuple[str, str]] | None = None) -> None:
        self._updating = True
        self.role_index = {role["id"]: role for role in self.dataset["roles"]}
        self.tree.clear()

        theme = cvlib.theme_from(self.dataset["profile"])
        highlight_color = QColor(theme["highlight"])

        for role in self.sorted_roles():
            role_item = QTreeWidgetItem(self.tree, [f"{role['title']} — {role['company']}", ""])
            role_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "role", "role": role["id"]})
            role_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            role_font = role_item.font(0)
            role_font.setBold(True)
            role_item.setFont(0, role_font)
            role_item.setCheckState(0, Qt.CheckState.Checked)

            for achievement in role["achievements"]:
                prefix = "★ " if achievement.get("highlight") else ""
                child = QTreeWidgetItem(
                    role_item,
                    [prefix + elide(achievement["text"]), ", ".join(achievement.get("themes", []))],
                )
                child.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {"type": "ach", "role": role["id"], "achievement": achievement["id"]},
                )
                child.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                child.setToolTip(0, achievement["text"])
                if achievement.get("highlight"):
                    child.setForeground(0, QBrush(highlight_color))

                if preserved is None:
                    checked = True
                else:
                    checked = (role["id"], achievement["id"]) in preserved
                child.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

            self.sync_role_state(role_item)
            role_item.setExpanded(True)

        populate_theme_combo(self.theme_filter, self.dataset["roles"])
        self._updating = False
        self.apply_filters()
        self.update_preview()

    def sorted_roles(self) -> list[dict[str, Any]]:
        return sorted(
            self.dataset["roles"],
            key=lambda role: (role.get("end") or "9999-99", role["start"]),
            reverse=True,
        )

    def item_role(self, item: QTreeWidgetItem) -> dict[str, Any] | None:
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        return self.role_index.get(data.get("role"))

    def item_achievement(
        self, item: QTreeWidgetItem
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        role = self.role_index.get(data.get("role"))
        if role is None:
            return None, None
        achievement = next(
            (a for a in role["achievements"] if a["id"] == data.get("achievement")), None
        )
        return role, achievement

    # ---------------- Selection state ----------------

    def selection(self) -> set[tuple[str, str]]:
        chosen: set[tuple[str, str]] = set()
        for index in range(self.tree.topLevelItemCount()):
            role_item = self.tree.topLevelItem(index)
            role_data = role_item.data(0, Qt.ItemDataRole.UserRole)
            if not role_data:
                continue
            role_id = role_data.get("role")
            for child_index in range(role_item.childCount()):
                child = role_item.child(child_index)
                if child.checkState(0) == Qt.CheckState.Checked:
                    child_data = child.data(0, Qt.ItemDataRole.UserRole)
                    chosen.add((role_id, child_data.get("achievement")))
        return chosen

    def set_all_checked(self, checked: bool) -> None:
        self._updating = True
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for index in range(self.tree.topLevelItemCount()):
            role_item = self.tree.topLevelItem(index)
            role_item.setCheckState(0, state)
            for child_index in range(role_item.childCount()):
                role_item.child(child_index).setCheckState(0, state)
        self._updating = False
        self.update_preview()

    def on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._updating or column != 0:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        self._updating = True
        if data["type"] == "role":
            state = item.checkState(0)
            for index in range(item.childCount()):
                item.child(index).setCheckState(0, state)
        else:
            self.sync_role_state(item.parent())
        self._updating = False
        self.update_preview()

    def sync_role_state(self, role_item: QTreeWidgetItem) -> None:
        total = role_item.childCount()
        if total == 0:
            return
        checked = sum(
            1 for index in range(total)
            if role_item.child(index).checkState(0) == Qt.CheckState.Checked
        )
        if checked == 0:
            role_item.setCheckState(0, Qt.CheckState.Unchecked)
        elif checked == total:
            role_item.setCheckState(0, Qt.CheckState.Checked)
        else:
            role_item.setCheckState(0, Qt.CheckState.PartiallyChecked)

    def apply_filters(self) -> None:
        query = self.search.text().strip().lower()
        theme = self.theme_filter.currentText()

        for index in range(self.tree.topLevelItemCount()):
            role_item = self.tree.topLevelItem(index)
            visible_children = 0
            for child_index in range(role_item.childCount()):
                child = role_item.child(child_index)
                _, achievement = self.item_achievement(child)
                if achievement is None:
                    continue
                haystack = (achievement.get("text", "") + " " + " ".join(achievement.get("themes", []))).lower()
                matches_query = not query or query in haystack
                matches_theme = theme == "All themes" or theme in achievement.get("themes", [])
                visible = matches_query and matches_theme
                child.setHidden(not visible)
                if visible:
                    visible_children += 1
            role_item.setHidden(visible_children == 0)

    # ---------------- Layout and look ----------------

    def saved_layout(self) -> str:
        item = layouts.find(str(self.settings.value("layout/slug", "") or ""))
        return item["slug"] if item else ""

    def populate_layout_combo(self) -> None:
        combo = self.layout_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Default layout", "")
        combo.setItemData(0, "The template of the dataset (or of the loaded example)", Qt.ItemDataRole.ToolTipRole)
        for item in layouts.discover():
            combo.addItem(item["name"], item["slug"])
            combo.setItemData(combo.count() - 1, item["description"], Qt.ItemDataRole.ToolTipRole)
        combo.setCurrentIndex(max(combo.findData(self.layout_slug), 0))
        combo.blockSignals(False)

    def sync_layout_combo(self) -> None:
        self.layout_combo.blockSignals(True)
        self.layout_combo.setCurrentIndex(max(self.layout_combo.findData(self.layout_slug), 0))
        self.layout_combo.blockSignals(False)

    def on_layout_selected(self, index: int) -> None:
        slug = self.layout_combo.itemData(index)
        self.layout_slug = slug if isinstance(slug, str) else ""
        self.settings.setValue("layout/slug", self.layout_slug)
        self.update_preview()
        self.statusBar().showMessage(f"Layout: {self.layout_combo.itemText(index)}", 4000)

    def effective_template(self) -> Path:
        if self.layout_slug:
            item = layouts.find(self.layout_slug)
            if item:
                return item["template"]
        return self.template_path

    def render_html(self, manifest: dict[str, Any] | None = None) -> str:
        if manifest is None:
            manifest = self.current_manifest()
        return cvlib.render_dataset(
            self.dataset, manifest, self.effective_template(), self.appearance
        )

    def customize_style(self) -> None:
        profile = self.dataset["profile"]
        saved_theme = deepcopy(profile.get("theme"))
        saved_dirty = self.profile_dirty
        saved_look = dict(self.appearance)

        dialog = AppearanceDialog(cvlib.theme_from(profile), self.appearance, self)
        dialog.changed.connect(self.apply_appearance)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings.setValue("appearance/json", appearance.dumps(self.appearance))
            return

        # Cancelled: put back exactly what was there, including the dirty flag.
        if saved_theme is None:
            profile.pop("theme", None)
        else:
            profile["theme"] = saved_theme
        self.profile_dirty = saved_dirty
        self.appearance = saved_look
        self.refresh_theme_buttons()
        self.recolor_highlights()
        self.update_preview()

    def apply_appearance(self, values: dict[str, str]) -> None:
        profile = self.dataset["profile"]
        current = cvlib.theme_from(profile)
        if any(values.get(key) != current[key] for key in ("accent", "highlight")):
            theme = profile.setdefault("theme", dict(cvlib.DEFAULT_THEME))
            for key in ("accent", "highlight"):
                theme[key] = values.get(key, current[key])
            if not self.example:
                self.profile_dirty = True
        self.appearance = appearance.clean({key: values.get(key) for key in appearance.KEYS})
        self.refresh_theme_buttons()
        self.recolor_highlights()
        self.update_preview()

    # ---------------- Colours and highlighting ----------------

    def pick_color(self, key: str) -> None:
        theme = cvlib.theme_from(self.dataset["profile"])
        initial = QColor(theme[key])
        color = QColorDialog.getColor(initial, self, f"{key.capitalize()} colour")
        if not color.isValid():
            return
        self.dataset["profile"].setdefault("theme", dict(cvlib.DEFAULT_THEME))[key] = color.name()
        if not self.example:  # examples are read-only, so the colour only lives in memory
            self.profile_dirty = True
        self.refresh_theme_buttons()
        self.recolor_highlights()
        self.update_preview()

    def recolor_highlights(self) -> None:
        color = QBrush(QColor(cvlib.theme_from(self.dataset["profile"])["highlight"]))
        for index in range(self.tree.topLevelItemCount()):
            role_item = self.tree.topLevelItem(index)
            for child_index in range(role_item.childCount()):
                child = role_item.child(child_index)
                _, achievement = self.item_achievement(child)
                if achievement and achievement.get("highlight"):
                    child.setForeground(0, color)
                else:
                    child.setForeground(0, QBrush())

    def toggle_highlight(self) -> None:
        if self.example:
            return
        targets: list[QTreeWidgetItem] = []
        for index in range(self.tree.topLevelItemCount()):
            role_item = self.tree.topLevelItem(index)
            for child_index in range(role_item.childCount()):
                child = role_item.child(child_index)
                if child.checkState(0) == Qt.CheckState.Checked:
                    targets.append(child)

        if not targets:
            self.statusBar().showMessage("Check at least one bullet first.", 4000)
            return

        turn_on = not all(
            (self.item_achievement(child)[1] or {}).get("highlight")
            for child in targets
        )

        self._updating = True
        for child in targets:
            role, achievement = self.item_achievement(child)
            if role is None or achievement is None:
                continue
            achievement["highlight"] = turn_on
            role_file = role.get("_file")
            if role_file:
                self.dirty_roles.add(role_file)
            text = achievement.get("text", "")
            child.setText(0, ("★ " if turn_on else "") + elide(text))
        self._updating = False

        self.recolor_highlights()
        self.update_preview()
        self.statusBar().showMessage(
            f"{'Highlighted' if turn_on else 'Unhighlighted'} {len(targets)} bullet(s) — save to keep.",
            5000,
        )

    # ---------------- Preview and export ----------------

    def current_manifest(self) -> dict[str, Any]:
        roles = []
        for index in range(self.tree.topLevelItemCount()):
            role_item = self.tree.topLevelItem(index)
            role_data = role_item.data(0, Qt.ItemDataRole.UserRole)
            if not role_data:
                continue
            role_id = role_data.get("role")
            achievement_ids = []
            for child_index in range(role_item.childCount()):
                child = role_item.child(child_index)
                if child.checkState(0) == Qt.CheckState.Checked:
                    child_data = child.data(0, Qt.ItemDataRole.UserRole)
                    achievement_ids.append(child_data.get("achievement"))
            if achievement_ids:
                roles.append({"id": role_id, "achievements": achievement_ids})

        skills = [box.text() for box in self.skill_boxes if box.isChecked()]
        return {
            "application": {
                "company": "",
                "role_title": "",
                "date": date.today().isoformat(),
                "job_description": "",
            },
            "include": {
                "roles": roles,
                "skills": skills,
                "education": self.education_check.isChecked(),
                "extras": self.extras_check.isChecked(),
            },
        }

    def update_preview(self) -> None:
        if not self.dataset:
            return
        manifest = self.current_manifest()
        try:
            html = self.render_html(manifest)
        except cvlib.CVDatasetError as exc:
            self.preview.set_message(str(exc))
            self.statusBar().showMessage(str(exc), 8000)
            return

        base = QUrl.fromLocalFile(str(self.root) + "/")
        self.preview.set_html(html, base)

        roles = len(manifest["include"]["roles"])
        bullets = sum(len(role["achievements"]) for role in manifest["include"]["roles"])
        self.counts_label.setText(f"{roles} role(s) · {bullets} bullet(s)")

    def export_html(self) -> None:
        name = f"{self.example['slug']}.html" if self.example else f"cv-{date.today().isoformat()}.html"
        default = str(self.output_root() / name)
        path, _ = QFileDialog.getSaveFileName(self, "Export HTML", default, "HTML (*.html)")
        if not path:
            return
        try:
            html = self.render_html()
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(html, encoding="utf-8")
        except (cvlib.CVDatasetError, OSError) as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.statusBar().showMessage(f"Wrote {path}", 6000)

    def save_manifest(self) -> None:
        if self.example:
            return
        default = str(self.root / "applications" / date.today().isoformat() / "manifest.yaml")
        path, _ = QFileDialog.getSaveFileName(self, "Save selection", default, "YAML (*.yaml)")
        if not path:
            return
        try:
            cvlib.save_manifest(Path(path), self.current_manifest())
        except OSError as exc:
            QMessageBox.critical(self, "Could not save", str(exc))
            return
        self.statusBar().showMessage(f"Wrote {path}", 6000)

    def open_in_browser(self) -> None:
        try:
            html = self.render_html()
        except cvlib.CVDatasetError as exc:
            QMessageBox.critical(self, "Cannot render", str(exc))
            return
        target = self.output_root() / "preview.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    # ---------------- Editing ----------------

    def edit_profile(self) -> None:
        if self.example:
            return
        dialog = ProfileDialog(self.dataset["profile"], self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.dataset["profile"] = dialog.result_profile()
        self.profile_dirty = True
        self.refresh_theme_buttons()
        self.rebuild_tree(self.selection())
        self.recolor_highlights()

    def selected_role(self) -> dict[str, Any] | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        return self.item_role(item)

    def add_role(self) -> None:
        if self.example:
            return
        role = cvlib.new_role()
        dialog = RoleDialog(role, self)
        dialog.setWindowTitle("Add role")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        role = dialog.result_role()

        if any(existing["id"] == role["id"] for existing in self.dataset["roles"]):
            QMessageBox.warning(self, "Duplicate ID", f"A role with ID '{role['id']}' already exists.")
            return

        path = cvlib.role_path(self.root, role)
        known_files = {r.get("_file") for r in self.dataset["roles"]}
        counter = 2
        while path.exists() or path in known_files:
            path = path.with_name(f"{path.stem}-{counter}.yaml")
            counter += 1
        role["_file"] = path
        self.dataset["roles"].append(role)
        self.dirty_roles.add(path)
        preserved = self.selection() | {(role["id"], a["id"]) for a in role["achievements"]}
        self.rebuild_tree(preserved)
        self.statusBar().showMessage(f"Added {path.name} — save to write it.", 6000)

    def edit_role(self) -> None:
        if self.example:
            return
        role = self.selected_role()
        if role is None:
            self.statusBar().showMessage("Select a role first.", 4000)
            return

        dialog = RoleDialog(role, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.result_role()

        if any(
            existing["id"] == updated["id"] and existing is not role
            for existing in self.dataset["roles"]
        ):
            QMessageBox.warning(self, "Duplicate ID", f"A role with ID '{updated['id']}' already exists.")
            return

        previous = self.selection()
        old_role_id = role["id"]
        old_ids = {a["id"] for a in role["achievements"]}
        checked_ids = {aid for rid, aid in previous if rid == old_role_id}
        new_ids = {a["id"] for a in updated["achievements"]}

        role.clear()
        role.update(updated)
        role["_file"] = updated["_file"]
        if role["_file"]:
            self.dirty_roles.add(role["_file"])

        preserved = {
            pair for pair in previous
            if pair[0] not in (old_role_id, role["id"])
        }
        preserved |= {(role["id"], aid) for aid in checked_ids & new_ids}
        preserved |= {(role["id"], aid) for aid in new_ids - old_ids}
        self.rebuild_tree(preserved)

    def delete_role(self) -> None:
        if self.example:
            return
        role = self.selected_role()
        if role is None:
            self.statusBar().showMessage("Select a role first.", 4000)
            return
        answer = QMessageBox.question(
            self,
            "Delete role",
            f"Delete '{role['title']} — {role['company']}' and its YAML file?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        role_file = role.get("_file")
        if role_file and Path(role_file).exists():
            try:
                Path(role_file).unlink()
            except OSError as exc:
                QMessageBox.critical(self, "Could not delete", str(exc))
                return
        if role_file:
            self.dirty_roles.discard(role_file)
        self.dataset["roles"].remove(role)
        self.rebuild_tree(self.selection())
        self.statusBar().showMessage("Role deleted.", 5000)

    def on_tree_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data["type"] == "role":
            self.edit_role()

    # ---------------- Persistence ----------------

    def save(self) -> None:
        if self.example:
            return
        errors: list[str] = []
        try:
            if self.profile_dirty:
                cvlib.save_profile(self.dataset["profile"], self.root / "profile.yaml")
                self.profile_dirty = False
        except (cvlib.CVDatasetError, OSError) as exc:
            errors.append(str(exc))

        for path in sorted(self.dirty_roles):
            role = next((r for r in self.dataset["roles"] if r.get("_file") == path), None)
            if role is None:
                continue
            try:
                cvlib.save_role(role, path)
            except (cvlib.CVDatasetError, OSError) as exc:
                errors.append(str(exc))
        if not errors:
            self.dirty_roles.clear()

        if errors:
            QMessageBox.critical(self, "Save failed", "\n".join(errors))
        else:
            self.statusBar().showMessage("Saved.", 4000)

    def load_example(self) -> None:
        examples = discover_examples()
        if not examples:
            QMessageBox.information(
                self,
                "No examples",
                "No bundled examples were found next to the application.",
            )
            return

        dialog = ExampleDialog(examples, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        example = dialog.selected_example()
        if example is None:
            return

        if self.profile_dirty or self.dirty_roles:
            answer = QMessageBox.question(
                self,
                "Unsaved changes",
                "Discard unsaved changes and load the example?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.load_dataset(EXAMPLES_DATA, example["template"], example)

    def open_dataset(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open cv-data folder", str(self.root))
        if path:
            self.load_dataset(Path(path))

    def closeEvent(self, event: Any) -> None:
        if not self.profile_dirty and not self.dirty_roles:
            event.accept()
            return
        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            "Save your changes before closing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Save:
            self.save()
            event.accept()
        elif answer == QMessageBox.StandardButton.Discard:
            event.accept()
        else:
            event.ignore()

    def about(self) -> None:
        QMessageBox.about(
            self,
            "About CV Selector",
            "<h3>CV Selector</h3>"
            "<p>Edit the YAML dataset, pick the bullets for a role, "
            "highlight what matters, and export HTML.</p>"
            "<p>QtWebEngine: "
            + ("available" if WEBENGINE_AVAILABLE else "not available on this machine")
            + "</p>",
        )


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CV Selector desktop app")
    parser.add_argument("--data", type=Path, default=Path(__file__).resolve().parents[1] / "cv-data")
    parser.add_argument("--smoke", type=Path, help="screenshot the window and exit (testing)")
    args = parser.parse_args(argv)

    if WEBENGINE_AVAILABLE:
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("CV Selector")
    app.setStyle("Fusion")
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow(args.data)
    window.show()

    if args.smoke:
        def capture() -> None:
            window.grab().save(str(args.smoke))
            app.quit()

        QTimer.singleShot(1200, capture)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
