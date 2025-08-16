from PySide6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QLineEdit, QPushButton
from PySide6.QtCore import Signal

class ConditionWidget(QWidget):
    # 이 위젯을 삭제해달라고 부모에게 요청하는 시그널
    remove_clicked = Signal(QWidget)

    def __init__(self, column_names, parent=None):
        super().__init__(parent)
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # 1. 컬럼 선택 콤보박스
        self.column_combo = QComboBox()
        self.column_combo.addItems(column_names)
        self.layout.addWidget(self.column_combo)

        # 2. 연산자 선택 콤보박스
        self.operator_combo = QComboBox()
        operators = ["Contains", "Does Not Contain", "Equals", "Not Equals", "Matches Regex"]
        self.operator_combo.addItems(operators)
        self.layout.addWidget(self.operator_combo)

        # 3. 값 입력 필드
        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("Enter value or pattern...")
        self.layout.addWidget(self.value_input)

        # 4. 삭제 버튼
        self.remove_button = QPushButton("-")
        self.remove_button.setFixedSize(30, 30)
        self.remove_button.clicked.connect(lambda: self.remove_clicked.emit(self))
        self.layout.addWidget(self.remove_button)

    def get_condition(self):
        """현재 위젯의 조건 상태를 딕셔너리로 반환합니다."""
        return {
            "column": self.column_combo.currentText(),
            "operator": self.operator_combo.currentText(),
            "value": self.value_input.text()
        }