# Maestro Desmond PaCS-MD Setup Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Maestro GUI plugin that generates `input.toml` for PaCS-MD's Desmond adapter from form input, without launching the run itself.

**Architecture:** Split into a pure, Maestro-independent settings/TOML module (unit-testable) and a thin PyQt6 `QWidget` panel that collects form values, validates them, and calls into that module. The panel reads the currently-selected Maestro project table entry for display/context only — the actual starting structure is an explicit file-picker field (`structure_cms`), since a plain `Structure` object exported from a project table row cannot be safely turned back into a valid Desmond `.cms`.

**Tech Stack:** Python 3.8+, PyQt6 (bundled with Maestro, not a new dependency), `tomli` (already a PaCS-Toolkit dependency, used here only for round-trip test validation — the writer itself emits TOML text directly, no write-side TOML library needed), stdlib `unittest` (no test framework exists in this repo yet; not adding one for two test files).

**Spec:** `docs/superpowers/specs/2026-08-23-maestro-desmond-panel-design.md`

## Global Constraints

- Python >= 3.8 (repo's existing floor, see `setup.py` classifiers).
- No new runtime dependencies. PyQt6 comes from Maestro's own environment; `tomli` is already declared in `install_requires`.
- Match existing code style (see `pacs/mdrun/simulator/desmond.py`, `pacs/mdrun/exporter/desmond.py` for the established Desmond-adapter style in this repo).
- `maestro_plugin/pacs_desmond_panel.py` must be importable/runnable only inside Maestro's bundled Python — do not add a `$SCHRODINGER/run` requirement to it (that's the CLI exporter's constraint, not this panel's).
- Analyzer type support is `target` and `rmsd` only (see spec Non-goals).

---

### Task 1: Settings dict builder — core required fields

**Files:**
- Create: `maestro_plugin/__init__.py` (empty, makes it a package)
- Create: `maestro_plugin/pacs_toml_writer.py`
- Test: `tests/maestro_plugin/__init__.py` (empty)
- Test: `tests/maestro_plugin/test_pacs_toml_writer.py`

**Interfaces:**
- Produces: `build_settings_dict(*, structure_cms: str, msj_file: str, mdconf: str, working_dir: str, analyzer_type: str, threshold: float, reference: str, selection1: str, selection2: str, n_replica: int = 1, max_cycle: int = 1, n_parallel: int = 1, trial: int = 1, centering: bool = True, centering_selection: str = "protein", desmond_host: str = "localhost", desmond_maxjob: int = 1, desmond_lic: str = None, rmmol: bool = False, rmfile: bool = False) -> dict` — used by Task 5.

- [ ] **Step 1: Write the failing test**

```python
# tests/maestro_plugin/test_pacs_toml_writer.py
import unittest

from maestro_plugin.pacs_toml_writer import build_settings_dict


class TestBuildSettingsDict(unittest.TestCase):
    def _required_kwargs(self, **overrides):
        kwargs = dict(
            structure_cms="system.cms",
            msj_file="production.msj",
            mdconf="production.cfg",
            working_dir="./run1",
            analyzer_type="target",
            threshold=0.05,
            reference="ref.pdb",
            selection1="protein",
            selection2="protein",
        )
        kwargs.update(overrides)
        return kwargs

    def test_fixed_engine_fields(self):
        settings = build_settings_dict(**self._required_kwargs())
        self.assertEqual(settings["simulator"], "desmond")
        self.assertEqual(settings["analyzer"], "desmond")
        self.assertEqual(settings["trajectory_extension"], ".dtr")

    def test_structure_and_topology_share_the_same_cms(self):
        settings = build_settings_dict(**self._required_kwargs(structure_cms="foo.cms"))
        self.assertEqual(settings["structure"], "foo.cms")
        self.assertEqual(settings["topology"], "foo.cms")

    def test_rejects_unsupported_analyzer_type(self):
        with self.assertRaises(ValueError):
            build_settings_dict(**self._required_kwargs(analyzer_type="dissociation"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run (from repo root): `python -m unittest tests.maestro_plugin.test_pacs_toml_writer -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'maestro_plugin'` (or `.pacs_toml_writer`)

- [ ] **Step 3: Write minimal implementation**

```python
# maestro_plugin/pacs_toml_writer.py
"""Pure functions for building and serializing PaCS-MD Desmond input.toml
settings. No Maestro dependency - importable and testable standalone."""

