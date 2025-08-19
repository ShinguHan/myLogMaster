# shinguhan/mylogmaster/myLogMaster-main/dialogs/DashboardDialog.py

import pandas as pd
from PySide6.QtWidgets import QDialog, QGridLayout
from PySide6.QtCore import QTimer
# ✅ QWebEngineView는 PySide6에 기본 포함되어 있습니다.
from PySide6.QtWebEngineWidgets import QWebEngineView
import plotly.express as px

class DashboardDialog(QDialog):
    def __init__(self, initial_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Real-time Dashboard")
        self.setGeometry(150, 150, 1000, 700)
        self.layout = QGridLayout(self)

        # 이 변수는 이제 QWebEngineView 위젯들을 저장합니다.
        self.web_views = {}
        
        self._create_chart_views()
        
        # 업데이트가 필요한 데이터를 저장할 변수
        self.data_to_update = initial_data

        # 성능을 위한 업데이트 타이머
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(1000)  # 1초 간격
        self.update_timer.timeout.connect(self._perform_update)
        self.update_timer.start() 

    def _create_chart_views(self):
        """각 차트를 위한 QWebEngineView 위젯을 생성하고 레이아웃에 추가합니다."""
        self.web_views['by_category'] = QWebEngineView()
        self.web_views['by_device'] = QWebEngineView()

        self.layout.addWidget(self.web_views['by_category'], 0, 0)
        self.layout.addWidget(self.web_views['by_device'], 0, 1)
        
        # 대화상자가 열리자마자 차트를 한번 그려줍니다.
        self._perform_update()

    def update_dashboard(self, new_data):
        """컨트롤러에서 새로운 데이터를 받아 저장하는 공개 메소드입니다."""
        self.data_to_update = new_data

    def _perform_update(self):
        """타이머가 주기적으로 호출하여 모든 차트를 업데이트하는 메소드입니다."""
        if self.data_to_update is None or self.data_to_update.empty:
            return

        df = self.data_to_update
        print(f"Dashboard updating with {len(df)} rows...")

        # --- Category 파이 차트 ---
        category_counts = df['Category'].value_counts().reset_index()
        fig_cat = px.pie(category_counts, names='Category', values='count', title="Log Counts by Category")
        self.web_views['by_category'].setHtml(fig_cat.to_html(include_plotlyjs='cdn'))

        # --- DeviceID 바 차트 ---
        device_counts = df['DeviceID'].value_counts().reset_index().head(10)
        fig_dev = px.bar(device_counts, x='DeviceID', y='count', title="Log Counts by DeviceID (Top 10)")
        self.web_views['by_device'].setHtml(fig_dev.to_html(include_plotlyjs='cdn'))

    def closeEvent(self, event):
        """대화상자가 닫힐 때 타이머를 정지시킵니다."""
        self.update_timer.stop()
        super().closeEvent(event)