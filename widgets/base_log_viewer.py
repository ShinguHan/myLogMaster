import json
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QSplitter, QTextEdit, QTableView, QMenu, QMessageBox
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, Signal
from PySide6.QtGui import QAction

from dialogs.VisualizationDialog import VisualizationDialog

class BaseLogViewerWidget(QWidget):
    """
    로그 표시를 위한 공통 UI 요소와 기능을 캡슐화한 재사용 가능한 위젯.
    테이블 뷰, 필터링, 상세 보기, 공통 컨텍스트 메뉴 등을 제공합니다.
    """
    # 외부에서 처리해야 할 동작을 위한 시그널 정의
    trace_requested = Signal(str)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """UI 요소들을 생성하고 레이아웃을 설정합니다."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter logs (case-insensitive)...")
        layout.addWidget(self.filter_input)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.tableView = QTableView()
        self.tableView.setSortingEnabled(True)
        self.tableView.setAlternatingRowColors(True)
        self.tableView.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tableView.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.splitter.addWidget(self.tableView)
        
        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setFontFamily("Courier New")
        self.detail_view.setVisible(False)
        self.splitter.addWidget(self.detail_view)
        
        self.splitter.setSizes([1, 0])
        layout.addWidget(self.splitter)
        
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setFilterKeyColumn(-1)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.tableView.setModel(self.proxy_model)

    def _connect_signals(self):
        """위젯 내부의 시그널과 슬롯을 연결합니다."""
        self.filter_input.textChanged.connect(self.proxy_model.setFilterFixedString)
        self.tableView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tableView.customContextMenuRequested.connect(self.show_table_context_menu)
        self.tableView.selectionModel().selectionChanged.connect(self.update_detail_view)

    def set_model(self, source_model):
        """뷰에 표시할 소스 모델을 설정합니다."""
        self.proxy_model.setSourceModel(source_model)
    
    def source_model(self):
        """현재 설정된 원본 모델을 반환합니다."""
        return self.proxy_model.sourceModel()

    def show_table_context_menu(self, pos):
        """테이블 뷰의 우클릭 컨텍스트 메뉴를 표시합니다."""
        selected_indexes = self.tableView.selectedIndexes()
        source_model = self.proxy_model.sourceModel()
        if not selected_indexes or not source_model:
            return

        menu = QMenu(self)
        
        source_index = self.proxy_model.mapToSource(selected_indexes[0])
        
        # 상세 보기/숨기기 액션 추가
        show_detail_action = QAction("상세 로그 보기", self)
        show_detail_action.triggered.connect(self.show_detail_pane)
        menu.addAction(show_detail_action)

        tracking_id = source_model.get_data_by_col_name(source_index.row(), "TrackingID")
        if tracking_id and str(tracking_id).strip():
            menu.addSeparator()
            
            # Trace 및 Visualize 액션 추가 (하위 클래스에서 이벤트를 처리할 수 있도록 시그널 사용)
            trace_action = QAction(f"Trace Event Flow: '{tracking_id}'", self)
            trace_action.triggered.connect(lambda: self.trace_requested.emit(str(tracking_id)))
            menu.addAction(trace_action)
            
            visualize_action = QAction(f"Visualize SECS Scenario for '{tracking_id}'", self)
            visualize_action.triggered.connect(lambda: self.visualize_secs_scenario(str(tracking_id)))
            menu.addAction(visualize_action)

        if self.detail_view.isVisible():
            if menu.actions() and not menu.actions()[-1].isSeparator():
                menu.addSeparator()
            hide_detail_action = QAction("원복", self)
            hide_detail_action.triggered.connect(self.hide_detail_pane)
            menu.addAction(hide_detail_action)
        
        menu.exec_(self.tableView.viewport().mapToGlobal(pos))
        
    def _display_log_detail(self, source_index):
        """선택된 로그의 상세 정보를 detail_view에 표시합니다."""
        source_model = self.proxy_model.sourceModel()
        if not source_model: return
        try:
            display_object = source_model.get_data_by_col_name(source_index.row(), "ParsedBodyObject")
            if display_object is None:
                 display_object = source_model.get_data_by_col_name(source_index.row(), "AsciiData")

            if display_object:
                if isinstance(display_object, dict):
                    formatted_text = json.dumps(display_object, indent=4, ensure_ascii=False)
                    self.detail_view.setText(formatted_text)
                elif isinstance(display_object, list):
                    # SECS 객체 포맷팅 로직
                    def format_secs_obj(obj, indent=0):
                        lines = []
                        indent_str = "    " * indent
                        for item in obj:
                            if hasattr(item, 'type') and hasattr(item, 'value'):
                                if item.type == 'L':
                                    lines.append(f"{indent_str}<L [{len(item.value)}]>")
                                    lines.extend(format_secs_obj(item.value, indent + 1))
                                else:
                                    lines.append(f"{indent_str}<{item.type} '{item.value}'>")
                        return lines
                    formatted_text = "\n".join(format_secs_obj(display_object))
                    self.detail_view.setText(formatted_text)
                else:
                    self.detail_view.setText(str(display_object))
            else:
                self.detail_view.setText("")
        except Exception as e:
            self.detail_view.setText(f"상세 정보를 표시하는 중 오류가 발생했습니다:\n{e}")

    def update_detail_view(self):
        """테이블 선택 변경 시 상세 뷰를 업데이트합니다."""
        if not self.detail_view.isVisible(): return
        selected_indexes = self.tableView.selectedIndexes()
        if not selected_indexes:
            self.detail_view.clear()
            return
        source_index = self.proxy_model.mapToSource(selected_indexes[0])
        self._display_log_detail(source_index)
        
    def show_detail_pane(self):
        """상세 뷰 창을 보여줍니다."""
        selected_indexes = self.tableView.selectedIndexes()
        if not selected_indexes: return
        source_index = self.proxy_model.mapToSource(selected_indexes[0])
        self._display_log_detail(source_index)
        if not self.detail_view.isVisible():
            self.detail_view.setVisible(True)
            self.splitter.setSizes([self.width() * 0.6, self.width() * 0.4])

    def hide_detail_pane(self):
        """상세 뷰 창을 숨깁니다."""
        self.detail_view.setVisible(False)
        self.splitter.setSizes([1, 0])

    def visualize_secs_scenario(self, trace_id):
        """SECS 통신 로그를 시퀀스 다이어그램으로 시각화합니다."""
        com_logs = self.controller.get_scenario_data(trace_id)
        if com_logs.empty:
            QMessageBox.information(self, "Info", f"No SECS messages (Com logs) found related to ID: {trace_id}")
            return
        mermaid_code = self._generate_mermaid_code(com_logs)
        # self를 부모로 전달하여 다이얼로그가 닫힐 때 함께 닫히도록 함
        self.viz_dialog = VisualizationDialog(mermaid_code, self)
        self.viz_dialog.exec()

    def _generate_mermaid_code(self, df):
        """DataFrame으로부터 Mermaid.js 시퀀스 다이어그램 코드를 생성합니다."""
        code = f"sequenceDiagram\n    participant Host\n    participant Equipment\n\n"
        for _, row in df.iterrows():
            ascii_data = row.get('AsciiData', '')
            parsed_body = row.get('ParsedBody', '')
            direction = "->>" if "<--" in ascii_data else "-->>"
            actor_from, actor_to = ("Host", "Equipment") if direction == "->>" else ("Equipment", "Host")
            msg_content = re.sub(r', loc :.*', '', ascii_data).replace('-->', '').replace('<--', '').strip()
            code += f"    {actor_from}{direction}{actor_to}: {parsed_body}: {msg_content}\n"
        return code
