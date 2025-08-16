import pandas as pd

class AnalysisResult:
    """분석 스크립트의 결과를 담기 위한 데이터 클래스"""
    def __init__(self):
        self.summary = ""
        self.markers = []  # (row_index, message, color) 튜플의 리스트
        self.new_dataframe = None
        self.new_df_title = ""
        self.captured_output = ""

    def set_summary(self, text):
        self.summary = str(text)

    def add_marker(self, row_index, message, color="yellow"):
        self.markers.append((row_index, message, color))

    def show_dataframe(self, df: pd.DataFrame, title="Analysis Result"):
        self.new_dataframe = df
        self.new_df_title = title