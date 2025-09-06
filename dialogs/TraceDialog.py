import pandas as pd
import json
import re
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QPushButton,
                               QLineEdit, QHBoxLayout, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from models.LogTableModel import LogTableModel
# BaseLogViewerWidget을 임포트하여 UI의 기반으로 사용합니다.
from widgets.base_log_viewer import BaseLogViewerWidget

class TraceDialog(QDialog):
    def __init__(self, data, trace_id, highlighting_rules, controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Event Trace for ID: {trace_id}")
        self.setGeometry(200, 200, 1100, 700)
        self.controller = controller

        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)

        main_layout = QVBoxLayout(self)
        
        # 필터 및 저장 버튼을 위한 상단 레이아웃 추가
        top_layout = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter traced logs...")
        save_button = QPushButton("Save View to CSV")
        save_button.clicked.connect(self.save_filtered_csv)
        top_layout.addWidget(self.filter_input)
        top_layout.addWidget(save_button)
        main_layout.addLayout(top_layout)

        # 💥💥💥 수정된 부분 💥💥💥
        # 1. 이 다이얼로그 전용 LogTableModel을 생성합니다.
        self.model = LogTableModel()
        self.model.update_data(data)
        self.model.set_highlighting_rules(highlighting_rules)

        # 2. BaseLogViewerWidget을 생성할 때, 위에서 만든 전용 모델을 `model=` 인자로 전달합니다.
        #    이렇게 하면 BaseLogViewerWidget이 MainWindow의 데이터가 아닌, 
        #    이 TraceDialog만의 데이터를 사용하게 됩니다.
        self.log_viewer = BaseLogViewerWidget(self.controller, model=self.model, parent=self)
        
        # 3. BaseLogViewerWidget의 필터 기능에 연결합니다.
        self.filter_input.textChanged.connect(self.log_viewer.proxy_model.setFilterFixedString)
        
        main_layout.addWidget(self.log_viewer)
        self.setLayout(main_layout)

    def save_filtered_csv(self):
        """현재 필터링된 뷰의 데이터를 CSV 파일로 저장합니다."""
        from PySide6.QtWidgets import QFileDialog
        
        # 프록시 모델을 통해 현재 보이는 행의 개수를 확인합니다.
        if self.log_viewer.proxy_model.rowCount() == 0:
            QMessageBox.information(self, "Info", "There is no data to save.")
            return
            
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Filtered Log", "trace_export.csv", "CSV Files (*.csv)")
        if filepath:
            # 현재 proxy model에 보이는 데이터만 DataFrame으로 재구성
            visible_rows_indices = [self.log_viewer.proxy_model.mapToSource(self.log_viewer.proxy_model.index(r, 0)).row() 
                                    for r in range(self.log_viewer.proxy_model.rowCount())]
            
            # 원본 데이터(self.model)에서 보이는 행들만 선택
            df_to_save = self.model._data.iloc[visible_rows_indices]

            # 컨트롤러에 저장 요청
            success, message = self.controller.save_log_to_csv(df_to_save, filepath)
            if not success:
                QMessageBox.critical(self, "Save Error", message)

