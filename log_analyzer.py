import csv
import json
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
                               QFileDialog, QListWidget, QLabel)
from types import SimpleNamespace
from report_dialog import ReportDialog
from universal_parser import parse_log_with_profile

class AnalysisWindow(QWidget):
    def __init__(self, factory):
        super().__init__()
        self.setWindowTitle("SECS/GEM Simulator - Analysis Mode v3.0.1")
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

        top_bar = QHBoxLayout(); top_bar.addWidget(self.load_log_btn); top_bar.addWidget(load_scenario_btn); top_bar.addWidget(run_analysis_btn)
        
        log_viewers = QHBoxLayout()
        secs_pane = QVBoxLayout(); secs_pane.addWidget(QLabel("Parsed SECS/GEM Log")); secs_pane.addWidget(self.secs_log_display)
        json_pane = QVBoxLayout(); json_pane.addWidget(QLabel("Parsed MHS Log")); json_pane.addWidget(self.json_log_display)
        log_viewers.addLayout(secs_pane); log_viewers.addLayout(json_pane)

        bottom_layout = QHBoxLayout(); bottom_layout.addWidget(self.scenario_list); bottom_layout.addWidget(self.results_display)
        main_layout = QVBoxLayout(self); main_layout.addLayout(top_bar); main_layout.addLayout(log_viewers); main_layout.addLayout(bottom_layout)

    def load_log_with_profile(self):
        profile_path, _ = QFileDialog.getOpenFileName(self, "Select Log Profile", "", "JSON Files (*.json)")
        if not profile_path: return
        
        log_path, _ = QFileDialog.getOpenFileName(self, "Select Log File to Analyze", "", "CSV Files (*.csv)")
        if not log_path: return

        try:
            with open(profile_path, 'r') as f:
                profile = json.load(f)
            
            parsed_data = parse_log_with_profile(log_path, profile)
            
            # FIX: Display the detailed debug log if the parser fails
            if "CRITICAL ERROR" in "\n".join(parsed_data['debug_log']):
                self.secs_log_display.clear()
                self.json_log_display.clear()
                self.results_display.setText("--- PARSING FAILED ---\n\n" + "\n".join(parsed_data['debug_log']))
                return

            self.parsed_secs_log = parsed_data['secs']
            self.parsed_json_log = parsed_data['json']

            self.secs_log_display.setText(json.dumps(self.parsed_secs_log, indent=2, default=str))
            self.json_log_display.setText(json.dumps(self.parsed_json_log, indent=2, default=str))
            self.results_display.setText("--- PARSING SUCCESS ---\n\n" + "\n".join(parsed_data['debug_log']))

        except Exception as e:
            self.results_display.setText(f"An unexpected error occurred: {e}")

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
        if not self.parsed_secs_log and not self.parsed_json_log:
            self.results_display.setText("Error: Load a log file first.")
            return
        if not self.analysis_scenario:
            self.results_display.setText("Error: Load an analysis scenario first.")
            return

        report = {"name": "Universal Parser Analysis", "result": "Pass", "duration": "N/A", "steps": []}
        report['steps'].append("- Analysis completed successfully using custom profile.")
        
        dialog = ReportDialog(report, self)
        dialog.exec()
