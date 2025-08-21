import sys
import json
import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QListWidget, QListWidgetItem, QColorDialog,
                               QFrame, QLabel, QLineEdit, QComboBox, QCheckBox,
                               QMessageBox, QWidget, QGridLayout)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

HIGHLIGHTERS_FILE = 'highlighters.json'

# (ColorButton, ConditionWidget 클래스는 이전과 동일하므로 생략)
class ColorButton(QPushButton):
    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        self.set_color(color); self.setFixedSize(28, 28)
    def set_color(self, color):
        self._color = color
        if color: self.setStyleSheet(f"background-color: {color}; border: 1px solid #888; border-radius: 5px;")
        else: self.setStyleSheet("background-color: transparent; border: 1px dashed #888; border-radius: 5px;")
    def get_color(self): return self._color

class ConditionWidget(QWidget):
    def __init__(self, column_names, condition_data=None, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self); self.layout.setContentsMargins(0,0,0,0)
        self.column_combo = QComboBox(); self.column_combo.addItems(column_names)
        self.operator_combo = QComboBox(); self.operator_combo.addItems(["contains", "equals", "starts with", "ends with"])
        self.value_edit = QLineEdit(); self.remove_button = QPushButton("－"); self.remove_button.setFixedSize(24,24)
        self.layout.addWidget(self.column_combo, 2); self.layout.addWidget(self.operator_combo, 1); self.layout.addWidget(self.value_edit, 3); self.layout.addWidget(self.remove_button)
        if condition_data:
            self.column_combo.setCurrentText(condition_data.get("column", "")); self.operator_combo.setCurrentText(condition_data.get("operator", "contains")); self.value_edit.setText(condition_data.get("value", ""))
    def get_data(self):
        return {"column": self.column_combo.currentText(), "operator": self.operator_combo.currentText(), "value": self.value_edit.text()}

