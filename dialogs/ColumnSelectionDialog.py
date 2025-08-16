from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QDialogButtonBox, QAbstractItemView
)

class ColumnSelectionDialog(QDialog):
    def __init__(self, all_columns, visible_columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Columns to Display")

        self.layout = QVBoxLayout(self)
        
        # 다중 선택이 가능한 리스트 위젯 생성
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.list_widget.addItems(all_columns)

        # 현재 보이는 컬럼들을 선택된 상태로 설정
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.text() in visible_columns:
                item.setSelected(True)

        # 확인, 취소 버튼
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout.addWidget(self.list_widget)
        self.layout.addWidget(self.button_box)

    def get_selected_columns(self):
        """사용자가 선택한 컬럼들의 리스트를 반환합니다."""
        return [item.text() for item in self.list_widget.selectedItems()]