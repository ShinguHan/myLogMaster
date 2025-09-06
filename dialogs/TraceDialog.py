from PySide6.QtWidgets import (QDialog, QVBoxLayout, QPushButton,
                               QLineEdit, QHBoxLayout, QWidget)
from widgets.base_log_viewer import BaseLogViewerWidget

class TraceDialog(QDialog):
    def __init__(self, data, trace_id, highlighting_rules, controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Event Trace for ID: {trace_id}")
        self.setGeometry(200, 200, 1100, 700)
        self.controller = controller

        main_layout = QVBoxLayout(self)

        # 💥 변경점: TraceDialog가 자신의 필터바를 직접 생성
        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter traced logs...")
        save_button = QPushButton("Save View to CSV")
        top_layout.addWidget(self.filter_input)
        top_layout.addWidget(save_button)
        main_layout.addWidget(top_bar)

        # BaseLogViewerWidget 생성
        self.log_viewer = BaseLogViewerWidget(controller, self)
        main_layout.addWidget(self.log_viewer)

        # 데이터 모델 설정 및 필터 연결
        source_model = self.log_viewer.source_model()
        source_model.update_data(data)
        source_model.set_highlighting_rules(highlighting_rules)
        
        self.filter_input.textChanged.connect(self.log_viewer.proxy_model.setFilterFixedString)
        save_button.clicked.connect(self.log_viewer.save_log_file)
        
        # TraceDialog에서는 Trace 메뉴가 필요 없으므로 시그널 연결 안함

