from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton,
    QPushButton, QScrollArea, QWidget, QDialogButtonBox, QTreeWidget, 
    QTreeWidgetItem, QComboBox
)
from .ConditionWidget import ConditionWidget

class QueryBuilderDialog(QDialog):
    def __init__(self, column_names, date_columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Query Builder (Tree View)")
        self.setGeometry(150, 150, 800, 500)
        self.column_names = column_names
        self.date_columns = date_columns

        # 메인 레이아웃
        self.main_layout = QVBoxLayout(self)

        # 1. 트리 위젯 생성
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.main_layout.addWidget(self.tree)

        # 2. 확인/취소 버튼
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(button_box)

        # 시작할 때 최상위 루트 그룹 하나 추가
        self._add_group_item(self.tree)

    def _add_group_item(self, parent_item):
        """트리에 새로운 '그룹' 아이템을 추가합니다."""
        group_item = QTreeWidgetItem(parent_item)
        
        group_widget = QWidget()
        group_layout = QHBoxLayout(group_widget)
        group_layout.setContentsMargins(0, 0, 0, 0)
        
        logic_combo = QComboBox()
        logic_combo.addItems(["AND", "OR"])
        
        add_condition_btn = QPushButton("+ Add Condition")
        add_group_btn = QPushButton("+ Add Group")
        remove_btn = QPushButton("- Remove Group")

        group_layout.addWidget(logic_combo)
        group_layout.addWidget(add_condition_btn)
        group_layout.addWidget(add_group_btn)
        group_layout.addWidget(remove_btn)
        
        self.tree.setItemWidget(group_item, 0, group_widget)

        add_condition_btn.clicked.connect(lambda: self._add_condition_item(group_item))
        add_group_btn.clicked.connect(lambda: self._add_group_item(group_item))

        if parent_item != self.tree:
            remove_btn.clicked.connect(lambda: parent_item.removeChild(group_item))
        else:
            remove_btn.setEnabled(False)

        # ⭐️ 부모가 QTreeWidgetItem일 경우에만 확장하도록 수정
        if isinstance(parent_item, QTreeWidgetItem):
            parent_item.setExpanded(True)


    def _add_condition_item(self, parent_item):
        """트리에 새로운 '조건' 아이템을 추가합니다."""
        condition_item = QTreeWidgetItem(parent_item)
        condition_widget = ConditionWidget(self.column_names, self.date_columns)
        
        condition_widget.remove_clicked.connect(
            lambda w: parent_item.removeChild(condition_item)
        )
        
        self.tree.setItemWidget(condition_item, 0, condition_widget)
        parent_item.setExpanded(True)

    def get_query_data(self):
        """트리 구조를 순회하며 중첩된 쿼리 딕셔너리를 생성합니다."""
        root = self.tree.invisibleRootItem()
        if root.childCount() > 0:
            return self._get_data_from_item(root.child(0))
        return None

    def _get_data_from_item(self, item):
        """트리 아이템으로부터 재귀적으로 데이터를 수집합니다."""
        widget = self.tree.itemWidget(item, 0)

        # 아이템이 '그룹'인 경우 (콤보박스가 있는지 확인)
        if isinstance(widget.layout().itemAt(0).widget(), QComboBox):
            logic = widget.layout().itemAt(0).widget().currentText()
            rules = []
            for i in range(item.childCount()):
                child_rule = self._get_data_from_item(item.child(i))
                if child_rule:
                    rules.append(child_rule)
            
            if rules:
                return {"logic": logic, "rules": rules}

        # 아이템이 '조건'인 경우
        elif isinstance(widget, ConditionWidget):
            cond = widget.get_condition()
            value = cond['value']
            if (isinstance(value, str) and value) or not isinstance(value, str):
                return cond
        
        return None