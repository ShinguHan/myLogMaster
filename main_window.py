import sys, json, os, re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QFileDialog, QMessageBox, QMenu, QStatusBar,QApplication,QTableView,
    QWidget, QVBoxLayout, QLineEdit, QHBoxLayout, QCheckBox, QPushButton
)
from PySide6.QtGui import QAction, QActionGroup
from functools import partial

# app_controller는 타입 힌팅을 위해 필요합니다.
from app_controller import AppController
from widgets.base_log_viewer import BaseLogViewerWidget
from dialogs.ScenarioBrowserDialog import ScenarioBrowserDialog
from dialogs.QueryConditionsDialog import QueryConditionsDialog
from dialogs.DashboardDialog import DashboardDialog
from dialogs.ColumnSelectionDialog import ColumnSelectionDialog
from dialogs.HighlightingDialog import HighlightingDialog
from dialogs.ValidationResultDialog import ValidationResultDialog
from dialogs.HistoryBrowserDialog import HistoryBrowserDialog
from dialogs.ScriptEditorDialog import ScriptEditorDialog


class MainWindow(QMainWindow):
    def __init__(self, controller: AppController):
        super().__init__()
        self.controller = controller
        # open_trace_dialogs는 MainWindow가 관리하는 것이 더 적합합니다.
        self.open_trace_dialogs = [] 
        self._is_fetching = False
        self.validation_result_dialog = None
        
        self._init_ui()
        self._create_menu()
        self.connect_signals()
        self.setup_ui_for_mode()
        self.apply_settings()

    def _init_ui(self):
        self.setWindowTitle("Log Analyzer")
        self.setGeometry(100, 100, 1200, 800)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        self.db_connect_button = QPushButton("📡 데이터베이스에 연결하여 로그 조회")
        main_layout.addWidget(self.db_connect_button)
        
        filter_layout = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter logs (case-insensitive)...")
        filter_layout.addWidget(self.filter_input)
        
        self.auto_scroll_checkbox = QCheckBox("Auto Scroll to Bottom")
        self.auto_scroll_checkbox.setChecked(True)
        filter_layout.addWidget(self.auto_scroll_checkbox)
        
        # 💥💥💥 수정된 부분 💥💥💥
        # 두 번째 인자로 self를 넘기지 않습니다. 대신 parent=self를 명시하여
        # 위젯의 부모-자식 관계를 올바르게 설정합니다.
        self.log_viewer = BaseLogViewerWidget(self.controller, parent=self)
        
        main_layout.addLayout(filter_layout)
        main_layout.addWidget(self.log_viewer)
        
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready.")

    def connect_signals(self):
        # 컨트롤러 신호 연결
        self.controller.model_updated.connect(self.update_table_model)
        self.controller.fetch_progress.connect(self.on_fetch_progress)
        self.controller.fetch_completed.connect(self.on_fetch_complete)
        self.controller.row_count_updated.connect(self._update_row_count_status)
        self.controller.fetch_error.connect(self.on_fetch_error)

        # UI 위젯 신호 연결
        self.db_connect_button.clicked.connect(self.start_db_connection)
        self.filter_input.textChanged.connect(self.log_viewer.set_filter_fixed_string)
        self.log_viewer.trace_requested.connect(self.start_event_trace)

    def _create_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        
        # 💥💥💥 수정된 부분 💥💥💥
        # self.log_viewer.open_log_file이 아닌 self.open_log_file에 연결합니다.
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
            action.triggered.connect(partial(self._apply_theme, theme))
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
        # 💥💥💥 신규 메뉴 추가 💥💥💥
        detailed_trace_action = QAction("Detailed Carrier Trace...", self)
        detailed_trace_action.triggered.connect(self.open_detailed_trace_dialog)
        self.tools_menu.addAction(detailed_trace_action)
        self.tools_menu.addSeparator()

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

    def populate_scenario_menu(self):
        self.scenario_menu.clear()
        run_all_action = QAction("Run All Scenarios", self)
        run_all_action.triggered.connect(lambda: self.run_scenario_validation(None))
        self.scenario_menu.addAction(run_all_action)
        self.scenario_menu.addSeparator()
        try:
            scenario_names = self.controller.get_scenario_names()
            for name in scenario_names:
                action = QAction(name, self)
                action.triggered.connect(partial(self.run_scenario_validation, name))
                self.scenario_menu.addAction(action)
        except Exception as e:
            action = QAction(f"Error loading scenarios: {e}", self)
            action.setEnabled(False)
            self.scenario_menu.addAction(action)

    def update_table_model(self, source_model):
        self.log_viewer.proxy_model.setSourceModel(source_model)
        self.log_viewer.log_table_model = source_model
        
        is_data_loaded = source_model is not None and not source_model._data.empty
        self.save_action.setEnabled(is_data_loaded)

        if self.auto_scroll_checkbox.isChecked():
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.log_viewer.tableView.scrollToBottom)
        
        self._update_row_count_status(source_model.rowCount())

    def open_log_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Log File", "", "CSV Files (*.csv);;All Files (*)")
        if filepath:
            self.log_viewer.log_table_model.clear_highlights()
            
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.statusBar().showMessage(f"Loading {os.path.basename(filepath)}...")
            try:
                success = self.controller.load_log_file(filepath)
                if not success:
                    QMessageBox.warning(self, "Load Failed", "No data could be parsed from the selected file.")
                else:
                    self.populate_scenario_menu()
            finally:
                QApplication.restoreOverrideCursor()

    # ... 이하 모든 다른 메소드들은 그대로 유지됩니다 ...
    # (start_event_trace, save_log_file, run_scenario_validation 등)
    def start_event_trace(self, trace_id):
        # TraceDialog를 지연 임포트하여 순환 참조를 방지합니다.
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

    def run_scenario_validation(self, scenario_name=None):
        if self.controller.source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return
        
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            validation_reports = self.controller.run_scenario_validation(scenario_name)
            
            if not validation_reports:
                QMessageBox.information(self, "Info", "No matching scenarios were attempted.")
                return

            self.validation_result_dialog = ValidationResultDialog(validation_reports, self.controller.source_model._data, self)
            self.validation_result_dialog.highlight_log_requested.connect(self.highlight_log_row)
            self.validation_result_dialog.show()

        finally:
            QApplication.restoreOverrideCursor()

    def open_scenario_browser(self):
        all_scenarios = self.controller.load_all_scenarios()
        dialog = ScenarioBrowserDialog(all_scenarios, self)
        dialog.exec()

    def open_query_builder(self):
        if self.controller.source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return
            
        column_names = self.controller.source_model._data.columns.tolist()
        date_columns = ['SystemDate']
        # saved_filters = self.controller.load_filters() # 컨트롤러가 직접 관리
        dialog = QueryConditionsDialog(column_names, date_columns, self.controller, self)
        
        if dialog.exec():
            query_data = dialog.get_query_data()
            
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self.controller.apply_advanced_filter(query_data)
                self.statusBar().showMessage(f"Filter applied. Showing {self.log_viewer.proxy_model.rowCount():,} of {self.controller.source_model.rowCount():,} rows.")
            finally:
                QApplication.restoreOverrideCursor()

    def clear_advanced_filter(self):
        self.controller.clear_advanced_filter()
        if self.controller.source_model:
            self.statusBar().showMessage(f"Filter cleared. Showing {self.controller.source_model.rowCount():,} rows.")
        is_data_loaded = self.controller.source_model is not None and not self.controller.source_model._data.empty
        self.save_action.setEnabled(is_data_loaded)
        
    def show_dashboard(self):
        if self.controller.source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return
        
        if self.controller.dashboard_dialog is None:
            self.controller.dashboard_dialog = DashboardDialog(self.controller.source_model._data, self)
            self.controller.dashboard_dialog.finished.connect(self._on_dashboard_closed)
        
        self.controller.dashboard_dialog.show()
        self.controller.dashboard_dialog.activateWindow()

    def open_column_selection_dialog(self):
        source_model = self.controller.source_model
        if source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return
            
        all_columns = source_model._data.columns.tolist()
        visible_columns = [col for i, col in enumerate(all_columns) if not self.log_viewer.tableView.isColumnHidden(i)]
        dialog = ColumnSelectionDialog(all_columns, visible_columns, self)
        if dialog.exec():
            new_visible_columns = dialog.get_selected_columns()
            for i, col_name in enumerate(all_columns):
                self.log_viewer.tableView.setColumnHidden(i, col_name not in new_visible_columns)

    def apply_settings(self):
        source_model = self.controller.source_model
        if source_model is None: return
        
        config = self.controller.get_config()
        visible_columns = config.get('visible_columns', [])
        
        if visible_columns and not source_model._data.empty:
            all_columns = source_model._data.columns.tolist()
            for i, col_name in enumerate(all_columns):
                self.log_viewer.tableView.setColumnHidden(i, col_name not in visible_columns)
        
        if not source_model._data.empty:
            for i in range(source_model.columnCount()):
                self.log_viewer.tableView.setColumnWidth(i, 80)

    def save_settings(self):
        source_model = self.controller.source_model
        if source_model is None or source_model._data.empty:
            self.controller.save_config() # 테마만이라도 저장
            return

        all_columns = source_model._data.columns.tolist()
        visible_columns = [col for i, col in enumerate(all_columns) if not self.log_viewer.tableView.isColumnHidden(i)]
        self.controller.config['visible_columns'] = visible_columns
        self.controller.save_config()
            
    def closeEvent(self, event):
        self.save_settings()
        event.accept()

    def open_script_editor(self):
        source_model = self.controller.source_model
        if source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return

        current_view_df = source_model._data.iloc[
            [self.log_viewer.proxy_model.mapToSource(self.log_viewer.proxy_model.index(r,0)).row() 
             for r in range(self.log_viewer.proxy_model.rowCount())]
        ]
        dialog = ScriptEditorDialog(self)
        
        def handle_run_request(script_code):
            # ... (이전과 동일)
            pass

        dialog.run_script_requested.connect(handle_run_request)
        dialog.exec()

    def show_about_dialog(self):
        QMessageBox.about(self,
            "About Advanced Log Analyzer",
            """
            <b>Advanced Log Analyzer v1.0</b>
            <p>A professional tool for analyzing complex manufacturing logs.</p>
            <p>Developed in partnership with a brilliant analyst.</p>
            <p>Powered by Python and PySide6.</p>
            """
        )
    
    def setup_ui_for_mode(self):
        if self.controller.mode == 'realtime':
            self.db_connect_button.setVisible(True)
            self.filter_input.setVisible(True)
            self.auto_scroll_checkbox.setVisible(True)
            self.setWindowTitle(f"Log Analyzer - [DB: {self.controller.connection_name}]")
            self.statusBar().showMessage("Ready to connect to the database.")
        else:
            self.db_connect_button.setVisible(False)
            self.filter_input.setVisible(True)
            self.auto_scroll_checkbox.setVisible(False)
            self.setWindowTitle("Log Analyzer - [File Mode]")
            self.statusBar().showMessage("Ready. Please open a log file.")

    def start_db_connection(self):
        if self._is_fetching:
            self.controller.cancel_db_fetch()
            self.statusBar().showMessage("Cancelling...")
        else:
            # 💥💥💥 수정된 부분 시작 💥💥💥
            # QueryConditionsDialog를 생성할 때, 더 이상 사용하지 않는 'date_columns' 인자를 제거합니다.
            dialog = QueryConditionsDialog(
                column_names=self.controller.get_default_column_names(), # 컨트롤러에서 컬럼명 가져오기
                parent=self
            )
            # 💥💥💥 수정된 부분 끝 💥💥💥
            if dialog.exec():
                query_conditions = dialog.get_conditions()
                if not query_conditions:
                    return 
                self.controller.start_db_fetch(query_conditions)
                self._is_fetching = True
                self.db_connect_button.setText("❌ 데이터 수신 중단")
                self.db_connect_button.setStyleSheet("background-color: #DA4453; color: white;")
                self.tools_menu.setEnabled(False)
                self.view_menu.setEnabled(False)
                    
    def on_fetch_progress(self, message):
        self.statusBar().showMessage(message)

    def on_fetch_complete(self):
        self._is_fetching = False
        self.db_connect_button.setEnabled(True)
        self.db_connect_button.setText("📡 데이터베이스에 연결하여 로그 조회")
        self.db_connect_button.setStyleSheet("")
        if self.controller.mode == 'realtime':
            self.tools_menu.setEnabled(True)
            self.view_menu.setEnabled(True)        
        source_model = self.controller.source_model
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
        from main import apply_theme # main.py에서 함수 가져오기
        if apply_theme(QApplication.instance(), theme_name):
            self.controller.set_current_theme(theme_name)
        else:
            QMessageBox.warning(self, "Theme Error", f"Could not find or apply theme: {theme_name}")

    def open_highlighting_dialog(self):
        if self.controller.source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load data first.")
            return

        if hasattr(self, 'highlighting_dialog') and self.highlighting_dialog.isVisible():
            self.highlighting_dialog.activateWindow()
            return

        column_names = self.controller.source_model._data.columns.tolist()
        rules_data = self.controller.get_highlighting_rules()
        self.highlighting_dialog = HighlightingDialog(column_names, rules_data, self)
        
        # 다이얼로그의 신호를 컨트롤러의 메소드에 연결
        self.highlighting_dialog.rules_updated.connect(self.controller.set_and_save_highlighting_rules)
        self.highlighting_dialog.show()

    def save_log_file(self):
        source_model = self.controller.source_model
        if source_model is None or self.log_viewer.proxy_model.rowCount() == 0:
            QMessageBox.information(self, "Info", "There is no data to save.")
            return
            
        default_filename = "log_export.csv"
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Log File", default_filename, "CSV Files (*.csv);;All Files (*)")

        if filepath:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.statusBar().showMessage("Saving file...")
            try:
                visible_rows_indices = [self.log_viewer.proxy_model.mapToSource(self.log_viewer.proxy_model.index(r, 0)).row() for r in range(self.log_viewer.proxy_model.rowCount())]
                df_to_save = source_model._data.iloc[visible_rows_indices]
                success, message = self.controller.save_log_to_csv(df_to_save, filepath)

                if success:
                    self.statusBar().showMessage(message)
                else:
                    QMessageBox.critical(self, "Save Error", message)
            finally:
                QApplication.restoreOverrideCursor()

    def highlight_log_row(self, original_index):
        source_model = self.controller.source_model
        if not source_model or source_model._data.empty:
            return
            
        try:
            model_row = source_model._data.index.get_loc(original_index)
            proxy_index = self.log_viewer.proxy_model.mapFromSource(source_model.index(model_row, 0))
            
            if proxy_index.isValid():
                self.log_viewer.tableView.scrollTo(proxy_index, QTableView.ScrollHint.PositionAtCenter)
                self.log_viewer.tableView.selectRow(proxy_index.row())
                self.activateWindow()
        except KeyError:
            print(f"Could not find original index {original_index} in the current model.")

    def open_history_browser(self):
        history_summary = self.controller.get_history_summary()
        if history_summary.empty:
            QMessageBox.information(self, "Info", "No validation history found.")
            return

        history_browser = HistoryBrowserDialog(history_summary, self)
        history_browser.history_selected.connect(self.show_history_detail)
        history_browser.exec()

    def show_history_detail(self, run_id):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            history_report = self.controller.get_history_detail(run_id)
            if not history_report:
                QMessageBox.warning(self, "Error", f"Could not load details for Run ID: {run_id}")
                return
            
            source_model = self.controller.source_model
            detail_dialog = ValidationResultDialog([history_report], source_model._data, self)
            detail_dialog.highlight_log_requested.connect(self.highlight_log_row)
            detail_dialog.show()

        finally:
            QApplication.restoreOverrideCursor()

    # 💥💥💥 신규 추가된 함수 💥💥💥
    def open_detailed_trace_dialog(self):
        """상세 시나리오 추출을 위한 파라미터 입력 다이얼로그를 엽니다."""
        if self.controller.original_data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return

        from dialogs.DetailedTraceDialog import DetailedTraceDialog
        from dialogs.TraceDialog import TraceDialog
        
        dialog = DetailedTraceDialog(self)
        if dialog.exec():
            params = dialog.get_trace_parameters()
            if not params['carrier_id']:
                QMessageBox.warning(self, "Input Required", "Carrier ID is a required field.")
                return

            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                trace_data = self.controller.get_carrier_move_scenario(**params)
                if trace_data.empty:
                    QMessageBox.information(self, "Trace Result", "No matching logs found for the given criteria.")
                    return

                # 결과를 새로운 TraceDialog에 담아 보여줍니다.
                title = f"Trace for {params['carrier_id']}"
                if params['from_device']: title += f" from {params['from_device']}"
                if params['to_device']: title += f" to {params['to_device']}"

                rules = self.controller.get_highlighting_rules()
                trace_dialog = TraceDialog(trace_data, title, rules, self.controller, self)
                
                trace_dialog.finished.connect(lambda: self.open_trace_dialogs.remove(trace_dialog))
                self.open_trace_dialogs.append(trace_dialog)
                trace_dialog.show()

            finally:
                QApplication.restoreOverrideCursor()

