import json
import re
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableView,
    QTextEdit,
    QSplitter,
    QMenu,
    QMessageBox,
    QInputDialog,
)
from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel
from PySide6.QtGui import QAction
from models.LogTableModel import LogTableModel


class CustomFilterProxyModel(QSortFilterProxyModel):
    """전체 컬럼에서 검색하는 커스텀 프록시 모델"""
    def __init__(self):
        super().__init__()
        self.filter_text = ""
        self.case_sensitive = False
    
    def set_filter_text(self, text, case_sensitive=False):
        """전체 컬럼에서 검색할 텍스트 설정"""
        self.filter_text = text
        self.case_sensitive = case_sensitive
        self.invalidateFilter()  # 필터 재적용
    
    def filterAcceptsRow(self, source_row, source_parent):
        """각 행이 필터를 통과하는지 확인 - 모든 컬럼에서 검색"""
        if not self.filter_text:
            return True
        
        source_model = self.sourceModel()
        col_count = source_model.columnCount()
        
        # 모든 컬럼을 순회하면서 검색 텍스트 찾기
        for col in range(col_count):
            index = source_model.index(source_row, col)
            data = source_model.data(index, Qt.ItemDataRole.DisplayRole)
            
            if data:
                data_str = str(data)
                if self.case_sensitive:
                    if self.filter_text in data_str:
                        return True
                else:
                    if self.filter_text.lower() in data_str.lower():
                        return True
        
        return False


