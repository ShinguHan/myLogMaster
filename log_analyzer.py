import csv
import json
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
                               QFileDialog, QListWidget, QLabel, QDialog, QLineEdit, 
                               QFormLayout, QDialogButtonBox, QTabWidget)
from PySide6.QtWebEngineWidgets import QWebEngineView
from types import SimpleNamespace
from report_dialog import ReportDialog
from universal_parser import parse_log_with_profile
from test_generator import generate_scenario_from_log
from library_generator import generate_library_from_log, generate_schema_from_json_log
from sequence_diagram_generator import generate_sequence_html
import database_handler
from analysis_engine import AnalysisEngine # New Import
import os

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
        self.parsed_log_data = {} # Unified dictionary for log data
        self.analysis_scenario = []
        self.engine = AnalysisEngine() # Instantiate the new engine
        self._setup_ui()

    def _setup_ui(self):
        self.secs_log_display = QTextEdit(); self.secs_log_display.setReadOnly(True)
        self.json_log_display = QTextEdit(); self.json_log_display.setReadOnly(True)
        self.results_display = QTextEdit(); self.results_display.setReadOnly(True)
        self.scenario_list = QListWidget()
        self.sequence_view = QWebEngineView()
        self.sequence_view.setHtml("<h1>Load a SECS/GEM log to see the sequence diagram.</h1>")
        self.load_log_btn = QPushButton("Load Log with Profile..."); self.load_log_btn.clicked.connect(self.load_log_with_profile)
        load_scenario_btn = QPushButton("Load Analysis Scenario"); load_scenario_btn.clicked.connect(self.load_analysis_scenario)
        run_analysis_btn = QPushButton("Run Analysis"); run_analysis_btn.clicked.connect(self.run_analysis)
        self.generate_scenario_btn = QPushButton("Generate Scenario"); self.generate_scenario_btn.clicked.connect(self.generate_scenario)
        self.generate_secs_lib_btn = QPushButton("Generate SECS Library"); self.generate_secs_lib_btn.clicked.connect(self.generate_secs_library)
        self.generate_mhs_schema_btn = QPushButton("Generate MHS Schema"); self.generate_mhs_schema_btn.clicked.connect(self.generate_mhs_schema)
        self.generate_scenario_btn.setEnabled(False); self.generate_secs_lib_btn.setEnabled(False); self.generate_mhs_schema_btn.setEnabled(False)
        top_bar = QHBoxLayout(); top_bar.addWidget(self.load_log_btn); top_bar.addWidget(load_scenario_btn); top_bar.addWidget(run_analysis_btn)
        generator_bar = QHBoxLayout(); generator_bar.addWidget(self.generate_scenario_btn); generator_bar.addWidget(self.generate_secs_lib_btn); generator_bar.addWidget(self.generate_mhs_schema_btn)
        log_tabs = QTabWidget(); log_viewer_widget = QWidget(); log_viewers_layout = QHBoxLayout(log_viewer_widget)
        secs_pane = QVBoxLayout(); secs_pane.addWidget(QLabel("Parsed SECS/GEM Log")); secs_pane.addWidget(self.secs_log_display)
        json_pane = QVBoxLayout(); json_pane.addWidget(QLabel("Parsed MHS Log")); json_pane.addWidget(self.json_log_display)
        log_viewers_layout.addLayout(secs_pane); log_viewers_layout.addLayout(json_pane); log_tabs.addTab(log_viewer_widget, "Log Viewer")
        log_tabs.addTab(self.sequence_view, "Sequence Diagram")
        bottom_layout = QHBoxLayout(); bottom_layout.addWidget(self.scenario_list); bottom_layout.addWidget(self.results_display)
        main_layout = QVBoxLayout(self); main_layout.addLayout(top_bar); main_layout.addLayout(generator_bar); main_layout.addWidget(log_tabs); main_layout.addLayout(bottom_layout)

    def load_log_with_profile(self):
        profile_path, _ = QFileDialog.getOpenFileName(self, "Select Log Profile", "", "JSON Files (*.json)")
        if not profile_path: return
        log_path, _ = QFileDialog.getOpenFileName(self, "Select Log File to Analyze", "", "CSV Files (*.csv)")
        if not log_path: return
        try:
            with open(profile_path, 'r') as f: profile = json.load(f)
            self.parsed_log_data = parse_log_with_profile(log_path, profile)
            if "CRITICAL ERROR" in "\n".join(self.parsed_log_data['debug_log']):
                self.results_display.setText("--- PARSING FAILED ---\n\n" + "\n".join(self.parsed_log_data['debug_log']))
                return
            self.secs_log_display.setText(json.dumps(self.parsed_log_data.get('secs', []), indent=2, default=str))
            self.json_log_display.setText(json.dumps(self.parsed_log_data.get('json', []), indent=2, default=str))
            self.results_display.setText("--- PARSING SUCCESS ---\n\n" + "\n".join(self.parsed_log_data['debug_log']))
            self.generate_scenario_btn.setEnabled(bool(self.parsed_log_data.get('secs')))
            self.generate_secs_lib_btn.setEnabled(bool(self.parsed_log_data.get('secs')))
            self.generate_mhs_schema_btn.setEnabled(bool(self.parsed_log_data.get('json')))
            self.update_sequence_view()
        except Exception as e:
            self.results_display.setText(f"An unexpected error occurred: {e}")

    def run_analysis(self):
        self.results_display.clear()
        if not self.parsed_log_data or not self.analysis_scenario:
            self.results_display.setText("Error: Load logs and a scenario first.")
            return
        
        # Call the new engine to do the work
        report = self.engine.run(self.parsed_log_data, self.analysis_scenario)
        
        database_handler.save_test_result(report)
        dialog = ReportDialog(report, self)
        dialog.exec()

    # ... (other methods like generate_scenario, load_analysis_scenario, etc. are unchanged) ...
    def update_sequence_view(self):
        if self.parsed_log_data.get('secs'):
            temp_scenario = generate_scenario_from_log(self.parsed_log_data.get('secs'))
            html = generate_sequence_html(temp_scenario)
            self.sequence_view.setHtml(html)
    def generate_scenario(self):
        if not self.parsed_log_data.get('secs'): return
        generated_data = generate_scenario_from_log(self.parsed_log_data.get('secs'))
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Generated Scenario", "", "JSON Files (*.json)")
        if filepath:
            with open(filepath, 'w') as f: json.dump(generated_data, f, indent=2)
            self.results_display.setText(f"Scenario successfully generated and saved to:\n{filepath}")
    def generate_secs_library(self):
        if not self.parsed_log_data.get('secs'): return
        dialog = DeviceIdDialog(self)
        if dialog.exec():
            device_id = dialog.get_device_id()
            library_data = generate_library_from_log(self.parsed_log_data.get('secs'), device_id)
            filepath, _ = QFileDialog.getSaveFileName(self, "Save SECS Library", "", "JSON Files (*.json)")
            if filepath:
                with open(filepath, 'w') as f: json.dump(library_data, f, indent=2)
                self.results_display.setText(f"SECS Library successfully generated and saved to:\n{filepath}")
    def generate_mhs_schema(self):
        if not self.parsed_log_data.get('json'): return
        schema_data = generate_schema_from_json_log(self.parsed_log_data.get('json'))
        filepath, _ = QFileDialog.getSaveFileName(self, "Save MHS Schema", "", "JSON Files (*.json)")
        if filepath:
            with open(filepath, 'w') as f: json.dump(schema_data, f, indent=2)
            self.results_display.setText(f"MHS Schema successfully generated and saved to:\n{filepath}")
    def load_analysis_scenario(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Analysis Scenario", "", "JSON Files (*.json)")
        if filepath:
            try: # <-- 오류 처리를 위한 try 블록 추가
                with open(filepath, 'r') as f:
                    # 파일이 비어있는지 먼저 확인
                    if os.path.getsize(filepath) == 0:
                        self.results_display.setText("Error: Selected scenario file is empty.")
                        self.analysis_scenario = []
                        return
                    loaded_data = json.load(f)
            except json.JSONDecodeError as e: # <-- JSON 디코딩 오류를 구체적으로 처리
                self.results_display.setText(f"Error: Invalid JSON format in {os.path.basename(filepath)}\nDetails: {e}")
                self.analysis_scenario = []
                return
            except Exception as e: # <-- 그 외 예외 처리
                self.results_display.setText(f"An unexpected error occurred: {e}")
                self.analysis_scenario = []
                return

            if isinstance(loaded_data, dict) and 'steps' in loaded_data:
                self.analysis_scenario = loaded_data['steps']
            elif isinstance(loaded_data, list):
                self.analysis_scenario = loaded_data
            else:
                self.results_display.setText("Error: Invalid scenario file format.")
                self.analysis_scenario = []
                return
                
            self.scenario_list.clear()
            for i, step in enumerate(self.analysis_scenario):
                if isinstance(step, dict) and 'action' in step:
                    action = step['action'].upper()
                    details = step.get('message', step.get('event', ''))
                    self.scenario_list.addItem(f"{i+1}: {action} - {details}")
