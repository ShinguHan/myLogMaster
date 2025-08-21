import pandas as pd
import json
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTableView, QTextEdit, 
                               QSplitter, QMenu, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from models.LogTableModel import LogTableModel

class TraceDialog(QDialog):
    def __init__(self, data, trace_id, highlighting_rules, controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Event Trace for ID: {trace_id}")
        self.setGeometry(200, 200, 1000, 600)
        self.controller = controller # ✅ 컨트롤러 참조 저장

        layout = QVBoxLayout(self)
        
        # ✅ 1. 메인창과 동일하게 Splitter와 상세 뷰(detail_view) 추가
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.tableView = QTableView()
        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setFontFamily("Courier New")
        
        self.splitter.addWidget(self.tableView)
        self.splitter.addWidget(self.detail_view)
        self.detail_view.setVisible(False) # 처음엔 숨김
        self.splitter.setSizes([1, 0])
        
        layout.addWidget(self.splitter)
        self.setLayout(layout)

        # ✅ 2. 자체 모델을 생성하고, 전달받은 하이라이트 규칙을 적용
        self.model = LogTableModel()
        self.model.update_data(data)
        self.model.set_highlighting_rules(highlighting_rules)
        self.tableView.setModel(self.model)

        # ✅ 3. 메인창과 동일하게 컨텍스트 메뉴 설정
        self.tableView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tableView.customContextMenuRequested.connect(self.show_table_context_menu)
        self.tableView.selectionModel().selectionChanged.connect(self.update_detail_view)

    # ✅ 4. 메인창의 컨텍스트 메뉴 관련 메소드들을 그대로 가져옴
    def show_table_context_menu(self, pos):
        menu = QMenu(self)
        selected_indexes = self.tableView.selectedIndexes()

        if selected_indexes:
            show_detail_action = QAction("상세 로그 보기", self)
            show_detail_action.triggered.connect(self.show_detail_pane)
            menu.addAction(show_detail_action)

        if self.detail_view.isVisible():
            if menu.actions(): menu.addSeparator()
            hide_detail_action = QAction("원복", self)
            hide_detail_action.triggered.connect(self.hide_detail_pane)
            menu.addAction(hide_detail_action)
        
        if menu.actions():
            menu.exec(self.tableView.viewport().mapToGlobal(pos))

    def _display_log_detail(self, index):
        if not self.model: return
        try:
            display_object = self.model.get_data_by_col_name(index.row(), "ParsedBodyObject")
            if display_object is None:
                 display_object = self.model.get_data_by_col_name(index.row(), "AsciiData")

            if display_object:
                if isinstance(display_object, dict):
                    self.detail_view.setText(json.dumps(display_object, indent=4, ensure_ascii=False))
                else:
                    self.detail_view.setText(str(display_object))
            else:
                self.detail_view.setText("")
        except Exception as e:
            self.detail_view.setText(f"상세 정보를 표시하는 중 오류가 발생했습니다:\n{e}")

    def show_detail_pane(self):
        selected_indexes = self.tableView.selectedIndexes()
        if not selected_indexes: return
        self._display_log_detail(selected_indexes[0])
        if not self.detail_view.isVisible():
            self.detail_view.setVisible(True)
            self.splitter.setSizes([self.height() * 0.6, self.height() * 0.4])

    def update_detail_view(self):
        if not self.detail_view.isVisible(): return
        selected_indexes = self.tableView.selectedIndexes()
        if not selected_indexes:
            self.detail_view.clear()
            return
        self._display_log_detail(selected_indexes[0])
        
    def hide_detail_pane(self):
        self.detail_view.setVisible(False)
        self.splitter.setSizes([1, 0])