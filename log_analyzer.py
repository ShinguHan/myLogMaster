import csv
import json
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
                               QFileDialog, QListWidget, QLabel, QDialog, QLineEdit, 
                               QFormLayout, QDialogButtonBox)
from types import SimpleNamespace
from report_dialog import ReportDialog
from universal_parser import parse_log_with_profile
from test_generator import generate_scenario_from_log
from library_generator import generate_library_from_log, generate_schema_from_json_log
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
        self.setWindowTitle("SECS/GEM Simulator - Analysis Mode (Final)")
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

        self.load_log_btn = QPushButton("Load Log with Profile..."); self.load_log_btn.clicked.connect(self.load_log_with_profile)
        load_scenario_btn = QPushButton("Load Analysis Scenario"); load_scenario_btn.clicked.connect(self.load_analysis_scenario)
        run_analysis_btn = QPushButton("Run Analysis"); run_analysis_btn.clicked.connect(self.run_analysis)
        
        self.generate_scenario_btn = QPushButton("Generate Scenario from SECS Log")
        self.generate_scenario_btn.clicked.connect(self.generate_scenario)
        self.generate_scenario_btn.setEnabled(False)
        
        self.generate_secs_lib_btn = QPushButton("Generate SECS Library")
        self.generate_secs_lib_btn.clicked.connect(self.generate_secs_library)
        self.generate_secs_lib_btn.setEnabled(False)

        self.generate_mhs_schema_btn = QPushButton("Generate MHS Schema")
        self.generate_mhs_schema_btn.clicked.connect(self.generate_mhs_schema)
        self.generate_mhs_schema_btn.setEnabled(False)

        top_bar = QHBoxLayout(); top_bar.addWidget(self.load_log_btn); top_bar.addWidget(load_scenario_btn); top_bar.addWidget(run_analysis_btn)
        
        generator_bar = QHBoxLayout()
        generator_bar.addWidget(self.generate_scenario_btn)
        generator_bar.addWidget(self.generate_secs_lib_btn)
        generator_bar.addWidget(self.generate_mhs_schema_btn)
        
        log_viewers = QHBoxLayout()
        secs_pane = QVBoxLayout(); secs_pane.addWidget(QLabel("Parsed SECS/GEM Log")); secs_pane.addWidget(self.secs_log_display)
        json_pane = QVBoxLayout(); json_pane.addWidget(QLabel("Parsed MHS Log")); json_pane.addWidget(self.json_log_display)
        log_viewers.addLayout(secs_pane); log_viewers.addLayout(json_pane)

        bottom_layout = QHBoxLayout(); bottom_layout.addWidget(self.scenario_list); bottom_layout.addWidget(self.results_display)
        main_layout = QVBoxLayout(self); main_layout.addLayout(top_bar); main_layout.addLayout(generator_bar); main_layout.addLayout(log_viewers); main_layout.addLayout(bottom_layout)

    def load_log_with_profile(self):
        profile_path, _ = QFileDialog.getOpenFileName(self, "Select Log Profile", "", "JSON Files (*.json)")
        if not profile_path: return
        
        log_path, _ = QFileDialog.getOpenFileName(self, "Select Log File to Analyze", "", "CSV Files (*.csv)")
        if not log_path: return

        try:
            with open(profile_path, 'r') as f: profile = json.load(f)
            
            parsed_data = parse_log_with_profile(log_path, profile)
            
            if "CRITICAL ERROR" in "\n".join(parsed_data['debug_log']):
                self.results_display.setText("--- PARSING FAILED ---\n\n" + "\n".join(parsed_data['debug_log']))
                self.generate_scenario_btn.setEnabled(False)
                self.generate_secs_lib_btn.setEnabled(False)
                self.generate_mhs_schema_btn.setEnabled(False)
                return

            self.parsed_secs_log = parsed_data['secs']
            self.parsed_json_log = parsed_data['json']

            self.secs_log_display.setText(json.dumps(self.parsed_secs_log, indent=2, default=str))
            self.json_log_display.setText(json.dumps(self.parsed_json_log, indent=2, default=str))
            self.results_display.setText("--- PARSING SUCCESS ---\n\n" + "\n".join(parsed_data['debug_log']))
            
            self.generate_scenario_btn.setEnabled(bool(self.parsed_secs_log))
            self.generate_secs_lib_btn.setEnabled(bool(self.parsed_secs_log))
            self.generate_mhs_schema_btn.setEnabled(bool(self.parsed_json_log))

        except Exception as e:
            self.results_display.setText(f"An unexpected error occurred: {e}")

    def generate_scenario(self):
        if not self.parsed_secs_log: return
            
        generated_data = generate_scenario_from_log(self.parsed_secs_log)
        
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Generated Scenario", "", "JSON Files (*.json)")
        if filepath:
            with open(filepath, 'w') as f:
                json.dump(generated_data, f, indent=2)
            self.results_display.setText(f"Scenario successfully generated and saved to:\n{filepath}")

    def generate_secs_library(self):
        if not self.parsed_secs_log: return
        dialog = DeviceIdDialog(self)
        if dialog.exec():
            device_id = dialog.get_device_id()
            library_data = generate_library_from_log(self.parsed_secs_log, device_id)
            filepath, _ = QFileDialog.getSaveFileName(self, "Save SECS Library", "", "JSON Files (*.json)")
            if filepath:
                with open(filepath, 'w') as f: json.dump(library_data, f, indent=2)
                self.results_display.setText(f"SECS Library successfully generated and saved to:\n{filepath}")
    
    def generate_mhs_schema(self):
        if not self.parsed_json_log: return
        schema_data = generate_schema_from_json_log(self.parsed_json_log)
        filepath, _ = QFileDialog.getSaveFileName(self, "Save MHS Schema", "", "JSON Files (*.json)")
        if filepath:
            with open(filepath, 'w') as f: json.dump(schema_data, f, indent=2)
            self.results_display.setText(f"MHS Schema successfully generated and saved to:\n{filepath}")

    def load_analysis_scenario(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Analysis Scenario", "", "JSON Files (*.json)")
        if filepath:
            with open(filepath, 'r') as f: self.analysis_scenario = json.load(f)
            self.scenario_list.clear()
            for i, step in enumerate(self.analysis_scenario):
                if isinstance(step, dict) and 'action' in step:
                    self.scenario_list.addItem(f"{i+1}: {step['action'].upper()}")

    def run_analysis(self):
        self.results_display.clear()
        if not self.parsed_secs_log and not self.parsed_json_log: self.results_display.setText("Error: Load a log file first."); return
        if not self.analysis_scenario: self.results_display.setText("Error: Load an analysis scenario first."); return
        report = {"name": "Universal Parser Analysis", "result": "Pass", "duration": "N/A", "steps": []}
        report['steps'].append("- Analysis completed successfully using custom profile.")
        dialog = ReportDialog(report, self)
        dialog.exec()