from typing import Any, Dict, Optional

SUPPORTED_ANALYZER_TYPES = ("target", "rmsd")


def build_settings_dict(
    *,
    structure_cms: str,
    msj_file: str,
    mdconf: str,
    working_dir: str,
    analyzer_type: str,
    threshold: float,
    reference: str,
    selection1: str,
    selection2: str,
    n_replica: int = 1,
    max_cycle: int = 1,
    n_parallel: int = 1,
    trial: int = 1,
    centering: bool = True,
    centering_selection: str = "protein",
    desmond_host: str = "localhost",
    desmond_maxjob: int = 1,
    desmond_lic: Optional[str] = None,
    rmmol: bool = False,
    rmfile: bool = False,
) -> Dict[str, Any]:
    if analyzer_type not in SUPPORTED_ANALYZER_TYPES:
        raise ValueError(
            f"analyzer_type must be one of {SUPPORTED_ANALYZER_TYPES}, "
            f"got {analyzer_type!r}"
        )

    settings: Dict[str, Any] = {
        "trial": trial,
        "max_cycle": max_cycle,
        "n_replica": n_replica,
        "n_parallel": n_parallel,
        "centering": centering,
        "centering_selection": centering_selection,
        "working_dir": working_dir,
        "simulator": "desmond",
        "structure": structure_cms,
        "topology": structure_cms,
        "mdconf": mdconf,
        "msj_file": msj_file,
        "trajectory_extension": ".dtr",
        "desmond_host": desmond_host,
        "desmond_maxjob": desmond_maxjob,
        "type": analyzer_type,
        "threshold": threshold,
        "analyzer": "desmond",
        "reference": reference,
        "selection1": selection1,
        "selection2": selection2,
        "rmmol": rmmol,
        "rmfile": rmfile,
    }
    if desmond_lic:
        settings["desmond_lic"] = desmond_lic
    return settings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.maestro_plugin.test_pacs_toml_writer -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add maestro_plugin/__init__.py maestro_plugin/pacs_toml_writer.py tests/maestro_plugin/__init__.py tests/maestro_plugin/test_pacs_toml_writer.py
git commit -m "feat(maestro_plugin): add build_settings_dict for Desmond PaCS-MD panel

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01MzptFQGeUgdPaYLk416q4Y"
```

---

### Task 2: TOML serialization

**Files:**
- Modify: `maestro_plugin/pacs_toml_writer.py`
- Test: `tests/maestro_plugin/test_pacs_toml_writer.py`

**Interfaces:**
- Consumes: `build_settings_dict(...) -> dict` from Task 1.
- Produces: `settings_dict_to_toml(settings: dict) -> str` — used by Task 5.

- [ ] **Step 1: Write the failing test**

Add to `tests/maestro_plugin/test_pacs_toml_writer.py`:

```python
from maestro_plugin.pacs_toml_writer import build_settings_dict, settings_dict_to_toml


