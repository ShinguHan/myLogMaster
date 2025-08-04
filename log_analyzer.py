import csv
import json
from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QFileDialog, QListWidget
from types import SimpleNamespace

class AnalysisWindow(QWidget):
    def __init__(self, factory):
        super().__init__()
        self.setWindowTitle("SECS/GEM Simulator - Analysis Mode v2.2.0")
        self.factory = factory
        self.parsed_log = []
        self.analysis_scenario = []
        self._setup_ui()

    def _setup_ui(self):
        self.log_display = QTextEdit(); self.log_display.setReadOnly(True)
        self.results_display = QTextEdit(); self.results_display.setReadOnly(True)
        self.scenario_list = QListWidget()
        load_log_btn = QPushButton("Load Log File"); load_log_btn.clicked.connect(self.load_log_file)
        load_scenario_btn = QPushButton("Load Analysis Scenario"); load_scenario_btn.clicked.connect(self.load_analysis_scenario)
        run_analysis_btn = QPushButton("Run Analysis"); run_analysis_btn.clicked.connect(self.run_analysis)
        top_bar = QHBoxLayout(); top_bar.addWidget(load_log_btn); top_bar.addWidget(load_scenario_btn); top_bar.addWidget(run_analysis_btn)
        bottom_layout = QHBoxLayout(); bottom_layout.addWidget(self.scenario_list); bottom_layout.addWidget(self.results_display)
        main_layout = QVBoxLayout(self); main_layout.addLayout(top_bar); main_layout.addWidget(self.log_display); main_layout.addLayout(bottom_layout)

    def load_log_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Log File", "", "Log Files (*.csv *.json)")
        if filepath:
            self.parsed_log = []
            self.log_display.clear()
            
            with open(filepath, 'r') as f:
                if filepath.endswith('.csv'):
                    reader = csv.reader(f)
                    for i, row in enumerate(reader):
                        self.log_display.append(", ".join(row))
                        try:
                            ts = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S'); msg = row[1].strip()
                            self.parsed_log.append({'type': 'secs', 'ts': ts, 'msg': msg, 'line': i})
                        except (ValueError, IndexError): continue
                elif filepath.endswith('.json'):
                    log_data = json.load(f)
                    self.log_display.setText(json.dumps(log_data, indent=2))
                    for i, entry in enumerate(log_data):
                        try:
                            ts = datetime.strptime(entry['timestamp'], '%Y-%m-%d %H:%M:%S')
                            self.parsed_log.append({'type': 'json', 'ts': ts, 'entry': entry, 'line': i})
                        except (ValueError, KeyError): continue
            
            self.results_display.setText(f"Loaded and parsed {len(self.parsed_log)} log entries.")

    def load_analysis_scenario(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Analysis Scenario", "", "JSON Files (*.json)")
        if filepath:
            with open(filepath, 'r') as f: self.analysis_scenario = json.load(f)
            self.scenario_list.clear()
            for i, step in enumerate(self.analysis_scenario): self.scenario_list.addItem(f"{i+1}: {step['action'].upper()}")

    def run_analysis(self):
        self.results_display.clear()
        if not self.parsed_log or not self.analysis_scenario:
            self.results_display.setText("Error: Load a log and a scenario first."); return

        overall_result = "Pass"; results_summary = []
        
        for step in self.analysis_scenario:
            action = step['action']
            # --- Logic for SECS/GEM rules ---
            if action == 'expect_within_time':
                # ... (previous timing logic is unchanged) ...
                pass
            # --- NEW: Logic for JSON rules ---
            elif action == 'verify_json_value':
                event_to_check, condition = step['event'], step['condition']
                found_and_passed = False; found_but_failed = False
                
                json_entries = [log for log in self.parsed_log if log['type'] == 'json']
                for log in json_entries:
                    if log['entry'].get('event') == event_to_check:
                        try:
                            if eval(condition, {"entry": log['entry']}):
                                results_summary.append(f"PASS: Found event '{event_to_check}' and condition '{condition}' was true.")
                                found_and_passed = True
                            else:
                                found_but_failed = True
                        except Exception as e:
                            results_summary.append(f"FAIL: Error evaluating condition for '{event_to_check}': {e}")
                            overall_result = "Fail"; found_but_failed = True
                        break
                
                if found_but_failed: overall_result = "Fail"
                elif not found_and_passed:
                    results_summary.append(f"FAIL: Never found event '{event_to_check}' that met condition.")
                    overall_result = "Fail"

        self.results_display.setText(f"Overall Result: {overall_result}\n\n" + "\n".join(results_summary))