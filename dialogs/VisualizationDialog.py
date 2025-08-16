from PySide6.QtWidgets import QDialog, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView

class VisualizationDialog(QDialog):
    def __init__(self, mermaid_code, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SECS Scenario Visualization")
        self.setGeometry(200, 200, 800, 600)

        layout = QVBoxLayout(self)
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        # Mermaid.js를 포함한 HTML 템플릿
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ background-color: #f0f0f0; }} /* 배경색을 앱과 유사하게 조정 */
            </style>
        </head>
        <body>
            <pre class="mermaid">
                {mermaid_code}
            </pre>
            <script type="module">
                import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }});
            </script>
        </body>
        </html>
        """
        self.web_view.setHtml(html_content)