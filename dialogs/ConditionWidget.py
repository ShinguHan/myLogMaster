from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QLineEdit, QPushButton, QStackedWidget,
    QDateTimeEdit
)
from PySide6.QtCore import Signal, QDateTime

class ConditionWidget(QWidget):
    remove_clicked = Signal(QWidget)

    def __init__(self, column_names, date_columns, parent=None):
        super().__init__(parent)
        
        self.date_columns = date_columns
        # ⭐️ 변수 이름을 self.layout에서 self._layout으로 변경
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # 1. 컬럼 선택 콤보박스
        self.column_combo = QComboBox()
        self.column_combo.addItems(column_names)
        self._layout.addWidget(self.column_combo)

        # 2. 연산자 선택 콤보박스
        self.operator_combo = QComboBox()
        self._layout.addWidget(self.operator_combo)

        # 3. 값 입력을 위한 QStackedWidget
        self.value_stack = QStackedWidget()
        self._setup_value_widgets()
        self._layout.addWidget(self.value_stack)

        # 4. 삭제 버튼
        self.remove_button = QPushButton("-")
        self.remove_button.setFixedSize(30, 30)
        self.remove_button.clicked.connect(lambda: self.remove_clicked.emit(self))
        self._layout.addWidget(self.remove_button)
        
        # 시그널 연결
        self.column_combo.currentTextChanged.connect(self._on_column_changed)
        self.operator_combo.currentTextChanged.connect(self._on_operator_changed)
        
        # 초기 상태 설정
        self._on_column_changed(self.column_combo.currentText())

    def _setup_value_widgets(self):
        """값 입력을 위한 위젯들을 미리 만들어 Stacked Widget에 추가합니다."""
        # Index 0: 텍스트 입력용
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Enter value or pattern...")
        self.value_stack.addWidget(self.text_input)

        # Index 1: 날짜/시간 입력용 (1개)
        self.date_input = QDateTimeEdit(QDateTime.currentDateTime())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.value_stack.addWidget(self.date_input)

        # Index 2: 날짜/시간 범위 입력용 (2개)
        self.date_range_widget = QWidget()
        range_layout = QHBoxLayout(self.date_range_widget)
        range_layout.setContentsMargins(0,0,0,0)
        self.date_from = QDateTimeEdit(QDateTime.currentDateTime().addDays(-1))
        self.date_to = QDateTimeEdit(QDateTime.currentDateTime())
        self.date_from.setCalendarPopup(True)
        self.date_to.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.date_to.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        range_layout.addWidget(self.date_from)
        range_layout.addWidget(self.date_to)
        self.value_stack.addWidget(self.date_range_widget)

    def _on_column_changed(self, column_name):
        """컬럼 선택이 변경되면 연산자 목록을 업데이트합니다."""
        self.operator_combo.clear()
        if column_name in self.date_columns:
            operators = ["is after", "is before", "is between"]
            self.operator_combo.addItems(operators)
        else:
            operators = ["Contains", "Does Not Contain", "Equals", "Not Equals", "Matches Regex"]
            self.operator_combo.addItems(operators)
            
    def _on_operator_changed(self, operator):
        """연산자 선택이 변경되면 값 입력 위젯을 전환합니다."""
        if operator in ["is after", "is before"]:
            self.value_stack.setCurrentIndex(1)
        elif operator == "is between":
            self.value_stack.setCurrentIndex(2)
        else: # Text operators
            self.value_stack.setCurrentIndex(0)

    def get_condition(self):
        """현재 위젯의 조건 상태를 딕셔너리로 반환합니다."""
        column = self.column_combo.currentText()
        operator = self.operator_combo.currentText()
        
        current_widget_index = self.value_stack.currentIndex()
        value = ""
        if current_widget_index == 0: # Text
            value = self.text_input.text()
        elif current_widget_index == 1: # Single Date
            value = self.date_input.dateTime()
        elif current_widget_index == 2: # Date Range
            value = (self.date_from.dateTime(), self.date_to.dateTime())
        
        return {"column": column, "operator": operator, "value": value}