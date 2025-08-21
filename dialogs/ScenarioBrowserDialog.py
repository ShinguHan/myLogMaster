import os
import json
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QCheckBox, QWidget, 
                               QPushButton, QMessageBox, QSplitter, QLabel,
                               QTextEdit)
from PySide6.QtCore import Qt
from PySide6.QtWebEngineWidgets import QWebEngineView

SCENARIOS_DIR = 'scenarios'

class ScenarioBrowserDialog(QDialog):
    def __init__(self, scenarios_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scenario Browser")
        self.scenarios_data = scenarios_data
        
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        self.setMinimumSize(900, 600)

        main_layout = QVBoxLayout(self)
        
        # ✅ 1. 화면을 좌우로 나누는 Splitter 추가
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- 왼쪽: 시나리오 리스트 ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("<b>Available Scenarios</b>"))
        self.table_widget = QTableWidget()

        # ✅ 아래의 setStyleSheet 코드로 기존 코드를 교체하거나 수정해주세요.
        self.table_widget.setStyleSheet("""
            QTableWidget {
                alternate-background-color: #f5f5f5; /* 옅은 회색으로 행 구분 */
                gridline-color: #e0e0e0;
            }
            QTableWidget::item:hover {
                background-color: #e8f4ff; /* 1. 마우스 호버 시 연한 파란색 */
            }
            QTableWidget::item:selected {
                background-color: #a8cce9;
                color: black;
            }
            QCheckBox::indicator {
                border: 1px solid #888;
                width: 13px;
                height: 13px;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #007aff; /* 2. 체크 시 파란색으로 채움 */
                border: 1px solid #005fbf;
            }
        """)

        self.table_widget.setColumnCount(3)
        self.table_widget.setHorizontalHeaderLabels(["Use", "Scenario Name", "Description"])
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.selectionModel().selectionChanged.connect(self.on_scenario_selected)
        left_layout.addWidget(self.table_widget)
        
        # --- 오른쪽: 선택된 시나리오 상세 뷰 ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("<b>Scenario Details & Flow</b>"))
        self.mermaid_view = QWebEngineView() # Mermaid Diagram을 보여줄 웹 뷰
        right_layout.addWidget(self.mermaid_view)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 600])
        main_layout.addWidget(splitter)
        
        # --- 하단 버튼 ---
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save Changes")
        save_button.clicked.connect(self.save_changes)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(close_button)
        main_layout.addLayout(button_layout)

        self.populate_table()

    def populate_table(self):
        self.table_widget.setRowCount(len(self.scenarios_data))
        
        for row, (name, details) in enumerate(self.scenarios_data.items()):
            # ✅ 2. Enable/Disable 체크박스 (항상 보이도록 수정)
            checkbox = QCheckBox()
            checkbox.setStyleSheet("QCheckBox::indicator { border: 1px solid #888; }")
            checkbox.setChecked(details.get("enabled", True))
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_layout.setContentsMargins(0,0,0,0)
            self.table_widget.setCellWidget(row, 0, checkbox_widget)

            self.table_widget.setItem(row, 1, QTableWidgetItem(name))
            self.table_widget.setItem(row, 2, QTableWidgetItem(details.get("description", "")))
        
        if self.table_widget.rowCount() > 0:
            self.table_widget.selectRow(0)

    def on_scenario_selected(self, selected, deselected):
        selected_rows = self.table_widget.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        selected_row = selected_rows[0].row()
        scenario_name = self.table_widget.item(selected_row, 1).text()
        scenario_details = self.scenarios_data.get(scenario_name)
        
        if scenario_details:
            mermaid_code = self.generate_mermaid_code(scenario_name, scenario_details)
            self.display_mermaid(mermaid_code)

    def generate_mermaid_code(self, name, details):
        """시나리오 데이터로부터 Mermaid 시퀀스 다이어그램 코드를 생성합니다."""
        code = "sequenceDiagram\n    participant User as Trigger\n    participant System\n\n"
        
        trigger = details.get("trigger_event", {})
        trigger_desc = f"{trigger.get('column')} {trigger.get('contains', trigger.get('equals', ''))}"
        code += f"    User->>System: 1. Trigger: {trigger_desc}\n"

        for i, step in enumerate(details.get("steps", [])):
            step_desc = f"{step['event_match'].get('column')} {step['event_match'].get('contains', step['event_match'].get('equals', ''))}"
            delay = step.get('max_delay_seconds', 'N/A')
            code += f"    System-->>System: {i+2}. Step: {step['name']} (wait max {delay}s)\n"
            code += f"    note right of System: expect: {step_desc}\n"
        return code

    def display_mermaid(self, mermaid_code):
        """Mermaid 코드를 QWebEngineView에 렌더링합니다."""
        escaped_code = json.dumps(mermaid_code)
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
            <script>mermaid.initialize({{startOnLoad:true, theme: 'neutral'}});</script>
        </head>
        <body>
            <div class="mermaid">
            {mermaid_code}
            </div>
        </body>
        </html>
        """
        self.mermaid_view.setHtml(html)

    def save_changes(self):
        # ... (이전과 동일한 저장 로직)
        for row in range(self.table_widget.rowCount()):
            checkbox = self.table_widget.cellWidget(row, 0).findChild(QCheckBox)
            name = self.table_widget.item(row, 1).text()
            if name in self.scenarios_data: self.scenarios_data[name]['enabled'] = checkbox.isChecked()
        try:
            # TODO: 개별 파일에 나누어 저장하는 로직으로 개선 필요
            file_to_save = os.path.join(SCENARIOS_DIR, "scenarios.json")
            with open(file_to_save, 'w', encoding='utf-8') as f:
                json.dump(self.scenarios_data, f, indent=4)
            QMessageBox.information(self, "Success", "Scenario settings have been saved.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save scenario settings:\n{e}")