class BaseLogViewerWidget(QWidget):
    trace_requested = Signal(str, str)  # (trace_id, additional_filter)

    def __init__(self, controller, model=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        # 💥💥💥 수정된 부분 💥💥💥
        # model이 직접 제공되면 그것을 사용하고, 아니면 컨트롤러의 기본 모델을 사용합니다.
        if model:
            self.log_table_model = model
        else:
            self.log_table_model = self.controller.source_model

        # 커스텀 프록시 모델 사용 - 전체 컬럼 검색 지원
        self.proxy_model = CustomFilterProxyModel()
        # 프록시 모델의 소스를 self.log_table_model로 설정합니다.
        self.proxy_model.setSourceModel(self.log_table_model)

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

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
        self.tableView.selectionModel().selectionChanged.connect(
            self.update_detail_view
        )

    def set_filter_key_column(self, column_index):
        # 커스텀 프록시에서는 이 설정이 무시됩니다 (전체 컬럼 검색)
        pass

    def set_filter_fixed_string(self, pattern):
        """전체 컬럼에서 대소문자 무시 검색"""
        self.proxy_model.set_filter_text(pattern, case_sensitive=False)

    def show_table_context_menu(self, pos):
        # ... (이전과 동일)
        menu = QMenu(self)
        selected_indexes = self.tableView.selectedIndexes()

        if selected_indexes:
            source_index = self.proxy_model.mapToSource(selected_indexes[0])

            show_detail_action = QAction("상세 로그 보기", self)
            show_detail_action.triggered.connect(self.show_detail_pane)
            menu.addAction(show_detail_action)

            tracking_id = self.log_table_model.get_data_by_col_name(
                source_index.row(), "TrackingID"
            )
            if tracking_id and str(tracking_id).strip():
                menu.addSeparator()
                trace_action = QAction(f"Trace Event Flow: '{tracking_id}'", self)
                trace_action.triggered.connect(
                    lambda: self.trace_requested.emit(str(tracking_id), None)
                )
                menu.addAction(trace_action)

                trace_with_filter_action = QAction(
                    "Trace with Additional Filter...", self
                )
                trace_with_filter_action.triggered.connect(
                    lambda: self._trace_with_filter(str(tracking_id))
                )
                menu.addAction(trace_with_filter_action)

                menu.addSeparator()

                visualize_action = QAction(
                    f"Visualize SECS Scenario for '{tracking_id}'", self
                )
                visualize_action.triggered.connect(
                    lambda: self.visualize_secs_scenario(str(tracking_id))
                )
                menu.addAction(visualize_action)

                viz_with_filter_action = QAction(
                    "Visualize with Additional Filter...", self
                )
                viz_with_filter_action.triggered.connect(
                    lambda: self._visualize_with_filter(str(tracking_id))
                )
                menu.addAction(viz_with_filter_action)

        if self.detail_view.isVisible():
            if menu.actions() and not menu.actions()[-1].isSeparator():
                menu.addSeparator()
            hide_detail_action = QAction("원복", self)
            hide_detail_action.triggered.connect(self.hide_detail_pane)
            menu.addAction(hide_detail_action)

        if menu.actions():
            menu.exec(self.tableView.viewport().mapToGlobal(pos))

    # 💥💥💥 수정된 부분 💥💥💥
    def _display_log_detail(self, source_index):
        """선택된 로그의 상세 정보를 포맷에 맞게 detail_view에 표시합니다."""
        if not self.log_table_model:
            return

        try:
            display_object = self.log_table_model.get_data_by_col_name(
                source_index.row(), "ParsedBodyObject"
            )
            # ParsedBodyObject가 없으면 AsciiData를 표시
            if display_object is None:
                display_object = self.log_table_model.get_data_by_col_name(
                    source_index.row(), "AsciiData"
                )

            if display_object:
                # JSON 객체일 경우
                if isinstance(display_object, dict):
                    formatted_text = json.dumps(
                        display_object, indent=4, ensure_ascii=False
                    )
                    self.detail_view.setText(formatted_text)
                # SECS/GEM 메시지 (리스트)일 경우
                elif isinstance(display_object, list):
                    # 재귀적으로 SECS 객체를 포맷팅하는 내부 함수
                    def format_secs_obj(obj, indent=0):
                        lines = []
                        indent_str = "    " * indent
                        for item in obj:
                            # SimpleNamespace 객체인지 확인
                            if hasattr(item, "type") and hasattr(item, "value"):
                                if item.type == "L":
                                    lines.append(f"{indent_str}<L [{len(item.value)}]>")
                                    # 리스트 값에 대해 재귀 호출
                                    lines.extend(
                                        format_secs_obj(item.value, indent + 1)
                                    )
                                else:
                                    lines.append(
                                        f"{indent_str}<{item.type} '{item.value}'>"
                                    )
                        return lines

                    formatted_text = "\n".join(format_secs_obj(display_object))
                    self.detail_view.setText(formatted_text)
                # 그 외 (일반 텍스트)
                else:
                    self.detail_view.setText(str(display_object))
            else:
                self.detail_view.setText("")  # 표시할 내용이 없으면 비움

        except Exception as e:
            self.detail_view.setText(
                f"상세 정보를 표시하는 중 오류가 발생했습니다:\n{e}"
            )
            print(f"Error displaying detail: {e}")

    def show_detail_pane(self):
        # ... (이전과 동일)
        selected_indexes = self.tableView.selectedIndexes()
        if not selected_indexes:
            return
        source_index = self.proxy_model.mapToSource(selected_indexes[0])
        self._display_log_detail(source_index)
        if not self.detail_view.isVisible():
            self.detail_view.setVisible(True)
            self.splitter.setSizes([self.width() * 0.6, self.width() * 0.4])

    def update_detail_view(self):
        # ... (이전과 동일)
        if not self.detail_view.isVisible():
            return
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

    def visualize_secs_scenario(self, trace_id, additional_filter=None):
        # ... (이전과 동일)
        from dialogs.VisualizationDialog import VisualizationDialog

        com_logs = self.controller.get_scenario_data(trace_id, additional_filter)
        if com_logs.empty:
            msg = f"No SECS messages (Com logs) found related to ID: {trace_id}"
            if additional_filter:
                msg += f" with filter: '{additional_filter}'"
            QMessageBox.information(self, "Info", msg)
            return
        mermaid_code = self._generate_mermaid_code(com_logs)
        # VisualizationDialog는 독립적으로 동작하므로 self에 저장할 필요 없음
        viz_dialog = VisualizationDialog(mermaid_code, self)
        viz_dialog.exec()

    def _trace_with_filter(self, trace_id):
        text, ok = QInputDialog.getText(
            self, "Trace with Filter", f"Enter additional filter for '{trace_id}':"
        )
        if ok and text.strip():
            self.trace_requested.emit(trace_id, text.strip())
        elif ok:
            self.trace_requested.emit(trace_id, None)

    def _visualize_with_filter(self, trace_id):
        text, ok = QInputDialog.getText(
            self, "Visualize with Filter", f"Enter additional filter for '{trace_id}':"
        )
        if ok and text.strip():
            self.visualize_secs_scenario(trace_id, text.strip())
        elif ok:
            self.visualize_secs_scenario(trace_id, None)

    def _generate_mermaid_code(self, df):
        import html

        code = f"sequenceDiagram\n    participant MES\n    participant Host\n    participant Equipment\n\n"
        for _, row in df.iterrows():
            category = str(row.get("Category", "")).replace('"', "")
            ascii_data = str(row.get("AsciiData", ""))
            parsed_body = str(row.get("ParsedBody", "") or "")
            method_id = str(row.get("MethodID", "") or "").lower()

            if category == "Com":
                # Host <-> Equipment (SECS)
                direction = "->>" if "<--" in ascii_data else "-->>"
                actor_from, actor_to = (
                    ("Host", "Equipment")
                    if direction == "->>"
                    else ("Equipment", "Host")
                )
                msg_content = (
                    re.sub(r", loc :.*", "", ascii_data)
                    .replace("-->", "")
                    .replace("<--", "")
                    .strip()
                )
            elif category == "Info":
                # MES <-> Host (Internal/JSON)
                # Heuristic: MES -> Host if method contains publish, schedule, receive, on, or MCSEvent
                is_mes_to_host = any(
                    x in method_id
                    for x in ["publish", "schedule", "receive", "on", "mcsevent"]
                )
                direction = "->>"
                actor_from, actor_to = (
                    ("MES", "Host") if is_mes_to_host else ("Host", "MES")
                )
                # MethodID와 AsciiData를 모두 포함합니다.
                msg_content = (
                    f"{method_id}: {ascii_data}"
                    if method_id and ascii_data
                    else (method_id or ascii_data or "Internal Event")
                )
            else:
                continue

            # Mermaid 문법 및 HTML 렌더링을 깨뜨릴 수 있는 특수문자 처리
            # 1. HTML Escape: <, >, & 등이 HTML 태그로 오해받지 않도록 합니다.
            msg_content_escaped = html.escape(msg_content)
            parsed_body_escaped = html.escape(parsed_body)

            # 2. Label 구성: double quote로 감싸서 Mermaid 파서가 특수문자(: 등)를 오해하지 않게 합니다.
            if parsed_body_escaped:
                label = f'"{parsed_body_escaped}: {msg_content_escaped}"'
            else:
                label = f'"{msg_content_escaped}"'

            code += f"    {actor_from}{direction}{actor_to}: {label}\n"
        return code
