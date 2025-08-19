# shinguhan/mylogmaster/myLogMaster-main/dialogs/DashboardDialog.py

# ... (기존 import)

class DashboardDialog(QDialog):
    def __init__(self, initial_data, parent=None):
        super().__init__(parent)
        # ...
        self.web_views = {}
        
        # ✅ 1. 마지막으로 차트를 그렸던 데이터를 저장할 변수 추가
        self.last_rendered_data = None
        self.data_to_update = initial_data
        
        self._create_chart_views()
        
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(1000)
        self.update_timer.timeout.connect(self._perform_update)
        # __init__에서는 타이머를 시작하지 않습니다.

    # ... (_create_chart_views는 동일)

    def update_dashboard(self, new_data):
        self.data_to_update = new_data

    def _perform_update(self):
        """타이머가 호출하여 차트를 업데이트합니다. 데이터가 변경됐을 때만 다시 그립니다."""
        if self.data_to_update is None or self.data_to_update.empty:
            return

        # ✅ 2. 현재 데이터와 마지막으로 그렸던 데이터가 동일하면, 아무것도 하지 않고 반환 (깜빡임 방지)
        if self.data_to_update.equals(self.last_rendered_data):
            return
        
        df = self.data_to_update
        # 마지막으로 그린 데이터를 현재 데이터로 업데이트
        self.last_rendered_data = df.copy()
        
        print(f"Dashboard updating with {len(df)} rows...")
        # ... (차트 그리는 로직은 동일)
        category_counts = df['Category'].value_counts().reset_index()
        fig_cat = px.pie(category_counts, names='Category', values='count', title="Log Counts by Category")
        self.web_views['by_category'].setHtml(fig_cat.to_html(include_plotlyjs='cdn'))

        device_counts = df['DeviceID'].value_counts().reset_index().head(10)
        fig_dev = px.bar(device_counts, x='DeviceID', y='count', title="Log Counts by DeviceID (Top 10)")
        self.web_views['by_device'].setHtml(fig_dev.to_html(include_plotlyjs='cdn'))

    # ✅ 3. 타이머를 제어하는 새로운 메소드들 추가
    def start_updates(self):
        """대시보드 실시간 업데이트를 시작합니다."""
        print("Dashboard updates started.")
        self.update_timer.start()

    def stop_updates(self):
        """대시보드 실시간 업데이트를 중지합니다."""
        print("Dashboard updates stopped.")
        self.update_timer.stop()

    def closeEvent(self, event):
        self.stop_updates() # 창이 닫힐 때도 타이머 정지
        super().closeEvent(event)