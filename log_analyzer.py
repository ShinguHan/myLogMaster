import csv
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QFileDialog, QListWidget, QFormLayout, QComboBox

class AnalysisWindow(QWidget):
    def __init__(self, factory):
        super().__init__()
        self.setWindowTitle("SECS/GEM Simulator - Analysis Mode")
        self.factory = factory
        self.loaded_log_data = []
        self.analysis_scenario = []

        # --- UI Elements ---
        self.log_display = QTextEdit(); self.log_display.setReadOnly(True)
        self.results_display = QTextEdit(); self.results_display.setReadOnly(True)
        self.scenario_list = QListWidget()

        load_log_btn = QPushButton("Load Log File")
        load_log_btn.clicked.connect(self.load_log_file)

        run_analysis_btn = QPushButton("Run Analysis")
        run_analysis_btn.clicked.connect(self.run_analysis)

        # --- Layouts ---
        top_bar = QHBoxLayout()
        top_bar.addWidget(load_log_btn)
        top_bar.addWidget(run_analysis_btn)

        # For this MVP, we'll manually add a rule
        self.analysis_scenario.append({"action": "expect", "message": "S1F14"})
        self.scenario_list.addItem("1: EXPECT - S1F14")

        left_pane = QVBoxLayout()
        left_pane.addWidget(self.scenario_list)

        right_pane = QVBoxLayout()
        right_pane.addWidget(self.results_display)

        main_layout = QVBoxLayout(self)
        main_layout.addLayout(top_bar)
        main_layout.addLayout(left_pane)
        main_layout.addWidget(self.log_display)
        main_layout.addLayout(right_pane)


    def load_log_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Log File", "", "CSV Files (*.csv)")
        if filepath:
            self.loaded_log_data = []
            self.log_display.clear()
            with open(filepath, 'r', newline='') as f:
                reader = csv.reader(f)
                for row in reader:
                    self.loaded_log_data.append(row)
                    self.log_display.append(", ".join(row))
            print(f"Loaded {len(self.loaded_log_data)} lines from {filepath}")

    def run_analysis(self):
        self.results_display.clear()
        if not self.loaded_log_data or not self.analysis_scenario:
            self.results_display.setText("Error: Load a log and define a scenario first.")
            return

        # Simple analysis logic for the MVP
        log_messages = [row[1].strip() for row in self.loaded_log_data if len(row) > 1] # Assuming message is in the 2nd column
        
        overall_result = "Pass"
        results_summary = []

        for step in self.analysis_scenario:
            if step['action'] == 'expect':
                expected_msg = step['message']
                if expected_msg in log_messages:
                    results_summary.append(f"Check PASSED: Found expected message '{expected_msg}'.")
                else:
                    results_summary.append(f"Check FAILED: Did not find expected message '{expected_msg}'.")
                    overall_result = "Fail"
        
        self.results_display.setText(f"Overall Result: {overall_result}\n\n" + "\n".join(results_summary))