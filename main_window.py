import json
from PySide6.QtWidgets import (QMainWindow, QTextEdit, QVBoxLayout, QHBoxLayout, QWidget, 
                               QPushButton, QFileDialog, QListWidget, QSplitter, QLineEdit,
                               QFormLayout, QComboBox, QSpinBox, QDialog, QDialogButtonBox, QLabel, QMessageBox) # Added QMessageBox
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from message_factory import MessageFactory
from secs_handler import EquipmentHandler, ScenarioExecutor

# AddStepDialog is unchanged
class AddStepDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Add New Step"); layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select action type:")); self.action_combo = QComboBox()
        self.action_combo.addItems(["send", "expect", "if", "loop", "delay"]); layout.addWidget(self.action_combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
    def get_selected_action(self): return self.action_combo.currentText()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SECS/GEM Simulator v1.6.0")
        # ... other init properties are unchanged ...
        self.factory = MessageFactory(); self.scenario_data = {'name': 'New Scenario', 'steps': []}
        self.current_scenario_file_path = None; self.all_logs = []
        self._setup_ui()
    
    # _setup_ui is unchanged
    def _setup_ui(self):
        menu_bar = self.menuBar(); file_menu = menu_bar.addMenu("&File")
        load_action = QAction("&Load Scenario...", self); load_action.triggered.connect(self.load_scenario_from_file); file_menu.addAction(load_action)
        save_action = QAction("&Save Scenario", self); save_action.triggered.connect(self.save_scenario); file_menu.addAction(save_action)
        file_menu.addSeparator()
        import_action = QAction("&Import External Library...", self); import_action.triggered.connect(self.import_library); file_menu.addAction(import_action)
        self.steps_list_widget = QListWidget(); self.steps_list_widget.currentItemChanged.connect(self.populate_step_editor)
        add_step_btn = QPushButton("Add Step"); add_step_btn.clicked.connect(self.add_step)
        remove_step_btn = QPushButton("Remove Step"); remove_step_btn.clicked.connect(self.remove_step)
        editor_layout = QVBoxLayout(); editor_layout.addWidget(add_step_btn); editor_layout.addWidget(remove_step_btn); editor_layout.addWidget(self.steps_list_widget)
        editor_widget = QWidget(); editor_widget.setLayout(editor_layout)
        self.step_editor_widget = QWidget(); self.step_editor_layout = QFormLayout(self.step_editor_widget)
        self.log_area = QTextEdit(); self.log_area.setReadOnly(True)
        self.filter_input = QLineEdit(); self.filter_input.setPlaceholderText("Filter logs..."); self.filter_input.textChanged.connect(self.filter_logs)
        log_layout = QVBoxLayout(); log_layout.addWidget(self.filter_input); log_layout.addWidget(self.log_area)
        log_widget = QWidget(); log_widget.setLayout(log_layout)
        self.btn_start_equip = QPushButton("Start Equipment"); self.btn_start_equip.clicked.connect(self.start_equipment)
        self.btn_run_scenario = QPushButton("Run Current Scenario"); self.btn_run_scenario.clicked.connect(self.run_scenario)
        main_controls_layout = QHBoxLayout(); main_controls_layout.addWidget(self.btn_start_equip); main_controls_layout.addWidget(self.btn_run_scenario)
        left_pane = QSplitter(Qt.Orientation.Vertical); left_pane.addWidget(editor_widget); left_pane.addWidget(self.step_editor_widget)
        main_splitter = QSplitter(Qt.Orientation.Horizontal); main_splitter.addWidget(left_pane); main_splitter.addWidget(log_widget); main_splitter.setSizes([400, 600])
        central_layout = QVBoxLayout(); central_layout.addLayout(main_controls_layout); central_layout.addWidget(main_splitter)
        central_widget = QWidget(); central_widget.setLayout(central_layout); self.setCentralWidget(central_widget)

    def run_scenario(self):
        if not self.scenario_data['steps']:
            self.log_message("[ERROR] Scenario has no steps.")
            return
        self.btn_run_scenario.setEnabled(False) # Disable button while running
        executor = ScenarioExecutor(self.factory, self.scenario_data)
        executor.log_signal.connect(self.log_message)
        executor.scenario_finished.connect(self.show_report) # Connect to the new signal
        executor.start()

    def show_report(self, report):
        """NEW: Displays the final test report in a dialog."""
        self.btn_run_scenario.setEnabled(True) # Re-enable button
        
        title = f"Test Report: {report['name']}"
        
        details = (f"Overall Result: {report['result']}\n"
                   f"Duration: {report['duration']}\n\n"
                   f"--- Steps ---\n" +
                   "\n".join(report['steps']))

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(f"Scenario finished with result: **{report['result']}**")
        msg_box.setInformativeText(details)
        msg_box.exec()

    # ... all other MainWindow methods are unchanged ...
    def populate_step_editor(self, current, previous):
        while self.step_editor_layout.rowCount() > 0: self.step_editor_layout.removeRow(0)
        row = self.steps_list_widget.currentRow()
        if row == -1 or not current: return
        step_data = self.scenario_data['steps'][row]; action = step_data.get('action')
        action_combo = QComboBox(); action_combo.addItems(["send", "expect", "if", "loop", "delay"])
        action_combo.currentTextChanged.connect(lambda text, r=row, k='action': self.update_step_data(r, k, text))
        action_combo.blockSignals(True); action_combo.setCurrentText(action); action_combo.blockSignals(False)
        self.step_editor_layout.addRow("Action:", action_combo)
        if action in ['send', 'expect']:
            msg_combo = QComboBox(); msg_combo.addItems(self.factory.message_names)
            msg_combo.currentTextChanged.connect(lambda text, r=row, k='message': self.update_step_data(r, k, text))
            msg_combo.blockSignals(True); msg_combo.setCurrentText(step_data.get('message')); msg_combo.blockSignals(False)
            self.step_editor_layout.addRow("Message:", msg_combo)
        elif action == 'delay':
            seconds_spin = QSpinBox(); seconds_spin.setMinimum(1)
            seconds_spin.valueChanged.connect(lambda val, r=row, k='seconds': self.update_step_data(r, k, val))
            seconds_spin.blockSignals(True); seconds_spin.setValue(step_data.get('seconds', 1)); seconds_spin.blockSignals(False)
            self.step_editor_layout.addRow("Seconds:", seconds_spin)
    def update_step_data(self, row, key, value):
        if row < len(self.scenario_data['steps']):
            is_action_change = key == 'action'; self.scenario_data['steps'][row][key] = value
            self.update_list_item_text(row); self.log_message(f"UI_UPDATE | Step {row + 1}: Set '{key}' to '{value}'")
            if is_action_change: self.populate_step_editor(self.steps_list_widget.currentItem(), None)
    def update_list_item_text(self, row):
        item = self.steps_list_widget.item(row)
        if not item: return
        step = self.scenario_data['steps'][row]
        action = step.get('action', 'N/A').upper(); details = ""
        if action in ["SEND", "EXPECT"]: details = step.get('message', '')
        item.setText(f"{row+1}: {action} - {details}")
    def add_step(self):
        dialog = AddStepDialog(self)
        if dialog.exec():
            action = dialog.get_selected_action(); new_step = {"action": action}
            if action in ["send", "expect"]: new_step["message"] = "S1F13"
            else: new_step.update({"seconds": 1})
            self.scenario_data['steps'].append(new_step)
            self.refresh_steps_list(); self.steps_list_widget.setCurrentRow(len(self.scenario_data['steps']) - 1)
    def refresh_steps_list(self):
        self.steps_list_widget.clear()
        for i, step in enumerate(self.scenario_data['steps']):
            action = step.get('action', 'N/A').upper(); details = ""
            if action in ["SEND", "EXPECT"]: details = step.get('message', '')
            self.steps_list_widget.addItem(f"{i+1}: {action} - {details}")
    def remove_step(self):
        if (current_row := self.steps_list_widget.currentRow()) > -1: del self.scenario_data['steps'][current_row]; self.refresh_steps_list()
    def start_equipment(self):
        handler = EquipmentHandler(self.factory); handler.log_signal.connect(self.log_message); handler.start(); self.btn_start_equip.setEnabled(False)
    def log_message(self, message):
        full_log_line = f"[{__import__('time').strftime('%H:%M:%S')}] | {message}"; self.all_logs.append(full_log_line)
        if not (filter_text := self.filter_input.text()) or filter_text.lower() in full_log_line.lower(): self.log_area.append(full_log_line)
    def filter_logs(self):
        filter_text = self.filter_input.text().lower(); self.log_area.clear()
        self.log_area.setPlainText("\n".join([log for log in self.all_logs if filter_text in log.lower()]))
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())
    def save_scenario(self, save_as=False):
        filepath = self.current_scenario_file_path;
        if save_as or not filepath: filepath, _ = QFileDialog.getSaveFileName(self, "Save Scenario As...", "", "JSON Files (*.json)");
        if filepath:
            self.current_scenario_file_path = filepath
            with open(filepath, 'w') as f: json.dump(self.scenario_data, f, indent=2); self.log_message(f"Scenario saved to {filepath}")
    def load_scenario_from_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Scenario", "", "JSON Files (*.json)")
        if filepath:
            self.current_scenario_file_path = filepath;
            with open(filepath, 'r') as f: self.scenario_data = json.load(f)
            self.log_message(f"Scenario loaded from {filepath}"); self.refresh_steps_list()
    def import_library(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Library", "", "JSON Files (*.json)")
        if filepath:
            new_messages = self.factory.add_from_file(filepath); self.log_message(f"Imported {len(new_messages)} new messages.")
            self.populate_step_editor(self.steps_list_widget.currentItem(), None)