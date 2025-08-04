from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QFileDialog

def generate_html_report(report):
    """Generates a self-contained HTML string from a report dictionary."""
    result_color = "green" if report['result'] == "Pass" else "red"
    steps_html = "".join(f"<li>{step}</li>\n" for step in report['steps'])

    html = f"""
    <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Test Report: {report['name']}</title>
    <style>
        body {{ font-family: sans-serif; margin: 2em; }} h1, h2 {{ color: #333; }}
        .summary {{ border: 1px solid #ccc; padding: 1em; margin-bottom: 1em; }}
        .result-pass {{ color: green; font-weight: bold; }} .result-fail {{ color: red; font-weight: bold; }}
        ul {{ list-style-type: none; padding-left: 0; }}
        li {{ background: #f9f9f9; border: 1px solid #eee; padding: 0.5em; margin-bottom: 0.5em; }}
    </style></head><body>
        <h1>Test Report: {report['name']}</h1>
        <div class="summary">
            <p><strong>Overall Result:</strong> <span class="result-{result_color.lower()}">{report['result']}</span></p>
            <p><strong>Duration:</strong> {report['duration']}</p>
        </div>
        <h2>Steps</h2><ul>{steps_html}</ul>
    </body></html>
    """
    return html

class ReportDialog(QDialog):
    def __init__(self, report, parent=None):
        super().__init__(parent)
        self.report = report
        self.setWindowTitle(f"Test Report: {report['name']}")
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        
        details = (f"Overall Result: {report['result']}\n"
                   f"Duration: {report['duration']}\n\n"
                   f"--- Steps ---\n" +
                   "\n".join(report['steps']))
        self.details_text.setText(details)
        
        layout.addWidget(self.details_text)

        # FIX: Changed 'buttons' to 'self.buttons' to make it an instance variable
        self.buttons = QDialogButtonBox()
        self.buttons.addButton("OK", QDialogButtonBox.AcceptRole)
        self.buttons.addButton("Save Report...", QDialogButtonBox.ActionRole)
        
        self.buttons.accepted.connect(self.accept)
        self.buttons.clicked.connect(self.handle_button_click)

        layout.addWidget(self.buttons)

    def handle_button_click(self, button):
        # FIX: Now correctly references 'self.buttons'
        if self.buttons.buttonRole(button) == QDialogButtonBox.ActionRole:
            self.save_report()

    def save_report(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Report", "", "HTML Files (*.html)")
        if filepath:
            html_content = generate_html_report(self.report)
            with open(filepath, 'w') as f:
                f.write(html_content)