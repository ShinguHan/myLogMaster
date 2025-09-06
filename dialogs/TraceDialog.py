from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout, QMessageBox
from PySide6.QtCore import Qt

from models.LogTableModel import LogTableModel
from widgets.base_log_viewer import BaseLogViewerWidget # 템플릿 위젯 import

class TraceDialog(QDialog):
    def __init__(self, data, trace_id, highlighting_rules, controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Event Trace for ID: {trace_id}")
        self.setGeometry(200, 200, 1100, 700)
        self.controller = controller
        
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)

        layout = QVBoxLayout(self)
        
        # --- 상단 버튼 및 필터 ---
        top_layout = QHBoxLayout()
        # BaseLogViewerWidget이 필터 입력창을 가지고 있으므로, 여기서는 버튼만 추가
        save_button = QPushButton("Save View to CSV")
        save_button.clicked.connect(self.save_filtered_csv)
        top_layout.addStretch() # 버튼을 오른쪽으로
        top_layout.addWidget(save_button)
        layout.addLayout(top_layout)

        # --- BaseLogViewerWidget 추가 ---
        self.log_viewer = BaseLogViewerWidget(self.controller, self)
        layout.addWidget(self.log_viewer)

        self.setLayout(layout)

        # 모델 생성 및 데이터 설정
        self.model = LogTableModel()
        self.model.update_data(data)
        self.model.set_highlighting_rules(highlighting_rules)
        
        # BaseLogViewer에 모델 설정
        self.log_viewer.set_model(self.model)

        # 시그널 연결 (TraceDialog에서는 Trace를 또 호출할 필요 없으므로 시그널 무시)
        # self.log_viewer.trace_requested.connect(...) # 이 부분은 연결하지 않음

    def save_filtered_csv(self):
        """현재 필터링된 뷰의 데이터를 CSV로 저장합니다."""
        proxy_model = self.log_viewer.proxy_model
        if proxy_model.rowCount() == 0:
            QMessageBox.information(self, "Info", "There is no data to save.")
            return
        
        from PySide6.QtWidgets import QFileDialog
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Filtered Log", "trace_export.csv", "CSV Files (*.csv)")
        
        if filepath:
            visible_rows_indices = [proxy_model.mapToSource(proxy_model.index(r, 0)).row() for r in range(proxy_model.rowCount())]
            df_to_save = self.model._data.iloc[visible_rows_indices]
            success, message = self.controller.save_log_to_csv(df_to_save, filepath)
            if not success:
                QMessageBox.critical(self, "Save Error", message)
