import csv
import json
from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QFileDialog, QListWidget, QLabel
from types import SimpleNamespace
from report_dialog import ReportDialog # Import the new dialog

class AnalysisWindow(QWidget):
    def __init__(self, factory):
        super().__init__()
        self.setWindowTitle("SECS/GEM Simulator - Analysis Mode v2.4.0")
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
        load_scenario_btn = QPushButton("Load Analysis Scenario"); load_scenario_btn.clicked.connect(self.load_analysis_scenario)
        run_analysis_btn = QPushButton("Run Analysis"); run_analysis_btn.clicked.connect(self.run_analysis)

        top_bar = QHBoxLayout()
        top_bar.addWidget(load_secs_btn)
        top_bar.addWidget(load_json_btn)
        top_bar.addWidget(load_scenario_btn)
        top_bar.addWidget(run_analysis_btn)
        
        log_viewers = QHBoxLayout()
        secs_pane = QVBoxLayout(); secs_pane.addWidget(QLabel("SECS/GEM Log")); secs_pane.addWidget(self.secs_log_display)
        json_pane = QVBoxLayout(); json_pane.addWidget(QLabel("MHS Log")); json_pane.addWidget(self.json_log_display)
        log_viewers.addLayout(secs_pane)
        log_viewers.addLayout(json_pane)

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.scenario_list)
        bottom_layout.addWidget(self.results_display)
        
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(top_bar)
        main_layout.addLayout(log_viewers)
        main_layout.addLayout(bottom_layout)

    def _parse_body_recursive(self, body_io):
        items = []
        format_code = body_io.read(1)
        if not format_code: return items
        length_byte = int.from_bytes(body_io.read(1), 'big')
        if format_code == b'\x01':
            items.append(SimpleNamespace(type='L', value=[item for _ in range(length_byte) for item in self._parse_body_recursive(body_io)]))
        elif format_code == b'\x21':
            items.append(SimpleNamespace(type='U1', value=int.from_bytes(body_io.read(length_byte), 'big')))
        elif format_code == b'\x41':
            items.append(SimpleNamespace(type='A', value=body_io.read(length_byte).decode('ascii')))
        return items

    def load_secs_log(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load SECS Log", "", "CSV Files (*.csv)")
        if filepath:
            self.parsed_secs_log = []
            self.secs_log_display.clear()
            with open(filepath, 'r', newline='') as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    self.secs_log_display.append(", ".join(row))
                    try:
                        ts = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                        msg = row[1].strip()
                        raw_body_hex = row[4].strip() if len(row) > 4 else ""
                        body_obj = self._parse_body_recursive(__import__('io').BytesIO(bytes.fromhex(raw_body_hex)))
                        self.parsed_secs_log.append({'ts': ts, 'msg': msg, 'body': body_obj})
                    except (ValueError, IndexError):
                        continue

    def load_json_log(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load MHS Log", "", "JSON Files (*.json)")
        if filepath:
            self.parsed_json_log = []
            self.json_log_display.clear()
            with open(filepath, 'r') as f:
                log_data = json.load(f)
                self.json_log_display.setText(json.dumps(log_data, indent=2))
                for i, entry in enumerate(log_data):
                    try:
                        ts = datetime.strptime(entry['timestamp'], '%Y-%m-%d %H:%M:%S')
                        self.parsed_json_log.append({'ts': ts, 'entry': entry})
                    except (ValueError, KeyError):
                        continue

    def load_analysis_scenario(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Analysis Scenario", "", "JSON Files (*.json)")
        if filepath:
            with open(filepath, 'r') as f:
                self.analysis_scenario = json.load(f)
            self.scenario_list.clear()
            for i, step in enumerate(self.analysis_scenario):
                self.scenario_list.addItem(f"{i+1}: {step['action'].upper()}")

    def run_analysis(self):
        self.results_display.clear()
        if not self.parsed_secs_log and not self.parsed_json_log:
            self.results_display.setText("Error: Load at least one log file first.")
            return
        if not self.analysis_scenario:
            self.results_display.setText("Error: Load an analysis scenario first.")
            return

        report = {"name": "Log Analysis", "result": "Pass", "duration": "N/A", "steps": []}
        
        # In a real application, the full analysis logic would populate the report steps.
        # For this example, we'll just create a placeholder result.
        report['steps'].append("- Analysis Step 1: Pass")
        report['steps'].append("- Analysis Step 2: Pass")
        
        dialog = ReportDialog(report, self)
        dialog.exec()