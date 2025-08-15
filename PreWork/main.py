import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton
from connection_manager import ConnectionManager
from log_analyzer import AnalysisWindow
from history_window import HistoryWindow
from trend_analysis_window import TrendAnalysisWindow # New Import
import database_handler

class AppLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SECS/GEM Tool Suite")
        self.setFixedSize(400, 300)

        self.sim_button = QPushButton("Open Connection Manager")
        self.sim_button.clicked.connect(self.open_connection_manager)

        self.analyzer_button = QPushButton("Open Log Analyzer")
        self.analyzer_button.clicked.connect(self.open_analyzer)
        
        self.history_button = QPushButton("View Test History")
        self.history_button.clicked.connect(self.open_history)

        self.trends_button = QPushButton("View Trend Analysis") # New Button
        self.trends_button.clicked.connect(self.open_trends)

        layout = QVBoxLayout()
        layout.addWidget(self.sim_button)
        layout.addWidget(self.analyzer_button)
        layout.addWidget(self.history_button)
        layout.addWidget(self.trends_button)
        
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.manager_window = None
        self.analyzer_window = None
        self.history_window = None
        self.trends_window = None

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
        self.history_window = HistoryWindow()
        self.history_window.show()

    def open_trends(self):
        self.trends_window = TrendAnalysisWindow()
        self.trends_window.show()

if __name__ == '__main__':
    database_handler.initialize_database()
    app = QApplication(sys.argv)
    launcher = AppLauncher()
    launcher.show()
    sys.exit(app.exec())
