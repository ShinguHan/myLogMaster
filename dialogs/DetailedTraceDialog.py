# shinguhan/mylogmaster/myLogMaster-main/dialogs/DetailedTraceDialog.py

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QDialogButtonBox
)
from .ui_components import create_section_label

class DetailedTraceDialog(QDialog):
    """
    상세 시나리오 추적을 위한 파라미터를 사용자로부터 입력받는 다이얼로그입니다.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detailed Carrier Trace Parameters")

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(create_section_label("Enter IDs for Detailed Scenario Trace"))

        # 입력을 위한 그리드 레이아웃
        grid_layout = QGridLayout()
        self.carrier_id_input = QLineEdit()
        self.from_device_input = QLineEdit()
        self.to_device_input = QLineEdit()

        grid_layout.addWidget(QLabel("Carrier ID (필수):"), 0, 0)
        grid_layout.addWidget(self.carrier_id_input, 0, 1)
        grid_layout.addWidget(QLabel("From Device ID (선택):"), 1, 0)
        grid_layout.addWidget(self.from_device_input, 1, 1)
        grid_layout.addWidget(QLabel("To Device ID (선택):"), 2, 0)
        grid_layout.addWidget(self.to_device_input, 2, 1)
        
        main_layout.addLayout(grid_layout)

        # OK, Cancel 버튼
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        main_layout.addWidget(self.button_box)

    def get_trace_parameters(self):
        """사용자가 입력한 파라미터를 딕셔너리 형태로 반환합니다."""
        return {
            "carrier_id": self.carrier_id_input.text().strip(),
            "from_device": self.from_device_input.text().strip(),
            "to_device": self.to_device_input.text().strip()
        }
