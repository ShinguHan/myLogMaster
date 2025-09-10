import json
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QFormLayout, QLineEdit, QWidget, QMessageBox, QListWidgetItem,
    QComboBox, QLabel
)
from PySide6.QtCore import Qt, Signal
# ✅ [변경] DB 연결 테스트를 위한 스레드 import
from utils.connection_tester import ConnectionTester

CONNECTIONS_FILE = 'connections.json'

class ConnectionManagerDialog(QDialog):
    connection_selected = Signal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DB Connection Manager")
        self.setMinimumSize(600, 400)
        self.connections = self._load_connections()
        
        self.connection_tester = None
        # ✅ [추가] 선택된 연결 정보를 저장할 멤버 변수
        self.selected_connection_name = None
        self.selected_connection_info = None

        main_layout = QHBoxLayout(self)

        left_layout = QVBoxLayout()
        self.connection_list = QListWidget()
        self.connection_list.itemSelectionChanged.connect(self.on_selection_changed)
        left_layout.addWidget(self.connection_list)

        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_connection)
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_connection)
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        left_layout.addLayout(button_layout)

        self.right_widget = QWidget()
        form_layout = self._create_form_layout()
        self.right_widget.setLayout(form_layout)

        main_layout.addLayout(left_layout, 1)
        main_layout.addWidget(self.right_widget, 2)

        self._set_form_enabled(False)
        self._populate_list()
        self._select_first_item()

    def _create_form_layout(self):
        layout = QFormLayout()
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        
        self.name_input = QLineEdit()
        self.db_type_combo = QComboBox()
        self.db_type_combo.addItems(["Oracle"])
        
        self.user_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.host_input = QLineEdit()
        self.port_input = QLineEdit()
        self.sid_input = QLineEdit()
        self.service_name_input = QLineEdit()

        layout.addRow("Connection Name:", self.name_input)
        layout.addRow("Database Type:", self.db_type_combo)
        layout.addRow("User:", self.user_input)
        layout.addRow("Password:", self.password_input)
        layout.addRow("Host:", self.host_input)
        layout.addRow("Port:", self.port_input)
        
        sid_service_label = QLabel("SID / Service Name:")
        sid_service_label.setToolTip("Oracle DSN 생성을 위해 SID 또는 Service Name 중 하나를 입력하세요.")
        layout.addRow(sid_service_label)
        layout.addRow("SID:", self.sid_input)
        layout.addRow("Service Name:", self.service_name_input)
        
        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self.test_connection)
        
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_connection)
        
        self.connect_button = QPushButton("Connect")
        self.connect_button.setStyleSheet("background-color: #3498db; color: white;")
        self.connect_button.clicked.connect(self.accept)

        button_box = QHBoxLayout()
        button_box.addWidget(self.test_button)
        button_box.addWidget(self.save_button)
        button_box.addWidget(self.connect_button)
        layout.addRow(button_box)

        return layout

    def _load_connections(self):
        if not os.path.exists(CONNECTIONS_FILE): return {}
        try:
            with open(CONNECTIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            QMessageBox.critical(self, "Error", f"Could not load connections file: {e}")
        return {}

    def _save_connections(self):
        try:
            with open(CONNECTIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.connections, f, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save connections file: {e}")

    def _populate_list(self):
        self.connection_list.clear()
        for name in sorted(self.connections.keys()):
            self.connection_list.addItem(QListWidgetItem(name))
            
    def _select_first_item(self):
        if self.connection_list.count() > 0:
            self.connection_list.setCurrentRow(0)

    def _set_form_enabled(self, enabled):
        # 폼 내의 모든 위젯 활성화/비활성화
        for i in range(self.right_widget.layout().rowCount()):
            item = self.right_widget.layout().itemAt(i, QFormLayout.FieldRole)
            if item and item.widget():
                item.widget().setEnabled(enabled)

    def on_selection_changed(self):
        selected_items = self.connection_list.selectedItems()
        if not selected_items:
            self._clear_form()
            self._set_form_enabled(False)
            return

        self._set_form_enabled(True)
        item_name = selected_items[0].text()
        details = self.connections.get(item_name, {})
        self.name_input.setText(item_name)
        
        db_type = details.get("type", "Oracle")
        index = self.db_type_combo.findText(db_type)
        if index >= 0: self.db_type_combo.setCurrentIndex(index)
            
        self.user_input.setText(details.get("user", ""))
        self.password_input.setText(details.get("password", ""))
        self.host_input.setText(details.get("host", ""))
        self.port_input.setText(str(details.get("port", "")))
        self.sid_input.setText(details.get("sid", ""))
        self.service_name_input.setText(details.get("service_name", ""))

    def _clear_form(self):
        for w in [self.name_input, self.user_input, self.password_input, 
                  self.host_input, self.port_input, self.sid_input, self.service_name_input]:
            w.clear()
        self.db_type_combo.setCurrentIndex(0)
    
    def add_connection(self):
        self.connection_list.clearSelection()
        self._clear_form()
        self._set_form_enabled(True)
        self.name_input.setText("New Connection")
        self.name_input.setFocus()

    def remove_connection(self):
        selected_items = self.connection_list.selectedItems()
        if not selected_items: return

        item_name = selected_items[0].text()
        reply = QMessageBox.question(self, "Confirm Deletion", f"'{item_name}' 연결 정보를 삭제하시겠습니까?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if item_name in self.connections:
                del self.connections[item_name]
                self._save_connections()
                self._populate_list()
                self._clear_form()
                self._set_form_enabled(False)

    def save_connection(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "입력 오류", "연결 이름은 필수 항목입니다.")
            return

        selected_items = self.connection_list.selectedItems()
        original_name = selected_items[0].text() if selected_items else None
        
        if name != original_name and name in self.connections:
            QMessageBox.warning(self, "이름 중복", f"'{name}' 이름의 연결 정보가 이미 존재합니다.")
            return
            
        if original_name and name != original_name and original_name in self.connections:
            del self.connections[original_name]

        self.connections[name] = self._get_details_from_form()
        
        self._save_connections()
        self._populate_list()
        
        items = self.connection_list.findItems(name, Qt.MatchFlag.MatchExactly)
        if items: self.connection_list.setCurrentItem(items[0])
            
        QMessageBox.information(self, "저장 완료", f"'{name}' 연결 정보가 저장되었습니다.")

    # ✅ [수정] test_connection 메소드 전체 구현
    def test_connection(self):
        """폼에 입력된 정보를 바탕으로 DB 연결을 테스트합니다."""
        conn_details = self._get_details_from_form()
        
        if not all(conn_details.get(k) for k in ['user', 'password', 'host', 'port']) or \
           not (conn_details.get('sid') or conn_details.get('service_name')):
            QMessageBox.warning(self, "입력 누락", "User, Password, Host, Port, SID/Service Name은 필수 항목입니다.")
            return

        self.test_button.setEnabled(False)
        self.test_button.setText("Testing...")

        self.connection_tester = ConnectionTester(conn_details, self)
        self.connection_tester.success.connect(self.on_test_success)
        self.connection_tester.error.connect(self.on_test_error)
        self.connection_tester.finished.connect(self.on_test_finished)
        self.connection_tester.start()

    # ✅ [추가] 연결 테스트 성공 시 호출될 슬롯
    def on_test_success(self, message):
        QMessageBox.information(self, "연결 성공", message)

    # ✅ [추가] 연결 테스트 실패 시 호출될 슬롯
    def on_test_error(self, error_message):
        QMessageBox.critical(self, "연결 실패", error_message)

    # ✅ [추가] 연결 테스트 완료 시(성공/실패 무관) 호출될 슬롯
    def on_test_finished(self):
        self.test_button.setEnabled(True)
        self.test_button.setText("Test Connection")
        self.connection_tester = None

    def _get_details_from_form(self):
        details = {
            'type': self.db_type_combo.currentText(),
            'user': self.user_input.text().strip(),
            'password': self.password_input.text(),
            'host': self.host_input.text().strip(),
            'port': self.port_input.text().strip(),
        }
        sid = self.sid_input.text().strip()
        service_name = self.service_name_input.text().strip()
        if service_name:
            details['service_name'] = service_name
        elif sid:
            details['sid'] = sid
        return details

    def accept(self):
        selected_items = self.connection_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "선택 오류", "접속할 DB를 선택해주세요.")
            return
            
        name = selected_items[0].text()
        details = self.connections.get(name)
        if details:
            # ✅ [수정] 선택된 정보를 멤버 변수에 저장
            self.selected_connection_name = name
            self.selected_connection_info = details
            self.connection_selected.emit(name, details)
        
        super().accept()

    # ✅ [추가] 선택된 연결 정보를 반환하는 메소드
    def get_selected_connection(self):
        """사용자가 최종 선택한 연결의 이름과 상세 정보를 반환합니다."""
        return self.selected_connection_name, self.selected_connection_info

