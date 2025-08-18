from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel, QFrame
from PySide6.QtCore import Qt, Signal

class ModeSelectionDialog(QDialog):
    # 사용자가 선택한 모드를 부모에게 알리는 시그널
    # 'file' 또는 'realtime' 문자열을 전달합니다.
    mode_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("작업 모드 선택")
        self.setModal(True) # 다른 창을 클릭할 수 없도록 설정
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        title_label = QLabel("어떤 작업을 시작하시겠습니까?")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        main_layout.addWidget(title_label)
        
        # --- 파일 분석 모드 버튼 ---
        file_button = QPushButton("📂  내 PC의 로그 파일 분석")
        file_button.setMinimumHeight(60)
        file_button.setStyleSheet("font-size: 14px; text-align: left; padding-left: 10px;")
        file_button.clicked.connect(lambda: self.select_mode('file'))
        main_layout.addWidget(file_button)
        
        file_desc = QLabel("- 저장된 CSV/LOG 파일을 열어 심층 분석을 수행합니다.")
        file_desc.setStyleSheet("color: gray; padding-left: 15px;")
        main_layout.addWidget(file_desc)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

        # --- 실시간 분석 모드 버튼 ---
        realtime_button = QPushButton("⚡  원격 DB 실시간 분석")
        realtime_button.setMinimumHeight(60)
        realtime_button.setStyleSheet("font-size: 14px; text-align: left; padding-left: 10px;")
        realtime_button.clicked.connect(lambda: self.select_mode('realtime'))
        main_layout.addWidget(realtime_button)

        realtime_desc = QLabel("- 원격 DB에 연결하여 실시간 로그를 모니터링합니다.")
        realtime_desc.setStyleSheet("color: gray; padding-left: 15px;")
        main_layout.addWidget(realtime_desc)
        
        self.resize(400, 300)

    def select_mode(self, mode):
        # ⭐️ 시그널을 보내는 대신, 선택된 모드를 인스턴스 변수에 저장합니다.
        self.selected_mode = mode
        self.accept() # 다이얼로그 닫기