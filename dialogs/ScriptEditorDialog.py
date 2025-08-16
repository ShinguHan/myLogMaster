import re
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QSplitter,
    QFileDialog, QMessageBox
)

DEFAULT_SCRIPT_TEMPLATE = """
# logs: 현재 필터링된 로그 데이터 (Pandas DataFrame)
# result: 분석 결과를 애플리케이션에 전달하는 객체
def analyze(logs, result):
    print(f"분석할 로그 수: {len(logs)}개")
    
    # --- 분석 결과 API 사용 예시 ---
    
    # 1. 최종 요약 메시지 설정
    # result.set_summary("여기에 최종 분석 요약을 입력하세요.")
    
    # 2. 특정 행에 마커(하이라이트) 추가 (다음 단계에서 구현 예정)
    # if not logs.empty:
    #     first_row_index = logs.index[0]
    #     result.add_marker(first_row_index, "첫 번째 로그", "lightblue")

    # 3. 새로 생성한 데이터를 별도 창으로 표시
    # import pandas as pd
    # new_data = {'col1': [1, 2], 'col2': [3, 4]}
    # new_df = pd.DataFrame(new_data)
    # result.show_dataframe(new_df, title="새로운 분석 결과")
    
    return "분석이 완료되었습니다."

"""

class PythonSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = ["def", "return", "if", "else", "elif", "for", "in", "while", "break", "continue", "import", "from", "as", "class", "True", "False", "None"]
        self.highlighting_rules.extend([(re.compile(f"\\b{word}\\b"), keyword_format) for word in keywords])
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        self.highlighting_rules.append((re.compile("\".*\""), string_format))
        self.highlighting_rules.append((re.compile("'.*'"), string_format))
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        self.highlighting_rules.append((re.compile("#[^\n]*"), comment_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), format)

class ScriptEditorDialog(QDialog):
    run_script_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Analysis Script Editor")
        self.setGeometry(200, 200, 800, 600)

        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)

        self.code_editor = QTextEdit()
        self.code_editor.setFontFamily("Courier New")
        self.highlighter = PythonSyntaxHighlighter(self.code_editor.document())
        
        self.result_output = QTextEdit()
        self.result_output.setReadOnly(True)
        self.result_output.setFontFamily("Courier New")
        
        splitter.addWidget(self.code_editor)
        splitter.addWidget(self.result_output)
        splitter.setSizes([400, 200])
        main_layout.addWidget(splitter)

        button_layout = QHBoxLayout()
        new_btn = QPushButton("New Script")
        load_btn = QPushButton("Load Script")
        save_btn = QPushButton("Save Script As...")
        run_btn = QPushButton("Run Script")
        close_btn = QPushButton("Close")

        button_layout.addWidget(new_btn)
        button_layout.addWidget(load_btn)
        button_layout.addWidget(save_btn)
        button_layout.addStretch()
        button_layout.addWidget(run_btn)
        button_layout.addWidget(close_btn)
        main_layout.addLayout(button_layout)
        
        run_btn.clicked.connect(self._on_run_clicked)
        close_btn.clicked.connect(self.reject)
        load_btn.clicked.connect(self.load_script)
        save_btn.clicked.connect(self.save_script)
        new_btn.clicked.connect(self.new_script)
        
        # ⭐️ 빠뜨렸던 이 한 줄을 추가합니다.
        self.new_script()

    def _on_run_clicked(self):
        self.result_output.clear()
        self.result_output.setText("Running analysis script...")
        script_code = self.code_editor.toPlainText()
        self.run_script_requested.emit(script_code)

    def set_result(self, result_text):
        self.result_output.setText(result_text)

    def new_script(self):
        self.code_editor.setText(DEFAULT_SCRIPT_TEMPLATE)
        self.result_output.clear()

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