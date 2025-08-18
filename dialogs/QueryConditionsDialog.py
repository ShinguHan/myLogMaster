import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox, 
    QDateTimeEdit, QLineEdit, QLabel
)
from PySide6.QtCore import QDateTime, Qt

class QueryConditionsDialog(QDialog):
    """
    데이터베이스 조회를 위한 시간 범위 및 필터 조건을 사용자로부터 입력받는 대화상자입니다.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("데이터 조회 조건 설정")
        self.setMinimumWidth(400)

        # --- UI 위젯 생성 ---
        # 시작 시간 편집기: 기본값으로 현재 시간으로부터 1시간 전을 설정
        self.start_time_edit = QDateTimeEdit(self)
        self.start_time_edit.setDateTime(QDateTime.currentDateTime().addSecs(-3600))
        self.start_time_edit.setCalendarPopup(True)
        self.start_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")

        # 종료 시간 편집기: 기본값으로 현재 시간을 설정
        self.end_time_edit = QDateTimeEdit(self)
        self.end_time_edit.setDateTime(QDateTime.currentDateTime())
        self.end_time_edit.setCalendarPopup(True)
        self.end_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")

        # 간단한 필터를 위한 라인 에디터 (예: DeviceID)
        self.device_id_edit = QLineEdit(self)
        self.device_id_edit.setPlaceholderText("예: EQ01 (선택 사항)")

        # OK, Cancel 버튼
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # --- 레이아웃 설정 ---
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        form_layout.addRow(QLabel("<b>조회 기간 설정</b>"))
        form_layout.addRow("시작 시간:", self.start_time_edit)
        form_layout.addRow("종료 시간:", self.end_time_edit)
        
        form_layout.addRow(QLabel("<b>추가 필터 (선택)</b>"))
        form_layout.addRow("Device ID:", self.device_id_edit)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(button_box)

    def get_conditions(self):
        """
        사용자가 입력한 조건들을 딕셔너리 형태로 반환합니다.
        datetime 객체는 JSON 직렬화를 위해 ISO 8601 형식의 문자열로 변환합니다.
        """
        filters = {}
        if self.device_id_edit.text():
            filters['DeviceID'] = self.device_id_edit.text()
        
        return {
            "start_time": self.start_time_edit.dateTime().toString(Qt.DateFormat.ISODateWithMs),
            "end_time": self.end_time_edit.dateTime().toString(Qt.DateFormat.ISODateWithMs),
            "filters": filters,
            "filters_json": json.dumps(filters) # DB 저장을 위한 JSON 문자열
        }

if __name__ == '__main__':
    # 이 파일을 직접 실행하여 대화상자가 어떻게 보이는지 테스트할 수 있습니다.
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = QueryConditionsDialog()
    if dialog.exec():
        conditions = dialog.get_conditions()
        print("조회 조건:")
        print(json.dumps(conditions, indent=4))
