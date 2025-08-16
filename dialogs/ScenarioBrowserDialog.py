import json
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QListWidget, QListWidgetItem, QLabel
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt

class ScenarioBrowserDialog(QDialog):
    # ⭐️ 생성자가 파일 대신 scenarios 딕셔너리를 직접 받도록 변경
    def __init__(self, scenarios_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scenario Browser")
        self.setGeometry(200, 200, 900, 600)
        
        self.scenarios = scenarios_data # 전달받은 데이터 사용
        
        try:
            with open('scenarios.json', 'r', encoding='utf-8') as f:
                self.scenarios = json.load(f)
        except Exception as e:
            self.scenarios = {"Error": {"description": f"Could not load scenarios.json:\n{e}", "steps": []}}

        main_layout = QHBoxLayout(self)
        self.list_widget = QListWidget()
        self.web_view = QWebEngineView()
        
        main_layout.addWidget(self.list_widget, 1)
        main_layout.addWidget(self.web_view, 2)

        self.list_widget.currentItemChanged.connect(self.display_scenario)
        self.populate_list()

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def populate_list(self):
        """왼쪽 목록에 정의된 시나리오들을 채웁니다."""
        for name, data in self.scenarios.items():
            item_text = f"{name}\n- {data.get('description', 'No description')}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, name) # 시나리오 이름을 데이터로 저장
            self.list_widget.addItem(item)

    def display_scenario(self, current_item, previous_item):
        """선택된 시나리오의 기대 흐름을 다이어그램으로 표시합니다."""
        if not current_item:
            self.web_view.setHtml("<html><body>Select a scenario to view its definition.</body></html>")
            return
            
        scenario_name = current_item.data(Qt.ItemDataRole.UserRole)
        scenario_data = self.scenarios.get(scenario_name, {})
        
        mermaid_code = self._generate_mermaid_for_definition(scenario_data)
        
        html_content = f"""
        <!DOCTYPE html>
        <html><body>
            <h3>Expected Sequence for '{scenario_name}'</h3>
            <pre class="mermaid">{mermaid_code}</pre>
            <script type="module">
                import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
            </script>
        </body></html>
        """
        self.web_view.setHtml(html_content)

    def _generate_mermaid_for_definition(self, scenario_def):
        """하나의 시나리오 정의로부터 기대 흐름 Mermaid 코드를 생성합니다."""
        code = "sequenceDiagram\n    participant Host\n    participant Equipment\n\n"
        trigger = scenario_def.get('trigger_event', {})
        
        if trigger:
             code += f"    Note over Host,Equipment: Trigger: {trigger.get('column')} {list(trigger.keys())[1]} '{list(trigger.values())[1]}'\n\n"

        for step in scenario_def.get('steps', []):
            step_name = step.get('name', 'Unknown Step')
            match_rule = step.get('event_match', {})
            timeout = step.get('max_delay_seconds', 'N/A')
            
            actor = "Equipment" if "S" in match_rule.get('equals', '') else "Host"
            
            code += f"    {actor}->>Host: {step_name}\n"
            code += f"    Note right of Host: Expects '{match_rule.get('column')}' to be '{match_rule.get('equals')}'<br/>Timeout: {timeout}s\n"
        
        return code