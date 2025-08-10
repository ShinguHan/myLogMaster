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
                self.generate_scenario_btn.setEnabled(False); self.generate_secs_lib_btn.setEnabled(False); self.generate_mhs_schema_btn.setEnabled(False)
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
            with open(filepath, 'w') as f: json.dump(generated_data, f, indent=2)
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
            with open(filepath, 'r') as f: loaded_data = json.load(f)
            if isinstance(loaded_data, dict) and 'steps' in loaded_data: self.analysis_scenario = loaded_data['steps']
            elif isinstance(loaded_data, list): self.analysis_scenario = loaded_data
            else:
                self.results_display.setText("Error: Invalid scenario file format."); self.analysis_scenario = []; return
            
            self.scenario_list.clear()
            for i, step in enumerate(self.analysis_scenario):
                if isinstance(step, dict) and 'action' in step:
                    # Display more details about the rule
                    action = step['action'].upper()
                    details = step.get('message', step.get('event', ''))
                    self.scenario_list.addItem(f"{i+1}: {action} - {details}")

    def run_analysis(self):
        self.results_display.clear()
        if not self.parsed_secs_log and not self.parsed_json_log:
            self.results_display.setText("Error: Load at least one log file first.")
            return
        if not self.analysis_scenario:
            self.results_display.setText("Error: Load an analysis scenario first.")
            return

        report = {"name": "Log Analysis", "result": "Pass", "duration": "N/A", "steps": []}
        
        # --- Build State-aware SECS Log ---
        stateful_secs_log = []
        current_process_state = "IDLE"
        for entry in self.parsed_secs_log:
            if entry['msg'] == 'S6F11': # Simplified state logic
                current_process_state = "PROCESSING"
            new_entry = entry.copy()
            new_entry['state'] = current_process_state
            stateful_secs_log.append(new_entry)

        # --- Execute Rules ---
        for step in self.analysis_scenario:
            action = step.get('action')
            step_result = "Pass"
            step_details = ""
            
            try:
                if action == 'verify_data':
                    msg_to_check, condition = step['message'], step['condition']
                    found_and_passed = False
                    for entry in self.parsed_secs_log:
                        if entry['msg'] == msg_to_check:
                            if eval(condition, {"body": entry['body']}):
                                found_and_passed = True
                                break
                    if not found_and_passed:
                        step_result = f"Fail: Condition '{condition}' was not met for message '{msg_to_check}'."
                
                elif action == 'correlate':
                    secs_msg, json_event = step['secs_message'], step['json_event']
                    key_path_s, key_path_j = step['key_path_secs'], step['key_path_json']
                    correlation_found = False
                    for secs_entry in stateful_secs_log:
                        if secs_entry['msg'] == secs_msg:
                            secs_key = eval(key_path_s, {"body": secs_entry['body']})
                            for json_entry in self.parsed_json_log:
                                if json_entry['entry'].get('event') == json_event:
                                    json_key = eval(key_path_j, {"entry": json_entry['entry']})
                                    if secs_key == json_key:
                                        correlation_found = True
                                        break
                            if correlation_found: break
                    if not correlation_found:
                        step_result = f"Fail: No correlation found."

            except Exception as e:
                step_result = f"Fail: Error during execution - {e}"

            if step_result != "Pass":
                report['result'] = "Fail"
            
            report['steps'].append(f"- {action.upper()} {step_details}: {step_result}")

        database_handler.save_test_result(report)
        dialog = ReportDialog(report, self)
        dialog.exec()
