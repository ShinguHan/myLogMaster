import json
import re
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableView, QTextEdit, 
                               QSplitter, QMenu, QMessageBox)
from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel
from PySide6.QtGui import QAction
from models.LogTableModel import LogTableModel

class BaseLogViewerWidget(QWidget):
    trace_requested = Signal(str)

    def __init__(self, controller, model=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        # 💥💥💥 수정된 부분 💥💥💥
        # model이 직접 제공되면 그것을 사용하고, 아니면 컨트롤러의 기본 모델을 사용합니다.
        if model:
            self.log_table_model = model
        else:
            self.log_table_model = self.controller.source_model
        
        self.proxy_model = QSortFilterProxyModel()
        # 프록시 모델의 소스를 self.log_table_model로 설정합니다.
        self.proxy_model.setSourceModel(self.log_table_model)
        
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tableView = QTableView()
        self.tableView.setAlternatingRowColors(True)
        self.tableView.setModel(self.proxy_model)
        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setFontFamily("Courier New")
        
        self.splitter.addWidget(self.tableView)
        self.splitter.addWidget(self.detail_view)
        self.detail_view.setVisible(False)
        self.splitter.setSizes([1, 0])
        
        main_layout.addWidget(self.splitter)
        
        self.tableView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tableView.customContextMenuRequested.connect(self.show_table_context_menu)
        self.tableView.selectionModel().selectionChanged.connect(self.update_detail_view)

    def set_filter_key_column(self, column_index):
        self.proxy_model.setFilterKeyColumn(column_index)

    def set_filter_fixed_string(self, pattern):
        self.proxy_model.setFilterFixedString(pattern)

    def show_table_context_menu(self, pos):
        # ... (이전과 동일)
        menu = QMenu(self)
        selected_indexes = self.tableView.selectedIndexes()

        if selected_indexes:
            source_index = self.proxy_model.mapToSource(selected_indexes[0])
            
            show_detail_action = QAction("상세 로그 보기", self)
            show_detail_action.triggered.connect(self.show_detail_pane)
            menu.addAction(show_detail_action)

            tracking_id = self.log_table_model.get_data_by_col_name(source_index.row(), "TrackingID")
            if tracking_id and str(tracking_id).strip():
                menu.addSeparator()
                trace_action = QAction(f"Trace Event Flow: '{tracking_id}'", self)
                trace_action.triggered.connect(lambda: self.trace_requested.emit(str(tracking_id)))
                menu.addAction(trace_action)
                
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

    # 💥💥💥 수정된 부분 💥💥💥
    def _display_log_detail(self, source_index):
        """선택된 로그의 상세 정보를 포맷에 맞게 detail_view에 표시합니다."""
        if not self.log_table_model: return
        
        try:
            display_object = self.log_table_model.get_data_by_col_name(source_index.row(), "ParsedBodyObject")
            # ParsedBodyObject가 없으면 AsciiData를 표시
            if display_object is None:
                display_object = self.log_table_model.get_data_by_col_name(source_index.row(), "AsciiData")

            if display_object:
                # JSON 객체일 경우
                if isinstance(display_object, dict):
                    formatted_text = json.dumps(display_object, indent=4, ensure_ascii=False)
                    self.detail_view.setText(formatted_text)
                # SECS/GEM 메시지 (리스트)일 경우
                elif isinstance(display_object, list):
                    # 재귀적으로 SECS 객체를 포맷팅하는 내부 함수
                    def format_secs_obj(obj, indent=0):
                        lines = []
                        indent_str = "    " * indent
                        for item in obj:
                            # SimpleNamespace 객체인지 확인
                            if hasattr(item, 'type') and hasattr(item, 'value'):
                                if item.type == 'L':
                                    lines.append(f"{indent_str}<L [{len(item.value)}]>")
                                    # 리스트 값에 대해 재귀 호출
                                    lines.extend(format_secs_obj(item.value, indent + 1))
                                else:
                                    lines.append(f"{indent_str}<{item.type} '{item.value}'>")
                        return lines
                    
                    formatted_text = "\n".join(format_secs_obj(display_object))
                    self.detail_view.setText(formatted_text)
                # 그 외 (일반 텍스트)
                else:
                    self.detail_view.setText(str(display_object))
            else:
                self.detail_view.setText("") # 표시할 내용이 없으면 비움

        except Exception as e:
            self.detail_view.setText(f"상세 정보를 표시하는 중 오류가 발생했습니다:\n{e}")
            print(f"Error displaying detail: {e}")


    def show_detail_pane(self):
        # ... (이전과 동일)
        selected_indexes = self.tableView.selectedIndexes();
        if not selected_indexes: return
        source_index = self.proxy_model.mapToSource(selected_indexes[0])
        self._display_log_detail(source_index)
        if not self.detail_view.isVisible():
            self.detail_view.setVisible(True)
            self.splitter.setSizes([self.width() * 0.6, self.width() * 0.4])
    
    def update_detail_view(self):
        # ... (이전과 동일)
        if not self.detail_view.isVisible(): return
        selected_indexes = self.tableView.selectedIndexes()
        if not selected_indexes:
            self.detail_view.clear()
            return
        source_index = self.proxy_model.mapToSource(selected_indexes[0])
        self._display_log_detail(source_index)
        
    def hide_detail_pane(self):
        # ... (이전과 동일)
        self.detail_view.setVisible(False)
        self.splitter.setSizes([1, 0])

    def visualize_secs_scenario(self, trace_id):
        # ... (이전과 동일)
        from dialogs.VisualizationDialog import VisualizationDialog
        com_logs = self.controller.get_scenario_data(trace_id)
        if com_logs.empty:
            QMessageBox.information(self, "Info", f"No SECS messages (Com logs) found related to ID: {trace_id}")
            return
        mermaid_code = self._generate_mermaid_code(com_logs)
        # VisualizationDialog는 독립적으로 동작하므로 self에 저장할 필요 없음
        viz_dialog = VisualizationDialog(mermaid_code, self)
        viz_dialog.exec()

    def _generate_mermaid_code(self, df):
        # ... (이전과 동일)
        code = f"sequenceDiagram\n    participant Host\n    participant Equipment\n\n"
        for _, row in df.iterrows():
            ascii_data = row.get('AsciiData', '')
            parsed_body = row.get('ParsedBody', '')
            direction = "->>" if "<--" in ascii_data else "-->>"
            actor_from, actor_to = ("Host", "Equipment") if direction == "->>" else ("Equipment", "Host")
            msg_content = re.sub(r', loc :.*', '', ascii_data).replace('-->', '').replace('<--', '').strip()
            code += f"    {actor_from}{direction}{actor_to}: {parsed_body}: {msg_content}\n"
        return code



