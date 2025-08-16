import pandas as pd
from PySide6.QtWidgets import QDialog, QVBoxLayout
import pyqtgraph as pg
import numpy as np # NumPy 임포트

class DashboardDialog(QDialog):
    def __init__(self, df, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log Statistics Dashboard")
        self.setGeometry(200, 200, 900, 700)
        self.df = df

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self._create_flow_chart()) # 메서드 이름 변경
        main_layout.addWidget(self._create_category_chart())

    # ⭐️ 메서드 전체를 새롭고 단순한 로직으로 교체
    def _create_flow_chart(self):
        """전체 로그를 100개의 구간으로 나누어 막대그래프로 표시합니다."""
        widget = pg.PlotWidget(title="Overall Log Flow (100 Bins)")
        widget.getAxis('left').setLabel("Log Count")
        widget.getAxis('bottom').setLabel("Log Sequence Bins")
        
        try:
            if self.df.empty: return widget

            num_logs = len(self.df)
            num_bins = 1000
            
            # 데이터가 100개 미만일 경우 처리
            if num_logs < num_bins:
                num_bins = num_logs
            
            # NumPy를 사용하여 매우 빠르게 구간별 합계 계산
            bin_counts = np.histogram(np.arange(num_logs), bins=num_bins)[0]

            # 막대 그래프 생성
            bar_graph = pg.BarGraphItem(x=range(num_bins), height=bin_counts, width=0.8, brush='c')
            widget.addItem(bar_graph)

        except Exception as e:
            print(f"Error creating flow chart: {e}")

        return widget

    def _create_category_chart(self):
        """로그 카테고리 분포 막대 차트를 생성합니다."""
        widget = pg.PlotWidget(title="Log Category Distribution")
        
        try:
            if self.df.empty or 'Category' not in self.df.columns:
                return widget

            category_counts = self.df['Category'].str.replace('"', '', regex=False).value_counts()
            
            if category_counts.empty:
                return widget

            ticks = [(i, category) for i, category in enumerate(category_counts.index)]
            axis = widget.getAxis('bottom')
            axis.setTicks([ticks])
            axis.setLabel("Category")
            widget.getAxis('left').setLabel("Count")
            
            bar_graph = pg.BarGraphItem(x=range(len(category_counts)), height=category_counts.values, width=0.6, brush='m')
            widget.addItem(bar_graph)

        except Exception as e:
            print(f"Error creating category chart: {e}")

        return widget