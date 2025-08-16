import sys
import json
import os
import re
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableView, QFileDialog, QMessageBox, QMenu,
    QWidget, QVBoxLayout, QLineEdit, QSplitter, QTextEdit
)
from PySide6.QtGui import QAction

from DashboardDialog import DashboardDialog
from VisualizationDialog import VisualizationDialog
from TraceDialog import TraceDialog
from ColumnSelectionDialog import ColumnSelectionDialog
from LogTableModel import LogTableModel
from universal_parser import parse_log_with_profile

CONFIG_FILE = 'config.json'

class LogAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Log Analyzer")
        self.setGeometry(100, 100, 1200, 800)

        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        
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

        self.source_model = LogTableModel()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(-1) 
        
        self.tableView.setModel(self.proxy_model)

        self.filter_input.textChanged.connect(self.proxy_model.setFilterFixedString)
        self.tableView.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tableView.customContextMenuRequested.connect(self.show_table_context_menu)
        
        self.tableView.selectionModel().selectionChanged.connect(self.update_detail_view)

        self.setCentralWidget(main_widget)
        self._create_menu()
        
    def _create_menu(self):
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

    def show_dashboard(self):
        """데이터 대시보드 다이얼로그를 엽니다."""
        if self.source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return
        
        self.dashboard_dialog = DashboardDialog(self.source_model._data, self)
        self.dashboard_dialog.exec()

    def show_table_context_menu(self, pos):
        selected_indexes = self.tableView.selectedIndexes()
        menu = QMenu(self)

        if selected_indexes:
            source_index = self.proxy_model.mapToSource(selected_indexes[0])
            
            show_detail_action = QAction("상세 로그 보기", self)
            show_detail_action.triggered.connect(self.show_detail_pane)
            menu.addAction(show_detail_action)
            
            tracking_id = self.source_model.get_data_by_col_name(source_index.row(), "TrackingID")
            if tracking_id and tracking_id.strip():
                menu.addSeparator()
                
                trace_action = QAction(f"Trace Event Flow: '{tracking_id}'", self)
                trace_action.triggered.connect(lambda: self.start_event_trace(tracking_id))
                menu.addAction(trace_action)

                visualize_action = QAction(f"Visualize SECS Scenario for '{tracking_id}'", self)
                visualize_action.triggered.connect(lambda: self.visualize_secs_scenario(tracking_id))
                menu.addAction(visualize_action)

        if self.detail_view.isVisible():
            if menu.actions() and not menu.actions()[-1].isSeparator(): menu.addSeparator()
            hide_detail_action = QAction("원복", self)
            hide_detail_action.triggered.connect(self.hide_detail_pane)
            menu.addAction(hide_detail_action)
        
        if menu.actions():
            menu.exec_(self.tableView.viewport().mapToGlobal(pos))

    def visualize_secs_scenario(self, trace_id):
        df = self.source_model._data
        mask = df.apply(lambda r: r.astype(str).str.contains(trace_id, case=False, na=False).any(), axis=1)
        scenario_df = df[mask]
        
        com_logs = scenario_df[scenario_df['Category'].str.replace('"', '') == 'Com'].sort_values(by='SystemDate')

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
        df = self.source_model._data
        mask = df.apply(lambda r: r.astype(str).str.contains(trace_id, case=False, na=False).any(), axis=1)
        trace_data = df[mask]
        if trace_data.empty:
            QMessageBox.information(self, "Trace Result", f"No logs found containing ID: '{trace_id}'")
            return
        self.trace_dialog = TraceDialog(trace_data, trace_id, self)
        self.trace_dialog.exec()

    def _display_log_detail(self, source_index):
        try:
            category = self.source_model.get_data_by_col_name(source_index.row(), "Category")
            
            display_object = self.source_model.get_data_by_col_name(source_index.row(), "ParsedBodyObject")
            
            if display_object is None:
                 display_object = self.source_model.get_data_by_col_name(source_index.row(), "AsciiData")

            if display_object:
                if isinstance(display_object, dict):
                    formatted_text = json.dumps(display_object, indent=4, ensure_ascii=False)
                    self.detail_view.setText(formatted_text)
                elif isinstance(display_object, list):
                    def format_secs_obj(obj, indent=0):
                        lines = []
                        indent_str = "    " * indent
                        for item in obj:
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
        if self.source_model._data.empty:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return
        all_columns = [self.source_model.headerData(i, Qt.Orientation.Horizontal) for i in range(self.source_model.columnCount())]
        visible_columns = [col for i, col in enumerate(all_columns) if not self.tableView.isColumnHidden(i)]
        self.col_dialog = ColumnSelectionDialog(all_columns, visible_columns, self)
        if self.col_dialog.exec():
            new_visible_columns = self.col_dialog.get_selected_columns()
            for i, col_name in enumerate(all_columns):
                self.tableView.setColumnHidden(i, col_name not in new_visible_columns)

    def apply_settings(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    visible_columns = config.get('visible_columns', [])
                    all_columns = [self.source_model.headerData(i, Qt.Orientation.Horizontal) for i in range(self.source_model.columnCount())]
                    for i, col_name in enumerate(all_columns):
                        self.tableView.setColumnHidden(i, col_name not in visible_columns)
        except Exception as e:
            print(f"Could not load settings: {e}")
        for i in range(self.source_model.columnCount()):
            self.tableView.setColumnWidth(i, 80)

    def save_settings(self):
        if self.source_model._data.empty: return
        all_columns = [self.source_model.headerData(i, Qt.Orientation.Horizontal) for i in range(self.source_model.columnCount())]
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

    def open_log_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Log File", "", "CSV Files (*.csv);;All Files (*)")
        if filepath:
            try:
                profile = {
                    'column_mapping': {'Category': 'Category', 'AsciiData': 'AsciiData', 'BinaryData': 'BinaryData'},
                    'type_rules': [{'value': 'Com', 'type': 'secs'}, {'value': 'Info', 'type': 'json'}]
                }
                parsed_data = parse_log_with_profile(filepath, profile)
                if not parsed_data:
                    QMessageBox.warning(self, "Warning", "No data could be parsed from the file.")
                    return
                self.source_model.update_data(parsed_data)
                self.apply_settings()
                print(f"Successfully loaded and parsed {len(parsed_data)} entries.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LogAnalyzerApp()
    window.show()
    sys.exit(app.exec())