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
        right_layout.addWidget(QLabel("<b>Scenario Details & Flow</b>"), stretch=0)
        self.mermaid_view = QWebEngineView() # Mermaid Diagram을 보여줄 웹 뷰
        right_layout.addWidget(self.mermaid_view, stretch=1)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
         # ✅ splitter.setSizes([300, 600]) 대신 아래 코드로 교체
        splitter.setStretchFactor(0, 1) # 왼쪽 패널의 Stretch Factor
        splitter.setStretchFactor(1, 3) # 오른쪽 패널의 Stretch Factor
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

    # shinguhan/mylogmaster/myLogMaster-main/dialogs/ScenarioBrowserDialog.py

    # shinguhan/mylogmaster/myLogMaster-main/dialogs/ScenarioBrowserDialog.py

    def generate_mermaid_code(self, name, details):
        """'branch_on_event'를 포함한 모든 고급 문법을 시각화하는 Mermaid 코드를 생성합니다."""
        code = f"sequenceDiagram\n    participant User as Logs\n    participant System as Analyzer\n\n"
        
        extractors = details.get("context_extractors")
        if extractors:
            # ... (Context 시각화 로직은 이전과 동일)
            extractor_desc = []
            for key, rules in extractors.items():
                rule_descs = []
                for rule in rules:
                    if "from_column" in rule: rule_descs.append(f"column '{rule['from_column']}'")
                    elif "from_regex" in rule: rule_descs.append(f"regex on '{rule['from_regex']['column']}'")
                extractor_desc.append(f"<b>{key}</b> from {' or '.join(rule_descs)}")
            code += f"    note over System: Extracts Context<br/>{'<br/>'.join(extractor_desc)}\n\n"

        trigger = details.get("trigger_event", {})
        trigger_desc = self._format_rule_group(trigger)
        code += f"    User->>System: 1. Trigger If<br/>{trigger_desc}\n"

        for i, step in enumerate(details.get("steps", [])):
            step_name = step.get('name', f'Step {i+2}')
            
            # ✅ --- 분기(Branch) 이벤트 시각화 로직 ---
            if 'branch_on_event' in step:
                branch_rule = step['branch_on_event']
                delay = branch_rule.get('max_delay_seconds')
                delay_text = f" (wait max {delay}s)" if delay else ""

                branch_event_desc = self._format_rule_group(branch_rule.get('event_match', {}))
                code += f"    System-->>System: {i+2}. {step_name}{delay_text}\n"
                code += f"    note right of System: find log where: {branch_event_desc}\n"
                
                # Mermaid의 alt/else 구문을 사용하여 분기 표현
                is_first_case = True
                for case_value, case_steps in branch_rule.get('cases', {}).items():
                    keyword = "alt" if is_first_case else "else"
                    code += f"    {keyword} Case: '{case_value}'\n"
                    # 분기된 하위 steps를 다시 시각화
                    for j, sub_step in enumerate(case_steps):
                        sub_step_name = sub_step.get('name', f'Sub-Step {j+1}')
                        sub_optional = " (Optional)" if sub_step.get('optional', False) else ""
                        sub_delay = sub_step.get('max_delay_seconds')
                        sub_delay_text = f" (wait max {sub_delay}s)" if sub_delay else " (no time limit)"
                        sub_desc = self._format_rule_group(sub_step.get('event_match', {}))
                        
                        code += f"        System-->>System: {sub_step_name}{sub_optional}{sub_delay_text}\n"
                        code += f"        note right of System: expect: {sub_desc}\n"
                    is_first_case = False
                if not is_first_case: # case가 하나라도 있었으면 end 추가
                    code += "    end\n"

            # --- 순서 없는 그룹(Unordered Group) 처리 ---
            elif 'unordered_group' in step:
                # ... (이전과 동일한 로직)
                delay = step.get('max_delay_seconds')
                delay_text = f" (within {delay}s)" if delay else ""
                code += f"\n    par {step_name}{delay_text} [All must occur in any order]\n"
                for sub_step in step.get('unordered_group', []):
                    sub_name = sub_step.get('name')
                    sub_desc = self._format_rule_group(sub_step.get('event_match', {}))
                    code += f"        System-->>System: {sub_name}\n"
                    code += f"        note right of System: expect: {sub_desc}\n"
                code += "    end\n"

            # --- 일반 단계(Ordered Step) 처리 ---
            else:
                # ... (이전과 동일한 로직)
                optional_text = " (Optional)" if step.get('optional', False) else ""
                delay = step.get('max_delay_seconds')
                delay_text = f" (wait max {delay}s)" if delay else " (no time limit)"
                step_desc = self._format_rule_group(step.get('event_match', {}))
                code += f"    System-->>System: {i+2}. {step_name}{optional_text}{delay_text}\n"
                code += f"    note right of System: expect: {step_desc}\n"
                
        return code

    def _format_rule_group(self, group):
        """AND/OR 복합 조건을 Mermaid에서 보기 좋은 텍스트로 변환하는 헬퍼 함수"""
        if not group: return "Any Event"
        
        # 단일 조건 (이전 버전 호환용)
        if "logic" not in group:
            col = group.get('column', '?')
            op = 'contains' if 'contains' in group else 'equals'
            val = group.get(op, '?')
            return f"{col} {op} '{val}'"

        # 복합 조건
        parts = []
        for rule in group.get("rules", []):
            if "logic" in rule:
                parts.append(f"({self._format_rule_group(rule)})")
            else:
                col = rule.get('column', '?')
                op = rule.get('operator', '?')
                val = rule.get('value', '?')
                parts.append(f"{col} {op} '{val}'")
        
        logic = f" {group.get('logic', 'AND')} "
        return logic.join(parts).replace("<", "&lt;").replace(">", "&gt;")

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

    # shinguhan/mylogmaster/myLogMaster-main/dialogs/ScenarioBrowserDialog.py

    def save_changes(self):
        """
        UI의 변경사항을 각 시나리오의 원본 개별 JSON 파일에 나누어 저장합니다.
        """
        # 1. UI의 현재 체크박스 상태를 self.scenarios_data에 먼저 업데이트합니다.
        for row in range(self.table_widget.rowCount()):
            checkbox = self.table_widget.cellWidget(row, 0).findChild(QCheckBox)
            name = self.table_widget.item(row, 1).text()
            if name in self.scenarios_data:
                self.scenarios_data[name]['enabled'] = checkbox.isChecked()

        # 2. 시나리오들을 원본 파일 이름별로 다시 그룹화합니다.
        files_to_update = {}
        for name, details in self.scenarios_data.items():
            source_file = details.get('_source_file')
            if not source_file:
                print(f"Warning: Source file not found for scenario '{name}'. Skipping.")
                continue

            if source_file not in files_to_update:
                files_to_update[source_file] = {}
            
            # 파일에 저장할 때는 임시 꼬리표(_source_file)를 제거합니다.
            clean_details = details.copy()
            del clean_details['_source_file']
            files_to_update[source_file][name] = clean_details

        # 3. 그룹화된 데이터를 각 파일에 덮어씁니다.
        try:
            for filename, content in files_to_update.items():
                filepath = os.path.join(SCENARIOS_DIR, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(content, f, indent=4,ensure_ascii=False)
            
            QMessageBox.information(self, "Success", "Scenario settings have been saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save scenario settings:\n{e}")