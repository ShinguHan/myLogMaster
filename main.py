import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton
from connection_manager import ConnectionManager # Updated import
from log_analyzer import AnalysisWindow

class AppLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SECS/GEM Tool Suite")
        self.setFixedSize(400, 200)

        self.sim_button = QPushButton("Open Connection Manager")
        self.sim_button.clicked.connect(self.open_connection_manager)

        self.analyzer_button = QPushButton("Open Log Analyzer")
        self.analyzer_button.clicked.connect(self.open_analyzer)

        layout = QVBoxLayout()
        layout.addWidget(self.sim_button)
        layout.addWidget(self.analyzer_button)
        
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.manager_window = None
        self.analyzer_window = None

    def open_connection_manager(self):
        if not self.manager_window:
            self.manager_window = ConnectionManager()
        self.manager_window.show()

    def open_analyzer(self):
        # The factory is passed in case the analyzer needs message definitions later
        if not self.analyzer_window:
            from message_factory import MessageFactory
            self.analyzer_window = AnalysisWindow(MessageFactory())
        self.analyzer_window.show()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    launcher = AppLauncher()
    launcher.show()
    sys.exit(app.exec())
