import csv
from datetime import datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QFileDialog, QListWidget

class AnalysisWindow(QWidget):
    def __init__(self, factory):
        super().__init__()
        self.setWindowTitle("SECS/GEM Simulator - Analysis Mode v1.8.0")
        self.factory = factory
        self.loaded_log_data = []
        self.analysis_scenario = []

        # --- UI Elements ---
        self.log_display = QTextEdit(); self.log_display.setReadOnly(True)
        self.results_display = QTextEdit(); self.results_display.setReadOnly(True)
        self.scenario_list = QListWidget()

        load_log_btn = QPushButton("Load Log File"); load_log_btn.clicked.connect(self.load_log_file)
        load_scenario_btn = QPushButton("Load Analysis Scenario"); load_scenario_btn.clicked.connect(self.load_analysis_scenario)
        run_analysis_btn = QPushButton("Run Analysis"); run_analysis_btn.clicked.connect(self.run_analysis)

        # --- Layouts ---
        top_bar = QHBoxLayout(); top_bar.addWidget(load_log_btn); top_bar.addWidget(load_scenario_btn); top_bar.addWidget(run_analysis_btn)
        left_pane = QVBoxLayout(); left_pane.addWidget(self.scenario_list)
        main_layout = QVBoxLayout(self); main_layout.addLayout(top_bar)
        main_layout.addLayout(left_pane); main_layout.addWidget(self.log_display); main_layout.addWidget(self.results_display)

    def load_log_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Log File", "", "CSV Files (*.csv)")
        if filepath:
            self.loaded_log_data = []
            self.log_display.clear()
            with open(filepath, 'r', newline='') as f:
                reader = csv.reader(f)
                for row in reader:
                    self.loaded_log_data.append(row); self.log_display.append(", ".join(row))

    def load_analysis_scenario(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Analysis Scenario", "", "JSON Files (*.json)")
        if filepath:
            import json
            with open(filepath, 'r') as f: self.analysis_scenario = json.load(f)
            self.scenario_list.clear()
            for i, step in enumerate(self.analysis_scenario):
                self.scenario_list.addItem(f"{i+1}: {step['action'].upper()}")

    def run_analysis(self):
        self.results_display.clear()
        if not self.loaded_log_data or not self.analysis_scenario:
            self.results_display.setText("Error: Load a log and a scenario first."); return

        overall_result = "Pass"; results_summary = []
        
        # Parse log with timestamps
        parsed_log = []
        for row in self.loaded_log_data:
            try:
                # Assuming format 'YYYY-MM-DD HH:MM:SS'
                ts = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                msg = row[1].strip()
                parsed_log.append({'ts': ts, 'msg': msg})
            except (ValueError, IndexError):
                continue # Skip malformed rows

        for step in self.analysis_scenario:
            if step['action'] == 'expect_within_time':
                msg_a, msg_b, timeout = step['message_a'], step['message_b'], step['timeout']
                
                found_a_ts = None
                found_b_in_time = False
                for log_entry in parsed_log:
                    if not found_a_ts and log_entry['msg'] == msg_a:
                        found_a_ts = log_entry['ts']
                    
                    if found_a_ts and log_entry['msg'] == msg_b:
                        delta = (log_entry['ts'] - found_a_ts).total_seconds()
                        if 0 < delta <= timeout:
                            results_summary.append(f"PASS: Found '{msg_b}' {delta:.2f}s after '{msg_a}'.")
                            found_b_in_time = True
                            break
                        else:
                            results_summary.append(f"FAIL: Found '{msg_b}' but it was {delta:.2f}s after '{msg_a}' (Timeout: {timeout}s).")
                            overall_result = "Fail"
                            found_b_in_time = True
                            break
                
                if found_a_ts and not found_b_in_time:
                    results_summary.append(f"FAIL: Found '{msg_a}' but never found '{msg_b}' afterwards.")
                    overall_result = "Fail"
                elif not found_a_ts:
                    results_summary.append(f"FAIL: Never found initial message '{msg_a}'.")
                    overall_result = "Fail"

        self.results_display.setText(f"Overall Result: {overall_result}\n\n" + "\n".join(results_summary))