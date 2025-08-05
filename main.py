import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton
from connection_manager import ConnectionManager
from log_analyzer import AnalysisWindow
from history_window import HistoryWindow # New Import
import database_handler # New Import

class AppLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SECS/GEM Tool Suite")
        self.setFixedSize(400, 250)

        self.sim_button = QPushButton("Open Connection Manager")
        self.sim_button.clicked.connect(self.open_connection_manager)

        self.analyzer_button = QPushButton("Open Log Analyzer")
        self.analyzer_button.clicked.connect(self.open_analyzer)
        
        self.history_button = QPushButton("View Test History") # New Button
        self.history_button.clicked.connect(self.open_history)

        layout = QVBoxLayout()
        layout.addWidget(self.sim_button)
        layout.addWidget(self.analyzer_button)
        layout.addWidget(self.history_button)
        
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.manager_window = None
        self.analyzer_window = None
        self.history_window = None

    def open_connection_manager(self):
        if not self.manager_window:
            self.manager_window = ConnectionManager()
        self.manager_window.show()

    def open_analyzer(self):
        if not self.analyzer_window:
            from message_factory import MessageFactory
            self.analyzer_window = AnalysisWindow(MessageFactory())
        self.analyzer_window.show()

    def open_history(self):
        # Re-create the window each time to ensure it shows the latest data
        self.history_window = HistoryWindow()
        self.history_window.show()

if __name__ == '__main__':
    # Initialize the database on startup
    database_handler.initialize_database()
    
    app = QApplication(sys.argv)
    launcher = AppLauncher()
    launcher.show()
    sys.exit(app.exec())
