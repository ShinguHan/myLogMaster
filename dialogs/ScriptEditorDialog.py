import re
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QSplitter,
    QFileDialog, QMessageBox
)

# 간단한 Python 문법 하이라이터 클래스
class PythonSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        # Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "def", "return", "if", "else", "elif", "for", "in", "while", 
            "break", "continue", "import", "from", "as", "class", "True", "False", "None"
        ]
        self.highlighting_rules.extend([(re.compile(f"\\b{word}\\b"), keyword_format) for word in keywords])

        # Strings (single and double quotes)
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        self.highlighting_rules.append((re.compile("\".*\""), string_format))
        self.highlighting_rules.append((re.compile("'.*'"), string_format))

        # Comments
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        self.highlighting_rules.append((re.compile("#[^\n]*"), comment_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), format)

# 스크립트 편집기 메인 다이얼로그
class ScriptEditorDialog(QDialog):
    # 'Run' 버튼 클릭 시, 작성된 코드를 메인 윈도우에 전달하는 시그널
    run_script_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Analysis Script Editor")
        self.setGeometry(200, 200, 800, 600)

        # UI 구성
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 코드 편집기
        self.code_editor = QTextEdit()
        self.code_editor.setFontFamily("Courier New")
        self.highlighter = PythonSyntaxHighlighter(self.code_editor.document())
        
        # 결과 표시창
        self.result_output = QTextEdit()
        self.result_output.setReadOnly(True)
        self.result_output.setFontFamily("Courier New")
        
        splitter.addWidget(self.code_editor)
        splitter.addWidget(self.result_output)
        splitter.setSizes([400, 200])
        main_layout.addWidget(splitter)

        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        load_btn = QPushButton("Load Script")
        save_btn = QPushButton("Save Script As...")
        run_btn = QPushButton("Run Script")
        close_btn = QPushButton("Close")

        button_layout.addWidget(load_btn)
        button_layout.addWidget(save_btn)
        button_layout.addStretch()
        button_layout.addWidget(run_btn)
        button_layout.addWidget(close_btn)
        main_layout.addLayout(button_layout)
        
        # 시그널 연결
        run_btn.clicked.connect(self._on_run_clicked)
        close_btn.clicked.connect(self.reject)
        load_btn.clicked.connect(self.load_script)
        save_btn.clicked.connect(self.save_script)

    def _on_run_clicked(self):
        self.result_output.clear()
        self.result_output.setText("Running analysis script...")
        script_code = self.code_editor.toPlainText()
        self.run_script_requested.emit(script_code)

    def set_result(self, result_text):
        self.result_output.setText(result_text)

    def load_script(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Python Script", "", "Python Files (*.py)")
        if filepath:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.code_editor.setText(f.read())

    def save_script(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Python Script As...", "", "Python Files (*.py)")
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.code_editor.toPlainText())