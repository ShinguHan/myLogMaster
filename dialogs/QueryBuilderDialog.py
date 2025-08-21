from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem, 
    QComboBox, QInputDialog, QWidget
)
from PySide6.QtCore import QDateTime, Qt
from .ConditionWidget import ConditionWidget

class QueryBuilderDialog(QDialog):
    def __init__(self, column_names, date_columns, saved_filters, last_query=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Query Builder")
        self.setGeometry(150, 150, 800, 500)
        self.column_names = column_names
        self.date_columns = date_columns
        self.saved_filters = saved_filters

        self.main_layout = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.main_layout.addWidget(self.tree)

        button_layout = QHBoxLayout()
        self.load_button = QPushButton("Load Filter")
        self.save_button = QPushButton("Save Filter As...")
        self.run_button = QPushButton("Run Filter")
        self.close_button = QPushButton("Close")
        
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.save_button)
        button_layout.addStretch()
        button_layout.addWidget(self.run_button)
        button_layout.addWidget(self.close_button)
        self.main_layout.addLayout(button_layout)
        
        self.run_button.clicked.connect(self.accept)
        self.close_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.save_filter)
        self.load_button.clicked.connect(self.load_filter)

                # ⭐️ 2. last_query 데이터가 있으면 UI를 복원하고, 없으면 기본 그룹 추가
        if last_query:
            self._populate_from_data(self.tree, last_query)
        else:
            self._add_group_item(self.tree)

        # self._add_group_item(self.tree)

    def save_filter(self):
        name, ok = QInputDialog.getText(self, "Save Filter As...", "Enter a name for this filter:")
        if ok and name:
            query_data = self.get_query_data()
            if query_data:
                self.saved_filters[name] = query_data
                print(f"Filter '{name}' prepared for saving.")

    def load_filter(self):
        filter_names = list(self.saved_filters.keys())
        if not filter_names:
            return
        
        name, ok = QInputDialog.getItem(self, "Load Filter", "Select a filter to load:", filter_names, 0, False)
        if ok and name:
            query_data = self.saved_filters[name]
            self.tree.clear()
            self._populate_from_data(self.tree, query_data)

    def _populate_from_data(self, parent_item, data):
        if 'logic' in data: # It's a group
            group_item = self._add_group_item(parent_item)
            group_widget = self.tree.itemWidget(group_item, 0)
            logic_combo = group_widget.findChild(QComboBox)
            if logic_combo:
                logic_combo.setCurrentText(data['logic'])
            
            for rule in data.get('rules', []):
                self._populate_from_data(group_item, rule)
        else: # It's a condition
            cond_item = self._add_condition_item(parent_item)
            cond_widget = self.tree.itemWidget(cond_item, 0)
            cond_widget.column_combo.setCurrentText(data.get('column', ''))
            cond_widget.operator_combo.setCurrentText(data.get('operator', ''))
            
            value = data.get('value')
            if isinstance(value, str):
                cond_widget.text_input.setText(value)
            elif isinstance(value, list) and len(value) == 2: # Date Range
                cond_widget.date_from.setDateTime(QDateTime.fromString(value[0], Qt.DateFormat.ISODate))
                cond_widget.date_to.setDateTime(QDateTime.fromString(value[1], Qt.DateFormat.ISODate))
            elif value: # Single Date
                cond_widget.date_input.setDateTime(QDateTime.fromString(value, Qt.DateFormat.ISODate))

    def _add_group_item(self, parent_item):
        group_item = QTreeWidgetItem(parent_item)
        group_widget = QWidget()
        group_layout = QHBoxLayout(group_widget)
        group_layout.setContentsMargins(5, 5, 5, 5)
        logic_combo = QComboBox()
        logic_combo.addItems(["AND", "OR"])
        add_condition_btn = QPushButton("+ Condition")
        add_group_btn = QPushButton("+ Group")
        remove_btn = QPushButton("-")
        group_layout.addWidget(logic_combo)
        group_layout.addWidget(add_condition_btn)
        group_layout.addWidget(add_group_btn)
        group_layout.addStretch()
        group_layout.addWidget(remove_btn)
        self.tree.setItemWidget(group_item, 0, group_widget)
        add_condition_btn.clicked.connect(lambda: self._add_condition_item(group_item))
        add_group_btn.clicked.connect(lambda: self._add_group_item(group_item))
        if parent_item != self.tree:
            remove_btn.clicked.connect(lambda: parent_item.removeChild(group_item))
        else:
            remove_btn.setEnabled(False)
        if isinstance(parent_item, QTreeWidgetItem):
            parent_item.setExpanded(True)
        return group_item

    def _add_condition_item(self, parent_item):
        condition_item = QTreeWidgetItem(parent_item)
        condition_widget = ConditionWidget(self.column_names, self.date_columns)
        condition_widget.remove_clicked.connect(lambda w: parent_item.removeChild(condition_item))
        self.tree.setItemWidget(condition_item, 0, condition_widget)
        parent_item.setExpanded(True)
        return condition_item

    def get_query_data(self):
        root = self.tree.invisibleRootItem()
        if root.childCount() > 0:
            return self._get_data_from_item(root.child(0))
        return None

    # ⭐️ 여기가 버그의 핵심 원인이었습니다. 로직을 수정합니다.
    def _get_data_from_item(self, item):
        widget = self.tree.itemWidget(item, 0)

        # 아이템이 '개별 조건' 위젯인지 먼저 확인
        if isinstance(widget, ConditionWidget):
            cond = widget.get_condition()
            value = cond['value']
            
            # QDateTime 객체를 ISO 포맷 문자열로 변환하여 JSON으로 저장/전송 가능하게 함
            if isinstance(value, QDateTime):
                cond['value'] = value.toString(Qt.DateFormat.ISODate)
            elif isinstance(value, tuple):
                cond['value'] = (value[0].toString(Qt.DateFormat.ISODate), value[1].toString(Qt.DateFormat.ISODate))
            
            # 값이 비어있지 않은 조건만 유효한 것으로 간주
            if (isinstance(cond['value'], str) and cond['value']) or not isinstance(cond['value'], str):
                return cond
        
        # '개별 조건'이 아니라면 '그룹'으로 간주
        else:
            logic_combo = widget.findChild(QComboBox)
            if not logic_combo: return None

            logic = logic_combo.currentText()
            rules = []
            for i in range(item.childCount()):
                child_rule = self._get_data_from_item(item.child(i))
                if child_rule: 
                    rules.append(child_rule)
            
            if rules: 
                return {"logic": logic, "rules": rules}
        
        return None