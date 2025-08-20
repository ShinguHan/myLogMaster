import sys
import json
import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QListWidget, QListWidgetItem, QFrame, QLabel,
                               QLineEdit, QDateTimeEdit, QMessageBox, QComboBox,
                               QTreeView, QMenu, QInputDialog)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import QDateTime, Qt

QUERY_PRESETS_FILE = 'query_presets.json'

class QueryConditionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Query Conditions")
        self.presets = self.load_presets()
        self.current_preset_name = None
        self.conditions = {}

        self.column_names = ["Category", "DeviceID", "MethodID", "TrackingID", "AsciiData", "MessageName"]
        self.setMinimumSize(800, 500)

        # 1. 대화상자 전체를 책임질 메인 수직(V) 레이아웃
        dialog_layout = QVBoxLayout(self)

        # 2. 상단 영역(왼쪽+오른쪽 패널)을 담을 수평(H) 레이아웃
        top_panel_layout = QHBoxLayout()

        # --- 왼쪽: 프리셋 리스트 ---
        left_frame = QFrame()
        left_frame.setFrameShape(QFrame.Shape.StyledPanel)
        left_layout = QVBoxLayout(left_frame)
        left_layout.addWidget(QLabel("<b>Saved Presets</b>"))
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_preset_selected)
        left_layout.addWidget(self.list_widget)
        top_panel_layout.addWidget(left_frame, 1)

        # --- 오른쪽: 조건 에디터 ---
        right_frame = QFrame()
        right_frame.setFrameShape(QFrame.Shape.StyledPanel)
        right_layout = QVBoxLayout(right_frame)
        
        right_layout.addWidget(QLabel("<b>Time Range</b>"))
        self.start_time_edit = QDateTimeEdit(QDateTime.currentDateTime().addDays(-1))
        self.end_time_edit = QDateTimeEdit(QDateTime.currentDateTime())
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Start:"))
        time_layout.addWidget(self.start_time_edit)
        time_layout.addWidget(QLabel("End:"))
        time_layout.addWidget(self.end_time_edit)
        right_layout.addLayout(time_layout)
        
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); line.setFrameShadow(QFrame.Shadow.Sunken)
        right_layout.addWidget(line)

        right_layout.addWidget(QLabel("<b>Advanced Conditions</b>"))
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(['Filter'])
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_tree_context_menu)
        self.tree_view.doubleClicked.connect(self.edit_rule_item)
        right_layout.addWidget(self.tree_view)
        top_panel_layout.addWidget(right_frame, 3)
        
        # ✅ 3. 모든 버튼을 하나의 하단 수평(H) 레이아웃에 통합합니다.
        bottom_button_layout = QHBoxLayout()
        add_button = QPushButton("Save Current")
        add_button.clicked.connect(self.save_current_preset)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self.remove_selected_preset)
        ok_button = QPushButton("Query")
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        bottom_button_layout.addWidget(add_button)
        bottom_button_layout.addWidget(remove_button)
        bottom_button_layout.addStretch() # 중간에 공간을 밀어넣음
        bottom_button_layout.addWidget(cancel_button)
        bottom_button_layout.addWidget(ok_button)

        # 4. 메인 수직 레이아웃에 상단 영역과 통합된 하단 버튼 영역을 추가합니다.
        dialog_layout.addLayout(top_panel_layout)
        dialog_layout.addLayout(bottom_button_layout)

        # 초기 상태 설정
        self.populate_preset_list()
        self.initialize_filter_tree()

    def initialize_filter_tree(self):
        root_item = self.tree_model.invisibleRootItem()
        and_item = QStandardItem("AND")
        and_item.setData({"type": "logic", "logic": "AND"}, Qt.ItemDataRole.UserRole)
        root_item.appendRow(and_item)
        self.tree_view.expandAll()

    def show_tree_context_menu(self, position):
        menu = QMenu()
        add_group_action = menu.addAction("Add Group (AND/OR)")
        add_rule_action = menu.addAction("Add Rule")
        remove_action = menu.addAction("Remove Item")
        
        action = menu.exec(self.tree_view.viewport().mapToGlobal(position))
        selected_index = self.tree_view.selectionModel().currentIndex()
        selected_item = self.tree_model.itemFromIndex(selected_index)

        if action == add_group_action:
            self.add_logic_item(selected_item)
        elif action == add_rule_action:
            self.add_rule_item(selected_item)
        elif action == remove_action:
            self.remove_item(selected_item)

    def add_logic_item(self, parent_item):
        if not parent_item or parent_item.data(Qt.ItemDataRole.UserRole)["type"] != "logic":
            parent_item = self.tree_model.invisibleRootItem().child(0)
        
        logic, ok = QInputDialog.getItem(self, "Add Group", "Select logic:", ["AND", "OR"], 0, False)
        if ok and logic:
            item = QStandardItem(logic)
            item.setData({"type": "logic", "logic": logic}, Qt.ItemDataRole.UserRole)
            parent_item.appendRow(item)
            self.tree_view.expandAll()

    def add_rule_item(self, parent_item):
        if not parent_item or parent_item.data(Qt.ItemDataRole.UserRole)["type"] != "logic":
            parent_item = self.tree_model.invisibleRootItem().child(0)

        new_rule_data = {"type": "rule", "column": self.column_names[0], "operator": "Contains", "value": ""}
        rule_text = f"{new_rule_data['column']} {new_rule_data['operator']} '{new_rule_data['value']}'"
        item = QStandardItem(rule_text)
        item.setData(new_rule_data, Qt.ItemDataRole.UserRole)
        parent_item.appendRow(item)
        self.tree_view.expandAll()

    def remove_item(self, item):
        if item and item.parent():
            item.parent().removeRow(item.row())

    def populate_preset_list(self):
        self.list_widget.clear()
        for name in self.presets.keys():
            self.list_widget.addItem(QListWidgetItem(name))

    def on_preset_selected(self, item):
        self.current_preset_name = item.text()
        preset_data = self.presets.get(self.current_preset_name, {})
        
        if 'start_time' in preset_data:
            self.start_time_edit.setDateTime(QDateTime.fromString(preset_data['start_time'], Qt.DateFormat.ISODate))
        if 'end_time' in preset_data:
            self.end_time_edit.setDateTime(QDateTime.fromString(preset_data['end_time'], Qt.DateFormat.ISODate))

        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(['Filter'])
        root_item = self.tree_model.invisibleRootItem()
        filter_data = preset_data.get('advanced_filter')
        if filter_data:
            self.build_tree_from_data(root_item, filter_data)
        else:
            self.initialize_filter_tree()
        self.tree_view.expandAll()

    def build_tree_from_data(self, parent_item, data_group):
        logic = data_group.get("logic", "AND")
        item = QStandardItem(logic)
        item.setData({"type": "logic", "logic": logic}, Qt.ItemDataRole.UserRole)
        parent_item.appendRow(item)
        for rule in data_group.get("rules", []):
            if "logic" in rule:
                self.build_tree_from_data(item, rule)
            else:
                rule_text = f"{rule.get('column','')} {rule.get('operator','')} '{rule.get('value','')}'"
                rule_item = QStandardItem(rule_text)
                rule_item.setData({"type": "rule", **rule}, Qt.ItemDataRole.UserRole)
                item.appendRow(rule_item)

    def save_current_preset(self):
        preset_name, ok = QInputDialog.getText(self, "Save Preset", "Enter a name for this preset:", text=self.current_preset_name or "")
        if ok and preset_name:
            self.presets[preset_name] = self.get_conditions()
            self.save_presets_to_file()
            self.populate_preset_list()

    def remove_selected_preset(self):
        if not self.current_preset_name:
            QMessageBox.warning(self, "Warning", "Please select a preset to remove.")
            return
        if QMessageBox.question(self, "Confirm", f"Are you sure you want to delete preset '{self.current_preset_name}'?") == QMessageBox.StandardButton.Yes:
            if self.current_preset_name in self.presets:
                del self.presets[self.current_preset_name]
                self.save_presets_to_file()
                self.populate_preset_list()
                self.current_preset_name = None

    def get_conditions(self):
        root_item = self.tree_model.invisibleRootItem().child(0)
        filter_data = self.build_data_from_tree(root_item) if root_item else None
        self.conditions = {
            'start_time': self.start_time_edit.dateTime().toString(Qt.DateFormat.ISODate),
            'end_time': self.end_time_edit.dateTime().toString(Qt.DateFormat.ISODate),
            'advanced_filter': filter_data
        }
        return self.conditions

    def build_data_from_tree(self, item):
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data: return None

        if item_data.get("type") == "logic":
            data = {"logic": item_data["logic"], "rules": []}
            for row in range(item.rowCount()):
                child_data = self.build_data_from_tree(item.child(row))
                if child_data:
                    data["rules"].append(child_data)
            return data
        else: # rule
            return item_data

    def edit_rule_item(self, index):
        item = self.tree_model.itemFromIndex(index)
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item or not item_data or item_data.get("type") != "rule":
            return

        editor_dialog = QDialog(self)
        editor_dialog.setWindowTitle("Edit Rule")
        layout = QVBoxLayout(editor_dialog)
        col_combo = QComboBox()
        col_combo.addItems(self.column_names)
        col_combo.setCurrentText(item_data.get("column"))
        op_combo = QComboBox()
        op_combo.addItems(["Contains", "Does Not Contain", "Equals", "Not Equals", "Matches Regex"])
        op_combo.setCurrentText(item_data.get("operator"))
        val_edit = QLineEdit(item_data.get("value"))
        
        button_box = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(editor_dialog.accept)
        cancel_btn.clicked.connect(editor_dialog.reject)
        button_box.addStretch(); button_box.addWidget(ok_btn); button_box.addWidget(cancel_btn)
        
        layout.addWidget(QLabel("Column:")); layout.addWidget(col_combo)
        layout.addWidget(QLabel("Operator:")); layout.addWidget(op_combo)
        layout.addWidget(QLabel("Value:")); layout.addWidget(val_edit)
        layout.addLayout(button_box)
        
        if editor_dialog.exec():
            new_data = {
                "type": "rule",
                "column": col_combo.currentText(),
                "operator": op_combo.currentText(),
                "value": val_edit.text()
            }
            new_text = f"{new_data['column']} {new_data['operator']} '{new_data['value']}'"
            item.setText(new_text)
            item.setData(new_data, Qt.ItemDataRole.UserRole)

    def load_presets(self):
        if not os.path.exists(QUERY_PRESETS_FILE): return {}
        try:
            with open(QUERY_PRESETS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except Exception: return {}

    def save_presets_to_file(self):
        try:
            with open(QUERY_PRESETS_FILE, 'w', encoding='utf-8') as f: json.dump(self.presets, f, indent=4)
        except Exception as e: QMessageBox.critical(self, "Error", f"Could not save presets: {e}")
        
    def accept(self):
        """OK/Query 버튼을 누르면 현재 조건을 저장하고 다이얼로그를 닫습니다."""
        self.get_conditions() # self.conditions 변수를 최신 상태로 업데이트
        super().accept()