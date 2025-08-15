import sys
import json
import os
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableView, QFileDialog, QMessageBox, QMenu,
    QWidget, QVBoxLayout, QLineEdit
)
from PySide6.QtGui import QAction

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

        self.tableView = QTableView(self)
        self.tableView.setSortingEnabled(True)
        self.tableView.setAlternatingRowColors(True)
        layout.addWidget(self.tableView)

        self.source_model = LogTableModel()
        
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.source_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        
        # ⭐️ 이 한 줄을 추가하여 모든 컬럼에서 검색하도록 설정합니다.
        self.proxy_model.setFilterKeyColumn(-1) 
        
        self.tableView.setModel(self.proxy_model)

        self.filter_input.textChanged.connect(self.proxy_model.setFilterFixedString)

        self.setCentralWidget(main_widget)
        self._create_menu()
        
    # 이하 다른 메서드들은 이전과 동일합니다.
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

    def open_column_selection_dialog(self):
        if self.source_model.columnCount() == 0:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return
        all_columns = [self.source_model.headerData(i, Qt.Orientation.Horizontal) for i in range(self.source_model.columnCount())]
        visible_columns = [col for i, col in enumerate(all_columns) if not self.tableView.isColumnHidden(i)]
        dialog = ColumnSelectionDialog(all_columns, visible_columns, self)
        if dialog.exec():
            new_visible_columns = dialog.get_selected_columns()
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
        if self.source_model.columnCount() == 0: return
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