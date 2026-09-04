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
