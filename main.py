import sys
from PySide6.QtWidgets import QApplication

from app_controller import AppController
from main_window import MainWindow
from dialogs.ModeSelectionDialog import ModeSelectionDialog
from dialogs.ConnectionManagerDialog import ConnectionManagerDialog # ⭐️ 임포트 추가

def launch_main_window(controller):
    """메인 윈도우를 생성하고 실행하는 헬퍼 함수"""
    window = MainWindow(controller)
    controller.model_updated.connect(window.update_table_model)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    mode_dialog = ModeSelectionDialog()
    
    if mode_dialog.exec():
        # ⭐️ 'mode_selected'가 아닌 'selected_mode' 변수를 읽어옵니다.
        app_mode = mode_dialog.selected_mode
        
        print(f"'{app_mode.upper()}' 모드로 애플리케이션을 시작합니다.")

        # ⭐️ 모드에 따라 실행 흐름 분기
        if app_mode == 'file':
            # ⭐️ 컨트롤러만 생성합니다.
            controller = AppController(app_mode=app_mode)
            # ⭐️ 컨트롤러가 관리하는 윈도우를 보여줍니다.
            controller.window.show()
            sys.exit(app.exec())
        
        # 실시간 모드 선택 시
        elif app_mode == 'realtime':
            conn_manager = ConnectionManagerDialog()
            if conn_manager.exec():
                conn_name, conn_info = conn_manager.get_selected_connection()
                
                if conn_name and conn_info:
                    print(f"Connecting to '{conn_name}'...")
                    controller = AppController(app_mode=app_mode, connection_name=conn_name, connection_info=conn_info)
                    # launch_main_window(controller) # 컨트롤러가 직접 윈도우를 생성하므로 주석 처리
                    controller.window.show()
                    sys.exit(app.exec())
                else:
                    print("연결이 선택되지 않았습니다. 프로그램을 종료합니다.")
            else:
                print("연결이 취소되었습니다. 프로그램을 종료합니다.")