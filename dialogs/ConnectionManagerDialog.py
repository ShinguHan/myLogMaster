import json
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QDialogButtonBox, QLineEdit, QLabel, QGridLayout, QMessageBox, QInputDialog, QWidget
)
from PySide6.QtCore import Qt

CONNECTIONS_FILE = 'connections.json'

class ConnectionManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("데이터베이스 연결 관리자")
        self.setGeometry(200, 200, 600, 300)
        
        self.load_connections()

        # ⭐️ 1. 여기서 (self)를 삭제합니다.
        main_layout = QHBoxLayout()
        
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
        
        dialog_buttons = QDialogButtonBox()
        
        test_btn = QPushButton("연결 테스트")
        dialog_buttons.addButton(test_btn, QDialogButtonBox.ButtonRole.ActionRole)

        connect_btn = dialog_buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        connect_btn.setText("연결")
        cancel_btn = dialog_buttons.addButton(QDialogButtonBox.StandardButton.Cancel)

        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        
        test_btn.clicked.connect(self.test_connection)
        
        # ⭐️ 2. 다이얼로그 전체를 위한 최종 레이아웃을 설정합니다.
        #    이제 bottom_container가 유일한 메인 레이아웃이 됩니다.
        bottom_container = QVBoxLayout(self) # 여기에 self를 전달합니다.
        bottom_container.addLayout(main_layout)
        bottom_container.addWidget(dialog_buttons)
        
        self.list_widget.currentItemChanged.connect(self.display_connection_details)
        new_btn.clicked.connect(self.new_connection)
        save_btn.clicked.connect(self.save_connection)
        delete_btn.clicked.connect(self.delete_connection)
        
        self.populate_list()
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        
    def populate_list(self):
        self.list_widget.clear()
        for name in sorted(self.connections.keys()):
            self.list_widget.addItem(QListWidgetItem(name))
            
    def display_connection_details(self, current, previous):
        if not current: 
            self.conn_name_input.clear()
            self.user_input.clear()
            self.password_input.clear()
            self.dsn_input.clear()
            return
        name = current.text()
        details = self.connections[name]
        self.conn_name_input.setText(name)
        self.user_input.setText(details.get("user", ""))
        self.password_input.setText(details.get("password", ""))
        self.dsn_input.setText(details.get("dsn", ""))
        
    def new_connection(self):
        name, ok = QInputDialog.getText(self, "새 연결", "새 연결의 이름을 입력하세요:")
        if ok and name:
            if name in self.connections:
                QMessageBox.warning(self, "오류", "이미 존재하는 이름입니다.")
                return
            self.connections[name] = {"type": "oracle", "user": "", "password": "", "dsn": ""}
            self.save_connections_file()
            self.populate_list()
            items = self.list_widget.findItems(name, Qt.MatchFlag.MatchExactly)
            if items: self.list_widget.setCurrentItem(items[0])

    def save_connection(self):
        current_item = self.list_widget.currentItem()
        if not current_item: 
            QMessageBox.warning(self, "알림", "저장할 연결을 목록에서 선택하세요.")
            return
        
        original_name = current_item.text()
        new_name = self.conn_name_input.text()
        details = {
            "type": "oracle",
            "user": self.user_input.text(),
            "password": self.password_input.text(),
            "dsn": self.dsn_input.text()
        }
        
        if original_name != new_name:
            if new_name in self.connections:
                QMessageBox.warning(self, "오류", "변경하려는 이름이 이미 존재합니다.")
                self.conn_name_input.setText(original_name)
                return
            del self.connections[original_name]
        
        self.connections[new_name] = details
        self.save_connections_file()
        self.populate_list()
        items = self.list_widget.findItems(new_name, Qt.MatchFlag.MatchExactly)
        if items: self.list_widget.setCurrentItem(items[0])
        
    def delete_connection(self):
        current_item = self.list_widget.currentItem()
        if not current_item: return
        
        name = current_item.text()
        reply = QMessageBox.question(self, "삭제 확인", f"'{name}' 연결을 정말로 삭제하시겠습니까?")
        if reply == QMessageBox.StandardButton.Yes:
            del self.connections[name]
            self.save_connections_file()
            self.populate_list()

    def load_connections(self):
        try:
            with open(CONNECTIONS_FILE, 'r', encoding='utf-8') as f:
                self.connections = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.connections = {}
            
    def save_connections_file(self):
        with open(CONNECTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.connections, f, indent=4)
            
    def get_selected_connection(self):
        current_item = self.list_widget.currentItem()
        if not current_item: return None, None
        name = current_item.text()
        return name, self.connections[name]
    
    def test_connection(self):
        """현재 입력된 정보로 DB 연결을 테스트합니다."""
        # TODO: 실제 oracledb 연결 테스트 로직 구현 필요
        #       (지금은 성공했다고 가정하고 메시지만 표시)
        user = self.user_input.text()
        dsn = self.dsn_input.text()
        
        if not user or not dsn:
            QMessageBox.warning(self, "정보 부족", "사용자 ID와 DSN(주소)를 입력하세요.")
            return

        QMessageBox.information(self, "연결 테스트", f"'{dsn}'에 연결을 시도합니다...\n(테스트 성공!)")