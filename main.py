import sys
from PySide6.QtWidgets import QApplication

# 필요한 모든 클래스를 main.py에서 직접 import합니다.
from app_controller import AppController
from main_window import MainWindow
from dialogs.ModeSelectionDialog import ModeSelectionDialog
from dialogs.ConnectionManagerDialog import ConnectionManagerDialog

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 1. 모드 선택 대화상자를 실행합니다.
    mode_dialog = ModeSelectionDialog()
    if not mode_dialog.exec():
        sys.exit() # 사용자가 모드 선택을 취소하면 프로그램 종료

    app_mode = mode_dialog.selected_mode
    print(f"'{app_mode.upper()}' 모드로 애플리케이션을 시작합니다.")

    controller = None
    conn_name = None
    conn_info = None

    # 2. 모드에 따라 컨트롤러를 설정합니다.
    if app_mode == 'file':
        controller = AppController(app_mode=app_mode)
    
    elif app_mode == 'realtime':
        conn_manager = ConnectionManagerDialog()
        if conn_manager.exec():
            conn_name, conn_info = conn_manager.get_selected_connection()
            if conn_name and conn_info:
                print(f"Connecting to '{conn_name}'...")
                controller = AppController(
                    app_mode=app_mode, 
                    connection_name=conn_name, 
                    connection_info=conn_info
                )
            else:
                print("연결이 선택되지 않았습니다. 프로그램을 종료합니다.")
                sys.exit()
        else:
            print("연결이 취소되었습니다. 프로그램을 종료합니다.")
            sys.exit()

    # 3. 컨트롤러가 성공적으로 생성되었을 경우에만 윈도우를 생성하고 실행합니다.
    if controller:
        # MainWindow를 생성하면서 컨트롤러를 전달합니다.
        main_win = MainWindow(controller)
        
        # 윈도우를 화면에 보여줍니다.
        main_win.show()
        
        # 애플리케이션 이벤트 루프를 시작합니다.
        sys.exit(app.exec())
