import re
import json
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableView, QTextEdit, 
                               QSplitter, QMenu, QMessageBox, QFileDialog, QApplication)
from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel
from PySide6.QtGui import QAction

# 💥 변경점: 순환 참조를 유발하는 모든 dialog import를 제거합니다.
# 이들은 이제 각 메소드 내부에서 지역적으로 import 됩니다.

class BaseLogViewerWidget(QWidget):
    trace_requested = Signal(str)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.last_query_data = None
        self.open_trace_dialogs = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tableView = QTableView()
        self.detail_view = QTextEdit()
        
        self._setup_ui()
        
        main_layout.addWidget(self.splitter)

        self.connect_signals()

    def _setup_ui(self):
        self.tableView.setSortingEnabled(True)
        self.tableView.setAlternatingRowColors(True)
        self.tableView.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tableView.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.tableView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        self.detail_view.setReadOnly(True)
        self.detail_view.setFontFamily("Courier New")
        self.detail_view.setVisible(False)

        self.splitter.addWidget(self.tableView)
        self.splitter.addWidget(self.detail_view)
        self.splitter.setSizes([1, 0])

        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setFilterKeyColumn(-1)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.tableView.setModel(self.proxy_model)

    def connect_signals(self):
        self.tableView.customContextMenuRequested.connect(self.show_table_context_menu)
        self.tableView.selectionModel().selectionChanged.connect(self.update_detail_view)

    def source_model(self):
        return self.proxy_model.sourceModel()

    def update_table_model(self, source_model):
        self.proxy_model.setSourceModel(source_model)
        if self.parent() and hasattr(self.parent(), 'apply_settings'):
            self.parent().apply_settings(source_model)
        
        is_data_loaded = source_model is not None and not source_model._data.empty
        if hasattr(self.parent(), 'save_action'):
             self.parent().save_action.setEnabled(is_data_loaded)

    def show_table_context_menu(self, pos):
        # ... (내용 변경 없음)
        selected_indexes = self.tableView.selectedIndexes()
        menu = QMenu(self)
        source_model = self.source_model()

        if selected_indexes and source_model:
            source_index = self.proxy_model.mapToSource(selected_indexes[0])
            show_detail_action = QAction("상세 로그 보기", self)
            show_detail_action.triggered.connect(self.show_detail_pane)
            menu.addAction(show_detail_action)
            
            tracking_id = source_model.get_data_by_col_name(source_index.row(), "TrackingID")
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

    def update_detail_view(self, selected=None, deselected=None):
        # ... (내용 변경 없음)
        if not self.detail_view.isVisible(): return
        selected_indexes = self.tableView.selectedIndexes()
        if not selected_indexes:
            self.detail_view.clear()
            return
        source_index = self.proxy_model.mapToSource(selected_indexes[0])
        self._display_log_detail(source_index)

    def _display_log_detail(self, source_index):
        # ... (내용 변경 없음)
        source_model = self.source_model()
        if not source_model: return
        try:
            display_object = source_model.get_data_by_col_name(source_index.row(), "ParsedBodyObject")
            if display_object is None:
                 display_object = source_model.get_data_by_col_name(source_index.row(), "AsciiData")

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
        # ... (내용 변경 없음)
        selected_indexes = self.tableView.selectedIndexes()
        if not selected_indexes: return
        source_index = self.proxy_model.mapToSource(selected_indexes[0])
        self._display_log_detail(source_index)
        if not self.detail_view.isVisible():
            self.detail_view.setVisible(True)
            self.splitter.setSizes([self.width() * 0.6, self.width() * 0.4])
        
    def hide_detail_pane(self):
        # ... (내용 변경 없음)
        self.detail_view.setVisible(False)
        self.splitter.setSizes([1, 0])

    def visualize_secs_scenario(self, trace_id):
        # 💥 변경점: 메소드 내부에서 지역적으로 import
        from dialogs.VisualizationDialog import VisualizationDialog
        com_logs = self.controller.get_scenario_data(trace_id)
        if com_logs.empty:
            QMessageBox.information(self, "Info", f"No SECS messages (Com logs) found related to ID: {trace_id}")
            return
        mermaid_code = self._generate_mermaid_code(com_logs)
        viz_dialog = VisualizationDialog(mermaid_code, self)
        viz_dialog.exec()

    def _generate_mermaid_code(self, df):
        # ... (내용 변경 없음)
        code = f"sequenceDiagram\n    participant Host\n    participant Equipment\n\n"
        for _, row in df.iterrows():
            ascii_data = row.get('AsciiData', '')
            parsed_body = row.get('ParsedBody', '')
            direction = "->>" if "<--" in ascii_data else "-->>"
            actor_from, actor_to = ("Host", "Equipment") if direction == "->>" else ("Equipment", "Host")
            msg_content = re.sub(r', loc :.*', '', ascii_data).replace('-->', '').replace('<--', '').strip()
            code += f"    {actor_from}{direction}{actor_to}: {parsed_body or msg_content}\n"
        return code
    
    def open_log_file(self):
        # ... (내용 변경 없음)
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Log File", "", "CSV Files (*.csv);;All Files (*)")
        if filepath:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self.controller.load_log_file(filepath)
            finally:
                QApplication.restoreOverrideCursor()

    def save_log_file(self):
        # ... (내용 변경 없음)
        source_model = self.source_model()
        if source_model is None or self.proxy_model.rowCount() == 0:
            return
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Log File", "log_export.csv", "CSV Files (*.csv)")
        if filepath:
            visible_rows = [self.proxy_model.mapToSource(self.proxy_model.index(r, 0)).row() for r in range(self.proxy_model.rowCount())]
            df_to_save = source_model._data.iloc[visible_rows]
            self.controller.save_log_to_csv(df_to_save, filepath)

    def open_query_builder(self):
        # 💥 변경점: 메소드 내부에서 지역적으로 import
        from dialogs.QueryBuilderDialog import QueryBuilderDialog
        source_model = self.source_model()
        if source_model is None or source_model._data.empty: return
        column_names = [source_model.headerData(i, Qt.Horizontal) for i in range(source_model.columnCount())]
        saved_filters = self.controller.load_filters()
        dialog = QueryBuilderDialog(column_names, ['SystemDate'], saved_filters, self.last_query_data, self)
        if dialog.exec():
            query_data = dialog.get_query_data()
            self.controller.apply_advanced_filter(query_data)
            self.last_query_data = query_data
            for name, query in dialog.saved_filters.items():
                self.controller.save_filter(name, query)
                
    def clear_advanced_filter(self):
        # ... (내용 변경 없음)
        self.controller.clear_advanced_filter()
        self.last_query_data = None

    def run_scenario_validation(self, scenario_name=None):
        # 💥 변경점: 메소드 내부에서 지역적으로 import
        from dialogs.ValidationResultDialog import ValidationResultDialog
        if self.source_model() is None or self.source_model()._data.empty: return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            reports = self.controller.run_scenario_validation(scenario_name)
            if reports:
                dialog = ValidationResultDialog(reports, self.source_model()._data, self)
                dialog.highlight_log_requested.connect(self.highlight_log_row)
                dialog.show()
        finally:
            QApplication.restoreOverrideCursor()
            
    def highlight_log_row(self, original_index):
        # ... (내용 변경 없음)
        source_model = self.source_model()
        if not source_model or source_model._data.empty: return
        try:
            model_row = source_model._data.index.get_loc(original_index)
            proxy_index = self.proxy_model.mapFromSource(source_model.index(model_row, 0))
            if proxy_index.isValid():
                self.tableView.scrollTo(proxy_index, QTableView.ScrollHint.PositionAtCenter)
                self.tableView.selectRow(proxy_index.row())
        except KeyError: pass

    def start_event_trace(self, trace_id):
        # 💥 변경점: 메소드 내부에서 지역적으로 import
        from dialogs.TraceDialog import TraceDialog
        trace_data = self.controller.get_trace_data(trace_id)
        if trace_data.empty:
            QMessageBox.information(self, "Trace Result", f"No logs found containing ID: '{trace_id}'")
            return
        rules = self.controller.get_highlighting_rules()
        trace_dialog = TraceDialog(trace_data, trace_id, rules, self.controller, self)
        trace_dialog.finished.connect(lambda: self.open_trace_dialogs.remove(trace_dialog))
        self.open_trace_dialogs.append(trace_dialog)
        trace_dialog.show()

    def open_column_selection_dialog(self):
        # 💥 변경점: 메소드 내부에서 지역적으로 import
        from dialogs.ColumnSelectionDialog import ColumnSelectionDialog
        if not self.source_model(): return
        all_cols = [self.source_model().headerData(i, Qt.Horizontal) for i in range(self.source_model().columnCount())]
        vis_cols = [c for i, c in enumerate(all_cols) if not self.tableView.isColumnHidden(i)]
        dialog = ColumnSelectionDialog(all_cols, vis_cols, self)
        if dialog.exec():
            new_vis_cols = dialog.get_selected_columns()
            for i, name in enumerate(all_cols):
                self.tableView.setColumnHidden(i, name not in new_vis_cols)

    def open_scenario_browser(self):
        # 💥 변경점: 메소드 내부에서 지역적으로 import
        from dialogs.ScenarioBrowserDialog import ScenarioBrowserDialog
        dialog = ScenarioBrowserDialog(self.controller.load_all_scenarios(), self)
        dialog.exec()

    def show_dashboard(self):
        # 💥 변경점: 메소드 내부에서 지역적으로 import
        from dialogs.DashboardDialog import DashboardDialog
        if not self.source_model() or self.source_model()._data.empty: return
        if self.controller.dashboard_dialog is None:
            self.controller.dashboard_dialog = DashboardDialog(self.source_model()._data, self)
            self.controller.dashboard_dialog.finished.connect(self._on_dashboard_closed)
        self.controller.dashboard_dialog.show()
        self.controller.dashboard_dialog.activateWindow()

    def _on_dashboard_closed(self):
        # ... (내용 변경 없음)
        self.controller.dashboard_dialog = None

    def open_script_editor(self):
        # 💥 변경점: 메소드 내부에서 지역적으로 import
        from dialogs.ScriptEditorDialog import ScriptEditorDialog
        if not self.source_model() or self.source_model()._data.empty: return
        vis_rows = [self.proxy_model.mapToSource(self.proxy_model.index(r,0)).row() for r in range(self.proxy_model.rowCount())]
        df = self.source_model()._data.iloc[vis_rows]
        dialog = ScriptEditorDialog(self)
        dialog.run_script_requested.connect(lambda code: self._run_analysis(code, df, dialog))
        dialog.exec()
        
    def _run_analysis(self, script_code, df, dialog):
        # 💥 변경점: 메소드 내부에서 지역적으로 import
        from dialogs.TraceDialog import TraceDialog
        result_obj = self.controller.run_analysis_script(script_code, df)
        final_output = ""
        if result_obj.captured_output:
            final_output += f"--- Captured Output ---\n{result_obj.captured_output}\n"
        if result_obj.summary:
            final_output += f"--- Summary ---\n{result_obj.summary}"
        dialog.set_result(final_output.strip())

        if result_obj.new_dataframe is not None:
            df_dialog = TraceDialog(result_obj.new_dataframe, result_obj.new_df_title, [], self.controller, self)
            df_dialog.show()
        
        source_model = self.source_model()
        if source_model:
            source_model.set_highlighting_rules(result_obj.markers) # Assume markers are in correct format

    def open_history_browser(self):
        # 💥 변경점: 메소드 내부에서 지역적으로 import
        from dialogs.HistoryBrowserDialog import HistoryBrowserDialog
        summary = self.controller.get_history_summary()
        if summary.empty: return
        dialog = HistoryBrowserDialog(summary, self)
        dialog.history_selected.connect(self.show_history_detail)
        dialog.exec()

    def show_history_detail(self, run_id):
        # 💥 변경점: 메소드 내부에서 지역적으로 import
        from dialogs.ValidationResultDialog import ValidationResultDialog
        detail = self.controller.get_history_detail(run_id)
        if not detail: return
        dialog = ValidationResultDialog([detail], self.source_model()._data, self)
        dialog.highlight_log_requested.connect(self.highlight_log_row)
        dialog.show()

