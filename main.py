import sys
import json
import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableView, QFileDialog, QMessageBox
)
from PySide6.QtGui import QAction

# 새로 만든 대화상자 클래스를 임포트합니다.
from ColumnSelectionDialog import ColumnSelectionDialog
from LogTableModel import LogTableModel
from universal_parser import parse_log_with_profile

# ⭐️ 설정 파일 경로를 상수로 정의
CONFIG_FILE = 'config.json'

class LogAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Log Analyzer")
        self.setGeometry(100, 100, 1200, 800)

        self.tableView = QTableView(self)
        self.tableView.setSortingEnabled(True)
        self.tableView.setAlternatingRowColors(True)

        self.tableModel = LogTableModel()
        self.tableView.setModel(self.tableModel)
        self.setCentralWidget(self.tableView)
        
        self._create_menu()
        
        # ⭐️ 우클릭 메뉴 관련 코드는 삭제합니다.

    def _create_menu(self):
        menu_bar = self.menuBar()
        
        # --- File Menu ---
        file_menu = menu_bar.addMenu("&File")
        open_action = QAction("&Open Log File...", self)
        open_action.triggered.connect(self.open_log_file)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # ⭐️ --- View Menu ---
        view_menu = menu_bar.addMenu("&View")
        select_columns_action = QAction("&Select Columns...", self)
        select_columns_action.triggered.connect(self.open_column_selection_dialog)
        view_menu.addAction(select_columns_action)

    def open_column_selection_dialog(self):
        """컬럼 선택 대화상자를 열고, 결과를 테이블에 반영합니다."""
        if self.tableModel.columnCount() == 0:
            QMessageBox.information(self, "Info", "Please load a log file first.")
            return

        all_columns = [self.tableModel.headerData(i, Qt.Orientation.Horizontal) for i in range(self.tableModel.columnCount())]
        visible_columns = [col for i, col in enumerate(all_columns) if not self.tableView.isColumnHidden(i)]
        
        dialog = ColumnSelectionDialog(all_columns, visible_columns, self)
        if dialog.exec():
            new_visible_columns = dialog.get_selected_columns()
            for i, col_name in enumerate(all_columns):
                if col_name in new_visible_columns:
                    self.tableView.setColumnHidden(i, False)
                else:
                    self.tableView.setColumnHidden(i, True)

    def apply_settings(self):
        """설정 파일에서 컬럼 가시성을 불러와 적용하고, 컬럼 너비를 조정합니다."""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    visible_columns = config.get('visible_columns', [])
                    
                    all_columns = [self.tableModel.headerData(i, Qt.Orientation.Horizontal) for i in range(self.tableModel.columnCount())]
                    for i, col_name in enumerate(all_columns):
                        if col_name in visible_columns:
                            self.tableView.setColumnHidden(i, False)
                        else:
                            self.tableView.setColumnHidden(i, True)
        except Exception as e:
            print(f"Could not load settings: {e}")

        # ⭐️ 모든 컬럼의 너비를 좁은 기본값(80px)으로 설정
        for i in range(self.tableModel.columnCount()):
            self.tableView.setColumnWidth(i, 80)

    def save_settings(self):
        """현재 컬럼 가시성 상태를 파일에 저장합니다."""
        if self.tableModel.columnCount() == 0:
            return # 저장할 데이터가 없으면 종료
        
        all_columns = [self.tableModel.headerData(i, Qt.Orientation.Horizontal) for i in range(self.tableModel.columnCount())]
        visible_columns = [col for i, col in enumerate(all_columns) if not self.tableView.isColumnHidden(i)]
        
        config = {'visible_columns': visible_columns}
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Could not save settings: {e}")

    def closeEvent(self, event):
        """애플리케이션이 닫힐 때 설정을 저장합니다."""
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
                
                self.tableModel.update_data(parsed_data)
                
                # ⭐️ 데이터 로드 후, 저장된 설정 적용 및 컬럼 너비 조정
                self.apply_settings()
                
                print(f"Successfully loaded and parsed {len(parsed_data)} entries.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LogAnalyzerApp()
    window.show()
    sys.exit(app.exec())