class HighlightingDialog(QDialog):
    def __init__(self, column_names, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conditional Highlighting Rules")
        self.column_names = column_names
        self.rules = self.load_rules()
        self.current_item = None
        self.setMinimumSize(800, 500)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 왼쪽: 규칙 리스트 ---
        left_panel = QFrame()
        left_panel.setObjectName("leftPanel")
        left_panel.setStyleSheet("#leftPanel { background-color: #e8e8e8; border-right: 1px solid #dcdcdc; }")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(1, 8, 1, 8)
        
        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self.on_item_selected)
        self.list_widget.setStyleSheet("""
            QListWidget { border: none; background-color: transparent; }
            QListWidget::item { padding: 8px 12px; }
            QListWidget::item:selected { background-color: #c7c7c7; color: black; border-radius: 5px; }
        """)
        left_layout.addWidget(self.list_widget) # ✅ Stretch factor 없이 추가

        # ✅ 버튼 레이아웃을 QFrame으로 감싸서 최소 크기를 보장
        button_container = QFrame()
        list_button_layout = QHBoxLayout()
        add_button = QPushButton("Add Rule") # 텍스트를 명확하게 변경
        add_button.setMinimumHeight(30)      # ✅ 최소 높이를 지정하여 버튼 크기 확보
        add_button.clicked.connect(self.add_new_rule)
        
        remove_button = QPushButton("Remove Rule") # 텍스트를 명확하게 변경
        remove_button.setMinimumHeight(30)       # ✅ 최소 높이를 지정하여 버튼 크기 확보
        remove_button.clicked.connect(self.remove_selected_rule)
        
        list_button_layout.addWidget(add_button)
        list_button_layout.addWidget(remove_button)
        list_button_layout.addStretch()
        left_layout.addLayout(list_button_layout) # ✅ QFrame으로 감싸지 않고 직접 추가
        
        # --- 오른쪽: 규칙 에디터 (이전과 동일) ---
        self.editor_widget = QWidget()
        right_layout = QVBoxLayout(self.editor_widget)
        right_layout.setContentsMargins(20, 20, 20, 20)
        self.name_edit = QLineEdit()
        self.enabled_check = QCheckBox("Enable this rule")
        self.conditions_area = QWidget()
        self.conditions_layout = QVBoxLayout(self.conditions_area)
        add_condition_button = QPushButton("+ Add Condition")
        add_condition_button.clicked.connect(self.add_condition_widget_action)
        format_frame = QFrame()
        format_frame.setFrameShape(QFrame.Shape.StyledPanel)
        format_layout = QGridLayout(format_frame)
        self.fg_button = ColorButton()
        self.fg_button.clicked.connect(lambda: self.pick_color('foreground'))
        format_layout.addWidget(QLabel("Text Color:"), 0, 0); format_layout.addWidget(self.fg_button, 0, 1)
        self.bg_button = ColorButton()
        self.bg_button.clicked.connect(lambda: self.pick_color('background'))
        format_layout.addWidget(QLabel("Background Color:"), 1, 0); format_layout.addWidget(self.bg_button, 1, 1)
        format_layout.setColumnStretch(2, 1)
        right_layout.addWidget(QLabel("<b>Rule Name</b>")); right_layout.addWidget(self.name_edit)
        right_layout.addWidget(self.enabled_check); right_layout.addSpacing(20)
        right_layout.addWidget(QLabel("<b>Conditions (all must be true)</b>")); right_layout.addWidget(self.conditions_area)
        right_layout.addWidget(add_condition_button, 0, Qt.AlignmentFlag.AlignLeft); right_layout.addSpacing(20)
        right_layout.addWidget(QLabel("<b>Formatting</b>")); right_layout.addWidget(format_frame)
        right_layout.addStretch()
        bottom_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self.apply_changes)
        bottom_layout.addStretch()
        bottom_layout.addWidget(ok_button)
        bottom_layout.addWidget(apply_button)
        bottom_layout.addWidget(cancel_button)
        right_panel = QWidget(); right_panel_layout = QVBoxLayout(right_panel)
        right_panel_layout.addWidget(self.editor_widget); right_panel_layout.addLayout(bottom_layout)
        main_layout.addWidget(left_panel, 1); main_layout.addWidget(right_panel, 3)

                # ✅ 1. UI 로딩 중인지 상태를 알려주는 플래그(깃발) 추가
        self._loading_rule = False
        self.populate_list()
        self.editor_widget.setEnabled(False)
        self.connect_editors()

    def on_item_selected(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            self.editor_widget.setEnabled(False)
            self.current_item = None
            return
            
        self.current_item = selected_items[0]
        row = self.list_widget.row(self.current_item)
        
        # ✅ IndexError 방지를 위한 안전장치
        if not (0 <= row < len(self.rules)):
            print(f"Warning: Selection index {row} out of range for rules list size {len(self.rules)}.")
            self.editor_widget.setEnabled(False)
            return

        rule = self.rules[row]

        # ✅ 1. "지금부터 UI에 데이터 채울 거니까, 업데이트 잠시 중단!"
        self._loading_rule = True

        self.editor_widget.setEnabled(True)
        self.name_edit.setText(rule.get("name", ""))
        self.enabled_check.setChecked(rule.get("enabled", True))
        self.fg_button.set_color(rule.get("foreground"))
        self.bg_button.set_color(rule.get("background"))
        self.rebuild_condition_widgets(rule)

        # ✅ 2. "데이터 채우기 끝! 이제 다시 업데이트 허용."
        self._loading_rule = False

    def populate_list(self):
        # selectionChanged 시그널을 잠시 비활성화하여 불필요한 호출 방지
        self.list_widget.itemSelectionChanged.disconnect(self.on_item_selected)
        self.list_widget.clear()
        for rule in self.rules:
            item = QListWidgetItem(rule.get("name", "Unnamed Rule"))
            self.list_widget.addItem(item)
        # 시그널을 다시 연결
        self.list_widget.itemSelectionChanged.connect(self.on_item_selected)

        if self.rules:
            self.list_widget.setCurrentRow(0)
        else:
            # 규칙이 없으면 에디터 비활성화
            self.on_item_selected()

    # (이하 나머지 메소드들은 이전과 동일합니다)
    def connect_editors(self): self.name_edit.textChanged.connect(self.update_rule_data); self.enabled_check.stateChanged.connect(self.update_rule_data)
    def rebuild_condition_widgets(self, rule):
        while self.conditions_layout.count():
            child = self.conditions_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        for cond_data in rule.get("conditions", []): self.add_condition_widget_to_layout(cond_data)
    def add_condition_widget_to_layout(self, condition_data=None):
        cond_widget = ConditionWidget(self.column_names, condition_data); cond_widget.remove_button.clicked.connect(lambda: self.remove_condition_widget(cond_widget)); cond_widget.column_combo.currentTextChanged.connect(self.update_rule_data); cond_widget.operator_combo.currentTextChanged.connect(self.update_rule_data); cond_widget.value_edit.textChanged.connect(self.update_rule_data); self.conditions_layout.addWidget(cond_widget)
    def add_condition_widget_action(self):
        if not self.current_item: return
        self.add_condition_widget_to_layout(); self.update_rule_data()
    def remove_condition_widget(self, widget):
        widget.deleteLater(); self.update_rule_data()
    def update_rule_data(self):
        # ✅ '업데이트 금지' 깃발이 세워져 있으면 즉시 함수 종료
        if self._loading_rule:
            return
        
        if not self.current_item: return
        row = self.list_widget.row(self.current_item)
        if not (0 <= row < len(self.rules)): return
        rule = self.rules[row]
        rule['name'] = self.name_edit.text(); rule['enabled'] = self.enabled_check.isChecked(); self.current_item.setText(rule['name'])
        conditions = []
        for i in range(self.conditions_layout.count()):
            widget = self.conditions_layout.itemAt(i).widget()
            if isinstance(widget, ConditionWidget): conditions.append(widget.get_data())
        rule['conditions'] = conditions
    def pick_color(self, target):
        if not self.current_item: return
        row = self.list_widget.row(self.current_item); rule = self.rules[row]; button = self.fg_button if target == 'foreground' else self.bg_button; initial_color = button.get_color(); color = QColorDialog.getColor(QColor(initial_color) if initial_color else Qt.GlobalColor.white, self)
        if color.isValid(): hex_color = color.name(); rule[target] = hex_color; button.set_color(hex_color)
    def add_new_rule(self):
        new_rule = {
                    "name": "New Rule", 
                    "enabled": True, 
                    "conditions": [{"column": self.column_names[0], "operator": "contains", "value": ""}], 
                    "foreground": "#ff0000", "background": None
                    }
        self.rules.append(new_rule)
        self.populate_list()
        self.list_widget.setCurrentRow(len(self.rules) - 1)

    def remove_selected_rule(self):
        if not self.current_item: return
        row = self.list_widget.row(self.current_item)
        if QMessageBox.question(self, "Confirm", f"Are you sure you want to delete rule '{self.rules[row]['name']}'?") == QMessageBox.StandardButton.Yes:
            del self.rules[row]; self.populate_list()
    def load_rules(self):
        if not os.path.exists(HIGHLIGHTERS_FILE): return []
        try:
            with open(HIGHLIGHTERS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except Exception: return []
    def save_rules(self):
        self.update_rule_data()
        try:
            with open(HIGHLIGHTERS_FILE, 'w', encoding='utf-8') as f: json.dump(self.rules, f, indent=4); return True
        except Exception as e: QMessageBox.critical(self, "Error", f"Could not save rules:\n{e}"); return False
    def accept(self):
        """OK 버튼: 변경사항을 저장 및 적용하고 창을 닫습니다."""
        # ✅ 1. UI의 현재 상태를 내부 데이터로 먼저 업데이트합니다.
        self.update_rule_data()
    
        if self.save_rules(): 
            self.parent().controller.apply_new_highlighting_rules()
            super().accept()

    def apply_changes(self):
        """Apply 버튼: 변경사항을 저장하고 실시간으로 적용합니다."""
        # ✅ 2. UI의 현재 상태를 내부 데이터로 먼저 업데이트합니다.
        self.update_rule_data()
    
        if self.save_rules(): 
            self.parent().controller.apply_new_highlighting_rules()

