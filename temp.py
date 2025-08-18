def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("데이터베이스 연결 관리자")
        self.setGeometry(200, 200, 600, 300)
        
        self.load_connections()

        main_layout = QHBoxLayout(self)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self.list_widget = QListWidget()
        left_layout.addWidget(QLabel("저장된 연결:"))
        left_layout.addWidget(self.list_widget)
        
        button_layout = QHBoxLayout()
        new_btn = QPushButton("신규")
        delete_btn = QPushButton("삭제")
        button_layout.addWidget(new_btn)
        button_layout.addWidget(delete_btn)
        left_layout.addLayout(button_layout)
        
        right_widget = QWidget()
        right_layout = QGridLayout(right_widget)
        self.conn_name_input = QLineEdit()
        self.user_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.dsn_input = QLineEdit()
        self.dsn_input.setPlaceholderText("예: server_ip:1521/SERVICE")
        
        right_layout.addWidget(QLabel("연결 이름:"), 0, 0)
        right_layout.addWidget(self.conn_name_input, 0, 1)
        right_layout.addWidget(QLabel("사용자 ID:"), 1, 0)
        right_layout.addWidget(self.user_input, 1, 1)
        right_layout.addWidget(QLabel("비밀번호:"), 2, 0)
        right_layout.addWidget(self.password_input, 2, 1)
        right_layout.addWidget(QLabel("DSN (주소):"), 3, 0)
        right_layout.addWidget(self.dsn_input, 3, 1)
        
        save_btn = QPushButton("변경 저장")
        right_layout.addWidget(save_btn, 4, 1)

        main_layout.addWidget(left_widget, 1)
        main_layout.addWidget(right_widget, 2)
        
        # ⭐️ 1. 하단 버튼 박스를 수정합니다.
        dialog_buttons = QDialogButtonBox()
        
        test_btn = QPushButton("연결 테스트")
        dialog_buttons.addButton(test_btn, QDialogButtonBox.ButtonRole.ActionRole)

        # OK 버튼을 '연결' 버튼으로 사용하고, Cancel 버튼을 추가합니다.
        connect_btn = dialog_buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        connect_btn.setText("연결")
        cancel_btn = dialog_buttons.addButton(QDialogButtonBox.StandardButton.Cancel)

        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        
        # ⭐️ 2. 연결 테스트 버튼에 기능을 연결합니다.
        test_btn.clicked.connect(self.test_connection)
        
        bottom_container = QVBoxLayout()
        bottom_container.addLayout(main_layout)
        bottom_container.addWidget(dialog_buttons)
        self.setLayout(bottom_container)
        
        self.list_widget.currentItemChanged.connect(self.display_connection_details)
        new_btn.clicked.connect(self.new_connection)
        save_btn.clicked.connect(self.save_connection)
        delete_btn.clicked.connect(self.delete_connection)
        
        self.populate_list()
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)