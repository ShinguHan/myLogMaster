import sys, json, os, re
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableView, QFileDialog, QMessageBox, QMenu, QStatusBar,
    QWidget, QVBoxLayout, QLineEdit, QSplitter, QTextEdit, QDialog, QTextBrowser, QPushButton
)
from PySide6.QtGui import QAction, QCursor

from dialogs.ScenarioBrowserDialog import ScenarioBrowserDialog
from dialogs.QueryBuilderDialog import QueryBuilderDialog
from dialogs.DashboardDialog import DashboardDialog
from dialogs.VisualizationDialog import VisualizationDialog
from dialogs.TraceDialog import TraceDialog
from dialogs.ColumnSelectionDialog import ColumnSelectionDialog
from models.LogTableModel import LogTableModel
from analysis_result import AnalysisResult
from dialogs.ScriptEditorDialog import ScriptEditorDialog

CONFIG_FILE = 'config.json'

class MainWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.last_query_data = None
        self.setWindowTitle("Log Analyzer")
        self.setGeometry(100, 100, 1200, 800)

        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # ⭐️ 1. DB 접속 버튼을 생성하고 레이아웃에 추가합니다.
        self.db_connect_button = QPushButton("📡 데이터베이스에 연결하여 로그 조회")
        self.db_connect_button.clicked.connect(self.start_db_connection)
        layout.addWidget(self.db_connect_button)
        
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
        self.setCentralWidget(main_widget)
        
        # ⭐️ 1. 상태 표시줄(Status Bar)을 생성하고 UI에 추가합니다.
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready. Please open a log file.")

        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setFilterKeyColumn(-1)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.tableView.setModel(self.proxy_model)

        self._create_menu()
        
        # ⭐️ 2. 컨트롤러의 신호를 UI의 슬롯에 연결합니다.
        self.controller.fetch_completed.connect(self.on_fetch_complete)
        self.controller.fetch_progress.connect(self.on_fetch_progress)

        self.filter_input.textChanged.connect(self.proxy_model.setFilterFixedString)
        self.tableView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tableView.customContextMenuRequested.connect(self.show_table_context_menu)
        self.tableView.selectionModel().selectionChanged.connect(self.update_detail_view)

        # ⭐️ 모드에 따라 UI를 초기화합니다.
        self.setup_ui_for_mode()

    def update_table_model(self, source_model):
        self.proxy_model.setSourceModel(source_model)
        self.apply_settings(source_model)
        # ⭐️ 2. 모델이 업데이트될 때마다 상태 표시줄 메시지도 업데이트합니다.
        total_rows = source_model.rowCount()
        self.statusBar().showMessage(f"Loaded {total_rows:,} logs.")
        
    def _create_menu(self):
        # ... (이전과 동일)
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        open_action = QAction("&Open Log File...", self)
        open_action.triggered.connect(self.open_log_file)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        view_menu = menu_bar.addMenu("&View")
        select_columns_action = QAction("&Select Columns...", self)
        select_columns_action.triggered.connect(self.open_column_selection_dialog)
        view_menu.addAction(select_columns_action)
        view_menu.addSeparator()
        dashboard_action = QAction("Show Dashboard...", self)
        dashboard_action.triggered.connect(self.show_dashboard)
        view_menu.addAction(dashboard_action)
        tools_menu = menu_bar.addMenu("&Tools")
        query_builder_action = QAction("Advanced Filter...", self)
        query_builder_action.triggered.connect(self.open_query_builder)
        tools_menu.addAction(query_builder_action)
        clear_filter_action = QAction("Clear Advanced Filter", self)
        clear_filter_action.triggered.connect(self.clear_advanced_filter)
        tools_menu.addAction(clear_filter_action)
        tools_menu.addSeparator()
        
        # ⭐️ 1. 여기서는 빈 하위 메뉴만 생성합니다.
        self.scenario_menu = tools_menu.addMenu("Run Scenario Validation")

        # ⭐️ 2. `populate_scenario_menu` 직접 호출을 삭제하고,
        #         메뉴가 열리기 직전에 호출되도록 시그널에 연결합니다.
        tools_menu.aboutToShow.connect(self.populate_scenario_menu)

        browse_scenarios_action = QAction("Browse Scenarios...", self)
        browse_scenarios_action.triggered.connect(self.open_scenario_browser)
        tools_menu.addAction(browse_scenarios_action)
        tools_menu.addSeparator()
        script_editor_action = QAction("Analysis Script Editor...", self)
        script_editor_action.triggered.connect(self.open_script_editor)
        tools_menu.addAction(script_editor_action)

                # ⭐️ 1. Help 메뉴 추가
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About...", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def populate_scenario_menu(self):
        # ... (이전과 동일)
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
                    action.triggered.connect(lambda checked, s_name=name: self.run_scenario_validation(s_name))
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
        source_model = self.proxy_model.sourceModel()
        if source_model is None or source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return
        
        # ⭐️ 3. 바쁜 커서(Busy Cursor) 적용
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result_text = self.controller.run_scenario_validation(scenario_name)
            
            result_dialog = QDialog(self)
            result_dialog.setWindowTitle("Scenario Validation Result")
            layout = QVBoxLayout(result_dialog)
            text_browser = QTextBrowser()
            text_browser.setText(result_text)
            text_browser.setFontFamily("Courier New")
            layout.addWidget(text_browser)
            result_dialog.resize(700, 350)
            result_dialog.exec()
        finally:
            QApplication.restoreOverrideCursor() # 작업 완료 후 커서 복원
    # ⭐️ --- 이 메서드가 누락되었습니다 --- ⭐️
    def open_scenario_browser(self):
        """시나리오 브라우저 다이얼로그를 엽니다."""
        all_scenarios = self.controller.load_all_scenarios()
        dialog = ScenarioBrowserDialog(all_scenarios, self)
        dialog.exec()
    def open_log_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Log File", "", "CSV Files (*.csv);;All Files (*)")
        if filepath:
            source_model = self.proxy_model.sourceModel()
            if source_model:
                source_model.clear_highlights()
            
            # ⭐️ 3. 바쁜 커서(Busy Cursor) 적용
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.statusBar().showMessage(f"Loading {os.path.basename(filepath)}...")
            try:
                success = self.controller.load_log_file(filepath)
                if not success:
                    # ⭐️ 4. 일관성 있는 알림 문구로 수정
                    QMessageBox.warning(self, "Load Failed", "No data could be parsed from the selected file.")
                else:
                    print(f"Successfully loaded file: {filepath}")
                    self.populate_scenario_menu()
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"An error occurred while opening the file:\n{e}")
            finally:
                QApplication.restoreOverrideCursor() # 작업 완료 후 커서 복원

    def open_query_builder(self):
        source_model = self.proxy_model.sourceModel()
        if source_model is None or source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return
            
        column_names = [source_model.headerData(i, Qt.Orientation.Horizontal) for i in range(source_model.columnCount())]
        date_columns = ['SystemDate']
        saved_filters = self.controller.load_filters()
        dialog = QueryBuilderDialog(column_names, date_columns, saved_filters, self.last_query_data, self)
        
        if dialog.exec():
            query_data = dialog.get_query_data()
            
            # ⭐️ 3. 바쁜 커서(Busy Cursor) 적용
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self.controller.apply_advanced_filter(query_data)
                self.last_query_data = query_data
                # ⭐️ 2. 상태 표시줄 메시지 업데이트
                self.statusBar().showMessage(f"Filter applied. Showing {self.proxy_model.rowCount():,} of {self.proxy_model.sourceModel().rowCount():,} rows.")
            finally:
                QApplication.restoreOverrideCursor()
        
        for name, query in dialog.saved_filters.items():
            self.controller.save_filter(name, query)

    def clear_advanced_filter(self):
        source_model = self.proxy_model.sourceModel()
        if source_model:
            source_model.clear_highlights()
        self.controller.clear_advanced_filter()
        self.last_query_data = None
        # ⭐️ 2. 상태 표시줄 메시지 업데이트
        if source_model:
            self.statusBar().showMessage(f"Filter cleared. Showing {source_model.rowCount():,} rows.")
        print("Advanced filter cleared.")
        
    def show_dashboard(self):
        source_model = self.proxy_model.sourceModel()
        if source_model is None or source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return
        
        self.dashboard_dialog = DashboardDialog(source_model._data, self)
        self.dashboard_dialog.exec()

    def show_table_context_menu(self, pos):
        selected_indexes = self.tableView.selectedIndexes()
        menu = QMenu(self)
        source_model = self.proxy_model.sourceModel()

        if selected_indexes and source_model:
            source_index = self.proxy_model.mapToSource(selected_indexes[0])
            show_detail_action = QAction("상세 로그 보기", self)
            show_detail_action.triggered.connect(self.show_detail_pane)
            menu.addAction(show_detail_action)
            
            tracking_id = source_model.get_data_by_col_name(source_index.row(), "TrackingID")
            if tracking_id and str(tracking_id).strip():
                menu.addSeparator()
                trace_action = QAction(f"Trace Event Flow: '{tracking_id}'", self)
                trace_action.triggered.connect(lambda: self.start_event_trace(str(tracking_id)))
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
            menu.exec_(self.tableView.viewport().mapToGlobal(pos))

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

    def start_event_trace(self, trace_id):
        trace_data = self.controller.get_trace_data(trace_id)
        if trace_data.empty:
            QMessageBox.information(self, "Trace Result", f"No logs found containing ID: '{trace_id}'")
            return
        self.trace_dialog = TraceDialog(trace_data, trace_id, self)
        self.trace_dialog.exec()

    def _display_log_detail(self, source_index):
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
            print(f"Error displaying detail: {e}")

    def show_detail_pane(self):
        selected_indexes = self.tableView.selectedIndexes()
        if not selected_indexes: return
        source_index = self.proxy_model.mapToSource(selected_indexes[0])
        self._display_log_detail(source_index)
        if not self.detail_view.isVisible():
            self.detail_view.setVisible(True)
            self.splitter.setSizes([self.width() * 0.6, self.width() * 0.4])

    def update_detail_view(self):
        if not self.detail_view.isVisible(): return
        selected_indexes = self.tableView.selectedIndexes()
        if not selected_indexes:
            self.detail_view.clear()
            return
        source_index = self.proxy_model.mapToSource(selected_indexes[0])
        self._display_log_detail(source_index)
        
    def hide_detail_pane(self):
        self.detail_view.setVisible(False)
        self.splitter.setSizes([1, 0])

    def open_column_selection_dialog(self):
        source_model = self.proxy_model.sourceModel()
        if source_model is None or source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return
            
        all_columns = [source_model.headerData(i, Qt.Orientation.Horizontal) for i in range(source_model.columnCount())]
        visible_columns = [col for i, col in enumerate(all_columns) if not self.tableView.isColumnHidden(i)]
        self.col_dialog = ColumnSelectionDialog(all_columns, visible_columns, self)
        if self.col_dialog.exec():
            new_visible_columns = self.col_dialog.get_selected_columns()
            for i, col_name in enumerate(all_columns):
                self.tableView.setColumnHidden(i, col_name not in new_visible_columns)

    def apply_settings(self, source_model):
        if source_model is None: return
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    visible_columns = config.get('visible_columns', [])
                    all_columns = [source_model.headerData(i, Qt.Orientation.Horizontal) for i in range(source_model.columnCount())]
                    for i, col_name in enumerate(all_columns):
                        self.tableView.setColumnHidden(i, col_name not in visible_columns)
        except Exception as e:
            print(f"Could not load settings: {e}")
        
        for i in range(source_model.columnCount()):
            self.tableView.setColumnWidth(i, 80)

    def save_settings(self):
        source_model = self.proxy_model.sourceModel()
        if source_model is None or source_model._data.empty: return

        all_columns = [source_model.headerData(i, Qt.Orientation.Horizontal) for i in range(source_model.columnCount())]
        visible_columns = [col for i, col in enumerate(all_columns) if not self.tableView.isColumnHidden(i)]
        config = {'visible_columns': visible_columns}
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Could not save settings: {e}")
            
    def closeEvent(self, event):
        self.save_settings()
        event.accept()

    def open_script_editor(self):
        source_model = self.proxy_model.sourceModel()
        if source_model is None or source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return

        current_view_df = source_model._data.iloc[
            [self.proxy_model.mapToSource(self.proxy_model.index(r,0)).row() for r in range(self.proxy_model.rowCount())]
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
                df_dialog = TraceDialog(result_obj.new_dataframe, result_obj.new_df_title, self)
                df_dialog.exec()
            
            source_model = self.proxy_model.sourceModel()
            if source_model:
                source_model.set_highlights(result_obj.markers)

        dialog.run_script_requested.connect(handle_run_request)
        dialog.exec()

    def show_about_dialog(self):
        """프로그램 정보 대화상자를 표시합니다."""
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
        """앱 모드에 따라 UI 요소를 설정합니다."""
        if self.controller.mode == 'realtime':
            self.db_connect_button.setVisible(True)
            self.filter_input.setVisible(False)
            self.setWindowTitle(f"Log Analyzer - [DB: {self.controller.connection_name}]")
            self.statusBar().showMessage("Ready to connect to the database.")
        else: # file mode
            self.db_connect_button.setVisible(False)
            self.filter_input.setVisible(True)
            self.setWindowTitle("Log Analyzer - [File Mode]")
            self.statusBar().showMessage("Ready. Please open a log file.")

    def start_db_connection(self):
        """사전 필터 UI를 열고 DB 조회를 시작합니다."""
        # TODO: Step 5에서 구현 - 사전 필터 다이얼로그 열기
        query_conditions = {} # 지금은 빈 조건으로 테스트
        
        self.controller.start_db_fetch(query_conditions)
        self.db_connect_button.setEnabled(False)
        self.db_connect_button.setText("⏳ Loading...")

    def on_fetch_progress(self, message):
        """Worker가 보내는 진행 상황을 상태 표시줄에 표시합니다."""
        self.statusBar().showMessage(message)

    def on_fetch_complete(self):
        """Worker의 작업 완료 신호를 받아 버튼 상태를 복원합니다."""
        self.db_connect_button.setEnabled(True)
        self.db_connect_button.setText("📡 데이터베이스에 연결하여 로그 조회")
        total_rows = self.proxy_model.sourceModel().rowCount()
        self.statusBar().showMessage(f"Local cache contains {total_rows:,} logs.")