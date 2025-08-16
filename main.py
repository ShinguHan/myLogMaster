import sys
from PySide6.QtWidgets import QApplication
from app_controller import AppController
from main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 컨트롤러와 메인 윈도우 생성
    controller = AppController()
    window = MainWindow(controller)
    
    # 컨트롤러의 데이터 변경 신호를 윈도우의 업데이트 슬롯에 연결
    controller.model_updated.connect(window.update_table_model)
    
    window.show()
    sys.exit(app.exec())