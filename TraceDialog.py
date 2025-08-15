from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QTableView
from PySide6.QtCore import QSortFilterProxyModel, Qt
from LogTableModel import LogTableModel

class TraceDialog(QDialog):
    def __init__(self, trace_data, trace_id, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Event Trace for ID: {trace_id}")
        self.setGeometry(150, 150, 1000, 700)

        # 레이아웃 및 위젯 설정
        layout = QVBoxLayout(self)
        
        filter_input = QLineEdit()
        filter_input.setPlaceholderText("Refine trace results...")
        layout.addWidget(filter_input)
        
        table_view = QTableView()
        table_view.setSortingEnabled(True)
        table_view.setAlternatingRowColors(True)
        layout.addWidget(table_view)

        # 모델 설정 (메인 윈도우와 동일한 구조)
        source_model = LogTableModel(trace_data)
        
        proxy_model = QSortFilterProxyModel()
        proxy_model.setSourceModel(source_model)
        proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        proxy_model.setFilterKeyColumn(-1)
        
        table_view.setModel(proxy_model)
        
        filter_input.textChanged.connect(proxy_model.setFilterFixedString)
        
        table_view.resizeColumnsToContents()