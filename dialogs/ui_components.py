from PySide6.QtWidgets import QLabel, QFrame, QPushButton
from PySide6.QtCore import Qt

def create_section_label(text):
    """섹션 제목 스타일이 적용된 QLabel을 생성합니다."""
    label = QLabel(f"<b>{text}</b>")
    label.setStyleSheet("font-size: 14px; margin-top: 5px; margin-bottom: 5px;")
    return label

def create_separator():
    """섹션 구분을 위한 수평선을 생성합니다."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line

def create_toggle_button(text, checked=False):
    """선택/비선택 상태를 가지는 토글 버튼을 생성합니다."""
    button = QPushButton(text)
    button.setCheckable(True)
    button.setChecked(checked)
    button.setStyleSheet("""
        QPushButton[checkable=true]:checked {
            background-color: #a8cce9;
            border: 1px solid #007aff;
            font-weight: bold;
        }
    """)
    return button

def create_action_button(text, is_default=False):
    """주요 동작(OK, Save 등)을 위한 스타일이 적용된 QPushButton을 생성합니다."""
    button = QPushButton(text)
    button.setDefault(is_default)
    button.setMinimumHeight(30)
    return button