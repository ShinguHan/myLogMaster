import sys
import json
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, QApplication,
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QStatusBar, QLineEdit
)
from PySide6.QtGui import QAction, QActionGroup
from functools import partial

from app_controller import AppController
from widgets.base_log_viewer import BaseLogViewerWidget
from dialogs.ui_components import create_action_button
from dialogs.HighlightingDialog import HighlightingDialog

class MainWindow(QMainWindow):
    def __init__(self, controller: AppController):
        super().__init__()
        self.controller = controller
        self._is_fetching = False

        self.setWindowTitle("Log Analyzer")
        self.setGeometry(100, 100, 1200, 800)

        self._init_ui()
        self._create_menu()
        self.connect_signals()
        self.setup_ui_for_mode()
        
        # 초기 모델 설정 (Controller가 데이터를 로드한 후 호출됨)
        self.log_viewer.update_table_model(self.controller.source_model)

    def _init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        self.db_connect_button = create_action_button("📡 데이터베이스에 연결하여 로그 조회")
        layout.addWidget(self.db_connect_button)
        
        # 💥 변경점: 필터 바를 MainWindow에서 직접 생성
        filter_layout = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter logs (case-insensitive)...")
        filter_layout.addWidget(self.filter_input)
        
        self.auto_scroll_checkbox = QCheckBox("Auto Scroll to Bottom")
        self.auto_scroll_checkbox.setChecked(True)
        filter_layout.addWidget(self.auto_scroll_checkbox)
        
        # 필터 바를 메인 레이아웃에 추가
        layout.addLayout(filter_layout)
        
        # BaseLogViewerWidget 생성 (이제 필터 바를 만들지 않음)
        self.log_viewer = BaseLogViewerWidget(self.controller, self)
        layout.addWidget(self.log_viewer)

        self.setCentralWidget(main_widget)
        self.setStatusBar(QStatusBar())

    def connect_signals(self):
        # 컨트롤러 신호 연결
        self.controller.model_updated.connect(self.log_viewer.update_table_model)
        self.controller.fetch_progress.connect(self.on_fetch_progress)
        self.controller.fetch_completed.connect(self.on_fetch_complete)
        self.controller.row_count_updated.connect(self._update_row_count_status)
        self.controller.fetch_error.connect(self.on_fetch_error)
        
        # UI 위젯 신호 연결
        self.db_connect_button.clicked.connect(self.start_db_connection)
        self.log_viewer.trace_requested.connect(self.log_viewer.start_event_trace)
        # 💥 변경점: MainWindow의 필터 입력을 log_viewer의 프록시 모델에 연결
        self.filter_input.textChanged.connect(self.log_viewer.proxy_model.setFilterFixedString)

    def _create_menu(self):
        menu_bar = self.menuBar()
        
        # File Menu
        file_menu = menu_bar.addMenu("&File")
        open_action = QAction("&Open Log File...", self)
        open_action.triggered.connect(self.log_viewer.open_log_file)
        file_menu.addAction(open_action)
        self.save_action = QAction("&Save View as CSV...", self)
        self.save_action.triggered.connect(self.log_viewer.save_log_file)
        self.save_action.setEnabled(False)
        file_menu.addAction(self.save_action)
        file_menu.addSeparator()
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View Menu
        view_menu = menu_bar.addMenu("&View")
        theme_menu = view_menu.addMenu("Theme")
        theme_group = QActionGroup(self)
        themes = ["light", "dark", "dracula", "solarized"] 
        for theme in themes:
            action = QAction(theme.capitalize(), self, checkable=True)
            action.triggered.connect(partial(self._apply_theme, theme))
            theme_group.addAction(action)
            theme_menu.addAction(action)
            if self.controller.get_current_theme() == theme:
                action.setChecked(True)
        view_menu.addSeparator()
        select_columns_action = QAction("&Select Columns...", self)
        select_columns_action.triggered.connect(self.log_viewer.open_column_selection_dialog)
        view_menu.addAction(select_columns_action)
        view_menu.addSeparator()
        dashboard_action = QAction("Show Dashboard...", self)
        dashboard_action.triggered.connect(self.log_viewer.show_dashboard)
        view_menu.addAction(dashboard_action)

        # Tools Menu
        tools_menu = menu_bar.addMenu("&Tools")
        query_builder_action = QAction("Advanced Filter...", self)
        query_builder_action.triggered.connect(self.log_viewer.open_query_builder)
        tools_menu.addAction(query_builder_action)
        clear_filter_action = QAction("Clear Advanced Filter", self)
        clear_filter_action.triggered.connect(self.log_viewer.clear_advanced_filter)
        tools_menu.addAction(clear_filter_action)
        tools_menu.addSeparator()
        
        self.scenario_menu = tools_menu.addMenu("Run Scenario Validation")
        tools_menu.aboutToShow.connect(self._populate_scenario_menu)

        browse_scenarios_action = QAction("Browse Scenarios...", self)
        browse_scenarios_action.triggered.connect(self.log_viewer.open_scenario_browser)
        tools_menu.addAction(browse_scenarios_action)
        tools_menu.addSeparator()
        script_editor_action = QAction("Analysis Script Editor...", self)
        script_editor_action.triggered.connect(self.log_viewer.open_script_editor)
        tools_menu.addAction(script_editor_action)
        tools_menu.addSeparator()
        highlighting_action = QAction("Conditional Highlighting...", self)
        highlighting_action.triggered.connect(self.open_highlighting_dialog)
        tools_menu.addAction(highlighting_action)
        tools_menu.addSeparator()
        history_action = QAction("Validation History...", self)
        history_action.triggered.connect(self.log_viewer.open_history_browser)
        tools_menu.addAction(history_action)

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About...", self)
        about_action.triggered.connect(lambda: QMessageBox.about(self, "About Log Analyzer", "Version 1.0"))
        help_menu.addAction(about_action)
    
    def _populate_scenario_menu(self):
        self.scenario_menu.clear()
        run_all_action = QAction("Run All Scenarios", self)
        run_all_action.triggered.connect(lambda: self.log_viewer.run_scenario_validation(None))
        self.scenario_menu.addAction(run_all_action)
        self.scenario_menu.addSeparator()
        
        scenario_names = self.controller.get_scenario_names()
        if scenario_names:
            for name in scenario_names:
                action = QAction(name, self)
                action.triggered.connect(partial(self.log_viewer.run_scenario_validation, name))
                self.scenario_menu.addAction(action)
        else:
            action = QAction("No scenarios enabled", self); action.setEnabled(False)
            self.scenario_menu.addAction(action)

    def setup_ui_for_mode(self):
        is_realtime = self.controller.mode == 'realtime'
        self.db_connect_button.setVisible(is_realtime)
        self.filter_input.setVisible(not is_realtime)
        self.auto_scroll_checkbox.setVisible(is_realtime)
        mode_title = f"[DB: {self.controller.connection_name}]" if is_realtime else "[File Mode]"
        self.setWindowTitle(f"Log Analyzer - {mode_title}")

    def open_highlighting_dialog(self):
        source_model = self.log_viewer.source_model()
        if not source_model or source_model._data.empty: return
        rules_data = self.controller.get_highlighting_rules()
        column_names = source_model._data.columns.tolist()
        dialog = HighlightingDialog(column_names, rules_data, self)
        dialog.rules_updated.connect(self.controller.set_and_save_highlighting_rules)
        dialog.show()

    def start_db_connection(self):
        from dialogs.QueryConditionsDialog import QueryConditionsDialog
        if self._is_fetching:
            self.controller.cancel_db_fetch()
        else:
            dialog = QueryConditionsDialog(self)
            if dialog.exec():
                self._is_fetching = True
                self.db_connect_button.setText("❌ 데이터 수신 중단")
                self.db_connect_button.setStyleSheet("background-color: #DA4453; color: white;")
                self.controller.start_db_fetch(dialog.get_conditions())
    
    def on_fetch_progress(self, message):
        self.statusBar().showMessage(message)

    def on_fetch_complete(self):
        self._is_fetching = False
        self.db_connect_button.setText("📡 데이터베이스에 연결하여 로그 조회")
        self.db_connect_button.setStyleSheet("")
        
    def _update_row_count_status(self, row_count):
        self.statusBar().showMessage(f"Receiving... {row_count:,} rows")
        if self.auto_scroll_checkbox.isChecked():
            QTimer.singleShot(0, self.log_viewer.tableView.scrollToBottom)

    def on_fetch_error(self, error_message):
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_message}")
        self.on_fetch_complete()

    def apply_settings(self, source_model):
        visible_columns = self.controller.config.get('visible_columns', [])
        all_columns = [source_model.headerData(i, Qt.Horizontal) for i in range(source_model.columnCount())]
        for i, col_name in enumerate(all_columns):
            self.log_viewer.tableView.setColumnHidden(i, visible_columns and col_name not in visible_columns)

    def save_settings(self):
        source_model = self.log_viewer.source_model()
        if source_model and not source_model._data.empty:
            all_cols = [source_model.headerData(i, Qt.Horizontal) for i in range(source_model.columnCount())]
            self.controller.config['visible_columns'] = [c for i, c in enumerate(all_cols) if not self.log_viewer.tableView.isColumnHidden(i)]
            self.controller.save_config()
            
    def closeEvent(self, event):
        self.save_settings()
        event.accept()
        
    def _apply_theme(self, theme_name):
        from main import apply_theme
        if apply_theme(QApplication.instance(), theme_name):
            self.controller.set_current_theme(theme_name)

