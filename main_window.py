import sys, json, os
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, QTableView, QStatusBar,
    QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QCheckBox
)
from PySide6.QtGui import QAction, QActionGroup
from functools import partial

from app_controller import AppController
from dialogs.ScenarioBrowserDialog import ScenarioBrowserDialog
from dialogs.QueryConditionsDialog import QueryConditionsDialog
from dialogs.QueryBuilderDialog import QueryBuilderDialog
from dialogs.DashboardDialog import DashboardDialog
from dialogs.TraceDialog import TraceDialog
from dialogs.ColumnSelectionDialog import ColumnSelectionDialog
from dialogs.ScriptEditorDialog import ScriptEditorDialog
from dialogs.HighlightingDialog import HighlightingDialog
from dialogs.ValidationResultDialog import ValidationResultDialog
from dialogs.HistoryBrowserDialog import HistoryBrowserDialog
from widgets.base_log_viewer import BaseLogViewerWidget

CONFIG_FILE = 'config.json'

class MainWindow(QMainWindow):
    def __init__(self, controller: AppController):
        super().__init__()
        self.controller = controller
        self.last_query_data = None
        self.open_trace_dialogs = []
        self._is_fetching = False
        self.validation_result_dialog = None

        self.setWindowTitle("Log Analyzer")
        self.setGeometry(100, 100, 1200, 800)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # --- UI 구성 ---
        self.db_connect_button = QPushButton("📡 데이터베이스에 연결하여 로그 조회")
        layout.addWidget(self.db_connect_button)
        
        # BaseLogViewerWidget 인스턴스 생성
        self.log_viewer = BaseLogViewerWidget(self.controller)
        
        # 필터 입력창과 자동 스크롤 체크박스를 담을 수평 레이아웃 생성
        filter_layout = QHBoxLayout()
        self.auto_scroll_checkbox = QCheckBox("Auto Scroll to Bottom")
        self.auto_scroll_checkbox.setChecked(True)
        
        # BaseLogViewer의 필터 입력창을 현재 레이아웃에서 제거
        filter_input_widget = self.log_viewer.layout().takeAt(0).widget()
        
        # 새로 만든 수평 레이아웃에 필터 입력창과 체크박스 추가
        filter_layout.addWidget(filter_input_widget)
        filter_layout.addWidget(self.auto_scroll_checkbox)
        
        # 메인 레이아웃에 수평 레이아웃과 로그 뷰어 추가
        layout.addLayout(filter_layout)
        layout.addWidget(self.log_viewer)
        
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready. Please open a log file.")

        self._create_menu()
        self.connect_signals()
        self.setup_ui_for_mode()
        self.update_table_model(self.controller.source_model)

    # ... (connect_signals 이하 다른 메소드들은 이전과 동일합니다) ...
    def connect_signals(self):
        self.db_connect_button.clicked.connect(self.start_db_connection)
        self.controller.model_updated.connect(self.update_table_model)
        self.controller.fetch_progress.connect(self.on_fetch_progress)
        self.controller.fetch_completed.connect(self.on_fetch_complete)
        self.controller.row_count_updated.connect(self._update_row_count_status)
        self.controller.fetch_error.connect(self.on_fetch_error)
        self.log_viewer.trace_requested.connect(self.start_event_trace)

    def update_table_model(self, source_model):
        self.log_viewer.set_model(source_model)
        self.apply_settings(source_model)

        is_data_loaded = source_model is not None and not source_model._data.empty
        self.save_action.setEnabled(is_data_loaded)

        if self.auto_scroll_checkbox.isChecked():
            QTimer.singleShot(0, self.log_viewer.tableView.scrollToBottom)

        total_rows = source_model.rowCount()
        self.statusBar().showMessage(f"Loaded {total_rows:,} logs.")
        
    def _create_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        open_action = QAction("&Open Log File...", self)
        open_action.triggered.connect(self.open_log_file)
        file_menu.addAction(open_action)

        self.save_action = QAction("&Save View as CSV...", self)
        self.save_action.triggered.connect(self.save_log_file)
        self.save_action.setEnabled(False)
        file_menu.addAction(self.save_action)

        file_menu.addSeparator()
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        self.view_menu = menu_bar.addMenu("&View")
        theme_menu = self.view_menu.addMenu("Theme")
        theme_group = QActionGroup(self)
        themes = ["light", "dark", "dracula", "solarized"] 
        for theme in themes:
            action = QAction(theme.capitalize(), self, checkable=True)
            action.triggered.connect(lambda checked, t=theme: self._apply_theme(t))
            theme_group.addAction(action)
            theme_menu.addAction(action)
            if self.controller.get_current_theme() == theme:
                action.setChecked(True)

        self.view_menu.addSeparator()
        select_columns_action = QAction("&Select Columns...", self)
        select_columns_action.triggered.connect(self.open_column_selection_dialog)
        self.view_menu.addAction(select_columns_action)
        self.view_menu.addSeparator()
        dashboard_action = QAction("Show Dashboard...", self)
        dashboard_action.triggered.connect(self.show_dashboard)
        self.view_menu.addAction(dashboard_action)

        self.tools_menu = menu_bar.addMenu("&Tools")
        query_builder_action = QAction("Advanced Filter...", self)
        query_builder_action.triggered.connect(self.open_query_builder)
        self.tools_menu.addAction(query_builder_action)
        clear_filter_action = QAction("Clear Advanced Filter", self)
        clear_filter_action.triggered.connect(self.clear_advanced_filter)
        self.tools_menu.addAction(clear_filter_action)
        self.tools_menu.addSeparator()
        
        self.scenario_menu = self.tools_menu.addMenu("Run Scenario Validation")
        self.tools_menu.aboutToShow.connect(self.populate_scenario_menu)
        browse_scenarios_action = QAction("Browse Scenarios...", self)
        browse_scenarios_action.triggered.connect(self.open_scenario_browser)
        self.tools_menu.addAction(browse_scenarios_action)
        self.tools_menu.addSeparator()
        script_editor_action = QAction("Analysis Script Editor...", self)
        script_editor_action.triggered.connect(self.open_script_editor)
        self.tools_menu.addAction(script_editor_action)

        self.tools_menu.addSeparator()
        highlighting_action = QAction("Conditional Highlighting...", self)
        highlighting_action.triggered.connect(self.open_highlighting_dialog)
        self.tools_menu.addAction(highlighting_action)

        self.tools_menu.addSeparator()
        history_action = QAction("Validation History...", self)
        history_action.triggered.connect(self.open_history_browser)
        self.tools_menu.addAction(history_action)

        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About...", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def start_event_trace(self, trace_id):
        trace_data = self.controller.get_trace_data(trace_id)
        if trace_data.empty:
            QMessageBox.information(self, "Trace Result", f"No logs found containing ID: '{trace_id}'")
            return
        
        rules = self.controller.highlighting_rules
        trace_dialog = TraceDialog(trace_data, trace_id, rules, self.controller, self)
        trace_dialog.finished.connect(lambda: self.open_trace_dialogs.remove(trace_dialog))
        self.open_trace_dialogs.append(trace_dialog)
        trace_dialog.show()

    def open_column_selection_dialog(self):
        source_model = self.log_viewer.source_model()
        if source_model is None or source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return
            
        all_columns = [source_model.headerData(i, Qt.Orientation.Horizontal) for i in range(source_model.columnCount())]
        visible_columns = [col for i, col in enumerate(all_columns) if not self.log_viewer.tableView.isColumnHidden(i)]
        self.col_dialog = ColumnSelectionDialog(all_columns, visible_columns, self)
        if self.col_dialog.exec():
            new_visible_columns = self.col_dialog.get_selected_columns()
            for i, col_name in enumerate(all_columns):
                self.log_viewer.tableView.setColumnHidden(i, col_name not in new_visible_columns)

    def apply_settings(self, source_model):
        if source_model is None: return
        try:
            # 💥 변경점 1: 파일 대신 컨트롤러의 config 객체에서 설정을 읽어옴
            visible_columns = self.controller.config.get('visible_columns', [])
            all_columns = [source_model.headerData(i, Qt.Orientation.Horizontal) for i in range(source_model.columnCount())]
            for i, col_name in enumerate(all_columns):
                # 컬럼 설정이 비어있으면 모든 컬럼을 보여줌 (최초 실행 등)
                self.log_viewer.tableView.setColumnHidden(i, visible_columns and col_name not in visible_columns)
        except Exception as e:
            print(f"Could not apply settings: {e}")
        
        for i in range(source_model.columnCount()):
            self.log_viewer.tableView.setColumnWidth(i, 80)

    def save_settings(self):
        source_model = self.log_viewer.source_model()
        if source_model is None or source_model._data.empty: return

        all_columns = [source_model.headerData(i, Qt.Orientation.Horizontal) for i in range(source_model.columnCount())]
        visible_columns = [col for i, col in enumerate(all_columns) if not self.log_viewer.tableView.isColumnHidden(i)]
        
        # 💥 변경점 2: 컨트롤러의 config 객체를 업데이트하고 저장 메소드 호출
        self.controller.config['visible_columns'] = visible_columns
        self.controller.save_config() # 프로그램 종료 시 최종 설정 저장

    def populate_scenario_menu(self):
        self.scenario_menu.clear()
        run_all_action = QAction("Run All Scenarios", self)
        run_all_action.triggered.connect(lambda: self.run_scenario_validation(None))
        self.scenario_menu.addAction(run_all_action)
        self.scenario_menu.addSeparator()
        try:
            scenario_names = self.controller.get_scenario_names()
            if scenario_names and "Error" not in scenario_names:
                for name in scenario_names:
                    action = QAction(name, self)
                    action.triggered.connect(partial(self.run_scenario_validation, name))
                    self.scenario_menu.addAction(action)
            else:
                action = QAction(scenario_names[0] if scenario_names else "No scenarios found", self)
                action.setEnabled(False)
                self.scenario_menu.addAction(action)
        except Exception as e:
            action = QAction(f"Error loading scenarios: {e}", self)
            action.setEnabled(False)
            self.scenario_menu.addAction(action)
    
    def run_scenario_validation(self, scenario_name=None):
        source_model = self.log_viewer.source_model()
        if source_model is None or source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return
        
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            validation_reports = self.controller.run_scenario_validation(scenario_name)
            if not validation_reports:
                QMessageBox.information(self, "Info", "No matching scenarios were attempted.")
                return

            self.validation_result_dialog = ValidationResultDialog(validation_reports, source_model._data, self)
            self.validation_result_dialog.highlight_log_requested.connect(self.highlight_log_row)
            self.validation_result_dialog.show()
        finally:
            QApplication.restoreOverrideCursor()

    def open_scenario_browser(self):
        all_scenarios = self.controller.load_all_scenarios()
        dialog = ScenarioBrowserDialog(all_scenarios, self)
        dialog.exec()

    def open_log_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Log File", "", "CSV Files (*.csv);;All Files (*)")
        if filepath:
            source_model = self.log_viewer.source_model()
            if source_model:
                source_model.clear_highlights()
            
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.statusBar().showMessage(f"Loading {os.path.basename(filepath)}...")
            try:
                success = self.controller.load_log_file(filepath)
                if not success:
                    QMessageBox.warning(self, "Load Failed", "No data could be parsed from the selected file.")
                else:
                    self.populate_scenario_menu()
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"An error occurred while opening the file:\n{e}")
            finally:
                QApplication.restoreOverrideCursor()

    def open_query_builder(self):
        source_model = self.log_viewer.source_model()
        if source_model is None or source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return
            
        column_names = [source_model.headerData(i, Qt.Orientation.Horizontal) for i in range(source_model.columnCount())]
        date_columns = ['SystemDate']
        saved_filters = self.controller.load_filters()
        dialog = QueryBuilderDialog(column_names, date_columns, saved_filters, self.last_query_data, self)
        
        if dialog.exec():
            query_data = dialog.get_query_data()
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self.controller.apply_advanced_filter(query_data)
                self.last_query_data = query_data
                self.statusBar().showMessage(f"Filter applied. Showing {self.log_viewer.proxy_model.rowCount():,} of {source_model.rowCount():,} rows.")
            finally:
                QApplication.restoreOverrideCursor()
        
        for name, query in dialog.saved_filters.items():
            self.controller.save_filter(name, query)

    def clear_advanced_filter(self):
        source_model = self.log_viewer.source_model()
        if source_model:
            source_model.clear_highlights()
        self.controller.clear_advanced_filter()
        self.last_query_data = None
        if source_model:
            self.statusBar().showMessage(f"Filter cleared. Showing {source_model.rowCount():,} rows.")

        is_data_loaded = source_model is not None and not source_model._data.empty
        self.save_action.setEnabled(is_data_loaded)
        
    def show_dashboard(self):
        source_model = self.log_viewer.source_model()
        if source_model is None or source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return
        
        if self.controller.dashboard_dialog is None:
            self.controller.dashboard_dialog = DashboardDialog(source_model._data, self)
            self.controller.dashboard_dialog.finished.connect(self._on_dashboard_closed)
        
        self.controller.dashboard_dialog.show()
        self.controller.dashboard_dialog.activateWindow()

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

    def open_script_editor(self):
        source_model = self.log_viewer.source_model()
        proxy_model = self.log_viewer.proxy_model
        if source_model is None or source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return

        current_view_df = source_model._data.iloc[
            [proxy_model.mapToSource(proxy_model.index(r,0)).row() for r in range(proxy_model.rowCount())]
        ]
        dialog = ScriptEditorDialog(self)
        
        def handle_run_request(script_code):
            result_obj = self.controller.run_analysis_script(script_code, current_view_df)
            final_output = ""
            if result_obj.captured_output:
                final_output += f"--- Captured Output ---\n{result_obj.captured_output}\n"
            if result_obj.summary:
                final_output += f"--- Summary ---\n{result_obj.summary}"
            dialog.set_result(final_output.strip())

            if result_obj.new_dataframe is not None:
                df_dialog = TraceDialog(result_obj.new_dataframe, result_obj.new_df_title, [], self.controller, self)
                df_dialog.exec()
            
            if source_model:
                source_model.set_highlights(result_obj.markers)

        dialog.run_script_requested.connect(handle_run_request)
        dialog.exec()

    def show_about_dialog(self):
        QMessageBox.about(self, "About Advanced Log Analyzer", "...")
    
    def setup_ui_for_mode(self):
        if self.controller.mode == 'realtime':
            self.db_connect_button.setVisible(True)
            # filter_input은 이제 filter_layout 안에 있으므로 직접 제어하지 않음
            # self.log_viewer.filter_input.setVisible(False)
            self.auto_scroll_checkbox.setVisible(True)
            self.setWindowTitle(f"Log Analyzer - [DB: {self.controller.connection_name}]")
        else: # file mode
            self.db_connect_button.setVisible(False)
            # self.log_viewer.filter_input.setVisible(True)
            self.auto_scroll_checkbox.setVisible(False)
            self.setWindowTitle("Log Analyzer - [File Mode]")

    def start_db_connection(self):
        if self._is_fetching:
            self.controller.cancel_db_fetch()
            self.statusBar().showMessage("Cancelling...")
        else:
            dialog = QueryConditionsDialog(self)
            if dialog.exec():
                query_conditions = dialog.get_conditions()
                self.controller.start_db_fetch(query_conditions)
                self._is_fetching = True
                self.db_connect_button.setText("❌ 데이터 수신 중단")
                self.db_connect_button.setStyleSheet("background-color: #DA4453; color: white;")
                if self.controller.mode == 'realtime':
                    self.tools_menu.setEnabled(False)
                    self.view_menu.setEnabled(False)
                    
    def on_fetch_progress(self, message): self.statusBar().showMessage(message)
    def on_fetch_complete(self):
        self._is_fetching = False
        self.db_connect_button.setEnabled(True)
        self.db_connect_button.setText("📡 데이터베이스에 연결하여 로그 조회")
        self.db_connect_button.setStyleSheet("")
        if self.controller.mode == 'realtime':
            self.tools_menu.setEnabled(True)
            self.view_menu.setEnabled(True)        
        source_model = self.log_viewer.source_model()
        if source_model:
            total_rows = source_model.rowCount()
            if self.statusBar().currentMessage() != "Cancelling...":
                 self.statusBar().showMessage(f"Completed. Total {total_rows:,} logs in view.")
           
    def _update_row_count_status(self, row_count):
        self.statusBar().showMessage(f"Receiving... {row_count:,} rows")
        if self.auto_scroll_checkbox.isChecked():
            self.log_viewer.tableView.scrollToBottom()

    def on_fetch_error(self, error_message):
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_message}")
        self.on_fetch_complete()

    def _on_dashboard_closed(self): 
        self.controller.dashboard_dialog = None

    def _apply_theme(self, theme_name):
        """선택된 테마를 앱에 적용하고 컨트롤러에 저장을 요청합니다."""
        from main import apply_theme
        if apply_theme(QApplication.instance(), theme_name):
            print(f"Applied theme: {theme_name}")
            # 💥 변경점 3: 컨트롤러의 set_current_theme만 호출하면 자동으로 저장됨
            self.controller.set_current_theme(theme_name)
        else:
            QMessageBox.warning(self, "Theme Error", f"Could not find or apply theme: {theme_name}")

    def open_highlighting_dialog(self):
        source_model = self.log_viewer.source_model()
        if source_model is None or source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load data first.")
            return

        if hasattr(self, 'highlighting_dialog') and self.highlighting_dialog.isVisible():
            self.highlighting_dialog.activateWindow()
            return
        column_names = source_model._data.columns.tolist()
        self.highlighting_dialog = HighlightingDialog(column_names, self)
        self.highlighting_dialog.show()

    def save_log_file(self):
        source_model = self.log_viewer.source_model()
        proxy_model = self.log_viewer.proxy_model
        if source_model is None or proxy_model.rowCount() == 0:
            QMessageBox.information(self, "Info", "There is no data to save.")
            return
            
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Log File", "log_export.csv", "CSV Files (*.csv);;All Files (*)")
        if filepath:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.statusBar().showMessage("Saving file...")
            try:
                visible_rows_indices = [proxy_model.mapToSource(proxy_model.index(r, 0)).row() for r in range(proxy_model.rowCount())]
                df_to_save = source_model._data.iloc[visible_rows_indices]
                success, message = self.controller.save_log_to_csv(df_to_save, filepath)

                if success: self.statusBar().showMessage(message)
                else: QMessageBox.critical(self, "Save Error", message)
            finally:
                QApplication.restoreOverrideCursor()

    def highlight_log_row(self, original_index):
        source_model = self.log_viewer.source_model()
        proxy_model = self.log_viewer.proxy_model
        if not source_model or source_model._data.empty: return
            
        try:
            model_row = source_model._data.index.get_loc(original_index)
            proxy_index = proxy_model.mapFromSource(source_model.index(model_row, 0))
            
            if proxy_index.isValid():
                self.log_viewer.tableView.scrollTo(proxy_index, QTableView.ScrollHint.PositionAtCenter)
                self.log_viewer.tableView.selectRow(proxy_index.row())
                self.activateWindow()
        except KeyError: pass

    def open_history_browser(self):
        history_summary = self.controller.get_history_summary()
        if history_summary.empty:
            QMessageBox.information(self, "Info", "No validation history found.")
            return
        history_browser = HistoryBrowserDialog(history_summary, self)
        history_browser.history_selected.connect(self.show_history_detail)
        history_browser.exec()

    def show_history_detail(self, run_id):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            history_report = self.controller.get_history_detail(run_id)
            if not history_report:
                QMessageBox.warning(self, "Error", f"Could not load details for Run ID: {run_id}")
                return
            
            source_model = self.log_viewer.source_model()
            detail_dialog = ValidationResultDialog([history_report], source_model._data, self)
            detail_dialog.highlight_log_requested.connect(self.highlight_log_row)
            detail_dialog.show()
        finally:
            QApplication.restoreOverrideCursor()

