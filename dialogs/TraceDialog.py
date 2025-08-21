import pandas as pd
import json
import re
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTableView, QTextEdit, 
                               QSplitter, QMenu, QMessageBox, QPushButton,
                               QLineEdit, QHBoxLayout)
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QAction
from models.LogTableModel import LogTableModel
from dialogs.VisualizationDialog import VisualizationDialog # 시각화 다이얼로그 임포트

class TraceDialog(QDialog):
    def __init__(self, data, trace_id, highlighting_rules, controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Event Trace for ID: {trace_id}")
        self.setGeometry(200, 200, 1100, 700)
        self.controller = controller
        self.trace_data = data # 원본 데이터 저장

        # ✅ 3. 최소화, 최대화 버튼 추가
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)

        layout = QVBoxLayout(self)
        
        # ✅ 4. 필터 및 저장 버튼을 위한 상단 레이아웃 추가
        top_layout = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter traced logs...")
        save_button = QPushButton("Save View to CSV")
        save_button.clicked.connect(self.save_filtered_csv)
        top_layout.addWidget(self.filter_input)
        top_layout.addWidget(save_button)
        layout.addLayout(top_layout)

        # ✅ 2. 상세 보기 창이 오른쪽에 나오도록 Horizontal로 변경
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tableView = QTableView()
        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setFontFamily("Courier New")
        
        self.splitter.addWidget(self.tableView)
        self.splitter.addWidget(self.detail_view)
        self.detail_view.setVisible(False)
        self.splitter.setSizes([1, 0])
        
        layout.addWidget(self.splitter)
        self.setLayout(layout)

        # ✅ 1. 마우스 Hover 효과(Alternating Row Colors) 추가
        self.tableView.setAlternatingRowColors(True)

        self.model = LogTableModel()
        self.model.update_data(self.trace_data)
        self.model.set_highlighting_rules(highlighting_rules)
        
        # 필터링을 위한 Proxy Model 설정
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.tableView.setModel(self.proxy_model)
        self.filter_input.textChanged.connect(self.proxy_model.setFilterFixedString)

        # 컨텍스트 메뉴 설정
        self.tableView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tableView.customContextMenuRequested.connect(self.show_table_context_menu)
        self.tableView.selectionModel().selectionChanged.connect(self.update_detail_view)

    def show_table_context_menu(self, pos):
        menu = QMenu(self)
        selected_indexes = self.tableView.selectedIndexes()

        if selected_indexes:
            source_index = self.proxy_model.mapToSource(selected_indexes[0])
            
            show_detail_action = QAction("상세 로그 보기", self)
            show_detail_action.triggered.connect(self.show_detail_pane)
            menu.addAction(show_detail_action)

            # ✅ 5. Visualize SECS 기능 추가
            tracking_id = self.model.get_data_by_col_name(source_index.row(), "TrackingID")
            if tracking_id and str(tracking_id).strip():
                menu.addSeparator()
                visualize_action = QAction(f"Visualize SECS Scenario for '{tracking_id}'", self)
                visualize_action.triggered.connect(lambda: self.visualize_secs_scenario(str(tracking_id)))
                menu.addAction(visualize_action)

        if self.detail_view.isVisible():
            if menu.actions() and not menu.actions()[-1].isSeparator(): menu.addSeparator()
            hide_detail_action = QAction("원복", self)
            hide_detail_action.triggered.connect(self.hide_detail_pane)
            menu.addAction(hide_detail_action)
        
        if menu.actions():
            menu.exec(self.tableView.viewport().mapToGlobal(pos))

    # --- (상세보기 관련 메소드들은 이전과 동일) ---
    def _display_log_detail(self, source_index):
        if not self.model: return
        try:
            display_object = self.model.get_data_by_col_name(source_index.row(), "ParsedBodyObject")
            if display_object is None: display_object = self.model.get_data_by_col_name(source_index.row(), "AsciiData")
            if display_object:
                if isinstance(display_object, dict): self.detail_view.setText(json.dumps(display_object, indent=4, ensure_ascii=False))
                else: self.detail_view.setText(str(display_object))
            else: self.detail_view.setText("")
        except Exception as e: self.detail_view.setText(f"상세 정보를 표시하는 중 오류가 발생했습니다:\n{e}")

    def show_detail_pane(self):
        selected_indexes = self.tableView.selectedIndexes();
        if not selected_indexes: return
        source_index = self.proxy_model.mapToSource(selected_indexes[0])
        self._display_log_detail(source_index)
        if not self.detail_view.isVisible(): self.detail_view.setVisible(True); self.splitter.setSizes([self.width() * 0.6, self.width() * 0.4])
    
    def update_detail_view(self):
        if not self.detail_view.isVisible(): return
        selected_indexes = self.tableView.selectedIndexes()
        if not selected_indexes: self.detail_view.clear(); return
        source_index = self.proxy_model.mapToSource(selected_indexes[0])
        self._display_log_detail(source_index)
        
    def hide_detail_pane(self):
        self.detail_view.setVisible(False); self.splitter.setSizes([1, 0])

    # --- (Visualize 및 CSV 저장 기능 추가) ---
    def visualize_secs_scenario(self, trace_id):
        com_logs = self.controller.get_scenario_data(trace_id)
        if com_logs.empty:
            QMessageBox.information(self, "Info", f"No SECS messages (Com logs) found related to ID: {trace_id}")
            return
        mermaid_code = self._generate_mermaid_code(com_logs)
        self.viz_dialog = VisualizationDialog(mermaid_code, self)
        self.viz_dialog.exec()

    def _generate_mermaid_code(self, df):
        code = f"sequenceDiagram\n    participant Host\n    participant Equipment\n\n"
        for _, row in df.iterrows():
            ascii_data = row.get('AsciiData', '')
            parsed_body = row.get('ParsedBody', '')
            direction = "->>" if "<--" in ascii_data else "-->>"
            actor_from, actor_to = ("Host", "Equipment") if direction == "->>" else ("Equipment", "Host")
            msg_content = re.sub(r', loc :.*', '', ascii_data).replace('-->', '').replace('<--', '').strip()
            code += f"    {actor_from}{direction}{actor_to}: {parsed_body}: {msg_content}\n"
        return code

    def save_filtered_csv(self):
        from PySide6.QtWidgets import QFileDialog
        if self.proxy_model.rowCount() == 0:
            QMessageBox.information(self, "Info", "There is no data to save.")
            return
            
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Filtered Log", "trace_export.csv", "CSV Files (*.csv)")
        if filepath:
            visible_rows_indices = [self.proxy_model.mapToSource(self.proxy_model.index(r, 0)).row() for r in range(self.proxy_model.rowCount())]
            df_to_save = self.model._data.iloc[visible_rows_indices]
            success, message = self.controller.save_log_to_csv(df_to_save, filepath)
            if not success:
                QMessageBox.critical(self, "Save Error", message)