from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
import database_handler

class HistoryWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test Run History")
        self.setGeometry(200, 200, 800, 600)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Scenario Name", "Result", "Duration"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.table)
        self.setCentralWidget(container)
        
        self.load_history()

    def load_history(self):
        results = database_handler.get_all_results()
        self.table.setRowCount(len(results))
        for i, row_data in enumerate(results):
            for j, cell_data in enumerate(row_data):
                self.table.setItem(i, j, QTableWidgetItem(str(cell_data)))
