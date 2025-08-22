from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, 
                               QTableWidgetItem, QHeaderView)
from PySide6.QtCore import Signal

class HistoryBrowserDialog(QDialog):
    # 사용자가 특정 이력을 더블클릭했음을 알리는 신호
    history_selected = Signal(int)

    def __init__(self, history_df, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Validation History")
        self.setMinimumSize(800, 500)

        layout = QVBoxLayout(self)
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(len(history_df.columns))
        self.table_widget.setHorizontalHeaderLabels(history_df.columns)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        layout.addWidget(self.table_widget)
        self.populate_table(history_df)

    def populate_table(self, df):
        self.table_widget.setRowCount(len(df))
        for row in range(len(df)):
            for col in range(len(df.columns)):
                item = QTableWidgetItem(str(df.iloc[row, col]))
                self.table_widget.setItem(row, col, item)

    def on_item_double_clicked(self, item):
        run_id_item = self.table_widget.item(item.row(), 0) # run_id는 첫 번째 컬럼
        try:
            run_id = int(run_id_item.text())
            self.history_selected.emit(run_id)
        except (ValueError, TypeError):
            pass