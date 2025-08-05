import json
from PySide6.QtWidgets import (QMainWindow, QTextEdit, QVBoxLayout, QHBoxLayout, QWidget,
                               QPushButton, QFileDialog, QListWidget, QSplitter,
                               QFormLayout, QComboBox, QSpinBox, QDialog, QDialogButtonBox, QLabel,
                               QAbstractItemView, QLineEdit, QListWidgetItem, QTreeWidget, QTreeWidgetItem)
from PySide6.QtGui import QAction, QColor
from PySide6.QtCore import Qt, QTimer

from message_factory import MessageFactory
from secs_handler import EquipmentHandler, ScenarioExecutor
from report_dialog import ReportDialog

class DraggableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

class AddStepDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Step")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select action type:"))
        self.action_combo = QComboBox()
        self.action_combo.addItems(["send", "expect", "if", "loop", "delay", "call", "log"])
        layout.addWidget(self.action_combo)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_action(self):
        return self.action_combo.currentText()

class SimulatorWindow(QMainWindow):
    def __init__(self, conn_details):
        super().__init__()
        self.conn_details = conn_details
        self.setWindowTitle(f"SECS/GEM Simulator - {self.conn_details['name']}")
        self.setGeometry(150, 150, 1200, 800)
        self.factory = MessageFactory()
        self.scenario_data = {'name': 'New Scenario', 'steps': []}
        self.current_scenario_file_path = None
        self.all_logs = []
        self._setup_ui()

    def _setup_ui(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        load_action = QAction("&Load Scenario...", self); load_action.triggered.connect(self.load_scenario_from_file); file_menu.addAction(load_action)
        save_action = QAction("&Save Scenario", self); save_action.triggered.connect(self.save_scenario); file_menu.addAction(save_action)

        self.steps_list_widget = DraggableListWidget(self)
        self.steps_list_widget.currentItemChanged.connect(self.populate_step_editor)
        self.steps_list_widget.model().rowsMoved.connect(self.on_steps_reordered)

        add_step_btn = QPushButton("Add Step"); add_step_btn.clicked.connect(self.add_step)
        remove_step_btn = QPushButton("Remove Step"); remove_step_btn.clicked.connect(self.remove_step)
        editor_layout = QVBoxLayout(); editor_layout.addWidget(add_step_btn); editor_layout.addWidget(remove_step_btn); editor_layout.addWidget(self.steps_list_widget)
        editor_widget = QWidget(); editor_widget.setLayout(editor_layout)
        
        self.step_editor_widget = QWidget()
        step_editor_main_layout = QVBoxLayout(self.step_editor_widget)
        self.step_action_form = QFormLayout()
        self.message_body_tree = QTreeWidget()
        self.message_body_tree.setHeaderLabels(["Name", "Format", "Value"])
        self.message_body_tree.setColumnWidth(0, 150)
        self.message_body_tree.setColumnWidth(1, 70)
        step_editor_main_layout.addLayout(self.step_action_form)
        step_editor_main_layout.addWidget(QLabel("Message Body:"))
        step_editor_main_layout.addWidget(self.message_body_tree)
        
        self.log_area = QTextEdit(); self.log_area.setReadOnly(True)
        self.filter_input = QLineEdit(); self.filter_input.setPlaceholderText("Filter logs...")
        self.filter_input.textChanged.connect(self.filter_logs)
        log_layout = QVBoxLayout(); log_layout.addWidget(self.filter_input); log_layout.addWidget(self.log_area)
        log_widget = QWidget(); log_widget.setLayout(log_layout)
        
        self.btn_start_equip = QPushButton(f"Start Listener on Port {self.conn_details['port']}")
        self.btn_start_equip.clicked.connect(self.start_equipment)
        self.btn_run_scenario = QPushButton("Run Current Scenario")
        self.btn_run_scenario.clicked.connect(self.run_scenario)
        main_controls_layout = QHBoxLayout(); main_controls_layout.addWidget(self.btn_start_equip); main_controls_layout.addWidget(self.btn_run_scenario)
        
        left_pane = QSplitter(Qt.Orientation.Vertical); left_pane.addWidget(editor_widget); left_pane.addWidget(self.step_editor_widget)
        main_splitter = QSplitter(Qt.Orientation.Horizontal); main_splitter.addWidget(left_pane); main_splitter.addWidget(log_widget)
        main_splitter.setSizes([500, 700])
        
        central_layout = QVBoxLayout(); central_layout.addLayout(main_controls_layout); central_layout.addWidget(main_splitter)
        central_widget = QWidget(); central_widget.setLayout(central_layout); self.setCentralWidget(central_widget)

    def log_message(self, level, message):
        timestamp = __import__('time').strftime('%H:%M:%S')
        
        color_map = {
            "SENT": "#007acc", "RECV": "#2a9d8f", "ERROR": "#e63946",
            "UI_UPDATE": "#8d99ae", "SCENARIO": "#e9c46a", "INFO": "#577590"
        }
        color = color_map.get(level, "#333333")

        full_log_line = f"[{timestamp}] | {level} | {message}"
        html_log_line = f'<span style="color: {color};">{full_log_line}</span>'
        
        self.all_logs.append(full_log_line)
        
        filter_text = self.filter_input.text()
        if not filter_text or filter_text.lower() in full_log_line.lower():
            self.log_area.append(html_log_line)

    def update_step_data(self, row, key, value):
        if row < len(self.scenario_data['steps']):
            is_major_change = key == 'action' or key == 'message'
            self.scenario_data['steps'][row][key] = value
            self.update_list_item_text(row)
            self.log_message("UI_UPDATE", f"Step {row + 1}: Set '{key}' to '{value}'")
            if is_major_change:
                QTimer.singleShot(0, lambda: self.populate_step_editor(self.steps_list_widget.currentItem(), None))

    def populate_step_editor(self, current, previous):
        while self.step_action_form.rowCount() > 0: self.step_action_form.removeRow(0)
        self.message_body_tree.clear()
        row = self.steps_list_widget.currentRow()
        if row == -1 or not current: return
        step_data = self.scenario_data['steps'][row]; action = step_data.get('action')
        action_combo = QComboBox(); action_combo.addItems(["send", "expect", "if", "loop", "delay", "call", "log"])
        action_combo.blockSignals(True); action_combo.setCurrentText(action); action_combo.blockSignals(False)
        action_combo.currentTextChanged.connect(lambda text, r=row, k='action': self.update_step_data(r, k, text)); self.step_action_form.addRow("Action:", action_combo)
        if action in ['send', 'expect']:
            msg_name = step_data.get('message'); msg_combo = QComboBox(); msg_combo.addItems(self.factory.message_names)
            msg_combo.blockSignals(True); msg_combo.setCurrentText(msg_name); msg_combo.blockSignals(False)
            msg_combo.currentTextChanged.connect(lambda text, r=row, k='message': self.update_step_data(r, k, text)); self.step_action_form.addRow("Message:", msg_combo)
            if msg_name in self.factory.library:
                msg_spec = self.factory.library[msg_name]; body_def = msg_spec.get('body_definition', [])
                self.build_body_tree(self.message_body_tree, body_def)
    
    def build_body_tree(self, parent_widget, item_definitions):
        for item_def in item_definitions:
            tree_item = QTreeWidgetItem()
            tree_item.setText(0, item_def.get('name', '')); tree_item.setText(1, item_def.get('format', ''))
            if isinstance(parent_widget, QTreeWidget): parent_widget.addTopLevelItem(tree_item)
            else: parent_widget.addChild(tree_item)
            item_format = item_def.get('format')
            if item_format == 'L': self.build_body_tree(tree_item, item_def.get('value', []))
            else:
                value = item_def.get('value', ''); editor = QLineEdit(str(value))
                self.message_body_tree.setItemWidget(tree_item, 2, editor)
    
    def on_steps_reordered(self):
        new_order_data = [self.steps_list_widget.item(i).data(Qt.UserRole) for i in range(self.steps_list_widget.count())]
        self.scenario_data['steps'] = new_order_data; self.refresh_steps_list(); self.log_message("UI_UPDATE", "Scenario steps reordered.")
    
    def refresh_steps_list(self):
        self.steps_list_widget.model().rowsMoved.disconnect(self.on_steps_reordered); self.steps_list_widget.currentItemChanged.disconnect(self.populate_step_editor)
        self.steps_list_widget.clear()
        for i, step in enumerate(self.scenario_data['steps']):
            action = step.get('action', 'N/A').upper(); details = ""
            if action in ["SEND", "EXPECT"]: details = step.get('message', '')
            item = QListWidgetItem(f"{i+1}: {action} - {details}"); item.setData(Qt.UserRole, step); self.steps_list_widget.addItem(item)
        self.steps_list_widget.model().rowsMoved.connect(self.on_steps_reordered); self.steps_list_widget.currentItemChanged.connect(self.populate_step_editor)
    
    def add_step(self):
        dialog = AddStepDialog(self)
        if dialog.exec():
            action = dialog.get_selected_action(); new_step = {"action": action}
            if action in ["send", "expect"]: new_step["message"] = "S1F13"
            else: new_step.update({"seconds": 1})
            self.scenario_data['steps'].append(new_step); self.refresh_steps_list(); self.steps_list_widget.setCurrentRow(len(self.scenario_data['steps']) - 1)
    
    def remove_step(self):
        if (current_row := self.steps_list_widget.currentRow()) > -1: del self.scenario_data['steps'][current_row]; self.refresh_steps_list()
    
    def update_list_item_text(self, row):
        item = self.steps_list_widget.item(row)
        if not item: return
        step = self.scenario_data['steps'][row]; action = step.get('action', 'N/A').upper(); details = ""
        if action in ["SEND", "EXPECT"]: details = step.get('message', '')
        item.setText(f"{row+1}: {action} - {details}")
    
    def start_equipment(self):
        handler = EquipmentHandler(self.factory, self.conn_details); handler.log_signal.connect(self.log_message); handler.start(); self.btn_start_equip.setEnabled(False)
    
    def run_scenario(self):
        if not self.scenario_data['steps']: self.log_message("ERROR", "Scenario has no steps."); return
        self.btn_run_scenario.setEnabled(False); executor = ScenarioExecutor(self.factory, self.scenario_data, self.conn_details)
        executor.log_signal.connect(self.log_message); executor.scenario_finished.connect(self.show_report); executor.start()
    
    def show_report(self, report):
        self.btn_run_scenario.setEnabled(True); dialog = ReportDialog(report, self); dialog.exec()
    
    def filter_logs(self):
        filter_text = self.filter_input.text().lower(); self.log_area.clear()
        visible_logs = [log for log in self.all_logs if filter_text in log.lower()]
        for log_line in visible_logs:
            parts = log_line.split(" | "); level = parts[1] if len(parts) > 1 else "INFO"
            color_map = {"SENT": "#007acc", "RECV": "#2a9d8f", "ERROR": "#e63946", "UI_UPDATE": "#8d99ae", "SCENARIO": "#e9c46a", "INFO": "#577590"}
            color = color_map.get(level, "#333333")
            self.log_area.append(f'<span style="color: {color};">{log_line}</span>')
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())
    
    def save_scenario(self, save_as=False):
        filepath = self.current_scenario_file_path
        if save_as or not filepath: filepath, _ = QFileDialog.getSaveFileName(self, "Save Scenario As...", "", "JSON Files (*.json)")
        if filepath:
            self.current_scenario_file_path = filepath;
            with open(filepath, 'w') as f: json.dump(self.scenario_data, f, indent=2); self.log_message("UI_UPDATE", f"Scenario saved to {filepath}")
    
    def load_scenario_from_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Scenario", "", "JSON Files (*.json)")
        if filepath:
            self.current_scenario_file_path = filepath;
            with open(filepath, 'r') as f: self.scenario_data = json.load(f)
            self.log_message("UI_UPDATE", f"Scenario loaded from {filepath}"); self.refresh_steps_list()
    
    def import_library(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Library", "", "JSON Files (*.json)")
        if filepath:
            new_messages = self.factory.add_from_file(filepath); self.log_message("UI_UPDATE", f"Imported {len(new_messages)} new messages.")
            self.populate_step_editor(self.steps_list_widget.currentItem(), None)
