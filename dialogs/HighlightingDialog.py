import sys, os
import json
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QListWidget, QListWidgetItem, QColorDialog,
                               QFrame, QLabel, QLineEdit, QComboBox, QCheckBox,
                               QMessageBox, QWidget)
from PySide6.QtGui import QColor, QPalette, QBrush
from PySide6.QtCore import Qt

HIGHLIGHTERS_FILE = 'highlighters.json'

class HighlightingDialog(QDialog):
    def __init__(self, column_names, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conditional Highlighting Rules")
        self.column_names = column_names
        self.rules = self.load_rules()
        self.current_item = None
        self.setMinimumSize(700, 400)

        # ✅ 1. 전체 위젯을 담을 메인 수직 레이아웃을 생성합니다.
        main_layout = QVBoxLayout(self)

        # 상단 부분 (리스트와 에디터를 담을 수평 레이아웃)
        top_part_layout = QHBoxLayout()

        # 왼쪽: 규칙 리스트
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.on_item_selected)
        left_layout.addWidget(self.list_widget)

        list_button_layout = QHBoxLayout()
        add_button = QPushButton("Add New")
        add_button.clicked.connect(self.add_new_rule)
        remove_button = QPushButton("Remove Selected")
        remove_button.clicked.connect(self.remove_selected_rule)
        list_button_layout.addWidget(add_button)
        list_button_layout.addWidget(remove_button)
        left_layout.addLayout(list_button_layout)
        
        # 오른쪽: 규칙 에디터
        self.editor_widget = QWidget()
        right_layout = QVBoxLayout(self.editor_widget)
        self.name_edit = QLineEdit()
        self.enabled_check = QCheckBox("Enabled")
        self.column_combo = QComboBox()
        self.column_combo.addItems(self.column_names)
        self.operator_combo = QComboBox()
        self.operator_combo.addItems(["contains", "equals", "starts with", "ends with"])
        self.value_edit = QLineEdit()
        self.fg_button = QPushButton("Foreground Color")
        self.fg_button.clicked.connect(lambda: self.pick_color('foreground'))
        self.bg_button = QPushButton("Background Color")
        self.bg_button.clicked.connect(lambda: self.pick_color('background'))
        
        right_layout.addWidget(QLabel("Rule Name:"))
        right_layout.addWidget(self.name_edit)
        right_layout.addWidget(self.enabled_check)
        right_layout.addWidget(QLabel("Column:"))
        right_layout.addWidget(self.column_combo)
        right_layout.addWidget(QLabel("Operator:"))
        right_layout.addWidget(self.operator_combo)
        right_layout.addWidget(QLabel("Value:"))
        right_layout.addWidget(self.value_edit)
        right_layout.addWidget(self.fg_button)
        right_layout.addWidget(self.bg_button)
        right_layout.addStretch()
        
        # 상단 레이아웃에 왼쪽과 오른쪽 위젯을 추가
        top_part_layout.addWidget(left_widget, 1)
        top_part_layout.addWidget(self.editor_widget, 2)

        # 하단 버튼 부분 (수평 레이아웃)
        bottom_button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self.apply_changes)
        bottom_button_layout.addStretch()
        bottom_button_layout.addWidget(ok_button)
        bottom_button_layout.addWidget(cancel_button)
        bottom_button_layout.addWidget(apply_button)

        # ✅ 2. 메인 수직 레이아웃에 상단과 하단 레이아웃을 순서대로 추가합니다.
        main_layout.addLayout(top_part_layout)
        main_layout.addLayout(bottom_button_layout)

        # 초기 상태 설정
        self.populate_list()
        self.editor_widget.setEnabled(False)
        self.connect_editors()

    def connect_editors(self):
        self.name_edit.textChanged.connect(self.update_rule_data)
        self.enabled_check.stateChanged.connect(self.update_rule_data)
        self.column_combo.currentTextChanged.connect(self.update_rule_data)
        self.operator_combo.currentTextChanged.connect(self.update_rule_data)
        self.value_edit.textChanged.connect(self.update_rule_data)

    def populate_list(self):
        self.list_widget.clear()
        for rule in self.rules:
            item = QListWidgetItem(rule.get("name", "Unnamed Rule"))
            self.list_widget.addItem(item)
        if self.rules:
            self.list_widget.setCurrentRow(0)
            self.on_item_selected(self.list_widget.item(0))

    def on_item_selected(self, item):
        self.current_item = item
        row = self.list_widget.row(item)
        rule = self.rules[row]
        
        self.editor_widget.setEnabled(True)
        self.name_edit.setText(rule.get("name", ""))
        self.enabled_check.setChecked(rule.get("enabled", True))
        self.column_combo.setCurrentText(rule.get("column", ""))
        self.operator_combo.setCurrentText(rule.get("operator", "contains"))
        self.value_edit.setText(rule.get("value", ""))
        self.update_color_button('foreground', rule.get("foreground"))
        self.update_color_button('background', rule.get("background"))
        
    def update_rule_data(self):
        if not self.current_item: return
        row = self.list_widget.row(self.current_item)
        rule = self.rules[row]
        
        rule['name'] = self.name_edit.text()
        rule['enabled'] = self.enabled_check.isChecked()
        rule['column'] = self.column_combo.currentText()
        rule['operator'] = self.operator_combo.currentText()
        rule['value'] = self.value_edit.text()
        self.current_item.setText(rule['name'])

    def pick_color(self, target):
        if not self.current_item: return
        row = self.list_widget.row(self.current_item)
        rule = self.rules[row]
        
        initial_color = rule.get(target)
        color = QColorDialog.getColor(QColor(initial_color) if initial_color else Qt.GlobalColor.white, self)
        
        if color.isValid():
            hex_color = color.name()
            rule[target] = hex_color
            self.update_color_button(target, hex_color)

    def update_color_button(self, target, hex_color):
        button = self.fg_button if target == 'foreground' else self.bg_button
        text = target.capitalize()
        if hex_color:
            button.setText(f"{text}: {hex_color}")
            button.setStyleSheet(f"background-color: {hex_color}; color: {self.get_contrasting_color(hex_color)}")
        else:
            button.setText(f"{text}: None")
            button.setStyleSheet("")

    def get_contrasting_color(self, hex_color):
        color = QColor(hex_color)
        return 'white' if color.lightness() < 128 else 'black'

    def add_new_rule(self):
        new_rule = {"name": "New Rule", "enabled": True, "column": self.column_names[0], "operator": "contains", "value": "", "foreground": "#ff0000", "background": None}
        self.rules.append(new_rule)
        self.populate_list()
        self.list_widget.setCurrentRow(len(self.rules) - 1)
        self.on_item_selected(self.list_widget.item(len(self.rules) - 1))

    def remove_selected_rule(self):
        if not self.current_item: return
        row = self.list_widget.row(self.current_item)
        if QMessageBox.question(self, "Confirm", f"Are you sure you want to delete rule '{self.rules[row]['name']}'?") == QMessageBox.StandardButton.Yes:
            del self.rules[row]
            self.populate_list()
            self.editor_widget.setEnabled(False)
            self.current_item = None

    def load_rules(self):
        if not os.path.exists(HIGHLIGHTERS_FILE):
            return []
        try:
            with open(HIGHLIGHTERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error loading highlighting rules: {e}")
            return []

    def save_rules(self):
        try:
            with open(HIGHLIGHTERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.rules, f, indent=4)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save rules:\n{e}")
            return False

    def accept(self):
        """OK 버튼을 누르면 변경사항을 적용하고 저장한 뒤 창을 닫습니다."""
        self.apply_changes() # ✅ 변경사항을 먼저 적용하는 함수 호출
        super().accept()     # 그 다음에 창을 닫습니다 (저장은 apply_changes에 포함됨)
    
    def apply_changes(self):
        if self.save_rules():
            # In a real app, you would emit a signal here to apply the changes live
            print("Changes applied and saved.")
            self.parent().controller.apply_new_highlighting_rules()