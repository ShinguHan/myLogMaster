import json
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
                               QListWidget, QListWidgetItem, QColorDialog,
                               QFrame, QLabel, QLineEdit, QComboBox, QCheckBox,
                               QMessageBox, QWidget, QGridLayout)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt, Signal
from .ui_components import create_section_label, create_action_button

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
    rules_updated = Signal(list)

    def __init__(self, column_names, rules_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conditional Highlighting Rules")
        self.column_names = column_names
        self.rules = rules_data
        self.current_item = None
        self.setMinimumSize(800, 500)
        
        self._loading_rule = False
        self._init_ui()
        
        self.populate_list()
        self.editor_widget.setEnabled(False)
        self.connect_editors()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        left_panel = QFrame()
        left_panel.setObjectName("leftPanel")
        left_panel.setStyleSheet("#leftPanel { background-color: #e8e8e8; border-right: 1px solid #dcdcdc; }")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(1, 8, 1, 8)
        
        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self.on_item_selected)
        left_layout.addWidget(self.list_widget)

        list_button_layout = QHBoxLayout()
        add_button = create_action_button("Add Rule")
        add_button.clicked.connect(self.add_new_rule)
        remove_button = create_action_button("Remove Rule")
        remove_button.clicked.connect(self.remove_selected_rule)
        list_button_layout.addWidget(add_button)
        list_button_layout.addWidget(remove_button)
        left_layout.addLayout(list_button_layout)
        
        self.editor_widget = QWidget()
        right_layout = QVBoxLayout(self.editor_widget)
        right_layout.setContentsMargins(20, 20, 20, 20)
        
        right_layout.addWidget(create_section_label("Rule Name"))
        self.name_edit = QLineEdit()
        right_layout.addWidget(self.name_edit)
        self.enabled_check = QCheckBox("Enable this rule")
        right_layout.addWidget(self.enabled_check); right_layout.addSpacing(20)
        
        right_layout.addWidget(create_section_label("Conditions (all must be true)"))
        self.conditions_area = QWidget()
        self.conditions_layout = QVBoxLayout(self.conditions_area)
        right_layout.addWidget(self.conditions_area)
        add_condition_button = create_action_button("+ Add Condition")
        add_condition_button.setStyleSheet("padding: 5px 10px;")
        add_condition_button.clicked.connect(self.add_condition_widget_action)
        right_layout.addWidget(add_condition_button, 0, Qt.AlignmentFlag.AlignLeft); right_layout.addSpacing(20)
        
        right_layout.addWidget(create_section_label("Formatting"))
        format_frame = QFrame(); format_frame.setFrameShape(QFrame.Shape.StyledPanel)
        format_layout = QGridLayout(format_frame)
        self.fg_button = ColorButton()
        self.fg_button.clicked.connect(lambda: self.pick_color('foreground'))
        format_layout.addWidget(QLabel("Text Color:"), 0, 0); format_layout.addWidget(self.fg_button, 0, 1)
        self.bg_button = ColorButton()
        self.bg_button.clicked.connect(lambda: self.pick_color('background'))
        format_layout.addWidget(QLabel("Background Color:"), 1, 0); format_layout.addWidget(self.bg_button, 1, 1)
        format_layout.setColumnStretch(2, 1)
        right_layout.addWidget(format_frame)
        right_layout.addStretch()

        bottom_layout = QHBoxLayout()
        ok_button = create_action_button("OK", is_default=True)
        ok_button.clicked.connect(self.accept)
        cancel_button = create_action_button("Cancel")
        cancel_button.clicked.connect(self.reject)
        apply_button = create_action_button("Apply")
        apply_button.clicked.connect(self.apply_changes)
        bottom_layout.addStretch()
        bottom_layout.addWidget(ok_button); bottom_layout.addWidget(apply_button); bottom_layout.addWidget(cancel_button)
        
        right_panel = QWidget(); right_panel_layout = QVBoxLayout(right_panel)
        right_panel_layout.addWidget(self.editor_widget); right_panel_layout.addLayout(bottom_layout)
        main_layout.addWidget(left_panel, 1); main_layout.addWidget(right_panel, 3)

    def on_item_selected(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            self.editor_widget.setEnabled(False); self.current_item = None; return
        self.current_item = selected_items[0]
        row = self.list_widget.row(self.current_item)
        if not (0 <= row < len(self.rules)): return
        
        self._loading_rule = True
        rule = self.rules[row]
        self.editor_widget.setEnabled(True)
        self.name_edit.setText(rule.get("name", ""))
        self.enabled_check.setChecked(rule.get("enabled", True))
        self.fg_button.set_color(rule.get("foreground"))
        self.bg_button.set_color(rule.get("background"))
        self.rebuild_condition_widgets(rule)
        self._loading_rule = False

    def populate_list(self):
        self.list_widget.itemSelectionChanged.disconnect(self.on_item_selected)
        self.list_widget.clear()
        for rule in self.rules:
            self.list_widget.addItem(QListWidgetItem(rule.get("name", "Unnamed Rule")))
        self.list_widget.itemSelectionChanged.connect(self.on_item_selected)
        if self.rules: self.list_widget.setCurrentRow(0)
        else: self.on_item_selected()

    def connect_editors(self):
        self.name_edit.textChanged.connect(self.update_rule_data)
        self.enabled_check.stateChanged.connect(self.update_rule_data)

    def rebuild_condition_widgets(self, rule):
        while self.conditions_layout.count():
            child = self.conditions_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        for cond_data in rule.get("conditions", []): self.add_condition_widget_to_layout(cond_data)

    def add_condition_widget_to_layout(self, condition_data=None):
        cond_widget = ConditionWidget(self.column_names, condition_data)
        cond_widget.remove_button.clicked.connect(lambda: self.remove_condition_widget(cond_widget))
        cond_widget.column_combo.currentTextChanged.connect(self.update_rule_data)
        cond_widget.operator_combo.currentTextChanged.connect(self.update_rule_data)
        cond_widget.value_edit.textChanged.connect(self.update_rule_data)
        self.conditions_layout.addWidget(cond_widget)

    def add_condition_widget_action(self):
        if not self.current_item: return
        self.add_condition_widget_to_layout(); self.update_rule_data()

    def remove_condition_widget(self, widget):
        widget.deleteLater(); self.update_rule_data()

    def update_rule_data(self):
        if self._loading_rule or not self.current_item: return
        row = self.list_widget.row(self.current_item)
        if not (0 <= row < len(self.rules)): return
        
        rule = self.rules[row]
        rule['name'] = self.name_edit.text()
        rule['enabled'] = self.enabled_check.isChecked()
        self.current_item.setText(rule['name'])
        
        # 💥 변경점: for 루프를 리스트 컴프리헨션으로 변경
        rule['conditions'] = [
            self.conditions_layout.itemAt(i).widget().get_data()
            for i in range(self.conditions_layout.count())
            if isinstance(self.conditions_layout.itemAt(i).widget(), ConditionWidget)
        ]

    def pick_color(self, target):
        if not self.current_item: return
        row = self.list_widget.row(self.current_item); rule = self.rules[row]
        button = self.fg_button if target == 'foreground' else self.bg_button
        initial_color = button.get_color()
        color = QColorDialog.getColor(QColor(initial_color) if initial_color else Qt.GlobalColor.white, self)
        if color.isValid():
            rule[target] = color.name(); button.set_color(color.name())

    def add_new_rule(self):
        new_rule = {"name": "New Rule", "enabled": True, "conditions": [{"column": self.column_names[0], "operator": "contains", "value": ""}], "foreground": "#ff0000", "background": None}
        self.rules.append(new_rule)
        self.populate_list()
        self.list_widget.setCurrentRow(len(self.rules) - 1)

    def remove_selected_rule(self):
        if not self.current_item: return
        row = self.list_widget.row(self.current_item)
        if QMessageBox.question(self, "Confirm", f"Are you sure you want to delete rule '{self.rules[row]['name']}'?") == QMessageBox.StandardButton.Yes:
            del self.rules[row]; self.populate_list()

    def accept(self):
        self.update_rule_data()
        self.rules_updated.emit(self.rules)
        super().accept()

    def apply_changes(self):
        self.update_rule_data()
        self.rules_updated.emit(self.rules)

