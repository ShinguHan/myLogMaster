import sys
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QTableView, 
                               QStatusBar, QApplication, QMenuBar, QProgressBar)
from PySide6.QtGui import QAction, QCursor
from PySide6.QtCore import Qt

from app_controller import AppController
# 다른 필요한 dialog들도 import 합니다.
from dialogs.QueryConditionsDialog import QueryConditionsDialog 

class MainWindow(QMainWindow):
    def __init__(self, controller: AppController):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("My Log Master v2.0")
        self.setGeometry(100, 100, 1200, 800)

        self.init_ui()
        self.create_actions()
        self.create_menus()
        
        # --- 중요: 컨트롤러의 시그널을 UI 슬롯에 연결 ---
        self.connect_signals()

        # 실시간 모드일 경우, 자동으로 DB 연결 시작
        if self.controller.app_mode == 'REALTIME':
            self.start_db_connection()

    def init_ui(self):
        """UI 위젯들을 초기화하고 배치합니다."""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        layout = QVBoxLayout(main_widget)
        
        self.log_table_view = QTableView()
        self.log_table_view.setSortingEnabled(True)
        layout.addWidget(self.log_table_view)
        
        # 상태바 설정
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

    def create_actions(self):
        """메뉴바에서 사용할 액션들을 생성합니다."""
        self.open_file_action = QAction("Open Log File...", self)
        self.open_file_action.triggered.connect(self.open_log_file)
        
        self.connect_db_action = QAction("Connect to DB...", self)
        self.connect_db_action.triggered.connect(self.start_db_connection)

    def create_menus(self):
        """메뉴바를 생성합니다."""
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction(self.open_file_action)

        db_menu = menu_bar.addMenu("Database")
        db_menu.addAction(self.connect_db_action)

    def connect_signals(self):
        """컨트롤러의 시그널을 이 클래스의 슬롯 메서드에 연결합니다."""
        # 모델 데이터가 업데이트되면, 테이블 뷰를 새로운 모델로 설정하는 슬롯에 연결
        self.controller.model_updated.connect(self.on_model_updated)
        
        # 상태 메시지가 업데이트되면, 상태바에 메시지를 표시하는 슬롯에 연결
        self.controller.status_updated.connect(self.on_status_updated)
        
        # 데이터 로딩이 완료되면, 대기 상태를 해제하는 슬롯에 연결
        self.controller.fetch_completed.connect(self.on_task_finished)

    # --- 아래부터는 컨트롤러의 신호를 받아 UI를 변경하는 '슬롯(Slot)' 메서드들 ---

    def on_model_updated(self, model):
        """컨트롤러로부터 새 모델을 받아 테이블 뷰에 설정합니다."""
        self.log_table_view.setModel(model)
        self.status_bar.showMessage(f"Log view updated. Total {model.rowCount()} rows.", 5000)
        print(f"UI Updated: Table view now has {model.rowCount()} rows.")

    def on_status_updated(self, message):
        """상태바 메시지를 업데이트합니다."""
        self.status_bar.showMessage(message)

    def on_task_started(self, message="Processing..."):
        """시간이 걸리는 작업 시작 시 UI를 대기 상태로 변경합니다."""
        self.status_bar.showMessage(message)
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

    def on_task_finished(self):
        """작업 완료 시 UI를 정상 상태로 되돌립니다."""
        self.status_bar.showMessage("Task finished.", 5000)
        QApplication.restoreOverrideCursor()

    # --- 사용자 액션에 의해 호출되는 메서드들 ---

    def open_log_file(self):
        # 이 부분은 기존 로직을 그대로 사용하거나 컨트롤러를 통해 파일 열기를 요청합니다.
        # 예: self.controller.load_log_file(filepath)
        pass

    def start_db_connection(self):
        """데이터베이스 연결 및 데이터 로딩을 시작합니다."""
        dialog = QueryConditionsDialog(self)
        if dialog.exec():
            query_conditions = dialog.get_conditions()
            self.on_task_started("Fetching data from database...")
            self.controller.start_db_fetch(query_conditions)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # AppController 인스턴스 생성 (실제 모드에 맞게 수정 필요)
    controller = AppController(app_mode='REALTIME', connection_name='aaa')
    main_win = MainWindow(controller)
    main_win.show()
    sys.exit(app.exec())