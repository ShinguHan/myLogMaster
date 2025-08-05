import csv
import json
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
                               QFileDialog, QListWidget, QLabel, QDialog, QLineEdit, 
                               QFormLayout, QDialogButtonBox)
from types import SimpleNamespace
from report_dialog import ReportDialog
from test_generator import generate_scenario_from_log
from library_generator import generate_library_from_log, generate_schema_from_json_log # New Import
import database_handler

class DeviceIdDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enter Device ID")
        layout = QFormLayout(self)
        self.device_id_input = QLineEdit("MyDevice")
        layout.addRow("Device ID/Prefix:", self.device_id_input)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    def get_device_id(self):
        return self.device_id_input.text()

class AnalysisWindow(QWidget):
    def __init__(self, factory):
        super().__init__()
        self.setWindowTitle("SECS/GEM Simulator - Analysis Mode v2.7.0")
        self.factory = factory
        self.parsed_secs_log = []
        self.parsed_json_log = []
        self.analysis_scenario = []
        self._setup_ui()

    def _setup_ui(self):
        self.secs_log_display = QTextEdit(); self.secs_log_display.setReadOnly(True)
        self.json_log_display = QTextEdit(); self.json_log_display.setReadOnly(True)
        self.results_display = QTextEdit(); self.results_display.setReadOnly(True)
        self.scenario_list = QListWidget()

        load_secs_btn = QPushButton("Load SECS Log (CSV)"); load_secs_btn.clicked.connect(self.load_secs_log)
        load_json_btn = QPushButton("Load MHS Log (JSON)"); load_json_btn.clicked.connect(self.load_json_log)
        
        self.generate_secs_lib_btn = QPushButton("Generate SECS Library"); self.generate_secs_lib_btn.clicked.connect(self.generate_secs_library)
        self.generate_secs_lib_btn.setEnabled(False)
        self.generate_json_schema_btn = QPushButton("Generate MHS Schema"); self.generate_json_schema_btn.clicked.connect(self.generate_json_schema)
        self.generate_json_schema_btn.setEnabled(False)

        top_bar = QHBoxLayout(); top_bar.addWidget(load_secs_btn); top_bar.addWidget(load_json_btn)
        
        generator_bar = QHBoxLayout(); generator_bar.addWidget(self.generate_secs_lib_btn); generator_bar.addWidget(self.generate_json_schema_btn)

        log_viewers = QHBoxLayout()
        secs_pane = QVBoxLayout(); secs_pane.addWidget(QLabel("SECS/GEM Log (CSV)")); secs_pane.addWidget(self.secs_log_display)
        json_pane = QVBoxLayout(); json_pane.addWidget(QLabel("MHS Log (JSON)")); json_pane.addWidget(self.json_log_display)
        log_viewers.addLayout(secs_pane); log_viewers.addLayout(json_pane)

        main_layout = QVBoxLayout(self); main_layout.addLayout(top_bar); main_layout.addLayout(generator_bar); main_layout.addLayout(log_viewers); main_layout.addWidget(self.results_display)

    def _parse_body_recursive(self, body_io):
        items = []; format_code = body_io.read(1)
        if not format_code: return items
        length_byte = int.from_bytes(body_io.read(1), 'big')
        if format_code == b'\x01': items.append(SimpleNamespace(type='L', value=[item for _ in range(length_byte) for item in self._parse_body_recursive(body_io)]))
        elif format_code == b'\x21': items.append(SimpleNamespace(type='U1', value=int.from_bytes(body_io.read(length_byte), 'big')))
        elif format_code == b'\x41': items.append(SimpleNamespace(type='A', value=body_io.read(length_byte).decode('ascii')))
        return items

    def load_secs_log(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load SECS Log", "", "CSV Files (*.csv)")
        if filepath:
            self.parsed_secs_log = []; self.secs_log_display.clear()
            with open(filepath, 'r', newline='') as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    self.secs_log_display.append(", ".join(row))
                    try:
                        ts = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S'); msg = row[1].strip()
                        raw_body_hex = row[4].strip() if len(row) > 4 else ""
                        body_obj = self._parse_body_recursive(__import__('io').BytesIO(bytes.fromhex(raw_body_hex)))
                        self.parsed_secs_log.append({'ts': ts, 'msg': msg, 'body': body_obj})
                    except (ValueError, IndexError): continue
            self.generate_secs_lib_btn.setEnabled(True)

    def load_json_log(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load MHS Log", "", "JSON Files (*.json)")
        if filepath:
            self.parsed_json_log = []; self.json_log_display.clear()
            with open(filepath, 'r') as f:
                log_data = json.load(f); self.json_log_display.setText(json.dumps(log_data, indent=2))
                for i, entry in enumerate(log_data):
                    try:
                        ts = datetime.strptime(entry['timestamp'], '%Y-%m-%d %H:%M:%S')
                        self.parsed_json_log.append({'ts': ts, 'entry': entry})
                    except (ValueError, KeyError): continue
            self.generate_json_schema_btn.setEnabled(True)

    def generate_secs_library(self):
        dialog = DeviceIdDialog(self)
        if dialog.exec():
            device_id = dialog.get_device_id()
            library_data = generate_library_from_log(self.parsed_secs_log, device_id)
            filepath, _ = QFileDialog.getSaveFileName(self, "Save SECS Library", "", "JSON Files (*.json)")
            if filepath:
                with open(filepath, 'w') as f: json.dump(library_data, f, indent=2)
                self.results_display.setText(f"SECS Library successfully generated and saved to:\n{filepath}")

    def generate_json_schema(self):
        schema_data = generate_schema_from_json_log(self.parsed_json_log)
        filepath, _ = QFileDialog.getSaveFileName(self, "Save MHS Schema", "", "JSON Files (*.json)")
        if filepath:
            with open(filepath, 'w') as f: json.dump(schema_data, f, indent=2)
            self.results_display.setText(f"MHS Schema successfully generated and saved to:\n{filepath}")
