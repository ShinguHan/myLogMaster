from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton,
    QPushButton, QScrollArea, QWidget, QDialogButtonBox
)
from ConditionWidget import ConditionWidget

class QueryBuilderDialog(QDialog):
    def __init__(self, column_names, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Query Builder")
        self.setGeometry(150, 150, 700, 400)
        self.column_names = column_names
        self.condition_widgets = []

        # 메인 레이아웃
        self.main_layout = QVBoxLayout(self)

        # 1. AND/OR 논리 그룹박스
        logic_groupbox = QGroupBox("Match Type")
        logic_layout = QHBoxLayout()
        self.radio_and = QRadioButton("All conditions (AND)")
        self.radio_or = QRadioButton("Any condition (OR)")
        self.radio_and.setChecked(True)
        logic_layout.addWidget(self.radio_and)
        logic_layout.addWidget(self.radio_or)
        logic_groupbox.setLayout(logic_layout)
        self.main_layout.addWidget(logic_groupbox)

        # 2. 조건 위젯들이 추가될 스크롤 영역
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.conditions_layout = QVBoxLayout(self.scroll_content)
        scroll_area.setWidget(self.scroll_content)
        self.main_layout.addWidget(scroll_area)

        # 3. 조건 추가 버튼
        add_condition_button = QPushButton("+ Add Condition")
        add_condition_button.clicked.connect(self.add_condition)
        self.main_layout.addWidget(add_condition_button)

        # 4. 확인/취소 버튼
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(button_box)

        # 시작할 때 기본 조건 하나 추가
        self.add_condition()

    def add_condition(self):
        """새로운 ConditionWidget을 레이아웃에 추가합니다."""
        condition = ConditionWidget(self.column_names)
        condition.remove_clicked.connect(self.remove_condition)
        self.conditions_layout.addWidget(condition)
        self.condition_widgets.append(condition)

    def remove_condition(self, condition_widget):
        """지정된 ConditionWidget을 레이아웃에서 제거합니다."""
        self.conditions_layout.removeWidget(condition_widget)
        self.condition_widgets.remove(condition_widget)
        condition_widget.deleteLater()

    def get_query_data(self):
        """현재 설정된 모든 쿼리 정보를 딕셔너리로 반환합니다."""
        logic = "AND" if self.radio_and.isChecked() else "OR"
        conditions = [w.get_condition() for w in self.condition_widgets if w.get_condition()['value']]
        
        if not conditions:
            return None
            
        return {
            "logic": logic,
            "conditions": conditions
        }