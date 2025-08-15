from PySide6.QtWidgets import QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from dashboard_generator import generate_dashboard_html

class TrendAnalysisWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Trend Analysis Dashboard")
        self.setGeometry(250, 250, 1000, 600)

        self.browser = QWebEngineView()
        self.setCentralWidget(self.browser)

        self.load_dashboard()

    def load_dashboard(self):
        html_content = generate_dashboard_html()
        self.browser.setHtml(html_content)
