import json
import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QListWidget, QFrame, QLabel,
                               QDateTimeEdit, QMessageBox, QWidget, QLineEdit,
                               QTreeView, QMenu, QInputDialog, QRadioButton,
                               QButtonGroup, QComboBox)
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import QDateTime, Qt
from .ui_components import create_section_label, create_separator, create_toggle_button, create_action_button

QUERY_PRESETS_FILE = 'query_presets.json'

class QueryConditionsDialog(QDialog):
    def __init__(self, column_names, query_templates, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Filter - File Mode")
        self.presets = self.load_presets()
        self.current_preset_name = None
        
        self.column_names = column_names
        self.query_templates = query_templates
        
        self.setMinimumSize(900, 700)
        self.setGeometry(100, 100, 1000, 750)
        
        self._init_ui()

        self.populate_preset_list()
        self.initialize_filter_tree()

    def _init_ui(self):
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setSpacing(10)
        dialog_layout.setContentsMargins(15, 15, 15, 15)
        
        # --- Section 1: Time Range ---
        time_frame = QFrame()
        time_frame.setFrameShape(QFrame.Shape.StyledPanel)
        time_frame.setStyleSheet("QFrame { border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9; padding: 10px; }")
        time_section = QVBoxLayout(time_frame)
        time_section.setContentsMargins(10, 10, 10, 10)
        time_label = create_section_label("📅 Time Range")
        time_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        time_section.addWidget(time_label)
        
        time_range_widget = QWidget()
        time_layout = QHBoxLayout(time_range_widget)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(15)
        
        # 시작 시간
        time_layout.addWidget(QLabel("From:"))
        self.start_time_edit = QDateTimeEdit(QDateTime.currentDateTime().addDays(-1))
        self.start_time_edit.setCalendarPopup(True)
        self.start_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_time_edit.setMinimumWidth(250)
        time_layout.addWidget(self.start_time_edit)
        
        # 종료 시간
        time_layout.addWidget(QLabel("To:"))
        self.end_time_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.end_time_edit.setCalendarPopup(True)
        self.end_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_time_edit.setMinimumWidth(250)
        time_layout.addWidget(self.end_time_edit)
        time_layout.addStretch()
        
        time_section.addWidget(time_range_widget)
        dialog_layout.addWidget(time_frame)
        
        # --- Section 2: Advanced Conditions ---
        condition_frame = QFrame()
        condition_frame.setFrameShape(QFrame.Shape.StyledPanel)
        condition_frame.setStyleSheet("QFrame { border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9; padding: 10px; }")
        condition_section = QVBoxLayout(condition_frame)
        condition_section.setContentsMargins(10, 10, 10, 10)
        cond_label = create_section_label("🔍 Filter Conditions (Optional)")
        cond_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        condition_section.addWidget(cond_label)
        
        # 트리 뷰
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(['Filter Rules'])
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setMinimumHeight(280)
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_tree_context_menu)
        self.tree_view.doubleClicked.connect(self.edit_rule_item)
        condition_section.addWidget(self.tree_view)
        dialog_layout.addWidget(condition_frame, 1)
        
        # --- Section 3: Presets + Buttons ---
        bottom_frame = QFrame()
        bottom_frame.setFrameShape(QFrame.Shape.StyledPanel)
        bottom_frame.setStyleSheet("QFrame { border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9; padding: 10px; }")
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(10, 10, 10, 10)
        
        preset_section = QVBoxLayout()
        preset_label = create_section_label("💾 Saved Presets")
        preset_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        preset_section.addWidget(preset_label)
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_preset_selected)
        self.list_widget.setMaximumHeight(100)
        preset_section.addWidget(self.list_widget)
        bottom_layout.addLayout(preset_section, 1)
        
        preset_button_layout = QVBoxLayout()
        add_preset_btn = create_action_button("Save")
        add_preset_btn.setMinimumWidth(80)
        add_preset_btn.clicked.connect(self.save_current_preset)
        remove_preset_btn = create_action_button("Remove")
        remove_preset_btn.setMinimumWidth(80)
        remove_preset_btn.clicked.connect(self.remove_selected_preset)
        preset_button_layout.addWidget(add_preset_btn)
        preset_button_layout.addWidget(remove_preset_btn)
        preset_button_layout.addStretch()
        bottom_layout.addLayout(preset_button_layout)
        
        dialog_layout.addWidget(bottom_frame)
        
        # --- Action Buttons ---
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        cancel_button = create_action_button("Cancel")
        cancel_button.setMinimumWidth(120)
        cancel_button.clicked.connect(self.reject)
        query_button = create_action_button("Query", is_default=True)
        query_button.setMinimumWidth(120)
        query_button.clicked.connect(self.accept)
        action_layout.addWidget(cancel_button)
        action_layout.addWidget(query_button)
        dialog_layout.addLayout(action_layout)

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
        
        if action == add_group_action: self.add_logic_item(selected_item)
        elif action == add_rule_action: self.add_rule_item(selected_item)
        elif action == remove_action: self.remove_item(selected_item)

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
    
    def edit_rule_item(self, index):
        item = self.tree_model.itemFromIndex(index)
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item or not item_data or item_data.get("type") != "rule":
            return
            
        editor_dialog = QDialog(self)
        editor_dialog.setWindowTitle("Edit Rule")
        layout = QVBoxLayout(editor_dialog)
        
        col_combo = QComboBox(); col_combo.addItems(self.column_names); col_combo.setCurrentText(item_data.get("column"))
        op_combo = QComboBox(); op_combo.addItems(["Contains", "Does Not Contain", "Equals", "Not Equals", "Matches Regex"]); op_combo.setCurrentText(item_data.get("operator"))
        val_edit = QLineEdit(item_data.get("value"))
        
        button_box = QHBoxLayout()
        ok_btn = create_action_button("OK", is_default=True)
        ok_btn.clicked.connect(editor_dialog.accept)
        cancel_btn = create_action_button("Cancel")
        cancel_btn.clicked.connect(editor_dialog.reject)
        button_box.addStretch(); button_box.addWidget(ok_btn); button_box.addWidget(cancel_btn)
        
        layout.addWidget(QLabel("Column:")); layout.addWidget(col_combo)
        layout.addWidget(QLabel("Operator:")); layout.addWidget(op_combo)
        layout.addWidget(QLabel("Value:")); layout.addWidget(val_edit)
        layout.addLayout(button_box)
        
        if editor_dialog.exec():
            new_data = {"type": "rule", "column": col_combo.currentText(), "operator": op_combo.currentText(), "value": val_edit.text()}
            new_text = f"{new_data['column']} {new_data['operator']} '{new_data['value']}'"
            item.setText(new_text)
            item.setData(new_data, Qt.ItemDataRole.UserRole)

    def build_data_from_tree(self, item):
        item_data = item.data(Qt.ItemDataRole.UserRole)
        if not item_data: return None
        if item_data.get("type") == "logic":
            data = {"logic": item_data["logic"], "rules": []}
            for row in range(item.rowCount()):
                child_data = self.build_data_from_tree(item.child(row))
                if child_data: data["rules"].append(child_data)
            return data if data["rules"] else None
        else:
            return item_data if item_data.get('value') else None

    def get_conditions(self):
        """파일 모드 전용 조건 반환 - apply_advanced_filter 형식"""
        root_item = self.tree_model.invisibleRootItem().child(0)
        filter_data = self.build_data_from_tree(root_item) if root_item else None
        
        # apply_advanced_filter()가 기대하는 형식: rules 키 필요
        if filter_data:
            return filter_data
        else:
            # 빈 필터 = 모든 데이터 표시
            return None

    def on_preset_selected(self, item):
        self.current_preset_name = item.text()
        preset_data = self.presets.get(self.current_preset_name, {})
        
        if 'start_time' in preset_data:
            self.start_time_edit.setDateTime(QDateTime.fromString(preset_data['start_time'], Qt.DateFormat.ISODate))
        if 'end_time' in preset_data:
            self.end_time_edit.setDateTime(QDateTime.fromString(preset_data['end_time'], Qt.DateFormat.ISODate))
        
        self.tree_model.clear(); self.tree_model.setHorizontalHeaderLabels(['Filter'])
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
        conditions = self.get_conditions()
        preset_name, ok = QInputDialog.getText(self, "Save Preset", "Enter a name for this preset:", text=self.current_preset_name or "")
        if ok and preset_name:
            self.presets[preset_name] = conditions
            self.save_presets_to_file()
            self.populate_preset_list()

    def remove_selected_preset(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select a preset to remove.")
            return
        
        preset_name = selected_items[0].text()
        if QMessageBox.question(self, "Confirm", f"Are you sure you want to delete preset '{preset_name}'?") == QMessageBox.StandardButton.Yes:
            if preset_name in self.presets:
                del self.presets[preset_name]
                self.save_presets_to_file()
                self.populate_preset_list()

    def load_presets(self):
        if not os.path.exists(QUERY_PRESETS_FILE): return {}
        try:
            with open(QUERY_PRESETS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except Exception: return {}

    def save_presets_to_file(self):
        try:
            with open(QUERY_PRESETS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.presets, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save presets: {e}")

    def accept(self):
        self.get_conditions()
        super().accept()

    def populate_preset_list(self):
        """프리셋 리스트를 채웁니다."""
        self.list_widget.clear()
        # 💥 변경점: for 루프 대신 addItems 사용
        self.list_widget.addItems(sorted(self.presets.keys()))


