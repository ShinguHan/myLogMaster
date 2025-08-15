import sys
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableView, QFileDialog, QMessageBox
)
from PySide6.QtGui import QAction

from LogTableModel import LogTableModel
from universal_parser import parse_log_with_profile

class LogAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Log Analyzer")
        self.setGeometry(100, 100, 1200, 800)

        # 메인 테이블 뷰 설정
        self.tableView = QTableView(self)
        self.tableView.setSortingEnabled(True) # 정렬 기능 활성화
        self.tableView.setAlternatingRowColors(True) # 행 색상 번갈아 표시

        # 초기 빈 모델을 설정합니다.
        self.tableModel = LogTableModel()
        self.tableView.setModel(self.tableModel)
        self.setCentralWidget(self.tableView)
        
        self._create_menu()

    def _create_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")

        open_action = QAction("&Open Log File...", self)
        open_action.triggered.connect(self.open_log_file)
        file_menu.addAction(open_action)
        
        exit_action = QAction("&Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def open_log_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, 
            "Open Log File", 
            "", 
            "CSV Files (*.csv);;Log Files (*.log);;All Files (*)"
        )
        
        if filepath:
            try:
                # 파싱에 사용할 프로파일 정의
                # 이 부분은 나중에 UI에서 설정할 수 있도록 확장할 수 있습니다.
                profile = {
                    'column_mapping': {
                        'Category': 'Category',
                        'AsciiData': 'AsciiData',
                        'BinaryData': 'BinaryData'
                    },
                    'type_rules': [
                        {'value': 'Com', 'type': 'secs'},
                        # Info 로그에도 JSON이 있으므로, AsciiData 내용으로 JSON 여부 판단
                        {'value': 'Info', 'type': 'json'} 
                    ]
                }
                
                # 수정된 파서 실행
                parsed_data = parse_log_with_profile(filepath, profile)

                if not parsed_data:
                    QMessageBox.warning(self, "Warning", "No data could be parsed from the file.")
                    return

                # 모델에 데이터 업데이트
                self.tableModel.update_data(parsed_data)
                
                # 컬럼 너비 자동 조절
                self.tableView.resizeColumnsToContents()
                print(f"Successfully loaded and parsed {len(parsed_data)} entries.")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred while opening the file: {e}")
                print(f"Error: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LogAnalyzerApp()
    window.show()
    sys.exit(app.exec())