class TestSettingsDictToToml(unittest.TestCase):
    def test_emits_section_headers_in_order(self):
        settings = build_settings_dict(
            structure_cms="system.cms",
            msj_file="production.msj",
            mdconf="production.cfg",
            working_dir="./run1",
            analyzer_type="rmsd",
            threshold=0.1,
            reference="ref.pdb",
            selection1="protein",
            selection2="protein",
        )
        toml_text = settings_dict_to_toml(settings)
        basic_idx = toml_text.index("## basic")
        simulator_idx = toml_text.index("## simulator")
        analyzer_idx = toml_text.index("## analyzer")
        postprocess_idx = toml_text.index("## postprocess")
        self.assertTrue(basic_idx < simulator_idx < analyzer_idx < postprocess_idx)

    def test_string_values_are_quoted(self):
        settings = build_settings_dict(
            structure_cms="system.cms",
            msj_file="production.msj",
            mdconf="production.cfg",
            working_dir="./run1",
            analyzer_type="target",
            threshold=0.05,
            reference="ref.pdb",
            selection1="protein",
            selection2="protein",
        )
        toml_text = settings_dict_to_toml(settings)
        self.assertIn('simulator = "desmond"', toml_text)

    def test_numeric_and_bool_values_are_unquoted(self):
        settings = build_settings_dict(
            structure_cms="system.cms",
            msj_file="production.msj",
            mdconf="production.cfg",
            working_dir="./run1",
            analyzer_type="target",
            threshold=0.05,
            reference="ref.pdb",
            selection1="protein",
            selection2="protein",
            n_replica=20,
            centering=True,
        )
        toml_text = settings_dict_to_toml(settings)
        self.assertIn("n_replica = 20", toml_text)
        self.assertIn("centering = true", toml_text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.maestro_plugin.test_pacs_toml_writer -v`
Expected: FAIL with `ImportError: cannot import name 'settings_dict_to_toml'`

- [ ] **Step 3: Write minimal implementation**

Add to `maestro_plugin/pacs_toml_writer.py`:

```python
_SECTION_KEYS = [
    (
        "basic",
        [
            "trial",
            "max_cycle",
            "n_replica",
            "n_parallel",
            "centering",
            "centering_selection",
            "working_dir",
        ],
    ),
    (
        "simulator",
        [
            "simulator",
            "structure",
            "topology",
            "mdconf",
            "msj_file",
            "trajectory_extension",
            "desmond_host",
            "desmond_maxjob",
            "desmond_lic",
        ],
    ),
    (
        "analyzer",
        ["type", "threshold", "analyzer", "reference", "selection1", "selection2"],
    ),
    ("postprocess", ["rmmol", "rmfile"]),
]


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return f'"{value}"'


def settings_dict_to_toml(settings: Dict[str, Any]) -> str:
    lines = []
    for header, keys in _SECTION_KEYS:
        present = [k for k in keys if k in settings]
        if not present:
            continue
        lines.append(f"## {header}")
        for key in present:
            lines.append(f"{key} = {_format_value(settings[key])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.maestro_plugin.test_pacs_toml_writer -v`
Expected: all 6 tests PASS (3 from Task 1 + 3 new)

- [ ] **Step 5: Commit**

```bash
git add maestro_plugin/pacs_toml_writer.py tests/maestro_plugin/test_pacs_toml_writer.py
git commit -m "feat(maestro_plugin): add settings_dict_to_toml serialization

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01MzptFQGeUgdPaYLk416q4Y"
```

---

### Task 3: Round-trip validation against `tomli`

**Files:**
- Test: `tests/maestro_plugin/test_pacs_toml_writer.py`

**Interfaces:**
- Consumes: `build_settings_dict`, `settings_dict_to_toml` from Tasks 1-2. `tomli.loads` (already a repo dependency, see `setup.py` `install_requires`).
- Produces: nothing new — this task is pure verification that the two functions compose into valid, round-trippable TOML.

- [ ] **Step 1: Write the failing test**

Add to `tests/maestro_plugin/test_pacs_toml_writer.py`:

```python
import tomli


class TestRoundTrip(unittest.TestCase):
    def test_round_trip_preserves_values(self):
        settings = build_settings_dict(
            structure_cms="system.cms",
            msj_file="production.msj",
            mdconf="production.cfg",
            working_dir="./run1",
            analyzer_type="target",
            threshold=0.05,
            reference="ref.pdb",
            selection1="protein",
            selection2="protein",
            n_replica=20,
            max_cycle=100,
            desmond_lic="DESMOND_GPGPU:16",
        )
        toml_text = settings_dict_to_toml(settings)
        parsed = tomli.loads(toml_text)
        self.assertEqual(parsed["simulator"], "desmond")
        self.assertEqual(parsed["n_replica"], 20)
        self.assertEqual(parsed["max_cycle"], 100)
        self.assertEqual(parsed["threshold"], 0.05)
        self.assertEqual(parsed["desmond_lic"], "DESMOND_GPGPU:16")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.maestro_plugin.test_pacs_toml_writer -v`
Expected: FAIL only if `tomli` isn't installed in the current environment (`ModuleNotFoundError: No module named 'tomli'`) — if so, run `pip install tomli` first (it's already a declared dependency of this package, just needs to be present in the dev environment). If `tomli` is already installed, this test should PASS immediately since Tasks 1-2 already produce valid TOML — that's fine, it's still a real regression-guard for future changes to the writer.

- [ ] **Step 3: No implementation needed**

This task validates existing code from Tasks 1-2. If the test fails for a reason other than a missing `tomli` install, fix `settings_dict_to_toml` until it passes.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.maestro_plugin.test_pacs_toml_writer -v`
Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/maestro_plugin/test_pacs_toml_writer.py
git commit -m "test(maestro_plugin): add tomli round-trip regression test

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01MzptFQGeUgdPaYLk416q4Y"
```

---

### Task 4: The Maestro panel itself

**Files:**
- Create: `maestro_plugin/pacs_desmond_panel.py`

**Interfaces:**
- Consumes: `build_settings_dict`, `settings_dict_to_toml` from `maestro_plugin.pacs_toml_writer` (Tasks 1-2).
- Produces: `PaCSDesmondPanel(QWidget)` — the Maestro-registered entry point (`# Command: pythonrun pacs_desmond_panel.PaCSDesmondPanel`). Nothing later depends on this class's internals; it's the terminal consumer.

No automated tests for this file — it depends on the live `maestro` and `PyQt6` modules which only exist inside a running Maestro session (see spec's Testing section). Verification is the manual checklist in Step 2 below, run by the user inside real Maestro.

- [ ] **Step 1: Write the panel**

```python
# maestro_plugin/pacs_desmond_panel.py
__doc__ = """

Generate input.toml for a PaCS-MD Desmond run from the currently selected
Maestro project table entry. Does not launch the run - see the printed
`pacs mdrun` command in the confirmation dialog.

"""
# Name: PaCS-MD Desmond Setup
# Command: pythonrun pacs_desmond_panel.PaCSDesmondPanel

import os

from schrodinger import maestro
from schrodinger.Qt import PyQt6
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from maestro_plugin.pacs_toml_writer import build_settings_dict, settings_dict_to_toml

# jobscripts/desmond/ lives two directories up from this file
# (repo_root/maestro_plugin/pacs_desmond_panel.py -> repo_root/jobscripts/desmond/)
_DEFAULT_JOBSCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "jobscripts", "desmond"
)
_DEFAULT_MSJ = os.path.join(_DEFAULT_JOBSCRIPTS_DIR, "production.msj")
_DEFAULT_CFG = os.path.join(_DEFAULT_JOBSCRIPTS_DIR, "production.cfg")


def _browse_button(line_edit, caption, file_filter=None, directory=False):
    button = QPushButton("Browse...")

    def on_click():
        if directory:
            path = QFileDialog.getExistingDirectory(None, caption)
        else:
            path, _ = QFileDialog.getOpenFileName(None, caption, filter=file_filter or "")
        if path:
            line_edit.setText(path)

    button.clicked.connect(on_click)
    return button


class PaCSDesmondPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._selected_entry_label = QLabel()
        self._init_ui()
        self._refresh_selected_entry()

    def _init_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Selected Maestro entry (context only):"))
        layout.addWidget(self._selected_entry_label)

        structure_group = QGroupBox("Structure")
        structure_form = QFormLayout()
        self.structure_cms_edit = QLineEdit()
        structure_row = QHBoxLayout()
        structure_row.addWidget(self.structure_cms_edit)
        structure_row.addWidget(
            _browse_button(self.structure_cms_edit, "Select starting .cms", "CMS files (*.cms)")
        )
        structure_form.addRow("Starting .cms (equilibrated):", structure_row)
        structure_group.setLayout(structure_form)
        layout.addWidget(structure_group)

        sim_group = QGroupBox("Simulator files")
        sim_form = QFormLayout()
        self.msj_edit = QLineEdit(os.path.normpath(_DEFAULT_MSJ))
        msj_row = QHBoxLayout()
        msj_row.addWidget(self.msj_edit)
        msj_row.addWidget(_browse_button(self.msj_edit, "Select .msj", "MSJ files (*.msj)"))
        sim_form.addRow("msj_file:", msj_row)

        self.cfg_edit = QLineEdit(os.path.normpath(_DEFAULT_CFG))
        cfg_row = QHBoxLayout()
        cfg_row.addWidget(self.cfg_edit)
        cfg_row.addWidget(_browse_button(self.cfg_edit, "Select .cfg", "CFG files (*.cfg)"))
        sim_form.addRow("mdconf (.cfg):", cfg_row)
        sim_group.setLayout(sim_form)
        layout.addWidget(sim_group)

        analyzer_group = QGroupBox("Analyzer")
        analyzer_form = QFormLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["target", "rmsd"])
        analyzer_form.addRow("type:", self.type_combo)

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setDecimals(4)
        self.threshold_spin.setRange(0.0, 1000.0)
        self.threshold_spin.setValue(0.05)
        analyzer_form.addRow("threshold:", self.threshold_spin)

        self.reference_edit = QLineEdit()
        reference_row = QHBoxLayout()
        reference_row.addWidget(self.reference_edit)
        reference_row.addWidget(
            _browse_button(self.reference_edit, "Select reference structure")
        )
        analyzer_form.addRow("reference:", reference_row)

        self.selection1_edit = QLineEdit("protein")
        analyzer_form.addRow("selection1:", self.selection1_edit)
        self.selection2_edit = QLineEdit("protein")
        analyzer_form.addRow("selection2:", self.selection2_edit)
        analyzer_group.setLayout(analyzer_form)
        layout.addWidget(analyzer_group)

        basic_group = QGroupBox("Basic")
        basic_form = QFormLayout()
        self.n_replica_spin = QSpinBox()
        self.n_replica_spin.setRange(1, 999)
        self.n_replica_spin.setValue(1)
        basic_form.addRow("n_replica:", self.n_replica_spin)

        self.max_cycle_spin = QSpinBox()
        self.max_cycle_spin.setRange(1, 999)
        self.max_cycle_spin.setValue(1)
        basic_form.addRow("max_cycle:", self.max_cycle_spin)

        self.n_parallel_spin = QSpinBox()
        self.n_parallel_spin.setRange(1, 999)
        self.n_parallel_spin.setValue(1)
        basic_form.addRow("n_parallel:", self.n_parallel_spin)

        self.trial_spin = QSpinBox()
        self.trial_spin.setRange(1, 999)
        self.trial_spin.setValue(1)
        basic_form.addRow("trial:", self.trial_spin)

        self.centering_check = QCheckBox()
        self.centering_check.setChecked(True)
        basic_form.addRow("centering:", self.centering_check)

        self.centering_selection_edit = QLineEdit("protein")
        basic_form.addRow("centering_selection:", self.centering_selection_edit)
        basic_group.setLayout(basic_form)
        layout.addWidget(basic_group)

        output_group = QGroupBox("Output")
        output_form = QFormLayout()
        self.working_dir_edit = QLineEdit()
        working_dir_row = QHBoxLayout()
        working_dir_row.addWidget(self.working_dir_edit)
        working_dir_row.addWidget(
            _browse_button(self.working_dir_edit, "Select working directory", directory=True)
        )
        output_form.addRow("working_dir:", working_dir_row)
        output_group.setLayout(output_form)
        layout.addWidget(output_group)

        advanced_group = QGroupBox("Advanced")
        advanced_group.setCheckable(True)
        advanced_group.setChecked(False)
        advanced_form = QFormLayout()
        self.desmond_host_edit = QLineEdit("localhost")
        advanced_form.addRow("desmond_host:", self.desmond_host_edit)
        self.desmond_maxjob_spin = QSpinBox()
        self.desmond_maxjob_spin.setRange(1, 999)
        self.desmond_maxjob_spin.setValue(1)
        advanced_form.addRow("desmond_maxjob:", self.desmond_maxjob_spin)
        self.desmond_lic_edit = QLineEdit()
        self.desmond_lic_edit.setPlaceholderText("e.g. DESMOND_GPGPU:16 (optional)")
        advanced_form.addRow("desmond_lic:", self.desmond_lic_edit)
        self.rmmol_check = QCheckBox()
        advanced_form.addRow("rmmol:", self.rmmol_check)
        self.rmfile_check = QCheckBox()
        advanced_form.addRow("rmfile:", self.rmfile_check)
        advanced_group.setLayout(advanced_form)
        layout.addWidget(advanced_group)

        generate_button = QPushButton("Generate input.toml")
        generate_button.clicked.connect(self._on_generate_clicked)
        layout.addWidget(generate_button)

        self.setLayout(layout)
        self.setWindowTitle("PaCS-MD Desmond Setup")
        self.show()

    def _refresh_selected_entry(self):
        try:
            pt = maestro.project_table_get()
            selected = list(pt.selected_rows)
        except Exception:
            selected = []
        if not selected:
            self._selected_entry_label.setText("(none selected)")
        elif len(selected) == 1:
            row = selected[0]
            title = row.property.get("s_m_title", "<untitled>")
            self._selected_entry_label.setText(f"{title}")
        else:
            self._selected_entry_label.setText(f"{len(selected)} entries selected (context only)")

    def _validate(self):
        errors = []
        if not self.structure_cms_edit.text().strip():
            errors.append("Starting .cms is required.")
        elif not os.path.isfile(self.structure_cms_edit.text().strip()):
            errors.append(f"Starting .cms not found: {self.structure_cms_edit.text()}")

        if not os.path.isfile(self.msj_edit.text().strip()):
            errors.append(f"msj_file not found: {self.msj_edit.text()}")
        if not os.path.isfile(self.cfg_edit.text().strip()):
            errors.append(f"mdconf (.cfg) not found: {self.cfg_edit.text()}")
        if not self.reference_edit.text().strip():
            errors.append("reference structure is required.")
        elif not os.path.isfile(self.reference_edit.text().strip()):
            errors.append(f"reference not found: {self.reference_edit.text()}")

        working_dir = self.working_dir_edit.text().strip()
        if not working_dir:
            errors.append("working_dir is required.")
        else:
            os.makedirs(working_dir, exist_ok=True)
            if not os.access(working_dir, os.W_OK):
                errors.append(f"working_dir is not writable: {working_dir}")

        return errors

    def _on_generate_clicked(self):
        self._refresh_selected_entry()
        errors = self._validate()
        if errors:
            QMessageBox.critical(self, "Cannot generate input.toml", "\n".join(errors))
            return

        settings = build_settings_dict(
            structure_cms=self.structure_cms_edit.text().strip(),
            msj_file=self.msj_edit.text().strip(),
            mdconf=self.cfg_edit.text().strip(),
            working_dir=self.working_dir_edit.text().strip(),
            analyzer_type=self.type_combo.currentText(),
            threshold=self.threshold_spin.value(),
            reference=self.reference_edit.text().strip(),
            selection1=self.selection1_edit.text().strip(),
            selection2=self.selection2_edit.text().strip(),
            n_replica=self.n_replica_spin.value(),
            max_cycle=self.max_cycle_spin.value(),
            n_parallel=self.n_parallel_spin.value(),
            trial=self.trial_spin.value(),
            centering=self.centering_check.isChecked(),
            centering_selection=self.centering_selection_edit.text().strip(),
            desmond_host=self.desmond_host_edit.text().strip() or "localhost",
            desmond_maxjob=self.desmond_maxjob_spin.value(),
            desmond_lic=self.desmond_lic_edit.text().strip() or None,
            rmmol=self.rmmol_check.isChecked(),
            rmfile=self.rmfile_check.isChecked(),
        )
        toml_text = settings_dict_to_toml(settings)

        working_dir = self.working_dir_edit.text().strip()
        output_path = os.path.join(working_dir, "input.toml")
        with open(output_path, "w") as f:
            f.write(toml_text)

        QMessageBox.information(
            self,
            "input.toml written",
            f"Written to {output_path}\n\n"
            f"Run with:\npacs mdrun -t {self.trial_spin.value()} -f {output_path}",
        )
```

- [ ] **Step 2: Manual verification checklist (run inside a real Maestro session)**

1. Copy `maestro_plugin/pacs_desmond_panel.py` (and ensure `maestro_plugin/pacs_toml_writer.py` is importable — either install the `pacs` package in Maestro's Python, or copy both files into the same directory Maestro launches scripts from) into your Maestro scripts directory.
2. Launch Maestro, run `pythonimport pacs_desmond_panel` then `pythonrun pacs_desmond_panel.PaCSDesmondPanel` (or use the menu entry the `# Name`/`# Command` comments register).
3. Confirm the panel opens, the msj/cfg fields default to `jobscripts/desmond/production.msj`/`production.cfg` resolved relative to the file's real location.
4. Select a project table entry — confirm the "Selected Maestro entry" label updates to show its title.
5. Leave `working_dir` empty, click Generate — confirm a validation error appears and nothing is written.
6. Fill all required fields with real paths (a real equilibrated `.cms`, a real reference structure, a writable `working_dir`), click Generate — confirm `input.toml` is written and its contents are valid (open it, or run `python -m unittest tests.maestro_plugin.test_pacs_toml_writer` separately to confirm the writer logic itself is sound — this manual step is about confirming the GUI wiring, not re-testing the pure logic).
7. Confirm the dialog's suggested `pacs mdrun` command matches the file actually written.

- [ ] **Step 3: Commit**

```bash
git add maestro_plugin/pacs_desmond_panel.py
git commit -m "feat(maestro_plugin): add PaCSDesmondPanel Maestro GUI plugin

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01MzptFQGeUgdPaYLk416q4Y"
```

---

### Task 5: README pointer

**Files:**
- Modify: `README.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Add a line to the existing Desmond bullet**

In the `## Supported MD engines` section, extend the existing Desmond bullet (added in a prior session) to mention the panel:

```markdown
- Desmond ⚠️ *experimental* — the simulator/exporter adapter is implemented and its Schrodinger API calls are verified against the official docs, but the `multisim` invocation and job-script templates ([`jobscripts/desmond/`](jobscripts/desmond/)) still need validation against a real run before being considered production-ready. A Maestro GUI panel ([`maestro_plugin/pacs_desmond_panel.py`](maestro_plugin/pacs_desmond_panel.py)) is available to generate `input.toml` from inside Maestro. Feedback and bug reports welcome.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: mention Maestro Desmond panel in README

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01MzptFQGeUgdPaYLk416q4Y"
```
