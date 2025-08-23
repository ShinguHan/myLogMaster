import sys
import json
import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QListWidget, QListWidgetItem, QFrame, QLabel,
                               QLineEdit, QDateTimeEdit, QMessageBox, QWidget,
                               QTreeView, QMenu, QInputDialog, QRadioButton, QComboBox,
                               QButtonGroup)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import QDateTime, Qt

QUERY_PRESETS_FILE = 'query_presets.json'

class QueryConditionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Query Conditions")
        self.presets = self.load_presets()
        self.current_preset_name = None
        
        self.column_names = ["Category", "DeviceID", "MethodID", "TrackingID", "AsciiData", "MessageName"]

        self.setMinimumSize(800, 600)
        
        # ✅ 1. 버튼 선택 상태가 보이도록 스타일시트 추가
        self.setStyleSheet("""
            QPushButton[checkable=true]:checked {
                background-color: #a8cce9;
                border: 1px solid #007aff;
            }
        """)
        dialog_layout = QVBoxLayout(self)
        top_panel_layout = QHBoxLayout()

        # --- 왼쪽: 프리셋 리스트 ---
        left_frame = QFrame()
        left_frame.setFrameShape(QFrame.Shape.StyledPanel)
        left_layout = QVBoxLayout(left_frame)
        left_layout.addWidget(QLabel("<b>Saved Presets</b>"))
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_preset_selected)
        left_layout.addWidget(self.list_widget)
        list_button_layout = QHBoxLayout()
        add_button = QPushButton("Save Current")
        add_button.clicked.connect(self.save_current_preset)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self.remove_selected_preset)
        list_button_layout.addWidget(add_button)
        list_button_layout.addWidget(remove_button)
        left_layout.addLayout(list_button_layout)
        top_panel_layout.addWidget(left_frame, 1)

        # --- 오른쪽: 조건 에디터 ---
        right_frame = QFrame()
        right_frame.setFrameShape(QFrame.Shape.StyledPanel)
        right_layout = QVBoxLayout(right_frame)
        
        right_layout.addWidget(QLabel("<b>1. Data Source</b>"))
        source_layout = QHBoxLayout()
        self.source_group = QButtonGroup(self)
        self.real_db_btn = QPushButton("Real Database")
        self.real_db_btn.setCheckable(True)
        self.real_db_btn.setChecked(True)
        self.mock_data_btn = QPushButton("Mock Data")
        self.mock_data_btn.setCheckable(True)
        self.source_group.addButton(self.real_db_btn)
        self.source_group.addButton(self.mock_data_btn)
        source_layout.addWidget(self.real_db_btn)
        source_layout.addWidget(self.mock_data_btn)
        right_layout.addLayout(source_layout)
        right_layout.addWidget(self.create_separator())

        right_layout.addWidget(QLabel("<b>2. Analysis Mode</b>"))
        mode_layout = QHBoxLayout()
        self.time_range_radio = QRadioButton("Time Range")
        self.time_range_radio.setChecked(True)
        self.real_time_radio = QRadioButton("Real-time Tailing")
        mode_layout.addWidget(self.time_range_radio)
        mode_layout.addWidget(self.real_time_radio)
        right_layout.addLayout(mode_layout)
        self.time_range_radio.toggled.connect(self.update_ui_for_mode)
        
        right_layout.addWidget(QLabel("<b>3. Conditions</b>"))
        self.time_range_widget = QWidget()
        time_layout = QHBoxLayout(self.time_range_widget)
        time_layout.setContentsMargins(0,0,0,0)
        self.start_time_edit = QDateTimeEdit(QDateTime.currentDateTime().addDays(-1))
        self.end_time_edit = QDateTimeEdit(QDateTime.currentDateTime())
        time_layout.addWidget(QLabel("Start:"))
        time_layout.addWidget(self.start_time_edit)
        time_layout.addWidget(QLabel("End:"))
        time_layout.addWidget(self.end_time_edit)
        right_layout.addWidget(self.time_range_widget)
        right_layout.addWidget(self.create_separator())

        right_layout.addWidget(QLabel("<b>Advanced Conditions</b>"))
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(['Filter'])
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # ✅ 2. 고급 필터 기능이 동작하도록 시그널 연결
        self.tree_view.customContextMenuRequested.connect(self.show_tree_context_menu)
        self.tree_view.doubleClicked.connect(self.edit_rule_item)
        right_layout.addWidget(self.tree_view)
        top_panel_layout.addWidget(right_frame, 3)
        
        bottom_button_layout = QHBoxLayout()
        ok_button = QPushButton("Query")
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        bottom_button_layout.addStretch()
        bottom_button_layout.addWidget(cancel_button)
        bottom_button_layout.addWidget(ok_button)
        
        dialog_layout.addLayout(top_panel_layout)
        dialog_layout.addLayout(bottom_button_layout)

        self.populate_preset_list()
        self.initialize_filter_tree()
        self.update_ui_for_mode(True)

    def create_separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    # ✅ 3. 라디오 버튼 선택에 따라 UI를 동적으로 변경하는 메소드 추가
    def update_ui_for_mode(self, is_time_range_checked):
        """'Time Range' 모드가 선택되었는지 여부에 따라 UI를 업데이트합니다."""
        self.time_range_widget.setEnabled(is_time_range_checked)
        self.tree_view.setEnabled(is_time_range_checked) # 실시간 모드에서는 고급 필터 비활성화

    def get_conditions(self):
        # ✅ 4. 사용자가 선택한 모드 정보까지 함께 반환하도록 수정
        root_item = self.tree_model.invisibleRootItem().child(0)
        filter_data = self.build_data_from_tree(root_item) if root_item else None
        
        data_source = "real" if self.real_db_btn.isChecked() else "mock"
        analysis_mode = "time_range" if self.time_range_radio.isChecked() else "real_time"

        self.conditions = {
            'data_source': data_source,
            'analysis_mode': analysis_mode,
            'start_time': self.start_time_edit.dateTime().toString(Qt.DateFormat.ISODate),
            'end_time': self.end_time_edit.dateTime().toString(Qt.DateFormat.ISODate),
            'advanced_filter': filter_data
        }
        return self.conditions

    # ✅ 3. 고급 필터 기능을 위한 헬퍼 메소드들을 모두 추가합니다.
    def initialize_filter_tree(self):
        root_item = self.tree_model.invisibleRootItem()
        and_item = QStandardItem("AND")
        and_item.setData({"type": "logic", "logic": "AND"}, Qt.ItemDataRole.UserRole)
        root_item.appendRow(and_item)
        self.tree_view.expandAll()

    def show_tree_context_menu(self, position):
        menu = QMenu()
        add_group_action = menu.addAction("Add Group (AND/OR)"); add_rule_action = menu.addAction("Add Rule"); remove_action = menu.addAction("Remove Item")
        action = menu.exec(self.tree_view.viewport().mapToGlobal(position))
        selected_index = self.tree_view.selectionModel().currentIndex(); selected_item = self.tree_model.itemFromIndex(selected_index)
        if action == add_group_action: self.add_logic_item(selected_item)
        elif action == add_rule_action: self.add_rule_item(selected_item)
        elif action == remove_action: self.remove_item(selected_item)

    def add_logic_item(self, parent_item):
        if not parent_item or parent_item.data(Qt.ItemDataRole.UserRole)["type"] != "logic": parent_item = self.tree_model.invisibleRootItem().child(0)
        logic, ok = QInputDialog.getItem(self, "Add Group", "Select logic:", ["AND", "OR"], 0, False)
        if ok and logic: item = QStandardItem(logic); item.setData({"type": "logic", "logic": logic}, Qt.ItemDataRole.UserRole); parent_item.appendRow(item); self.tree_view.expandAll()

    def add_rule_item(self, parent_item):
        if not parent_item or parent_item.data(Qt.ItemDataRole.UserRole)["type"] != "logic": parent_item = self.tree_model.invisibleRootItem().child(0)
        new_rule_data = {"type": "rule", "column": self.column_names[0], "operator": "Contains", "value": ""}; rule_text = f"{new_rule_data['column']} {new_rule_data['operator']} '{new_rule_data['value']}'"
        item = QStandardItem(rule_text); item.setData(new_rule_data, Qt.ItemDataRole.UserRole); parent_item.appendRow(item); self.tree_view.expandAll()

    def remove_item(self, item):
        if item and item.parent(): item.parent().removeRow(item.row())
    
    def edit_rule_item(self, index):
        item = self.tree_model.itemFromIndex(index); item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item or not item_data or item_data.get("type") != "rule": return
        editor_dialog = QDialog(self); editor_dialog.setWindowTitle("Edit Rule"); layout = QVBoxLayout(editor_dialog)
        col_combo = QComboBox(); col_combo.addItems(self.column_names); col_combo.setCurrentText(item_data.get("column"))
        op_combo = QComboBox(); op_combo.addItems(["Contains", "Does Not Contain", "Equals", "Not Equals", "Matches Regex"]); op_combo.setCurrentText(item_data.get("operator"))
        val_edit = QLineEdit(item_data.get("value")); button_box = QHBoxLayout(); ok_btn = QPushButton("OK"); cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(editor_dialog.accept); cancel_btn.clicked.connect(editor_dialog.reject)
        button_box.addStretch(); button_box.addWidget(ok_btn); button_box.addWidget(cancel_btn)
        layout.addWidget(QLabel("Column:")); layout.addWidget(col_combo); layout.addWidget(QLabel("Operator:")); layout.addWidget(op_combo); layout.addWidget(QLabel("Value:")); layout.addWidget(val_edit); layout.addLayout(button_box)
        if editor_dialog.exec():
            new_data = {"type": "rule", "column": col_combo.currentText(), "operator": op_combo.currentText(), "value": val_edit.text()}
            new_text = f"{new_data['column']} {new_data['operator']} '{new_data['value']}'"; item.setText(new_text); item.setData(new_data, Qt.ItemDataRole.UserRole)

    def build_data_from_tree(self, item):
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data: return None
        if item_data.get("type") == "logic":
            data = {"logic": item_data["logic"], "rules": []}
            for row in range(item.rowCount()):
                child_data = self.build_data_from_tree(item.child(row))
                if child_data: data["rules"].append(child_data)
            return data
        else: return item_data