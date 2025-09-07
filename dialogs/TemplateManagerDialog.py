import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QWidget,
    QListWidget, QListWidgetItem, QLabel, QLineEdit, QTextEdit,
    QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt
from .ui_components import create_section_label, create_action_button

class TemplateManagerDialog(QDialog):
    """사용자 정의 쿼리 템플릿을 관리하는 다이얼로그"""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Query Template Manager")
        self.controller = controller
        self.templates = self.controller.load_query_templates()
        self.current_template_name = None
        
        self.setMinimumSize(800, 500)
        self._init_ui()
        self.populate_list()
        
        # UI 초기 상태 설정
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        else:
            self.editor_widget.setEnabled(False)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left Panel: Template List ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(create_section_label("Templates"))
        
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self.display_template_details)
        left_layout.addWidget(self.list_widget)
        
        list_button_layout = QHBoxLayout()
        new_button = create_action_button("New")
        new_button.clicked.connect(self.new_template)
        delete_button = create_action_button("Delete")
        delete_button.clicked.connect(self.delete_template)
        list_button_layout.addWidget(new_button)
        list_button_layout.addWidget(delete_button)
        left_layout.addLayout(list_button_layout)

        # --- Right Panel: Editor ---
        self.editor_widget = QWidget()
        right_layout = QVBoxLayout(self.editor_widget)
        
        right_layout.addWidget(create_section_label("Template Name"))
        self.name_edit = QLineEdit()
        right_layout.addWidget(self.name_edit)
        
        right_layout.addWidget(create_section_label("Description"))
        self.desc_edit = QTextEdit()
        self.desc_edit.setFixedHeight(60)
        right_layout.addWidget(self.desc_edit)

        right_layout.addWidget(create_section_label("Query (SELECT statement)"))
        self.query_edit = QTextEdit()
        self.query_edit.setFontFamily("Consolas")
        self.query_edit.setAcceptRichText(False)
        right_layout.addWidget(self.query_edit)

        splitter.addWidget(left_panel)
        splitter.addWidget(self.editor_widget)
        splitter.setSizes([200, 600])
        main_layout.addWidget(splitter)
        
        # --- Bottom Buttons ---
        bottom_buttons = QHBoxLayout()
        save_button = create_action_button("Save & Close", is_default=True)
        save_button.clicked.connect(self.save_and_close)
        cancel_button = create_action_button("Cancel")
        cancel_button.clicked.connect(self.reject)
        bottom_buttons.addStretch()
        bottom_buttons.addWidget(save_button)
        bottom_buttons.addWidget(cancel_button)
        main_layout.addLayout(bottom_buttons)

    def populate_list(self):
        self.list_widget.clear()
        for name in sorted(self.templates.keys()):
            self.list_widget.addItem(QListWidgetItem(name))

    def display_template_details(self, current_item, previous_item):
        if not current_item:
            self.editor_widget.setEnabled(False)
            return

        self.update_current_template_from_ui(previous_item)
        
        self.editor_widget.setEnabled(True)
        self.current_template_name = current_item.text()
        details = self.templates.get(self.current_template_name, {})
        
        self.name_edit.setText(self.current_template_name)
        self.desc_edit.setText(details.get("description", ""))
        self.query_edit.setText(details.get("query", ""))
        
    def new_template(self):
        name, ok = QInputDialog.getText(self, "New Template", "Enter a name for the new template:")
        if ok and name:
            if name in self.templates:
                QMessageBox.warning(self, "Name Exists", "A template with this name already exists.")
                return
            
            self.templates[name] = {"description": "", "query": "SELECT * FROM V_LOG_MESSAGE WHERE "}
            self.populate_list()
            # 새로 만든 아이템을 선택 상태로 만듦
            items = self.list_widget.findItems(name, Qt.MatchFlag.MatchExactly)
            if items:
                self.list_widget.setCurrentItem(items[0])

    def delete_template(self):
        if not self.current_template_name: return
        
        reply = QMessageBox.question(self, "Confirm Delete", 
            f"Are you sure you want to delete the template '{self.current_template_name}'?")
        if reply == QMessageBox.StandardButton.Yes:
            del self.templates[self.current_template_name]
            self.current_template_name = None
            self.populate_list()
            
    def update_current_template_from_ui(self, list_item):
        """리스트 선택이 변경될 때, 이전에 편집 중이던 내용을 self.templates에 임시 저장"""
        if not list_item: return
        
        original_name = list_item.text()
        if original_name not in self.templates: return

        self.templates[original_name] = {
            "description": self.desc_edit.toPlainText(),
            "query": self.query_edit.toPlainText()
        }
        
        new_name = self.name_edit.text()
        if original_name != new_name:
            if new_name in self.templates:
                QMessageBox.warning(self, "Name Exists", f"The name '{new_name}' already exists. Reverting.")
                self.name_edit.setText(original_name)
            else:
                self.templates[new_name] = self.templates.pop(original_name)
                list_item.setText(new_name)

    def save_and_close(self):
        self.update_current_template_from_ui(self.list_widget.currentItem())
        self.controller.save_query_templates(self.templates)
        QMessageBox.information(self, "Success", "Query templates saved successfully.")
        self.accept()
